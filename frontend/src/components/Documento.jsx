import { useState, useEffect } from 'react';
import { api } from '../api.js';

export default function Documento({ id, onVerPagina, onIr, onContexto }) {
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let interval;
    const fetchDoc = async () => {
      try {
        const d = await api.documento(id);
        setDoc(d);
        setError(null);
        onContexto?.(d.titulo);
        if (d.estatus !== 'listo' && d.estatus !== 'error') {
          interval = setTimeout(fetchDoc, 2000); // Polling every 2s
        }
      } catch (err) {
        setDoc(null);
        setError(err.message);
      }
    };
    fetchDoc();
    return () => clearTimeout(interval);
  }, [id]);

  if (error) return <div style={{ textAlign: 'center', marginTop: '4rem' }}>No pudimos abrir este documento: {error}</div>;
  if (!doc) return <div style={{ textAlign: 'center', marginTop: '4rem' }}>Cargando documento...</div>;
  const fuente = doc.fuente || {};

  return (
    <div className="doc-container">
      <nav className="migas">
        <button className="btn-link" onClick={() => onIr('/')}>Inicio</button> /{' '}
        <button className="btn-link" onClick={() => onIr(`/estado/${doc.estado.id}`)}>{doc.estado.nombre}</button>
        {doc.municipio && <> / <button className="btn-link" onClick={() => onIr(`/municipio/${doc.municipio.id}`)}>{doc.municipio.nombre}</button></>}
      </nav>

      <div className="doc-detail-header">
        <div className="doc-meta-pills">
          <span className="doc-pill-tag">
            <i className="fa-regular fa-folder" style={{ color: 'var(--accent-color)' }}></i> {doc.seccion.nombre}
          </span>
          <span className="doc-pill-tag">
            <i className="fa-solid fa-location-dot" style={{ color: '#10b981' }}></i> {doc.municipio?.nombre ? `${doc.municipio.nombre}, ${doc.estado.nombre}` : doc.estado.nombre}
          </span>
          {doc.anio && (
            <span className="doc-pill-tag">
              <i className="fa-regular fa-calendar"></i> {doc.anio}
            </span>
          )}
          {doc.total_paginas > 0 && (
            <span className="doc-pill-tag">
              <i className="fa-regular fa-file"></i> {doc.total_paginas} págs
            </span>
          )}
        </div>
        <h2 className="doc-main-title">{doc.titulo}</h2>
      </div>

      {(fuente.dependencia || fuente.url_fuente || doc.pdf_url) && (
        <div className="doc-fuente-card">
          <div className="doc-fuente-info">
            <div className="doc-fuente-icon">
              <i className="fa-solid fa-shield-halved"></i>
            </div>
            <div>
              <strong style={{ fontSize: '0.95rem', color: 'var(--primary-color)' }}>Fuente Oficial del Documento</strong>
              {fuente.dependencia && <p className="doc-fuente-dep">{fuente.dependencia}</p>}
              {fuente.fecha_publicacion && <span className="doc-fuente-fecha">Publicado: {fuente.fecha_publicacion}</span>}
            </div>
          </div>
          <div className="doc-fuente-actions">
            {doc.pdf_url && (
              <a href={doc.pdf_url} target="_blank" rel="noopener noreferrer" className="btn-doc-pdf">
                <i className="fa-regular fa-file-pdf"></i> Abrir PDF original
              </a>
            )}
            {fuente.url_fuente && (
              <a href={fuente.url_fuente} target="_blank" rel="noopener noreferrer" className="btn-doc-web">
                <i className="fa-solid fa-arrow-up-right-from-square"></i> Portal oficial
              </a>
            )}
          </div>
        </div>
      )}

      {doc.estatus !== 'listo' ? (
        <div style={{ padding: '2.5rem', background: 'white', borderRadius: '12px', textAlign: 'center', boxShadow: 'var(--card-shadow)' }}>
          <i className="fa-solid fa-spinner fa-spin fa-2x" style={{ color: 'var(--primary-color)', marginBottom: '1rem' }}></i>
          <p style={{ fontSize: '1.2rem', color: 'var(--primary-color)', fontWeight: 500 }}>Procesando documento...</p>
          <p className="tenue">La IA está analizando y extrayendo los datos importantes ({doc.estatus}).</p>
        </div>
      ) : (
        <>
          <div className="doc-section-card">
            <h3 className="doc-section-title">
              <i className="fa-solid fa-wand-magic-sparkles" style={{ color: 'var(--accent-color)' }}></i> Resumen Ejecutivo
            </h3>
            <div className="doc-resumen-body">
              {doc.resumen}
            </div>
          </div>

          <div className="doc-section-card" style={{ marginTop: '2rem' }}>
            <h3 className="doc-section-title">
              <i className="fa-solid fa-list-check" style={{ color: 'var(--primary-color)' }}></i> Puntos Clave Extraídos
            </h3>
            <ul className="doc-puntos-list">
              {doc.puntos_clave.map((p, i) => (
                <li key={i} className="doc-punto-item">
                  <div className="doc-punto-bullet">{i + 1}</div>
                  <div className="doc-punto-content">
                    <p className="doc-punto-text">{p.texto}</p>
                  </div>
                  {p.pagina && (
                    <button className="btn-punto-pag" onClick={() => onVerPagina(doc.id, p.pagina)} title="Ver página original">
                      <i className="fa-regular fa-file-lines"></i> Pág. {p.pagina}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
