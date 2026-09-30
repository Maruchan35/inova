"""Busca el sitio web oficial de cada municipio y comprueba que de verdad sea el suyo.

    python recolector/sitios.py

Lee documentos/_catalogo/municipios.csv (de catalogo.py) y escribe documentos/_catalogo/sitios_municipales.csv.

De dónde salen los sitios:
1. Wikidata: el "sitio web oficial" registrado para cada clave INEGI (muchos son de
   administraciones pasadas y ya no existen: por eso se comprueban todos).
2. Dominios .gob.mx armados con el nombre: irapuato.gob.mx, tepejidelriohgo.gob.mx,
   municipiodurango.gob.mx, guanajuatocapital.gob.mx...

Un sitio cuenta como verificado solo si abre y su página de inicio habla de un gobierno municipal
("ayuntamiento", "municipio"...) y menciona al municipio (y al estado, si hay otro municipio con
el mismo nombre en otro estado).
"""

import asyncio
import re
from collections import defaultdict
from urllib.parse import urlsplit

import httpx

from comun import AGENTE, DNS, FUENTES, escribir_csv, leer_csv, palabras

WIKIDATA = "https://query.wikidata.org/sparql"
CONSULTA = "SELECT ?clave ?sitio WHERE { ?item wdt:P3801 ?clave . ?item wdt:P856 ?sitio }"

# Cómo abrevia cada estado en los dominios municipales (tepejidelriohgo.gob.mx) y su subdominio estatal
# (algunos estados alojan a sus municipios: tierrablanca.guanajuato.gob.mx).
DOMINIO_ESTADO = {
    "01": ("ags", "aguascalientes"), "02": ("bc", "bajacalifornia"), "03": ("bcs", "bcs"),
    "04": ("camp", "campeche"), "05": ("coah", "coahuila"), "06": ("col", "colima"),
    "07": ("chis", "chiapas"), "08": ("chih", "chihuahua"), "09": ("cdmx", "cdmx"),
    "10": ("dgo", "durango"), "11": ("gto", "guanajuato"), "12": ("gro", "guerrero"),
    "13": ("hgo", "hidalgo"), "14": ("jal", "jalisco"), "15": ("edomex", "edomex"),
    "16": ("mich", "michoacan"), "17": ("mor", "morelos"), "18": ("nay", "nayarit"),
    "19": ("nl", "nl"), "20": ("oax", "oaxaca"), "21": ("pue", "puebla"), "22": ("qro", "queretaro"),
    "23": ("qroo", "qroo"), "24": ("slp", "slp"), "25": ("sin", "sinaloa"), "26": ("son", "sonora"),
    "27": ("tab", "tabasco"), "28": ("tamps", "tamaulipas"), "29": ("tlax", "tlaxcala"),
    "30": ("ver", "veracruz"), "31": ("yuc", "yucatan"), "32": ("zac", "zacatecas"),
}

# Portales de los gobiernos estatales: si un candidato cae ahí, no es el sitio del municipio.
PORTALES_ESTATALES = {
    "aguascalientes.gob.mx", "baja.gob.mx", "bcs.gob.mx", "campeche.gob.mx", "coahuila.gob.mx",
    "col.gob.mx", "chiapas.gob.mx", "chihuahua.gob.mx", "cdmx.gob.mx", "durango.gob.mx",
    "guanajuato.gob.mx", "guerrero.gob.mx", "hidalgo.gob.mx", "jalisco.gob.mx", "edomex.gob.mx",
    "michoacan.gob.mx", "morelos.gob.mx", "nayarit.gob.mx", "nl.gob.mx", "oaxaca.gob.mx",
    "puebla.gob.mx", "queretaro.gob.mx", "qroo.gob.mx", "slp.gob.mx", "sinaloa.gob.mx",
    "sonora.gob.mx", "tabasco.gob.mx", "tamaulipas.gob.mx", "tlaxcala.gob.mx", "veracruz.gob.mx",
    "yucatan.gob.mx", "zacatecas.gob.mx", "gob.mx",
}

CONECTORES = {"de", "del", "la", "las", "los", "el", "y"}
GENERICAS = {"san", "santa", "santo", "santiago", "santa maria", "villa", "heroica", "ciudad", "general",
             "nuevo", "nueva", "valle", "ejido", "magdalena", "santos", "reyes", "mineral"}
