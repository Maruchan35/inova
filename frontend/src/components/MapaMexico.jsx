import React, { useState, useEffect } from 'react';
import { ComposableMap, Geographies, Geography, Marker } from 'react-simple-maps';

const geoUrl = "https://raw.githubusercontent.com/deldersveld/topojson/master/countries/mexico/mexico-states.json";

export default function MapaMexico({ estados, onElegirEstado }) {
  // Configuración de proyección centrada en México
  const proyeccion = {
    scale: 1200,
    center: [-102, 24] // Coordenadas centrales aproximadas de México
  };

  return (
    <div style={{ width: '100%', maxWidth: '800px', margin: '0 auto' }}>
      <ComposableMap projection="geoMercator" projectionConfig={proyeccion} style={{ width: '100%', height: 'auto' }}>
        <Geographies geography={geoUrl}>
          {({ geographies }) =>
            geographies.map((geo) => (
              <Geography
                key={geo.rsmKey}
                geography={geo}
                fill="#e0e0e0"
                stroke="#ffffff"
                strokeWidth={0.5}
                style={{
                  default: { outline: 'none' },
                  hover: { fill: '#d0d0d0', outline: 'none' },
                  pressed: { outline: 'none' }
                }}
              />
            ))
          }
        </Geographies>

        {estados && estados.map((estado) => {
          // Asegurarnos de que tenga latitud y longitud antes de poner un pin
          if (estado.latitud && estado.longitud) {
            return (
              <Marker 
                key={estado.id} 
                coordinates={[estado.longitud, estado.latitud]} 
                onClick={() => onElegirEstado({ tipo: 'estado', id: estado.id })}
                style={{ cursor: 'pointer' }}
              >
                <circle r={5} fill="var(--accent-color)" stroke="#fff" strokeWidth={1.5} />
                <text
                  textAnchor="middle"
                  y={-8}
                  style={{ fontFamily: "system-ui", fill: "#5D5A6D", fontSize: "10px", pointerEvents: "none" }}
                >
                  {/* Solo mostramos el nombre si queremos, pero los pines ya son interactivos */}
                </text>
              </Marker>
            );
          }
          return null;
        })}
      </ComposableMap>
    </div>
  );
}
