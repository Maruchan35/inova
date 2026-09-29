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
    ruta.unlink(missing_ok=True)
    con = sqlite3.connect(ruta)
    try:
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
