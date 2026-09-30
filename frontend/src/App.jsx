import { useState, useEffect } from 'react';
import { api } from './api.js';
import Portada from './components/Portada.jsx';
import Lugar from './components/Lugar.jsx';
import Documento from './components/Documento.jsx';
import PaginaModal from './components/PaginaModal.jsx';
import Chatbot from './components/Chatbot.jsx';
import Suscripcion from './components/Suscripcion.jsx';

export default function App() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const [pagina, setPagina] = useState(null);
  const [chatbotAbierto, setChatbotAbierto] = useState(false);
  const [contexto, setContexto] = useState('todos los documentos'); // sobre qué pregunta el chatbot

  useEffect(() => {
    const handlePopState = () => setCurrentPath(window.location.pathname);
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = (path) => {
    window.history.pushState(null, '', path);
    setCurrentPath(path);
  };

  const verPagina = (docId, numero) => api.pagina(docId, numero).then(setPagina).catch(() => {});

  let content = null;
  let chatbotFiltros = {};
  const isDocumento = currentPath.startsWith('/documento/');
  const isLugar = currentPath.startsWith('/estado/') || currentPath.startsWith('/municipio/');

  useEffect(() => {
    if (!isDocumento && !isLugar) setContexto('todos los documentos');
  }, [isDocumento, isLugar]);

  if (isDocumento) {
    const id = parseInt(currentPath.split('/')[2], 10);
    content = <Documento id={id} onVerPagina={verPagina} onIr={navigate} onContexto={setContexto} />;
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
        onContexto={setContexto}
        onIr={navigate} 
        onVerPagina={verPagina} 
      />
    );
    chatbotFiltros = tipo === 'estado' ? { estado_id: id } : { municipio_id: id };
  } else {
    content = <Portada onElegir={(l) => navigate(`/${l.tipo}/${l.id}`)} />;
  }

  let lugarActual = { tipo: 'estado', id: 1 };
  if (isLugar) {
    const partes = currentPath.split('/');
    lugarActual = { tipo: partes[1], id: parseInt(partes[2], 10) };
  }

  return (
    <>
      <header>
        <div className="logo" style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 'bold' }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color, #4a90e2)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
          </svg>
          <span style={{ color: 'var(--primary-color)' }}>CabildoAbierto</span>
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

      <PaginaModal pagina={pagina} onClose={() => setPagina(null)} onVerPagina={verPagina} />

      <main>
        {content}
      </main>

      <Suscripcion key={currentPath} autoOpen={currentPath === '/'} lugar={lugarActual} nombre={isLugar ? 'tu gobierno' : 'tu estado'} />
      <Chatbot filtros={chatbotFiltros} contexto={contexto} onVerPagina={verPagina} abiertoPorDefecto={chatbotAbierto} onCerrar={() => setChatbotAbierto(false)} />

      <footer>
        <p>&copy; 2026 CabildoAbierto. Plataforma de Transparencia Ciudadana impulsada por Inteligencia Artificial.</p>
      </footer>
    </>
  );
}
