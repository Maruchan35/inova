"""Descarga la base completa (documentos oficiales ya procesados) desde los Releases de GitHub.

    python datos/descargar_base.py                     # la versión más reciente
    python datos/descargar_base.py base-2026-09-30     # una versión en particular

Reemplaza datos/cabildo.db; si ya había una, la guarda antes como datos/cabildo.db.respaldo.
La base no trae suscripciones a avisos ni respuestas guardadas (datos personales).
Ojo: `python datos/init_db.py` la borra y deja solo la base de ejemplo.
"""

import json
import shutil
import sqlite3
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO = "Maruchan35/inova"
DATOS = Path(__file__).resolve().parent


def _json(url: str):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"}), timeout=60) as r:
        return json.load(r)


def buscar_version(etiqueta: str | None) -> dict:
    if etiqueta:
        return _json(f"https://api.github.com/repos/{REPO}/releases/tags/{etiqueta}")
    versiones = [v for v in _json(f"https://api.github.com/repos/{REPO}/releases?per_page=50")
                 if v["tag_name"].startswith("base-")]
    if not versiones:
        raise SystemExit("No hay ninguna versión de la base publicada todavía.")
    return max(versiones, key=lambda v: v["published_at"])


def descargar(url: str, destino: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as r, destino.open("wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        bajado, siguiente = 0, 0
        while bloque := r.read(1 << 20):
            f.write(bloque)
            bajado += len(bloque)
            if bajado >= siguiente:
                print(f"  {bajado / 1e6:.0f} de {total / 1e6:.0f} MB", flush=True)
                siguiente += 10_000_000


def main(etiqueta: str | None = None, destino: Path = DATOS / "cabildo.db") -> None:
    version = buscar_version(etiqueta)
    zips = [a for a in version["assets"] if a["name"].endswith(".zip")]
    if not zips:
        raise SystemExit(f"La versión {version['tag_name']} no tiene el archivo de la base.")
    print(f"Descargando {version['tag_name']} ({zips[0]['size'] / 1e6:.0f} MB)…")
    with tempfile.TemporaryDirectory() as tmp:
        archivo_zip = Path(tmp) / zips[0]["name"]
        descargar(zips[0]["browser_download_url"], archivo_zip)
        with zipfile.ZipFile(archivo_zip) as z:
            z.extract("cabildo.db", tmp)
        nueva = Path(tmp) / "cabildo.db"
        con = sqlite3.connect(nueva)
        try:
            if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise SystemExit("La base descargada está dañada; no se reemplazó nada. Inténtalo de nuevo.")
            documentos = con.execute("SELECT COUNT(*) FROM documentos WHERE estatus = 'listo'").fetchone()[0]
            municipios = con.execute("SELECT COUNT(*) FROM municipios").fetchone()[0]
        finally:
            con.close()
        if destino.exists():
            shutil.copy2(destino, destino.with_name(destino.name + ".respaldo"))
            print(f"La base anterior quedó en {destino.name}.respaldo")
        shutil.move(nueva, destino)
    print(f"Listo: {destino} con {documentos:,} documentos y {municipios:,} municipios.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
