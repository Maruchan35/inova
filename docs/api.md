# Contrato entre bloques

**Ningún bloque lo cambia por su cuenta**: los cambios se acuerdan entre todos y se hacen por PR.
El backend corre en `http://127.0.0.1:8000`; el frontend llama a `/api/...` y Vite lo redirige.
Documentación interactiva del backend: http://127.0.0.1:8000/docs

## Rutas del backend

### `GET /api/salud`
Devuelve `{ "estado": "ok" }`.

### `GET /api/actas`
Lista de actas, de la más reciente a la más antigua.
```json
[{ "id": 1, "titulo": "Acta de la Sesión Ordinaria de Cabildo No. 12", "fecha": "2026-03-14",
   "municipio": "Municipio de Ejemplo", "paginas": 3 }]
```

### `GET /api/actas/{acta_id}/paginas/{numero}`
Texto completo de una página. `404` si no existe.
```json
{ "acta_id": 1, "acta_titulo": "Acta ...", "pagina": 2, "texto": "Punto cuarto. Se aprueba ..." }
```

### `GET /api/buscar?q=texto`
Búsqueda de texto en todas las páginas (sin importar acentos ni mayúsculas), ordenada por relevancia.
Las palabras encontradas vienen marcadas con `[[` y `]]` dentro de `fragmento`.
```json
{ "consulta": "pavimentacion hidalgo",
  "resultados": [{ "acta_id": 1, "acta_titulo": "Acta ...", "pagina": 2,
                   "fragmento": "…contratación de Constructora Horizonte para la [[pavimentación]] de la calle [[Hidalgo]]…" }] }
```

### `POST /api/preguntar`
Recibe `{ "pregunta": "¿Cuánto costó el mercado?" }`. Devuelve una respuesta y las citas que la
respaldan (mismo formato que los resultados de `/api/buscar`, máximo 5).
```json
{ "pregunta": "...", "respuesta": "Encontré 2 fragmento(s) relevante(s) en las actas.", "citas": [ ... ] }
```
Hoy `respuesta` es un texto fijo; el bloque backend la generará con IA a partir de las citas. El
formato de salida no cambia.

### `GET /api/proveedores/concentracion`
Monto adjudicado por proveedor, de mayor a menor. `porcentaje` es sobre el total de contratos.
```json
[{ "id": 1, "nombre": "Constructora Horizonte S.A. de C.V.", "contratos": 3,
   "monto_total": 5130000.0, "porcentaje": 83.3 }]
```

## Modelo de datos (`datos/schema.sql`)

| Tabla | Campos | Notas |
|---|---|---|
| `actas` | `id`, `titulo`, `fecha`, `municipio`, `archivo` | Una fila por PDF de acta |
| `paginas` | `id`, `acta_id`, `numero`, `texto` | Una fila por página: es la unidad de cita |
| `paginas_fts` | índice de búsqueda sobre `paginas.texto` | Se actualiza solo con triggers |
| `proveedores` | `id`, `nombre`, `rfc` | |
| `contratos` | `id`, `acta_id`, `pagina`, `proveedor_id`, `concepto`, `monto`, `fecha` | `pagina` = dónde se aprobó |
