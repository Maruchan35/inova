# Guía del equipo — Hackatech

## Roles

| Rol | Bloque | Responsable |
|---|---|---|
| Frontend | `frontend/` | Alisson |
| Backend | `backend/` | Jorge |
| Datos | `datos/` | Marko |
| Requisitos y documentación | `docs/` | _nombre_ |
| Exposición | demo y presentación | _nombre_ |

## Antes del hackathon (una sola vez, cada integrante)

1. Acepta la invitación de colaborador al repo (te llega por correo de GitHub).
2. Clona el repo y activa los hooks del equipo:
   ```bash
   git clone https://github.com/Maruchan35/inova.git
   cd inova
   git config core.hooksPath .githooks
   ```
   Los hooks bloquean commits y push directos a `main`, también si los intenta una IA.
3. Si es la primera vez que usas Git en esa computadora:
   ```bash
   git config --global user.name "Tu Nombre"
   git config --global user.email "tu-correo-de-github@ejemplo.com"
   ```
4. Abre el repo en tu herramienta (Claude Code o Antigravity) y pídele: *"Lee AGENTS.md y dime
   qué reglas vas a seguir"*. Si no las menciona, avisa al equipo.

## Hora 0 — cuando anuncien el reto (primera hora, todos juntos)

1. **Requisitos:** escribe el reto y los requisitos en `docs/requisitos.md` y crea un *Issue* en
   GitHub por cada tarea pequeña, asignado a alguien.
2. **Todos:** decidan el stack y llenen la sección "Proyecto" de `AGENTS.md` (stack, cómo se
   ejecuta, cómo se verifica). Puedes pedírselo a la IA con el prompt de abajo.
3. **Los 3 que programan:** acuerden `docs/api.md`, qué rutas hay y qué datos entran y salen.
   Es el contrato: con él, el frontend avanza con datos falsos mientras el backend no está listo.
4. **Una sola persona** crea la base del proyecto (estructura, dependencias, "hola mundo" que
   corre) en una rama, abre el PR y se une a `main`. **Nadie empieza su bloque antes de eso.**

Prompt para la hora 0 (Claude Code o Antigravity):

> Lee AGENTS.md y docs/requisitos.md. Vamos a construir [idea] con [stack]. Llena la sección
> "Proyecto" de AGENTS.md con el stack, el comando para ejecutar y el comando para verificar, y
> propón un borrador de docs/api.md. No toques nada más. Hazlo en la rama docs/hora-0.

## Ciclo de trabajo (cada tarea)

```bash
git checkout main && git pull            # 1. traer lo último
git checkout -b frontend/login           # 2. rama nueva para la tarea
# ... trabajar, commits pequeños ...
git add . && git commit -m "frontend: agrega formulario de login"
git fetch origin && git merge origin/main   # 3. traer lo de los demás
# 4. EJECUTAR Y PROBAR que funciona
git push -u origin frontend/login        # 5. subir la rama (mínimo cada hora)
```

6. En GitHub: **Compare & pull request**, llena la plantilla y pide a un compañero que lo revise.
7. Cuando lo aprueben: **Merge pull request**. Luego borra la rama y vuelve al paso 1.

**Ritmo:** push de tu rama cada hora como mínimo; PR a `main` cada 1-2 horas o al terminar la
tarea. PRs pequeños = errores fáciles de encontrar.

## Integración cada 3-4 horas (todos)

1. Todos unen sus PRs pendientes.
2. Alguien descarga `main` y prueba el sistema **completo**.
3. Si funciona, se marca una versión estable para la demo:
   ```bash
   git tag v1 && git push origin v1      # luego v2, v3...
   ```
   Quien expone siempre usa la última versión con tag, aunque lo más nuevo esté roto.

## Si algo se rompe

- **Encontrar qué PR lo rompió:** en GitHub, pestaña *Pull requests → Closed*, o `git log --oneline`.
  Como los PRs son pequeños, el culpable suele ser el último que se unió.
- **Deshacer un PR sin perder lo demás:** en el PR unido, botón **Revert** (crea un PR que lo
  deshace). O desde terminal: `git revert <commit>` en una rama y PR.
- **Volver a la versión estable para la demo:** `git checkout v2` (el tag que sirva).
- **Nunca** arreglen con `git push --force`.

## Conflictos de merge

Pasan cuando dos personas cambian las mismas líneas. Al hacer `git merge origin/main`, Git marca
los archivos en conflicto. Pídele a tu IA: *"Resuelve los conflictos conservando el trabajo de
ambos lados y explícame qué decidiste"*. Revisa, prueba, commit y push.

## Cambiar entre sesión local y en la nube (Claude Code)

La sesión en la nube solo ve lo que está en GitHub y no recuerda la conversación local:
1. Antes de cambiar: commit + push de tu rama y actualiza tu nota en `notas/`.
2. En la nube: *"Lee AGENTS.md y notas/<bloque>.md y sigue desde ahí en la rama <rama>"*.
3. Al volver: `git pull` de tu rama.

## Calendario sugerido (36 h)

| Hora | Qué |
|---|---|
| 0-1 | Reto, requisitos, stack, contrato `api.md`, base del proyecto en `main` |
| 1-30 | Ciclos de tareas; integración + tag cada 3-4 h |
| 30 | **Congelar funciones:** solo arreglos y pulido |
| 33 | Tag final `v-final`; ensayo de la demo con esa versión |
| 33-36 | Presentación, documentación final, respaldo |

## Reglas de oro

1. `main` siempre funciona. Nada entra a `main` sin PR.
2. Nunca subas código sin ejecutarlo.
3. Cada quien en su bloque; el contrato (`api.md`) se cambia entre todos.
4. Commits y PRs pequeños y frecuentes.
5. Nunca `--force`, nunca secretos en el repo.
