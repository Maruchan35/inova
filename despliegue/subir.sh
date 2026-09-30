#!/usr/bin/env bash
# Sube al servidor lo que no está en Git. Se corre en TU computadora (Git Bash), desde la raíz del repo:
#
#     bash despliegue/subir.sh azureuser@cabildoabierto.eastus.cloudapp.azure.com            # base y .env
#     bash despliegue/subir.sh azureuser@cabildoabierto.eastus.cloudapp.azure.com --whatsapp # además, la sesión del bot
#
# - datos/cabildo.db  → la base con todos los documentos (se copia con una copia segura, aunque el backend esté encendido)
# - backend/.env      → la clave de DeepSeek y el token del bot (nunca va a Git)
# - backend/whatsapp/sesion/ (con --whatsapp) → para no volver a escanear el QR. Apaga antes el bot de tu
#   computadora: la misma sesión en dos lados se desconecta.
# Los PDF originales (6.8 GB) no se suben: sin ellos la página ofrece el portal oficial de cada documento.
set -euo pipefail

DESTINO="${1:?Uso: bash despliegue/subir.sh usuario@servidor [--whatsapp]}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
PY="$RAIZ/backend/.venv/Scripts/python"; [ -x "$PY" ] || PY="$RAIZ/backend/.venv/bin/python"
COPIA="$(mktemp -d)/cabildo.db"

echo "== Copia segura de la base"
"$PY" - "$RAIZ/datos/cabildo.db" "$COPIA" <<'EOF'
import sqlite3, sys
origen, destino = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
origen.backup(destino)
destino.close(); origen.close()
EOF

echo "== Subiendo la base ($(du -h "$COPIA" | cut -f1)) y el .env"
ssh "$DESTINO" "mkdir -p inova/datos inova/backend"
scp -C "$COPIA" "$DESTINO:inova/datos/cabildo.db.nueva"
scp "$RAIZ/backend/.env" "$DESTINO:inova/backend/.env"
# En el servidor, el enlace de los avisos de WhatsApp apunta al propio servidor.
ssh "$DESTINO" "mv inova/datos/cabildo.db.nueva inova/datos/cabildo.db; chmod 600 inova/backend/.env; sed -i 's/$//' inova/backend/.env; sed -i 's|^ENLACE_DOCUMENTO=.*|ENLACE_DOCUMENTO=https://${DESTINO#*@}/documento/{id}|' inova/backend/.env"
rm -f "$COPIA"

if [ "${2:-}" = "--whatsapp" ]; then
  echo "== Subiendo la sesión del bot de WhatsApp"
  ssh "$DESTINO" "mkdir -p inova/backend/whatsapp"
  scp -r "$RAIZ/backend/whatsapp/sesion" "$DESTINO:inova/backend/whatsapp/"
fi

echo "Listo. Si el servidor ya estaba instalado: ssh $DESTINO 'sudo systemctl restart cabildo-backend cabildo-whatsapp'"
