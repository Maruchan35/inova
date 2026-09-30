"""Sitios oficiales de los 32 gobiernos estatales: portal, finanzas, transparencia, informe, obras, compras...

    python recolector/estatales.py

Prueba los subdominios típicos de cada portal estatal (finanzas.guanajuato.gob.mx,
transparencia.hidalgo.gob.mx, periodicooficial.col.gob.mx...) y algunos dominios propios conocidos
(sefintlax.gob.mx, finanzasoaxaca.gob.mx...). Guarda los que abren en documentos/_catalogo/sitios_estatales.csv,
con el tipo de fuente según su nombre. rastrear.py parte de ellos para buscar documentos.
"""

import asyncio
import warnings

import httpx

from comun import AGENTE, DNS, FUENTES, escribir_csv, leer_csv
from sitios import abrir, host, texto_visible

PORTAL = {
    "01": "aguascalientes.gob.mx", "02": "bajacalifornia.gob.mx", "03": "bcs.gob.mx", "04": "campeche.gob.mx",
    "05": "coahuila.gob.mx", "06": "col.gob.mx", "07": "chiapas.gob.mx", "08": "chihuahua.gob.mx",
    "09": "cdmx.gob.mx", "10": "durango.gob.mx", "11": "guanajuato.gob.mx", "12": "guerrero.gob.mx",
    "13": "hidalgo.gob.mx", "14": "jalisco.gob.mx", "15": "edomex.gob.mx", "16": "michoacan.gob.mx",
    "17": "morelos.gob.mx", "18": "nayarit.gob.mx", "19": "nl.gob.mx", "20": "oaxaca.gob.mx",
    "21": "puebla.gob.mx", "22": "queretaro.gob.mx", "23": "qroo.gob.mx", "24": "slp.gob.mx",
    "25": "sinaloa.gob.mx", "26": "sonora.gob.mx", "27": "tabasco.gob.mx", "28": "tamaulipas.gob.mx",
    "29": "tlaxcala.gob.mx", "30": "veracruz.gob.mx", "31": "yucatan.gob.mx", "32": "zacatecas.gob.mx",
}

# Dominios estatales que no cuelgan del portal (se prueban igual: si no abren, no se guardan).
PROPIOS = {
    "02": ["baja.gob.mx"], "07": ["haciendachiapas.gob.mx"], "15": ["ipomex.org.mx"],
    "18": ["hacienda-nayarit.gob.mx"], "20": ["finanzasoaxaca.gob.mx"], "24": ["slpfinanzas.gob.mx"],
    "29": ["sefintlax.gob.mx"],
}

# Congresos estatales: aprueban y publican las leyes de ingresos, presupuestos y cuentas públicas de
# cada municipio (la fuente más completa para los municipios que no tienen sitio propio).
CONGRESOS = {
    "01": "congresoags.gob.mx", "02": "congresobc.gob.mx", "03": "cbcs.gob.mx", "04": "congresocam.gob.mx",
    "05": "congresocoahuila.gob.mx", "06": "congresocol.gob.mx", "07": "congresochiapas.gob.mx",
    "08": "congresochihuahua.gob.mx", "09": "congresocdmx.gob.mx", "10": "congresodurango.gob.mx",
    "11": "congresogto.gob.mx", "12": "congresogro.gob.mx", "13": "congreso-hidalgo.gob.mx",
    "14": "congresojal.gob.mx", "15": "legislativoedomex.gob.mx", "16": "congresomich.gob.mx",
    "17": "congresomorelos.gob.mx", "18": "congresonayarit.gob.mx", "19": "hcnl.gob.mx",
    "20": "congresooaxaca.gob.mx", "21": "congresopuebla.gob.mx", "22": "legislaturaqueretaro.gob.mx",
    "23": "congresoqroo.gob.mx", "24": "congresoslp.gob.mx", "25": "congresosinaloa.gob.mx",
    "26": "congresoson.gob.mx", "27": "congresotabasco.gob.mx", "28": "congresotamaulipas.gob.mx",
    "29": "congresodetlaxcala.gob.mx", "30": "legisver.gob.mx", "31": "congresoyucatan.gob.mx",
    "32": "congresozac.gob.mx",
}

# Páginas conocidas que el sondeo de subdominios no encuentra (se comprueban igual antes de usarlas).
EXTRA = {
    "01": [("presupuesto", "https://www.aguascalientes.gob.mx/sefi/"),
           ("periodico_oficial", "https://eservicios2.aguascalientes.gob.mx/periodicooficial/")],
    "02": [("periodico_oficial", "https://periodicooficial.bajacalifornia.gob.mx/")],
    "03": [("portal", "https://www.bcs.gob.mx/"), ("presupuesto", "https://finanzas.bcs.gob.mx/"),
           ("presupuesto", "https://secfin.bcs.gob.mx/")],
    "06": [("periodico_oficial", "https://periodicooficial.col.gob.mx/"), ("informes", "https://plancolima.col.gob.mx/"),
           ("transparencia", "https://www.col.gob.mx/transparencia")],
    "07": [("presupuesto", "https://www.haciendachiapas.gob.mx/")],
    "08": [("presupuesto", "https://ihacienda.chihuahua.gob.mx/")],
    "18": [("portal", "https://www.nayarit.gob.mx/")],
    "22": [("portal", "https://www.queretaro.gob.mx/"), ("transparencia", "https://www.queretaro.gob.mx/transparencia/"),
           ("presupuesto", "https://www.queretaro.gob.mx/finanzas/")],
    "30": [("presupuesto", "https://www.veracruz.gob.mx/finanzas/"),
           ("transparencia", "https://www.veracruz.gob.mx/transparencia/"),
           ("periodico_oficial", "https://www.editoraveracruz.gob.mx/")],
}

