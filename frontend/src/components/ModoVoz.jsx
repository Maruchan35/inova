import { useState, useEffect, useRef } from 'react';
import { api } from '../api.js';
import { vozDisponible, escuchar, hablar, callar } from '../voz.js';

// Modo por voz: la persona toca el micrófono, dice a dónde quiere ir o qué quiere saber, y la página la lleva
// o le pregunta al chatbot. Qué hacer con lo dicho lo decide el backend (POST /api/voz).
export default function ModoVoz({ filtros, pedir, onIr, onInicio, onAtras, onPreguntar }) {
  const [fase, setFase] = useState(''); // '', 'escuchando', 'pensando', 'listo', 'error'
  const [dicho, setDicho] = useState('');
  const [mensaje, setMensaje] = useState('');
  const escucha = useRef(null);

  function cerrar() {
    escucha.current?.cancelar();
    escucha.current = null;
    callar();
    setFase('');
  }

  function empezar() {
    if (!vozDisponible) return;
    escucha.current?.cancelar();
    callar();
    setDicho('');
    setMensaje('');
    setFase('escuchando');
    try {
      escucha.current = escuchar({
        onParcial: setDicho,
        onFinal: (texto) => { setDicho(texto); atender(texto); },
        onError: (aviso) => { setMensaje(aviso); setFase('error'); hablar(aviso); },
      });
    } catch (e) {
      setMensaje('No pude encender el micrófono. Vuelve a intentarlo.');
      setFase('error');
    }
  }

  async function atender(texto) {
    setFase('pensando');
    try {
      const r = await api.voz(texto, filtros);
      setMensaje(r.decir || '');
      if (r.accion === 'preguntar') {
        setFase('');
        onPreguntar(r.pregunta); // el chatbot se abre, responde y lee la respuesta en voz alta
        return;
      }
      if (r.accion === 'ir') onIr(r.tipo, r.id, r.seccion);
      else if (r.accion === 'inicio') onInicio();
      else if (r.accion === 'atras') onAtras();
      setFase('listo');
      const navega = r.accion !== 'decir';
      hablar(r.decir, navega ? () => setFase(f => (f === 'listo' ? '' : f)) : undefined);
    } catch (e) {
      setMensaje('No pude entender la orden. Revisa tu conexión y vuelve a intentarlo.');
      setFase('error');
    }
  }

  // Otros micrófonos de la página (el del buscador y el del chat) piden empezar a escuchar.
  useEffect(() => {
    if (pedir) empezar();
  }, [pedir]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => cerrar, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!vozDisponible) return null;

  return (
    <>
      <button
        className={`voz-toggle ${fase === 'escuchando' ? 'escuchando' : ''}`}
        onClick={fase === 'escuchando' ? cerrar : empezar}
        title="Hablar: di a dónde quieres ir o qué quieres saber"
        aria-label="Modo por voz"
      >
        <i className="fa-solid fa-microphone"></i>
      </button>
      {fase && (
        <div className="voz-panel" role="status" aria-live="polite">
          <div className={`voz-icono ${fase}`}>
            <i className={fase === 'pensando' ? 'fa-solid fa-circle-notch fa-spin' : 'fa-solid fa-microphone'}></i>
          </div>
          <div className="voz-texto">
            <strong>
              {fase === 'escuchando' && 'Te escucho… habla ahora'}
              {fase === 'pensando' && 'Un momento…'}
              {fase === 'listo' && 'Entendido'}
              {fase === 'error' && 'No te entendí'}
            </strong>
            {dicho && <p className="voz-dicho">“{dicho}”</p>}
            {fase === 'escuchando' && !dicho && (
              <p className="voz-ejemplos">Por ejemplo: “llévame a Irapuato” o “¿cuánto costó el mercado?”</p>
            )}
            {mensaje && fase !== 'escuchando' && <p className="voz-mensaje">{mensaje}</p>}
          </div>
          <div className="voz-botones">
            {fase !== 'escuchando' && fase !== 'pensando' && (
              <button onClick={empezar}><i className="fa-solid fa-microphone"></i> Hablar otra vez</button>
            )}
            <button className="voz-cerrar" onClick={cerrar}>Cerrar</button>
          </div>
        </div>
      )}
    </>
  );
}
