# Notas — datos (Marko)

## Estado actual del bloque `datos/`

- **Esquema de base de datos (`datos/schema.sql`):**
  - Catálogo geográfico completo con clave INEGI y coordenadas (`latitud`, `longitud`): 32 estados y 2,475 municipios de la República Mexicana.
  - Tabla `documentos` enriquecida con metadatos oficiales de auditoría y procedencia: `url_fuente`, `formato`, `sha256`, `fecha_publicacion`, `dependencia`.
  - Tabla `obras` reservada en el esquema para vincular obras georreferenciadas con auditoría presupuestal real.
  - Tabla `respuestas` agregada para el caché persistente de preguntas ciudadanas del backend.
  - Tablas `suscripciones` y `notificaciones` añadidas para el sistema de alertas ciudadanas por WhatsApp/SMS con control estricto antiduplicados (`UNIQUE(suscripcion_id, documento_id)`).
- **Catálogo de lugares (`datos/lugares.sql`):**
  - Creado con los 32 estados y los 2,475 municipios de México con coordenadas oficiales de cabeceras municipales.
  - Conserva estrictamente los IDs canónicos preexistentes para compatibilidad total con el backend y tests:
    - Guanajuato = 1 (Irapuato = 1, León = 2, Celaya = 3, y municipios 1..46)
    - Baja California = 2 (municipios 101..107)
- **Base de datos semilla (`datos/seed.sql`):**
  - Contiene datos mínimos de prueba aislados para garantizar que la suite de pruebas del backend corra sin dependencias externas.
- **Base de datos local (`datos/cabildo.db`):**
  - Se inicializa ejecutando `python datos/init_db.py`. El script fue blindado para manejar de forma segura bloqueos de archivo en Windows (`WinError 32`) si la base está abierta en DB Browser for SQLite.

---

## 0. Limpieza y rectificación de datos no oficiales

1. **Eliminación de archivos no oficiales:**
   - Se removió `datos/pdfs/informe-extendido-guanajuato.pdf` y los informes extendidos impresos desde navegador (Chrome). No son decretos ni publicaciones oficiales de la SHCP ni de los gobiernos estatales.
   - Se removieron del control de versiones de Git todos los binarios PDF en `datos/pdfs/` mediante `.gitignore`.
2. **Depuración de `datos/obras.sql`:**
   - Se vaciaron los registros inventados o no respaldados por decretos oficiales. La tabla `obras` permanece en `schema.sql` para cuando se cuente con las obras oficiales del Programa General de Obra (PGO) o decretos verificados.
3. **Rectificación de notas anteriores:**
   - Se corrigen las menciones pasadas que catalogaban los resúmenes impresos como "PDF oficial de SHCP" o "extraídas de la Cuenta Pública 2025". Dichos datos carecían de trazabilidad jurídica.

---

## 1. Catálogo nacional de documentos oficiales (32 entidades federativas)

Se integraron y procesaron los documentos de las carpetas `Estados` y `PRESUPUESTO DE EGRESOS ESTADOS FALTANTES`, alcanzando una **cobertura nacional del 100% (32 de 32 estados)** con documentos oficiales:

- **Total de documentos procesados en `cabildo.db`:** 70 registros (65 reales + 5 de prueba aislados en `seed.sql`).
- **Volumen de texto indexado:** 9,584 páginas extraídas con índice de búsqueda de texto completo FTS5.
- **Puntos clave y citas ciudadanas:** 334 puntos clave extraídos con indicación estricta de página de origen.
- **Carpetas gestionadas:**
  - `PRESUPUESTO DE EGRESOS ESTADOS FALTANTES`: 25 decretos y leyes de egresos estatales (24 PDFs + 1 XLSX).
  - `Estados`: 25 informes de proyectos y obras de inversión pública estatal.
- **Archivo de catálogo:** `datos/documentos.csv` contiene el inventario exhaustivo de los 65 documentos con su estado, título, año, liga oficial de procedencia (`url_fuente`), hash SHA-256 y secretaría emisora.
- **Script de carga masiva:** Se incorporó `datos/cargar_catalogo.py` para reconstruir la base o reingestar todos los documentos de `documentos.csv` en cualquier momento.