# Páginas que abren pero no sirven para buscar documentos (inicios de sesión, instalaciones rotas...).
INSERVIBLES = ("login", "passwd", "install.php", "access-denied", "servicio=citas", "account/")

# Subdominio → tipo de fuente. El tipo coincide con las secciones de la plataforma cuando se puede.
SUBDOMINIOS = {
    "finanzas": "presupuesto", "hacienda": "presupuesto", "ihacienda": "presupuesto", "s-finanzas": "presupuesto",
    "sefin": "presupuesto", "sefina": "presupuesto", "safin": "presupuesto", "sfa": "presupuesto",
    "saf": "presupuesto", "spf": "presupuesto", "sefiplan": "presupuesto", "presupuesto": "presupuesto",
    "presupuestociudadano": "presupuesto", "egresos": "presupuesto", "armonizacion": "presupuesto",
    "informe": "informes", "informes": "informes", "planeacion": "informes", "seplan": "informes",
    "ped": "informes", "obras": "obras", "sop": "obras", "seop": "obras", "sidur": "obras",
    "infraestructura": "obras", "compras": "contratos", "licitaciones": "contratos",
    "adquisiciones": "contratos", "compranet": "contratos", "periodicooficial": "periodico_oficial",
    "periodico": "periodico_oficial", "poe": "periodico_oficial", "transparencia": "transparencia",
    "contraloria": "transparencia", "datos": "transparencia", "datosabiertos": "transparencia",
}


async def abrir_url(cliente: httpx.AsyncClient, limite: asyncio.Semaphore, url: str) -> tuple[str, str, str] | None:
    async with limite:
        try:
            r = await cliente.get(url)
        except (httpx.HTTPError, OSError, ValueError):
            return None
        if r.status_code >= 400:
            return None
        titulo, texto = texto_visible(r.text[:600_000])
        return str(r.url), titulo, texto


def tipo_de(h: str, portal: str) -> str:
    if h == portal:
        return "portal"
    if h in CONGRESOS.values():
        return "congreso"
    prefijo = h.removesuffix("." + portal)
    if prefijo in SUBDOMINIOS:
        return SUBDOMINIOS[prefijo]
    for clave, tipo in SUBDOMINIOS.items():
        if clave in h:
            return tipo
    return "otro"


async def main() -> None:
    estados = {e["clave_estado"]: e["estado"] for e in leer_csv(FUENTES / "estados.csv")}
    probar = []
    for clave, portal in PORTAL.items():
        probar += [(clave, portal)] + [(clave, f"{s}.{portal}") for s in SUBDOMINIOS]
        probar += [(clave, d) for d in PROPIOS.get(clave, [])] + [(clave, CONGRESOS[clave])]
    async with DNS() as dns:
        existen = await asyncio.gather(*(dns.alguno_existe(h) for _, h in probar))
    vivos = [p for p, ok in zip(probar, existen) if ok]
    print(f"{len(vivos)} de {len(probar)} dominios estatales existen; abriéndolos...")

    limite = asyncio.Semaphore(24)
    async with httpx.AsyncClient(headers={"User-Agent": AGENTE}, timeout=25, follow_redirects=True,
                                 verify=False) as cliente:
        paginas = await asyncio.gather(*(abrir(cliente, limite, h) for _, h in vivos))
        extra = [(clave, tipo, url) for clave, lista in EXTRA.items() for tipo, url in lista]
        paginas_extra = await asyncio.gather(*(abrir_url(cliente, limite, url) for _, _, url in extra))

    filas, vistos = [], set()
    candidatos = [(clave, tipo_de(h, PORTAL[clave]), h, p) for (clave, h), p in zip(vivos, paginas)]
    candidatos += [(clave, tipo, "", p) for (clave, tipo, _), p in zip(extra, paginas_extra)]
    for clave, tipo, h, pagina in candidatos:
        if not pagina or pagina[0] in vistos or any(x in pagina[0].lower() for x in INSERVIBLES):
            continue
        url, titulo, _ = pagina
        vistos.add(url)
        # Un subdominio que redirige al portal principal (o a otro lado) no aporta nada nuevo.
        if h and h != PORTAL[clave] and host(url) != h and url.rstrip("/").count("/") <= 2:
            continue
        filas.append({"clave_estado": clave, "estado": estados[clave], "tipo": tipo, "sitio": url,
                      "titulo": titulo[:150]})

    filas.sort(key=lambda f: (f["clave_estado"], f["tipo"] != "portal", f["tipo"], f["sitio"]))
    escribir_csv(FUENTES / "sitios_estatales.csv", filas, ["clave_estado", "estado", "tipo", "sitio", "titulo"])
    print(f"{len(filas)} sitios estatales → sitios_estatales.csv")
    for clave in sorted(estados):
        tipos = sorted({f["tipo"] for f in filas if f["clave_estado"] == clave})
        print(f"  {estados[clave]}: {', '.join(tipos) or 'NINGUNO'}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    asyncio.run(main())
