# Notas — backend (Jorge)

## Estado

- FastAPI en `backend/app/main.py`, con las rutas de `docs/api.md` funcionando sobre la base de datos.
- Tests en `backend/tests/` (`pytest`), usan una base temporal con los datos de ejemplo.

## Tareas (en orden)

1. **Respuesta con IA en `/api/preguntar`:** mandar la pregunta + las citas encontradas a un LLM (por
   ejemplo la API de Gemini, clave gratis en Google AI Studio) y devolver la respuesta redactada.
   La clave va en un archivo `.env` (nunca se sube). Si no hay clave, dejar la respuesta actual.
   **Regla:** que el LLM responda solo con lo que dicen las citas.
2. **Mejorar la búsqueda:** quitar palabras vacías ("cuánto", "quién", "costó"...) para que las citas
   sean más precisas; revisar que responda en menos de 2 segundos.
3. **Ruta para el grafo de proveedores** (proveedor ↔ actas ↔ montos) para el visualizador; acordar el
   formato con Alisson y añadirlo a `docs/api.md`.
4. Un test por cada ruta nueva.

## En progreso

- Rama:
- Tarea:

## Decisiones y problemas

-
