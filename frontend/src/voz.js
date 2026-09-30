// Modo por voz con lo que ya trae el navegador (sin costo): reconocer lo que dice la persona y leer en voz alta.
// El reconocimiento existe en Chrome y Edge (computadora y Android) y necesita internet y una página segura
// (https o localhost). Donde no existe, `vozDisponible` es falso y los micrófonos no se muestran.

const Reconocimiento = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);

export const vozDisponible = Boolean(Reconocimiento);
export const lecturaDisponible = typeof window !== 'undefined' && 'speechSynthesis' in window;

const ERRORES = {
  'not-allowed': 'Necesito permiso para usar el micrófono. Permítelo en el navegador y vuelve a tocar el micrófono.',
  'service-not-allowed': 'Necesito permiso para usar el micrófono. Permítelo en el navegador y vuelve a tocar el micrófono.',
  'audio-capture': 'No encontré un micrófono en este equipo.',
  'no-speech': 'No te escuché. Toca el micrófono y vuelve a intentarlo.',
};

// El error "network" casi nunca es falta de internet: Brave (y otros derivados de Chrome) en computadora traen
// el botón pero no el servicio de reconocimiento, que solo viene en Chrome y Edge. En Android sí funciona.
function avisoSinServicio() {
  if (!navigator.onLine) return 'No hay conexión a internet para reconocer la voz.';
  const navegador = navigator.brave ? 'Brave' : 'Este navegador';
  return `${navegador} no trae reconocimiento de voz en computadora. Abre esta página en Chrome o Edge para hablarle, o escribe tu pregunta.`;
}

// Empieza a escuchar. onParcial(texto) mientras habla; onFinal(texto) al terminar; onError(mensaje) si algo falla.
// Devuelve { cancelar() }.
export function escuchar({ onParcial, onFinal, onError }) {
  const r = new Reconocimiento();
  r.lang = 'es-MX';
  r.interimResults = true;
  r.continuous = false;
  r.maxAlternatives = 1;
  let final = '';
  let cerrado = false;
  r.onresult = (e) => {
    let parcial = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const dicho = e.results[i][0].transcript;
      if (e.results[i].isFinal) final += dicho;
      else parcial += dicho;
    }
    onParcial?.(`${final} ${parcial}`.trim());
  };
  r.onerror = (e) => {
    if (cerrado) return;
    cerrado = true;
    onError?.(e.error === 'network' ? avisoSinServicio() : ERRORES[e.error] || 'No pude escucharte. Vuelve a intentarlo.');
  };
  r.onend = () => {
    if (cerrado) return;
    cerrado = true;
    if (final.trim()) onFinal?.(final.trim());
    else onError?.(ERRORES['no-speech']);
  };
  r.start();
  return { cancelar: () => { cerrado = true; r.abort(); } };
}

function vozEnEspanol() {
  const voces = window.speechSynthesis.getVoices();
  return voces.find(v => v.lang === 'es-MX') || voces.find(v => v.lang === 'es-US')
    || voces.find(v => v.lang?.startsWith('es')) || null;
}

// Lee un texto en voz alta, frase por frase (los textos largos de un jalón se cortan en Chrome).
export function hablar(texto, alTerminar) {
  if (!lecturaDisponible || !texto) { alTerminar?.(); return; }
  callar();
  const frases = texto.replace(/\s+/g, ' ').split(/(?<=[.!?])\s+/); // "$2,300,000.00" no se parte: no hay espacio
  const voz = vozEnEspanol();
  frases.map(f => f.trim()).filter(Boolean).forEach((frase, i, todas) => {
    const u = new SpeechSynthesisUtterance(frase);
    u.lang = voz?.lang || 'es-MX';
    if (voz) u.voice = voz;
    u.rate = 0.95;
    if (i === todas.length - 1 && alTerminar) { u.onend = alTerminar; u.onerror = alTerminar; }
    window.speechSynthesis.speak(u);
  });
}

export function callar() {
  if (lecturaDisponible) window.speechSynthesis.cancel();
}
