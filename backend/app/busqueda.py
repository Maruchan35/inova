"""Búsqueda de texto completo en las páginas (FTS5). La usan /api/buscar y el cerebro de /api/preguntar."""

import re
import sqlite3
import unicodedata

Con = sqlite3.Connection

# Palabras que no ayudan a encontrar la página correcta (aparecen en casi todas, o solo son la forma de preguntar).
VACIAS = set("""
que cual cuales cuanto cuanta cuantos cuantas como donde cuando quien quienes cuyo para por con sin sobre entre
desde hasta hacia segun durante los las del una uno unos unas este esta estos estas ese esa esos esas eso esto
aquel aquella hay fue fueron ser son era eran han has hace hizo tiene tienen tuvo mas muy sus les nos todo toda
todos todas otro otra otros otras tambien ademas pero porque pues algo alguna alguno algunos algunas mucho
mucha muchos muchas poco dime dame hablame habla explica explicame quiero quisiera saber informacion info datos
puedes podrias favor gracias hola oye compara comparar comparame comparacion comparativo comparativa versus
""".split())


def _sin_acentos(palabra: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", palabra.lower()) if not unicodedata.combining(c))


def filtros_sql(estado_id=None, municipio_id=None, seccion=None, documento_id=None, municipio_y_su_estado=None,
                documento_ids=None, solo_del_estado=None):
    """Condiciones WHERE opcionales sobre documentos (d) y secciones (s).

    `municipio_y_su_estado`: los documentos del municipio y los estatales de su estado (el chatbot pregunta así:
    un informe estatal trae datos de cada municipio). `solo_del_estado`: solo los del gobierno del estado."""
    condiciones, params = [], []
    if solo_del_estado is not None:
        condiciones.append("(d.municipio_id IS NULL AND d.estado_id = ?)")
        params.append(solo_del_estado)
    if municipio_y_su_estado is not None:
        condiciones.append("(d.municipio_id = ? OR (d.municipio_id IS NULL AND "
                           "d.estado_id = (SELECT estado_id FROM municipios WHERE id = ?)))")
        params += [municipio_y_su_estado, municipio_y_su_estado]
    if documento_ids:
        condiciones.append(f"d.id IN ({', '.join('?' * len(documento_ids))})")
        params += list(documento_ids)
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


def consulta_fts(texto: str, operador: str = "OR", excluir: frozenset = frozenset()) -> str:
    """Palabras de 3+ letras, entre comillas para que FTS5 no las interprete como operadores.

    Las de 5+ letras se buscan sin plural y como prefijo, para que el singular encuentre el plural y al revés:
    "becas" → "beca"* (beca, becas, becarios), "municipales" → "municipal"*.
    Se quitan las palabras vacías ("cuánto", "qué", "hay"...) y las de `excluir` (sin acentos)."""
    terminos = []
    for p in re.findall(r"\w+", texto, flags=re.UNICODE):
        if len(p) < 3 or _sin_acentos(p) in VACIAS or _sin_acentos(p) in excluir:
            continue
        if len(p) < 5:
            terminos.append(f'"{p}"')
            continue
        minus = p.lower()
        raiz = p[:-2] if len(p) >= 6 and minus.endswith("es") else p[:-1] if minus.endswith("s") else p
        terminos.append(f'"{raiz}"*')
    return f" {operador} ".join(dict.fromkeys(terminos))


def buscar_fragmentos(con: Con, texto: str, limite: int = 10, excluir: frozenset = frozenset(), **filtros) -> list[dict]:
    """Primero las páginas que tienen TODAS las palabras importantes; si no alcanzan, las que tienen alguna."""
    resultados, vistas = [], set()
    for operador in ("AND", "OR"):
        consulta = consulta_fts(texto, operador, excluir)
        if not consulta or len(resultados) >= limite:
            break
        for r in _buscar(con, consulta, limite, **filtros):
            if (r["documento_id"], r["pagina"]) not in vistas:
                vistas.add((r["documento_id"], r["pagina"]))
                resultados.append(r)
    return resultados[:limite]


def _buscar(con: Con, consulta: str, limite: int, **filtros) -> list[dict]:
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
