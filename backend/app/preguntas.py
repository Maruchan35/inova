"""El "cerebro" de /api/preguntar: responde con DeepSeek gastando lo menos posible.

1. Caché propio: la misma pregunta sobre los mismos documentos se responde una sola vez. Las demás
   personas reciben la respuesta guardada, y si llegan al mismo tiempo esperan a la primera.
   Vive en memoria y en la tabla `respuestas`, así que sobrevive a los reinicios del servidor.
2. Pregunta sobre un documento: se manda el documento completo, siempre primero y siempre igual,
   para aprovechar el caché de DeepSeek (la entrada que ya tiene guardada cuesta ~50 veces menos).
3. Pregunta sobre un lugar o una sección: solo las páginas más relevantes de la búsqueda.

Sin clave, o si la IA falla, se responde con las citas de la búsqueda: la demo nunca se cae.
"""

import hashlib
import json
import re
import sqlite3
import threading
import time
import unicodedata
from collections import OrderedDict, deque

from .busqueda import buscar_fragmentos, consulta_fts, filtros_sql
from .db import abrir
from .procesamiento import llm

MAX_CITAS = 5
PAGINAS_RELEVANTES = 6
MAX_CARACTERES_PAGINA = 6_000
MAX_CARACTERES_DOCUMENTO = 900_000  # ~300k tokens; si es más grande, solo van las páginas relevantes
MAX_RESPUESTAS = 1_000  # respuestas guardadas en memoria; se descartan las menos usadas
# Súbelo si cambian las instrucciones de la IA: así no se sirven respuestas guardadas con las anteriores.
VERSION_RESPUESTAS = 1

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


def limpiar_cache(tambien_guardadas: bool = True) -> None:
    """Vacía el caché en memoria y, si se pide, también el de la base (lo usan los tests)."""
    with _candado:
        _respuestas.clear()
        _candados.clear()
    if tambien_guardadas:
        con = abrir()
        try:
            con.execute("DELETE FROM respuestas")
            con.commit()
        except sqlite3.OperationalError:
            pass
        finally:
            con.close()


# Qué se le dice a la página sobre el origen de cada respuesta (campo "detalle").
ORIGEN_PUBLICO = {"DeepSeek": "ia", "caché propio": "cache", "respaldo sin IA": "sin_ia",
                  "búsqueda sin resultados": "sin_resultados", "sin pregunta": "sin_resultados"}


def responder(con: sqlite3.Connection, pregunta: str, **filtros) -> dict:
    """Respuesta con el formato de /api/preguntar, más "detalle": de dónde salió, cuánto tardó y cuánto costó."""
    registro = {"pregunta": pregunta.strip()[:500], "origen": None, "modo": None, "uso": {}, "aviso": None}
    resultado = _responder(con, registro, **filtros)
    resultado["detalle"] = {
        "origen": ORIGEN_PUBLICO.get(registro["origen"], "sin_ia"),
        "modo": registro["modo"],
        "segundos": registro["segundos"],
        "costo_usd": registro["costo_usd"],
        "alcance": registro.get("alcance", "lugar"),
        "motivo": ("La IA no está disponible en este momento; se muestran los fragmentos encontrados."
                   if registro["origen"] == "respaldo sin IA" else None),
    }
    return resultado


def _responder(con: sqlite3.Connection, registro: dict, **filtros) -> dict:
    inicio = time.time()
    pregunta = registro["pregunta"]
    try:
        if not normalizar(pregunta):
            registro["origen"] = "sin pregunta"
            return {"pregunta": pregunta, "respuesta": "Escribe una pregunta.", "citas": []}
        if not llm.configurado():
            registro["origen"], registro["aviso"] = "respaldo sin IA", "No hay DEEPSEEK_API_KEY en backend/.env"
            return _sin_ia(con, pregunta, filtros, registro)

        documento = _documento_completo(con, filtros.get("documento_id"))
        registro["modo"] = "documento completo" if documento else "páginas relevantes"
        clave = json.dumps([VERSION_RESPUESTAS, normalizar(pregunta), filtros, _huella(con, filtros)], sort_keys=True)
        with _candado_de(clave):  # si 300 personas preguntan lo mismo a la vez, solo la primera llama a la IA
            guardada = _leer(clave) or _leer_de_la_base(con, clave)
            if guardada:
                registro["origen"] = "caché propio"
                return {"pregunta": pregunta, **guardada}
            try:
                if documento:
                    resultado = _con_documento(con, pregunta, *documento, registro["uso"])
                else:
                    resultado = _con_paginas_relevantes(con, pregunta, filtros, registro["uso"], registro)
            except Exception as e:  # la IA falló: respaldo sin IA, y no se guarda para reintentar después
                registro["origen"] = "respaldo sin IA"
                registro["aviso"] = f"La IA falló ({type(e).__name__}: {e})"
                return _sin_ia(con, pregunta, filtros, registro)
            registro["origen"] = "DeepSeek" if registro["uso"] else "búsqueda sin resultados"
            _guardar(clave, resultado)
            _guardar_en_la_base(con, clave, pregunta, resultado)
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


