# Notas — frontend (Alisson)

## Estado (contrato v2)

- React + Vite en `frontend/`. Versión **funcional mínima**, sin diseño, con 3 pantallas:
  1. **Inicio:** buscador de estado o municipio.
  2. **Lugar** (estado o municipio): buscador/preguntas filtrado por ese lugar, las 5 secciones con
     sus documentos, municipios (si es estado) y concentración de proveedores.
  3. **Documento:** resumen, "lo más importante" con enlace a cada página, buscador dentro del documento.
- Todas las llamadas al backend están en `frontend/src/api.js`. No pongas datos fijos en los componentes.

## Tareas (en orden)

1. **Diseño e identidad visual** (colores, tipografía, logo) y separar `App.jsx` en componentes
   dentro de `src/components/`.
2. **Navegación con URLs** (`/municipio/1`, `/documento/2`) para poder compartir enlaces; por
   ejemplo con `react-router` (avisar al equipo antes de agregarlo).
3. **Página de lugar:** secciones como tarjetas o pestañas, con contador de documentos.
4. **Página de documento:** resumen destacado, puntos clave como tarjetas y visor de página.
5. **Estados de carga, error y "procesando"** en todas las pantallas; que se vea bien en celular.
6. **Formulario para subir documentos** cuando Jorge tenga `POST /api/documentos`.
7. Gráfica de concentración más visual, con aviso cuando un proveedor supera cierto porcentaje.

## En progreso

- Rama: `frontend/diseno`
- Tarea: Mover el diseño a React e integrarlo con `api.js`.

## Decisiones y problemas

- El diseño de la portada, ranking, lugares y documentos se movió a componentes React en `frontend/src/components/`.
- Se removió completamente el mapa estático ya que no había datos de obras geolocalizados, alineándose con la guía de evitar dependencias extra si no era funcional.
- El Chatbot fue integrado exitosamente usando `api.preguntar()`.
- Falta: Formulario para subir documentos y la gráfica de concentración visual con porcentaje de riesgo.
