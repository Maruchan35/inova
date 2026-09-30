import React from 'react';

/**
 * Icono vectorial SVG de los 3 pilares con frontón clásico,
 * idéntico al emblema oficial de CabildoAbierto.
 */
export function LogoIcono({ size = 28, className = '' }) {
  const alto = Math.round((size * 58) / 72);
  return (
    <svg 
      xmlns="http://www.w3.org/2000/svg" 
      viewBox="0 0 72 58" 
      width={size} 
      height={alto} 
      className={`logo-pillars-icon ${className}`}
      fill="currentColor"
      aria-hidden="true"
      style={{ display: 'inline-block', verticalAlign: 'middle', flexShrink: 0 }}
    >
      <g>
        {/* Frontón triangular con remate */}
        <path d="M 36 2.5 L 68 18 L 4 18 Z" />
        {/* Óculo circular blanco en el tímpano */}
        <circle cx="36" cy="11" r="3.6" fill="var(--logo-oculo, #ffffff)" />
        {/* Entablamiento / Arquitrabe horizontal */}
        <rect x="2" y="19" width="68" height="3.8" rx="0.6" />
        {/* Columna Izquierda (Capitel, Fuste, Basa) */}
        <rect x="11" y="23.8" width="12" height="1.8" rx="0.4" />
        <rect x="13.2" y="25.6" width="7.6" height="18.8" />
        <rect x="11" y="44.4" width="12" height="1.8" rx="0.4" />
        {/* Columna Central (Capitel, Fuste, Basa) */}
        <rect x="30" y="23.8" width="12" height="1.8" rx="0.4" />
        <rect x="32.2" y="25.6" width="7.6" height="18.8" />
        <rect x="30" y="44.4" width="12" height="1.8" rx="0.4" />
        {/* Columna Derecha (Capitel, Fuste, Basa) */}
        <rect x="49" y="23.8" width="12" height="1.8" rx="0.4" />
        <rect x="51.2" y="25.6" width="7.6" height="18.8" />
        <rect x="49" y="44.4" width="12" height="1.8" rx="0.4" />
        {/* Estilóbato / Escalón 1 */}
        <rect x="5" y="47.5" width="62" height="3.2" rx="0.5" />
        {/* Estilóbato / Escalón 2 (Base inferior) */}
        <rect x="0.5" y="51.8" width="71" height="3.6" rx="0.6" />
      </g>
    </svg>
  );
}

/**
 * Componente principal de Logo con icono de pilares y tipografía CABILDOABIERTO.
 */
export default function Logo({ size = 30, texto = true, onClick, className = '' }) {
  return (
    <div 
      className={`logo interactive-logo ${className}`}
      onClick={onClick}
      title="Ir a Inicio - CabildoAbierto"
    >
      <LogoIcono size={size} />
      {texto && <span className="logo-brand-text">CABILDOABIERTO</span>}
    </div>
  );
}
