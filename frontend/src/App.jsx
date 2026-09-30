import { useState, useEffect } from 'react';
import { api } from './api.js';
import Portada from './components/Portada.jsx';
import Lugar from './components/Lugar.jsx';
import Documento from './components/Documento.jsx';
import PaginaModal from './components/PaginaModal.jsx';

export default function App() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const [pagina, setPagina] = useState(null);

  useEffect(() => {
    const handlePopState = () => setCurrentPath(window.location.pathname);
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = (path) => {
    window.history.pushState(null, '', path);
    setCurrentPath(path);
  };

  const verPagina = (docId, numero) => api.pagina(docId, numero).then(setPagina);

  let content = null;
  const isDocumento = currentPath.startsWith('/documento/');
  const isLugar = currentPath.startsWith('/estado/') || currentPath.startsWith('/municipio/');

  if (isDocumento) {
    const id = parseInt(currentPath.split('/')[2], 10);
    content = <Documento id={id} onVerPagina={verPagina} />;
  } else if (isLugar) {
    const partes = currentPath.split('/');
    const tipo = partes[1]; // 'estado' o 'municipio'
    const id = parseInt(partes[2], 10);
    content = (
      <Lugar 
        lugar={{ tipo, id }} 
        onElegir={(l) => navigate(`/${l.tipo}/${l.id}`)} 
        onDocumento={(dId) => navigate(`/documento/${dId}`)} 
        onVerPagina={verPagina} 
      />
    );
  } else {
    content = <Portada onElegir={(l) => navigate(`/${l.tipo}/${l.id}`)} />;
  }

  return (
    <>
      <header>
        <div className="logo">
          <i className="fa-regular fa-message"></i> CabildoAbierto
        </div>
        <nav>
          <ul>
            <li>
              <button className="btn-link" onClick={() => navigate('/')}>
                Inicio
              </button>
            </li>
            {(isLugar || isDocumento) && (
              <li>
                <button className="btn-link" onClick={() => window.history.back()}>
                  <i className="fa-solid fa-arrow-left"></i> Volver
                </button>
              </li>
            )}
          </ul>
        </nav>
      </header>

      <PaginaModal pagina={pagina} onClose={() => setPagina(null)} />

      <main>
        {content}
      </main>

      <footer>
        <p>&copy; 2026 CabildoAbierto. Plataforma de Transparencia Ciudadana impulsada por Inteligencia Artificial.</p>
      </footer>
    </>
  );
}
