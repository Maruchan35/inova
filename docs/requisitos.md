# Requisitos — CabildoAbierto AI

## Reto

Hackatón TecNM · Ciberdemocracia y Tecnologías para la Gestión Pública · **Propuesta 3: CabildoAbierto AI
(Auditoría RAG)**.

## Problema que resolvemos

Las actas de cabildo, licitaciones y contratos de obra se publican en PDFs no indexables, lo que hace
imposible que la ciudadanía fiscalice cómo se gasta el dinero público.

## Alcance MVP (24-36 h)

| ID | Requisito | Prioridad | Bloque |
|---|---|---|---|
| RF-01 | Ingesta de 5 actas reales de cabildo (PDF → texto por página en la base de datos) | debe | datos |
| RF-02 | Preguntas en lenguaje natural con respuesta y **cita textual con acta y página** | debe | backend + frontend |
| RF-03 | Indicador de concentración de compras a contratistas | debe | todos |
| RF-04 | Ver la página completa del acta citada | debe | frontend |
| RF-05 | Respuesta en menos de 2 segundos | debe | backend |
| RF-06 | Respuesta redactada con IA a partir de las citas | debería | backend |
| RF-07 | Visualizador de grafo de proveedores | debería | frontend + backend |
| RF-08 | OCR para PDFs escaneados | opcional | datos |

## Requisitos no funcionales

- La página muestra **solo** datos que vienen de la base de datos (vía backend).
- Nunca inventar información: toda respuesta va respaldada por citas.
- Interfaz en español, clara para jueces no técnicos.

## Diferenciador para la demo

Preguntar en lenguaje natural sobre montos ejercidos y obtener la foja presupuestal exacta (acta y
página) en menos de 2 segundos.

## Fuera de alcance

- Cuentas de usuario e inicio de sesión.
- Subir PDFs desde la página (la ingesta se hace con un script).

## Criterios de evaluación de los jueces

- _Anotar aquí la rúbrica si la dan._
