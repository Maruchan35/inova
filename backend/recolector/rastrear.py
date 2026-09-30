"""Recorre los sitios oficiales y separa por sección los documentos que encuentra (aquí no se descarga nada).

    python recolector/rastrear.py                        # estados y luego municipios (de mayor a menor población)
    python recolector/rastrear.py --solo estados
    python recolector/rastrear.py --solo municipios --estado 11
    python recolector/rastrear.py --paginas 60 --sitios 40

Lee documentos/_catalogo/sitios_estatales.csv y documentos/_catalogo/sitios_municipales.csv. Se puede interrumpir y
volver a ejecutar: salta los sitios que ya recorrió. Va agregando a:
- documentos/_catalogo/enlaces_<estados|municipios>.csv: cada documento (PDF, Excel...) con clave, estado, municipio, sección,
  título, año, dirección y la página donde apareció.
- documentos/_catalogo/rastreo_<estados|municipios>.csv: cómo le fue a cada sitio (páginas vistas, documentos encontrados o error).

Buenas prácticas: se identifica con su nombre, respeta robots.txt, pide una página a la vez por sitio
con pausa entre páginas y no pasa de N páginas por sitio.
"""

import argparse
import asyncio
import csv
import heapq
import itertools
from collections import defaultdict
import re
import time
import warnings
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from comun import AGENTE, EXTENSIONES_DOC, FUENTES, SECCIONES, anio, clasificar, escribir_csv, leer_csv, palabras

ENLACES = FUENTES / "enlaces.csv"
RASTREO = FUENTES / "rastreo.csv"
COL_ENLACES = ["clave", "estado", "municipio", "seccion", "titulo", "anio", "tipo", "url", "pagina", "sitio"]
COL_RASTREO = ["clave", "estado", "municipio", "sitio", "paginas", "documentos", "error", "segundos"]

# Enlaces que vale la pena seguir antes que los demás: menús de transparencia, finanzas, obras...
PISTAS = ("transparencia", "informe", "presupuest", "finanzas", "tesoreria", "hacienda", "egresos", "ingresos",
          "cuenta publica", "armonizacion", "conac", "ldf", "sevac", "obra", "cabildo", "actas", "gaceta",
          "licitacion", "contrat", "adquisicion", "compras", "documentos", "descargas", "publicaciones",
          "fraccion", "articulo 70", "obligaciones", "financier", "plan de desarrollo", "rendicion", "fais")
REDES = ("facebook.", "twitter.", "x.com", "instagram.", "youtube.", "youtu.be", "tiktok.", "whatsapp.", "wa.me",
         "t.me", "linkedin.", "flickr.", "spotify.", "threads.", "maps.google", "goo.gl")
NO_SON_PAGINAS = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".bmp", ".mp4", ".mp3", ".avi", ".mov", ".ico",
                  ".css", ".js", ".json", ".xml", ".woff", ".woff2", ".ttf", ".rar", ".7z", ".exe", ".apk", ".ppt",
                  ".pptx", ".txt", ".rss")
REDIRECCION_JS = re.compile(r"""location(?:\.href)?\s*=\s*["']([^"']+)["']|location\.replace\(\s*["']([^"']+)["']""")
# Palabras de relleno en el texto de un enlace ("Descarga PDF", "Clic aquí"): no sirven como título.
RELLENO = {"descargar", "descarga", "descargue", "ver", "aqui", "clic", "click", "pdf", "mas", "consultar", "consulta",
           "abrir", "documento", "archivo", "link", "enlace", "leer", "download", "xlsx", "xls", "excel", "el", "la",
           "los", "las", "de", "del", "en", "formato", "haz", "da", "boton", "vinculo", "hipervinculo", "doc", "docx"}
# Documentos que no son de ninguna sección aunque mencionen "tesorería" u "obra".
EXCLUIR = ("manual", "reglamento", "aviso de privacidad", "avisos de privacidad", "curriculum", "codigo de etica", "codigo de conducta",
           "organigrama", "directorio", "tramite", "requisitos")


