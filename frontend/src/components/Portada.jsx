import { useState, useEffect, useRef } from 'react';
import { api } from '../api.js';

function quitarAcentos(str) {
  return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

export default function Portada({ onElegir }) {
  const [estados, setEstados] = useState([]);
  const [texto, setTexto] = useState('');
  const [resultados, setResultados] = useState([]);
  const wrapperRef = useRef(null);

  useEffect(() => {
    api.estados().then(setEstados).catch(() => setEstados([]));
  }, []);

  useEffect(() => {
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

  return (
    <>
      <section className="hero">
        <h1>Explora la información de tu ciudad</h1>
        <p>Busca cualquier estado o municipio y accede a informes, presupuestos y contratos al instante.</p>
        
        <div className="search-container" ref={wrapperRef}>
          <div className="search-bar">
            <i className="fa-solid fa-magnifying-glass" style={{ color: '#aaa', marginLeft: '15px' }}></i>
            <input 
              type="text" 
              value={texto} 
              onChange={e => setTexto(e.target.value)} 
              placeholder="Ej. Irapuato, Guanajuato..." 
            />
            <button className="search-btn">
              Explorar
            </button>
          </div>
          
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
