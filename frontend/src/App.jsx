import { useState, useEffect, Component } from 'react';
import { api } from './api.js';
import Portada from './components/Portada.jsx';
import Lugar from './components/Lugar.jsx';
import Documento from './components/Documento.jsx';
import PaginaModal from './components/PaginaModal.jsx';
import Chatbot from './components/Chatbot.jsx';
import Suscripcion from './components/Suscripcion.jsx';

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

  const isDocumento = currentPath.startsWith('/documento/');
  const isLugar = currentPath.startsWith('/estado/') || currentPath.startsWith('/municipio/');
  const esPaginaPrincipal = currentPath === '/' || currentPath === '';

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
      setPagina(null);
      window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    setPagina(null);
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    if (!isDocumento && !isLugar) setContexto('todos los documentos');
  }, [currentPath, isDocumento, isLugar]);

  const navigate = (path) => {
    window.history.pushState(null, '', path);
    setCurrentPath(path);
    setPagina(null);
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  };

  const verPagina = (docId, numero) => api.pagina(docId, numero).then(setPagina).catch(() => {});

  let content = null;
  let chatbotFiltros = {};

  let lugarActual = { tipo: 'estado', id: 1 };
  if (isLugar) {
    const partes = currentPath.split('/');
    lugarActual = { tipo: partes[1], id: parseInt(partes[2], 10) };
  }

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
        <div 
          className="logo interactive-logo" 
          onClick={() => {
            navigate('/');
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
          title="Ir a Inicio"
        >
          <i className="fa-regular fa-message"></i> CabildoAbierto
        </div>
        <nav>
          <ul>
            {!esPaginaPrincipal && (
              <>
                <li>
                  <button className="btn-link" onClick={() => navigate('/')}>
                    <i className="fa-solid fa-house" style={{ marginRight: '5px' }}></i> Inicio
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
                    <i className="fa-solid fa-magnifying-glass" style={{ marginRight: '5px' }}></i> Buscar lugar
                  </button>
                </li>
                <li>
                  <button className="btn-link" onClick={() => setChatbotAbierto(true)}>
                    <i className="fa-solid fa-wand-magic-sparkles" style={{ marginRight: '5px' }}></i> Pregúntale a la IA
                  </button>
                </li>
                <li>
                  <button className="btn-link" onClick={() => window.history.back()}>
                    <i className="fa-solid fa-arrow-left"></i> Volver
                  </button>
                </li>
              </>
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

      <Suscripcion key={currentPath} autoOpen={false} lugar={lugarActual} nombre={isLugar ? 'tu gobierno' : 'tu estado'} />

      <Chatbot filtros={chatbotFiltros} contexto={contexto} onVerPagina={verPagina} onIr={navigate} abiertoPorDefecto={chatbotAbierto} onCerrar={() => setChatbotAbierto(false)} />

      <footer>
        <p>&copy; 2026 CabildoAbierto. Plataforma de Transparencia Ciudadana impulsada por Inteligencia Artificial.</p>
      </footer>
    </>
  );
}
