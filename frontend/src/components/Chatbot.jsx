import { useState, useRef, useEffect } from 'react';
import { api } from '../api.js';
import Fragmento from './Fragmento.jsx';

// Debajo de cada respuesta: de dónde salió (IA, caché o sin IA), cuánto tardó y cuánto costó.
function describirOrigen(detalle) {
  if (!detalle) return null;
  const costo = detalle.costo_usd ? ` · $${detalle.costo_usd.toFixed(4)} USD` : '';
  const amplio = detalle.alcance === 'todo' ? 'No había nada de este lugar; busqué en todos los documentos. ' : '';
  switch (detalle.origen) {
    case 'ia': return `${amplio}Respondió la IA (DeepSeek) en ${detalle.segundos} s${costo}`;
    case 'cache': return 'Respuesta guardada: alguien ya lo había preguntado · al instante · $0';
    case 'sin_resultados': return 'No encontré páginas relacionadas con tu pregunta.';
    default: return amplio + (detalle.motivo || 'La IA no está disponible en este momento.');
  }
}

export default function Chatbot({ filtros, contexto, onVerPagina, onIr, abiertoPorDefecto, onCerrar }) {
  const [open, setOpen] = useState(false);
  const [pregunta, setPregunta] = useState('');
  const [mensajes, setMensajes] = useState([{
    tipo: 'bot',
    texto: '¡Hola! Pregúntame por los documentos oficiales de cualquier estado o municipio: un informe, un presupuesto, una obra o un contrato. Cada dato te lo doy con la página de donde sale.'
  }]);
  const [cargando, setCargando] = useState(false);
  const bodyRef = useRef(null);
  const contextoAnterior = useRef(contexto);

  // Si cambias de página, el chatbot avisa sobre qué preguntas ahora.
  useEffect(() => {
    if (contexto && contexto !== contextoAnterior.current) {
      contextoAnterior.current = contexto;
      setMensajes(prev => prev.length > 1 ? [...prev, { tipo: 'aviso', texto: `Ahora preguntas sobre: ${contexto}` }] : prev);
    }
  }, [contexto]);

  useEffect(() => {
    if (abiertoPorDefecto) {
      setOpen(true);
    }
  }, [abiertoPorDefecto]);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [mensajes, cargando]);

  async function enviar() {
    if (!pregunta.trim()) return;
    const txt = pregunta.trim();
    setPregunta('');
    setMensajes(prev => [...prev, { tipo: 'user', texto: txt }]);
    setCargando(true);

    try {
      const res = await api.preguntar(txt, filtros);
      setMensajes(prev => [...prev, { tipo: 'bot', resultado: res }]);
    } catch (err) {
      setMensajes(prev => [...prev, { tipo: 'bot', error: 'Hubo un error al buscar en los documentos: ' + err.message }]);
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="chatbot-container">
      <div className="chat-toggle" onClick={() => { setOpen(!open); if (open && onCerrar) onCerrar(); }}>
        <i className={open ? "fa-solid fa-xmark" : "fa-regular fa-message"}></i>
      </div>
      {open && (
        <div className="chat-window">
          <div className="chat-header">
            <div>
              <h4 style={{ fontWeight: 500 }}><i className="fa-solid fa-wand-magic-sparkles" style={{ marginRight: '8px' }}></i> Asistente IA</h4>
              {contexto && <small className="chat-contexto">Preguntando sobre: {contexto}</small>}
            </div>
            <i className="fa-solid fa-xmark close-btn" onClick={() => { setOpen(false); if (onCerrar) onCerrar(); }} style={{ cursor: 'pointer' }}></i>
          </div>
          <div className="chat-messages" ref={bodyRef}>
            {mensajes.map((m, i) => (
              m.tipo === 'aviso' ? <p key={i} className="chat-aviso">{m.texto}</p> :
              <div key={i} className={`msg-bubble ${m.tipo === 'bot' ? 'msg-bot' : 'msg-user'}`}>
                {m.texto && <p>{m.texto}</p>}
                {m.error && <p className="error">{m.error}</p>}
                {m.resultado && (
                  <div>
                    <p>{m.resultado.respuesta}</p>
                    {m.resultado.citas.map((c, j) => (
                      <div key={j} className="cita">
                        <button className="btn-link" onClick={() => onVerPagina(c.documento_id, c.pagina)}>
                          <strong>{c.documento_titulo}</strong> · pág. {c.pagina} ({c.lugar})
                        </button>
                        <p><Fragmento texto={c.fragmento} /></p>
                      </div>
                    ))}
                    {m.resultado.documentos?.length > 0 && (
                      <div className="chat-documentos">
                        <strong>Documentos relacionados</strong>
                        {m.resultado.documentos.map(d => (
                          <button key={d.id} className="btn-link" onClick={() => onIr?.(`/documento/${d.id}`)}>
                            {d.titulo} <span>· {d.lugar}{d.anio ? ` · ${d.anio}` : ''}</span>
                          </button>
                        ))}
                      </div>
                    )}
                    {m.resultado.detalle?.entendido && (m.resultado.detalle.entendido.lugar || m.resultado.detalle.entendido.seccion) && (
                      <p className="chat-entendido">
                        Entendí: {[m.resultado.detalle.entendido.lugar, m.resultado.detalle.entendido.seccion].filter(Boolean).join(' · ')}
                      </p>
                    )}
                    {describirOrigen(m.resultado.detalle) && (
                      <p className={`chat-origen origen-${m.resultado.detalle.origen}`}>{describirOrigen(m.resultado.detalle)}</p>
                    )}
                  </div>
                )}
              </div>
            ))}
            {cargando && <span className="typing-indicator">Buscando en los documentos...</span>}
          </div>
          <div className="chat-input">
            <input
              type="text"
              value={pregunta}
              onChange={e => setPregunta(e.target.value)}
              placeholder="Ej. ¿Cuánto costó el hospital?"
              onKeyDown={e => e.key === 'Enter' && enviar()}
            />
            <button onClick={enviar}><i className="fa-regular fa-paper-plane"></i></button>
          </div>
        </div>
      )}
    </div>
  );
}
