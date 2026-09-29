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

## Tareas (en orden)

1. **Script de carga masiva** que lea `datos/documentos.csv` (de Marko) y procese todos los PDFs.
3. **Respuesta con IA en `/api/preguntar`** usando solo las citas encontradas.
4. Extraer contratos (proveedor, concepto, monto, página) → `proveedores` y `contratos`.
5. Opcional: OCR para PDFs escaneados.

## En progreso

- Rama: `backend/procesamiento`
- Tarea: motor listo y probado con IA real; siguiente: carga masiva

## Para retomar en una sesión nueva (léelo primero)

1. Rama de trabajo: **`backend/carga-masiva`** (creada desde `main` con el motor ya unido en el PR #3).
   `git checkout backend/carga-masiva && git fetch origin && git merge origin/main`.
2. **Clave de DeepSeek:** está en `backend/.env` (solo local, Git la ignora). Si no existe en esta
   computadora, pídesela al usuario y créala con el formato de `backend/.env.example`. **Nunca la subas.**
3. **Base de datos local:** `python datos/init_db.py` la borra y la recrea con los datos de ejemplo.
   Baja California todavía no está en `datos/seed.sql` (pendiente de Marko). Para probar el PDF de
   Baja California, agrégala solo en local:
   `python -c "import sqlite3; c=sqlite3.connect('datos/cabildo.db'); c.execute(\"INSERT INTO estados VALUES (2, 'Baja California')\"); c.commit()"`
4. **Probar el motor:** `cd backend` → `.venv\Scripts\activate` → `uvicorn app.main:app --reload --port 8000`
   → abrir http://127.0.0.1:8000/prueba. PDF de prueba del usuario: `E:\descargas\Presupuesto-Ciudadano-2026.pdf`.
5. **Siguiente tarea: carga masiva.** Script `backend/cargar.py` que lea `datos/documentos.csv` y procese
   cada PDF con `procesamiento.procesar()`. Formato propuesto del CSV (confirmarlo con Marko, que lo llena):
   `archivo,estado,municipio,seccion,titulo,anio` (municipio vacío = documento estatal; `seccion` = clave).
   Que se pueda volver a ejecutar sin duplicar documentos (por ejemplo, saltar los que ya tengan el mismo
   `archivo`) y que muestre avance, tiempo y costo total.
6. Luego: respuesta con IA en `/api/preguntar` (solo con las citas; mismo formato de salida) y extraer
   contratos a `proveedores`/`contratos`.

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
- Pendiente para Marko: agregar Baja California (o todos los estados) al catálogo de lugares.
