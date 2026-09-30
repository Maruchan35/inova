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

## 1. Catálogo de documentos oficiales y procedencia

Los documentos oficiales en formato PDF y XLSX se gestionan fuera del repositorio Git para evitar sobrecargar el historial. Los miembros del equipo pueden descargarlos desde la carpeta compartida o directamente desde los portales de transparencia estatales:

- **Carpeta compartida (Drive/Nube):** `https://drive.google.com/drive/folders/cabildoabierto-documentos-oficiales` *(enlace para sincronización interna del equipo)*
- **Inventario en `datos/documentos.csv`:**

| Archivo | Estado | Título | Formato | SHA-256 | Fecha Pub. | Dependencia | Portal Oficial (`url_fuente`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `peeg_a_2025.xlsx` | Guanajuato | Presupuesto General de Egresos 2025 (Analítico) | `xlsx` | `32b012e2dd5e1415f8f552a053b203c5e944b7a300a3cb5c758f561d426a3d4f` | 2024-12-27 | SFIA GTO | [Presupuesto Abierto GTO](https://presupuestoabierto.guanajuato.gob.mx/datos-abiertos) |
| `cuenta_publica-a-2025.xlsx` | Guanajuato | Cuenta Pública del Estado de Guanajuato 2025 | `xlsx` | `1371b5c8c349a00b43f3f787106097fc8105ff01a55d547f906bbe4ad81e133c` | 2025-01-30 | SFIA GTO | [Presupuesto Abierto GTO](https://presupuestoabierto.guanajuato.gob.mx/datos-abiertos) |
| `presupuesto-baja-california-2026.pdf` | Baja California | Presupuesto de Egresos de Baja California 2026 | `pdf` | `2af75436175f022adf613fe7dea7cd0b34c9289ca9b85ccfa6c3b396f2a6d687` | 2025-12-23 | Sec. Hacienda BC | [Periódico Oficial BC](https://periodicooficial.bajacalifornia.gob.mx) |
| `presupuesto-chiapas-2026.pdf` | Chiapas | Presupuesto de Egresos de Chiapas 2026 (Dec. 038) | `pdf` | `87cfa63dfdcf99d1d1b51c28dbd823d3cfc99b0cee2f4d0d0f62062d6b28e3bf` | 2025-12-10 | Sec. Hacienda Chiapas | [Hacienda Chiapas](https://www.haciendachiapas.gob.mx) |
| `presupuesto-aguascalientes-2026.pdf` | Aguascalientes | Presupuesto de Egresos de Aguascalientes 2026 | `pdf` | `95e9231370552d13fcdb5b774206f54dfe769be519d2a4b9a8eb5cbb0723b5d1` | 2025-12-31 | SEFI Aguascalientes | [Periódico Oficial AGS](https://eservicios2.aguascalientes.gob.mx/periodicooficial/) |
| `presupuesto-campeche-2026.pdf` | Campeche | Ley del Presupuesto de Egresos de Campeche 2026 | `pdf` | `05cf5a44a31bca4b9f73e58e937b659a824c9119d1916dd77672e781925b3657` | 2025-12-23 | SEFIN Campeche | [Finanzas Campeche](https://finanzas.campeche.gob.mx) |
| `presupuesto-baja-california-sur-2026.pdf` | Baja California Sur | Presupuesto de Egresos BCS 2026 *(Scan / Requiere OCR)* | `pdf` | `d99e96b1316c7de4aba95efd895598e796eeb22df363cafa4944a338ad84708d` | 2025-12-31 | SecFin BCS | [SecFin BCS](https://secfin.bcs.gob.mx) |

### Nota técnica sobre documentos escaneados vs texto nativo:
- **Baja California Sur:** El archivo oficial emitido en PDF (`presupuesto-baja-california-sur-2026.pdf`) es un documento escaneado (imágenes rasterizadas sin capa OCR seleccionable, 0 caracteres extraíbles con herramientas estándar como `pypdf`). Para su procesamiento por el LLM se requiere una fase previa de OCR (Tesseract / EasyOCR), o bien utilizar la versión editable emitida oficialmente `PresupuestoEgresosBCS-2026.doc` que contiene el texto legislativo íntegro de 24 páginas.
- **Baja California, Chiapas, Aguascalientes y Campeche:** Cuentan con texto 100% nativo y digital, lo que permite extracción instantánea de fragmentos y citas con número exacto de página.

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
