"""Búsqueda de texto completo en las páginas (FTS5). La usan /api/buscar y el cerebro de /api/preguntar."""

import re
import sqlite3

Con = sqlite3.Connection


def filtros_sql(estado_id=None, municipio_id=None, seccion=None, documento_id=None):
    """Condiciones WHERE opcionales sobre documentos (d) y secciones (s)."""
    condiciones, params = [], []
    for valor, sql in (
        (estado_id, "d.estado_id = ?"),
        (municipio_id, "d.municipio_id = ?"),
        (seccion, "s.clave = ?"),
        (documento_id, "d.id = ?"),
    ):
        if valor is not None:
            condiciones.append(sql)
            params.append(valor)
    return "".join(f" AND {c}" for c in condiciones), params


def consulta_fts(texto: str) -> str:
    # Palabras de 3+ letras, entre comillas para que FTS5 no las interprete como operadores.
    palabras = [p for p in re.findall(r"\w+", texto, flags=re.UNICODE) if len(p) >= 3]
    return " OR ".join(f'"{p}"' for p in palabras)


def buscar_fragmentos(con: Con, texto: str, limite: int = 10, **filtros) -> list[dict]:
    consulta = consulta_fts(texto)
    if not consulta:
        return []
    where, params = filtros_sql(**filtros)
    filas = con.execute(
        f"""
        SELECT d.id AS documento_id, d.titulo AS documento_titulo, s.clave AS seccion,
               COALESCE(m.nombre, e.nombre) AS lugar, p.numero AS pagina,
               snippet(paginas_fts, 0, '[[', ']]', '…', 24) AS fragmento
        FROM paginas_fts
        JOIN paginas p ON p.id = paginas_fts.rowid
        JOIN documentos d ON d.id = p.documento_id
        JOIN secciones s ON s.id = d.seccion_id
        JOIN estados e ON e.id = d.estado_id
        LEFT JOIN municipios m ON m.id = d.municipio_id
        WHERE paginas_fts MATCH ?{where}
        ORDER BY bm25(paginas_fts)
        LIMIT ?
        """,
        (consulta, *params, limite),
    ).fetchall()
    return [dict(f) for f in filas]
