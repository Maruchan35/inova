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

## Decisiones y problemas

- Procesar al subir, no al consultar: la búsqueda responde en menos de 2 segundos y la IA se paga
  una sola vez por documento, no por cada ciudadano que consulta.
- IA: DeepSeek `deepseek-flash`, el más barato (~$0.30 USD por millón de tokens de entrada en horario pico).
- **Modo pensar desactivado** (`"thinking": {"type": "disabled"}`): con él activo, el mismo PDF tardó
  25 s y costó 4 veces más (6,347 tokens de salida contra 475), sin mejorar el resumen.
- Estimación: un documento de 500 páginas cuesta ~$0.10-0.15 USD en procesarse, una sola vez.
- Pendiente para Marko: agregar Baja California (o todos los estados) al catálogo de lugares.
