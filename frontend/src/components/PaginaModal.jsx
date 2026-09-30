// Visor de una página del documento: su texto, pasar a la anterior o la siguiente, y abrir el PDF original ahí.
export default function PaginaModal({ pagina, onClose, onVerPagina }) {
  if (!pagina) return null;
  const { documento_id: doc, pagina: n, total_paginas: total } = pagina;
  return (
    <div className="pagina-modal" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="pagina-content">
        <h3 style={{ color: 'var(--primary-color)', marginBottom: '1rem', borderBottom: '1px solid var(--accent-color)', paddingBottom: '10px' }}>
          {pagina.documento_titulo} <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>· página {n}{total ? ` de ${total}` : ''}</span>
        </h3>
        <p style={{ lineHeight: '1.6', color: '#444', whiteSpace: 'pre-wrap' }}>{pagina.texto}</p>
        <div className="pagina-acciones">
          <button disabled={n <= 1} onClick={() => onVerPagina(doc, n - 1)}>‹ Anterior</button>
          <button disabled={!!total && n >= total} onClick={() => onVerPagina(doc, n + 1)}>Siguiente ›</button>
          {pagina.pdf_url ? (
            <a className="pagina-pdf" href={pagina.pdf_url} target="_blank" rel="noopener noreferrer">
              <i className="fa-regular fa-file-pdf"></i> Ver en el PDF original
            </a>
          ) : pagina.url_fuente ? (
            <a className="pagina-pdf" href={pagina.url_fuente} target="_blank" rel="noopener noreferrer">
              <i className="fa-solid fa-arrow-up-right-from-square"></i> Ver fuente oficial
            </a>
          ) : null}
          <button onClick={onClose}>Cerrar vista</button>
        </div>
      </div>
    </div>
  );
}
