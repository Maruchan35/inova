import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).resolve().parents[2] / "datos" / "cabildo.db"))


def abrir() -> sqlite3.Connection:
    """Conexión suelta, para el procesamiento en segundo plano."""
    if not DB_PATH.exists():
        raise RuntimeError(f"No existe la base de datos {DB_PATH}. Ejecuta: python datos/init_db.py")
    # FastAPI puede abrir la conexión en un hilo y usarla en otro; cada petición usa la suya
    # de forma secuencial, así que desactivar la verificación de hilo es seguro.
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def conectar():
    """Dependencia de FastAPI: una conexión por petición."""
    con = abrir()
    try:
        yield con
    finally:
        con.close()
