import { useState, useEffect, useRef } from 'react';
import { api } from '../api.js';
import Concentracion from './Concentracion.jsx';
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
      
      // Clean map tile (Voyager without labels or clean standard)
      window.L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap'
      }).addTo(mapInstance.current);
      
      markersLayer.current = window.L.layerGroup().addTo(mapInstance.current);
    }

    // Simularemos el centro basado en un hash del nombre del lugar para no mover el mapa al azar
    const hash = datos.nombre.length; 
    // México center +- some degrees
    const centerLat = 20 + (hash % 10) * 0.5;
    const centerLng = -100 + (hash % 10) * 0.5;
    
    mapInstance.current.flyTo([centerLat, centerLng], 12, { duration: 1.5 });
    
    // Clear markers when data changes
    if (markersLayer.current) markersLayer.current.clearLayers();
    
    // We will save the center to state so we can render pins
    return () => {
      // Cleanup map on unmount
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    }
  }, [datos]);

  // Render markers when active category changes
  useEffect(() => {
    if (!mapInstance.current || !markersLayer.current || !datos) return;
    
    markersLayer.current.clearLayers();
    if (!categoriaActiva) return;

    const seccion = datos.secciones.find(s => s.clave === categoriaActiva);
    if (!seccion || seccion.documentos.length === 0) return;

    const center = mapInstance.current.getCenter();
    const iconForSection = (clave) => {
      const icons = {
        informes: 'fa-regular fa-file-contract',
        presupuesto: 'fa-regular fa-file-invoice-dollar',
        obras: 'fa-solid fa-person-digging',
        actas: 'fa-regular fa-gavel',
        contratos: 'fa-regular fa-file-signature'
      };
      return icons[clave] || 'fa-regular fa-folder';
    };

    const iconClass = iconForSection(categoriaActiva);
    const markerIcon = window.L.divIcon({
        className: 'custom-icon',
        html: `<div style="width: 38px; height: 38px; background-color: var(--primary-color); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; box-shadow: 0 4px 10px rgba(0,0,0,0.3); border: 2px solid white;">
                <i class="${iconClass}"></i></div>`,
        iconSize: [38, 38], iconAnchor: [19, 38], popupAnchor: [0, -38]
    });

    seccion.documentos.forEach((doc, idx) => {
      // Offset aleatorio pero determinista
      const latOffset = (Math.sin(idx * 123) * 0.02);
      const lngOffset = (Math.cos(idx * 321) * 0.02);
      
      const popup = `<div style="text-align:center; padding:5px; font-family: 'Inter', sans-serif;">
                      <h4 style="color: #1a1a2e; margin:0 0 5px 0; font-size: 1rem;">${doc.titulo}</h4>
                      <span style="font-size:12px; color:#888;">${doc.anio}</span>
                     </div>`;
      window.L.marker([center.lat + latOffset, center.lng + lngOffset], { icon: markerIcon })
        .bindPopup(popup)
        .addTo(markersLayer.current);
    });
    
  }, [categoriaActiva, datos]);


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
      actas: 'fa-regular fa-file-signature',
      contratos: 'fa-regular fa-handshake'
    };
    return icons[clave] || 'fa-regular fa-folder';
  };

  return (
    <div className="lugar-container">
      <div className="lugar-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <i className="fa-regular fa-map-location-dot" style={{ color: 'var(--accent-color)' }}></i> {locationName}
        </h2>
        <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
          Selecciona una categoría para visualizar los documentos en el mapa.
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
                Ver detalle <i className="fa-regular fa-arrow-right"></i>
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
    </div>
  );
}
