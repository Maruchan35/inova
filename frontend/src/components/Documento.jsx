import { useState, useEffect } from 'react';
import { api } from '../api.js';
import Chatbot from './Chatbot.jsx';

export default function Documento({ id, onVerPagina }) {
  const [doc, setDoc] = useState(null);

  useEffect(() => {
    let interval;
    const fetchDoc = async () => {
      try {
        const d = await api.documento(id);
        setDoc(d);
        if (d.estatus !== 'listo' && d.estatus !== 'error') {
          interval = setTimeout(fetchDoc, 2000); // Polling every 2s
        }
      } catch (err) {
        setDoc(null);
      }
    };
    fetchDoc();
    return () => clearTimeout(interval);
  }, [id]);

  if (!doc) return <div style={{ textAlign: 'center', marginTop: '4rem' }}>Cargando documento...</div>;

  return (
    <>
      <div className="doc-detail-header" style={{ marginTop: '2rem' }}>
        <p className="tenue" style={{ marginBottom: '10px' }}>
          {doc.seccion.nombre} · {doc.municipio?.nombre ?? doc.estado.nombre} · {doc.anio}
        </p>
        <h2>{doc.titulo}</h2>
      </div>

      {doc.estatus !== 'listo' ? (
        <div style={{ padding: '2rem', background: 'white', borderRadius: '12px', textAlign: 'center' }}>
          <i className="fa-solid fa-spinner fa-spin fa-2x" style={{ color: 'var(--royal-blue)', marginBottom: '1rem' }}></i>
          <p style={{ fontSize: '1.2rem', color: 'var(--royal-blue)' }}>Procesando documento...</p>
          <p className="tenue">La IA está analizando y extrayendo los datos importantes ({doc.estatus}).</p>
        </div>
      ) : (
        <>
          <div className="doc-resumen">
            <strong>Resumen del documento:</strong><br/><br/>
            {doc.resumen}
          </div>

          <h3 style={{ color: 'var(--royal-blue)', marginBottom: '1rem', fontSize: '1.5rem' }}>Lo más importante</h3>
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

      {doc.estatus === 'listo' && <Chatbot filtros={{ documento_id: doc.id }} onVerPagina={onVerPagina} />}
    </>
  );
}
