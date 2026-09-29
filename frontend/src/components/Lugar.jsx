import { useState, useEffect } from 'react';
import { api } from '../api.js';
import Concentracion from './Concentracion.jsx';
import Chatbot from './Chatbot.jsx';

export default function Lugar({ lugar, onElegir, onDocumento, onVerPagina }) {
  const [datos, setDatos] = useState(null);
  
  useEffect(() => {
    const pedir = lugar.tipo === 'estado' ? api.estado : api.municipio;
    pedir(lugar.id).then(setDatos).catch(() => setDatos(null));
  }, [lugar.tipo, lugar.id]);
  
  if (!datos) return <div style={{ textAlign: 'center', marginTop: '4rem' }}>Cargando informaciÃ³n...</div>;

  const filtros = lugar.tipo === 'estado' ? { estado_id: datos.id } : { municipio_id: datos.id };
  const locationName = datos.nombre + (datos.estado ? `, ${datos.estado.nombre}` : '');

  const iconForSection = (clave) => {
    const icons = {
      informes: 'fa-solid fa-file-contract',
      presupuesto: 'fa-solid fa-file-invoice-dollar',
      obras: 'fa-solid fa-person-digging',
      actas: 'fa-solid fa-gavel',
      contratos: 'fa-solid fa-file-signature'
    };
    return icons[clave] || 'fa-solid fa-folder';
  };

  return (
    <>
      <div className="dynamic-title-area" style={{ marginTop: '2rem' }}>
        Mostrando documentos y datos para: <span className="highlight-location">{locationName}</span>
      </div>

      <div className="section-grid">
        {datos.secciones.map((s) => (
          <div className="section-card" key={s.clave}>
            <h3>
              {s.nombre}
              <i className={iconForSection(s.clave)} style={{ color: 'var(--platinum)' }}></i>
            </h3>
            {s.documentos.length === 0 ? (
              <p className="tenue" style={{ marginTop: '10px' }}>Sin documentos todavÃ­a.</p>
            ) : (
              <ul className="document-list" style={{ marginTop: '1rem' }}>
                {s.documentos.map((d) => (
                  <li key={d.id} className="document-item">
                    <button className="document-title" onClick={() => onDocumento(d.id)}>
                      {d.titulo}
                    </button>
                    <span className="document-meta">
                      {d.anio} {d.estatus !== 'listo' && `(${d.estatus})`}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      {datos.municipios && datos.municipios.length > 0 && (
        <section style={{ marginBottom: '4rem', padding: '2rem', background: 'white', borderRadius: '20px' }}>
          <h3 style={{ color: 'var(--royal-blue)', marginBottom: '1rem' }}>Municipios de {datos.nombre}</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            {datos.municipios.map((m) => (
              <button 
                key={m.id} 
                className="btn-link" 
                style={{ padding: '8px 16px', background: 'var(--swan-wing)', borderRadius: '20px' }}
                onClick={() => onElegir({ tipo: 'municipio', id: m.id })}
              >
                {m.nombre}
              </button>
            ))}
          </div>
        </section>
      )}

      <Concentracion filtros={filtros} locationName={locationName} />
      
      <Chatbot filtros={filtros} onVerPagina={onVerPagina} />
    </>
  );
}
