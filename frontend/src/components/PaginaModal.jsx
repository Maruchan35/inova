export default function PaginaModal({ pagina, onClose }) {
  if (!pagina) return null;
  return (
    <div className="pagina-modal">
      <div className="pagina-content">
        <h3 style={{ color: 'var(--primary-color)', marginBottom: '1rem', borderBottom: '1px solid var(--accent-color)', paddingBottom: '10px' }}>
          {pagina.documento_titulo} <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Â· página {pagina.pagina}</span>
        </h3>
        <p style={{ lineHeight: '1.6', color: '#444', whiteSpace: 'pre-wrap' }}>{pagina.texto}</p>
        <div style={{ textAlign: 'right' }}>
          <button onClick={onClose}>Cerrar vista</button>
        </div>
      </div>
    </div>
  );
}
