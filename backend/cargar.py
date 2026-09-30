"""Carga masiva: lee datos/documentos.csv y procesa todos sus PDFs de una vez.

    cd backend
    python cargar.py                  # carga lo que falte de datos/documentos.csv
    python cargar.py --solo-revisar   # revisa el CSV y los PDFs sin procesar nada
    python cargar.py --reprocesar     # vuelve a procesar también los que ya estaban listos
    python cargar.py --hilos 4        # cuántos documentos se procesan a la vez (por defecto 3)

Formato del CSV (se acepta separado por comas o por punto y coma, como lo guarda Excel):

    archivo,estado,municipio,seccion,titulo,anio,url_fuente,formato,sha256,fecha_publicacion,dependencia
    presupuesto-irapuato-2026.pdf,Guanajuato,Irapuato,presupuesto,Presupuesto de Egresos 2026,2026,https://...,pdf,...,2026-01-10,Tesorería
    informe-estatal-2025.pdf,Guanajuato,,informes,Informe de Gobierno 2025,2025,,,,,

- `archivo`: nombre del PDF dentro de datos/pdfs/ (o ruta relativa a esa carpeta).
- `estado` y `municipio`: nombres como están en la base (sin importar acentos ni mayúsculas).
  Municipio vacío = documento del gobierno estatal.
- `seccion`: clave de la sección (informes, presupuesto, obras, actas, contratos).
- `anio`: opcional.
- `url_fuente`, `formato`, `sha256`, `fecha_publicacion`, `dependencia`: opcionales; se guardan en el documento.
  Si viene `sha256`, el archivo tiene que coincidir: así no se carga un archivo cambiado o equivocado.
- Por ahora solo se procesan PDF con texto; Excel, Word y escaneados se reportan para hacerlos después.

Se puede ejecutar las veces que haga falta: un documento con el mismo `archivo` que ya está listo
se salta; si quedó a medias o con error, se vuelve a procesar sobre el mismo registro.
"""

import argparse
import csv
import hashlib
import io
import re
import sqlite3
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pypdf import PdfReader

from app import config  # noqa: F401  (carga backend/.env con la clave de DeepSeek)
from app import db, procesamiento
from app.procesamiento import llm

RAIZ = Path(__file__).resolve().parents[1]
COLUMNAS = ("archivo", "estado", "municipio", "seccion", "titulo", "anio")
METADATOS = ("url_fuente", "formato", "sha256", "fecha_publicacion", "dependencia")
# Un PDF "impreso" desde un navegador no suele ser el documento oficial (así llegó uno falso).
NAVEGADOR = re.compile(r"chrom|skia|headless|puppeteer|wkhtmltopdf", re.I)


