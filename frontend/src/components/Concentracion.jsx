import { useState, useEffect } from 'react';
import { api } from '../api.js';

const pesos = (n) => n.toLocaleString('es-MX', { style: 'currency', currency: 'MXN' });

export default function Concentracion({ filtros, locationName }) {
  const [filas, setFilas] = useState([]);
  
  useEffect(() => { 
    api.concentracion(filtros).then(setFilas).catch(() => setFilas([]));
  }, [filtros.estado_id, filtros.municipio_id]);
  
  if (!filas.length) return null;

  return (
    <div className="ranking-section" style={{ marginTop: '4rem' }}>
      <div className="ranking-header">
        <h2>¿A quién se le paga más en <span className="highlight-location">{locationName}</span>?</h2>
        <p style={{ color: 'var(--text-muted)', marginTop: '10px', fontSize: '1.1rem' }}>
          Proveedores con mayor concentración de compras y contratos.
        </p>
      </div>

      <div className="ranking-list">
        {filas.map((f, i) => (
          <div key={f.id} className="ranking-card">
            <div className="rank-number">{i + 1}</div>
            <div className="rank-details">
              <h3>{f.nombre}</h3>
              <p>{f.contratos} contrato(s) adjudicados.</p>
              <div className="barra">
                <div style={{ width: `${f.porcentaje}%` }}>{f.porcentaje}%</div>
              </div>
            </div>
            <div className="rank-stats">
              <span className="impact-score">{pesos(f.monto_total)}</span>
              <span className="impact-label">Total ({f.porcentaje}%)</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
