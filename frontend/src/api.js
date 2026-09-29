// Todas las llamadas al backend pasan por aquí. Rutas y formatos: docs/api.md
async function pedir(ruta, opciones) {
  const res = await fetch(`/api${ruta}`, opciones)
  if (!res.ok) throw new Error(`Error ${res.status} en ${ruta}`)
  return res.json()
}

export const api = {
  actas: () => pedir('/actas'),
  pagina: (actaId, numero) => pedir(`/actas/${actaId}/paginas/${numero}`),
  preguntar: (pregunta) =>
    pedir('/preguntar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pregunta }),
    }),
  concentracion: () => pedir('/proveedores/concentracion'),
}
