import { useState, useEffect, Component } from 'react';
import { api } from './api.js';
import Portada from './components/Portada.jsx';
import Lugar from './components/Lugar.jsx';
import Documento from './components/Documento.jsx';
import PaginaModal from './components/PaginaModal.jsx';
import Chatbot from './components/Chatbot.jsx';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ textAlign: 'center', padding: '4rem 1.5rem', maxWidth: '600px', margin: '0 auto' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem', color: '#e67e22' }}>
            <i className="fa-solid fa-triangle-exclamation"></i>
          </div>
          <h2 style={{ color: 'var(--primary-color)', marginBottom: '0.8rem' }}>No pudimos cargar esta sección</h2>
          <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem', lineHeight: 1.5 }}>
            {this.state.error?.message || 'Ocurrió un error inesperado al procesar la información.'}
          </p>
          <button 
            className="search-btn" 
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.href = '/';
            }}
          >
            <i className="fa-solid fa-house" style={{ marginRight: '8px' }}></i> Volver al Inicio
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

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
    content = <Portada onElegir={(l) => navigate(`/${l.tipo}/${l.id}`)} onDocumento={(dId) => navigate(`/documento/${dId}`)} />;
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

      <PaginaModal pagina={pagina} onClose={() => setPagina(null)} onVerPagina={verPagina} />

      <main>
        <ErrorBoundary>
          {content}
        </ErrorBoundary>
      </main>

      <Chatbot filtros={chatbotFiltros} contexto={contexto} onVerPagina={verPagina} onIr={navigate} abiertoPorDefecto={chatbotAbierto} onCerrar={() => setChatbotAbierto(false)} />

      <footer>
        <p>&copy; 2026 CabildoAbierto. Plataforma de Transparencia Ciudadana impulsada por Inteligencia Artificial.</p>
      </footer>
    </>
  );
}
