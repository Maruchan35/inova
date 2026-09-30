#!/usr/bin/env bash
# Instala CabildoAbierto en una máquina Ubuntu 24.04 (pensado para Azure for Students).
# Se corre DENTRO de la máquina, con el usuario administrador (no root):
#
#     bash instalar.sh cabildoabierto.eastus.cloudapp.azure.com
#
# Se puede volver a correr: actualiza el código, recompila la página y reinicia los servicios.
# Antes o después hay que subir lo que no está en Git con `despliegue/subir.sh` (la base, el .env y,
# si se quiere, la sesión del bot de WhatsApp).
set -euo pipefail

DOMINIO="${1:?Uso: bash instalar.sh <dominio> (por ejemplo cabildoabierto.eastus.cloudapp.azure.com)}"
REPO="https://github.com/Maruchan35/inova.git"
DIR="$HOME/inova"
SITIO="/var/www/cabildo"

echo "== 1/6 Programas (Python, Node 22, Caddy)"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git curl unzip caddy
if ! command -v node >/dev/null || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

echo "== 2/6 Código"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else  # la carpeta puede existir ya con la base y el .env que subio subir.sh
  mkdir -p "$DIR"
  git -C "$DIR" init -q -b main
  git -C "$DIR" remote add origin "$REPO"
  git -C "$DIR" fetch -q origin main
  git -C "$DIR" checkout -q -f -B main origin/main
fi

echo "== 3/6 Backend"
python3 -m venv "$DIR/backend/.venv"
"$DIR/backend/.venv/bin/pip" install -q --upgrade pip
"$DIR/backend/.venv/bin/pip" install -q -r "$DIR/backend/requirements.txt"
if [ ! -f "$DIR/backend/.env" ]; then
  cp "$DIR/backend/.env.example" "$DIR/backend/.env"
  echo "   OJO: falta backend/.env con la clave de DeepSeek (súbelo con despliegue/subir.sh)"
fi
# El enlace que llega en los avisos de WhatsApp apunta a este servidor.
sed -i "s|^ENLACE_DOCUMENTO=.*|ENLACE_DOCUMENTO=https://$DOMINIO/documento/{id}|" "$DIR/backend/.env"
if [ ! -f "$DIR/datos/cabildo.db" ]; then
  echo "   No hay base: se baja la última publicada en GitHub (súbela con despliegue/subir.sh para traer la tuya)"
  "$DIR/backend/.venv/bin/python" "$DIR/datos/descargar_base.py"
fi

echo "== 4/6 Página (frontend)"
(cd "$DIR/frontend" && npm install --no-audit --no-fund && npm run build)
sudo mkdir -p "$SITIO"
sudo rm -rf "$SITIO"/*
sudo cp -r "$DIR/frontend/dist/." "$SITIO/"

echo "== 5/6 Bot de WhatsApp"
(cd "$DIR/backend/whatsapp" && npm install --no-audit --no-fund)

echo "== 6/6 Servicios y https"
sudo tee /etc/systemd/system/cabildo-backend.service >/dev/null <<EOF
[Unit]
Description=CabildoAbierto - backend (FastAPI)
After=network.target

[Service]
User=$USER
WorkingDirectory=$DIR/backend
ExecStart=$DIR/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/cabildo-whatsapp.service >/dev/null <<EOF
[Unit]
Description=CabildoAbierto - bot de WhatsApp
After=network.target cabildo-backend.service

[Service]
User=$USER
WorkingDirectory=$DIR/backend/whatsapp
ExecStart=/usr/bin/node bot.js
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Caddy saca el certificado https solo. Hacia afuera solo se abre lo que usa la página:
# ni las páginas de prueba, ni las rutas internas, ni subir documentos.
sudo tee /etc/caddy/Caddyfile >/dev/null <<EOF
$DOMINIO {
	encode gzip

	@privado path /api/prueba/* /api/interno/* /prueba /vista /docs /redoc /openapi.json
	respond @privado 404

	@escribir {
		method POST PUT PATCH DELETE
		not path /api/preguntar /api/voz /api/suscripciones /api/suscripciones/verificar /api/suscripciones/baja
	}
	respond @escribir 403

	handle /api/* {
		reverse_proxy 127.0.0.1:8000
	}
	handle {
		root * $SITIO
		try_files {path} /index.html
		file_server
	}
}
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now cabildo-backend cabildo-whatsapp
sudo systemctl restart cabildo-backend cabildo-whatsapp
sudo systemctl reload caddy || sudo systemctl restart caddy

echo
echo "Listo: https://$DOMINIO"
echo "Estado:  systemctl status cabildo-backend cabildo-whatsapp caddy"
echo "Bitácora: journalctl -u cabildo-backend -f"
echo "Si el bot de WhatsApp no tiene sesión, vincúlalo: en tu computadora corre"
echo "  ssh -L 3001:127.0.0.1:3001 $USER@$DOMINIO   y abre http://127.0.0.1:3001/qr"
