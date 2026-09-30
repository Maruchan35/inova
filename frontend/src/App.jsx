import { useState, useEffect } from 'react';
import { api } from './api.js';
import Portada from './components/Portada.jsx';
import Lugar from './components/Lugar.jsx';
import Documento from './components/Documento.jsx';
import PaginaModal from './components/PaginaModal.jsx';
import Chatbot from './components/Chatbot.jsx';

export default function App() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const [pagina, setPagina] = useState(null);
  const [chatbotAbierto, setChatbotAbierto] = useState(false);

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
  let chatbotFiltros = {};
  const isDocumento = currentPath.startsWith('/documento/');
  const isLugar = currentPath.startsWith('/estado/') || currentPath.startsWith('/municipio/');

  if (isDocumento) {
    const id = parseInt(currentPath.split('/')[2], 10);
    content = <Documento id={id} onVerPagina={verPagina} />;
    chatbotFiltros = { documento_id: id };
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
    chatbotFiltros = tipo === 'estado' ? { estado_id: id } : { municipio_id: id };
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
            <li>
              <button className="btn-link" onClick={() => {
                navigate('/');
                setTimeout(() => {
                  const buscador = document.querySelector('.search-bar input');
                  buscador?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                  buscador?.focus();
                }, 100);
              }}>
                Buscar lugar
              </button>
            </li>
            <li>
              <button className="btn-link" onClick={() => setChatbotAbierto(true)}>
                Pregúntale a la IA
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

      <Chatbot filtros={chatbotFiltros} onVerPagina={verPagina} abiertoPorDefecto={chatbotAbierto} onCerrar={() => setChatbotAbierto(false)} />

      <footer>
        <p>&copy; 2026 CabildoAbierto. Plataforma de Transparencia Ciudadana impulsada por Inteligencia Artificial.</p>
      </footer>
    </>
  );
}
