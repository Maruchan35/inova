import { useState, useEffect, useRef } from 'react';
import { api } from '../api.js';
import Concentracion from './Concentracion.jsx';
import Chatbot from './Chatbot.jsx';
import Suscripcion from './Suscripcion.jsx';

// Coordenadas base por defecto si no hay
const DEFAULT_CENTER = [23.6345, -102.5528]; // México

export default function Lugar({ lugar, onElegir, onDocumento, onVerPagina }) {
  const [datos, setDatos] = useState(null);
  const [categoriaActiva, setCategoriaActiva] = useState(null);
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersLayer = useRef(null);

  useEffect(() => {
    const pedir = lugar.tipo === 'estado' ? api.estado : api.municipio;
    pedir(lugar.id).then(d => {
      setDatos(d);
      setCategoriaActiva(null);
    }).catch(() => setDatos(null));
  }, [lugar.tipo, lugar.id]);

  // Init Map
  useEffect(() => {
    if (!datos || !window.L || !mapRef.current) return;
    
    if (!mapInstance.current) {
      mapInstance.current = window.L.map(mapRef.current, { zoomControl: false }).setView(DEFAULT_CENTER, 5);
      window.L.control.zoom({ position: 'bottomright' }).addTo(mapInstance.current);
      
      window.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(mapInstance.current);
      
      markersLayer.current = window.L.layerGroup().addTo(mapInstance.current);
    }

    // Centro real: coordenadas de la cabecera (catálogo INEGI) que manda el backend.
    const tieneCoordenadas = datos.latitud != null && datos.longitud != null;
    const centro = tieneCoordenadas ? [datos.latitud, datos.longitud] : DEFAULT_CENTER;
    const zoom = tieneCoordenadas ? (lugar.tipo === 'municipio' ? 12 : 7) : 5;
    mapInstance.current.flyTo(centro, zoom, { duration: 1.5 });

    if (markersLayer.current) {
      markersLayer.current.clearLayers();
      if (tieneCoordenadas) {
        const etiqueta = document.createElement('strong');
        etiqueta.textContent = datos.nombre; // texto, no HTML
        window.L.marker(centro).bindPopup(etiqueta).addTo(markersLayer.current);
      }
    }
    
    // We will save the center to state so we can render pins
    return () => {
      // Cleanup map on unmount
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    }
  }, [datos]);



  if (!datos) return <div style={{ textAlign: 'center', marginTop: '4rem' }}>Cargando información...</div>;

  const filtros = lugar.tipo === 'estado' ? { estado_id: datos.id } : { municipio_id: datos.id };
  const locationName = datos.nombre + (datos.estado ? `, ${datos.estado.nombre}` : '');

  // Flatten all documents for the carousel if no category is selected, or filter by category
  let docsToShow = [];
  if (categoriaActiva) {
    const sec = datos.secciones.find(s => s.clave === categoriaActiva);
    if (sec) docsToShow = sec.documentos;
  } else {
    datos.secciones.forEach(s => { docsToShow.push(...s.documentos) });
  }

  const iconForSection = (clave) => {
    const icons = {
      informes: 'fa-regular fa-file-lines',
      presupuesto: 'fa-regular fa-money-bill-1',
      obras: 'fa-solid fa-person-digging', // obras is usually solid, or use fa-building
      actas: 'fa-solid fa-file-signature',
      contratos: 'fa-regular fa-handshake'
    };
    return icons[clave] || 'fa-regular fa-folder';
  };

  return (
    <div className="lugar-container">
      <div className="lugar-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <i className="fa-solid fa-map-location-dot" style={{ color: 'var(--accent-color)' }}></i> {locationName}
        </h2>
        <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
          Selecciona una categoría para filtrar los documentos.
        </p>
      </div>

      <div className="pills-container">
        {datos.secciones.map((s) => (
          <button 
            key={s.clave} 
            className={`pill-btn ${categoriaActiva === s.clave ? 'active' : ''}`}
            onClick={() => setCategoriaActiva(categoriaActiva === s.clave ? null : s.clave)}
          >
            <i className={iconForSection(s.clave)}></i> {s.nombre}
            <span style={{ background: categoriaActiva === s.clave ? 'rgba(255,255,255,0.2)' : '#f1f2f6', padding: '2px 8px', borderRadius: '12px', fontSize: '0.8rem', marginLeft: '5px' }}>
              {s.documentos.length}
            </span>
          </button>
        ))}
      </div>

      <div ref={mapRef} className="map-wrapper"></div>

      <h3 style={{ fontSize: '1.4rem', color: 'var(--primary-color)', marginTop: '3rem' }}>
        Archivos Fuente {categoriaActiva && `de ${datos.secciones.find(s=>s.clave===categoriaActiva)?.nombre}`}
      </h3>
      
      {docsToShow.length === 0 ? (
        <p style={{ color: 'var(--text-muted)', marginTop: '1rem' }}>No hay documentos en esta sección.</p>
      ) : (
        <div className="docs-carousel-container">
          {docsToShow.map(d => (
            <div key={d.id} className="doc-card">
              <div>
                <h4>{d.titulo}</h4>
                <p><i className="fa-regular fa-calendar" style={{marginRight:'5px'}}></i> {d.anio} {d.estatus !== 'listo' && `(${d.estatus})`}</p>
              </div>
              <button onClick={() => onDocumento(d.id)}>
                Ver detalle <i className="fa-solid fa-arrow-right"></i>
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="cta-container">
        <button className="cta-btn" onClick={() => alert("Aquí se abriría la vista completa de categorías y años.")}>
          Ver todos los archivos
        </button>
      </div>

      <Concentracion filtros={filtros} locationName={locationName} />
      
      <Suscripcion lugar={lugar} />
      
      <Chatbot filtros={filtros} onVerPagina={onVerPagina} />
    </div>
  );
}
