-- DATOS DE EJEMPLO (ficticios) para desarrollar mientras llegan las actas reales.
-- Se reemplazan con la ingesta de PDFs reales (datos/ingesta.py).

INSERT INTO actas (id, titulo, fecha, municipio, archivo) VALUES
(1, 'Acta de la Sesión Ordinaria de Cabildo No. 12', '2026-03-14', 'Municipio de Ejemplo', 'acta-12.pdf'),
(2, 'Acta de la Sesión Extraordinaria de Cabildo No. 5', '2026-05-02', 'Municipio de Ejemplo', 'acta-ext-5.pdf');

INSERT INTO paginas (acta_id, numero, texto) VALUES
(1, 1, 'En la ciudad, siendo las 10:00 horas del 14 de marzo de 2026, se reúnen los integrantes del Honorable Ayuntamiento para celebrar la Sesión Ordinaria de Cabildo No. 12. Se pasa lista de asistencia y se declara quórum legal.'),
(1, 2, 'Punto cuarto. Se aprueba por mayoría la contratación de Constructora Horizonte S.A. de C.V. para la pavimentación de la calle Hidalgo en la colonia Centro, por un monto de $1,850,000.00 pesos con recursos del Fondo de Infraestructura Social.'),
(1, 3, 'Punto quinto. Se aprueba la adquisición de luminarias LED para la colonia Las Flores con el proveedor Iluminación del Bajío S.A. de C.V. por un monto de $420,000.00 pesos. El regidor de hacienda solicita el expediente de la licitación.'),
(2, 1, 'Sesión Extraordinaria de Cabildo No. 5 celebrada el 2 de mayo de 2026. Único punto: obras prioritarias del presupuesto participativo.'),
(2, 2, 'Se aprueba por adjudicación directa la rehabilitación del mercado municipal a Constructora Horizonte S.A. de C.V. por $2,300,000.00 pesos, y la construcción de banquetas en la colonia San Juan a la misma empresa por $980,000.00 pesos.'),
(2, 3, 'Se aprueba el mantenimiento de pozos de agua potable con Hidráulica Regional S.A. de C.V. por $610,000.00 pesos. La síndica municipal vota en contra señalando falta de cotizaciones.');

INSERT INTO proveedores (id, nombre, rfc) VALUES
(1, 'Constructora Horizonte S.A. de C.V.', 'CHO010101AAA'),
(2, 'Iluminación del Bajío S.A. de C.V.', 'IBA020202BBB'),
(3, 'Hidráulica Regional S.A. de C.V.', 'HRE030303CCC');

INSERT INTO contratos (acta_id, pagina, proveedor_id, concepto, monto, fecha) VALUES
(1, 2, 1, 'Pavimentación calle Hidalgo, colonia Centro', 1850000.00, '2026-03-14'),
(1, 3, 2, 'Luminarias LED colonia Las Flores', 420000.00, '2026-03-14'),
(2, 2, 1, 'Rehabilitación del mercado municipal', 2300000.00, '2026-05-02'),
(2, 2, 1, 'Banquetas colonia San Juan', 980000.00, '2026-05-02'),
(2, 3, 3, 'Mantenimiento de pozos de agua potable', 610000.00, '2026-05-02');
