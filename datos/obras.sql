-- Obras públicas georreferenciadas con auditoría de presupuesto y semáforo de anomalías
-- Todos los campos están completos (cero NULLs en documento_id, proveedor_id y contrato_id)

-- 1. Proveedores oficiales asignados a las obras
INSERT OR IGNORE INTO proveedores (id, nombre, rfc) VALUES
(1, 'Constructora Horizonte S.A. de C.V.', 'CHO010101AAA'),
(2, 'Iluminación del Bajío S.A. de C.V.', 'IBA020202BBB'),
(3, 'Hidráulica Regional S.A. de C.V.', 'HRE030303CCC'),
(4, 'Infraestructura Médica del Centro S.A. de C.V.', 'IMC150312DF1'),
(5, 'Drenajes y Conducciones del Bajío S.A. de C.V.', 'DCB180422KL3'),
(6, 'Edificaciones y Acabados de Guanajuato S.A. de C.V.', 'EAG190815MN8'),
(7, 'Electrificaciones y Alumbrados del Centro S.A. de C.V.', 'EAC200110PX9'),
(8, 'Pavimentaciones y Asfaltos de Guanajuato S.A. de C.V.', 'PAG160904TR2'),
(9, 'Caminos y Terracerías de la Sierra S.A. de C.V.', 'CTS170518UY7');

-- 2. Contratos vinculados a cada obra con foja de soporte documental
INSERT OR IGNORE INTO contratos (id, documento_id, pagina, proveedor_id, concepto, monto, fecha) VALUES
(1, 1, 2, 1, 'Pavimentación calle Hidalgo, colonia Centro (Irapuato)', 1850000.00, '2026-03-14'),
(2, 1, 3, 2, 'Luminarias LED en Calzada de los Insurgentes (Irapuato)', 580000.00, '2026-03-14'),
(3, 3, 1, 1, 'Rehabilitación y techado del Mercado Municipal (Irapuato)', 2750000.00, '2026-02-01'),
(4, 3, 2, 1, 'Banquetas accesibles en colonia San Juan (Irapuato)', 980000.00, '2026-02-01'),
(5, 3, 2, 3, 'Mantenimiento electromecánico de pozo de agua potable No. 8', 610000.00, '2026-02-01'),
(6, 2, 3, 1, 'Sustitución y ampliación de Unidad Médica Las Reinas (Irapuato)', 12200000.00, '2025-11-20'),
(7, 4, 2, 5, 'Construcción de colector sanitario norte y red de atarjeas (León)', 14200000.00, '2025-08-15'),
(8, 4, 2, 6, 'Rehabilitación de Oficialía de Registro Civil San José el Alto (León)', 1999775.30, '2025-09-10'),
(9, 2, 3, 7, 'Modernización de red de alumbrado público en Periférico Sur (Celaya)', 4250000.00, '2025-07-28'),
(10, 4, 2, 8, 'Mantenimiento mayor y pavimentación en Vialidad Diego Rivera (Guanajuato)', 5800000.00, '2025-05-12'),
(11, 4, 2, 9, 'Pavimentación de camino rural con huellas de piedra en Sierra Gorda (San Luis de la Paz)', 3100000.00, '2025-04-18');

-- 3. Catálogo de obras cívicas georreferenciadas con análisis de sobrecostos
INSERT OR IGNORE INTO obras (
    id, municipio_id, documento_id, pagina_fuente, proveedor_id, contrato_id,
    titulo, descripcion, categoria, estatus,
    latitud, longitud, direccion, colonia,
    presupuesto_aprobado, presupuesto_modificado, presupuesto_ejercido,
    variacion_porcentaje, nivel_alerta, analisis_alerta, anio
) VALUES
-- ================= IRAPUATO (municipio_id = 1) =================
(1, 1, 1, 2, 1, 1,
 'Pavimentación con concreto hidráulico Calle Hidalgo',
 'Rehabilitación integral de arroyo vehicular, banquetas y tomas domiciliarias.',
 'urbanizacion', 'concluida',
 20.6738, -101.3562, 'Calle Miguel Hidalgo entre Zaragoza y Obregón', 'Centro Histórico',
 1850000.00, 1850000.00, 1845200.00,
 -0.26, 'normal',
 'Monto ejercido dentro del presupuesto aprobado en Acta de Cabildo 12. En rango estándar de $1,250 MXN/m².',
 2026),

(2, 1, 1, 3, 2, 2,
 'Sustitución de Luminarias LED en Calzada de los Insurgentes',
 'Instalación de 140 postes y luminarias solares y LED de alta eficiencia.',
 'electrificacion', 'en_proceso',
 20.6812, -101.3445, 'Calzada de los Insurgentes tramo Paseo Las Huertas', 'Las Flores',
 420000.00, 580000.00, 560000.00,
 38.10, 'critico',
 'Sobrecosto del 38.1% sin adenda técnica justificada en cabildo. Costo unitario 45% arriba del precio de mercado.',
 2026),

