# Contrato entre bloques (v2)

**Ningún bloque lo cambia por su cuenta**: los cambios se acuerdan entre todos y se hacen por PR.
El backend corre en `http://127.0.0.1:8000`; el frontend llama a `/api/...` y Vite lo redirige.
Documentación interactiva del backend: http://127.0.0.1:8000/docs

## Idea general

Los gobiernos suben documentos (PDF) → el backend los **procesa una sola vez** (texto por página,
índice de búsqueda, resumen, puntos clave, contratos) → el ciudadano elige su estado o municipio,
ve los documentos por **sección** y puede buscar o preguntar. Cada dato lleva su página de origen.

## Rutas del backend

### Navegación

#### `GET /api/secciones`
Lista fija, en el orden en que se muestran.
```json
[{ "clave": "informes", "nombre": "Informes de gobierno" }, { "clave": "presupuesto", "nombre": "Presupuesto y finanzas" }]
```
Claves: `informes`, `presupuesto`, `obras`, `actas`, `contratos`.

#### `GET /api/estados`
Estados con sus municipios (para el buscador de lugar).
```json
[{ "id": 1, "nombre": "Guanajuato", "municipios": [{ "id": 1, "nombre": "Irapuato" }] }]
```

#### `GET /api/municipios/{id}` y `GET /api/estados/{id}`
Página de un lugar: todas las secciones (aunque estén vacías) con sus documentos.
`/estados/{id}` trae solo los documentos **del gobierno estatal** y además la lista `municipios`.
`404` si no existe.
```json
{ "tipo": "municipio", "id": 1, "nombre": "Irapuato", "estado": { "id": 1, "nombre": "Guanajuato" },
  "secciones": [
    { "clave": "presupuesto", "nombre": "Presupuesto y finanzas",
      "documentos": [{ "id": 2, "titulo": "Presupuesto de Egresos 2026", "anio": 2026, "fecha": "2026-01-10",
                       "total_paginas": 3, "estatus": "listo" }] }
  ] }
```

### Documentos

#### `GET /api/documentos/{id}`
Detalle con lo que ve el ciudadano. `resumen` es `null` y `puntos_clave` vacío mientras
`estatus` no sea `"listo"`. `municipio` es `null` en documentos estatales. `404` si no existe.
```json
{ "id": 2, "titulo": "Presupuesto de Egresos 2026", "anio": 2026, "fecha": "2026-01-10",
  "total_paginas": 3, "estatus": "listo", "error": null,
  "resumen": "El municipio planea gastar 3,200 millones de pesos en 2026...",
  "seccion": { "clave": "presupuesto", "nombre": "Presupuesto y finanzas" },
  "estado": { "id": 1, "nombre": "Guanajuato" }, "municipio": { "id": 1, "nombre": "Irapuato" },
  "puntos_clave": [{ "texto": "Presupuesto total 2026: $3,200 millones de pesos.", "pagina": 1 }] }
```
`estatus`: `pendiente` → `procesando` → `listo` | `error` (con mensaje en `error`).

#### `GET /api/documentos/{id}/paginas/{numero}`
Texto completo de una página. `404` si no existe.
```json
{ "documento_id": 2, "documento_titulo": "Presupuesto de Egresos 2026", "pagina": 1, "texto": "..." }
```

#### `POST /api/documentos`
Subir un PDF. `multipart/form-data` con: `archivo` (PDF), `estado_id`, `municipio_id` (opcional:
vacío = documento estatal), `seccion` (clave), `titulo`, `anio` (opcional). Responde `201` con
`{ "id": 6, "estatus": "pendiente" }` y lo procesa en segundo plano; el frontend consulta
`GET /api/documentos/{id}` cada segundo para ver el avance. `400` si el archivo no es PDF, o si el
estado, el municipio (del estado indicado) o la sección no existen.

### Búsqueda y preguntas

#### `GET /api/buscar?q=texto`
Búsqueda en el texto de todas las páginas (sin importar acentos ni mayúsculas), por relevancia.
Filtros opcionales: `estado_id` (todo el estado, incluidos sus municipios), `municipio_id`,
`seccion` (clave), `documento_id`. Las palabras encontradas vienen entre `[[` y `]]`.
```json
{ "consulta": "mercado", "resultados": [
  { "documento_id": 3, "documento_titulo": "Programa de Obra Pública 2026", "seccion": "obras",
    "lugar": "Irapuato", "pagina": 1, "fragmento": "…Rehabilitación del [[mercado]] municipal por $2,300,000.00…" } ] }
```

#### `POST /api/preguntar`
Recibe `{ "pregunta": "...", "estado_id": null, "municipio_id": 1, "seccion": null, "documento_id": null }`
(los filtros son opcionales, igual que en `/buscar`). Devuelve la respuesta y hasta 5 citas con el
mismo formato que los resultados de `/buscar`.
```json
{ "pregunta": "¿Cuánto costó el mercado?", "respuesta": "...", "citas": [ ... ] }
```
Hoy `respuesta` es un texto fijo; el bloque backend la generará con IA a partir de las citas. El
formato no cambia.

### Indicadores

#### `GET /api/proveedores/concentracion`
Monto por proveedor, de mayor a menor. Filtros opcionales `estado_id` y `municipio_id`.
```json
[{ "id": 1, "nombre": "Constructora Horizonte S.A. de C.V.", "contratos": 3, "monto_total": 5130000.0, "porcentaje": 83.3 }]
```

## Modelo de datos (`datos/schema.sql`)

| Tabla | Campos | Notas |
|---|---|---|
| `estados` | `id`, `nombre` | |
| `municipios` | `id`, `estado_id`, `nombre` | |
| `secciones` | `id`, `clave`, `nombre`, `orden` | Lista fija de 5 |
| `documentos` | `id`, `estado_id`, `municipio_id`, `seccion_id`, `titulo`, `anio`, `fecha`, `archivo`, `total_paginas`, `estatus`, `error`, `resumen`, `subido_en` | `municipio_id` NULL = documento estatal |
| `paginas` | `id`, `documento_id`, `numero`, `texto` | Una fila por página: es la unidad de cita |
| `paginas_fts` | índice de búsqueda sobre `paginas.texto` | Se actualiza solo con triggers |
| `puntos_clave` | `id`, `documento_id`, `orden`, `texto`, `pagina` | "Lo más importante", con su página |
| `proveedores` | `id`, `nombre`, `rfc` | |
| `contratos` | `id`, `documento_id`, `pagina`, `proveedor_id`, `concepto`, `monto`, `fecha` | |

**Quién escribe qué:** el bloque datos define las tablas y carga estados, municipios, secciones y
datos de ejemplo. El procesador del backend llena `documentos` (estatus, resumen, total_paginas),
`paginas`, `puntos_clave`, `proveedores` y `contratos` al procesar cada PDF.
