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

- Rama: `frontend/rutas-y-avisos`
- Tarea: Router sin dependencias y Formulario de WhatsApp

## Decisiones y problemas

- Se creó un router custom usando `window.history.pushState` y el evento `popstate` para manejar rutas directas: `/`, `/estado/:id`, `/municipio/:id`, `/documento/:id`.
- Botón de atrás integrado con `window.history.back()`.
- Nuevo componente `Suscripcion.jsx` para el flujo de WhatsApp (ingreso de teléfono -> validación de código).
- Se actualizó `api.js` para propagar los errores `detail` que manda el backend, necesario para mostrar correctamente los fallos en la suscripción (ej. código incorrecto).
- Los acentos fueron corregidos en los archivos JSX localmente tras problemas con fetch.
- Falta: Formulario para subir documentos y la gráfica de concentración visual con porcentaje de riesgo.

- **Chat más grande y ajustable** (rama `frontend/chat-grande-y-boton`, Jorge, 30 sep): la ventana del chatbot abre en 440×600, tiene un botón para ampliarla y se puede ajustar arrastrando su esquina de arriba a la izquierda (el tamaño se recuerda en el navegador). La página del documento tiene el botón "Chat con IA", que abre el chat sobre ese documento.

- **Modo por voz** (rama `frontend/modo-voz`, Jorge, 30 sep): `src/voz.js` (reconocer y leer en voz alta con lo que trae el navegador, es-MX, sin costo) y `components/ModoVoz.jsx` (micrófono flotante y panel "Te escucho"). También hay micrófono en el buscador de la portada y en el chat. Lo dicho va a `POST /api/voz`, que responde si hay que ir a un lugar (con sección), regresar o preguntarle al chatbot; las preguntas hechas por voz se leen en voz alta con su documento y página. Solo funciona en Chrome y Edge, con internet y en https o localhost; en otros navegadores los micrófonos no se muestran.

- **Adaptable a celular y tableta** (rama `frontend/adaptable-a-celular`, Jorge, 30 sep): al final de `App.css` hay un bloque de `@media` (768, 600, 420 y 340 px). En celular: encabezado en dos filas, título y márgenes más chicos, documentos en una columna, visor de páginas a pantalla completa, chat a casi toda la pantalla (sin ajustar tamaño), botones flotantes más chicos y campos de texto de 16 px para que el teléfono no haga zoom. Las reglas nuevas para escritorio deben ir antes de ese bloque.
