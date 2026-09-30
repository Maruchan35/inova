"""Descarga los documentos encontrados a documentos/<Estado>/<Municipio o Gobierno del estado>/<Sección>/.

    python recolector/descargar.py                          # lo pendiente de documentos/_catalogo/enlaces*.csv
    python recolector/descargar.py --estado 11 --seccion presupuesto
    python recolector/descargar.py --por-municipio 10 --por-estado 30   # máximo por lugar y sección
    python recolector/descargar.py --max-mb 80 --max-gb 30 --tipos pdf,xlsx

Por cada lugar y sección baja primero lo más reciente. No vuelve a bajar lo que ya tenemos:
- un archivo con el mismo contenido (sha256) que otro de documentos/ o de datos/documentos.csv;
- un documento que datos/documentos.csv ya lista (mismo lugar, sección, año y casi el mismo título);
- una dirección que ya se intentó antes (documentos/_catalogo/descargas.csv; con --reintentar se reintentan los errores).

Escribe documentos/indice.csv (solo archivos que sí están en disco, en el formato de datos/documentos.csv).
Para procesarlos con el backend (desde backend/): python cargar.py --csv ../documentos/indice.csv --pdfs ../documentos
"""

import argparse
import asyncio
import hashlib
import re
import time
import warnings
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from comun import AGENTE, DATOS, DOCUMENTOS, FUENTES, escribir_csv, leer_csv, palabras

INDICE = DOCUMENTOS / "indice.csv"
BITACORA = FUENTES / "descargas.csv"
COL_INDICE = ["archivo", "estado", "municipio", "seccion", "titulo", "anio", "url_fuente", "formato", "sha256",
              "fecha_publicacion", "dependencia", "clave_inegi", "pagina_origen", "bytes"]
COL_BITACORA = ["url", "estatus", "detalle", "archivo"]
CARPETA_SECCION = {"informes": "Informes de gobierno", "presupuesto": "Presupuesto y finanzas",
                   "obras": "Obras públicas", "actas": "Actas de cabildo", "contratos": "Contratos y licitaciones"}
FIRMAS = {"pdf": (b"%PDF",), "xlsx": (b"PK",), "xls": (b"\xd0\xcf\x11\xe0",), "docx": (b"PK",),
          "doc": (b"\xd0\xcf\x11\xe0",), "zip": (b"PK",), "csv": ()}
MAX_RUTA = 235  # Windows no acepta rutas de más de 260 letras


def nombre_seguro(texto: str, largo: int) -> str:
    """Nombre válido para carpeta o archivo en Windows, Mac y Linux (conserva acentos)."""
    texto = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", texto)
    texto = " ".join(texto.split()).strip(" .")
    return texto[:largo].strip(" .") or "sin nombre"


def url_de_descarga(url: str, tipo: str) -> tuple[str, str]:
    """(dirección para bajar el archivo, formato esperado). Google Drive necesita una dirección especial."""
    if tipo != "drive":
        return url, tipo
    ident = re.search(r"/d/([\w-]{10,})", url) or re.search(r"[?&]id=([\w-]{10,})", url)
    if not ident:
        return url, "pdf"
    if "docs.google.com/document" in url:
        return f"https://docs.google.com/document/d/{ident.group(1)}/export?format=pdf", "pdf"
    if "docs.google.com/spreadsheets" in url:
        return f"https://docs.google.com/spreadsheets/d/{ident.group(1)}/export?format=xlsx", "xlsx"
    return f"https://drive.google.com/uc?export=download&id={ident.group(1)}", "pdf"


def firma_ok(formato: str, inicio: bytes) -> bool:
    """¿Los primeros bytes son de verdad de ese formato? (Muchos sitios responden una página de error.)"""
    if formato == "pdf":
        return b"%PDF" in inicio[:1024]
    firmas = FIRMAS.get(formato, ())
    return not firmas or any(inicio.lstrip().startswith(s) for s in firmas)


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def parecidos(a: str, b: str) -> bool:
    pa, pb = set(palabras(a).split()) - {"de", "del", "la", "el", "los", "las", "y", "para"}, \
        set(palabras(b).split()) - {"de", "del", "la", "el", "los", "las", "y", "para"}
    return bool(pa and pb) and len(pa & pb) / len(pa | pb) >= 0.6


