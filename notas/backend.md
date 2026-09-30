# Notas — backend (Jorge)

## Estado (contrato v2)

- FastAPI en `backend/app/main.py` con las rutas de `docs/api.md`: lugares, secciones, documentos,
  páginas, búsqueda y preguntas con filtros, concentración y subida de documentos. 21 tests (`pytest`).
- **Motor de procesamiento** en `backend/app/procesamiento/`: PDF → texto por página (pypdf) → índice
  de búsqueda → resumen y puntos clave, cada uno con su página.
  - Con IA: DeepSeek `deepseek-flash`, por bloques de ~120k caracteres que luego se combinan.
  - **Respaldo sin IA** si no hay clave o la IA falla: fragmentos con cifras. La demo nunca se cae.
  - Se descarta cualquier punto de la IA que no traiga una página válida.
- `POST /api/documentos`: subida + procesamiento en segundo plano.
- **Página de prueba del motor:** http://127.0.0.1:8000/prueba (no es parte del contrato). Sube un PDF
  y muestra estatus, motor usado, tiempo, tokens, costo aproximado, resumen, puntos y buscador.
- Probado con el Presupuesto Ciudadano 2026 de **Baja California** (22 páginas):
  - sin IA: 0.3 s;
  - con `deepseek-flash` sin modo pensar: **3 s, $0.002 USD**, 8 puntos, las 23 cifras citadas
    verificadas en su página.
- **Vista previa ciudadana (provisional):** http://127.0.0.1:8000/vista (`backend/app/vista.html`, no es parte
  del contrato ni reemplaza el frontend de Alisson). Inicio con buscador de lugar, página de lugar con
  secciones, preguntas y concentración de proveedores, página de documento con resumen, puntos clave y
  visor de páginas. Todo sale de la API.
- **Carga masiva** en `backend/cargar.py` (ver su docstring): lee `datos/documentos.csv`, busca los PDFs
  en `datos/pdfs/` y procesa cada uno con `procesamiento.procesar()`. Muestra avance, tiempo, tokens y
  costo total. `--solo-revisar` revisa el CSV sin procesar; `--reprocesar` rehace los que ya están listos.
  - Estado y municipio por **nombre** (sin importar acentos ni mayúsculas); sección por clave.
  - Acepta CSV de Excel en español (`;`, cp1252, encabezados con acentos).
  - Se puede volver a ejecutar: salta los `listo` con el mismo `archivo` (se guarda como
    `datos/pdfs/<nombre>`) y retoma los que quedaron con error o a medias, sin duplicar.
  - 4 tests en `tests/test_cargar.py`.
- **Cerebro de `/api/preguntar`** en `backend/app/preguntas.py` (búsqueda movida a `app/busqueda.py`).
  Mismo formato de salida que en `docs/api.md`. En orden:
  1. **Caché propio en memoria:** misma pregunta (sin acentos/mayúsculas/signos) + mismos filtros + misma
     "huella" de documentos listos en ese lugar → respuesta guardada, 0 s y $0. Si llegan varias iguales
     a la vez, solo la primera llama a la IA. Un documento nuevo en el lugar cambia la huella. Se vacía al
     reiniciar el servidor (y no se entera si se reprocesa un documento con otro PDF: reiniciar).
  2. Con `documento_id`: **documento completo** con `[Página N]`, siempre primero y siempre igual → el caché
     de DeepSeek cobra esa parte 50 veces más barata ($0.006 vs $0.30 por millón). Medido: 99.5% de la
     entrada salió del caché desde la 2ª pregunta.
  3. Sin `documento_id` (lugar/sección): las 6 páginas más relevantes de la búsqueda. Sin resultados → no
     se llama a la IA.
  4. Reglas: solo datos de los textos, cifras copiadas tal cual (**sin hacer cuentas**: la IA convertía
     porcentajes a pesos), cada dato con su página; se descartan páginas que no se le mandaron. Si la IA
     falla o responde un dato sin página → respaldo sin IA (y no se guarda).
  - `GET /api/prueba/preguntas`: bitácora (origen, modo, tiempo, tokens, costo). `/vista` la muestra debajo
    de cada respuesta para la demo.
  - Con DeepSeek real y los datos de ejemplo: ~1 s y ~$0.0002 USD por pregunta.
  - 10 tests en `tests/test_preguntar.py` con IA simulada (37 en total).
