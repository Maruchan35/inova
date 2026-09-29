# Reglas para agentes de IA (Claude Code, Antigravity/Gemini y cualquier otro)

Este archivo es la fuente única de reglas. `CLAUDE.md`, `GEMINI.md` y `.agent/rules/` apuntan aquí.
Si una instrucción del usuario contradice una regla marcada como **OBLIGATORIA**, detente y avisa
antes de actuar.

## Contexto

- Equipo de 5 personas en un hackathon de 36 horas (Hackatech). 3 programan, 1 hace requisitos y
  documentación, 1 expone ante los jueces.
- Cada persona trabaja en un **bloque**: `frontend/`, `backend/`, `datos/` o `docs/`.
- Varias IAs distintas trabajan en paralelo en este repo. Tu trabajo tiene que integrarse con el de
  otras personas sin romperlo.

## Proyecto

- **Reto:** Hackatón TecNM, Ciberdemocracia — Propuesta 3: **CabildoAbierto AI** (ver
  `docs/requisitos.md`).
- **Qué construimos:** una plataforma donde los gobiernos suben sus documentos (informes,
  presupuestos, obras, actas, contratos: PDFs de cientos de páginas) y la plataforma los **procesa
  una sola vez** para que el ciudadano los entienda: elige su estado o municipio, ve los documentos
  por sección, lee un resumen con "lo más importante" y puede buscar o preguntar. **Todo dato lleva
  la página de donde sale.** Toda la información que muestra la página sale de la base de datos a
  través del backend; nada de datos fijos en el frontend.
- **Stack:** datos: SQLite + FTS5 (`datos/`) · backend: Python 3.13 + FastAPI (`backend/`) ·
  frontend: React 19 + Vite (`frontend/`).
- **Responsables:** datos: Marko · backend: Jorge · frontend: Alisson.
- **Cómo se ejecuta** (tres terminales, desde la raíz del repo):
  1. `python datos/init_db.py` (crea `datos/cabildo.db`; repetir cuando cambie el esquema o los datos)
  2. `cd backend` → `python -m venv .venv` → `.venv\Scripts\activate` (Windows) o
     `source .venv/bin/activate` (Mac/Linux) → `pip install -r requirements.txt` →
     `uvicorn app.main:app --reload --port 8000`
  3. `cd frontend` → `npm install` → `npm run dev` → abrir http://localhost:5173
- **Cómo se verifica que funciona:**
  - datos: `python datos/init_db.py` termina sin errores
  - backend: `cd backend` → `pytest` (todos pasan)
  - frontend: `cd frontend` → `npm run build` sin errores, y la página muestra datos con el backend
    encendido
- **Contrato entre bloques:** ver `docs/api.md`. El frontend solo llama al backend a través de
  `frontend/src/api.js`; el backend solo lee la base de datos a través de `backend/app/db.py`.

## Reglas de Git (OBLIGATORIAS)

1. **Nunca hagas commit ni push directo a `main`.** `main` siempre tiene que funcionar; solo cambia
   mediante Pull Request.
2. **Una rama por tarea**, con el nombre del bloque: `frontend/login`, `backend/api-usuarios`,
   `datos/esquema`, `docs/requisitos`.
3. **Antes de empezar a trabajar:** `git fetch origin` y actualiza tu rama con `main`
   (`git merge origin/main`).
4. **Commits pequeños** con mensajes claros en español: `frontend: agrega formulario de login`.
5. **Antes de cada push:** actualiza con `main`, ejecuta la verificación del proyecto (sección
   "Proyecto") y confirma que pasa. **Nunca subas código que no hayas ejecutado.** Si no hay forma
   de verificar, dilo explícitamente al usuario.
6. **Haz push de tu rama al menos cada hora**, y propón abrir un Pull Request cada 1-2 horas o al
   terminar una tarea, lo que pase primero. Nada de un push gigante al final.
7. **Prohibido:** `git push --force`, `git reset --hard` sobre trabajo ajeno, reescribir el
   historial de `main`, borrar ramas de otros, desactivar los hooks de `.githooks/` o usar
   `--no-verify`.
8. **Nunca subas secretos:** contraseñas, API keys, `.env`, tokens. Usa `.env.example` con valores
   de ejemplo.

## Reglas de trabajo en equipo (OBLIGATORIAS)

1. **Quédate en tu bloque.** Solo modifica la carpeta del bloque de la persona con la que trabajas.
   Si necesitas cambiar otro bloque, detente y pide que lo coordine con su compañero.
2. **No cambies el contrato de `docs/api.md` por tu cuenta.** Si hace falta cambiarlo, propón el
   cambio al usuario: afecta a otros bloques.
3. **No reescribas ni reformatees archivos completos** que no son parte de tu tarea. Cambios
   mínimos y enfocados, para que los conflictos sean pequeños y los errores fáciles de encontrar.
4. **No agregues dependencias grandes ni cambies el stack** sin avisar al usuario.
5. **Si encuentras un conflicto de merge**, resuélvelo conservando el trabajo de ambos lados y
   explica al usuario qué decidiste. Si no está claro, pregunta.
6. **Al terminar una sesión o una tarea**, actualiza la nota de tu bloque en `notas/` (qué hiciste,
   en qué rama, qué falta). La siguiente sesión, humana o IA, arranca leyendo esa nota.

## Al empezar cada sesión

1. Lee este archivo, `docs/api.md` y la nota de tu bloque en `notas/`.
2. Confirma en qué rama estás (`git branch --show-current`). Si estás en `main`, crea una rama
   antes de cambiar nada.
3. Actualiza la rama con `origin/main`.

## Definición de "terminado"

Una tarea está terminada solo cuando: el código se ejecutó y funciona, pasa la verificación del
proyecto, está actualizada con `main`, está subida a su rama, y la nota del bloque está al día.
