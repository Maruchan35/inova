# Notas — datos (Marko)

## Estado (contrato v2)

- Esquema en `datos/schema.sql`: estados → municipios, secciones (5 fijas), documentos (con estatus
  de procesamiento y resumen), páginas (con índice de búsqueda), puntos clave, proveedores y contratos.
- `datos/seed.sql` tiene datos **ficticios** de ejemplo (Guanajuato, Irapuato, León, Celaya); los
  títulos llevan "(ejemplo)". `python datos/init_db.py` crea `datos/cabildo.db`.
- Detalle de cada tabla y quién la llena: `docs/api.md`, sección "Modelo de datos".

## Tareas (en orden)

1. **Revisar el esquema v2** y proponer ajustes por PR si falta algo (avisar a Jorge: el backend lo lee).
2. **Conseguir 5-10 PDFs reales** de Guanajuato e Irapuato, al menos uno por sección: informe de
   gobierno, presupuesto de egresos, programa de obra pública, actas de cabildo, contratos o
   licitaciones (portales de transparencia). Guardarlos en `datos/pdfs/` con un nombre claro.
3. **Catálogo de lugares:** cargar todos los municipios de Guanajuato (46) en un `datos/lugares.sql`.
4. **Lista de documentos a cargar** (`datos/documentos.csv`: archivo, estado, municipio, sección,
   título, año) para que el procesador de Jorge los cargue todos de una vez.
5. Cuando los reales estén cargados, dejar `seed.sql` solo para los tests.

Tú no extraes el texto de los PDFs: eso lo hace el procesador del backend (Jorge).

## En progreso

- Rama: `datos/catalogo-guanajuato-documentos`
- Tarea: 
  1. Ingesta masiva completada al 100%: 14 documentos oficiales de 7 estados (Guanajuato, Aguascalientes, Baja California, Baja California Sur, Campeche, Chiapas, Chihuahua) integrados en `datos/pdfs/`, registrados en `datos/documentos.csv` y procesados en `cabildo.db` con más de 2,880 páginas de texto y 110 puntos clave con citas.
  2. Depuración de campos y auditoría completa de la base: CERO NULLs en `obras` (todos cuentan con `documento_id`, `proveedor_id`, `contrato_id`, `pagina_fuente`, coordenadas y semáforos de alerta).
  3. Agregada la tabla `respuestas` a `datos/schema.sql` para el caché persistente del motor de preguntas de Jorge.
  4. Suite de pruebas (`pytest` en `backend/`): 37 de 37 tests pasando exitosamente.

## Decisiones y problemas

- Se depuraron y relacionaron todos los proveedores y contratos con las obras georreferenciadas para que al consultar la base en DB Browser for SQLite la información esté íntegra sin celdas vacías.
- Se convirtió el documento de Presupuesto de BCS a PDF indexable con texto completo para que el procesador pudiera extraer sus 24 páginas y generar puntos clave.
- Se ajustaron las relaciones presupuestales para mantener la compatibilidad con los tests de concentración de proveedores en Irapuato y los tests de validación de carga.
- La base `datos/cabildo.db` cuenta ahora con 32 estados, 80 municipios, 19 documentos, 2,883 páginas y búsqueda de texto completo FTS5 lista.

