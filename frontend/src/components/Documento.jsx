import { useState, useEffect, useMemo } from 'react';
import { api } from '../api.js';

/**
 * Limpia fragmentos cortados y caracteres OCR residuales de un punto clave.
 */
function cleanPuntoText(texto) {
  if (!texto) return '';
  let s = texto.replace(/\ufffd/g, '');
  // Quitar elipsis, comas o restos numéricos huérfanos al inicio (p. ej. "...s ", "...,030,308")
  s = s.replace(/^[….\s,-]+(?:\d+[,.\d]*)?\s*/, '');
  // Quitar letras sueltas huérfanas al inicio de corte (p. ej. "...s ", "...o ")
  s = s.replace(/^[….\s,-]*[a-zA-ZáéíóúÁÉÍÓÚñÑ]{1,2}\s+/, '');
  // Quitar elipsis o símbolos al final
  s = s.replace(/[….\s,-]+$/, '');
  return s.trim();
}

/**
 * Detecta y extrae conceptos contables/financieros y sus cifras para presentarlos en tarjetas estructuradas.
 */
function extractFinancialMetrics(texto) {
  const cleaned = cleanPuntoText(texto);
  // Busca: (Concepto en mayúsculas/título) seguido de (1 a 4 cifras/porcentajes)
  const regex = /([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñÑ0-9\s()\/.-]{2,40}?)\s+((?:-?[\d,.]+%?\s*){1,4})(?=(?:[A-ZÁÉÍÓÚÑ]|$))/g;
  const metrics = [];
  let match;

  while ((match = regex.exec(cleaned)) !== null) {
    const concept = match[1].trim();
    const rawVals = match[2].trim().split(/\s+/).filter(Boolean);
    const hasFinancialNumber = rawVals.some(v => v.includes(',') || v.includes('%') || v.length >= 4);

    if (hasFinancialNumber && concept.length >= 3) {
      metrics.push({
        concepto: concept,
        cifras: rawVals.map(val => {
          const isPercent = val.endsWith('%');
          const isNegative = val.startsWith('-');
          return {
            raw: val,
            isPercent,
            isNegative,
            display: isPercent
              ? val
              : /^-?[\d,]+(?:\.\d+)?$/.test(val) && (val.includes(',') || val.length >= 4)
              ? (isNegative ? `-$${val.replace('-', '')}` : `$${val}`)
              : val
          };
        })
      });
    }
  }

  return { cleaned, metrics };
}

