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
- `cargar.py` ya guarda los metadatos del CSV de Marko (`url_fuente`, `formato`, `sha256`, `fecha_publicacion`,
  `dependencia`), **rechaza un archivo que no coincide con su sha256**, avisa si un PDF parece impreso desde un
  navegador (así llegó el falso) y procesa varios a la vez (`--hilos`, 3 por defecto). Para montar los 65
  documentos faltan los archivos (están en la computadora de Marko): ponerlos en `datos/pdfs/` y correr
  `python cargar.py --solo-revisar` y luego `python cargar.py`.
- **Caché permanente:** las respuestas de la IA se guardan también en la tabla `respuestas`, así que
  sobreviven a los reinicios. Medido con DeepSeek real: 10 veces la misma pregunta (escrita distinto) = 1
  llamada; 15 personas a la vez = 1 llamada; preguntas distintas sobre el mismo informe: 99.8% del texto
  sale del caché de DeepSeek ($0.0008 contra $0.0315). Si cambias las instrucciones de la IA en
  `preguntas.py`, sube `VERSION_RESPUESTAS` para no servir respuestas viejas.
- **Búsqueda con miles de documentos:** sin palabras vacías ("cuánto", "qué", "hay"…), primero páginas con
  todas las palabras importantes y luego con alguna; el chatbot no busca el nombre del lugar ya filtrado.
  `cargar.py`: `--procesos N` (varios núcleos), `--omitir-escaneados` (lista en `pendientes_ocr.txt`), salta
  archivos repetidos por sha256; `cryptography` para PDFs encriptados.
- **El chatbot entiende la pregunta** (`backend/app/entender.py`): lugar (estados con alias como CDMX, edomex,
  NL; municipios de nombre único), sección (informes, presupuesto, obras, actas, contratos) y si pide un
  **panorama** ("háblame del informe de…", "qué dice el presupuesto…") o un **dato**. El lugar que dice la pregunta
  gana sobre la página. Primero elige documentos (título + páginas que tratan el tema) y luego:
  panorama → explica el documento con su inicio y sus páginas del tema (si hay varios parecidos, dice cuáles);
  dato → busca dentro de esos documentos. La respuesta trae `documentos` y `detalle.entendido`.
- **Cerebro v3** (rama `backend/cerebro-v3`, PR #24; 81 tests). Todo en `backend/app/preguntas.py`:
  - **Verificador de cifras** (`cifras`, `_verificar_cifras`): cada cifra de la respuesta se busca en las páginas
    que vio la IA. Acepta redondeos y "millones" ("3,200 millones" = "$3,200,000,000.00") y cifras como vienen en
    los PDF (pegadas al texto de la tabla, "13, 200", "$2,500.000,000.00"). Si está en una página no citada, se
    cita; si no está en ninguna, va en `detalle.cifras_sin_verificar` y el chatbot avisa.
  - **Memoria** (`_seguimiento`): `/api/preguntar` recibe `historial`. "¿y en León?", "¿y en 2024?", "¿qué dice de
    seguridad?" se buscan con el tema de la pregunta anterior (el lugar nuevo reemplaza al de antes) y la IA recibe
    las 2 últimas preguntas con su respuesta. Una pregunta con su lugar y su tema se toma como nueva.
  - **Comparar lugares** (`_con_comparacion`): `entender` devuelve todos los `lugares`; con 2 o más junta hasta
    3 páginas de cada uno. Para un estado solo usa documentos del gobierno del estado; para un municipio, un
    documento estatal solo cuenta si la página lo nombra. Si de un lugar no hay nada, se le dice a la IA.
  - **Caché más listo**: la clave usa las palabras importantes ordenadas (`_clave_pregunta`), así "¿qué dice el
    presupuesto de Jalisco?" y "háblame del presupuesto de jalisco" son la misma. "no", "sin", "cuánto"… se quedan.
  - **Tope de gasto diario** (`DEEPSEEK_TOPE_DIARIO_USD`, 3 por defecto): el gasto del día se lleva en
    `backend/gasto_ia.json`; al llegar al tope responde sin IA hasta el día siguiente.
  - **Preguntas sugeridas**: `GET /api/preguntas-sugeridas` (portada, estado, municipio o documento) y
    `python precalentar.py` para dejarlas en el caché antes de la demo (51 preguntas ≈ $0.04 USD fuera de hora pico).
  - Orden de documentos: primero los del gobierno del estado si se pregunta por un estado, el año que pide la
    pregunta, y las páginas que tratan el tema cuentan con tope (un anexo de 1,000 páginas ya no gana solo por tamaño).
  - `llm.py` reintenta si DeepSeek responde 429 o 5xx. Un 402 es **sin saldo**: hay que recargar en
    platform.deepseek.com; mientras tanto el chatbot responde con los fragmentos.
- **Reclasificación con IA** (`python reclasificar.py`): ya se corrió con los 1,687 documentos (1,626 títulos
  nuevos, 180 cambios de sección, año y una descripción de 1-2 frases). **Resúmenes con IA**
  (`python resumir.py`): van 232; faltan ~1,450 (~$3 USD fuera de hora pico, lee hasta 120 mil caracteres por
  documento; sigue donde se quedó y se detiene solo si se acaba el saldo).
- **Versión final v2.2.0** (rama `backend/version-final-v2.2.0`): la v2.2.0 de Marko y Alisson (mapa interactivo,
  WhatsApp flotante, visor nuevo, etiqueta de versión) unida con el cerebro v3. Único conflicto: el final de
  `frontend/src/App.css`, donde se conservaron los estilos de ambos. `GET /api/estados` trae `latitud`/`longitud`.
- Siguiente: terminar los resúmenes cuando haya saldo y publicar la base nueva en Releases (sin datos
  personales); leer Word y Excel; extraer contratos a `proveedores`/`contratos`; OCR de los escaneados.
- Resuelto de datos (Marko): claves INEGI corregidas en Guanajuato (San Miguel 11003 y 34..46 ajustadas), Oaxaca (desambiguados San Juan y San Pedro Mixtepec con distritos) y Chiapas (Honduras de la Sierra 07125 sin duplicados). Catálogo de 2,475 municipios 100% verificado.

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

- **Modo por voz** (30 sep): `backend/app/voz.py` y `POST /api/voz` deciden qué hacer con lo que dijo la persona (ir a un lugar y sección, inicio, atrás, o pregunta para el chatbot) reutilizando `entender`, sin IA. 19 tests en `tests/test_voz.py` (101 en total). El servidor público debe permitir `POST /api/voz`.
