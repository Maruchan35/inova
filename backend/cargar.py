"""Carga masiva: lee datos/documentos.csv y procesa todos sus PDFs de una vez.

    cd backend
    python cargar.py                  # carga lo que falte de datos/documentos.csv
    python cargar.py --solo-revisar   # revisa el CSV y los PDFs sin procesar nada
    python cargar.py --reprocesar     # vuelve a procesar también los que ya estaban listos

Formato del CSV (se acepta separado por comas o por punto y coma, como lo guarda Excel):

    archivo,estado,municipio,seccion,titulo,anio
    presupuesto-irapuato-2026.pdf,Guanajuato,Irapuato,presupuesto,Presupuesto de Egresos 2026,2026
    informe-estatal-2025.pdf,Guanajuato,,informes,Informe de Gobierno 2025,2025

- `archivo`: nombre del PDF dentro de datos/pdfs/ (o ruta relativa a esa carpeta).
- `estado` y `municipio`: nombres como están en la base (sin importar acentos ni mayúsculas).
  Municipio vacío = documento del gobierno estatal.
- `seccion`: clave de la sección (informes, presupuesto, obras, actas, contratos).
- `anio`: opcional.

Se puede ejecutar las veces que haga falta: un documento con el mismo `archivo` que ya está listo
se salta; si quedó a medias o con error, se vuelve a procesar sobre el mismo registro.
"""

import argparse
import csv
import io
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

from app import config  # noqa: F401  (carga backend/.env con la clave de DeepSeek)
from app import db, procesamiento
from app.procesamiento import llm

RAIZ = Path(__file__).resolve().parents[1]
COLUMNAS = ("archivo", "estado", "municipio", "seccion", "titulo", "anio")


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
    return [{c: (fila.get(c) or "").strip() for c in COLUMNAS} for fila in lector]


def clave_archivo(ruta: Path) -> str:
    """Lo que se guarda en documentos.archivo: ruta relativa al repo, igual en todas las computadoras."""
    try:
        return ruta.relative_to(RAIZ).as_posix()
    except ValueError:
        return ruta.as_posix()


def _inicio(ruta: Path) -> bytes:
    with ruta.open("rb") as f:
        return f.read(4)


def validar(con: sqlite3.Connection, filas: list[dict], carpeta_pdfs: Path) -> tuple[list[dict], list[str]]:
    """Convierte cada fila en un documento listo para insertar, o en un error con su número de línea."""
    estados = {normalizar(e["nombre"]): e for e in con.execute("SELECT id, nombre FROM estados")}
    municipios = {
        (m["estado_id"], normalizar(m["nombre"])): m for m in con.execute("SELECT id, estado_id, nombre FROM municipios")
    }
    secciones = {s["clave"]: s["id"] for s in con.execute("SELECT id, clave FROM secciones")}

    validos, errores, vistos = [], [], set()
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
            problemas.append(f"{fila['archivo']} no es un PDF")
        elif ruta in vistos:
            problemas.append(f"{fila['archivo']} está repetido en el CSV")
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
        })
    return validos, errores


def registrar(con: sqlite3.Connection, doc: dict, reprocesar: bool) -> int | None:
    """Crea el registro del documento, o reutiliza el existente. None = ya estaba listo, se salta."""
    existente = con.execute(
        "SELECT id, estatus FROM documentos WHERE archivo = ? ORDER BY id LIMIT 1", (doc["archivo"],)
    ).fetchone()
    datos = (doc["estado_id"], doc["municipio_id"], doc["seccion_id"], doc["titulo"], doc["anio"], doc["archivo"])
    if existente and existente["estatus"] == "listo" and not reprocesar:
        return None
    if existente:  # quedó a medias, con error, o se pidió reprocesar: se actualiza con lo que diga el CSV
        con.execute(
            "UPDATE documentos SET estado_id = ?, municipio_id = ?, seccion_id = ?, titulo = ?, anio = ?, archivo = ?"
            " WHERE id = ?",
            (*datos, existente["id"]),
        )
        documento_id = existente["id"]
    else:
        documento_id = con.execute(
            "INSERT INTO documentos (estado_id, municipio_id, seccion_id, titulo, anio, archivo) VALUES (?, ?, ?, ?, ?, ?)",
            datos,
        ).lastrowid
    con.commit()  # antes de procesar: si el procesamiento falla, su rollback no borra el registro
    return documento_id


def cargar(con: sqlite3.Connection, ruta_csv: Path, carpeta_pdfs: Path, reprocesar=False, solo_revisar=False) -> dict:
    validos, errores = validar(con, leer_csv(ruta_csv), carpeta_pdfs)
    for e in errores:
        print(f"  ERROR {e}")
    resultado = {"procesados": 0, "saltados": 0, "fallidos": 0, "invalidos": len(errores), "uso": {}, "segundos": 0.0}
    if solo_revisar:
        print(f"Revisión: {len(validos)} filas correctas, {len(errores)} con errores. No se procesó nada.")
        return resultado

    motor = llm.modelo() if llm.configurado() else "respaldo sin IA (no hay DEEPSEEK_API_KEY en backend/.env)"
    print(f"{len(validos)} documentos en el CSV · motor: {motor}")
    inicio = time.time()
    for n, doc in enumerate(validos, start=1):
        prefijo = f"[{n}/{len(validos)}] {doc['titulo']} - {doc['lugar']}"
        documento_id = registrar(con, doc, reprocesar)
        if documento_id is None:
            resultado["saltados"] += 1
            print(f"{prefijo}: ya estaba cargado, se salta")
            continue
        print(f"{prefijo}: procesando...", flush=True)
        procesamiento.procesar(con, documento_id, doc["ruta"])
        bitacora = procesamiento.BITACORA.pop(documento_id)
        for k, v in bitacora["uso"].items():
            resultado["uso"][k] = resultado["uso"].get(k, 0) + v
        fila = con.execute(
            "SELECT estatus, error, total_paginas, (SELECT COUNT(*) FROM puntos_clave WHERE documento_id = d.id) AS puntos"
            " FROM documentos d WHERE id = ?",
            (documento_id,),
        ).fetchone()
        if fila["estatus"] == "listo":
            resultado["procesados"] += 1
            print(
                f"    listo (id {documento_id}): {fila['total_paginas']} páginas, {fila['puntos']} puntos"
                f" · {bitacora['motor']} · {bitacora['segundos']} s · ${bitacora['costo_usd']:.4f} USD"
            )
        else:
            resultado["fallidos"] += 1
            print(f"    ERROR (id {documento_id}): {fila['error']}")
        if bitacora["aviso"] and llm.configurado():
            print(f"    Aviso: {bitacora['aviso']}")

    resultado["segundos"] = round(time.time() - inicio, 1)
    uso = resultado["uso"]
    print(
        f"\nTerminado: {resultado['procesados']} procesados, {resultado['saltados']} ya estaban cargados,"
        f" {resultado['fallidos']} con error, {resultado['invalidos']} filas inválidas en el CSV."
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
    args = parser.parse_args()
    if not args.csv.is_file():
        print(f"No existe {args.csv}")
        return 1
    con = db.abrir()
    try:
        r = cargar(con, args.csv, args.pdfs, args.reprocesar, args.solo_revisar)
    finally:
        con.close()
    return 1 if r["fallidos"] or r["invalidos"] else 0


if __name__ == "__main__":
    sys.exit(main())
