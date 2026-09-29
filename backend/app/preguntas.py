"""El "cerebro" de /api/preguntar: responde con DeepSeek gastando lo menos posible.

1. Caché propio: la misma pregunta sobre los mismos documentos se responde una sola vez. Las demás
   personas reciben la respuesta guardada, y si llegan al mismo tiempo esperan a la primera.
2. Pregunta sobre un documento: se manda el documento completo, siempre primero y siempre igual,
   para aprovechar el caché de DeepSeek (la entrada que ya tiene guardada cuesta ~50 veces menos).
3. Pregunta sobre un lugar o una sección: solo las páginas más relevantes de la búsqueda.

Sin clave, o si la IA falla, se responde con las citas de la búsqueda: la demo nunca se cae.
El caché vive en memoria: se vacía al reiniciar el servidor.
"""

import json
import re
import sqlite3
import threading
import time
import unicodedata
from collections import OrderedDict, deque

from .busqueda import buscar_fragmentos, consulta_fts, filtros_sql
from .procesamiento import llm

MAX_CITAS = 5
PAGINAS_RELEVANTES = 6
MAX_CARACTERES_PAGINA = 6_000
MAX_CARACTERES_DOCUMENTO = 900_000  # ~300k tokens; si es más grande, solo van las páginas relevantes
MAX_RESPUESTAS = 1_000  # respuestas guardadas en memoria; se descartan las menos usadas

NO_ENCONTRE = "No encontré información sobre eso en los documentos cargados."

SISTEMA = (
    "Eres un asistente que responde preguntas de ciudadanos sobre documentos oficiales de gobiernos de México. "
    "Usa únicamente la información de los documentos que se te dan; si la respuesta no está ahí, dilo y no "
    "inventes nada. Responde en español sencillo, en 1 a 4 frases, con las cifras exactas del documento cuando "
    "existan. "
    "No des opiniones políticas ni juicios sobre personas o partidos. Responde solo con JSON válido."
)

FORMATO = (
    'Devuelve JSON con esta forma: {{"encontrado": true, "respuesta": "...", "fuentes": [N]}}. '
    "'fuentes': {que_es} de donde sale cada dato de tu respuesta (máximo 5). Si los textos no traen ningún "
    "dato sobre la pregunta, devuelve encontrado false, explícalo en 'respuesta' y deja 'fuentes' vacío. Si solo "
    "la responden en parte, da lo que sí dicen, con sus fuentes. "
    "Importante: copia cada cifra tal como aparece en el texto. No hagas operaciones: si el texto da un "
    "porcentaje, responde con el porcentaje y no lo conviertas a pesos."
)
FORMATO_DOCUMENTO = FORMATO.format(que_es="los números de [Página N]")
FORMATO_FUENTES = FORMATO.format(que_es="los números de [Fuente N]")

# Últimas preguntas, para la página de prueba y la vista previa: de dónde salió cada respuesta y cuánto costó.
BITACORA: deque = deque(maxlen=50)

_respuestas: OrderedDict[str, dict] = OrderedDict()
_candados: dict[str, threading.Lock] = {}
_candado = threading.Lock()


