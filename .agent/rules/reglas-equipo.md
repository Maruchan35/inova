# Reglas del equipo (Antigravity)

Las reglas completas están en `AGENTS.md`, en la raíz del repo. **Léelo antes de hacer cualquier
cambio.** Resumen de lo obligatorio:

- Nunca hagas commit ni push directo a `main`. Una rama por tarea: `frontend/...`, `backend/...`,
  `datos/...`, `docs/...`.
- Antes de cada push: actualiza con `origin/main`, ejecuta la verificación del proyecto y confirma
  que pasa. Nunca subas código sin ejecutarlo.
- Push de tu rama al menos cada hora; Pull Request cada 1-2 horas o al terminar una tarea.
- Prohibido: `git push --force`, `git reset --hard` sobre trabajo ajeno, `--no-verify`, subir
  secretos o `.env`.
- Quédate en tu bloque. No cambies `docs/api.md` ni otros bloques sin que el usuario lo coordine.
- Al terminar, actualiza la nota de tu bloque en `notas/`.
