# Notas — datos (Marko)

## Estado

- Esquema en `datos/schema.sql`: actas, páginas (con índice de búsqueda), proveedores, contratos.
- `datos/seed.sql` tiene datos **ficticios** de ejemplo; `python datos/init_db.py` crea `datos/cabildo.db`.

## Tareas (en orden)

1. **Conseguir 5 actas reales de cabildo** en PDF (portal de transparencia del municipio). Guardarlas en
   `datos/pdfs/`.
2. **Script de ingesta** `datos/ingesta.py`: leer cada PDF página por página (librería `pypdf`) e insertar
   en `actas` y `paginas`. La búsqueda funciona sola gracias a los triggers.
3. **Contratos:** extraer de las actas proveedor, concepto, monto y página → tablas `proveedores` y
   `contratos`. Puede ser manual al principio (un `datos/contratos.sql`).
4. Cuando las actas reales estén cargadas, dejar de usar `seed.sql` (o dejarlo solo para tests).
5. Opcional: OCR para PDFs escaneados.

Si necesitas cambiar tablas o columnas, avisa a Jorge: el backend las lee y está en `docs/api.md`.

## En progreso

- Rama:
- Tarea:

## Decisiones y problemas

-
