// Visor de una página del documento: su texto, pasar a la anterior o la siguiente, y abrir el PDF original ahí.
export default function PaginaModal({ pagina, onClose, onVerPagina }) {
  if (!pagina) return null;
  const { documento_id: doc, pagina: n, total_paginas: total } = pagina;
  return (
    <div className="pagina-modal" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="pagina-content">
        <div className="pagina-header">
          <div>
            <span className="pagina-badge">
              <i className="fa-regular fa-file-lines" style={{ marginRight: '5px' }}></i>
              Página {n}{total ? ` de ${total}` : ''}
            </span>
            <h3 className="pagina-title">{pagina.documento_titulo}</h3>
          </div>
          <button className="pagina-close-btn" onClick={onClose} title="Cerrar ventana">
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>

        <div className="pagina-body">
          <p className="pagina-texto">{pagina.texto}</p>
        </div>

        <div className="pagina-acciones">
          <div className="pagina-nav-controles">
            <button className="btn-pag-nav" disabled={n <= 1} onClick={() => onVerPagina(doc, n - 1)}>
              <i className="fa-solid fa-chevron-left"></i> Anterior
            </button>
            <span className="pagina-contador">{n} / {total || '—'}</span>
            <button className="btn-pag-nav" disabled={!!total && n >= total} onClick={() => onVerPagina(doc, n + 1)}>
              Siguiente <i className="fa-solid fa-chevron-right"></i>
            </button>
          </div>
          
          <div className="pagina-links-externos">
            {pagina.pdf_url ? (
              <a className="pagina-pdf" href={pagina.pdf_url} target="_blank" rel="noopener noreferrer">
                <i className="fa-regular fa-file-pdf"></i> Ver PDF original
              </a>
            ) : pagina.url_fuente ? (
              <a className="pagina-pdf" href={pagina.url_fuente} target="_blank" rel="noopener noreferrer">
                <i className="fa-solid fa-arrow-up-right-from-square"></i> Fuente oficial
              </a>
            ) : null}
            <button className="btn-pag-cerrar" onClick={onClose}>Cerrar vista</button>
          </div>
        </div>
      </div>
    </div>
  );
}