def normalizar(texto: str) -> str:
    """'  León ' → 'leon': para comparar nombres sin importar acentos, mayúsculas ni espacios."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(sin_acentos.casefold().split())


def leer_csv(ruta: Path) -> list[dict]:
    try:
        texto = ruta.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        texto = ruta.read_text(encoding="cp1252")  # Excel en español guarda así los CSV
    encabezado = texto.partition("\n")[0]
    lector = csv.DictReader(io.StringIO(texto), delimiter=";" if encabezado.count(";") > encabezado.count(",") else ",")
    # Encabezados tolerantes: "Sección" → "seccion", "Año" → "anio".
    lector.fieldnames = [{"ano": "anio"}.get(normalizar(c), normalizar(c)) for c in lector.fieldnames or []]
    faltan = [c for c in ("archivo", "estado", "seccion", "titulo") if c not in lector.fieldnames]
    if faltan:
        raise SystemExit(f"Al CSV le faltan las columnas: {', '.join(faltan)}. Esperadas: {','.join(COLUMNAS)}")
    return [{c: (fila.get(c) or "").strip() for c in COLUMNAS + METADATOS} for fila in lector]


def clave_archivo(ruta: Path) -> str:
    """Lo que se guarda en documentos.archivo: ruta relativa al repo, igual en todas las computadoras."""
    try:
        return ruta.relative_to(RAIZ).as_posix()
    except ValueError:
        return ruta.as_posix()


def _inicio(ruta: Path) -> bytes:
    with ruta.open("rb") as f:
        return f.read(4)


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def hecho_en_navegador(ruta: Path) -> str | None:
    """'Chromium' si los metadatos del PDF dicen que se imprimió desde un navegador; None si no."""
    try:
        meta = PdfReader(ruta).metadata or {}
    except Exception:
        return None
    for clave in ("/Creator", "/Producer"):
        if NAVEGADOR.search(str(meta.get(clave) or "")):
            return str(meta.get(clave))
    return None


def validar(con: sqlite3.Connection, filas: list[dict], carpeta_pdfs: Path) -> tuple[list[dict], list[str], list[str]]:
    """Convierte cada fila en un documento listo para insertar, o en un error con su número de línea.
    Además devuelve avisos: filas correctas que conviene revisar a mano."""
    estados = {normalizar(e["nombre"]): e for e in con.execute("SELECT id, nombre FROM estados")}
    municipios = {
        (m["estado_id"], normalizar(m["nombre"])): m for m in con.execute("SELECT id, estado_id, nombre FROM municipios")
    }
    secciones = {s["clave"]: s["id"] for s in con.execute("SELECT id, clave FROM secciones")}

    validos, errores, avisos, vistos = [], [], [], set()
    for linea, fila in enumerate(filas, start=2):  # la línea 1 es el encabezado
        if not any(fila.values()):
            continue
        problemas = []
        ruta = (carpeta_pdfs / fila["archivo"]).resolve()
        if not fila["archivo"]:
            problemas.append("falta el archivo")
        elif not ruta.is_file():
            problemas.append(f"no existe {ruta}")
        elif _inicio(ruta) != b"%PDF":
            if ruta.suffix.lower() in (".xlsx", ".xls", ".docx", ".doc", ".csv"):
                problemas.append(f"{fila['archivo']}: el formato {ruta.suffix.lower()} todavía no se procesa (solo PDF)")
            else:
                problemas.append(f"{fila['archivo']} no es un PDF")
        elif ruta in vistos:
            problemas.append(f"{fila['archivo']} está repetido en el CSV")
        elif fila["sha256"] and sha256(ruta) != fila["sha256"].lower():
            problemas.append(f"{fila['archivo']} no coincide con su sha256 del CSV (¿es otro archivo o se modificó?)")
        estado = estados.get(normalizar(fila["estado"]))
        estado_id = estado["id"] if estado else None
        if not estado:
            problemas.append(f"el estado '{fila['estado']}' no está en la base")
        municipio = None
        if fila["municipio"] and estado:
            municipio = municipios.get((estado_id, normalizar(fila["municipio"])))
            if not municipio:
                problemas.append(f"el municipio '{fila['municipio']}' no está en {fila['estado']}")
        seccion_id = secciones.get(normalizar(fila["seccion"]))
        if not seccion_id:
            problemas.append(f"la sección '{fila['seccion']}' no existe (usa: {', '.join(secciones)})")
        if not fila["titulo"]:
            problemas.append("falta el título")
        if fila["anio"] and not fila["anio"].isdigit():
            problemas.append(f"el año '{fila['anio']}' no es un número")

        if problemas:
            errores.append(f"Línea {linea}: " + "; ".join(problemas))
            continue
        if origen := hecho_en_navegador(ruta):
            avisos.append(f"Línea {linea}: {fila['archivo']} parece impreso desde un navegador ({origen}); "
                          "revisa que sea el documento oficial")
        vistos.add(ruta)
        validos.append({
            "ruta": ruta,
            "archivo": clave_archivo(ruta),
            "estado_id": estado_id,
            "municipio_id": municipio["id"] if municipio else None,
            "seccion_id": seccion_id,
            "titulo": fila["titulo"],
            "anio": int(fila["anio"]) if fila["anio"] else None,
            "lugar": municipio["nombre"] if municipio else f"{estado['nombre']} (estatal)",
            **{m: fila[m] or None for m in METADATOS},
        })
    return validos, errores, avisos


def registrar(con: sqlite3.Connection, doc: dict, reprocesar: bool) -> int | None:
    """Crea el registro del documento, o reutiliza el existente. None = ya estaba listo, se salta."""
    existente = con.execute(
        "SELECT id, estatus FROM documentos WHERE archivo = ? ORDER BY id LIMIT 1", (doc["archivo"],)
    ).fetchone()
    columnas = ("estado_id", "municipio_id", "seccion_id", "titulo", "anio", "archivo") + METADATOS
    datos = tuple(doc[c] for c in columnas)
    if existente and existente["estatus"] == "listo" and not reprocesar:
        return None
    if existente:  # quedó a medias, con error, o se pidió reprocesar: se actualiza con lo que diga el CSV
        con.execute(
            f"UPDATE documentos SET {', '.join(f'{c} = ?' for c in columnas)} WHERE id = ?", (*datos, existente["id"])
        )
        documento_id = existente["id"]
    else:
        documento_id = con.execute(
            f"INSERT INTO documentos ({', '.join(columnas)}) VALUES ({', '.join('?' * len(columnas))})", datos
        ).lastrowid
    con.commit()  # antes de procesar: si el procesamiento falla, su rollback no borra el registro
    return documento_id


def _procesar_en_hilo(ruta_db: str, documento_id: int, ruta_pdf: Path) -> tuple[dict, sqlite3.Row]:
    """Cada hilo usa su propia conexión: SQLite no comparte una conexión entre hilos."""
    con = sqlite3.connect(ruta_db, timeout=120)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        procesamiento.procesar(con, documento_id, ruta_pdf)
        fila = con.execute(
            "SELECT estatus, error, total_paginas, (SELECT COUNT(*) FROM puntos_clave WHERE documento_id = d.id) AS puntos"
            " FROM documentos d WHERE id = ?",
            (documento_id,),
        ).fetchone()
        return procesamiento.BITACORA.pop(documento_id), fila
    finally:
        con.close()


def cargar(con: sqlite3.Connection, ruta_csv: Path, carpeta_pdfs: Path, reprocesar=False, solo_revisar=False,
           hilos: int = 3) -> dict:
    validos, errores, avisos = validar(con, leer_csv(ruta_csv), carpeta_pdfs)
    for e in errores:
        print(f"  ERROR {e}")
    for a in avisos:
        print(f"  REVISAR {a}")
    resultado = {"procesados": 0, "saltados": 0, "fallidos": 0, "invalidos": len(errores), "avisos": len(avisos),
                 "uso": {}, "segundos": 0.0}
    if solo_revisar:
        print(f"Revisión: {len(validos)} filas correctas ({len(avisos)} para revisar), {len(errores)} con errores."
              " No se procesó nada.")
        return resultado

    motor = llm.modelo() if llm.configurado() else "respaldo sin IA (no hay DEEPSEEK_API_KEY en backend/.env)"
    inicio = time.time()
    pendientes = []
    for doc in validos:  # el registro es rápido y en orden; lo lento (leer el PDF y la IA) va en paralelo
        documento_id = registrar(con, doc, reprocesar)
        if documento_id is None:
            resultado["saltados"] += 1
            print(f"  {doc['titulo']} - {doc['lugar']}: ya estaba cargado, se salta")
        else:
            pendientes.append((doc, documento_id))
    print(f"{len(pendientes)} documentos por procesar · motor: {motor} · {hilos} a la vez", flush=True)

    ruta_db = con.execute("PRAGMA database_list").fetchone()["file"]
    with ThreadPoolExecutor(max_workers=max(1, hilos)) as grupo:
        tareas = {grupo.submit(_procesar_en_hilo, ruta_db, documento_id, doc["ruta"]): (doc, documento_id)
                  for doc, documento_id in pendientes}
        for n, tarea in enumerate(as_completed(tareas), start=1):
            doc, documento_id = tareas[tarea]
            bitacora, fila = tarea.result()
            for k, v in bitacora["uso"].items():
                resultado["uso"][k] = resultado["uso"].get(k, 0) + v
            prefijo = f"[{n}/{len(pendientes)}] {doc['titulo']} - {doc['lugar']}"
            if fila["estatus"] == "listo":
                resultado["procesados"] += 1
                print(f"{prefijo}\n    listo (id {documento_id}): {fila['total_paginas']} páginas, {fila['puntos']} puntos"
                      f" · {bitacora['motor']} · {bitacora['segundos']} s · ${bitacora['costo_usd']:.4f} USD", flush=True)
            else:
                resultado["fallidos"] += 1
                print(f"{prefijo}\n    ERROR (id {documento_id}): {fila['error']}", flush=True)
            if bitacora["aviso"] and llm.configurado():
                print(f"    Aviso: {bitacora['aviso']}")

    resultado["segundos"] = round(time.time() - inicio, 1)
    uso = resultado["uso"]
    print(
        f"\nTerminado: {resultado['procesados']} procesados, {resultado['saltados']} ya estaban cargados,"
        f" {resultado['fallidos']} con error, {resultado['invalidos']} filas inválidas en el CSV,"
        f" {resultado['avisos']} para revisar a mano."
        f"\nTiempo total: {resultado['segundos']} s · tokens: {uso.get('entrada', 0):,} de entrada,"
        f" {uso.get('salida', 0):,} de salida · costo aprox.: ${llm.costo_usd(uso):.4f} USD"
    )
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description="Procesa todos los PDFs de datos/documentos.csv.")
    parser.add_argument("--csv", type=Path, default=RAIZ / "datos" / "documentos.csv")
    parser.add_argument("--pdfs", type=Path, default=RAIZ / "datos" / "pdfs", help="carpeta de los PDFs")
    parser.add_argument("--reprocesar", action="store_true", help="procesa también los que ya están listos")
    parser.add_argument("--solo-revisar", action="store_true", help="revisa el CSV sin procesar nada")
    parser.add_argument("--hilos", type=int, default=3, help="documentos que se procesan a la vez")
    args = parser.parse_args()
    if not args.csv.is_file():
        print(f"No existe {args.csv}")
        return 1
    con = db.abrir()
    try:
        r = cargar(con, args.csv, args.pdfs, args.reprocesar, args.solo_revisar, args.hilos)
    finally:
        con.close()
    return 1 if r["fallidos"] or r["invalidos"] else 0


if __name__ == "__main__":
    sys.exit(main())
