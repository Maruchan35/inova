"""Configuración leída de variables de entorno y de backend/.env (que nunca se sube a Git)."""

import os
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _cargar_env(ruta: Path) -> None:
    # Las variables ya definidas en el entorno tienen prioridad sobre el archivo.
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env(BACKEND / ".env")

SUBIDOS_DIR = Path(os.environ.get("SUBIDOS_DIR", BACKEND / "subidos"))
