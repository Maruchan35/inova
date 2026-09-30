import { useState } from 'react';

/**
 * Modal informativo para empresas u organizaciones interesadas en anunciarse.
 */
export function ModalPublicidad({ abierto, onCerrar }) {
  const [enviado, setEnviado] = useState(false);
  const [form, setForm] = useState({ nombre: '', empresa: '', correo: '', telefono: '', mensaje: '' });

  if (!abierto) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    setEnviado(true);
  };

  const handleReset = () => {
    setEnviado(false);
    setForm({ nombre: '', empresa: '', correo: '', telefono: '', mensaje: '' });
    onCerrar();
  };

  return (
    <div className="modal-overlay" onClick={handleReset} style={{ zIndex: 1200 }}>
      <div 
        className="modal-publicidad-card" 
        onClick={(e) => e.stopPropagation()}
      >
        <button 
          className="modal-close-btn" 
          onClick={handleReset}
          aria-label="Cerrar modal de publicidad"
        >
          <i className="fa-solid fa-xmark"></i>
        </button>

        <div className="modal-publicidad-header">
          <div className="modal-pub-icon">
            <i className="fa-solid fa-bullhorn"></i>
          </div>
          <div>
            <h3>Espacio Publicitario y Patrocinios</h3>
            <p className="modal-pub-subtitle">
              Impulsa tu empresa apoyando el acceso libre a la información pública
            </p>
          </div>
        </div>

        <div className="modal-publicidad-body">
          <div className="modal-pub-beneficios">
            <div className="beneficio-item">
              <i className="fa-solid fa-earth-americas"></i>
              <div>
                <strong>Presencia Nacional</strong>
                <p>Alcance en los 32 estados y más de 2,400 municipios de México.</p>
              </div>
            </div>
            <div className="beneficio-item">
              <i className="fa-solid fa-users-viewfinder"></i>
              <div>
                <strong>Audiencia Calificada</strong>
                <p>Ciudadanos activos, periodistas, investigadores, servidores públicos y empresarios.</p>
              </div>
            </div>
            <div className="beneficio-item">
              <i className="fa-solid fa-handshake-angle"></i>
              <div>
                <strong>Publicidad con Propósito</strong>
                <p>Tu inversión financia servidores, procesamiento de documentos oficiales y RAG con IA.</p>
              </div>
            </div>
          </div>

          {enviado ? (
            <div className="ad-exito-box">
              <i className="fa-solid fa-circle-check" style={{ color: '#10b981', fontSize: '2.5rem', marginBottom: '10px' }}></i>
              <h4>¡Solicitud enviada con éxito!</h4>
              <p>Un asesor de vinculación y patrocinios se pondrá en contacto contigo a la brevedad.</p>
              <button className="search-btn" style={{ marginTop: '15px' }} onClick={handleReset}>
                Entendido
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="modal-pub-form">
              <h4>Solicitar informes de tarifas y espacios disponibles</h4>
              
              <div className="pub-form-grid">
                <div>
                  <label>Nombre o contacto</label>
                  <input 
                    type="text" 
                    required 
                    placeholder="Tu nombre completo"
                    value={form.nombre} 
                    onChange={e => setForm({ ...form, nombre: e.target.value })} 
                  />
                </div>
                <div>
                  <label>Empresa u Organización</label>
                  <input 
                    type="text" 
                    required 
                    placeholder="Nombre comercial"
                    value={form.empresa} 
                    onChange={e => setForm({ ...form, empresa: e.target.value })} 
                  />
                </div>
                <div>
                  <label>Correo electrónico</label>
                  <input 
                    type="email" 
                    required 
                    placeholder="ejemplo@empresa.com"
                    value={form.correo} 
                    onChange={e => setForm({ ...form, correo: e.target.value })} 
                  />
                </div>
                <div>
                  <label>Teléfono o WhatsApp</label>
                  <input 
                    type="tel" 
                    placeholder="(Opcional)"
                    value={form.telefono} 
                    onChange={e => setForm({ ...form, telefono: e.target.value })} 
                  />
                </div>
              </div>

              <div style={{ marginTop: '10px' }}>
                <label>Detalle de tu campaña o interés</label>
                <textarea 
                  rows="3" 
                  placeholder="Ej. Nos interesa presencia en las secciones de finanzas y obras públicas..."
                  value={form.mensaje} 
                  onChange={e => setForm({ ...form, mensaje: e.target.value })} 
                />
              </div>

              <div className="modal-pub-actions">
                <button type="submit" className="search-btn">
                  <i className="fa-regular fa-paper-plane" style={{ marginRight: '8px' }}></i> Enviar solicitud
                </button>
                <a 
                  href="https://wa.me/?text=Hola%20CabildoAbierto,%20me%20interesa%20información%20sobre%20los%20espacios%20publicitarios." 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="btn-whatsapp-ad"
                >
                  <i className="fa-brands fa-whatsapp" style={{ marginRight: '6px' }}></i> Contactar por WhatsApp
                </a>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Rectángulo publicitario único en la orilla inferior izquierda.
 * Por defecto permanece siempre minimizado como una píldora discreta
 * y solo se expande al hacer clic sobre ella.
 */
export default function EspacioPublicidad({ onAbrirModal }) {
  // Siempre inicia minimizado hasta que el usuario dé clic
  const [minimizado, setMinimizado] = useState(true);

  if (minimizado) {
    return (
      <div className="ad-container-bottom-left">
        <button 
          type="button"
          className="ad-pill-minimizado" 
          onClick={() => setMinimizado(false)}
          title="Espacio publicitario disponible - Clic para ver"
          aria-label="Espacio publicitario disponible - Clic para ver"
        >
          <span className="ad-pill-icon">
            <i className="fa-solid fa-rectangle-ad"></i>
          </span>
          <span className="ad-pill-texto">Publicidad</span>
          <i className="fa-solid fa-chevron-up ad-pill-flecha"></i>
        </button>
      </div>
    );
  }

  return (
    <div className="ad-container-bottom-left">
      <aside 
        className="ad-rectangulo-orilla ad-expanded-card" 
        aria-label="Espacio publicitario"
      >
        <button 
          className="ad-cerrar-discreto" 
          onClick={(e) => { e.stopPropagation(); setMinimizado(true); }}
          title="Minimizar anuncio"
          aria-label="Minimizar anuncio"
        >
          <i className="fa-solid fa-chevron-down"></i>
        </button>

        <div className="ad-badge-header">
          <span className="ad-pill-tag">
            <i className="fa-solid fa-rectangle-ad" style={{ marginRight: '5px' }}></i>
            ESPACIO PUBLICITARIO
          </span>
        </div>

        <div className="ad-placeholder-graphic">
          <i className="fa-regular fa-images"></i>
          <span>Tu anuncio aquí</span>
        </div>

        <div className="ad-content-text">
          <h5>Impulsa tu Empresa</h5>
          <p>
            Espacio reservado para empresas y comercios con presencia local o nacional.
          </p>
        </div>

        <button 
          type="button" 
          className="ad-btn-accion" 
          onClick={onAbrirModal}
        >
          <i className="fa-solid fa-arrow-up-right-from-square" style={{ marginRight: '6px' }}></i>
          Anúnciate aquí
        </button>

        <small className="ad-footer-legal">Publicidad ética y no invasiva</small>
      </aside>
    </div>
  );
}