- **Avisos por WhatsApp** (rama `backend/notificaciones`):
  - `backend/whatsapp/bot.js` (Node + Baileys): WhatsApp **normal** vinculado con QR como dispositivo
    (http://127.0.0.1:3001/qr). Va contra las reglas de WhatsApp: usar un chip de repuesto. Manda en fila con
    pausas de 4-9 s y atiende "BAJA". La sesión queda en `backend/whatsapp/sesion/` (ignorada por Git).
    Arranque: `cd backend/whatsapp` → `npm install` → `npm start`.
  - `backend/app/notificaciones.py`: suscribirse con código de 6 dígitos por WhatsApp (máx. 3 códigos por
    número por hora), verificar, baja (token o "BAJA"), y aviso automático al terminar de procesar un
    documento (título + 2 puntos clave con página + enlace). Un aviso por documento y teléfono.
    Quien sigue un municipio recibe sus documentos y los estatales; quien sigue un estado, solo los estatales.
  - Rutas nuevas (proponer en `docs/api.md`): `POST /api/suscripciones`, `POST /api/suscripciones/verificar`,
    `POST /api/suscripciones/baja`; internas: `POST /api/interno/baja` (token del bot), `GET /api/prueba/avisos`.
  - `.env`: `WHATSAPP_BOT_URL`, `WHATSAPP_BOT_TOKEN`, `ENLACE_DOCUMENTO` (dirección pública con `{id}`).
    Sin `WHATSAPP_BOT_URL` es "modo prueba": los mensajes solo quedan en `/api/prueba/avisos`.
  - Tablas `suscripciones` y `notificaciones` en `datos/schema.sql` (PR #7 de Marko). 8 tests en
    `tests/test_notificaciones.py`. `/api/estados/{id}` y `/api/municipios/{id}` traen `latitud`/`longitud`
    reales (catálogo INEGI) para el mapa. 46 tests en total.

## Tareas (en orden)

1. ~~Script de carga masiva~~ (PR #4, en `main`). Falta probarlo con los PDFs reales de Marko.
3. ~~Respuesta con IA en `/api/preguntar` con caché~~ (rama `backend/respuesta-ia`). Falta medir tiempo y
   costo con un PDF real de cientos de páginas. Cuando Marko agregue la tabla `respuestas`, pasar el caché
   de memoria a la base.
4. Extraer contratos (proveedor, concepto, monto, página) → `proveedores` y `contratos`.
5. Opcional: OCR para PDFs escaneados.

## En progreso

- **Versión 2 en `main` (etiqueta `v2.0`)**: backend + datos de Marko (catálogo INEGI, metadatos, tablas de
  avisos) + frontend de Alisson (direcciones propias, formulario de WhatsApp, mapa con coordenadas reales).
  Probado de punta a punta el 29 de sep de 2026: el bot envió código, bienvenida y el aviso del informe real.
- Siguiente: leer Word y Excel (Marko ya tiene 2 Excel oficiales en el CSV), guardar en `documentos` las
  columnas nuevas del CSV (`url_fuente`, `sha256`…, y verificar el hash), verificador de páginas de las
  cifras, caché de preguntas en la tabla `respuestas`, y botón "ver documento oficial" con `url_fuente`.
- Pendiente de datos (Marko): claves INEGI recorridas en 14 municipios de Guanajuato, 2 municipios de
  Oaxaca perdidos por nombre repetido y la clave 07125 de Chiapas.

## Para retomar en una sesión nueva (léelo primero)

1. Crea una rama nueva desde `main` para cada tarea (`git fetch origin` y `git switch -c backend/<tarea> origin/main`).
   El repo está en `Documents\inova\inova` (la carpeta de afuera es otro repo viejo: no hagas push desde ahí).
   Para correr todo: backend (`uvicorn`), frontend (`npm run dev`) y, para avisos reales, el bot
   (`cd backend/whatsapp` → `npm install` → `npm start`; la sesión vinculada queda en `backend/whatsapp/sesion/`).
2. **Clave de DeepSeek:** está en `backend/.env` (solo local, Git la ignora). Si no existe en esta
   computadora, pídesela al usuario y créala con el formato de `backend/.env.example`. **Nunca la subas.**
3. **Base de datos local:** `python datos/init_db.py` la borra y la recrea con los datos de ejemplo.
   Baja California todavía no está en `datos/seed.sql` (pendiente de Marko). Para probar el PDF de
   Baja California, agrégala solo en local:
   `python -c "import sqlite3; c=sqlite3.connect('datos/cabildo.db'); c.execute(\"INSERT INTO estados VALUES (2, 'Baja California')\"); c.commit()"`
4. **Probar el motor:** `cd backend` → `.venv\Scripts\activate` → `uvicorn app.main:app --reload --port 8000`
   → abrir http://127.0.0.1:8000/prueba. PDF de prueba del usuario: `E:\descargas\Presupuesto-Ciudadano-2026.pdf`.
5. **Carga masiva (hecha):** `cd backend` → `python cargar.py --solo-revisar` y luego `python cargar.py`.
   Formato del CSV (**confirmarlo con Marko**, que lo llena): `archivo,estado,municipio,seccion,titulo,anio`,
   con los PDFs en `datos/pdfs/`. Si Marko aún no tiene el CSV: `--csv` y `--pdfs` apuntan a otro lugar.
6. **Preguntas con IA (hecho):** ver "Cerebro" arriba. Si cambias los textos para la IA en `preguntas.py`,
   **reinicia el servidor**: el caché propio guarda las respuestas viejas y `--reload` a veces no detecta
   el cambio en Windows.
7. Siguiente: extraer contratos a `proveedores`/`contratos`.

Cosas a saber de esta computadora (Windows):
- La terminal del usuario es **PowerShell 5.1**: no acepta `&&`; dale comandos de una línea o separados.
- `curl` en Git Bash manda mal los acentos; para probar la API con acentos usa un archivo JSON o Python.
- Para apagar servidores de prueba, cierra solo el proceso de su puerto (nunca todos los `node`/`python`).
- Para unir a `main` hay que abrir un PR en GitHub (los hooks bloquean el push directo, y está bien así).

## Decisiones y problemas

- Procesar al subir, no al consultar: la búsqueda responde en menos de 2 segundos y la IA se paga
  una sola vez por documento, no por cada ciudadano que consulta.
- IA: DeepSeek `deepseek-flash`, el más barato (~$0.30 USD por millón de tokens de entrada en horario pico).
- **Modo pensar desactivado** (`"thinking": {"type": "disabled"}`): con él activo, el mismo PDF tardó
  25 s y costó 4 veces más (6,347 tokens de salida contra 475), sin mejorar el resumen.
- Estimación: un documento de 500 páginas cuesta ~$0.10-0.15 USD en procesarse, una sola vez.
- Pendiente para Marko: agregar Baja California (o todos los estados) al catálogo de lugares, confirmar el
  formato de `datos/documentos.csv` y agregar la tabla `respuestas` (caché de preguntas permanente).
