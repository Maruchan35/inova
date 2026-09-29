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
    setResultados(res.slice(0, 10)); // max 10
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
        <h1>Transparencia Inteligente para Todos</h1>
        <div className="hero-description">
          <p>En MÃ©xico existe informaciÃ³n pÃºblica sobre presupuestos, contratos, proveedores y obras, pero suele estar dispersa en diferentes portales y documentos extensos, lo que dificulta su consulta y comprensiÃ³n por parte de la ciudadanÃ­a.</p>
          <p><span className="brand-highlight">CabildoAbierto</span> busca solucionar esta barrera mediante inteligencia artificial y RAG, permitiendo realizar preguntas en lenguaje natural y obtener respuestas claras junto con su fuente y pÃ¡gina correspondiente. AsÃ­, la informaciÃ³n pÃºblica se vuelve mÃ¡s accesible, verificable y Ãºtil para la participaciÃ³n ciudadana.</p>
        </div>
      </section>

      <div className="search-container" ref={wrapperRef}>
        <div className="search-bar">
          <input 
            type="text" 
            value={texto} 
            onChange={e => setTexto(e.target.value)} 
            placeholder="Buscar por estado o municipio (ej. Irapuato, Guanajuato)..." 
          />
          <button className="search-btn">
            <i className="fa-solid fa-location-arrow"></i> Buscar Obras
          </button>
        </div>
        
        {resultados.length > 0 && (
          <ul className="search-results">
            {resultados.map((r, i) => (
              <li key={i} onClick={() => onElegir({ tipo: r.tipo, id: r.id })}>
                {r.nombre} {r.tipo === 'estado' ? '(Estado)' : ''}
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