def _clave_corta(clave: str) -> str:
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()


def _leer_de_la_base(con: sqlite3.Connection, clave: str) -> dict | None:
    """Respuesta guardada en la tabla `respuestas` (por ejemplo, de antes de reiniciar el servidor)."""
    try:
        fila = con.execute("SELECT respuesta, citas_json FROM respuestas WHERE clave = ?", (_clave_corta(clave),)).fetchone()
    except sqlite3.OperationalError:  # base vieja sin la tabla: solo caché en memoria
        return None
    if fila is None:
        return None
    resultado = {"respuesta": fila["respuesta"], "citas": json.loads(fila["citas_json"] or "[]")}
    _guardar(clave, resultado)
    return resultado


def _guardar_en_la_base(con: sqlite3.Connection, clave: str, pregunta: str, resultado: dict) -> None:
    try:
        con.execute(
            "INSERT OR REPLACE INTO respuestas (clave, pregunta, respuesta, citas_json) VALUES (?, ?, ?, ?)",
            (_clave_corta(clave), pregunta, resultado["respuesta"], json.dumps(resultado["citas"], ensure_ascii=False)),
        )
        con.commit()
    except sqlite3.Error:  # si no se puede guardar, sigue en memoria
        pass


def _huella(con: sqlite3.Connection, filtros: dict) -> list:
    """Cambia cuando se agrega o procesa un documento en ese lugar (o en cualquiera, por la búsqueda ampliada):
    así nunca se sirve una respuesta vieja."""
    where, params = filtros_sql(**_alcance(filtros))
    fila = con.execute(
        f"""
        SELECT COUNT(*), MAX(d.id), SUM(d.total_paginas)
        FROM documentos d JOIN secciones s ON s.id = d.seccion_id
        WHERE d.estatus = 'listo'{where}
        """,
        params,
    ).fetchone()
    total = con.execute("SELECT COUNT(*), MAX(id) FROM documentos WHERE estatus = 'listo'").fetchone()
    return list(fila) + list(total)


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


def _alcance(filtros: dict) -> dict:
    """En un municipio, el chatbot busca en sus documentos y en los estatales de su estado."""
    alcance = {k: v for k, v in filtros.items() if v is not None}
    if alcance.get("municipio_id") and not alcance.get("documento_id"):
        alcance["municipio_y_su_estado"] = alcance.pop("municipio_id")
    return alcance


def paginas_relevantes(con, pregunta: str, filtros: dict, registro: dict | None = None) -> list[dict]:
    """Las páginas que se le mandan a la IA (o que se muestran sin IA), con su texto.

    Primero en el lugar (municipio + estatales de su estado), y primero las que nombran al municipio.
    Si en el lugar no hay nada, busca en todo el catálogo y lo anota en `registro["alcance"] = "todo"`."""
    alcance = _alcance(filtros)
    candidatas = buscar_fragmentos(con, pregunta, limite=PAGINAS_RELEVANTES * 4, **alcance)
    if not candidatas and alcance:
        candidatas = buscar_fragmentos(con, pregunta, limite=PAGINAS_RELEVANTES * 4)
        if candidatas and registro is not None:
            registro["alcance"] = "todo"
    for c in candidatas:
        c["texto"] = con.execute(
            "SELECT texto FROM paginas WHERE documento_id = ? AND numero = ?", (c["documento_id"], c["pagina"])
        ).fetchone()["texto"]
    municipio_id = alcance.get("municipio_y_su_estado")
    if municipio_id:
        nombre = normalizar(con.execute("SELECT nombre FROM municipios WHERE id = ?", (municipio_id,)).fetchone()["nombre"])
        candidatas.sort(key=lambda c: nombre not in normalizar(c["texto"]))  # estable: respeta la relevancia
    return candidatas[:PAGINAS_RELEVANTES]


def _con_paginas_relevantes(con, pregunta: str, filtros: dict, uso: dict, registro: dict) -> dict:
    encontradas = paginas_relevantes(con, pregunta, filtros, registro)
    if not encontradas:  # nada que mandarle a la IA: se ahorra la llamada
        return {"respuesta": NO_ENCONTRE, "citas": []}
    fuentes, permitidas = [], {}
    for n, c in enumerate(encontradas, start=1):
        texto = c["texto"]
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


def _sin_ia(con, pregunta: str, filtros: dict, registro: dict | None = None) -> dict:
    consulta = consulta_fts(pregunta)
    citas = [_cita(con, c["documento_id"], c["pagina"], consulta)
             for c in paginas_relevantes(con, pregunta, filtros, registro)[:MAX_CITAS]]
    respuesta = f"Encontré {len(citas)} fragmento(s) relevante(s) en los documentos." if citas else NO_ENCONTRE
    return {"pregunta": pregunta, "respuesta": respuesta, "citas": citas}
