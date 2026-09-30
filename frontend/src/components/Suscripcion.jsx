import { useState } from 'react';
import { api } from '../api.js';

export default function Suscripcion({ lugar }) {
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

  return (
    <div className="suscripcion-card" style={{ marginTop: '2rem', padding: '2rem', background: 'white', borderRadius: '12px', boxShadow: 'var(--card-shadow)' }}>
      <h3 style={{ color: 'var(--primary-color)', marginBottom: '1rem' }}>
        <i className="fa-brands fa-whatsapp" style={{ color: '#25D366' }}></i> Recibe avisos por WhatsApp
      </h3>
      
      {error && <p className="error" style={{ marginBottom: '1rem', color: 'red' }}>{error}</p>}
      
      {paso === 0 && (
        <form onSubmit={handleSubmitTelefono}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: '400px' }}>
            <input
              type="tel"
              placeholder="Número de celular (10 dígitos)"
              value={telefono}
              onChange={(e) => setTelefono(e.target.value.replace(/\D/g, '').slice(0, 10))}
              style={{ padding: '10px', borderRadius: '8px', border: '1px solid #ccc' }}
            />
            <label style={{ fontSize: '0.9rem', color: 'var(--text-muted)', display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
              <input type="checkbox" checked={acepto} onChange={(e) => setAcepto(e.target.checked)} style={{ marginTop: '4px' }} />
              <span>Acepto el aviso de privacidad: guardamos tu número y el lugar que sigues solo para avisarte de documentos nuevos; no lo compartimos; te das de baja respondiendo BAJA.</span>
            </label>
            <button type="submit" disabled={cargando} className="cta-btn" style={{ padding: '10px' }}>
              {cargando ? 'Enviando...' : 'Enviarme el código'}
            </button>
          </div>
        </form>
      )}

      {paso === 1 && (
        <form onSubmit={handleSubmitCodigo}>
          <p style={{ marginBottom: '1rem' }}>Hemos enviado un código por WhatsApp al {telefono}.</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: '400px' }}>
            <input
              type="text"
              placeholder="Código de 6 dígitos"
              value={codigo}
              onChange={(e) => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 6))}
              style={{ padding: '10px', borderRadius: '8px', border: '1px solid #ccc', letterSpacing: '2px', textAlign: 'center', fontSize: '1.2rem' }}
            />
            <button type="submit" disabled={cargando} className="cta-btn" style={{ padding: '10px' }}>
              {cargando ? 'Verificando...' : 'Confirmar'}
            </button>
          </div>
        </form>
      )}

      {paso === 2 && (
        <div style={{ padding: '1rem', background: '#dcf8c6', borderRadius: '8px', color: '#075e54' }}>
          <strong>Listo:</strong> te avisaremos por WhatsApp cuando el gobierno de {lugarNombre} publique documentos nuevos. Para dejar de recibirlos, responde BAJA.
        </div>
      )}

      {paso === 3 && (
        <div style={{ padding: '1rem', background: '#e2f0fb', borderRadius: '8px', color: '#005c9e' }}>
          Ya recibes avisos de {lugarNombre}.
        </div>
      )}
    </div>
  );
}