MARCAS_MUNICIPALES = ("ayuntamiento", "municipio", "municipal", "cabildo", "alcaldia", "presidencia municip")


def host(url: str) -> str:
    h = urlsplit(url if "//" in url else f"//{url}").hostname or ""
    return h.lower().removeprefix("www.")


def formas_del_nombre(nombre: str) -> list[str]:
    """'San Pedro Tlaquepaque' → ['sanpedrotlaquepaque', 'tlaquepaque', 'sanpedro']: cómo suele ir en el dominio."""
    p = palabras(nombre).split()
    formas = ["".join(p)]
    antes_de = []
    for w in p:
        if w in ("de", "del"):
            break
        antes_de.append(w)
    formas.append("".join(antes_de))                      # Tepatitlán de Morelos → tepatitlan
    sin_conectores = [w for w in p if w not in CONECTORES]
    formas.append("".join(sin_conectores))                # Ixtlahuacán de los Membrillos → ixtlahuacanmembrillos
    if len(p) > 1 and p[0] in ("san", "santa", "santo", "santiago", "heroica", "villa", "ciudad"):
        formas.append("".join(p[1:]))                     # Heroica Nogales → nogales
        formas.append(p[-1])                              # San Pedro Tlaquepaque → tlaquepaque
        formas.append("".join(p[:2]))                     # San Pedro Garza García → sanpedro
    vistas, salida = set(), []
    for f in formas:
        if len(f) >= 4 and f not in GENERICAS and f not in vistas:
            vistas.add(f)
            salida.append(f)
    return salida


def candidatos(m: dict) -> list[str]:
    abrev, sub = DOMINIO_ESTADO[m["clave_estado"]]
    hosts = []
    for f in formas_del_nombre(m["municipio"]):
        hosts += [f"{f}.gob.mx", f"{f}{abrev}.gob.mx", f"{f}.{sub}.gob.mx", f"municipio{f}.gob.mx",
                  f"municipiode{f}.gob.mx", f"{f}capital.gob.mx", f"capital{f}.gob.mx", f"capitalde{f}.gob.mx",
                  f"ayuntamiento{f}.gob.mx", f"{f}.gob.mx".replace(".gob.mx", "-" + abrev + ".gob.mx")]
    vistos = set()
    # Cada parte de un dominio admite máximo 63 letras (los nombres largos de Oaxaca se pasan).
    return [h for h in hosts if h not in PORTALES_ESTATALES and all(len(p) <= 63 for p in h.split("."))
            and not (h in vistos or vistos.add(h))]


def texto_visible(html: str) -> tuple[str, str]:
    titulo = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    cuerpo = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    cuerpo = re.sub(r"<[^>]+>", " ", cuerpo)
    return (" ".join(titulo.group(1).split()) if titulo else ""), cuerpo


async def abrir(cliente: httpx.AsyncClient, limite: asyncio.Semaphore, h: str) -> tuple[str, str, str] | None:
    """(url final, título, texto) de la página de inicio, o None si no abre."""
    async with limite:
        for url in (f"https://www.{h}/", f"https://{h}/", f"http://www.{h}/", f"http://{h}/"):
            try:
                r = await cliente.get(url)
            except (httpx.HTTPError, OSError, ValueError):
                continue
            if r.status_code < 400 and "html" in r.headers.get("content-type", "html"):
                titulo, texto = texto_visible(r.text[:600_000])
                return str(r.url), titulo, texto
        return None


def es_su_sitio(m: dict, titulo: str, texto: str, repetido: bool, estados: dict[str, str]) -> bool:
    t = f" {palabras(titulo + ' ' + texto)} "
    if not any(marca in t for marca in MARCAS_MUNICIPALES):
        return False
    nombre = palabras(m["municipio"])
    formas = [nombre] + [" ".join(w for w in nombre.split() if w not in CONECTORES)]
    corto = nombre.split(" de ")[0]
    if len(corto) >= 5 and corto not in GENERICAS:
        formas.append(corto)
    if not any(f" {f} " in t for f in formas):
        return False
    if repetido:
        estado = palabras(estados[m["clave_estado"]])
        variantes = {estado, estado.split(" de ")[0], DOMINIO_ESTADO[m["clave_estado"]][0]}
        return any(f" {v} " in t for v in variantes if v)
    return True


