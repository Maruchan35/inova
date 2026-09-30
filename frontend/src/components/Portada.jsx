import { useState, useEffect, useRef } from 'react';
import { api } from '../api.js';

function quitarAcentos(str) {
  return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

export default function Portada({ onElegir, onDocumento }) {
  const [estados, setEstados] = useState([]);
  const [texto, setTexto] = useState('');
  const [lugares, setLugares] = useState([]);
  const [documentos, setDocumentos] = useState([]);
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
      return;
    }
    const txt = quitarAcentos(q);

    // 1. Búsqueda de Lugares (Estados y Municipios corregido)
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

    // 2. Búsqueda de Documentos y Temas en FTS5
    if (q.length >= 3) {
      setBuscando(true);
      const timer = setTimeout(() => {
        api.buscar(q)
          .then(data => {
            const vistos = new Set();
            const docs = [];
            for (const r of (data.resultados || [])) {
              if (!vistos.has(r.documento_id)) {
                vistos.add(r.documento_id);
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
        setLugares([]);
        setDocumentos([]);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [wrapperRef]);

  // "Explorar" o Enter: abre el primer lugar o documento coincidente
  function explorar(e) {
    e.preventDefault();
    if (lugares.length > 0) {
      onElegir({ tipo: lugares[0].tipo, id: lugares[0].id });
    } else if (documentos.length > 0 && onDocumento) {
      onDocumento(documentos[0].documento_id);
    } else if (texto.trim()) {
      setAviso('No encontramos resultados para esa búsqueda. Prueba con el nombre de un estado, municipio, o tema como "Presupuesto" o "Obras".');
    }
  }

  return (
    <>
      <section className="hero">
        <h1>Explora la información de tu ciudad</h1>
        <p>Busca cualquier estado o municipio y accede a informes, presupuestos y contratos al instante.</p>
        
        <div className="search-container" ref={wrapperRef}>
          <form className="search-bar" onSubmit={explorar}>
            <i className="fa-solid fa-magnifying-glass" style={{ color: '#aaa', marginLeft: '15px' }}></i>
            <input 
              type="text" 
              value={texto} 
              onChange={e => setTexto(e.target.value)} 
              placeholder="Ej. Irapuato, Guanajuato..." 
            />
            <button type="submit" className="search-btn">
              Explorar
            </button>
          </form>
          {aviso && <p className="tenue" style={{ marginTop: '10px' }}>{aviso}</p>}
          
          {(lugares.length > 0 || documentos.length > 0) && (
            <ul className="search-results">
              {lugares.length > 0 && (
                <>
                  <li className="search-group-title"><i className="fa-solid fa-map-location-dot" style={{ marginRight: '6px' }}></i> Estados y Municipios</li>
                  {lugares.map((r, i) => (
                    <li key={`lugar-${i}`} onClick={() => onElegir({ tipo: r.tipo, id: r.id })}>
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
                    <li key={`doc-${i}`} onClick={() => onDocumento(d.documento_id)} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
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
            </ul>
          )}
        </div>
      </section>

      <section style={{ textAlign: 'center', marginTop: '3rem', overflow: 'hidden' }}>
        <h3 style={{ color: 'var(--text-muted)', fontWeight: 400, marginBottom: '2rem' }}>¿Cómo funciona CabildoAbierto?</h3>
        
        <div className="como-funciona-container">
          <div className="como-funciona-track">
            <div className="cf-card">
              <i className="fa-regular fa-file-pdf"></i>
              <h4>1. Recopilación de datos</h4>
              <p>Los gobiernos suben sus documentos públicos y reportes.</p>
            </div>
            <div className="cf-card">
              <i className="fa-solid fa-microchip"></i>
              <h4>2. Procesamiento de IA</h4>
              <p>La IA extrae resúmenes y puntos clave automáticamente.</p>
            </div>
            <div className="cf-card">
              <i className="fa-regular fa-message"></i>
              <h4>3. Búsqueda Inteligente</h4>
              <p>Haces preguntas y recibes respuestas directas y claras.</p>
            </div>
            <div className="cf-card">
              <i className="fa-regular fa-check-circle"></i>
              <h4>4. Verificación</h4>
              <p>Revisas la fuente exacta con un solo clic.</p>
            </div>
            
            {/* Duplicated for seamless loop */}
            <div className="cf-card">
              <i className="fa-regular fa-file-pdf"></i>
              <h4>1. Recopilación de datos</h4>
              <p>Los gobiernos suben sus documentos públicos y reportes.</p>
            </div>
            <div className="cf-card">
              <i className="fa-solid fa-microchip"></i>
              <h4>2. Procesamiento de IA</h4>
              <p>La IA extrae resúmenes y puntos clave automáticamente.</p>
            </div>
            <div className="cf-card">
              <i className="fa-regular fa-message"></i>
              <h4>3. Búsqueda Inteligente</h4>
              <p>Haces preguntas y recibes respuestas directas y claras.</p>
            </div>
            <div className="cf-card">
              <i className="fa-regular fa-check-circle"></i>
              <h4>4. Verificación</h4>
              <p>Revisas la fuente exacta con un solo clic.</p>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
