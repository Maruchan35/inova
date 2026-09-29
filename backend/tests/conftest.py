import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def cliente(tmp_path_factory):
    # Base de datos temporal con los datos de ejemplo: los tests no tocan datos/cabildo.db.
    ruta = tmp_path_factory.mktemp("db") / "test.db"
    subprocess.run([sys.executable, str(RAIZ / "datos" / "init_db.py"), str(ruta)], check=True)
    os.environ["DB_PATH"] = str(ruta)

    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)
