// Todas las llamadas al backend pasan por aquí. Rutas y formatos: docs/api.md
async function pedir(ruta, opciones) {
  const res = await fetch(`/api${ruta}`, opciones)
  if (!res.ok) {
    let detail = `Error ${res.status} en ${ruta}`
    try {
      const errorJson = await res.json()
      if (errorJson.detail) {
        detail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail)
      }
    } catch (e) {}
    throw new Error(detail)
  }
  return res.json()
}

// Convierte { municipio_id: 1, seccion: undefined } en "?municipio_id=1"
function query(params = {}) {
  const limpio = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  return limpio.length ? `?${new URLSearchParams(limpio)}` : ''
}

export const api = {
  estados: () => pedir('/estados'),
  estado: (id) => pedir(`/estados/${id}`),
  municipio: (id) => pedir(`/municipios/${id}`),
  documento: (id) => pedir(`/documentos/${id}`),
  pagina: (documentoId, numero) => pedir(`/documentos/${documentoId}/paginas/${numero}`),
  buscar: (q, filtros) => pedir(`/buscar${query({ q, ...filtros })}`),
  preguntar: (pregunta, filtros) =>
    pedir('/preguntar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pregunta, ...filtros }),
    }),
  concentracion: (filtros) => pedir(`/proveedores/concentracion${query(filtros)}`),
  suscribir: (telefono, estado_id, municipio_id) =>
    pedir('/suscripciones', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ telefono, estado_id, municipio_id: municipio_id || null }),
    }),
  verificarSuscripcion: (telefono, codigo) =>
    pedir('/suscripciones/verificar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ telefono, codigo }),
    })
}
