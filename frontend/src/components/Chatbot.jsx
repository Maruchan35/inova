import { useState, useRef, useEffect } from 'react';
import { api } from '../api.js';
import Fragmento from './Fragmento.jsx';
import { vozDisponible, hablar, callar } from '../voz.js';

// Lo que se lee en voz alta cuando la pregunta se hizo hablando: la respuesta y de dónde sale.
function paraLeer(res) {
  const cita = res.citas?.[0];
  return res.respuesta + (cita ? ` Esto sale de ${cita.documento_titulo}, página ${cita.pagina}.` : '');
}

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

// Las últimas preguntas con su respuesta (desde el último cambio de página), para entender "¿y en León?".
function historialDe(mensajes) {
  const desde = mensajes.map(m => m.tipo).lastIndexOf('aviso') + 1;
  const pares = [];
  for (let i = desde; i < mensajes.length - 1; i++) {
    if (mensajes[i].tipo === 'user' && mensajes[i + 1].resultado) {
      pares.push({ pregunta: mensajes[i].texto, respuesta: mensajes[i + 1].resultado.respuesta });
    }
  }
  return pares.slice(-3);
}

// Tamaño de la ventana del chat: se puede ampliar con un botón o arrastrando su esquina, y se recuerda.
const TAM_NORMAL = { ancho: 440, alto: 600 };
const TAM_GRANDE = { ancho: 860, alto: 2000 };

function limitar(t) {
  return {
    ancho: Math.round(Math.max(320, Math.min(t.ancho, window.innerWidth - 40))),
    alto: Math.round(Math.max(360, Math.min(t.alto, window.innerHeight - 120))),
  };
}

function tamGuardado() {
  try {
    const t = JSON.parse(localStorage.getItem('chat-tam'));
    if (t && t.ancho > 0 && t.alto > 0) return t;
  } catch (e) {}
  return TAM_NORMAL;
}

