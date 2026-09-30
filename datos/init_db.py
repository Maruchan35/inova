"""Crea la base de datos desde cero con el esquema y los datos de ejemplo.

    python datos/init_db.py                 # crea datos/cabildo.db
    python datos/init_db.py otra/ruta.db    # crea la base en otra ruta (la usan los tests)
"""

import sqlite3
import sys
from pathlib import Path

DATOS = Path(__file__).resolve().parent
RUTA_DEFAULT = DATOS / "cabildo.db"


def crear(ruta: Path = RUTA_DEFAULT) -> Path:
    ruta = Path(ruta)
    limpiar_tablas = False
    try:
        ruta.unlink(missing_ok=True)
    except PermissionError:
        # El archivo está abierto en un visor (ej. DB Browser for SQLite)
        limpiar_tablas = True

    con = sqlite3.connect(ruta)
    try:
        if limpiar_tablas:
            con.execute("PRAGMA foreign_keys = OFF;")
            tablas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'").fetchall()]
            for t in tablas:
                con.execute(f"DROP TABLE IF EXISTS {t}")
                con.execute(f"DROP VIEW IF EXISTS {t}")
            con.commit()
            con.execute("PRAGMA foreign_keys = ON;")
        con.executescript((DATOS / "schema.sql").read_text(encoding="utf-8"))
        lugares = DATOS / "lugares.sql"
        if lugares.is_file():
            con.executescript(lugares.read_text(encoding="utf-8"))
        con.executescript((DATOS / "seed.sql").read_text(encoding="utf-8"))
        obras = DATOS / "obras.sql"
        if obras.is_file():
            con.executescript(obras.read_text(encoding="utf-8"))
        con.commit()
    finally:
        con.close()
    return ruta


if __name__ == "__main__":
    ruta = crear(Path(sys.argv[1]) if len(sys.argv) > 1 else RUTA_DEFAULT)
    print(f"Base de datos creada: {ruta}")