def normalizar(texto: str) -> str:
    """'¿Cuánto costó el Mercado?' → 'cuanto costo el mercado': la misma pregunta escrita distinto."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", sin_acentos.casefold()))


def limpiar_cache() -> None:
    with _candado:
        _respuestas.clear()
        _candados.clear()


def responder(con: sqlite3.Connection, pregunta: str, **filtros) -> dict:
    inicio = time.time()
    pregunta = pregunta.strip()[:500]
    registro = {"pregunta": pregunta, "origen": None, "modo": None, "uso": {}, "aviso": None}
    try:
        if not normalizar(pregunta):
            registro["origen"] = "sin pregunta"
            return {"pregunta": pregunta, "respuesta": "Escribe una pregunta.", "citas": []}
        if not llm.configurado():
            registro["origen"], registro["aviso"] = "respaldo sin IA", "No hay DEEPSEEK_API_KEY en backend/.env"
            return _sin_ia(con, pregunta, filtros)

        documento = _documento_completo(con, filtros.get("documento_id"))
        registro["modo"] = "documento completo" if documento else "páginas relevantes"
        clave = json.dumps([normalizar(pregunta), filtros, _huella(con, filtros)], sort_keys=True)
        with _candado_de(clave):  # si 300 personas preguntan lo mismo a la vez, solo la primera llama a la IA
            guardada = _leer(clave)
            if guardada:
                registro["origen"] = "caché propio"
                return {"pregunta": pregunta, **guardada}
            try:
                if documento:
                    resultado = _con_documento(con, pregunta, *documento, registro["uso"])
                else:
                    resultado = _con_paginas_relevantes(con, pregunta, filtros, registro["uso"])
            except Exception as e:  # la IA falló: respaldo sin IA, y no se guarda para reintentar después
                registro["origen"] = "respaldo sin IA"
                registro["aviso"] = f"La IA falló ({type(e).__name__}: {e})"
                return _sin_ia(con, pregunta, filtros)
            registro["origen"] = "DeepSeek" if registro["uso"] else "búsqueda sin resultados"
            _guardar(clave, resultado)
            return {"pregunta": pregunta, **resultado}
    finally:
        registro["segundos"] = round(time.time() - inicio, 2)
        registro["costo_usd"] = round(llm.costo_usd(registro["uso"]), 6)
        BITACORA.appendleft(registro)


# --- Caché propio ---


def _candado_de(clave: str) -> threading.Lock:
    with _candado:
        return _candados.setdefault(clave, threading.Lock())


def _leer(clave: str) -> dict | None:
    with _candado:
        if clave in _respuestas:
            _respuestas.move_to_end(clave)
            return _respuestas[clave]
    return None


def _guardar(clave: str, resultado: dict) -> None:
    with _candado:
        _respuestas[clave] = resultado
        while len(_respuestas) > MAX_RESPUESTAS:
            viejo, _ = _respuestas.popitem(last=False)
            _candados.pop(viejo, None)


def _huella(con: sqlite3.Connection, filtros: dict) -> list:
    """Cambia cuando se agrega o procesa un documento en ese lugar: así nunca se sirve una respuesta vieja."""
    where, params = filtros_sql(**filtros)
    fila = con.execute(
        f"""
        SELECT COUNT(*), MAX(d.id), SUM(d.total_paginas)
        FROM documentos d JOIN secciones s ON s.id = d.seccion_id
        WHERE d.estatus = 'listo'{where}
        """,
        params,
    ).fetchone()
    return list(fila)


# --- Los dos modos de preguntar ---


def _documento_completo(con: sqlite3.Connection, documento_id: int | None) -> tuple | None:
    """(id, título, [(número, texto)]) si la pregunta es sobre un documento que cabe completo."""
    if documento_id is None:
        return None
    doc = con.execute("SELECT id, titulo FROM documentos WHERE id = ? AND estatus = 'listo'", (documento_id,)).fetchone()
    if doc is None:
        return None
    paginas = con.execute(
        "SELECT numero, texto FROM paginas WHERE documento_id = ? ORDER BY numero", (documento_id,)
    ).fetchall()
    if not paginas or sum(len(p["texto"]) for p in paginas) > MAX_CARACTERES_DOCUMENTO:
        return None
    return doc["id"], doc["titulo"], [(p["numero"], p["texto"]) for p in paginas]


def _con_documento(con, pregunta: str, documento_id: int, titulo: str, paginas: list, uso: dict) -> dict:
    # El documento va primero y siempre igual; la pregunta, al final. Así DeepSeek reutiliza su caché.
    texto = "".join(f"[Página {n}]\n{t.strip()}\n\n" for n, t in paginas)
    usuario = f"DOCUMENTO: {titulo}\n\n{texto}{FORMATO_DOCUMENTO}\n\nPREGUNTA: {pregunta}"
    permitidas = {n: (documento_id, n) for n, _ in paginas}
    return _resultado(con, pregunta, llm.pedir_json(SISTEMA, usuario, uso), permitidas)


def _con_paginas_relevantes(con, pregunta: str, filtros: dict, uso: dict) -> dict:
    encontradas = buscar_fragmentos(con, pregunta, limite=PAGINAS_RELEVANTES, **filtros)
    if not encontradas:  # nada que mandarle a la IA: se ahorra la llamada
        return {"respuesta": NO_ENCONTRE, "citas": []}
    fuentes, permitidas = [], {}
    for n, c in enumerate(encontradas, start=1):
        texto = con.execute(
            "SELECT texto FROM paginas WHERE documento_id = ? AND numero = ?", (c["documento_id"], c["pagina"])
        ).fetchone()["texto"]
        fuentes.append(f"[Fuente {n}] {c['documento_titulo']} ({c['lugar']}), página {c['pagina']}:\n"
                       f"{texto.strip()[:MAX_CARACTERES_PAGINA]}\n")
        permitidas[n] = (c["documento_id"], c["pagina"])
    usuario = "FUENTES:\n\n" + "\n".join(fuentes) + f"\n{FORMATO_FUENTES}\n\nPREGUNTA: {pregunta}"
    return _resultado(con, pregunta, llm.pedir_json(SISTEMA, usuario, uso), permitidas)


def _resultado(con, pregunta: str, datos: dict, permitidas: dict) -> dict:
    """Valida lo que devolvió la IA: toda respuesta con datos tiene que traer al menos una página válida."""
    respuesta = str(datos.get("respuesta") or "").strip()
    elegidas = []
    for f in datos.get("fuentes") or []:
        try:
            ref = permitidas.get(int(f))
        except (TypeError, ValueError):
            continue
        if ref and ref not in elegidas:  # se descarta cualquier página que no le mandamos
            elegidas.append(ref)
    if datos.get("encontrado") is False and not elegidas:
        return {"respuesta": respuesta or NO_ENCONTRE, "citas": []}
    if not respuesta or not elegidas:
        raise ValueError("La IA respondió sin decir de qué página sale el dato")
    consulta = consulta_fts(pregunta)
    return {"respuesta": respuesta, "citas": [_cita(con, d, p, consulta) for d, p in elegidas[:MAX_CITAS]]}


def _cita(con, documento_id: int, pagina: int, consulta: str) -> dict:
    """Una cita con el mismo formato que los resultados de /api/buscar."""
    fila = con.execute(
        """
        SELECT p.id, p.texto, d.id AS documento_id, d.titulo AS documento_titulo, s.clave AS seccion,
               COALESCE(m.nombre, e.nombre) AS lugar, p.numero AS pagina
        FROM paginas p
        JOIN documentos d ON d.id = p.documento_id
        JOIN secciones s ON s.id = d.seccion_id
        JOIN estados e ON e.id = d.estado_id
        LEFT JOIN municipios m ON m.id = d.municipio_id
        WHERE p.documento_id = ? AND p.numero = ?
        """,
        (documento_id, pagina),
    ).fetchone()
    fragmento = None
    if consulta:  # el fragmento de esa página donde aparecen las palabras de la pregunta
        f = con.execute(
            "SELECT snippet(paginas_fts, 0, '[[', ']]', '…', 24) FROM paginas_fts WHERE paginas_fts MATCH ? AND rowid = ?",
            (consulta, fila["id"]),
        ).fetchone()
        fragmento = f[0] if f else None
    if not fragmento:
        texto = " ".join(fila["texto"].split())
        fragmento = texto[:200] + ("…" if len(texto) > 200 else "")
    return {**{k: fila[k] for k in ("documento_id", "documento_titulo", "seccion", "lugar", "pagina")}, "fragmento": fragmento}


def _sin_ia(con, pregunta: str, filtros: dict) -> dict:
    citas = buscar_fragmentos(con, pregunta, limite=MAX_CITAS, **filtros)
    respuesta = f"Encontré {len(citas)} fragmento(s) relevante(s) en los documentos." if citas else NO_ENCONTRE
    return {"pregunta": pregunta, "respuesta": respuesta, "citas": citas}
