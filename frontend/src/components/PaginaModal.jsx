export default function PaginaModal({ pagina, onClose }) {
  if (!pagina) return null;
  return (
    <div className="pagina-modal">
      <div className="pagina-content">
        <h3 style={{ color: 'var(--royal-blue)', marginBottom: '1rem', borderBottom: '1px solid var(--platinum)', paddingBottom: '10px' }}>
          {pagina.documento_titulo} <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Â· pÃ¡gina {pagina.pagina}</span>
        </h3>
        <p style={{ lineHeight: '1.6', color: '#444', whiteSpace: 'pre-wrap' }}>{pagina.texto}</p>
        <div style={{ textAlign: 'right' }}>
          <button onClick={onClose}>Cerrar vista</button>
        </div>
      </div>
    </div>
  );
}
