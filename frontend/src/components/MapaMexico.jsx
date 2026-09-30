import { useState, useMemo } from 'react';
import { ComposableMap, Geographies, Geography, Marker } from 'react-simple-maps';

// GeoJSON local servido por Vite desde /public/mexico.json (100% confiable, sin 404 ni dependencia de red)
const geoUrl = "/mexico.json";

function normalizar(str) {
  return str ? str.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim() : "";
}

export default function MapaMexico({ estados = [], onElegirEstado }) {
  const [tooltip, setTooltip] = useState(null);
  const [estadoHover, setEstadoHover] = useState(null);

  // Mapeo rápido de nombres normalizados a objetos de estado del backend
  const estadosMap = useMemo(() => {
    const mapa = new Map();
    estados.forEach(e => {
      mapa.set(normalizar(e.nombre), e);
      // Aliases comunes para coincidencias seguras
      if (e.nombre.includes('México') && !e.nombre.includes('Ciudad')) {
        mapa.set('estado de mexico', e);
        mapa.set('mexico', e);
      }
      if (e.nombre.includes('Ciudad de México')) {
        mapa.set('distrito federal', e);
        mapa.set('cdmx', e);
      }
      if (e.nombre.includes('Coahuila')) mapa.set('coahuila', e);
      if (e.nombre.includes('Michoacán')) mapa.set('michoacan', e);
      if (e.nombre.includes('Veracruz')) mapa.set('veracruz', e);
    });
    return mapa;
  }, [estados]);

  // Proyección Mercator centrada de forma balanceada en toda la República Mexicana
  const proyeccion = {
    scale: 1100,
    center: [-102, 23.6]
  };

  const encontrarEstado = (geoName) => {
    const norm = normalizar(geoName);
    if (estadosMap.has(norm)) return estadosMap.get(norm);
    for (const [k, v] of estadosMap.entries()) {
      if (norm.includes(k) || k.includes(norm)) return v;
    }
    return null;
  };

  return (
    <div className="mapa-mexico-container">
      {/* Tooltip flotante al pasar el mouse por un estado o pin */}
      {tooltip && (
        <div 
          className="mapa-tooltip" 
          style={{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }}
        >
          <div className="mapa-tooltip-title">
            <i className="fa-solid fa-location-dot" style={{ color: 'var(--accent-color)', marginRight: '6px' }}></i>
            {tooltip.nombre}
          </div>
          <div className="mapa-tooltip-sub">
            {tooltip.municipios > 0 ? `${tooltip.municipios} municipios indexados` : 'Entidad federativa'}
          </div>
          <div className="mapa-tooltip-cta">
            Clic para ver documentos oficiales <i className="fa-solid fa-arrow-right"></i>
          </div>
        </div>
      )}

      <ComposableMap 
        projection="geoMercator" 
        projectionConfig={proyeccion} 
        width={800} 
        height={460}
        style={{ width: '100%', height: 'auto', maxHeight: '520px' }}
      >
        {/* Polígonos de los 32 Estados */}
        <Geographies geography={geoUrl}>
          {({ geographies }) =>
            geographies.map((geo) => {
              const geoName = geo.properties.name;
              const estadoMatch = encontrarEstado(geoName);
              const isHovered = estadoHover && estadoMatch && estadoHover.id === estadoMatch.id;

              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill={isHovered ? "#93c5fd" : "#e2e8f0"}
                  stroke="#ffffff"
                  strokeWidth={1}
                  onMouseEnter={(evt) => {
                    if (estadoMatch) {
                      setEstadoHover(estadoMatch);
                      const rect = evt.currentTarget.getBoundingClientRect();
                      setTooltip({
                        x: evt.clientX - 100,
                        y: evt.clientY - 75,
                        nombre: estadoMatch.nombre,
                        municipios: estadoMatch.municipios?.length || 0
                      });
                    }
                  }}
                  onMouseMove={(evt) => {
                    if (tooltip) {
                      setTooltip(prev => prev ? ({ ...prev, x: evt.clientX - 100, y: evt.clientY - 75 }) : null);
                    }
                  }}
                  onMouseLeave={() => {
                    setEstadoHover(null);
                    setTooltip(null);
                  }}
                  onClick={() => {
                    if (estadoMatch) {
                      onElegirEstado({ tipo: 'estado', id: estadoMatch.id });
                    }
                  }}
                  style={{
                    default: { outline: 'none', transition: 'fill 0.2s ease', cursor: estadoMatch ? 'pointer' : 'default' },
                    hover: { fill: '#93c5fd', outline: 'none', cursor: 'pointer' },
                    pressed: { fill: '#60a5fa', outline: 'none' }
                  }}
                />
              );
            })
          }
        </Geographies>

        {/* Pines Interactivos sobre cada Estado */}
        {estados && estados.map((estado) => {
          if (!estado.latitud || !estado.longitud) return null;
          const isHovered = estadoHover && estadoHover.id === estado.id;

          return (
            <Marker 
              key={`pin-${estado.id}`} 
              coordinates={[estado.longitud, estado.latitud]} 
              onClick={() => onElegirEstado({ tipo: 'estado', id: estado.id })}
              onMouseEnter={(evt) => {
                setEstadoHover(estado);
                setTooltip({
                  x: evt.clientX - 100,
                  y: evt.clientY - 75,
                  nombre: estado.nombre,
                  municipios: estado.municipios?.length || 0
                });
              }}
              onMouseMove={(evt) => {
                if (tooltip) {
                  setTooltip(prev => prev ? ({ ...prev, x: evt.clientX - 100, y: evt.clientY - 75 }) : null);
                }
              }}
              onMouseLeave={() => {
                setEstadoHover(null);
                setTooltip(null);
              }}
              style={{ cursor: 'pointer' }}
            >
              {/* Círculo de pulso exterior */}
              <circle
                r={isHovered ? 9 : 6}
                fill={isHovered ? "rgba(37, 99, 235, 0.4)" : "rgba(74, 144, 226, 0.35)"}
                className="mapa-pin-pulse"
              />
              {/* Punto central del pin */}
              <circle 
                r={isHovered ? 5 : 3.5} 
                fill={isHovered ? "#1d4ed8" : "var(--accent-color)"} 
                stroke="#ffffff" 
                strokeWidth={1.5} 
              />
            </Marker>
          );
        })}
      </ComposableMap>

      <div className="mapa-mexico-footer-hint">
        <span>
          <i className="fa-solid fa-circle-info" style={{ color: 'var(--accent-color)', marginRight: '6px' }}></i>
          Pasa el cursor por cualquier estado o pin y haz clic para entrar directamente a su expediente.
        </span>
      </div>
    </div>
  );
}