export default function Documento({ id, onVerPagina, onIr, onContexto }) {
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let interval;
    const fetchDoc = async () => {
      try {
        const d = await api.documento(id);
        setDoc(d);
        setError(null);
        onContexto?.(d.titulo);
        if (d.estatus !== 'listo' && d.estatus !== 'error') {
          interval = setTimeout(fetchDoc, 2000); // Polling every 2s
        }
      } catch (err) {
        setDoc(null);
        setError(err.message);
      }
    };
    fetchDoc();
    return () => clearTimeout(interval);
  }, [id, onContexto]);

  // Procesar puntos clave para presentación estructurada
  const puntosProcesados = useMemo(() => {
    if (!doc?.puntos_clave) return [];
    return doc.puntos_clave.map((p) => {
      const { cleaned, metrics } = extractFinancialMetrics(p.texto);
      return {
        ...p,
        textoLimpio: cleaned,
        metrics
      };
    });
  }, [doc?.puntos_clave]);

  if (error) {
    return (
      <div className="doc-error-container">
        <i className="fa-solid fa-triangle-exclamation" style={{ fontSize: '2.5rem', color: '#e67e22', marginBottom: '1rem' }}></i>
        <h3>No pudimos abrir este documento</h3>
        <p className="tenue">{error}</p>
        <button className="search-btn" onClick={() => onIr('/')} style={{ marginTop: '1.5rem' }}>
          Volver al Inicio
        </button>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="doc-loading-container">
        <i className="fa-solid fa-spinner fa-spin fa-2x" style={{ color: 'var(--accent-color)', marginBottom: '1rem' }}></i>
        <p style={{ fontWeight: 500 }}>Cargando expediente oficial...</p>
      </div>
    );
  }

  const fuente = doc.fuente || {};
  const esResumenFallback = doc.resumen?.includes('sin IA') || doc.resumen?.includes('Resumen automático');

  return (
    <div className="doc-container">
      {/* Miga de pan de navegación */}
      <nav className="migas">
        <button className="btn-link" onClick={() => onIr('/')}>Inicio</button> /{' '}
        <button className="btn-link" onClick={() => onIr(`/estado/${doc.estado.id}`)}>{doc.estado.nombre}</button>
        {doc.municipio && (
          <>
            {' '} / <button className="btn-link" onClick={() => onIr(`/municipio/${doc.municipio.id}`)}>{doc.municipio.nombre}</button>
          </>
        )}
      </nav>

      {/* Encabezado principal del documento */}
      <div className="doc-detail-header">
        <div className="doc-meta-pills">
          <span className="doc-pill-tag">
            <i className="fa-regular fa-folder" style={{ color: 'var(--accent-color)' }}></i> {doc.seccion.nombre}
          </span>
          <span className="doc-pill-tag">
            <i className="fa-solid fa-location-dot" style={{ color: '#10b981' }}></i>
            {doc.municipio?.nombre ? `${doc.municipio.nombre}, ${doc.estado.nombre}` : doc.estado.nombre}
          </span>
          {doc.anio && (
            <span className="doc-pill-tag">
              <i className="fa-regular fa-calendar"></i> Ejercicio {doc.anio}
            </span>
          )}
          {doc.total_paginas > 0 && (
            <span className="doc-pill-tag">
              <i className="fa-regular fa-file-lines"></i> {doc.total_paginas} páginas
            </span>
          )}
        </div>
        <h2 className="doc-main-title">{doc.titulo}</h2>
      </div>

      {/* Tarjeta de procedencia y fuente oficial */}
      {(fuente.dependencia || fuente.url_fuente || doc.pdf_url) && (
        <div className="doc-fuente-card">
          <div className="doc-fuente-info">
            <div className="doc-fuente-icon">
              <i className="fa-solid fa-shield-halved"></i>
            </div>
            <div>
              <strong style={{ fontSize: '0.95rem', color: 'var(--primary-color)' }}>Fuente Oficial del Expediente</strong>
              {fuente.dependencia && <p className="doc-fuente-dep">{fuente.dependencia}</p>}
              {fuente.fecha_publicacion && <span className="doc-fuente-fecha">Publicado: {fuente.fecha_publicacion}</span>}
            </div>
          </div>
          <div className="doc-fuente-actions">
            {doc.total_paginas > 0 && (
              <button className="btn-pag-nav" onClick={() => onVerPagina(doc.id, 1)} title="Abrir visor de páginas">
                <i className="fa-solid fa-table-cells"></i> Abrir visor interactivo
              </button>
            )}
            {doc.pdf_url && (
              <a href={doc.pdf_url} target="_blank" rel="noopener noreferrer" className="btn-doc-pdf">
                <i className="fa-regular fa-file-pdf"></i> Abrir PDF original
              </a>
            )}
            {fuente.url_fuente && (
              <a href={fuente.url_fuente} target="_blank" rel="noopener noreferrer" className="btn-doc-web">
                <i className="fa-solid fa-arrow-up-right-from-square"></i> Portal oficial
              </a>
            )}
          </div>
        </div>
      )}

      {/* Estado del procesamiento si aún no está listo */}
      {doc.estatus !== 'listo' ? (
        <div className="doc-procesando-card">
          <i className="fa-solid fa-spinner fa-spin fa-2x" style={{ color: 'var(--accent-color)', marginBottom: '1rem' }}></i>
          <p style={{ fontSize: '1.2rem', color: 'var(--primary-color)', fontWeight: 600 }}>Procesando documento...</p>
          <p className="tenue">La IA está digitalizando y analizando los datos ({doc.estatus}).</p>
        </div>
      ) : (
        <>
          {/* Ficha técnica y Resumen Ejecutivo */}
          <div className="doc-section-card">
            <div className="doc-section-header-row">
              <h3 className="doc-section-title">
                <i className="fa-solid fa-file-contract" style={{ color: 'var(--accent-color)' }}></i> Ficha de Síntesis y Resumen
              </h3>
              <span className="doc-status-badge">
                <i className="fa-solid fa-circle-check" style={{ color: '#10b981', marginRight: '5px' }}></i> Documento Oficial Indexado
              </span>
            </div>

            {/* Ficha informativa en cuadrícula limpia */}
            <div className="doc-ficha-grid">
              <div className="doc-ficha-item">
                <span className="doc-ficha-label"><i className="fa-solid fa-building-columns"></i> Dependencia</span>
                <strong className="doc-ficha-val">{fuente.dependencia || 'Gobierno Estatal / Municipal'}</strong>
              </div>
              <div className="doc-ficha-item">
                <span className="doc-ficha-label"><i className="fa-solid fa-calendar-days"></i> Período / Ejercicio</span>
                <strong className="doc-ficha-val">{doc.anio ? `Año Fiscal ${doc.anio}` : 'Vigente'}</strong>
              </div>
              <div className="doc-ficha-item">
                <span className="doc-ficha-label"><i className="fa-solid fa-file-lines"></i> Extensión</span>
                <strong className="doc-ficha-val">{doc.total_paginas > 0 ? `${doc.total_paginas} páginas` : 'Expediente digital'}</strong>
              </div>
              <div className="doc-ficha-item">
                <span className="doc-ficha-label"><i className="fa-solid fa-map-pin"></i> Cobertura</span>
                <strong className="doc-ficha-val">
                  {doc.municipio?.nombre ? `${doc.municipio.nombre}, ${doc.estado.nombre}` : doc.estado.nombre}
                </strong>
              </div>
            </div>

            {/* Cuerpo del Resumen */}
            <div className="doc-resumen-body">
              {esResumenFallback ? (
                <p className="doc-resumen-desc">
                  Este expediente oficial ha sido digitalizado e indexado para consulta ciudadana abierta. A continuación se desglosan los puntos clave, cifras y variaciones presupuestales detectadas en el documento, con acceso directo a la página original correspondiente.
                </p>
              ) : (
                <p className="doc-resumen-desc">{doc.resumen}</p>
              )}
            </div>
          </div>

          {/* Desglose de Puntos Clave y Cifras Extraídas */}
          <div className="doc-section-card" style={{ marginTop: '2rem' }}>
            <div className="doc-section-header-row">
              <h3 className="doc-section-title">
                <i className="fa-solid fa-chart-pie" style={{ color: 'var(--primary-color)' }}></i> Puntos y Cifras Clave del Documento
              </h3>
              <span className="tenue" style={{ fontSize: '0.85rem' }}>
                {puntosProcesados.length} {puntosProcesados.length === 1 ? 'extracto relevante' : 'extractos relevantes'}
              </span>
            </div>

            {puntosProcesados.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2.5rem 1rem' }}>
                <p className="tenue">No se detectaron cifras clave aisladas en este archivo.</p>
                {doc.total_paginas > 0 && (
                  <button className="btn-pag-nav" onClick={() => onVerPagina(doc.id, 1)} style={{ marginTop: '1rem' }}>
                    <i className="fa-regular fa-file-lines"></i> Explorar páginas del documento
                  </button>
                )}
              </div>
            ) : (
              <div className="doc-puntos-container">
                {puntosProcesados.map((p, i) => (
                  <div key={i} className="doc-punto-card">
                    <div className="doc-punto-header">
                      <div className="doc-punto-badge-num">
                        <span>{i + 1}</span>
                      </div>
                      <span className="doc-punto-tipo">
                        {p.metrics.length > 0 ? (
                          <>
                            <i className="fa-solid fa-coins" style={{ color: '#d97706', marginRight: '5px' }}></i>
                            Datos Financieros y Cifras
                          </>
                        ) : (
                          <>
                            <i className="fa-regular fa-bookmark" style={{ color: 'var(--accent-color)', marginRight: '5px' }}></i>
                            Extracto de Contenido
                          </>
                        )}
                      </span>
                      {p.pagina && (
                        <button
                          type="button"
                          className="btn-punto-pag"
                          onClick={() => onVerPagina(doc.id, p.pagina)}
                          title="Ver página original en el visor estructurado"
                        >
                          <i className="fa-regular fa-file-lines"></i> Pág. {p.pagina}
                        </button>
                      )}
                    </div>

                    {/* Si tiene métricas contables/financieras detectadas, mostrarlas en tarjetas limpias */}
                    {p.metrics.length > 0 ? (
                      <div className="doc-metrics-grid">
                        {p.metrics.map((m, mIdx) => (
                          <div key={mIdx} className="doc-metric-item">
                            <span className="doc-metric-concept">{m.concepto}</span>
                            <div className="doc-metric-values">
                              {m.cifras.map((c, cIdx) => (
                                <span
                                  key={cIdx}
                                  className={`doc-metric-tag ${c.isPercent ? (c.isNegative ? 'badge-down' : 'badge-up') : (c.isNegative ? 'num-neg' : 'num-pos')}`}
                                >
                                  {c.display}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="doc-punto-text">{p.textoLimpio}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
