import { useState, useEffect, useRef } from 'react';
import { api } from '../api.js';
import MapaMexico from './MapaMexico.jsx';

function quitarAcentos(str) {
  return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

export default function Portada({ onElegir }) {
  const [estados, setEstados] = useState([]);
  const [texto, setTexto] = useState('');
  const [resultados, setResultados] = useState([]);
  const [aviso, setAviso] = useState('');
  const wrapperRef = useRef(null);

  useEffect(() => {
    api.estados().then(setEstados).catch(() => setEstados([]));
  }, []);

  useEffect(() => {
    setAviso('');
    if (!texto.trim()) {
      setResultados([]);
      return;
    }
    const txt = quitarAcentos(texto.trim());
    let res = [];
    estados.forEach(e => {
      if (quitarAcentos(e.nombre).includes(txt)) {
        res.push({ tipo: 'estado', id: e.id, nombre: e.nombre });
      }
      e.municipios.forEach(m => {
        if (quitarAcentos(m.nombre).includes(txt) || quitarAcentos(e.nombre).includes(txt)) {
          res.push({ tipo: 'municipio', id: m.id, nombre: `${m.nombre}, ${e.nombre}` });
        }
      });
    });
    setResultados(res.slice(0, 8)); // max 8
  }, [texto, estados]);

  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setResultados([]);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [wrapperRef]);

  // "Explorar" o Enter: abre el primer lugar que coincide con lo escrito.
  function explorar(e) {
    e.preventDefault();
    if (resultados.length > 0) {
      onElegir({ tipo: resultados[0].tipo, id: resultados[0].id });
    } else if (texto.trim()) {
      setAviso('No encontramos ese lugar. Prueba con el nombre de un estado o municipio.');
    }
  }

  return (
    <>
      <section className="hero">
        <h1>Explora la información de tu ciudad</h1>
        <p>
          En México existe información pública sobre presupuestos, contratos, proveedores y obras, pero suele estar dispersa en diferentes portales y documentos extensos, lo que dificulta su consulta y comprensión por parte de la ciudadanía.
        </p>
        <p style={{ marginTop: '-1.5rem', marginBottom: '3rem' }}>
          CabildoAbierto AI busca solucionar esta barrera mediante inteligencia artificial y RAG, permitiendo realizar preguntas en lenguaje natural y obtener respuestas claras junto con su fuente y página correspondiente. Así, la información pública se vuelve más accesible, verificable y útil para la participación ciudadana.
        </p>        
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
          
          {resultados.length > 0 && (
            <ul className="search-results">
              {resultados.map((r, i) => (
                <li key={i} onClick={() => onElegir({ tipo: r.tipo, id: r.id })}>
                  <i className="fa-solid fa-location-dot" style={{ marginRight: '10px', color: '#ccc' }}></i>
                  {r.nombre} {r.tipo === 'estado' ? '(Estado)' : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section style={{ textAlign: 'center', marginTop: '4rem', padding: '0 20px', paddingBottom: '2rem' }}>
        <h3 style={{ color: 'var(--text-muted)', fontWeight: 400, marginBottom: '2rem' }}>Explora por Estado</h3>
        <MapaMexico estados={estados} onElegirEstado={onElegir} />
      </section>

      <section style={{ textAlign: 'center', marginTop: '3rem', marginBottom: '4rem', overflow: 'hidden' }}>
        <h3 style={{ color: 'var(--text-muted)', fontWeight: 400, marginBottom: '2rem' }}>¿Cómo funciona CabildoAbierto?</h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', maxWidth: '1200px', margin: '0 auto', padding: '0 20px' }}>
          <div className="cf-card" style={{ animation: 'none' }}>
            <i className="fa-regular fa-file-pdf"></i>
            <h4>1. Recopilación de datos</h4>
            <p>Los gobiernos suben sus documentos públicos y reportes.</p>
          </div>
          <div className="cf-card" style={{ animation: 'none' }}>
            <i className="fa-solid fa-microchip"></i>
            <h4>2. Procesamiento de IA</h4>
            <p>La IA extrae resúmenes y puntos clave automáticamente.</p>
          </div>
          <div className="cf-card" style={{ animation: 'none' }}>
            <i className="fa-regular fa-message"></i>
            <h4>3. Búsqueda Inteligente</h4>
            <p>Haces preguntas y recibes respuestas directas y claras.</p>
          </div>
          <div className="cf-card" style={{ animation: 'none' }}>
            <i className="fa-regular fa-check-circle"></i>
            <h4>4. Verificación</h4>
            <p>Revisas la fuente exacta con un solo clic.</p>
          </div>
        </div>
      </section>
    </>
  );
}
