import { useEffect, useState } from 'react'
import { api } from './api.js'

const pesos = (n) => n.toLocaleString('es-MX', { style: 'currency', currency: 'MXN' })

// El backend marca las coincidencias con [[ ]]; se resaltan sin usar HTML crudo.
function Fragmento({ texto }) {
  return texto.split(/(\[\[.*?\]\])/).map((parte, i) =>
    parte.startsWith('[[') ? <mark key={i}>{parte.slice(2, -2)}</mark> : parte,
  )
}

function Preguntas({ onVerPagina }) {
  const [pregunta, setPregunta] = useState('')
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState(null)

  async function enviar(e) {
    e.preventDefault()
    if (!pregunta.trim()) return
    setError(null)
    try {
      setResultado(await api.preguntar(pregunta))
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section>
      <h2>Pregunta a las actas</h2>
      <form onSubmit={enviar} className="buscador">
        <input
          value={pregunta}
          onChange={(e) => setPregunta(e.target.value)}
          placeholder="Ej. ¿Cuánto se pagó por la pavimentación de la calle Hidalgo?"
        />
        <button>Preguntar</button>
      </form>
      {error && <p className="error">{error}</p>}
      {resultado && (
        <div>
          <p>{resultado.respuesta}</p>
          {resultado.citas.map((c) => (
            <article key={`${c.acta_id}-${c.pagina}`} className="cita">
              <button className="enlace" onClick={() => onVerPagina(c.acta_id, c.pagina)}>
                {c.acta_titulo} · página {c.pagina}
              </button>
              <p><Fragmento texto={c.fragmento} /></p>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

function Concentracion() {
  const [filas, setFilas] = useState([])
  useEffect(() => { api.concentracion().then(setFilas).catch(() => setFilas([])) }, [])

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

function Actas({ onVerPagina }) {
  const [actas, setActas] = useState([])
  useEffect(() => { api.actas().then(setActas).catch(() => setActas([])) }, [])

  return (
    <section>
      <h2>Actas cargadas</h2>
      <ul>
        {actas.map((a) => (
          <li key={a.id}>
            <button className="enlace" onClick={() => onVerPagina(a.id, 1)}>{a.titulo}</button>
            {' '}— {a.fecha} · {a.paginas} páginas
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function App() {
  const [pagina, setPagina] = useState(null)
  const verPagina = (actaId, numero) => api.pagina(actaId, numero).then(setPagina)

  return (
    <main>
      <header>
        <h1>CabildoAbierto AI</h1>
        <p>Consulta las actas de cabildo con citas exactas de página.</p>
      </header>
      <Preguntas onVerPagina={verPagina} />
      {pagina && (
        <section className="pagina">
          <h2>{pagina.acta_titulo} · página {pagina.pagina}</h2>
          <p>{pagina.texto}</p>
          <button onClick={() => setPagina(null)}>Cerrar</button>
        </section>
      )}
      <Concentracion />
      <Actas onVerPagina={verPagina} />
    </main>
  )
}
