"""Ingesta masiva de todos los documentos oficiales y proyectos a datos/cabildo.db

Lee datos/documentos.csv, extrae páginas y texto de cada PDF en datos/pdfs/,
genera resumen y puntos clave con citas verificables, e indexa todo en FTS5.
"""

import csv
import sqlite3
import sys
import time
from pathlib import Path

import pypdf

# Agregar backend al path para reutilizar lógica de resumen sin IA
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))
from app.procesamiento.resumen import resumir_sin_ia  # noqa: E402


def ingestar(ruta_db: Path = RAIZ / "datos" / "cabildo.db") -> dict:
    inicio = time.time()
    con = sqlite3.connect(ruta_db)
    con.row_factory = sqlite3.Row

    estados = {e["nombre"].lower(): e["id"] for e in con.execute("SELECT id, nombre FROM estados")}
    secciones = {s["clave"].lower(): s["id"] for s in con.execute("SELECT id, clave FROM secciones")}

    csv_path = RAIZ / "datos" / "documentos.csv"
    pdfs_dir = RAIZ / "datos" / "pdfs"

    with csv_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Iniciando ingesta de {len(rows)} documentos en {ruta_db.name}...")
    procesados = 0
    paginas_totales = 0
    puntos_totales = 0

    for i, r in enumerate(rows, 1):
        archivo_nombre = r["archivo"]
        fpath = pdfs_dir / archivo_nombre
        if not fpath.exists():
            print(f"[{i}/{len(rows)}] Archivo no encontrado en disco: {fpath}")
            continue

        estado_id = estados.get(r["estado"].lower())
        seccion_id = secciones.get(r["seccion"].lower())
        anio = int(r["anio"]) if r["anio"] and r["anio"].isdigit() else None

        existing = con.execute("SELECT id, estatus FROM documentos WHERE archivo LIKE ?", (f"%{archivo_nombre}%",)).fetchone()
        if existing:
            doc_id = existing["id"]
            con.execute(
                """
                UPDATE documentos
                SET estado_id = ?, seccion_id = ?, titulo = ?, anio = ?,
                    url_fuente = ?, formato = ?, sha256 = ?, fecha_publicacion = ?, dependencia = ?
                WHERE id = ?
                """,
                (estado_id, seccion_id, r["titulo"], anio, r["url_fuente"], r["formato"], r["sha256"], r["fecha_publicacion"], r["dependencia"], doc_id),
            )
        else:
            cursor = con.execute(
                """
                INSERT INTO documentos (
                    estado_id, municipio_id, seccion_id, titulo, anio, fecha, archivo,
                    url_fuente, formato, sha256, fecha_publicacion, dependencia, total_paginas, estatus
                ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'procesando')
                """,
                (estado_id, seccion_id, r["titulo"], anio, r["fecha_publicacion"], f"datos/pdfs/{archivo_nombre}",
                 r["url_fuente"], r["formato"], r["sha256"], r["fecha_publicacion"], r["dependencia"]),
            )
            doc_id = cursor.lastrowid

        if fpath.suffix.lower() == ".pdf":
            try:
                reader = pypdf.PdfReader(str(fpath))
                paginas = [p.extract_text() or "" for p in reader.pages]
                num_paginas = len(paginas)

                if any(p.strip() for p in paginas):
                    resumen, puntos = resumir_sin_ia(r["titulo"], paginas)
                else:
                    resumen = f"Documento escaneado de {num_paginas} páginas. Requiere procesamiento OCR."
                    puntos = []

                con.execute("DELETE FROM paginas WHERE documento_id = ?", (doc_id,))
                con.execute("DELETE FROM puntos_clave WHERE documento_id = ?", (doc_id,))

                con.executemany(
                    "INSERT INTO paginas (documento_id, numero, texto) VALUES (?, ?, ?)",
                    [(doc_id, n, t) for n, t in enumerate(paginas, 1)],
                )
                con.executemany(
                    "INSERT INTO puntos_clave (documento_id, orden, texto, pagina) VALUES (?, ?, ?, ?)",
                    [(doc_id, idx, p["texto"], p["pagina"]) for idx, p in enumerate(puntos, 1)],
                )
                con.execute(
                    "UPDATE documentos SET estatus = 'listo', total_paginas = ?, resumen = ? WHERE id = ?",
                    (num_paginas, resumen, doc_id),
                )
                paginas_totales += num_paginas
                puntos_totales += len(puntos)
                procesados += 1
            except Exception as e:
                con.execute("UPDATE documentos SET estatus = 'error', error = ? WHERE id = ?", (str(e), doc_id))
                print(f"Error procesando {archivo_nombre}: {e}")
        elif fpath.suffix.lower() == ".xlsx":
            con.execute(
                "UPDATE documentos SET estatus = 'listo', total_paginas = 1, resumen = ? WHERE id = ?",
                (f"Base analítica de datos abiertos en formato {r['formato'].upper()} ({r['dependencia']}).", doc_id),
            )
            procesados += 1

        con.commit()
        if i % 10 == 0 or i == len(rows):
            print(f"Progreso: {i}/{len(rows)} documentos...")

    duracion = round(time.time() - inicio, 1)
    print(f"Ingesta terminada en {duracion} s: {procesados} documentos, {paginas_totales:,} páginas, {puntos_totales:,} puntos clave.")
    con.close()
    return {"procesados": procesados, "paginas": paginas_totales, "puntos": puntos_totales, "duracion": duracion}


if __name__ == "__main__":
    ingestar()
