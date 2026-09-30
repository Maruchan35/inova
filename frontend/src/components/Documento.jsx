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
    <>
      <nav className="migas">
        <button className="btn-link" onClick={() => onIr('/')}>Inicio</button> /{' '}
        <button className="btn-link" onClick={() => onIr(`/estado/${doc.estado.id}`)}>{doc.estado.nombre}</button>
        {doc.municipio && <> / <button className="btn-link" onClick={() => onIr(`/municipio/${doc.municipio.id}`)}>{doc.municipio.nombre}</button></>}
      </nav>
      <div className="doc-detail-header" style={{ marginTop: '1rem' }}>
        <p className="tenue" style={{ marginBottom: '10px' }}>
          {doc.seccion.nombre} · {doc.municipio?.nombre ?? doc.estado.nombre} · {doc.anio}
        </p>
        <h2>{doc.titulo}</h2>
      </div>

      {(fuente.dependencia || fuente.url_fuente || doc.pdf_url) && (
        <div className="doc-fuente">
          <strong>Documento oficial</strong>
          {fuente.dependencia && <span>{fuente.dependencia}</span>}
          {fuente.fecha_publicacion && <span>Publicado el {fuente.fecha_publicacion}</span>}
          {doc.pdf_url && (
            <a href={doc.pdf_url} target="_blank" rel="noopener noreferrer"><i className="fa-regular fa-file-pdf"></i> Abrir el PDF original</a>
          )}
          {fuente.url_fuente && (
            <a href={fuente.url_fuente} target="_blank" rel="noopener noreferrer"><i className="fa-solid fa-arrow-up-right-from-square"></i> Portal oficial</a>
          )}
        </div>
      )}

      {doc.estatus !== 'listo' ? (
        <div style={{ padding: '2rem', background: 'white', borderRadius: '12px', textAlign: 'center' }}>
          <i className="fa-solid fa-spinner fa-spin fa-2x" style={{ color: 'var(--primary-color)', marginBottom: '1rem' }}></i>
          <p style={{ fontSize: '1.2rem', color: 'var(--primary-color)', fontWeight: 500 }}>Procesando documento...</p>
          <p className="tenue">La IA está analizando y extrayendo los datos importantes ({doc.estatus}).</p>
        </div>
      ) : (
        <>
          <div className="doc-resumen">
            <strong>Resumen del documento:</strong><br/><br/>
            {doc.resumen}
          </div>

          <h3 style={{ color: 'var(--primary-color)', marginBottom: '1rem', fontSize: '1.5rem' }}>Lo más importante</h3>
          <ul className="doc-puntos">
            {doc.puntos_clave.map((p, i) => (
              <li key={i}>
                <span style={{ paddingRight: '1rem', lineHeight: '1.5' }}>{p.texto}</span>
                {p.pagina && (
                  <button onClick={() => onVerPagina(doc.id, p.pagina)}>
                    pág. {p.pagina}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
