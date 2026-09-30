import { useState, useEffect, useRef } from 'react';
import { api } from '../api.js';
import MapaMexico from './MapaMexico.jsx';

function quitarAcentos(str) {
  return str ? str.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase() : "";
}

// Distancia Levenshtein para sugerencias por errores tipográficos / sintaxis
function levenshtein(a, b) {
  if (a === b) return 0;
  const an = a.length;
  const bn = b.length;
  if (an === 0) return bn;
  if (bn === 0) return an;
  const d = Array.from({ length: an + 1 }, () => new Array(bn + 1));
  for (let i = 0; i <= an; i++) d[i][0] = i;
  for (let j = 0; j <= bn; j++) d[0][j] = j;
  for (let i = 1; i <= an; i++) {
    for (let j = 1; j <= bn; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      d[i][j] = Math.min(
        d[i - 1][j] + 1,
        d[i][j - 1] + 1,
        d[i - 1][j - 1] + cost
      );
    }
  }
  return d[an][bn];
}

const ALIASES = {
  gto: 'Guanajuato',
  cdmx: 'Ciudad de México',
  df: 'Ciudad de México',
  edomex: 'México',
  nl: 'Nuevo León',
  mty: 'Monterrey',
  gdl: 'Guadalajara',
  qro: 'Querétaro',
  slp: 'San Luis Potosí',
  bc: 'Baja California',
  bcs: 'Baja California Sur',
  chih: 'Chihuahua',
  son: 'Sonora',
  sin: 'Sinaloa',
  jal: 'Jalisco',
  mich: 'Michoacán',
  ver: 'Veracruz',
  yuc: 'Yucatán',
  coah: 'Coahuila',
  tam: 'Tamaulipas',
  tamps: 'Tamaulipas',
  pue: 'Puebla',
  oax: 'Oaxaca',
  chis: 'Chiapas',
  tab: 'Tabasco',
  mor: 'Morelos',
  hgo: 'Hidalgo',
  zac: 'Zacatecas',
  ags: 'Aguascalientes',
  nay: 'Nayarit',
  col: 'Colima',
  camp: 'Campeche',
  qr: 'Quintana Roo',
  qroo: 'Quintana Roo',
  tlax: 'Tlaxcala'
};

const TEMAS = [
  'Presupuesto',
  'Obras Públicas',
  'Informes de Gobierno',
  'Contratos',
  'Actas de Cabildo',
  'Seguridad',
  'Educación',
  'Salud',
  'Cuenta Pública'
];

