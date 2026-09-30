# Recolector de documentos oficiales

Busca en los sitios oficiales de los 32 estados y sus 2,478 municipios los documentos de las 5 secciones
de la plataforma (informes, presupuesto, obras, actas, contratos) y los guarda en `documentos/`,
separados por estado, municipio y sección. Solo consulta información pública; se identifica con su
nombre, respeta `robots.txt` y hace pausas entre páginas del mismo sitio.

Desde `backend/`, con el entorno activado (`.venv\Scripts\activate`), en este orden:

| Paso | Comando | Qué deja en `documentos/_catalogo/` |
|---|---|---|
| 1 | `python recolector/catalogo.py` | `estados.csv`, `municipios.csv` (INEGI, con clave oficial) |
| 2 | `python recolector/estatales.py` | `sitios_estatales.csv`: portal, finanzas, transparencia, informe, congreso... de cada estado |
| 3 | `python recolector/sitios.py` | `sitios_municipales.csv`: sitio oficial de cada municipio (Wikidata + dominios `.gob.mx`, verificados) |
| 4 | `python recolector/rastrear.py` | `enlaces.csv` y `por_seccion/*.csv`: cada documento encontrado con su sección (no descarga) |
| 5 | `python recolector/descargar.py` | Los archivos en `documentos/<Estado>/<Municipio o Gobierno del estado>/<Sección>/` y `documentos/indice.csv` |
| 6 | `python cargar.py --csv ../documentos/indice.csv --pdfs ../documentos` | Procesa los PDFs con la IA y los carga a la base |

- `rastrear.py` y `descargar.py` se pueden interrumpir y volver a correr: retoman donde se quedaron.
- `descargar.py` no repite nada de lo que ya hay en `documentos/` ni de lo que lista `datos/documentos.csv`
  (compara el contenido con sha256). Por defecto baja los 8 más recientes por municipio y sección, los
  25 más recientes por estado y sección, solo PDF, hasta 80 MB por archivo y 30 GB en total (ver `--help`).
- Un documento de un sitio estatal que dice "Municipio de X" (leyes de ingresos del congreso, por ejemplo)
  se guarda en el municipio X.
