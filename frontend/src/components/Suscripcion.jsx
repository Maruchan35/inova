import { useState } from 'react';
import { api } from '../api.js';

export default function Suscripcion({ lugar = { tipo: 'estado', id: 1 }, nombre = 'tu gobierno', autoOpen = false }) {
  const [telefono, setTelefono] = useState('');
  const [acepto, setAcepto] = useState(false);
  const [codigo, setCodigo] = useState('');
  const [paso, setPaso] = useState(0); // 0: telefono, 1: codigo, 2: success, 3: ya suscrito
  const [error, setError] = useState('');
  const [lugarNombre, setLugarNombre] = useState('');
  const [cargando, setCargando] = useState(false);

  const handleSubmitTelefono = async (e) => {
    e.preventDefault();
    if (!acepto) {
      setError('Debes aceptar el aviso de privacidad.');
      return;
    }
    if (telefono.length !== 10) {
      setError('El teléfono debe tener 10 dígitos.');
      return;
    }
    setError('');
    setCargando(true);
    try {
      const estado_id = lugar.tipo === 'estado' ? lugar.id : null;
      const municipio_id = lugar.tipo === 'municipio' ? lugar.id : null;
      const res = await api.suscribir(telefono, estado_id, municipio_id);
      
      setLugarNombre(res.lugar);
      if (res.estatus === 'codigo_enviado') {
        setPaso(1);
      } else if (res.estatus === 'ya_suscrito') {
        setPaso(3);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  };

  const handleSubmitCodigo = async (e) => {
    e.preventDefault();
    if (codigo.length !== 6) {
      setError('El código debe tener 6 dígitos.');
      return;
    }
    setError('');
    setCargando(true);
    try {
      const res = await api.verificarSuscripcion(telefono, codigo);
      if (res.estatus === 'activa') {
        setPaso(2);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  };

  // Estado para controlar si la ventanita flotante está abierta
  const [abierto, setAbierto] = useState(autoOpen);

  return (
    <div className="whatsapp-container">
      {abierto && (
        <div className="whatsapp-window">
          <div className="whatsapp-header">
            <span>
              <i className="fa-brands fa-whatsapp" style={{ marginRight: '8px' }}></i>
              Recibe avisos por WhatsApp
            </span>
            <button onClick={() => setAbierto(false)} style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer', fontSize: '1.2rem' }}>
              <i className="fa-solid fa-xmark"></i>
            </button>
          </div>
          
          <div className="whatsapp-content">
            {error && <p className="error" style={{ marginBottom: '1rem', color: 'red', fontSize: '0.9rem' }}>{error}</p>}
            
            {paso === 0 && (
              <form onSubmit={handleSubmitTelefono}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <p style={{ fontSize: '0.9rem', color: 'var(--text-main)', margin: 0, marginBottom: '0.5rem' }}>
                    Entérate cuando {nombre} publique nuevos informes.
                  </p>
                  <input
                    type="tel"
                    placeholder="Número (10 dígitos)"
                    value={telefono}
                    onChange={(e) => setTelefono(e.target.value.replace(/\D/g, '').slice(0, 10))}
                    style={{ padding: '10px', borderRadius: '8px', border: '1px solid #ccc' }}
                  />
                  <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                    <input type="checkbox" checked={acepto} onChange={(e) => setAcepto(e.target.checked)} style={{ marginTop: '3px' }} />
                    <span>Acepto el aviso de privacidad para enviarme avisos de nuevos documentos.</span>
                  </label>
                  <button type="submit" disabled={cargando} className="cta-btn" style={{ padding: '10px', fontSize: '0.9rem', background: '#25D366', boxShadow: 'none' }}>
                    {cargando ? 'Enviando...' : 'Recibir informes'}
                  </button>
                </div>
              </form>
            )}

            {paso === 1 && (
              <form onSubmit={handleSubmitCodigo}>
                <p style={{ marginBottom: '1rem', fontSize: '0.9rem' }}>Enviamos un código al {telefono}.</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <input
                    type="text"
                    placeholder="Código de 6 dígitos"
                    value={codigo}
                    onChange={(e) => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    style={{ padding: '10px', borderRadius: '8px', border: '1px solid #ccc', letterSpacing: '2px', textAlign: 'center', fontSize: '1.2rem' }}
                  />
                  <button type="submit" disabled={cargando} className="cta-btn" style={{ padding: '10px', fontSize: '0.9rem', background: '#25D366', boxShadow: 'none' }}>
                    {cargando ? 'Verificando...' : 'Confirmar'}
                  </button>
                </div>
              </form>
            )}

            {paso === 2 && (
              <div style={{ padding: '1rem', background: '#dcf8c6', borderRadius: '8px', color: '#075e54', fontSize: '0.9rem' }}>
                <strong>¡Listo!</strong> Te avisaremos por WhatsApp cuando {lugarNombre} publique documentos nuevos.
              </div>
            )}

            {paso === 3 && (
              <div style={{ padding: '1rem', background: '#e2f0fb', borderRadius: '8px', color: '#005c9e', fontSize: '0.9rem' }}>
                Ya recibes avisos de {lugarNombre}.
              </div>
            )}
          </div>
        </div>
      )}
      
      {!abierto && (
        <button className="whatsapp-toggle" onClick={() => setAbierto(true)} onMouseEnter={() => setAbierto(true)} aria-label="Recibir avisos por WhatsApp">
          <i className="fa-brands fa-whatsapp"></i>
        </button>
      )}
    </div>
  );
}
