import { useState, useEffect, useRef } from 'react';
import { api } from '../api.js';
import Concentracion from './Concentracion.jsx';
import Suscripcion from './Suscripcion.jsx';

// Coordenadas base por defecto si no hay
const DEFAULT_CENTER = [23.6345, -102.5528]; // México

export default function Lugar({ lugar, onElegir, onDocumento, onVerPagina, onContexto, onIr }) {
  const [datos, setDatos] = useState(null);
  const [categoriaActiva, setCategoriaActiva] = useState(null);
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersLayer = useRef(null);
  const docsSectionRef = useRef(null);

  useEffect(() => {
    const pedir = lugar.tipo === 'estado' ? api.estado : api.municipio;
    pedir(lugar.id).then(d => {
      setDatos(d);
      onContexto?.(d.nombre + (d.estado ? `, ${d.estado.nombre}` : ''));
      setCategoriaActiva(null);
    }).catch(() => setDatos(null));
  }, [lugar.tipo, lugar.id]);

  const seleccionarCategoria = (clave) => {
    const nueva = categoriaActiva === clave ? null : clave;
    setCategoriaActiva(nueva);
    if (nueva && docsSectionRef.current) {
      setTimeout(() => {
        docsSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);
    }
  };

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

  const [filtroTexto, setFiltroTexto] = useState('');
  const [origenDoc, setOrigenDoc] = useState('todos'); // 'todos', 'municipales', 'estatales'

  if (!datos) return <div style={{ textAlign: 'center', marginTop: '4rem' }}>Cargando información...</div>;

  const filtros = lugar.tipo === 'estado' ? { estado_id: datos.id } : { municipio_id: datos.id };
  const locationName = datos.nombre + (datos.estado ? `, ${datos.estado.nombre}` : '');

  // 1. Recopilar documentos municipales y estatales aplicables
  const esMunicipio = lugar.tipo === 'municipio';
  let todosDocs = [];

  // Documentos propios
  datos.secciones.forEach(s => {
    s.documentos.forEach(d => {
      todosDocs.push({ ...d, seccionClave: s.clave, seccionNombre: s.nombre, esEstatal: false, origenTexto: 'Municipal' });
    });
  });

  // Documentos estatales aplicables al municipio (si aplica)
  if (esMunicipio && datos.documentos_estatales) {
    datos.documentos_estatales.forEach(s => {
      s.documentos.forEach(d => {
        todosDocs.push({
          ...d,
          seccionClave: s.clave,
          seccionNombre: s.nombre,
          esEstatal: true,
          origenTexto: `Estatal (${datos.estado?.nombre || 'Gobierno del Estado'})`
        });
      });
    });
  }

  // 2. Filtrado por categoría activa, origen (municipal/estatal) y búsqueda por texto
  let docsToShow = todosDocs;
  if (categoriaActiva) {
    docsToShow = docsToShow.filter(d => d.seccionClave === categoriaActiva);
  }
  if (esMunicipio && origenDoc === 'municipales') {
    docsToShow = docsToShow.filter(d => !d.esEstatal);
  } else if (esMunicipio && origenDoc === 'estatales') {
    docsToShow = docsToShow.filter(d => d.esEstatal);
  }
  if (filtroTexto.trim()) {
    const q = filtroTexto.trim().toLowerCase();
    docsToShow = docsToShow.filter(d => 
      (d.titulo && d.titulo.toLowerCase().includes(q)) ||
      (d.dependencia && d.dependencia.toLowerCase().includes(q)) ||
      (d.anio && String(d.anio).includes(q)) ||
      (d.seccionNombre && d.seccionNombre.toLowerCase().includes(q))
    );
  }

  const iconForSection = (clave) => {
    const icons = {
      informes: 'fa-regular fa-file-lines',
      presupuesto: 'fa-regular fa-money-bill-1',
      obras: 'fa-solid fa-person-digging',
      actas: 'fa-solid fa-file-signature',
      contratos: 'fa-regular fa-handshake'
    };
    return icons[clave] || 'fa-regular fa-folder';
  };

  // Conteo total para píldoras
  const conteoSeccion = (clave) => {
    return todosDocs.filter(d => d.seccionClave === clave).length;
  };

  return (
    <div className="lugar-container">
      <nav className="migas">
        <button className="btn-link" onClick={() => onIr('/')}>Inicio</button>
        {datos.estado && <> / <button className="btn-link" onClick={() => onElegir({ tipo: 'estado', id: datos.estado.id })}>{datos.estado.nombre}</button></>}
        {' '}/ {datos.nombre}
      </nav>
      <div className="lugar-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <i className="fa-solid fa-map-location-dot" style={{ color: 'var(--accent-color)' }}></i> {locationName}
        </h2>
        <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
          {esMunicipio 
            ? `Consulta los documentos oficiales de ${datos.nombre} y los decretos estatales de ${datos.estado?.nombre} aplicables.`
            : `Consulta los decretos, presupuestos e informes oficiales de ${datos.nombre}.`}
        </p>
      </div>

      <div className="pills-container">
        {datos.secciones.map((s) => {
          const totalSec = conteoSeccion(s.clave);
          return (
            <button 
              key={s.clave} 
              className={`pill-btn ${categoriaActiva === s.clave ? 'active' : ''}`}
              onClick={() => seleccionarCategoria(s.clave)}
            >
              <i className={iconForSection(s.clave)}></i> {s.nombre}
              <span style={{ background: categoriaActiva === s.clave ? 'rgba(255,255,255,0.2)' : '#f1f2f6', padding: '2px 8px', borderRadius: '12px', fontSize: '0.8rem', marginLeft: '5px' }}>
                {totalSec}
              </span>
            </button>
          );
        })}
      </div>

      <div ref={mapRef} className="map-wrapper"></div>

      <div 
        ref={docsSectionRef} 
        id="seccion-documentos" 
        style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          flexWrap: 'wrap', 
          gap: '1rem', 
          marginTop: '2rem',
          scrollMarginTop: '90px'
        }}
      >
        <h3 style={{ fontSize: '1.4rem', color: 'var(--primary-color)', margin: 0 }}>
          Archivos Disponibles {categoriaActiva && `de ${datos.secciones.find(s=>s.clave===categoriaActiva)?.nombre}`}
          <span style={{ fontSize: '1rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: '10px' }}>
            ({docsToShow.length} {docsToShow.length === 1 ? 'documento' : 'documentos'})
          </span>
        </h3>

        {esMunicipio && (
          <div style={{ display: 'flex', gap: '8px' }}>
            <button 
              className={`pill-btn ${origenDoc === 'todos' ? 'active' : ''}`}
              style={{ padding: '6px 14px', fontSize: '0.85rem' }}
              onClick={() => setOrigenDoc('todos')}
            >
              Todos ({todosDocs.length})
            </button>
            <button 
              className={`pill-btn ${origenDoc === 'municipales' ? 'active' : ''}`}
              style={{ padding: '6px 14px', fontSize: '0.85rem' }}
              onClick={() => setOrigenDoc('municipales')}
            >
              Municipales ({todosDocs.filter(d => !d.esEstatal).length})
            </button>
            <button 
              className={`pill-btn ${origenDoc === 'estatales' ? 'active' : ''}`}
              style={{ padding: '6px 14px', fontSize: '0.85rem' }}
              onClick={() => setOrigenDoc('estatales')}
            >
              Estatales aplicables ({todosDocs.filter(d => d.esEstatal).length})
            </button>
          </div>
        )}
      </div>

      <div className="search-bar" style={{ maxWidth: '420px', margin: '1rem 0 2rem 0', boxShadow: '0 4px 15px rgba(0,0,0,0.05)' }}>
        <i className="fa-solid fa-magnifying-glass" style={{ color: '#aaa', marginLeft: '12px' }}></i>
        <input 
          type="text" 
          value={filtroTexto} 
          onChange={e => setFiltroTexto(e.target.value)} 
          placeholder="Filtrar por título, año, secretaría..."
        />
        {filtroTexto && (
          <button type="button" onClick={() => setFiltroTexto('')} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 12px', color: '#888' }}>
            <i className="fa-solid fa-xmark"></i>
          </button>
        )}
      </div>
      
      {docsToShow.length === 0 ? (
        <div style={{ padding: '2.5rem', background: 'white', borderRadius: '12px', textAlign: 'center', border: '1px dashed #ddd', margin: '1.5rem 0' }}>
          <i className="fa-regular fa-folder-open fa-2x" style={{ color: '#bbb', marginBottom: '0.8rem' }}></i>
          <p style={{ color: 'var(--text-muted)' }}>
            No se encontraron documentos {categoriaActiva ? `en ${datos.secciones.find(s=>s.clave===categoriaActiva)?.nombre}` : ''} con esos filtros.
          </p>
          {(categoriaActiva || filtroTexto || origenDoc !== 'todos') && (
            <button className="btn-link" style={{ marginTop: '0.8rem', color: 'var(--accent-color)', fontWeight: 600 }} onClick={() => { setCategoriaActiva(null); setFiltroTexto(''); setOrigenDoc('todos'); }}>
              Restablecer filtros y ver todos ({todosDocs.length})
            </button>
          )}
        </div>
      ) : (
        <div className="docs-carousel-container">
          {docsToShow.map(d => (
            <div key={d.id} className="doc-card" style={{ borderLeft: d.esEstatal ? '4px solid #6c5ce7' : '4px solid var(--accent-color)' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '5px' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '2px 8px', borderRadius: '6px', background: d.esEstatal ? '#f0eeff' : '#eaf8f0', color: d.esEstatal ? '#6c5ce7' : '#10b981' }}>
                    {d.origenTexto}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {d.seccionNombre}
                  </span>
                </div>
                <h4>{d.titulo}</h4>
                <p>
                  <i className="fa-regular fa-calendar" style={{ marginRight: '5px' }}></i> {d.anio || 'Año no especificado'}
                  {d.total_paginas > 0 && <span style={{ marginLeft: '10px' }}><i className="fa-regular fa-file" style={{ marginRight: '4px' }}></i> {d.total_paginas} págs</span>}
                </p>
                {d.dependencia && (
                  <p style={{ fontSize: '0.8rem', color: '#777', marginTop: '4px' }}>
                    <i className="fa-solid fa-building-columns" style={{ marginRight: '5px' }}></i> {d.dependencia}
                  </p>
                )}
              </div>
              <button onClick={() => onDocumento(d.id)} style={{ marginTop: '1rem' }}>
                Ver detalle <i className="fa-solid fa-arrow-right"></i>
              </button>
            </div>
          ))}
        </div>
      )}

      {categoriaActiva && (
        <div className="cta-container">
          <button className="cta-btn" onClick={() => setCategoriaActiva(null)}>
            Ver todas las secciones
          </button>
        </div>
      )}

      {datos.municipios?.length > 0 && (
        <section className="municipios-lista">
          <h3>Municipios de {datos.nombre}</h3>
          <div>
            {datos.municipios.map(m => (
              <button key={m.id} className="pill-btn" onClick={() => onElegir({ tipo: 'municipio', id: m.id })}>{m.nombre}</button>
            ))}
          </div>
        </section>
      )}

      <Concentracion filtros={filtros} locationName={locationName} />
      
      <Suscripcion lugar={lugar} />
    </div>
  );
}
