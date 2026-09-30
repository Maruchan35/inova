import { useState, useMemo, useEffect } from 'react';

/**
 * Limpia caracteres de reemplazo o artefactos OCR en texto de páginas.
 */
function cleanOcrText(str) {
  if (!str) return '';
  return str.replace(/\ufffd/g, '').trim();
}

/**
 * Formatea un valor numérico o porcentual para visualización financiera atractiva.
 */
function formatFinancialCell(val) {
  if (!val) return '—';
  const clean = val.trim();
  
  // Porcentajes
  if (clean.endsWith('%')) {
    const num = parseFloat(clean.replace('%', '').replace(',', ''));
    let badgeClass = 'badge-neutral';
    if (!isNaN(num)) {
      if (num > 0) badgeClass = 'badge-up';
      else if (num < 0) badgeClass = 'badge-down';
    }
    return <span className={`pagina-metric-pill ${badgeClass}`}>{clean}</span>;
  }

  // Cifras numéricas con comas o decimales (importes monetarios o cantidades)
  if (/^-?[\d,]+(?:\.\d+)?$/.test(clean)) {
    const isNegative = clean.startsWith('-');
    const hasCommas = clean.includes(',');
    // Si tiene comas o más de 3 dígitos, asumimos importe en pesos
    if (hasCommas || clean.replace('-', '').length >= 4) {
      return (
        <span className={`pagina-num-val ${isNegative ? 'num-negative' : ''}`}>
          {isNegative ? `-$${clean.replace('-', '')}` : `$${clean}`}
        </span>
      );
    }
    return <span className="pagina-num-val">{clean}</span>;
  }

  return clean;
}

/**
 * Analiza el texto plano de la página y reconstruye párrafos fluidos y continuos,
 * evitando saltos de línea bruscos a mitad de oración, detectando tablas de datos
 * y cintillos de sección contable genuinos.
 */
