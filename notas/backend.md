# Notas — backend (Jorge)

## Estado (contrato v2)

- FastAPI en `backend/app/main.py` con las rutas de lectura de `docs/api.md`: lugares, secciones,
  documentos, páginas, búsqueda y preguntas con filtros, concentración. 14 tests (`pytest`).
- Falta todo el **procesamiento** de documentos: hoy el resumen y los puntos clave vienen del seed.

## Tareas (en orden) — el procesador de documentos

1. **`backend/app/procesamiento/`**: función `procesar(documento_id)` que:
   - extrae el texto de cada página del PDF (`pypdf`) → tabla `paginas` (la búsqueda se indexa sola);
   - cambia `estatus`: `procesando` → `listo` (o `error` con el mensaje);
   - genera `resumen` y `puntos_clave` (cada punto con su página).
2. **Resumen con IA (Gemini)** por bloques de páginas que luego se combinan; clave en `backend/.env`
   (nunca se sube, usar `.env.example`). **Respaldo sin IA** si no hay clave o falla: frases con
   montos, fechas y palabras clave. La demo nunca debe caerse.
3. **Script de carga masiva** que lea `datos/documentos.csv` (de Marko) y procese todos los PDFs.
4. **`POST /api/documentos`**: subir un PDF y procesarlo en segundo plano (formato en `docs/api.md`).
5. **Respuesta con IA en `/api/preguntar`** usando solo las citas encontradas.
6. Extraer contratos (proveedor, concepto, monto, página) → `proveedores` y `contratos`.
7. Opcional: OCR para PDFs escaneados.

## En progreso

- Rama:
- Tarea:

## Decisiones y problemas

- Procesar al subir, no al consultar: así la búsqueda responde en menos de 2 segundos.
