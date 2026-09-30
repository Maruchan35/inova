import { useState, useRef, useEffect } from 'react';
import { api } from '../api.js';
import Fragmento from './Fragmento.jsx';

export default function Chatbot({ filtros, onVerPagina, abiertoPorDefecto, onCerrar }) {
  const [open, setOpen] = useState(false);
  const [pregunta, setPregunta] = useState('');
  const [mensajes, setMensajes] = useState([{
    tipo: 'bot',
    texto: '¡Hola! Soy el asistente RAG de CabildoAbierto. Puedo leer contratos, presupuestos y auditorías por ti. ¿Sobre qué obra te gustaría consultar hoy?'
  }]);
  const [cargando, setCargando] = useState(false);
  const bodyRef = useRef(null);

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
            <h4 style={{ fontWeight: 500 }}><i className="fa-solid fa-wand-magic-sparkles" style={{ marginRight: '8px' }}></i> Asistente IA</h4>
            <i className="fa-solid fa-xmark close-btn" onClick={() => { setOpen(false); if (onCerrar) onCerrar(); }} style={{ cursor: 'pointer' }}></i>
          </div>
          <div className="chat-messages" ref={bodyRef}>
            {mensajes.map((m, i) => (
              <div key={i} className={`msg-bubble ${m.tipo === 'bot' ? 'msg-bot' : 'msg-user'}`}>
                {m.texto && <p>{m.texto}</p>}
                {m.error && <p className="error">{m.error}</p>}
                {m.resultado && (
                  <div>
                    <p>{m.resultado.respuesta}</p>
                    {m.resultado.citas.map(c => (
                      <div key={`${c.documento_id}-${c.pagina}`} className="cita">
                        <button className="btn-link" onClick={() => onVerPagina(c.documento_id, c.pagina)}>
                          <strong>{c.documento_titulo}</strong> · pág. {c.pagina} ({c.lugar})
                        </button>
                        <p><Fragmento texto={c.fragmento} /></p>
                      </div>
                    ))}
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