function parsePageText(text, docTitle = '') {
  if (!text) return [];
  const rawLines = text.split('\n').map(l => cleanOcrText(l));
  
  const blocks = [];
  let currentTable = null;
  let activeHeaders = null;
  let currentParagraph = [];

  const flushParagraph = () => {
    if (currentParagraph.length > 0) {
      blocks.push({
        type: 'paragraph',
        text: currentParagraph.join(' ')
      });
      currentParagraph = [];
    }
  };

  const flushTable = () => {
    if (currentTable && currentTable.rows.length > 0) {
      blocks.push(currentTable);
    }
    currentTable = null;
  };

  const normTitle = cleanOcrText(docTitle).toLowerCase();

  for (let i = 0; i < rawLines.length; i++) {
    const line = rawLines[i];

    // Línea vacía: fin de párrafo natural
    if (!line) {
      flushParagraph();
      flushTable();
      continue;
    }

    // Número de página aislado (ej. "14")
    if (/^\d{1,4}$/.test(line)) {
      flushParagraph();
      flushTable();
      continue;
    }

    // Encabezado de repetición del documento en las primeras líneas
    if (normTitle && line.toLowerCase().includes(normTitle.slice(0, 25)) && line.length < 90 && i < 3) {
      flushParagraph();
      flushTable();
      continue;
    }

    // 1. Detectar cabecera de tabla contable explícita
    if (/^(Concepto|Cuenta|Partida|Descripci[oó]n|Rubro)\b/i.test(line) && (/\d|%|Variaci|Columna/i.test(line))) {
      flushParagraph();
      flushTable();
      const headers = line.split(/\s{2,}|\t/).filter(Boolean);
      activeHeaders = headers.length > 1 ? headers : ['Concepto / Rubro', 'Período Actual', 'Período Anterior', 'Variación ($)', 'Variación (%)'];
      continue;
    }

    // 2. Fila tabular con concepto y columnas numéricas al final
    const rawTokens = line.split(/\s+/);
    const tokens = [];
    for (let tIdx = 0; tIdx < rawTokens.length; tIdx++) {
      let tok = rawTokens[tIdx];
      while (tIdx + 1 < rawTokens.length) {
        const next = rawTokens[tIdx + 1];
        if (/^-?[\d,.]+%?$/.test(tok) && /^-?[\d,.]+%?$/.test(next)) {
          if (tok.endsWith(',') || next.startsWith('.') || (next.length <= 2 && /^\d+%?$/.test(next))) {
            tok += next;
            tIdx++;
            continue;
          }
        }
        break;
      }
      tokens.push(tok);
    }

    let numStart = -1;
    for (let k = tokens.length - 1; k >= 0; k--) {
      if (/^-?[\d,.]+%?$/.test(tokens[k])) {
        numStart = k;
      } else {
        break;
      }
    }

    const hasMultipleNumbers = numStart > 0 && (tokens.length - numStart >= 2);
    const hasSingleFormattedNumber = numStart > 0 && (tokens.length - numStart === 1) && (tokens[numStart].includes(',') || tokens[numStart].includes('%'));
    const isSingleYear = (tokens.length - numStart === 1) && /^(19|20)\d{2}$/.test(tokens[numStart]);
    const conceptLength = tokens.slice(0, numStart).join(' ').length;
    const isProseSentence = line.includes(' es decir, ') || line.includes('representó el') || line.includes('de acuerdo con') || line.length > 90;

    // Solo es fila tabular si tiene concepto compacto (< 45 caracteres) y cifras numéricas claras (no una frase descriptiva)
    if (numStart > 0 && (hasMultipleNumbers || hasSingleFormattedNumber) && !isSingleYear && conceptLength < 45 && !isProseSentence) {
      flushParagraph();
      if (!currentTable) {
        currentTable = {
          type: 'table',
          headers: activeHeaders || ['Concepto / Rubro', 'Importe 1', 'Importe 2', 'Variación', '%'],
          rows: []
        };
      }
      currentTable.rows.push({
        concept: tokens.slice(0, numStart).join(' '),
        values: tokens.slice(numStart)
      });
      continue;
    }

    // 3. Título de sección genuino (en mayúsculas puras, corto, sin punto ni coma, no es una oración corrida)
    const isUpper = line === line.toUpperCase() && /[A-ZÁÉÍÓÚÑ]/.test(line);
    const endsWithColon = line.endsWith(':');
    const isCleanSectionTitle = !line.includes('.') && !line.includes(',') && !/\d{2,}/.test(line) && line.length <= 40;

    if ((isUpper || endsWithColon) && isCleanSectionTitle) {
      flushParagraph();
      flushTable();
      blocks.push({ type: 'section', title: line.replace(/:$/, '') });
      continue;
    }

    // 4. Prosa y texto continuo: se unen las líneas consecutivas para que las oraciones no se corten
    flushTable();
    currentParagraph.push(line);
  }

  flushParagraph();
  flushTable();
  return blocks;
}