### Nota técnica sobre documentos escaneados vs texto nativo:
- **Baja California Sur:** El archivo emitido en PDF (`presupuesto-baja-california-sur-2026.pdf`) es un documento escaneado (imágenes rasterizadas sin capa OCR seleccionable, 0 caracteres extraíbles con herramientas estándar como `pypdf`). Para su procesamiento por el LLM se requiere una fase previa de OCR, o bien utilizar la versión editable oficial `PresupuestoEgresosBCS-2026.doc`.
- **Resto de las entidades federativas (31 estados):** Cuentan con texto 100% nativo y digital, lo que permite extracción instantánea de fragmentos y citas con número exacto de página.

---

## 2. Ajustes al esquema y aviso al equipo de Backend (Jorge)

Se han añadido las siguientes columnas a la tabla `documentos` en `datos/schema.sql` y en `datos/documentos.csv`:
- `url_fuente TEXT`: Enlace oficial del portal o gaceta de origen.
- `formato TEXT`: Extensión o tipo de recurso (`pdf`, `xlsx`, `csv`, `docx`). Por defecto `'pdf'`.
- `sha256 TEXT`: Huella criptográfica para verificar integridad del documento.
- `fecha_publicacion TEXT`: Fecha de publicación en gaceta/periódico oficial (formato `AAAA-MM-DD`).
- `dependencia TEXT`: Órgano o secretaría responsable de la emisión.

> [!NOTE]
> **Impacto para Jorge:**
> Al actualizar `backend/cargar.py` y `backend/app/main.py`, se sugiere incluir estos campos al registrar nuevos documentos para que la API (`/api/documentos/{id}`) pueda exponer la procedencia oficial directamente a la interfaz ciudadana de Alisson.

### Nuevas tablas para Avisos por WhatsApp (acordado con Jorge): `suscripciones` y `notificaciones`
- **`suscripciones`**: Almacena el número telefónico (`telefono`, formato `52` + 10 dígitos), lugar de interés (`estado_id`, `municipio_id` donde `municipio_id` NULL representa alertas solo estatales), estado de verificación (`verificada`, `activa`), código temporal (`codigo`, `codigo_expira`), token único de baja (`token_baja`) y fecha de alta (`creada_en`). Se protege con el índice único `idx_suscripciones_lugar ON suscripciones (telefono, estado_id, IFNULL(municipio_id, 0))`.
- **`notificaciones`**: Registro histórico gestionado por el backend para evitar reenvíos. Campos: `suscripcion_id`, `documento_id`, `estatus` ('enviado' | 'prueba' | 'error'), `detalle` y `enviada_en`. Incorpora `UNIQUE (suscripcion_id, documento_id)` para asegurar físicamente a nivel de base de datos que **nunca se envíe el mismo documento dos veces al mismo suscriptor**.

---

## 3. Propuesta formal técnica (a discutir con Jorge y Alisson)

### A. Tabla `partidas_presupuesto` para datos analíticos tabulares
Los portales de datos abiertos (como el de Guanajuato con `peeg_a_2025.xlsx`) publican su desglose más granular en hojas de cálculo con más de 40 columnas presupuestales que no se prestan a ser procesadas eficientemente como párrafos de texto en `paginas`.

**Propuesta de esquema:**
```sql
CREATE TABLE partidas_presupuesto (
    id            INTEGER PRIMARY KEY,
    documento_id  INTEGER NOT NULL REFERENCES documentos(id),
    municipio_id  INTEGER REFERENCES municipios(id),
    capitulo      TEXT NOT NULL,          -- ej: '1000 Servicios Personales', '6000 Inversión Pública'
    concepto      TEXT,                   -- ej: '6100 Obra pública en bienes de dominio público'
    partida       TEXT,                   -- ej: '6121 Edificación no habitacional'
    descripcion   TEXT NOT NULL,
    aprobado      REAL NOT NULL DEFAULT 0.0,
    modificado    REAL NOT NULL DEFAULT 0.0,
    devengado     REAL NOT NULL DEFAULT 0.0,
    ejercido      REAL NOT NULL DEFAULT 0.0,
    anio          INTEGER NOT NULL
);

CREATE INDEX idx_partidas_doc ON partidas_presupuesto (documento_id);
CREATE INDEX idx_partidas_capitulo ON partidas_presupuesto (capitulo);
```

