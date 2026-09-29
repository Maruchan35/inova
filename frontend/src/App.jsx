import { useEffect, useState } from 'react'
import { api } from './api.js'

// Versión funcional mínima: el diseño y la división en componentes son del bloque frontend.

const pesos = (n) => n.toLocaleString('es-MX', { style: 'currency', currency: 'MXN' })

// El backend marca las coincidencias con [[ ]]; se resaltan sin usar HTML crudo.
function Fragmento({ texto }) {
  return texto.split(/(\[\[.*?\]\])/).map((parte, i) =>
    parte.startsWith('[[') ? <mark key={i}>{parte.slice(2, -2)}</mark> : parte,
  )
}

function BuscarLugar({ onElegir }) {
  const [estados, setEstados] = useState([])
  const [texto, setTexto] = useState('')
  useEffect(() => { api.estados().then(setEstados).catch(() => setEstados([])) }, [])

  const coincide = (nombre) => nombre.toLowerCase().includes(texto.trim().toLowerCase())
  return (
    <section>
      <h2>¿Qué estado o municipio quieres consultar?</h2>
      <input className="ancho" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Ej. Irapuato" />
      <ul>
        {estados.map((e) => (
          <li key={e.id}>
            {coincide(e.nombre) && (
              <button className="enlace" onClick={() => onElegir({ tipo: 'estado', id: e.id })}>{e.nombre} (estado)</button>
            )}
            <ul>
              {e.municipios.filter((m) => coincide(m.nombre) || coincide(e.nombre)).map((m) => (
                <li key={m.id}>
                  <button className="enlace" onClick={() => onElegir({ tipo: 'municipio', id: m.id })}>{m.nombre}</button>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Preguntas({ filtros, onVerPagina }) {
  const [pregunta, setPregunta] = useState('')
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState(null)

  async function enviar(e) {
    e.preventDefault()
    if (!pregunta.trim()) return
    setError(null)
    try {
      setResultado(await api.preguntar(pregunta, filtros))
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section>
      <h2>Busca o pregunta</h2>
      <form onSubmit={enviar} className="buscador">
        <input value={pregunta} onChange={(e) => setPregunta(e.target.value)} placeholder="Ej. ¿Cuánto costó el mercado municipal?" />
        <button>Buscar</button>
      </form>
      {error && <p className="error">{error}</p>}
      {resultado && (
        <div>
          <p>{resultado.respuesta}</p>
          {resultado.citas.map((c) => (
            <article key={`${c.documento_id}-${c.pagina}`} className="cita">
              <button className="enlace" onClick={() => onVerPagina(c.documento_id, c.pagina)}>
                {c.documento_titulo} · página {c.pagina}
              </button>
              <p><Fragmento texto={c.fragmento} /></p>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

function Concentracion({ filtros }) {
  const [filas, setFilas] = useState([])
  useEffect(() => { api.concentracion(filtros).then(setFilas).catch(() => setFilas([])) }, [filtros.estado_id, filtros.municipio_id])
  if (!filas.length) return null

  return (
    <section>
      <h2>Concentración de compras por proveedor</h2>
      {filas.map((f) => (
        <div key={f.id} className="barra-fila">
          <span>{f.nombre} · {f.contratos} contrato(s) · {pesos(f.monto_total)}</span>
          <div className="barra"><div style={{ width: `${f.porcentaje}%` }}>{f.porcentaje}%</div></div>
        </div>
      ))}
    </section>
  )
}

function Lugar({ lugar, onElegir, onDocumento, onVerPagina }) {
  const [datos, setDatos] = useState(null)
  useEffect(() => {
    const pedir = lugar.tipo === 'estado' ? api.estado : api.municipio
    pedir(lugar.id).then(setDatos).catch(() => setDatos(null))
  }, [lugar.tipo, lugar.id])
  if (!datos) return <p>Cargando…</p>

  const filtros = lugar.tipo === 'estado' ? { estado_id: datos.id } : { municipio_id: datos.id }
  return (
    <>
      <h2>{datos.nombre}{datos.estado && `, ${datos.estado.nombre}`}</h2>
      <Preguntas filtros={filtros} onVerPagina={onVerPagina} />
      {datos.secciones.map((s) => (
        <section key={s.clave}>
          <h3>{s.nombre}</h3>
          {s.documentos.length === 0 && <p className="tenue">Sin documentos todavía.</p>}
          <ul>
            {s.documentos.map((d) => (
              <li key={d.id}>
                <button className="enlace" onClick={() => onDocumento(d.id)}>{d.titulo}</button>
                {' '}· {d.anio} {d.estatus !== 'listo' && <em>({d.estatus})</em>}
              </li>
            ))}
          </ul>
        </section>
      ))}
      {datos.municipios && (
        <section>
          <h3>Municipios</h3>
          {datos.municipios.map((m) => (
            <button key={m.id} className="enlace separado" onClick={() => onElegir({ tipo: 'municipio', id: m.id })}>{m.nombre}</button>
          ))}
        </section>
      )}
      <Concentracion filtros={filtros} />
    </>
  )
}

function Documento({ id, onVerPagina }) {
  const [doc, setDoc] = useState(null)
  useEffect(() => { api.documento(id).then(setDoc).catch(() => setDoc(null)) }, [id])
  if (!doc) return <p>Cargando…</p>

  return (
    <>
      <section>
        <p className="tenue">{doc.seccion.nombre} · {doc.municipio?.nombre ?? doc.estado.nombre} · {doc.anio}</p>
        <h2>{doc.titulo}</h2>
        {doc.estatus !== 'listo' ? (
          <p><em>Este documento se está procesando ({doc.estatus}).</em></p>
        ) : (
          <>
            <p>{doc.resumen}</p>
            <h3>Lo más importante</h3>
            <ul>
              {doc.puntos_clave.map((p, i) => (
                <li key={i}>
                  {p.texto}{' '}
                  {p.pagina && <button className="enlace" onClick={() => onVerPagina(doc.id, p.pagina)}>(pág. {p.pagina})</button>}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
      {doc.estatus === 'listo' && <Preguntas filtros={{ documento_id: doc.id }} onVerPagina={onVerPagina} />}
    </>
  )
}

export default function App() {
  const [lugar, setLugar] = useState(null)
  const [documentoId, setDocumentoId] = useState(null)
  const [pagina, setPagina] = useState(null)
  const verPagina = (docId, numero) => api.pagina(docId, numero).then(setPagina)

  return (
    <main>
      <header>
        <h1>CabildoAbierto AI</h1>
        <p>Los documentos de tu gobierno, explicados y con la página exacta de donde sale cada dato.</p>
        {(lugar || documentoId) && (
          <button onClick={() => (documentoId ? setDocumentoId(null) : setLugar(null))}>← Regresar</button>
        )}
      </header>
      {pagina && (
        <section className="pagina">
          <h2>{pagina.documento_titulo} · página {pagina.pagina}</h2>
          <p>{pagina.texto}</p>
          <button onClick={() => setPagina(null)}>Cerrar</button>
        </section>
      )}
      {documentoId ? (
        <Documento id={documentoId} onVerPagina={verPagina} />
      ) : lugar ? (
        <Lugar lugar={lugar} onElegir={setLugar} onDocumento={setDocumentoId} onVerPagina={verPagina} />
      ) : (
        <BuscarLugar onElegir={setLugar} />
      )}
    </main>
  )
}