export default function PaginaModal({ pagina, onClose, onVerPagina }) {
  const [vista, setVista] = useState('estructurada'); // 'estructurada' | 'original'
  const [copiado, setCopiado] = useState(false);

  // Escuchar tecla Escape para cerrar
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const blocks = useMemo(() => {
    if (!pagina?.texto) return [];
    return parsePageText(pagina.texto, pagina.documento_titulo);
  }, [pagina?.texto, pagina?.documento_titulo]);

  const copiarTexto = async () => {
    if (!pagina?.texto) return;
    try {
      await navigator.clipboard.writeText(pagina.texto);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      // Fallback
    }
  };

  if (!pagina) return null;
  const { documento_id: doc, pagina: n, total_paginas: total } = pagina;

  const tieneTablas = blocks.some(b => b.type === 'table');

  return (
    <div className="pagina-modal" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="pagina-content">
        {/* Cabecera del visor */}
        <div className="pagina-header">
          <div className="pagina-header-left">
            <div className="pagina-header-tags">
              <span className="pagina-badge">
                <i className="fa-regular fa-file-lines" style={{ marginRight: '6px' }}></i>
                Página {n}{total ? ` de ${total}` : ''}
              </span>
              {tieneTablas && (
                <span className="pagina-badge-accent">
                  <i className="fa-solid fa-chart-simple" style={{ marginRight: '5px' }}></i>
                  Datos tabulares detectados
                </span>
              )}
            </div>
            <h3 className="pagina-title">{pagina.documento_titulo}</h3>
          </div>

          <div className="pagina-header-controls">
            {/* Selector de modo de vista */}
            <div className="pagina-view-switcher">
              <button
                type="button"
                className={`btn-view-tab ${vista === 'estructurada' ? 'active' : ''}`}
                onClick={() => setVista('estructurada')}
                title="Ver texto continuo y tablas organizadas"
              >
                <i className="fa-solid fa-table-cells" style={{ marginRight: '6px' }}></i>
                Vista Estructurada
              </button>
              <button
                type="button"
                className={`btn-view-tab ${vista === 'original' ? 'active' : ''}`}
                onClick={() => setVista('original')}
                title="Ver transcripción OCR original"
              >
                <i className="fa-solid fa-align-left" style={{ marginRight: '6px' }}></i>
                Texto Original
              </button>
            </div>

            <button className="pagina-close-btn" onClick={onClose} title="Cerrar visor">
              <i className="fa-solid fa-xmark"></i>
            </button>
          </div>
        </div>

        {/* Cuerpo del visor */}
        <div className="pagina-body">
          {vista === 'estructurada' ? (
            <div className="pagina-structured-container">
              {blocks.length === 0 ? (
                <p className="tenue" style={{ textAlign: 'center', padding: '2rem' }}>No hay texto extraído en esta página.</p>
              ) : (
                blocks.map((block, idx) => {
                  if (block.type === 'section') {
                    return (
                      <div key={idx} className="pagina-seccion-banner">
                        <i className="fa-solid fa-layer-group" style={{ marginRight: '8px', color: 'var(--accent-color)' }}></i>
                        {block.title}
                      </div>
                    );
                  }

                  if (block.type === 'table') {
                    const maxCols = Math.max(...block.rows.map(r => r.values.length), block.headers.length - 1);
                    return (
                      <div key={idx} className="pagina-table-wrapper">
                        <table className="pagina-data-table">
                          <thead>
                            <tr>
                              <th style={{ textAlign: 'left' }}>{block.headers[0] || 'Concepto'}</th>
                              {Array.from({ length: maxCols }).map((_, cIdx) => (
                                <th key={cIdx} style={{ textAlign: 'right' }}>
                                  {block.headers[cIdx + 1] || `Columna ${cIdx + 1}`}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {block.rows.map((row, rIdx) => (
                              <tr key={rIdx}>
                                <td className="pagina-cell-concept">{row.concept}</td>
                                {Array.from({ length: maxCols }).map((_, cIdx) => (
                                  <td key={cIdx} className="pagina-cell-num">
                                    {formatFinancialCell(row.values[cIdx])}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    );
                  }

                  // Párrafo continuo de texto
                  return (
                    <p key={idx} className="pagina-parrafo-clean">
                      {block.text}
                    </p>
                  );
                })
              )}
            </div>
          ) : (
            <div className="pagina-original-container">
              <div className="pagina-original-toolbar">
                <span className="tenue" style={{ fontSize: '0.8rem' }}>Transcripción de caracteres sin formato</span>
                <button type="button" className="btn-copy-raw" onClick={copiarTexto}>
                  <i className={copiado ? 'fa-solid fa-check' : 'fa-regular fa-copy'} style={{ marginRight: '6px' }}></i>
                  {copiado ? '¡Copiado!' : 'Copiar texto'}
                </button>
              </div>
              <pre className="pagina-texto-raw">{pagina.texto}</pre>
            </div>
          )}
        </div>

        {/* Acciones y navegación inferior */}
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
