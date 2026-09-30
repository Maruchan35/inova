# Poner CabildoAbierto en internet (Azure for Students)

Una sola máquina virtual con todo: backend, página, bot de WhatsApp y https. La dirección queda como
`https://<nombre>.<región>.cloudapp.azure.com` (el subdominio gratis de Azure).

> Estos scripts todavía no se han probado en una máquina real. Si algo falla, el mensaje de error dice en
> qué paso (1/6 a 6/6).

## 1. Crear la cuenta y la máquina (lo hace una persona, en el navegador)

1. Activa **Azure for Students** con tu correo de la escuela: <https://azure.microsoft.com/free/students>
   (100 dólares de crédito, sin tarjeta).
2. En <https://portal.azure.com> → **Máquinas virtuales** → **Crear**:
   - Imagen: **Ubuntu Server 24.04 LTS**.
   - Tamaño: **B2s** (2 núcleos, 4 GB; unos 30 dólares al mes del crédito). Con B1s (1 GB, gratis 12 meses)
     la página no alcanza a compilarse.
   - Autenticación: **Clave pública SSH**, usuario `azureuser`. Descarga el archivo `.pem` cuando lo ofrezca.
   - Puertos de entrada: **SSH (22), HTTP (80) y HTTPS (443)**.
   - Disco: 30 GB (64 GB si después se quieren subir los PDF originales).
3. Ya creada: **Información general** → **Nombre DNS** → *Configurar* → escribe un nombre (por ejemplo
   `cabildoabierto`) y guarda. Esa es la dirección: `cabildoabierto.<región>.cloudapp.azure.com`.

## 2. Instalar (desde tu computadora, en Git Bash, en la raíz del repo)

```bash
# Una sola vez: que ssh use la clave que bajaste
mkdir -p ~/.ssh && cp /ruta/a/la-clave.pem ~/.ssh/azure.pem && chmod 600 ~/.ssh/azure.pem
printf 'Host *.cloudapp.azure.com\n  User azureuser\n  IdentityFile ~/.ssh/azure.pem\n' >> ~/.ssh/config

SERVIDOR=cabildoabierto.eastus.cloudapp.azure.com     # tu dirección

# 1) Sube la base y el .env (lo que no está en Git). Con --whatsapp también la sesión del bot.
bash despliegue/subir.sh azureuser@$SERVIDOR

# 2) Instala todo en la máquina (unos 5 minutos)
scp despliegue/instalar.sh azureuser@$SERVIDOR:
ssh azureuser@$SERVIDOR "bash instalar.sh $SERVIDOR"
```

Abre `https://<tu dirección>`. El certificado https tarda unos segundos la primera vez.

## 3. Actualizar después

- **Código nuevo en `main`:** `ssh azureuser@$SERVIDOR "bash instalar.sh $SERVIDOR"` (baja, recompila y reinicia).
- **Base nueva:** `bash despliegue/subir.sh azureuser@$SERVIDOR` y luego
  `ssh azureuser@$SERVIDOR 'sudo systemctl restart cabildo-backend'`.

## Qué queda abierto hacia afuera

Solo la página y las rutas que usa (`/api/...` de consulta, `/api/preguntar`, `/api/voz` y las de
suscripciones). Las páginas de prueba, las rutas internas y subir documentos responden 404/403. El gasto en
IA lo limita `DEEPSEEK_TOPE_DIARIO_USD` del `.env`.

## Cosas a saber

- **WhatsApp:** la sesión del bot solo puede estar en un lugar. Si la subes con `--whatsapp`, apaga el bot de
  tu computadora. Para vincular desde cero: `ssh -L 3001:127.0.0.1:3001 azureuser@$SERVIDOR` y abre
  <http://127.0.0.1:3001/qr>.
- **PDF originales:** no se suben (6.8 GB). Sin ellos, el botón "Abrir PDF original" no aparece y queda
  "Portal oficial", que lleva a la liga del gobierno.
- **Apagar para no gastar crédito:** en el portal, *Detener* la máquina (desasignar). La dirección se conserva.
- **Bitácoras:** `journalctl -u cabildo-backend -f`, `journalctl -u cabildo-whatsapp -f`, `journalctl -u caddy -f`.
