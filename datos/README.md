# datos — Marko

Base de datos SQLite (esquema v2: estados, municipios, secciones, documentos). `python datos/init_db.py` la crea desde `schema.sql` + `seed.sql`.
El archivo `cabildo.db` no se sube a Git: cada quien lo genera. Tareas en `notas/datos.md`.

## Base completa (documentos oficiales ya cargados)

`python datos/descargar_base.py` baja la versión más reciente publicada en los Releases de GitHub
(`base-AAAA-MM-DD`, ~100 MB comprimida) y la deja en `datos/cabildo.db` (la anterior queda como
`cabildo.db.respaldo`). No trae datos personales (suscripciones ni respuestas guardadas).
`python datos/init_db.py` la borra y deja solo la base de ejemplo; los tests no la usan.

Para publicar una versión nueva: copiar la base, borrar `suscripciones`, `notificaciones` y `respuestas`,
`VACUUM`, comprimirla como `cabildo.db` dentro de un .zip y subirla con
`gh release create base-AAAA-MM-DD archivo.zip`.