class Descargador:
    def __init__(self, args):
        self.args = args
        self.indice = leer_csv(INDICE) if INDICE.exists() else []
        self.bitacora = leer_csv(BITACORA) if BITACORA.exists() else []
        self.hashes = {f["sha256"] for f in self.indice if f.get("sha256")}
        self.listados = leer_csv(DATOS / "documentos.csv") if (DATOS / "documentos.csv").exists() else []
        self.hashes |= {f["sha256"] for f in self.listados if f.get("sha256")}
        en_indice = {(DOCUMENTOS / f["archivo"]).resolve() for f in self.indice}
        for ruta in DOCUMENTOS.rglob("*"):
            if ruta.is_file() and ruta.suffix.lower() != ".csv" and ruta.resolve() not in en_indice:
                self.hashes.add(sha256_de(ruta))
        self.por_host = defaultdict(lambda: asyncio.Semaphore(2))
        self.reservadas = set()
        self.bytes_total = sum(int(f.get("bytes") or 0) for f in self.indice)
        self.cuenta = defaultdict(int)

    def elegir(self) -> list[dict]:
        intentadas = {b["url"] for b in self.bitacora
                      if not (self.args.reintentar and b["estatus"] in ("error", "no_es_documento"))}
        tipos = set(self.args.tipos.split(","))
        grupos = defaultdict(list)
        for e in (e for ruta in sorted(FUENTES.glob("enlaces*.csv")) for e in leer_csv(ruta)):
            if (e["seccion"] not in CARPETA_SECCION or e["url"] in intentadas
                    or "privacidad" in palabras(e["titulo"])
                    or (e["tipo"] not in tipos and not (e["tipo"] == "drive" and "pdf" in tipos))
                    or (self.args.estado and e["clave"][:2] != self.args.estado)
                    or (self.args.seccion and e["seccion"] != self.args.seccion)
                    or (self.args.solo == "estados" and len(e["clave"]) != 2)
                    or (self.args.solo == "municipios" and len(e["clave"]) != 5)):
                continue
            grupos[(e["clave"], e["municipio"], e["seccion"])].append(e)
        elegidos, vistos = [], set()
        for (clave, municipio, _), lista in grupos.items():
            tope = self.args.por_municipio if municipio else self.args.por_estado
            lista.sort(key=lambda e: (-(int(e["anio"]) if e["anio"] else 0), e["titulo"]))
            for e in lista:
                if e["url"] not in vistos and tope > 0:
                    vistos.add(e["url"])
                    elegidos.append(e)
                    tope -= 1
        # Primero los estados (clave de 2 dígitos), y turnando entre sitios: así se baja de muchos a la vez
        # en lugar de hacer fila en uno solo.
        por_sitio = defaultdict(list)
        for e in sorted(elegidos, key=lambda e: (len(e["clave"]), e["clave"])):
            por_sitio[(len(e["clave"]), urlsplit(e["url"]).netloc)].append(e)
        orden = []
        for nivel in (2, 5):
            colas = [c for (n, _), c in por_sitio.items() if n == nivel]
            for i in range(max((len(c) for c in colas), default=0)):
                orden += [c[i] for c in colas if i < len(c)]
        return orden

    def ya_listado(self, e: dict) -> bool:
        return any(normal(f["estado"]) == normal(e["estado"]) and normal(f["municipio"]) == normal(e["municipio"])
                   and f["seccion"] == e["seccion"] and f.get("anio", "") == e["anio"] and parecidos(f["titulo"], e["titulo"])
                   for f in self.listados)

    def destino(self, e: dict, formato: str) -> Path:
        carpeta = (DOCUMENTOS / nombre_seguro(e["estado"], 40)
                   / (nombre_seguro(e["municipio"], 50) if e["municipio"] else "Gobierno del estado")
                   / CARPETA_SECCION[e["seccion"]])
        disponible = MAX_RUTA - len(str(carpeta)) - len(formato) - 8
        base = nombre_seguro(e["titulo"] if e["anio"] in e["titulo"] else f"{e['titulo']} {e['anio']}", max(disponible, 20))
        ruta, n = carpeta / f"{base}.{formato}", 2
        while ruta.exists() or ruta in self.reservadas:
            ruta, n = carpeta / f"{base} ({n}).{formato}", n + 1
        self.reservadas.add(ruta)  # que otra descarga simultánea no tome el mismo nombre
        return ruta

    def anotar(self, url: str, estatus: str, detalle: str = "", archivo: str = "") -> None:
        self.bitacora.append({"url": url, "estatus": estatus, "detalle": detalle[:200], "archivo": archivo})
        self.cuenta[estatus] += 1

    async def bajar(self, cliente: httpx.AsyncClient, limite: asyncio.Semaphore, e: dict) -> None:
        if self.bytes_total > self.args.max_gb * 1e9:
            return
        if self.ya_listado(e):
            return self.anotar(e["url"], "ya_listado", "datos/documentos.csv ya lo tiene")
        url, formato = url_de_descarga(e["url"], e["tipo"])
        async with limite, self.por_host[urlsplit(url).netloc]:
            ruta = self.destino(e, formato)
            temporal = ruta.with_name(ruta.name + ".parcial")
            try:
                async with cliente.stream("GET", url) as r:
                    if r.status_code >= 400:
                        return self.anotar(e["url"], "error", f"HTTP {r.status_code}")
                    largo = int(r.headers.get("content-length") or 0)
                    if largo > self.args.max_mb * 1e6:
                        return self.anotar(e["url"], "muy_grande", f"{largo / 1e6:.0f} MB")
                    h, total, inicio = hashlib.sha256(), 0, b""
                    ruta.parent.mkdir(parents=True, exist_ok=True)
                    with temporal.open("wb") as f:
                        async for bloque in r.aiter_bytes(1 << 16):
                            if len(inicio) < 1024:
                                inicio += bloque[:1024 - len(inicio)]
                                if len(inicio) >= 1024 and not firma_ok(formato, inicio):
                                    break  # es una página de error o de aviso, no el documento
                            total += len(bloque)
                            if total > self.args.max_mb * 1e6:
                                break
                            h.update(bloque)
                            f.write(bloque)
            except (httpx.HTTPError, OSError, ValueError) as ex:
                temporal.unlink(missing_ok=True)
                self.reservadas.discard(ruta)
                return self.anotar(e["url"], "error", type(ex).__name__)
            finally:
                self.reservadas.discard(ruta)
            if not firma_ok(formato, inicio):
                temporal.unlink(missing_ok=True)
                return self.anotar(e["url"], "no_es_documento", r.headers.get("content-type", ""))
            if total > self.args.max_mb * 1e6:
                temporal.unlink(missing_ok=True)
                return self.anotar(e["url"], "muy_grande", f"más de {self.args.max_mb} MB")
            huella = h.hexdigest()
            if huella in self.hashes:
                temporal.unlink(missing_ok=True)
                return self.anotar(e["url"], "repetido", "mismo contenido que otro archivo")
            self.hashes.add(huella)
            temporal.replace(ruta)
            self.bytes_total += total
            relativo = ruta.relative_to(DOCUMENTOS).as_posix()
            self.indice.append({
                "archivo": relativo, "estado": e["estado"], "municipio": e["municipio"], "seccion": e["seccion"],
                "titulo": e["titulo"], "anio": e["anio"], "url_fuente": e["url"], "formato": formato,
                "sha256": huella, "fecha_publicacion": "", "dependencia": urlsplit(e["sitio"]).netloc,
                "clave_inegi": e["clave"], "pagina_origen": e["pagina"], "bytes": total})
            self.anotar(e["url"], "descargado", f"{total / 1e6:.1f} MB", relativo)
            n = self.cuenta["descargado"]
            if n % 25 == 0:
                self.guardar()
                print(f"  {n} descargados ({self.bytes_total / 1e9:.2f} GB) · último: {relativo}", flush=True)

    def guardar(self) -> None:
        escribir_csv(INDICE, self.indice, COL_INDICE)
        escribir_csv(BITACORA, self.bitacora, COL_BITACORA)