(3, 1, 3, 1, 1, 3,
 'Rehabilitación y techado del Mercado Municipal',
 'Cambio de techumbre de asbesto por lámina termoacústica y piso epóxico comercial.',
 'urbanizacion', 'en_proceso',
 20.6789, -101.3510, 'Avenida 20 de Noviembre #104', 'Barrio de San Vicente',
 2300000.00, 2750000.00, 2700000.00,
 19.57, 'precaucion',
 'Incremento del 19.6% reportado por fallas en estructura previa. Requiere cotejo de bitácora de obra.',
 2026),

(4, 1, 3, 2, 1, 4,
 'Construcción de Guarniciones y Banquetas con Accesibilidad Universal',
 'Banquetas de concreto con rampas para personas con discapacidad visual y motriz.',
 'urbanizacion', 'concluida',
 20.6650, -101.3620, 'Calle Benito Juárez', 'San Juan',
 980000.00, 980000.00, 975000.00,
 -0.51, 'normal',
 'Obra concluida en tiempo y forma, en apego estricto a las especificaciones técnicas del contrato.',
 2026),

(5, 1, 3, 2, 3, 5,
 'Mantenimiento Mayor de Pozo de Agua Potable No. 8',
 'Equipamiento electromecánico y rehabilitación de columna de bombeo de 12 pulgadas.',
 'agua_drenaje', 'concluida',
 20.6905, -101.3735, 'Camino a Cuchicuato km 2', 'La Purísima',
 610000.00, 610000.00, 608500.00,
 -0.25, 'normal',
 'Monto unitario y refaccionamiento dentro del catálogo paramétrico de la Comisión Estatal del Agua.',
 2026),

(6, 1, 2, 3, 1, 6,
 'Unidad Médica y Clínica de Primer Nivel Irapuato Norte',
 'Sustitución y ampliación de Unidad Médica con 4 consultorios y área de urgencias básicas.',
 'salud', 'en_proceso',
 20.7020, -101.3380, 'Blvd. Gómez Morín s/n', 'Fracc. Las Reinas',
 8500000.00, 12200000.00, 11800000.00,
 43.53, 'critico',
 'Sobrecosto crítico del 43.5% derivado de retrasos contractuales y penalizaciones no aplicadas al contratista.',
 2025),

-- ================= LEÓN (municipio_id = 2) =================
(7, 2, 5, 2, 5, 7,
 'Colector Sanitario Norte y Red de Atarjeas',
 'Construcción de red de atarjeas y colector principal para atención a colonias periféricas.',
 'agua_drenaje', 'concluida',
 21.1620, -101.6850, 'Blvd. José María Morelos tramo Libramiento Norte', 'Gran Jardín',
 14200000.00, 14200000.00, 13950000.00,
 -1.76, 'normal',
 'Obra respaldada en FISM 2026 con avance del 95% auditado por SHCP sin inconsistencias.',
 2026),

(8, 2, 5, 2, 6, 8,
 'Rehabilitación de la Oficialía del Registro Civil San José el Alto',
 'Acondicionamiento de módulos de atención ciudadana y archivo digital.',
 'urbanizacion', 'planeada',
 21.0850, -101.6210, 'Calle Principal #45', 'San José el Alto',
 0.00, 1999775.30, 0.00,
 100.00, 'precaucion',
 'Obra con asignación no contemplada en el presupuesto original (Aprobado $0.00). Modificado de $1.99 MDP.',
 2025),

-- ================= CELAYA (municipio_id = 3) =================
(9, 3, 2, 3, 7, 9,
 'Modernización de Alumbrado y Red Eléctrica Periférico Sur',
 'Luminarias de alta potencia en entronque salida a Salvatierra.',
 'electrificacion', 'concluida',
 20.5050, -100.8250, 'Periférico Sur y Av. Lázaro Cárdenas', 'Rancho Seco',
 3400000.00, 4250000.00, 4210000.00,
 25.00, 'precaucion',
 'Variación del 25.0% en monto final adjudicado por aumento en volumen de cableado subterráneo.',
 2025),

-- ================= GUANAJUATO CAPITAL (municipio_id = 15) =================
(10, 15, 4, 2, 8, 10,
 'Conservación y Pavimentación en Vialidad Diego Rivera',
 'Mantenimiento correctivo de asfalto y estabilización de taludes carreteros.',
 'urbanizacion', 'concluida',
 21.0020, -101.2480, 'Acceso Diego Rivera km 4+200', 'Paseo de la Presa',
 5800000.00, 5800000.00, 5740000.00,
 -1.03, 'normal',
 'Ejecución respaldada en el Informe de Gobierno del Estado. Costos en rango normativo de SICOM.',
 2025),

-- ================= SAN LUIS DE LA PAZ (municipio_id = 32) =================
(11, 32, 4, 2, 9, 11,
 'Camino Rural con Huellas de Piedra Ahogada en Sierra Gorda',
 'Pavimentación de 4.2 km de camino rural para conectividad de comunidades de alta marginación.',
 'urbanizacion', 'concluida',
 21.2850, -100.5200, 'Camino a Mineral de Pozos tramo La Fragua', 'Comunidad El Bozo',
 3100000.00, 3100000.00, 3090000.00,
 -0.32, 'normal',
 'Fondo FISE Estatal, concluido al 100% con registro fotográfico georreferenciado verificado ante SHCP.',
 2025);
