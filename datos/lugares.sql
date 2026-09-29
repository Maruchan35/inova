-- Catálogo de entidades federativas y municipios para CabildoAbierto AI.
-- Guanajuato (46 municipios completos) y Baja California.

INSERT OR IGNORE INTO estados (id, nombre) VALUES
(1, 'Guanajuato'),
(2, 'Baja California');

-- Municipios de Guanajuato (estado_id = 1)
INSERT OR IGNORE INTO municipios (id, estado_id, nombre) VALUES
(1, 1, 'Irapuato'),
(2, 1, 'León'),
(3, 1, 'Celaya'),
(4, 1, 'Abasolo'),
(5, 1, 'Acámbaro'),
(6, 1, 'Apaseo el Alto'),
(7, 1, 'Apaseo el Grande'),
(8, 1, 'Atarjea'),
(9, 1, 'Comonfort'),
(10, 1, 'Coroneo'),
(11, 1, 'Cortazar'),
(12, 1, 'Cuerámaro'),
(13, 1, 'Doctor Mora'),
(14, 1, 'Dolores Hidalgo Cuna de la Independencia Nacional'),
(15, 1, 'Guanajuato'),
(16, 1, 'Huanímaro'),
(17, 1, 'Jaral del Progreso'),
(18, 1, 'Jerécuaro'),
(19, 1, 'Manuel Doblado'),
(20, 1, 'Moroleón'),
(21, 1, 'Ocampo'),
(22, 1, 'Pénjamo'),
(23, 1, 'Pueblo Nuevo'),
(24, 1, 'Purísima del Rincón'),
(25, 1, 'Romita'),
(26, 1, 'Salamanca'),
(27, 1, 'Salvatierra'),
(28, 1, 'San Diego de la Unión'),
(29, 1, 'San Felipe'),
(30, 1, 'San Francisco del Rincón'),
(31, 1, 'San José Iturbide'),
(32, 1, 'San Luis de la Paz'),
(33, 1, 'San Miguel de Allende'),
(34, 1, 'Santa Catarina'),
(35, 1, 'Santa Cruz de Juventino Rosas'),
(36, 1, 'Santiago Maravatío'),
(37, 1, 'Silao de la Victoria'),
(38, 1, 'Tarandacuao'),
(39, 1, 'Tarimoro'),
(40, 1, 'Tierra Blanca'),
(41, 1, 'Uriangato'),
(42, 1, 'Valle de Santiago'),
(43, 1, 'Victoria'),
(44, 1, 'Villagrán'),
(45, 1, 'Xichú'),
(46, 1, 'Yuriria');

-- Municipios principales de Baja California (estado_id = 2)
INSERT OR IGNORE INTO municipios (id, estado_id, nombre) VALUES
(101, 2, 'Mexicali'),
(102, 2, 'Tijuana'),
(103, 2, 'Ensenada'),
(104, 2, 'Tecate'),
(105, 2, 'Playas de Rosarito'),
(106, 2, 'San Quintín'),
(107, 2, 'San Felipe');