BLOQUES = {"tr", "li", "p", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6", "article"}


class Enlaces(HTMLParser):
    """Saca de una página su título y sus enlaces: (dirección, texto del enlace, texto de su fila o párrafo).

    El texto de la fila importa: en muchas tablas el enlace solo dice "Descargar" y el nombre del
    documento está en la celda de al lado."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titulo, self.enlaces, self.redirecciones = "", [], []
        self._en_titulo, self._a, self._bloque = False, None, []

    def _contexto(self) -> str:
        return " ".join(" ".join(self._bloque).split())[-160:]

    def _cerrar_a(self):
        if self._a:
            self.enlaces.append((self._a[0], " ".join(" ".join(self._a[1]).split()), self._a[2]))
            self._a = None

    def handle_starttag(self, tag, attrs):
        a = {k: v or "" for k, v in attrs}
        if tag in BLOQUES:
            self._bloque = []
        if tag == "title":
            self._en_titulo = True
        elif tag == "a" and a.get("href"):
            self._cerrar_a()
            self._a = [a["href"], [a.get("title", ""), a.get("aria-label", "")], self._contexto()]
        elif tag in ("iframe", "embed", "frame") and a.get("src"):
            self.enlaces.append((a["src"], a.get("title", ""), self._contexto()))
        elif tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            destino = re.search(r"url\s*=\s*['\"]?([^'\";]+)", a.get("content", ""), re.I)
            if destino:
                self.redirecciones.append(destino.group(1).strip())
        elif tag == "object" and a.get("data"):
            self.enlaces.append((a["data"], "", self._contexto()))
        elif tag == "img" and self._a and a.get("alt"):
            self._a[1].append(a["alt"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._en_titulo = False
        elif tag == "a":
            self._cerrar_a()

    def handle_data(self, data):
        if self._en_titulo:
            self.titulo += data
            return
        if self._a:
            self._a[1].append(data)
        self._bloque.append(data)
        if len(self._bloque) > 80:
            self._bloque = self._bloque[-40:]


def sin_www(h: str) -> str:
    return (h or "").lower().removeprefix("www.")


def limpiar(url: str) -> str | None:
    """Dirección absoluta sin '#...', o None si no es una página web (correo, teléfono, javascript...)."""
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    return urlunsplit((p.scheme, p.netloc.lower(), p.path or "/", p.query, ""))


def tipo_documento(url: str) -> str | None:
    """'pdf', 'xlsx'... si la dirección apunta a un documento; 'drive' si es un archivo de Google Drive."""
    p = urlsplit(url)
    ruta, consulta = unquote(p.path).lower(), unquote(p.query).lower()
    for ext in EXTENSIONES_DOC:
        if ruta.endswith(ext) or re.search(re.escape(ext) + r"(&|$)", consulta):
            return ext[1:]
    if p.netloc.endswith("drive.google.com") and ("/file/d/" in ruta or "id=" in consulta):
        return "drive"
    if p.netloc.endswith("docs.google.com") and re.search(r"/(document|spreadsheets|presentation)/d/", ruta):
        return "drive"
    return None


def titulo_de(texto: str, url: str, contexto: str = "") -> str:
    """El texto del enlace. Si es relleno ("Descarga PDF"): el texto de su fila ("Cuenta Pública 2025 - Enero"),
    o el nombre del archivo ('1er Informe de Gobierno 2021 2024') si no es un código ('b4b1c4508b37...')."""
    texto = " ".join(texto.split())
    utiles = [w for w in palabras(texto).split() if w not in RELLENO]
    if len(utiles) >= 2:
        return texto[:250]
    fila = " ".join(contexto.removesuffix(texto).split())
    if len([w for w in palabras(fila).split() if w not in RELLENO and not w.isdigit()]) >= 2:
        fila = fila if len(fila) < 150 else fila[-150:].split(" ", 1)[-1]
        return (f"{fila} - {texto}" if utiles else fila)[:250]
    archivo = unquote(urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1])
    archivo = re.sub(r"\.[a-z0-9]{2,4}$", "", archivo, flags=re.I)
    archivo = re.sub(r"(?=[a-z0-9]*\d)[a-z0-9]{12,}", " ", archivo, flags=re.I)  # quita códigos y hashes
    archivo = " ".join(re.sub(r"[_\-+.]+", " ", archivo).split())
    if len(re.findall(r"[^\W\d_]{3,}", archivo)) >= 2:
        return archivo[:250]
    return (texto if utiles else archivo or texto)[:250]


async def permitido(cliente: httpx.AsyncClient, robots: dict, url: str) -> tuple[bool, float]:
    """(¿robots.txt deja entrar?, pausa pedida por el sitio). Sin robots.txt válido se entra (como Google)."""
    p = urlsplit(url)
    origen = f"{p.scheme}://{p.netloc}"
    if origen not in robots:
        rp = None
        try:
            r = await cliente.get(f"{origen}/robots.txt", timeout=15)
            if r.status_code == 200 and "html" not in r.headers.get("content-type", ""):
                rp = RobotFileParser()
                rp.parse(r.text.splitlines())
        except (httpx.HTTPError, OSError, ValueError):
            pass
        robots[origen] = rp
    rp = robots[origen]
    if rp is None:
        return True, 0.0
    return rp.can_fetch(AGENTE, url), min(float(rp.crawl_delay(AGENTE) or 0), 10.0)


MENCION = re.compile(r"\b(?:municipio|ayuntamiento|alcaldia|municipal)\s+(?:de\s+|del\s+)?")


def indice_municipios() -> dict[str, list[tuple[str, str, str]]]:
    """Por clave de estado: (nombre normalizado, clave INEGI, nombre) de sus municipios, los nombres largos primero."""
    por_estado = defaultdict(list)
    for m in leer_csv(FUENTES / "municipios.csv"):
        por_estado[m["clave_estado"]].append((palabras(m["municipio"]), m["clave_inegi"], m["municipio"]))
    for lista in por_estado.values():
        lista.sort(key=lambda x: -len(x[0]))
    return por_estado


def municipio_mencionado(texto: str, municipios: list[tuple[str, str, str]]) -> tuple[str, str] | None:
    """'Ley de Ingresos para el Municipio de León, Gto. 2026' → ('11020', 'León'). Solo con "municipio de X"
    o "ayuntamiento de X", para no confundir al municipio de Guanajuato con el estado de Guanajuato."""
    t = palabras(texto)
    for m in MENCION.finditer(t):
        resto = t[m.end():] + " "
        for nombre, clave, original in municipios:
            if resto.startswith(nombre + " "):
                return clave, original
    return None


def clasificar_en_contexto(texto: str, url: str, rastro: list[str], titulo_pagina: str, contexto: str = "") -> str:
    """Primero por el propio documento; si no dice nada, por su fila o párrafo, luego por la página donde
    está y el camino para llegar a ella."""
    archivo = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
    propio = f" {palabras(f'{texto} {archivo}')} "
    if any(f" {x} " in propio for x in EXCLUIR):
        return "otros"
    for pista in [f"{texto} {archivo}", contexto, titulo_pagina, *reversed(rastro)]:
        seccion = clasificar(pista)
        if seccion:
            return seccion
    return "otros"


async def recorrer(cliente: httpx.AsyncClient, sitio: dict, max_paginas: int, max_prof: int, pausa: float,
                   limite_seg: float) -> tuple[list[dict], dict]:
    inicio = time.monotonic()
    bases = {sin_www(urlsplit(s).hostname) for s in sitio["semillas"]}
    orden = itertools.count()
    cola = [(0, 0, next(orden), s, []) for s in sitio["semillas"]]
    vistas, docs, robots = set(), {}, {}
    paginas, errores_seguidos, error = 0, 0, ""

    def registrar(url: str, tipo: str, texto: str, pagina: str, rastro: list[str], titulo_pagina: str,
                  contexto: str = ""):
        if url not in docs:
            titulo = titulo_de(texto, url, contexto)
            if len(re.findall(r"[^\W\d_]{3,}", titulo)) < 2 and titulo_pagina:  # "12.pdf" → "Actas 2025 - 12"
                titulo = f"{titulo_pagina[:120]} - {titulo}"
            clave, municipio = sitio["clave"], sitio["municipio"]
            if not municipio:  # documento de un sitio estatal (congreso, periódico oficial...) sobre un municipio
                archivo = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
                encontrado = municipio_mencionado(f"{titulo} {archivo}", sitio["municipios"])
                if encontrado:
                    clave, municipio = encontrado
            docs[url] = {"clave": clave, "estado": sitio["estado"], "municipio": municipio,
                         "seccion": clasificar_en_contexto(titulo, url, rastro, titulo_pagina, contexto),
                         "titulo": titulo, "tipo": tipo, "url": url, "pagina": pagina,
                         "anio": anio(f"{titulo} {url}") or anio(contexto) or anio(titulo_pagina) or anio(" ".join(rastro)),
                         "sitio": sitio["semillas"][0]}

    while cola and paginas < max_paginas and errores_seguidos < 8 and time.monotonic() - inicio < limite_seg:
        _, prof, _, url, rastro = heapq.heappop(cola)
        if url in vistas:
            continue
        vistas.add(url)
        entra, pausa_sitio = await permitido(cliente, robots, url)
        if not entra:
            continue
        try:
            r = await cliente.get(url)
        except (httpx.HTTPError, OSError, ValueError) as e:
            errores_seguidos += 1
            error = type(e).__name__
            continue
        tipo_contenido = r.headers.get("content-type", "").lower()
        if r.status_code >= 400:
            errores_seguidos += 1
            error = f"HTTP {r.status_code}"
            continue
        if "html" not in tipo_contenido:
            # Un enlace sin extensión que resultó ser documento (descargar.php?id=...).
            if "pdf" in tipo_contenido or "spreadsheet" in tipo_contenido or "excel" in tipo_contenido:
                registrar(url, "pdf" if "pdf" in tipo_contenido else "xlsx", rastro[-1] if rastro else "", url,
                          rastro, "")
            continue
        errores_seguidos, error = 0, ""
        paginas += 1
        lector = Enlaces()
        try:
            lector.feed(r.text[:3_000_000])
        except Exception:  # HTML muy roto: nos quedamos con lo que alcanzó a leer
            pass
        titulo_pagina = " ".join(lector.titulo.split())
        # Páginas que solo redirigen (meta refresh o window.location): se sigue el destino, aunque esté en
        # otro subdominio de gobierno (secfin.bcs.gob.mx → finanzas.bcs.gob.mx).
        redirecciones = lector.redirecciones + (
            [a or b for a, b in REDIRECCION_JS.findall(r.text)] if len(r.text) < 5000 else [])
        for href in redirecciones:
            destino = limpiar(urljoin(str(r.url), href))
            h = sin_www(urlsplit(destino).hostname) if destino else ""
            if destino and destino not in vistas and (h.endswith(".gob.mx") or any(h.endswith(b) for b in bases)):
                bases.add(h)
                heapq.heappush(cola, (0, prof, next(orden), destino, rastro))
        for href, texto, contexto in lector.enlaces:
            destino = limpiar(urljoin(str(r.url), href))
            if not destino or any(red in destino for red in REDES):
                continue
            tipo = tipo_documento(destino)
            if tipo:
                registrar(destino, tipo, texto, str(r.url), rastro, titulo_pagina, contexto)
                continue
            h = sin_www(urlsplit(destino).hostname)
            ruta = urlsplit(destino).path.lower()
            if (prof >= max_prof or destino in vistas or ruta.endswith(NO_SON_PAGINAS)
                    or not any(h == b or h.endswith("." + b) for b in bases)):
                continue
            # Primero lo que ya dice su sección (Cuenta pública, Actas de cabildo), luego los menús de
            # transparencia/documentos y al final todo lo demás.
            enlace = f"{texto} {unquote(destino)}"
            prioridad = 0 if clasificar(enlace) else 1 if any(p in palabras(enlace) for p in PISTAS) else 2
            heapq.heappush(cola, (prioridad, prof + 1, next(orden), destino,
                                  (rastro + [texto])[-3:] if prioridad < 2 and texto else rastro))
        await asyncio.sleep(max(pausa, pausa_sitio))

    resumen = {"clave": sitio["clave"], "estado": sitio["estado"], "municipio": sitio["municipio"],
               "sitio": sitio["semillas"][0], "paginas": paginas, "documentos": len(docs),
               "error": error if not paginas else "", "segundos": round(time.monotonic() - inicio)}
    return list(docs.values()), resumen


def agregar(ruta, filas: list[dict], columnas: list[str]) -> None:
    nuevo = not ruta.exists()
    with ruta.open("a", encoding="utf-8-sig" if nuevo else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        if nuevo:
            w.writeheader()
        w.writerows(filas)


def sitios_a_recorrer(solo: str | None, estado: str | None) -> list[dict]:
    municipios = {m["clave_inegi"]: m for m in leer_csv(FUENTES / "municipios.csv")}
    por_estado = indice_municipios()
    sitios = []
    if solo in (None, "estados") and (FUENTES / "sitios_estatales.csv").exists():
        for s in leer_csv(FUENTES / "sitios_estatales.csv"):
            if not estado or s["clave_estado"] == estado:
                sitios.append({"clave": s["clave_estado"], "id": f"{s['clave_estado']} {s['sitio']}",
                               "estado": s["estado"], "municipio": "", "semillas": [s["sitio"]], "es_estado": True,
                               "municipios": por_estado[s["clave_estado"]]})
    if solo in (None, "municipios") and (FUENTES / "sitios_municipales.csv").exists():
        del_municipio = []
        for s in leer_csv(FUENTES / "sitios_municipales.csv"):
            if not s["sitio"] or (estado and s["clave_inegi"][:2] != estado):
                continue
            # Solo sitios comprobados, o los de Wikidata en .gob.mx (ese dominio solo lo tiene gobierno).
            if s["verificado"] == "si" or (s["verificado"] == "no" and ".gob.mx" in s["sitio"]):
                del_municipio.append({"clave": s["clave_inegi"], "id": f"{s['clave_inegi']} {s['sitio']}",
                                      "estado": s["estado"], "municipio": s["municipio"], "semillas": [s["sitio"]],
                                      "es_estado": False})
        del_municipio.sort(key=lambda s: -int(municipios.get(s["clave"], {}).get("poblacion") or 0))
        sitios += del_municipio
    return sitios


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--solo", choices=["estados", "municipios"])
    parser.add_argument("--estado", help="clave INEGI del estado: 11 = Guanajuato")
    parser.add_argument("--paginas", type=int, default=60, help="páginas máximas por sitio municipal")
    parser.add_argument("--paginas-estado", type=int, default=150, help="páginas máximas por sitio estatal")
    parser.add_argument("--sitios", type=int, default=40, help="sitios que se recorren al mismo tiempo")
    parser.add_argument("--pausa", type=float, default=0.5, help="segundos entre páginas del mismo sitio")
    args = parser.parse_args()

    # Cada recorrido escribe en sus propios archivos: así estados y municipios pueden correr a la vez.
    global ENLACES, RASTREO
    sufijo = f"_{args.solo}" if args.solo else ""
    ENLACES, RASTREO = FUENTES / f"enlaces{sufijo}.csv", FUENTES / f"rastreo{sufijo}.csv"
    hechos = {f"{r['clave']} {r['sitio']}" for ruta in FUENTES.glob("rastreo*.csv") for r in leer_csv(ruta)}
    pendientes = [s for s in sitios_a_recorrer(args.solo, args.estado) if s["id"] not in hechos]
    print(f"{len(pendientes)} sitios por recorrer ({len(hechos)} ya recorridos antes)", flush=True)

    limite = asyncio.Semaphore(args.sitios)
    totales = {"sitios": 0, "documentos": 0}
    inicio = time.monotonic()
    limites = httpx.Limits(max_connections=args.sitios * 2, max_keepalive_connections=args.sitios)
    async with httpx.AsyncClient(headers={"User-Agent": AGENTE}, timeout=20, follow_redirects=True, verify=False,
                                 limits=limites) as cliente:

        async def uno(sitio: dict) -> None:
            async with limite:
                try:
                    docs, resumen = await recorrer(
                        cliente, sitio, args.paginas_estado if sitio["es_estado"] else args.paginas, 4,
                        args.pausa, 1200 if sitio["es_estado"] else 480)
                except Exception as e:  # un sitio raro no debe tumbar el recorrido completo
                    docs, resumen = [], {"clave": sitio["clave"], "estado": sitio["estado"],
                                         "municipio": sitio["municipio"], "sitio": sitio["semillas"][0],
                                         "paginas": 0, "documentos": 0, "error": f"{type(e).__name__}: {e}"[:200],
                                         "segundos": 0}
                agregar(ENLACES, docs, COL_ENLACES)
                agregar(RASTREO, [resumen], COL_RASTREO)
                totales["sitios"] += 1
                totales["documentos"] += len(docs)
                lugar = f"{sitio['municipio']}, {sitio['estado']}" if sitio["municipio"] else sitio["estado"]
                print(f"[{totales['sitios']}/{len(pendientes)}] {lugar}: {resumen['paginas']} páginas, "
                      f"{len(docs)} documentos {resumen['error']} "
                      f"(total {totales['documentos']}, {round((time.monotonic() - inicio) / 60)} min)", flush=True)

        await asyncio.gather(*(uno(s) for s in pendientes))
    print(f"\nListo: {totales['sitios']} sitios, {totales['documentos']} documentos nuevos → {ENLACES}")
    separar_por_seccion()


def separar_por_seccion() -> None:
    """documentos/_catalogo/por_seccion/<sección>.csv: los enlaces encontrados, uno por sección, sin repetir."""
    por_seccion, vistos = defaultdict(list), set()
    for e in (e for ruta in sorted(FUENTES.glob("enlaces*.csv")) for e in leer_csv(ruta)):
        if e["url"] not in vistos:
            vistos.add(e["url"])
            por_seccion[e["seccion"]].append(e)
    for seccion in [*SECCIONES, "otros"]:
        filas = sorted(por_seccion.get(seccion, []), key=lambda e: (e["estado"], e["municipio"], -int(e["anio"] or 0)))
        escribir_csv(FUENTES / "por_seccion" / f"{seccion}.csv", filas, COL_ENLACES)
        print(f"  {seccion}: {len(filas)} documentos")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    asyncio.run(main())
