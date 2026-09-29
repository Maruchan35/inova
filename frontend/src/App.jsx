import { useState } from 'react';
import { api } from './api.js';
import Portada from './components/Portada.jsx';
import Lugar from './components/Lugar.jsx';
import Documento from './components/Documento.jsx';
import PaginaModal from './components/PaginaModal.jsx';

export default function App() {
  const [lugar, setLugar] = useState(null);
  const [documentoId, setDocumentoId] = useState(null);
  const [pagina, setPagina] = useState(null);

  const verPagina = (docId, numero) => api.pagina(docId, numero).then(setPagina);

  return (
    <>
      <header>
        <div className="logo">
          <i className="fa-solid fa-landmark-dome"></i> CabildoAbierto
        </div>
        <nav>
          <ul>
            <li>
              <button className="btn-link" onClick={() => { setLugar(null); setDocumentoId(null); }}>
                Inicio
              </button>
            </li>
            {(lugar || documentoId) && (
              <li>
                <button className="btn-link" style={{ fontWeight: 700 }} onClick={() => (documentoId ? setDocumentoId(null) : setLugar(null))}>
                  <i className="fa-solid fa-arrow-left"></i> Volver atrás
                </button>
              </li>
            )}
          </ul>
        </nav>
      </header>

      <PaginaModal pagina={pagina} onClose={() => setPagina(null)} />

      <main>
        {documentoId ? (
          <Documento id={documentoId} onVerPagina={verPagina} />
        ) : lugar ? (
          <Lugar lugar={lugar} onElegir={setLugar} onDocumento={setDocumentoId} onVerPagina={verPagina} />
        ) : (
          <Portada onElegir={setLugar} />
        )}
      </main>

      <footer>
        <p>&copy; 2026 CabildoAbierto. Plataforma de Transparencia Ciudadana impulsada por Inteligencia Artificial.</p>
      </footer>
    </>
  );
}
