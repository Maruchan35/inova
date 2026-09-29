# Requisitos — CabildoAbierto AI

## Reto

Hackatón TecNM · Ciberdemocracia y Tecnologías para la Gestión Pública · **Propuesta 3: CabildoAbierto AI
(Auditoría RAG)**.

## Problema que resolvemos

Los gobiernos publican informes, presupuestos, actas y contratos en PDFs de cientos de páginas. La
información es pública, pero en la práctica nadie la lee: el ciudadano promedio no va a revisar un
documento de 500 páginas para saber en qué se gasta el dinero de su municipio.

## Cómo lo resolvemos

1. Los gobiernos suben sus documentos, organizados por **estado → municipio → sección**.
2. La plataforma los procesa **una sola vez**: extrae el texto, lo indexa, genera un resumen y
   "lo más importante", y detecta montos y proveedores.
3. El ciudadano busca su municipio (por ejemplo Irapuato), ve las secciones y los documentos, lee el
   resumen y puede buscar o preguntar. Cada dato muestra la página exacta de donde sale.

## Alcance MVP (24-36 h)

| ID | Requisito | Prioridad | Bloque |
|---|---|---|---|
| RF-01 | Navegar por estado → municipio → sección → documento | debe | frontend + backend |
| RF-02 | Procesar PDFs: texto por página, índice de búsqueda y estatus del proceso | debe | backend |
| RF-03 | Resumen y "lo más importante" de cada documento, cada punto con su página | debe | backend |
| RF-04 | Buscador y preguntas filtrados por lugar, sección o documento, con cita de página | debe | backend + frontend |
| RF-05 | Cargar 5-10 documentos reales de Guanajuato / Irapuato en las 5 secciones | debe | datos |
| RF-06 | Concentración de compras por proveedor en cada lugar | debe | todos |
| RF-07 | Respuesta en menos de 2 segundos (el procesamiento pesado se hace al subir) | debe | backend |
| RF-08 | Subir PDFs desde la página (formulario para gobiernos) | debería | backend + frontend |
| RF-09 | Respuesta redactada con IA a partir de las citas | debería | backend |
| RF-10 | OCR para PDFs escaneados | opcional | backend |

## Secciones

Informes de gobierno · Presupuesto y finanzas · Obras públicas · Actas de cabildo · Contratos y licitaciones.

## Requisitos no funcionales

- Nunca inventar información: todo resumen, punto clave y respuesta va respaldado por su página.
- Si la IA no está disponible, la plataforma sigue funcionando con un resumen de respaldo sin IA.
- Interfaz en español, clara para ciudadanos y jueces no técnicos; que funcione en celular.

## Diferenciador para la demo

Un documento de cientos de páginas convertido en un resumen de 30 segundos, y una pregunta en
lenguaje natural que devuelve el dato exacto con su página.

## Fuera de alcance

- Cuentas de usuario e inicio de sesión (para gobiernos o ciudadanos).
- Validar que quien sube un documento es realmente un gobierno.

## Criterios de evaluación de los jueces

- _Anotar aquí la rúbrica si la dan._
