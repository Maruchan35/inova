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
  1. Catálogo completo de los 46 municipios de Guanajuato y Baja California integrado en `datos/lugares.sql`.
  2. Integración de los datos oficiales de Guanajuato (`Downloads/basedtos`): PDF oficial de SHCP con 4,680 proyectos copiado a `datos/pdfs/informe-extendido-guanajuato.pdf` y registrado en `datos/documentos.csv`.
  3. Extensión del esquema en `datos/schema.sql` agregando la tabla `obras` para el mapa cívico (latitud, longitud, presupuestos aprobado/modificado/ejercido, variación porcentual y semáforo de alerta `normal`, `precaucion`, `critico`).
  4. Generado `datos/obras.sql` con obras georreferenciadas en Irapuato (Centro, Las Flores, San Juan, Las Reinas) y municipios del estado (León, Celaya, Guanajuato Capital, San Luis de la Paz).
  5. `datos/init_db.py` actualizado y verificado: genera `datos/cabildo.db` sin errores.

## Decisiones y problemas

- Se usaron las coordenadas reales de colonias de Irapuato y municipios de Guanajuato para alimentar el mapa de Alisson (`frontend/`).
- Se incorporaron las métricas de variación presupuestal (Aprobado vs Modificado vs Ejercido) extraídas de la Cuenta Pública 2025 para respaldar el análisis cívico de sobrecostos.
- La tabla `obras` incluye `pagina_fuente` para mantener la regla de oro del proyecto: todo dato cita su foja exacta del documento oficial.

