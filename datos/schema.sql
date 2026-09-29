-- Esquema de CabildoAbierto AI (SQLite).
-- Responsable: bloque datos. Los cambios que afecten al backend se acuerdan en docs/api.md.

PRAGMA foreign_keys = ON;

CREATE TABLE actas (
    id        INTEGER PRIMARY KEY,
    titulo    TEXT NOT NULL,
    fecha     TEXT,               -- ISO 8601: AAAA-MM-DD
    municipio TEXT,
    archivo   TEXT                -- nombre del PDF original
);

-- Texto de cada página: es la unidad que se cita ("acta X, página N").
CREATE TABLE paginas (
    id      INTEGER PRIMARY KEY,
    acta_id INTEGER NOT NULL REFERENCES actas(id) ON DELETE CASCADE,
    numero  INTEGER NOT NULL,
    texto   TEXT NOT NULL,
    UNIQUE (acta_id, numero)
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

CREATE TABLE proveedores (
    id     INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    rfc    TEXT
);

CREATE TABLE contratos (
    id           INTEGER PRIMARY KEY,
    acta_id      INTEGER REFERENCES actas(id) ON DELETE SET NULL,
    pagina       INTEGER,         -- página del acta donde se aprobó
    proveedor_id INTEGER NOT NULL REFERENCES proveedores(id),
    concepto     TEXT NOT NULL,
    monto        REAL NOT NULL,   -- pesos MXN
    fecha        TEXT
);