export default function Chatbot({ filtros, contexto, onVerPagina, onIr, abiertoPorDefecto, onCerrar, dictado, onVoz }) {
  const [open, setOpen] = useState(false);
  const [tam, setTam] = useState(tamGuardado);
  const inputRef = useRef(null);
  const [pregunta, setPregunta] = useState('');
  const [mensajes, setMensajes] = useState([{
    tipo: 'bot',
    texto: '¡Hola! Pregúntame por los documentos oficiales de cualquier estado o municipio: un informe, un presupuesto, una obra o un contrato. Cada dato te lo doy con la página de donde sale.'
  }]);
  const [cargando, setCargando] = useState(false);
  const [sugeridas, setSugeridas] = useState([]);
  const bodyRef = useRef(null);
  const contextoAnterior = useRef(contexto);

  // Si cambias de página, el chatbot avisa sobre qué preguntas ahora.
  useEffect(() => {
    if (contexto && contexto !== contextoAnterior.current) {
      contextoAnterior.current = contexto;
      setMensajes(prev => prev.length > 1 ? [...prev, { tipo: 'aviso', texto: `Ahora preguntas sobre: ${contexto}` }] : prev);
    }
  }, [contexto]);

  // Preguntas de ejemplo según la página (las da el backend).
  const filtrosClave = JSON.stringify(filtros || {});
  useEffect(() => {
    if (!open) return;
    let vigente = true;
    api.sugeridas(filtros || {})
      .then(s => { if (vigente) setSugeridas(s); })
      .catch(() => { if (vigente) setSugeridas([]); });
    return () => { vigente = false; };
  }, [open, filtrosClave]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (abiertoPorDefecto) {
      setOpen(true);
    }
  }, [abiertoPorDefecto]);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [mensajes, cargando]);

  // Al abrirlo (con su botón o con "Chat con IA" de un documento), listo para escribir.
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    try { localStorage.setItem('chat-tam', JSON.stringify(tam)); } catch (e) {}
  }, [tam]);

  // La ventana está pegada abajo a la derecha: crece al arrastrar su esquina de arriba a la izquierda.
  function empezarAjuste(e) {
    e.preventDefault();
    const inicio = { x: e.clientX, y: e.clientY, ...limitar(tam) };
    const mover = ev => setTam(limitar({ ancho: inicio.ancho + inicio.x - ev.clientX, alto: inicio.alto + inicio.y - ev.clientY }));
    const soltar = () => {
      window.removeEventListener('pointermove', mover);
      window.removeEventListener('pointerup', soltar);
    };
    window.addEventListener('pointermove', mover);
    window.addEventListener('pointerup', soltar);
  }

  const ampliado = tam.ancho > TAM_NORMAL.ancho + 60;

  async function enviar(elegida, porVoz = false) {
    const txt = (typeof elegida === 'string' ? elegida : pregunta).trim();
    if (!txt || cargando) return;
    callar();
    const historial = historialDe(mensajes);
    setPregunta('');
    setMensajes(prev => [...prev, { tipo: 'user', texto: txt }]);
    setCargando(true);

    try {
      const res = await api.preguntar(txt, filtros, historial);
      setMensajes(prev => [...prev, { tipo: 'bot', resultado: res }]);
      if (porVoz) hablar(paraLeer(res));
    } catch (err) {
      setMensajes(prev => [...prev, { tipo: 'bot', error: 'Hubo un error al buscar en los documentos: ' + err.message }]);
    } finally {
      setCargando(false);
    }
  }

  // Una pregunta dicha por voz: se abre el chat, se manda y la respuesta se lee en voz alta.
  useEffect(() => {
    if (dictado?.texto) {
      setOpen(true);
      enviar(dictado.texto, true);
    }
  }, [dictado?.n]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) callar();
  }, [open]);

  return (
    <div className="chatbot-container">
      <div className="chat-toggle" onClick={() => { setOpen(!open); if (open && onCerrar) onCerrar(); }}>
        <i className={open ? "fa-solid fa-xmark" : "fa-regular fa-message"}></i>
      </div>
      {open && (
        <div className="chat-window" style={{ width: tam.ancho, height: tam.alto }}>
          <span className="chat-ajustar" onPointerDown={empezarAjuste} title="Arrastra para cambiar el tamaño"></span>
          <div className="chat-header">
            <div>
              <h4 style={{ fontWeight: 500 }}><i className="fa-solid fa-wand-magic-sparkles" style={{ marginRight: '8px' }}></i> Asistente IA</h4>
              {contexto && <small className="chat-contexto">Preguntando sobre: {contexto}</small>}
            </div>
            <div className="chat-header-botones">
              <i
                className={ampliado ? "fa-solid fa-compress" : "fa-solid fa-expand"}
                title={ampliado ? "Tamaño normal" : "Hacer más grande"}
                onClick={() => setTam(ampliado ? TAM_NORMAL : limitar(TAM_GRANDE))}
              ></i>
              <i className="fa-solid fa-xmark close-btn" title="Cerrar" onClick={() => { setOpen(false); if (onCerrar) onCerrar(); }}></i>
            </div>
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
                    {m.resultado.detalle?.cifras_sin_verificar?.length > 0 && (
                      <p className="chat-verificar">
                        <i className="fa-solid fa-triangle-exclamation"></i> No encontré estas cifras tal cual en las páginas: {m.resultado.detalle.cifras_sin_verificar.join(', ')}. Revísalas en el documento.
                      </p>
                    )}
                    {m.resultado.detalle?.entendido && (m.resultado.detalle.entendido.lugar || m.resultado.detalle.entendido.seccion) && (
                      <p className="chat-entendido">
                        {m.resultado.detalle.entendido.tipo === 'comparacion' ? 'Comparé: ' : 'Entendí: '}
                        {[m.resultado.detalle.entendido.lugar, m.resultado.detalle.entendido.seccion].filter(Boolean).join(' · ')}
                      </p>
                    )}
                    {describirOrigen(m.resultado.detalle) && (
                      <p className={`chat-origen origen-${m.resultado.detalle.origen}`}>{describirOrigen(m.resultado.detalle)}</p>
                    )}
                  </div>
                )}
              </div>
            ))}
            {!cargando && sugeridas.length > 0 && (mensajes.length === 1 || mensajes[mensajes.length - 1].tipo === 'aviso') && (
              <div className="chat-sugeridas">
                {sugeridas.map(s => <button key={s} onClick={() => enviar(s)}>{s}</button>)}
              </div>
            )}
            {cargando && <span className="typing-indicator">Buscando en los documentos...</span>}
          </div>
          <div className="chat-input">
            <input
              ref={inputRef}
              type="text"
              value={pregunta}
              onChange={e => setPregunta(e.target.value)}
              placeholder="Ej. ¿Cuánto costó el hospital?"
              onKeyDown={e => e.key === 'Enter' && enviar()}
            />
            {vozDisponible && onVoz && (
              <button className="chat-mic" onClick={onVoz} title="Pregunta hablando"><i className="fa-solid fa-microphone"></i></button>
            )}
            <button onClick={enviar}><i className="fa-regular fa-paper-plane"></i></button>
          </div>
        </div>
      )}
    </div>
  );
}
