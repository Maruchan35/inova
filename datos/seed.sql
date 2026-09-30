-- DATOS DE EJEMPLO (ficticios) para desarrollar mientras llegan los PDFs reales.
-- Los títulos llevan "(ejemplo)" para que nunca se confundan con información oficial.

INSERT INTO secciones (id, clave, nombre, orden) VALUES
(1, 'informes',    'Informes de gobierno',     1),
(2, 'presupuesto', 'Presupuesto y finanzas',   2),
(3, 'obras',       'Obras públicas',           3),
(4, 'actas',       'Actas de cabildo',         4),
(5, 'contratos',   'Contratos y licitaciones', 5);

INSERT OR IGNORE INTO estados (id, nombre) VALUES (1, 'Guanajuato');

INSERT OR IGNORE INTO municipios (id, estado_id, nombre) VALUES
(1, 1, 'Irapuato'),
(2, 1, 'León'),
(3, 1, 'Celaya');

INSERT INTO documentos (id, estado_id, municipio_id, seccion_id, titulo, anio, fecha, archivo, total_paginas, estatus, resumen) VALUES
(1, 1, 1, 4, 'Acta de Cabildo No. 12 (ejemplo)', 2026, '2026-03-14', 'ejemplo/acta-12.pdf', 3, 'listo',
 'Sesión ordinaria donde se aprobaron la pavimentación de la calle Hidalgo y la compra de luminarias LED.'),
(2, 1, 1, 2, 'Presupuesto de Egresos 2026 (ejemplo)', 2026, '2026-01-10', 'ejemplo/presupuesto-2026.pdf', 3, 'listo',
 'El municipio planea gastar 3,200 millones de pesos en 2026; la mayor parte va a seguridad y obra pública.'),
(3, 1, 1, 3, 'Programa de Obra Pública 2026 (ejemplo)', 2026, '2026-02-01', 'ejemplo/obra-2026.pdf', 2, 'listo',
 'Lista de obras del año: rehabilitación del mercado municipal, banquetas en San Juan y pozos de agua.'),
(4, 1, NULL, 1, 'Informe de Gobierno del Estado 2025 (ejemplo)', 2025, '2025-09-15', 'ejemplo/informe-estatal-2025.pdf', 2, 'listo',
 'El gobierno estatal reporta avances en salud, educación y carreteras durante 2025.'),
(5, 1, 2, 1, 'Informe de Gobierno Municipal 2025 (ejemplo)', 2025, '2025-10-01', 'ejemplo/informe-leon-2025.pdf', 0, 'pendiente', NULL);

INSERT INTO paginas (documento_id, numero, texto) VALUES
(1, 1, 'Siendo las 10:00 horas del 14 de marzo de 2026 se reúnen los integrantes del Honorable Ayuntamiento para la Sesión Ordinaria de Cabildo No. 12. Se declara quórum legal.'),
(1, 2, 'Punto cuarto. Se aprueba por mayoría la contratación de Constructora Horizonte S.A. de C.V. para la pavimentación de la calle Hidalgo en la colonia Centro, por un monto de $1,850,000.00 pesos.'),
(1, 3, 'Punto quinto. Se aprueba la adquisición de luminarias LED para la colonia Las Flores con Iluminación del Bajío S.A. de C.V. por $420,000.00 pesos. El regidor de hacienda solicita el expediente de la licitación.'),
(2, 1, 'Presupuesto de Egresos para el ejercicio fiscal 2026. Monto total autorizado: $3,200,000,000.00 pesos.'),
(2, 2, 'Distribución por rubro: seguridad pública 28%, obra pública 22%, servicios municipales 18%, salud 12%, educación y cultura 8%, administración 12%.'),
(2, 3, 'Se asignan $704,000,000.00 pesos a obra pública, incluyendo pavimentación, alumbrado y agua potable.'),
(3, 1, 'Programa anual de obra pública 2026. Rehabilitación del mercado municipal por $2,300,000.00 pesos adjudicada a Constructora Horizonte S.A. de C.V.'),
(3, 2, 'Construcción de banquetas en la colonia San Juan por $980,000.00 pesos (Constructora Horizonte S.A. de C.V.) y mantenimiento de pozos de agua potable por $610,000.00 pesos (Hidráulica Regional S.A. de C.V.).'),
(4, 1, 'Primer informe de gobierno del estado. En salud se abrieron 12 centros de atención y se ampliaron horarios en hospitales generales.'),
(4, 2, 'En infraestructura se modernizaron 140 kilómetros de carreteras estatales y se construyeron 35 escuelas.');

INSERT INTO puntos_clave (documento_id, orden, texto, pagina) VALUES
(1, 1, 'Se aprobó pavimentar la calle Hidalgo por $1.85 millones con Constructora Horizonte.', 2),
(1, 2, 'Se compraron luminarias LED para Las Flores por $420 mil.', 3),
(1, 3, 'Un regidor pidió revisar el expediente de la licitación de luminarias.', 3),
(2, 1, 'Presupuesto total 2026: $3,200 millones de pesos.', 1),
(2, 2, 'Seguridad pública recibe la mayor parte: 28%.', 2),
(2, 3, 'Obra pública recibe $704 millones.', 3),
(3, 1, 'La rehabilitación del mercado municipal cuesta $2.3 millones.', 1),
(3, 2, 'Constructora Horizonte tiene 2 de las 3 obras del programa.', 2),
(4, 1, 'Se abrieron 12 centros de salud.', 1),
(4, 2, 'Se modernizaron 140 km de carreteras y se construyeron 35 escuelas.', 2);

INSERT INTO proveedores (id, nombre, rfc) VALUES
(1, 'Constructora Horizonte S.A. de C.V.', 'CHO010101AAA'),
(2, 'Iluminación del Bajío S.A. de C.V.', 'IBA020202BBB'),
(3, 'Hidráulica Regional S.A. de C.V.', 'HRE030303CCC');

INSERT INTO contratos (documento_id, pagina, proveedor_id, concepto, monto, fecha) VALUES
(1, 2, 1, 'Pavimentación calle Hidalgo, colonia Centro', 1850000.00, '2026-03-14'),
(1, 3, 2, 'Luminarias LED colonia Las Flores', 420000.00, '2026-03-14'),
(3, 1, 1, 'Rehabilitación del mercado municipal', 2300000.00, '2026-02-01'),
(3, 2, 1, 'Banquetas colonia San Juan', 980000.00, '2026-02-01'),
(3, 2, 3, 'Mantenimiento de pozos de agua potable', 610000.00, '2026-02-01');
