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
- Tarea: Catálogo completo de 46 municipios de Guanajuato y Baja California creado en `datos/lugares.sql` e integrado en `datos/init_db.py`. Creada carpeta `datos/pdfs/` y plantilla `datos/documentos.csv` para carga masiva.

## Decisiones y problemas

- Se cargaron los 46 municipios oficiales de Guanajuato y municipios de Baja California para desbloquear las pruebas del backend y soportar la expansión de todo el estado.
- Se configuró `init_db.py` para cargar `lugares.sql` antes de `seed.sql`, con `INSERT OR IGNORE` para evitar conflictos de claves.