def normal(texto: str) -> str:
    return palabras(texto or "")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--estado", help="clave INEGI del estado: 11 = Guanajuato")
    parser.add_argument("--seccion", choices=list(CARPETA_SECCION))
    parser.add_argument("--solo", choices=["estados", "municipios"], help="bajar solo de un nivel de gobierno")
    parser.add_argument("--por-municipio", type=int, default=8, help="máximo por municipio y sección")
    parser.add_argument("--por-estado", type=int, default=25, help="máximo por gobierno estatal y sección")
    parser.add_argument("--tipos", default="pdf", help="formatos a bajar, separados por coma: pdf,xlsx")
    parser.add_argument("--max-mb", type=float, default=80, help="salta archivos más grandes")
    parser.add_argument("--max-gb", type=float, default=30, help="se detiene al llegar a este total")
    parser.add_argument("--simultaneas", type=int, default=24)
    parser.add_argument("--reintentar", action="store_true", help="reintenta los que dieron error antes")
    args = parser.parse_args()

    d = Descargador(args)
    elegidos = d.elegir()
    print(f"{len(elegidos)} documentos por bajar ({len(d.hashes)} archivos que ya tenemos se usan para no repetir)",
          flush=True)
    inicio = time.monotonic()
    limite = asyncio.Semaphore(args.simultaneas)
    try:
        async with httpx.AsyncClient(headers={"User-Agent": AGENTE}, timeout=httpx.Timeout(60, connect=20),
                                     follow_redirects=True, verify=False) as cliente:
            await asyncio.gather(*(d.bajar(cliente, limite, e) for e in elegidos))
    finally:
        d.guardar()
    print(f"\nListo en {round((time.monotonic() - inicio) / 60)} min: " +
          ", ".join(f"{v} {k}" for k, v in sorted(d.cuenta.items())) +
          f". En disco: {d.bytes_total / 1e9:.2f} GB → {DOCUMENTOS}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    asyncio.run(main())
