"""Procesador de documentos: PDF → páginas indexadas → resumen y puntos clave.

El trabajo pesado se hace una sola vez, al subir el documento; las consultas de los ciudadanos
solo leen lo ya procesado.
"""

import sqlite3
import time
from pathlib import Path

from pypdf import PdfReader

from . import llm
from .resumen import resumir_con_ia, resumir_sin_ia

# Última ejecución de cada documento (solo en memoria), para la página de prueba del motor.
BITACORA: dict[int, dict] = {}


def extraer_paginas(ruta: Path) -> list[str]:
    return [pagina.extract_text() or "" for pagina in PdfReader(ruta).pages]


def procesar(con: sqlite3.Connection, documento_id: int, ruta: Path) -> None:
    inicio = time.time()
    bitacora = BITACORA[documento_id] = {"motor": None, "segundos": None, "uso": {}, "aviso": None}
    con.execute("UPDATE documentos SET estatus = 'procesando', error = NULL WHERE id = ?", (documento_id,))
    con.commit()
    try:
        titulo = con.execute("SELECT titulo FROM documentos WHERE id = ?", (documento_id,)).fetchone()["titulo"]
        paginas = extraer_paginas(ruta)
        if not any(p.strip() for p in paginas):
            raise ValueError("El PDF no tiene texto seleccionable (¿es escaneado? necesita OCR)")

        resumen = puntos = None
        if llm.configurado():
            try:
                resumen, puntos = resumir_con_ia(titulo, paginas, bitacora["uso"])
                bitacora["motor"] = llm.modelo()
            except Exception as e:  # la IA falló: se usa el respaldo y se deja constancia
                bitacora["aviso"] = f"La IA falló ({type(e).__name__}: {e}); se usó el respaldo sin IA."
        else:
            bitacora["aviso"] = "No hay DEEPSEEK_API_KEY en backend/.env; se usó el respaldo sin IA."
        if resumen is None:
            resumen, puntos = resumir_sin_ia(titulo, paginas)
            bitacora["motor"] = "respaldo sin IA"

        con.execute("DELETE FROM paginas WHERE documento_id = ?", (documento_id,))
        con.execute("DELETE FROM puntos_clave WHERE documento_id = ?", (documento_id,))
        con.executemany(
            "INSERT INTO paginas (documento_id, numero, texto) VALUES (?, ?, ?)",
            [(documento_id, n, t) for n, t in enumerate(paginas, start=1)],
        )
        con.executemany(
            "INSERT INTO puntos_clave (documento_id, orden, texto, pagina) VALUES (?, ?, ?, ?)",
            [(documento_id, i, p["texto"], p["pagina"]) for i, p in enumerate(puntos, start=1)],
        )
        con.execute(
            "UPDATE documentos SET estatus = 'listo', total_paginas = ?, resumen = ? WHERE id = ?",
            (len(paginas), resumen, documento_id),
        )
        con.commit()
    except Exception as e:
        con.rollback()
        con.execute("UPDATE documentos SET estatus = 'error', error = ? WHERE id = ?", (str(e), documento_id))
        con.commit()
    finally:
        bitacora["segundos"] = round(time.time() - inicio, 1)
        bitacora["costo_usd"] = round(llm.costo_usd(bitacora["uso"]), 5)
