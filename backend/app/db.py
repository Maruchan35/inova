import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).resolve().parents[2] / "datos" / "cabildo.db"))


def conectar():
    """Dependencia de FastAPI: una conexión por petición."""
    if not DB_PATH.exists():
        raise RuntimeError(f"No existe la base de datos {DB_PATH}. Ejecuta: python datos/init_db.py")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()
