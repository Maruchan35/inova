-- Esquema de CabildoAbierto AI v2 (SQLite).
-- Documentos de gobierno organizados por estado → municipio → sección.
-- Responsable: bloque datos. Los cambios que afecten al backend se acuerdan en docs/api.md.

PRAGMA foreign_keys = ON;

CREATE TABLE estados (
    id          INTEGER PRIMARY KEY,
    nombre      TEXT NOT NULL UNIQUE,
    clave_inegi TEXT,
    latitud     REAL,
    longitud    REAL
);

CREATE TABLE municipios (
    id          INTEGER PRIMARY KEY,
    estado_id   INTEGER NOT NULL REFERENCES estados(id),
    nombre      TEXT NOT NULL,
    clave_inegi TEXT,
    latitud     REAL,
    longitud    REAL,
    UNIQUE (estado_id, nombre)
);

-- Lista fija de secciones; el frontend las muestra en este orden.
CREATE TABLE secciones (
    id     INTEGER PRIMARY KEY,
    clave  TEXT NOT NULL UNIQUE,   -- identificador para URLs y filtros: 'presupuesto'
    nombre TEXT NOT NULL,
    orden  INTEGER NOT NULL
);

-- Un documento oficial subido por un gobierno.
-- municipio_id NULL = documento del gobierno estatal.
CREATE TABLE documentos (
    id                INTEGER PRIMARY KEY,
    estado_id         INTEGER NOT NULL REFERENCES estados(id),
    municipio_id      INTEGER REFERENCES municipios(id),
    seccion_id        INTEGER NOT NULL REFERENCES secciones(id),
    titulo            TEXT NOT NULL,
    anio              INTEGER,
    fecha             TEXT,              -- ISO 8601: AAAA-MM-DD
    archivo           TEXT,              -- ruta del PDF/documento
    url_fuente        TEXT,              -- liga oficial de descarga/portal de transparencia
    formato           TEXT DEFAULT 'pdf',-- pdf, docx, xlsx, csv
    sha256            TEXT,              -- hash sha256 de verificación de integridad
    fecha_publicacion TEXT,              -- fecha oficial en periódico o portal
    dependencia       TEXT,              -- secretaría u órgano que lo emite
    total_paginas     INTEGER NOT NULL DEFAULT 0,
    -- Procesamiento (bloque backend): pendiente → procesando → listo | error
    estatus           TEXT NOT NULL DEFAULT 'pendiente'
                      CHECK (estatus IN ('pendiente', 'procesando', 'listo', 'error')),
    error             TEXT,              -- mensaje si estatus = 'error'
    resumen           TEXT,              -- resumen para el ciudadano, generado al procesar
    subido_en         TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Texto de cada página: es la unidad que se cita ("documento X, página N").
CREATE TABLE paginas (
    id           INTEGER PRIMARY KEY,
    documento_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    numero       INTEGER NOT NULL,
    texto        TEXT NOT NULL,
    UNIQUE (documento_id, numero)
);

-- Índice de búsqueda de texto completo, sin acentos ni mayúsculas.
CREATE VIRTUAL TABLE paginas_fts USING fts5(
    texto,
    content = 'paginas',
    content_rowid = 'id',
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER paginas_ai AFTER INSERT ON paginas BEGIN
    INSERT INTO paginas_fts(rowid, texto) VALUES (new.id, new.texto);
END;
CREATE TRIGGER paginas_ad AFTER DELETE ON paginas BEGIN
    INSERT INTO paginas_fts(paginas_fts, rowid, texto) VALUES ('delete', old.id, old.texto);
END;
CREATE TRIGGER paginas_au AFTER UPDATE ON paginas BEGIN
    INSERT INTO paginas_fts(paginas_fts, rowid, texto) VALUES ('delete', old.id, old.texto);
    INSERT INTO paginas_fts(rowid, texto) VALUES (new.id, new.texto);
END;

-- "Lo más importante" de cada documento, generado al procesar. Siempre con su página.
CREATE TABLE puntos_clave (
    id           INTEGER PRIMARY KEY,
    documento_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    orden        INTEGER NOT NULL,
    texto        TEXT NOT NULL,
    pagina       INTEGER
);

CREATE TABLE proveedores (
    id     INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    rfc    TEXT
);

CREATE TABLE contratos (
    id           INTEGER PRIMARY KEY,
    documento_id INTEGER REFERENCES documentos(id) ON DELETE SET NULL,
    pagina       INTEGER,            -- página del documento donde aparece
    proveedor_id INTEGER NOT NULL REFERENCES proveedores(id),
    concepto     TEXT NOT NULL,
    monto        REAL NOT NULL,      -- pesos MXN
    fecha        TEXT
);

CREATE INDEX idx_documentos_lugar ON documentos (estado_id, municipio_id, seccion_id);
CREATE INDEX idx_contratos_documento ON contratos (documento_id);

-- Obras públicas georreferenciadas para el mapa cívico de Guanajuato
CREATE TABLE obras (
    id                     INTEGER PRIMARY KEY,
    municipio_id           INTEGER NOT NULL REFERENCES municipios(id),
    documento_id           INTEGER REFERENCES documentos(id) ON DELETE SET NULL,
    pagina_fuente          INTEGER,            -- foja o página del documento que respalda la obra
    proveedor_id           INTEGER REFERENCES proveedores(id),
    contrato_id            INTEGER REFERENCES contratos(id),
    titulo                 TEXT NOT NULL,
    descripcion            TEXT,
    categoria              TEXT NOT NULL,      -- 'urbanizacion', 'agua_drenaje', 'electrificacion', 'educacion', 'salud', 'seguridad'
    estatus                TEXT NOT NULL DEFAULT 'en_proceso'
                           CHECK (estatus IN ('planeada', 'en_proceso', 'concluida', 'cancelada')),
    latitud                REAL NOT NULL,
    longitud               REAL NOT NULL,
    direccion              TEXT,
    colonia                TEXT,
    presupuesto_aprobado   REAL NOT NULL DEFAULT 0.0,
    presupuesto_modificado REAL NOT NULL DEFAULT 0.0,
    presupuesto_ejercido   REAL NOT NULL DEFAULT 0.0,
    variacion_porcentaje   REAL NOT NULL DEFAULT 0.0,
    nivel_alerta           TEXT NOT NULL DEFAULT 'normal'
                           CHECK (nivel_alerta IN ('normal', 'precaucion', 'critico')),
    analisis_alerta        TEXT,               -- justificación o explicación del semáforo
    anio                   INTEGER NOT NULL
);

CREATE INDEX idx_obras_municipio ON obras (municipio_id);
CREATE INDEX idx_obras_alerta ON obras (nivel_alerta);

-- Caché permanente de respuestas de IA para consultas ciudadanas frecuentes
CREATE TABLE respuestas (
    id         INTEGER PRIMARY KEY,
    clave      TEXT NOT NULL UNIQUE,   -- clave hash de [pregunta_normalizada, filtros, huella]
    pregunta   TEXT NOT NULL,
    respuesta  TEXT NOT NULL,
    citas_json TEXT,                   -- JSON con las citas exactas asociadas
    creado_en  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_respuestas_clave ON respuestas (clave);