def wikidata() -> dict[str, list[str]]:
    r = httpx.get(WIKIDATA, params={"query": CONSULTA, "format": "json"}, headers={"User-Agent": AGENTE}, timeout=120)
    r.raise_for_status()
    sitios = defaultdict(list)
    for b in r.json()["results"]["bindings"]:
        sitios[b["clave"]["value"]].append(b["sitio"]["value"])
    return sitios


async def main() -> None:
    municipios = leer_csv(FUENTES / "municipios.csv")
    estados = {m["clave_estado"]: m["estado"] for m in municipios}
    cuantos = defaultdict(int)
    for m in municipios:
        cuantos[palabras(m["municipio"])] += 1

    wd = wikidata()
    print(f"Wikidata: {len(wd)} municipios con sitio registrado")

    por_municipio = {}
    for m in municipios:
        propios = [host(u) for u in wd.get(m["clave_inegi"], [])]
        por_municipio[m["clave_inegi"]] = [(h, "wikidata") for h in propios if h] + [
            (h, "dominio") for h in candidatos(m) if h not in propios]
    todos = sorted({h for lista in por_municipio.values() for h, _ in lista})
    print(f"Probando {len(todos)} dominios posibles...")
    async with DNS() as dns:
        existen = await asyncio.gather(*(dns.alguno_existe(h) for h in todos))
    vivos = {h for h, ok in zip(todos, existen) if ok}
    print(f"{len(vivos)} dominios existen; abriendo sus páginas de inicio...")

    limite = asyncio.Semaphore(48)
    async with httpx.AsyncClient(headers={"User-Agent": AGENTE}, timeout=20, follow_redirects=True,
                                 verify=False) as cliente:
        vivos = sorted(vivos)
        paginas = dict(zip(vivos, await asyncio.gather(*(abrir(cliente, limite, h) for h in vivos))))

    filas, usados = [], defaultdict(list)
    for m in municipios:
        repetido = cuantos[palabras(m["municipio"])] > 1
        fila = {**{k: m[k] for k in ("clave_inegi", "estado", "municipio")}, "sitio": "", "fuente": "",
                "verificado": "no", "titulo": ""}
        for h, fuente in por_municipio[m["clave_inegi"]]:
            pagina = paginas.get(h)
            if not pagina:
                continue
            url, titulo, texto = pagina
            if host(url) in PORTALES_ESTATALES:
                continue
            if es_su_sitio(m, titulo, texto, repetido, estados):
                fila.update(sitio=url, fuente=fuente, verificado="si", titulo=titulo[:150])
                usados[host(url)].append(m["clave_inegi"])
                break
            if fuente == "wikidata" and not fila["sitio"]:
                # Abre pero no se pudo confirmar (sitio en construcción, página de bienvenida...): se guarda sin verificar.
                fila.update(sitio=url, fuente=fuente, titulo=titulo[:150])
        filas.append(fila)

    # Un mismo sitio no puede ser de dos municipios: si pasa, se queda sin verificar en todos.
    for h, claves in usados.items():
        if len(claves) > 1:
            for f in filas:
                if f["clave_inegi"] in claves:
                    f["verificado"] = "revisar"

    escribir_csv(FUENTES / "sitios_municipales.csv", filas,
                 ["clave_inegi", "estado", "municipio", "sitio", "fuente", "verificado", "titulo"])
    ok = sum(f["verificado"] == "si" for f in filas)
    print(f"\n{ok} de {len(filas)} municipios con sitio oficial verificado; "
          f"{sum(bool(f['sitio']) and f['verificado'] != 'si' for f in filas)} por revisar → sitios_municipales.csv")
    for clave_estado in sorted(estados):
        del_estado = [f for f in filas if f["clave_inegi"][:2] == clave_estado]
        print(f"  {estados[clave_estado]}: {sum(f['verificado'] == 'si' for f in del_estado)}/{len(del_estado)}")


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    asyncio.run(main())