export default function Portada({ onElegir, onDocumento }) {
  const [estados, setEstados] = useState([]);
  const [texto, setTexto] = useState('');
  const [lugares, setLugares] = useState([]);
  const [documentos, setDocumentos] = useState([]);
  const [sugerencias, setSugerencias] = useState([]);
  const [desplegableAbierto, setDesplegableAbierto] = useState(false);
  const [buscando, setBuscando] = useState(false);
  const [aviso, setAviso] = useState('');
  const wrapperRef = useRef(null);

  useEffect(() => {
    api.estados().then(setEstados).catch(() => setEstados([]));
  }, []);

  useEffect(() => {
    setAviso('');
    const q = texto.trim();
    if (!q) {
      setLugares([]);
      setDocumentos([]);
      setSugerencias([]);
      setDesplegableAbierto(false);
      return;
    }
    const txt = quitarAcentos(q);
    setDesplegableAbierto(true);

    // 1. Búsqueda directa de Lugares (Estados y Municipios)
    let resLugares = [];
    estados.forEach(e => {
      const eNom = quitarAcentos(e.nombre);
      if (eNom.includes(txt)) {
        resLugares.push({
          tipo: 'estado',
          id: e.id,
          nombre: e.nombre,
          exacto: eNom === txt,
        });
      }
      e.municipios.forEach(m => {
        const mNom = quitarAcentos(m.nombre);
        const comb = quitarAcentos(`${m.nombre} ${e.nombre}`);
        if (mNom.includes(txt) || comb.includes(txt)) {
          resLugares.push({
            tipo: 'municipio',
            id: m.id,
            nombre: `${m.nombre}, ${e.nombre}`,
            exacto: mNom === txt,
          });
        }
      });
    });

    resLugares.sort((a, b) => (b.exacto ? 1 : 0) - (a.exacto ? 1 : 0));
    setLugares(resLugares.slice(0, 5));

    // 2. Cálculo de sugerencias difusas (errores ortográficos, sintaxis, alias)
    let posiblesSugerencias = [];
    if (txt.length >= 2) {
      // Alias directos (ej. 'gto' -> 'Guanajuato')
      if (ALIASES[txt]) {
        const aliasNombre = ALIASES[txt];
        const aliasTxt = quitarAcentos(aliasNombre);
        estados.forEach(e => {
          if (quitarAcentos(e.nombre) === aliasTxt) {
            posiblesSugerencias.push({ tipo: 'estado', id: e.id, nombre: e.nombre, dist: 0 });
          }
          e.municipios.forEach(m => {
            if (quitarAcentos(m.nombre) === aliasTxt) {
              posiblesSugerencias.push({ tipo: 'municipio', id: m.id, nombre: `${m.nombre}, ${e.nombre}`, dist: 0 });
            }
          });
        });
      }

      // Fuzzy matching con estados y municipios
      const maxDist = txt.length <= 4 ? 1 : (txt.length <= 8 ? 2 : 3);
      estados.forEach(e => {
        const eNom = quitarAcentos(e.nombre);
        if (eNom !== txt && !eNom.includes(txt)) {
          const d = levenshtein(txt, eNom);
          if (d <= maxDist) {
            posiblesSugerencias.push({ tipo: 'estado', id: e.id, nombre: e.nombre, dist: d });
          }
        }
        e.municipios.forEach(m => {
          const mNom = quitarAcentos(m.nombre);
          if (mNom !== txt && !mNom.includes(txt)) {
            const d = levenshtein(txt, mNom);
            if (d <= maxDist) {
              posiblesSugerencias.push({ tipo: 'municipio', id: m.id, nombre: `${m.nombre}, ${e.nombre}`, dist: d });
            }
          }
        });
      });

      // Fuzzy matching con temas de gobierno
      TEMAS.forEach(t => {
        const tNom = quitarAcentos(t);
        if (tNom.includes(txt)) {
          posiblesSugerencias.push({ tipo: 'tema', nombre: t, dist: 0.5 });
        } else {
          const d = levenshtein(txt, tNom);
          if (d <= maxDist) {
            posiblesSugerencias.push({ tipo: 'tema', nombre: t, dist: d });
          }
        }
      });

      // Deduplicar y ordenar por menor distancia
      const vistos = new Set();
      posiblesSugerencias = posiblesSugerencias
        .filter(s => {
          if (vistos.has(s.nombre)) return false;
          vistos.add(s.nombre);
          return true;
        })
        .sort((a, b) => a.dist - b.dist)
        .slice(0, 4);
    }
    setSugerencias(posiblesSugerencias);

    // 3. Búsqueda de Documentos y Temas en FTS5
    if (q.length >= 3) {
      setBuscando(true);
      const timer = setTimeout(() => {
        api.buscar(q)
          .then(data => {
            const vistosDocs = new Set();
            const docs = [];
            for (const r of (data.resultados || [])) {
              if (!vistosDocs.has(r.documento_id)) {
                vistosDocs.add(r.documento_id);
                docs.push(r);
                if (docs.length >= 5) break;
              }
            }
            setDocumentos(docs);
          })
          .catch(() => setDocumentos([]))
          .finally(() => setBuscando(false));
      }, 250);
      return () => clearTimeout(timer);
    } else {
      setDocumentos([]);
    }
  }, [texto, estados]);

  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setDesplegableAbierto(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [wrapperRef]);

  function aplicarSugerencia(s) {
    if (s.tipo === 'estado' || s.tipo === 'municipio') {
      onElegir({ tipo: s.tipo, id: s.id });
    } else if (s.tipo === 'tema') {
      setTexto(s.nombre);
    }
    setDesplegableAbierto(false);
  }

  // "Explorar" o Enter: abre el primer lugar, documento coincidente o sugerencia inteligente
  function explorar(e) {
    e.preventDefault();
    if (lugares.length > 0) {
      onElegir({ tipo: lugares[0].tipo, id: lugares[0].id });
    } else if (documentos.length > 0 && onDocumento) {
      onDocumento(documentos[0].documento_id);
    } else if (sugerencias.length > 0) {
      aplicarSugerencia(sugerencias[0]);
    } else if (texto.trim()) {
      setAviso(`No encontramos resultados para "${texto.trim()}". Prueba con un estado, municipio o tema (ej. "Presupuesto", "Obras").`);
    }
  }

  const tieneResultadosDirectos = lugares.length > 0 || documentos.length > 0;
  const mostrarSugerencias = !tieneResultadosDirectos && sugerencias.length > 0;

  return (
    <>
      <section className="hero">
        <h1>Explora la información de tu ciudad</h1>
        <p style={{ maxWidth: '820px', margin: '0 auto 1.2rem', lineHeight: 1.6, color: 'var(--text-muted)' }}>
          En México existe información pública sobre presupuestos, contratos, proveedores y obras, pero suele estar dispersa en diferentes portales y documentos extensos, lo que dificulta su consulta y comprensión por parte de la ciudadanía.
        </p>
        <p style={{ maxWidth: '820px', margin: '0 auto 2.5rem', lineHeight: 1.6, color: 'var(--text-muted)' }}>
          <strong>CabildoAbierto AI</strong> busca solucionar esta barrera mediante inteligencia artificial y RAG, permitiendo realizar preguntas en lenguaje natural y obtener respuestas claras junto con su fuente y página correspondiente. Así, la información pública se vuelve más accesible, verificable y útil para la participación ciudadana.
        </p>
        
        <div className="search-container" ref={wrapperRef}>
          <form className="search-bar" onSubmit={explorar}>
            <i className="fa-solid fa-magnifying-glass" style={{ color: '#aaa', marginLeft: '15px' }}></i>
            <input 
              type="text" 
              value={texto} 
              onFocus={() => setDesplegableAbierto(true)}
              onChange={e => setTexto(e.target.value)} 
              placeholder="Ej. Irapuato, Guanajuato, Presupuesto..." 
            />
            {buscando && <i className="fa-solid fa-circle-notch fa-spin" style={{ color: 'var(--accent-color)', marginRight: '10px' }}></i>}
            <button type="submit" className="search-btn">
              Explorar
            </button>
          </form>

          {mostrarSugerencias && (
            <div className="sugerencias-banner">
              <div className="sugerencias-header">
                <i className="fa-solid fa-lightbulb" style={{ color: '#e67e22', marginRight: '6px' }}></i>
                <span>¿Quizás quisiste decir?</span>
              </div>
              <div className="sugerencias-chips">
                {sugerencias.map((s, idx) => (
                  <button 
                    key={`chip-${idx}`} 
                    type="button" 
                    className="chip-sugerencia" 
                    onClick={() => aplicarSugerencia(s)}
                  >
                    <i className={s.tipo === 'tema' ? 'fa-solid fa-file-lines' : 'fa-solid fa-location-dot'} style={{ marginRight: '6px' }}></i>
                    {s.nombre}
                  </button>
                ))}
              </div>
            </div>
          )}

          {aviso && !mostrarSugerencias && <p className="tenue" style={{ marginTop: '12px' }}>{aviso}</p>}
          
          {desplegableAbierto && (tieneResultadosDirectos || mostrarSugerencias) && (
            <ul className="search-results">
              {lugares.length > 0 && (
                <>
                  <li className="search-group-title"><i className="fa-solid fa-map-location-dot" style={{ marginRight: '6px' }}></i> Estados y Municipios</li>
                  {lugares.map((r, i) => (
                    <li key={`lugar-${i}`} onClick={() => { onElegir({ tipo: r.tipo, id: r.id }); setDesplegableAbierto(false); }}>
                      <i className="fa-solid fa-location-dot" style={{ marginRight: '10px', color: 'var(--accent-color)' }}></i>
                      <span>{r.nombre}</span> {r.tipo === 'estado' ? <span className="badge-tipo">Estado</span> : ''}
                    </li>
                  ))}
                </>
              )}
              {documentos.length > 0 && (
                <>
                  <li className="search-group-title"><i className="fa-regular fa-file-pdf" style={{ marginRight: '6px' }}></i> Documentos Oficiales</li>
                  {documentos.map((d, i) => (
                    <li key={`doc-${i}`} onClick={() => { onDocumento(d.documento_id); setDesplegableAbierto(false); }} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <i className="fa-regular fa-file-lines" style={{ color: 'var(--primary-color)' }}></i>
                        <span style={{ fontWeight: 600 }}>{d.documento_titulo}</span>
                      </div>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', paddingLeft: '22px' }}>
                        {d.lugar} · {d.seccion} (pág. {d.pagina})
                      </span>
                    </li>
                  ))}
                </>
              )}
              {mostrarSugerencias && (
                <>
                  <li className="search-group-title">
                    <i className="fa-solid fa-wand-magic-sparkles" style={{ marginRight: '6px', color: 'var(--accent-color)' }}></i>
                    Sugerencias de búsqueda
                  </li>
                  {sugerencias.map((s, idx) => (
                    <li key={`sug-drop-${idx}`} onClick={() => aplicarSugerencia(s)} className="sugerencia-item">
                      <i className={s.tipo === 'tema' ? 'fa-regular fa-file-lines' : 'fa-solid fa-location-dot'} style={{ marginRight: '10px', color: 'var(--accent-color)' }}></i>
                      <span>{s.nombre}</span>
                      <span className="badge-tipo">{s.tipo === 'tema' ? 'Tema' : (s.tipo === 'estado' ? 'Estado' : 'Municipio')}</span>
                    </li>
                  ))}
                </>
              )}
            </ul>
          )}
        </div>

        {/* Mapa Interactivo de la República Mexicana directamente debajo del buscador */}
        <div className="mapa-home-wrapper">
          <div className="mapa-home-header">
            <h3>
              <i className="fa-solid fa-map-location-dot" style={{ color: 'var(--accent-color)', marginRight: '8px' }}></i>
              Explora México en el Mapa Interactivo
            </h3>
            <p>Selecciona cualquier estado o haz clic en su pin para consultar sus informes oficiales, actas y municipios.</p>
          </div>
          <MapaMexico estados={estados} onElegirEstado={onElegir} />
        </div>
      </section>

      <section style={{ textAlign: 'center', marginTop: '3rem', marginBottom: '4rem', padding: '0 20px' }}>
        <h3 style={{ color: 'var(--text-muted)', fontWeight: 500, fontSize: '1.4rem', marginBottom: '2rem' }}>¿Cómo funciona CabildoAbierto?</h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', maxWidth: '1100px', margin: '0 auto' }}>
          <div className="cf-card">
            <i className="fa-regular fa-file-pdf"></i>
            <h4>1. Recopilación de datos</h4>
            <p>Los gobiernos publican sus documentos oficiales, presupuestos y reportes.</p>
          </div>
          <div className="cf-card">
            <i className="fa-solid fa-microchip"></i>
            <h4>2. Procesamiento de IA</h4>
            <p>La IA extrae resúmenes ejecutivos, cifras auditables y puntos clave automáticamente.</p>
          </div>
          <div className="cf-card">
            <i className="fa-regular fa-message"></i>
            <h4>3. Búsqueda Inteligente</h4>
            <p>Haces preguntas en lenguaje cotidiano y recibes respuestas directas y claras.</p>
          </div>
          <div className="cf-card">
            <i className="fa-regular fa-check-circle"></i>
            <h4>4. Verificación</h4>
            <p>Revisas la fuente exacta y la página del documento con un solo clic.</p>
          </div>
        </div>
      </section>
    </>
  );
}
