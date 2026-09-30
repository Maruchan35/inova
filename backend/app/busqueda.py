"""Búsqueda de texto completo en las páginas (FTS5). La usan /api/buscar y el cerebro de /api/preguntar."""

import re
import sqlite3

Con = sqlite3.Connection


def filtros_sql(estado_id=None, municipio_id=None, seccion=None, documento_id=None, municipio_y_su_estado=None):
    """Condiciones WHERE opcionales sobre documentos (d) y secciones (s).

    `municipio_y_su_estado`: los documentos del municipio y los estatales de su estado (el chatbot pregunta así:
    un informe estatal trae datos de cada municipio)."""
    condiciones, params = [], []
    if municipio_y_su_estado is not None:
        condiciones.append("(d.municipio_id = ? OR (d.municipio_id IS NULL AND "
                           "d.estado_id = (SELECT estado_id FROM municipios WHERE id = ?)))")
        params += [municipio_y_su_estado, municipio_y_su_estado]
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
    """Palabras de 3+ letras, entre comillas para que FTS5 no las interprete como operadores.

    Las de 5+ letras se buscan sin plural y como prefijo, para que el singular encuentre el plural y al revés:
    "becas" → "beca"* (beca, becas, becarios), "municipales" → "municipal"*."""
    terminos = []
    for p in re.findall(r"\w+", texto, flags=re.UNICODE):
        if len(p) < 3:
            continue
        if len(p) < 5:
            terminos.append(f'"{p}"')
            continue
        minus = p.lower()
        raiz = p[:-2] if len(p) >= 6 and minus.endswith("es") else p[:-1] if minus.endswith("s") else p
        terminos.append(f'"{raiz}"*')
    return " OR ".join(terminos)


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