### B. Georreferenciación de Obras Públicas
Los decretos de presupuesto en PDF rara vez incluyen coordenadas geográficas exactas (`latitud` y `longitud`). Se proponen dos vías para alimentar la tabla `obras`:
1. **Catálogo del PGO (Programa General de Obra):** Los programas de obra municipales de ayuntamientos (ej. Irapuato, León) desglosan las obras con colonia, calle o cruce de vialidades.
2. **Geocodificación automatizada:** Implementar una tarea de backend con **Nominatim (OpenStreetMap)** o la API de geocodificación de Google Maps para resolver la dirección y colonia dentro del municipio y asignar `latitud`/`longitud` con alta precisión, registrando el nivel de confianza de la geolocalización.

### C. Citas verificables con campo `ubicacion`
Actualmente el esquema utiliza `pagina INTEGER` en `paginas` y citas. Para documentos extensos, decretos tabulares u hojas de cálculo, una sola página puede contener cientos de cifras.
- **Propuesta:** Introducir o enriquecer con `ubicacion TEXT` tanto en `paginas` como en `citas_json` de `respuestas`:
  - En PDFs: `"pág. 190, tabla 4.2: Asignación a Obra Hidráulica"`
  - En Excel: `"Hoja 'Datos', fila 450: Partida 6120"`
  - En Gacetas: `"Gaceta Municipal No. 12, Acta Sesión 45, pág. 12"`

---

## 4. Verificación y pruebas

- **Inicialización de base:** `python datos/init_db.py` probado con éxito, reconstruye `cabildo.db` con catálogo INEGI íntegro (32 estados, 2,475 municipios).
- **Suite de pruebas:** En `backend/`, `pytest` pasa al 100% (37/37 pruebas aprobadas).
- **Control de versiones:** Rama lista en `datos/catalogo-guanajuato-documentos` sin PDFs versionados en Git.

## Sesión de Jorge (30 sep 2026, madrugada; Marko dormido)

- **Catálogo INEGI corregido** con el catálogo oficial que baja `backend/recolector/catalogo.py` (API de claves
  geoestadísticas del INEGI): 2,478 municipios. Se arreglaron las claves recorridas (14 de Guanajuato, 4 de
  Guerrero, Chiapas), nombres oficiales y acentos, y se agregaron los 5 que faltaban (el segundo San Juan y San
  Pedro Mixtepec de Oaxaca, Villa de Pozos, Eldorado y Juan José Ríos). Se conservaron todos los ID.
  `datos/lugares.sql` se regeneró desde la base corregida.
- **Documentos del recolector** (`documentos/`, 6.8 GB, fuera de Git; índice en `documentos/indice.csv` con liga
  directa y sha256 de cada archivo) cargados con `backend/cargar.py`, sin IA:
  - 1,691 documentos con texto (84 mil páginas), de los 32 estados y 379 municipios.
  - 989 escaneados sin texto: fuera de la base, listados en `documentos/pendientes_ocr.txt`.
  - Fuera también: 4 Excel, 15 archivos que no eran PDF (el sitio devolvió una página web) y 1 PDF dañado
    (Plan de Desarrollo de Teoloyucan).
  - 20 PDF marcados para revisar a mano porque parecen impresos desde un navegador.
  - Se quitaron 5 duplicados exactos; el informe de Guanajuato quedó una sola vez, con su liga oficial.
- **La base no está en Git** (`cabildo.db`, ~300 MB): se publica en los Releases de GitHub sin datos personales
  (`base-2026-09-30`, 99 MB comprimida) y cada quien la baja con `python datos/descargar_base.py`.
- Pendiente: OCR de los escaneados, leer Excel, y los resúmenes con IA de todos (~$6–12 USD).
