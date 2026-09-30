"""El "cerebro" de /api/preguntar: responde con DeepSeek gastando lo menos posible.

1. Caché propio: la misma pregunta sobre los mismos documentos se responde una sola vez. Las demás
   personas reciben la respuesta guardada, y si llegan al mismo tiempo esperan a la primera.
   Vive en memoria y en la tabla `respuestas`, así que sobrevive a los reinicios del servidor.
2. Pregunta sobre un documento: se manda el documento completo, siempre primero y siempre igual,
   para aprovechar el caché de DeepSeek (la entrada que ya tiene guardada cuesta ~50 veces menos).
3. Pregunta sobre un lugar o una sección: solo las páginas más relevantes de la búsqueda.
4. Verificador de cifras: cada cifra de la respuesta tiene que estar en las páginas que vio la IA.
5. Memoria: "¿y en León?" sigue el tema de la pregunta anterior. "Compara X y Y" junta fuentes de cada lugar.
6. Tope de gasto diario en IA (DEEPSEEK_TOPE_DIARIO_USD): al llegar, responde sin IA hasta el día siguiente.

Sin clave, o si la IA falla, se responde con las citas de la búsqueda: la demo nunca se cae.
"""

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
import unicodedata
from collections import OrderedDict, deque
from pathlib import Path

from . import config
from .busqueda import VACIAS, buscar_fragmentos, consulta_fts, filtros_sql
from .entender import entender
from .db import abrir
from .procesamiento import llm

MAX_CITAS = 5
PAGINAS_RELEVANTES = 6
MAX_CARACTERES_PAGINA = 6_000
MAX_CARACTERES_DOCUMENTO = 900_000  # ~300k tokens; si es más grande, solo van las páginas relevantes
MAX_RESPUESTAS = 1_000  # respuestas guardadas en memoria; se descartan las menos usadas
# Súbelo si cambian las instrucciones de la IA: así no se sirven respuestas guardadas con las anteriores.
VERSION_RESPUESTAS = 5  # 5: títulos reclasificados, verificador de cifras, memoria, comparaciones, sin "(Fuente N)"

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
    "la responden en parte, da lo que sí dicen, con sus fuentes: todo dato o cifra que menciones lleva su fuente, "
    "aunque encontrado sea false. "
    "Importante: copia cada cifra tal como aparece en el texto. No hagas operaciones: si el texto da un "
    "porcentaje, responde con el porcentaje y no lo conviertas a pesos. No escribas '(Fuente N)' dentro de "
    "'respuesta': las fuentes se le muestran a la persona aparte."
)
# Por si la IA lo escribe de todos modos: "(Fuente 1)", "(Fuentes 4, 5 y 6)", "[Fuente 2]".
MENCION_DE_FUENTE = re.compile(r"\s*[(\[]\s*fuentes?\s*\d+(?:\s*(?:,|y)\s*\d+)*\s*[)\]]", re.IGNORECASE)
FORMATO_DOCUMENTO = FORMATO.format(que_es="los números de [Página N]")
FORMATO_FUENTES = FORMATO.format(que_es="los números de [Fuente N]")
FORMATO_COMPARACION = FORMATO_FUENTES + (
    " La persona quiere comparar lugares: en 'respuesta' compara lugar por lugar con las cifras de las fuentes. "
    "Si de algún lugar no hay datos, dilo. No calcules diferencias, sumas ni porcentajes que no estén en las fuentes."
)
FORMATO_PANORAMA = FORMATO_FUENTES + (
    " La persona pide un panorama, no un dato: en 'respuesta' (3 a 6 frases) di qué documento es (o cuáles hay, "
    "si son varios), de qué trata y lo más importante, con cifras cuando existan. Si ninguno es exactamente lo que "
    "pide (por ejemplo, pide el informe del gobierno del estado y solo hay informes de alcaldías), dilo claramente "
    "y di qué hay en su lugar."
)

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


def responder(con: sqlite3.Connection, pregunta: str, historial: list | None = None, **filtros) -> dict:
    """Respuesta con el formato de /api/preguntar, más "detalle": de dónde salió, cuánto tardó y cuánto costó.

    `historial`: preguntas y respuestas anteriores de la conversación ([{"pregunta", "respuesta"}]), para
    entender seguimientos como "¿y en León?"."""
    registro = {"pregunta": pregunta.strip()[:500], "origen": None, "modo": None, "uso": {}, "aviso": None,
                "motivo": None, "busqueda": None}
    resultado = _responder(con, registro, historial or [], **filtros)
    resultado.setdefault("documentos", [])
    cifras_sin_verificar = resultado.pop("cifras_sin_verificar", [])
    entendido = resultado.pop("entendido", None)
    resultado["detalle"] = {
        "entendido": entendido,
        "origen": ORIGEN_PUBLICO.get(registro["origen"], "sin_ia"),
        "modo": registro["modo"],
        "segundos": registro["segundos"],
        "costo_usd": registro["costo_usd"],
        "alcance": registro.get("alcance", "lugar"),
        "motivo": registro["motivo"] or ("La IA no está disponible en este momento; se muestran los fragmentos "
                                         "encontrados." if registro["origen"] == "respaldo sin IA" else None),
        "cifras_sin_verificar": cifras_sin_verificar,
    }
    return resultado


def _responder(con: sqlite3.Connection, registro: dict, historial: list, **filtros) -> dict:
    inicio = time.time()
    pregunta = registro["pregunta"]
    try:
        if not normalizar(pregunta):
            registro["origen"] = "sin pregunta"
            return {"pregunta": pregunta, "respuesta": "Escribe una pregunta.", "citas": []}
        # "¿y en León?" se busca con el tema de la conversación; a la IA le llegan la pregunta tal cual y el contexto
        busqueda, contexto = _seguimiento(con, pregunta, historial)
        if busqueda != pregunta:
            registro["busqueda"] = busqueda
        if not llm.configurado():
            registro["origen"], registro["aviso"] = "respaldo sin IA", "No hay DEEPSEEK_API_KEY en backend/.env"
            return _sin_ia(con, busqueda, filtros, registro, pregunta)

        documento = _documento_completo(con, filtros.get("documento_id"))
        registro["modo"] = "documento completo" if documento else "páginas relevantes"
        # La conversación entra a la clave: una "respuesta anterior" inventada por alguien no le llega a nadie más.
        clave = json.dumps([VERSION_RESPUESTAS, _clave_pregunta(busqueda), filtros, _huella(con, filtros),
                            _clave_corta(contexto)[:16] if contexto else ""], sort_keys=True)
        with _candado_de(clave):  # si 300 personas preguntan lo mismo a la vez, solo la primera llama a la IA
            guardada = _leer(clave) or _leer_de_la_base(con, clave)
            if guardada:
                registro["origen"] = "caché propio"
                return {"pregunta": pregunta, **guardada}
            if gasto_de_hoy() >= tope_diario():  # nadie puede acabarse el saldo de DeepSeek desde el enlace público
                registro["origen"] = "respaldo sin IA"
                registro["motivo"] = "Se alcanzó el tope diario de gasto en IA; se muestran los fragmentos encontrados."
                return _sin_ia(con, busqueda, filtros, registro, pregunta)
            try:
                if documento:
                    resultado = _con_documento(con, pregunta, *documento, registro["uso"], contexto, busqueda)
                else:
                    plan = _preparar(con, busqueda, filtros, pregunta)
                    plan["contexto"] = contexto
                    if plan["entendido"]["comparacion"]:
                        registro["modo"] = "comparación"
                        resultado = _con_comparacion(con, pregunta, plan, registro["uso"])
                    elif plan["entendido"]["panorama"] and plan["documentos"]:
                        registro["modo"] = "panorama"
                        resultado = _con_panorama(con, pregunta, plan, registro["uso"])
                    else:
                        resultado = _con_paginas_relevantes(con, pregunta, plan["filtros"], registro["uso"], registro,
                                                            plan)
                    resultado["documentos"] = [_documento_publico(d) for d in plan["documentos"]]
                    resultado["entendido"] = _entendido_publico(con, plan["entendido"])
            except Exception as e:  # la IA falló: respaldo sin IA, y no se guarda para reintentar después
                registro["origen"] = "respaldo sin IA"
                registro["aviso"] = f"La IA falló ({type(e).__name__}: {e})"
                return _sin_ia(con, busqueda, filtros, registro, pregunta)
            finally:
                if registro["uso"]:
                    sumar_gasto(llm.costo_usd(registro["uso"]))
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
    guardado = json.loads(fila["citas_json"] or "[]")
    if isinstance(guardado, list):  # formato viejo: solo citas
        guardado = {"citas": guardado}
    resultado = {"respuesta": fila["respuesta"], **guardado}
    _guardar(clave, resultado)
    return resultado


def _guardar_en_la_base(con: sqlite3.Connection, clave: str, pregunta: str, resultado: dict) -> None:
    try:
        con.execute(
            "INSERT OR REPLACE INTO respuestas (clave, pregunta, respuesta, citas_json) VALUES (?, ?, ?, ?)",
            (_clave_corta(clave), pregunta, resultado["respuesta"],
             json.dumps({k: v for k, v in resultado.items() if k != "respuesta"}, ensure_ascii=False)),
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


def _con_documento(con, pregunta: str, documento_id: int, titulo: str, paginas: list, uso: dict,
                   contexto: str = "", busqueda: str | None = None) -> dict:
    # El documento va primero y siempre igual; la conversación y la pregunta, al final: DeepSeek reutiliza su caché.
    texto = "".join(f"[Página {n}]\n{t.strip()}\n\n" for n, t in paginas)
    usuario = f"DOCUMENTO: {titulo}\n\n{texto}{contexto}{FORMATO_DOCUMENTO}\n\nPREGUNTA: {pregunta}"
    permitidas = {n: (documento_id, n) for n, _ in paginas}
    textos = {(documento_id, n): t for n, t in paginas}
    return _resultado(con, busqueda or pregunta, llm.pedir_json(SISTEMA, usuario, uso), permitidas, textos,
                      f"{titulo}\n{pregunta}")


def _alcance(filtros: dict) -> dict:
    """En un municipio, el chatbot busca en sus documentos y en los estatales de su estado."""
    alcance = {k: v for k, v in filtros.items() if v is not None}
    if alcance.get("municipio_id") and not alcance.get("documento_id"):
        alcance["municipio_y_su_estado"] = alcance.pop("municipio_id")
    return alcance


def paginas_relevantes(con, pregunta: str, filtros: dict, registro: dict | None = None,
                       plan: dict | None = None) -> list[dict]:
    """Las páginas que se le mandan a la IA (o que se muestran sin IA), con su texto.

    Primero en el lugar (municipio + estatales de su estado), y primero las que nombran al municipio.
    Si en el lugar no hay nada, busca en todo el catálogo y lo anota en `registro["alcance"] = "todo"`."""
    alcance = _alcance(filtros)
    pregunta = plan["busqueda"] if plan else pregunta  # con el tema de la conversación
    # El nombre del lugar ya filtrado no ayuda a buscar ("Sinaloa" sale en el encabezado de cada página de Sinaloa)
    excluir = _palabras_del_lugar(con, alcance) | (plan["excluir"] if plan else frozenset())
    candidatas = []
    if plan and plan["documentos"]:  # primero dentro de los documentos que mejor corresponden a la pregunta
        candidatas = buscar_fragmentos(con, pregunta, limite=PAGINAS_RELEVANTES * 4, excluir=excluir,
                                       documento_ids=[d["id"] for d in plan["documentos"]])
    if not candidatas:
        candidatas = buscar_fragmentos(con, pregunta, limite=PAGINAS_RELEVANTES * 4, excluir=excluir, **alcance)
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


def _palabras_del_lugar(con, alcance: dict) -> frozenset:
    nombres = []
    if alcance.get("estado_id"):
        nombres += [f[0] for f in con.execute("SELECT nombre FROM estados WHERE id = ?", (alcance["estado_id"],))]
    if alcance.get("municipio_y_su_estado"):
        nombres += list(con.execute(
            "SELECT m.nombre, e.nombre FROM municipios m JOIN estados e ON e.id = m.estado_id WHERE m.id = ?",
            (alcance["municipio_y_su_estado"],)).fetchone() or ())
    return frozenset(normalizar(p) for n in nombres for p in n.split() if len(p) >= 3)


def _con_paginas_relevantes(con, pregunta: str, filtros: dict, uso: dict, registro: dict, plan: dict | None = None) -> dict:
    encontradas = paginas_relevantes(con, pregunta, filtros, registro, plan)
    if not encontradas:  # nada que mandarle a la IA: se ahorra la llamada
        return {"respuesta": NO_ENCONTRE, "citas": []}
    fuentes, permitidas, textos = [], {}, {}
    for n, c in enumerate(encontradas, start=1):
        texto = c["texto"]
        fuentes.append(f"[Fuente {n}] {c['documento_titulo']} ({c['lugar']}), página {c['pagina']}:\n"
                       f"{texto.strip()[:MAX_CARACTERES_PAGINA]}\n")
        permitidas[n] = (c["documento_id"], c["pagina"])
        textos[(c["documento_id"], c["pagina"])] = texto
    usuario = "FUENTES:\n\n" + "\n".join(fuentes) + f"\n{FORMATO_FUENTES}\n\nPREGUNTA: {pregunta}"
    contexto, busqueda = (plan["contexto"], plan["busqueda"]) if plan else ("", pregunta)
    return _resultado(con, busqueda, llm.pedir_json(SISTEMA, contexto + usuario, uso), permitidas, textos, usuario)


def _resultado(con, pregunta: str, datos: dict, permitidas: dict, textos: dict | None = None, extra: str = "") -> dict:
    """Valida lo que devolvió la IA: toda respuesta con datos tiene que traer al menos una página válida.

    `textos` ({(documento, página): texto}) y `extra` (títulos, pregunta) son lo que vio la IA: con ellos se
    verifican las cifras de la respuesta (ver `_verificar_cifras`)."""
    respuesta = MENCION_DE_FUENTE.sub("", str(datos.get("respuesta") or "")).strip()
    elegidas = []
    for f in datos.get("fuentes") or []:
        try:
            ref = permitidas.get(int(f))
        except (TypeError, ValueError):
            continue
        if ref and ref not in elegidas:  # se descarta cualquier página que no le mandamos
            elegidas.append(ref)
    sin_verificar = _verificar_cifras(respuesta, textos, extra, elegidas) if textos and respuesta else []
    if datos.get("encontrado") is False and not elegidas:
        return {"respuesta": respuesta or NO_ENCONTRE, "citas": [], "cifras_sin_verificar": sin_verificar}
    if not respuesta or not elegidas:
        raise ValueError("La IA respondió sin decir de qué página sale el dato")
    consulta = consulta_fts(pregunta)
    return {"respuesta": respuesta, "citas": [_cita(con, d, p, consulta) for d, p in elegidas[:MAX_CITAS]],
            "cifras_sin_verificar": sin_verificar}


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


def _sin_ia(con, pregunta: str, filtros: dict, registro: dict | None = None, actual: str | None = None) -> dict:
    """Las páginas de la búsqueda, sin IA. `pregunta` puede traer el tema de la conversación; `actual` es la que
    escribió la persona."""
    consulta = consulta_fts(pregunta)
    plan = _preparar(con, pregunta, filtros, actual) if not filtros.get("documento_id") else None
    citas = [_cita(con, c["documento_id"], c["pagina"], consulta)
             for c in paginas_relevantes(con, pregunta, plan["filtros"] if plan else filtros, registro, plan)[:MAX_CITAS]]
    respuesta = f"Encontré {len(citas)} fragmento(s) relevante(s) en los documentos." if citas else NO_ENCONTRE
    resultado = {"pregunta": actual or pregunta, "respuesta": respuesta, "citas": citas}
    if plan:
        resultado["documentos"] = [_documento_publico(d) for d in plan["documentos"]]
        resultado["entendido"] = _entendido_publico(con, plan["entendido"])
    return resultado


# --- Entender la pregunta y elegir documentos antes de buscar páginas ---

MAX_DOCUMENTOS = 5


def _preparar(con, pregunta: str, filtros: dict, actual: str | None = None) -> dict:
    """Lugar y sección que dice la pregunta (ganan sobre la página en la que se está) y los documentos candidatos.

    `pregunta` puede traer el tema de la conversación ("presupuesto de Irapuato ¿y las obras?"): el lugar y la
    sección que nombre la pregunta `actual` ganan."""
    entendido = entender(con, pregunta)
    if actual and actual != pregunta:
        propio = entender(con, actual)
        if propio["lugares"]:
            entendido.update({k: propio[k] for k in ("estado_id", "municipio_id", "lugar", "lugares", "comparacion")})
        if propio["seccion"]:
            entendido["seccion"] = propio["seccion"]
    anios = _anios(actual) or _anios(pregunta)
    filtros = dict(filtros)
    if entendido["municipio_id"]:
        filtros.update(municipio_id=entendido["municipio_id"], estado_id=None)
    elif entendido["estado_id"]:
        filtros.update(estado_id=entendido["estado_id"], municipio_id=None)
    alcance = _alcance(filtros)
    excluir = frozenset(entendido["palabras_lugar"]) | _palabras_del_lugar(con, alcance)
    documentos = documentos_candidatos(con, pregunta, alcance, entendido["seccion"], excluir, anios)
    return {"entendido": entendido, "filtros": filtros, "excluir": excluir, "documentos": documentos,
            "busqueda": pregunta, "contexto": "", "anios": anios}


def documentos_candidatos(con, pregunta: str, alcance: dict, seccion: str | None, excluir: frozenset,
                          anios: frozenset = frozenset()) -> list[dict]:
    """Los documentos que mejor corresponden a la pregunta: por su título, por cuántas páginas tratan el tema y,
    si la pregunta dice un año ("¿y en 2024?"), primero los de ese año. Si se pregunta por un estado, primero los
    del gobierno del estado. Las páginas que tratan el tema cuentan hasta cierto punto, para que un anexo de 1,000
    páginas no le gane a un documento cuyo título dice justo lo que se pide."""
    def en_alcance(con_seccion: bool) -> list:
        where, params = filtros_sql(**{**alcance, "seccion": seccion if con_seccion else alcance.get("seccion")})
        return con.execute(
            f"""
            SELECT d.id, d.titulo, d.anio, d.total_paginas, d.municipio_id, s.clave AS seccion,
                   s.nombre AS seccion_nombre, COALESCE(m.nombre, e.nombre) AS lugar
            FROM documentos d JOIN secciones s ON s.id = d.seccion_id JOIN estados e ON e.id = d.estado_id
            LEFT JOIN municipios m ON m.id = d.municipio_id
            WHERE d.estatus = 'listo'{where}
            """,
            params,
        ).fetchall()

    filas = en_alcance(bool(seccion)) or (en_alcance(False) if seccion else [])
    if not filas:
        return []
    terminos = {t.strip('"*') for t in consulta_fts(pregunta, excluir=excluir).split(" OR ") if t}
    paginas_por_doc = {}
    ids = [f["id"] for f in filas]
    for operador in ("AND", "OR"):
        consulta = consulta_fts(pregunta, operador, excluir)
        if not consulta:
            break
        for i in range(0, len(ids), 900):
            lote = ids[i:i + 900]
            for documento_id, cuantas in con.execute(
                f"""SELECT p.documento_id, COUNT(*) FROM paginas_fts JOIN paginas p ON p.id = paginas_fts.rowid
                    WHERE paginas_fts MATCH ? AND p.documento_id IN ({', '.join('?' * len(lote))})
                    GROUP BY p.documento_id""",
                (consulta, *lote),
            ):
                paginas_por_doc[documento_id] = cuantas
        if paginas_por_doc:
            break
    estatal = bool(alcance.get("estado_id")) and not (alcance.get("municipio_id") or alcance.get("municipio_y_su_estado"))
    documentos = []
    for f in filas:
        titulo = normalizar(f["titulo"])
        en_titulo = sum(1 for t in terminos if normalizar(t) in titulo)
        paginas = paginas_por_doc.get(f["id"], 0)
        if not en_titulo and not paginas:
            continue
        puntaje = (2 * en_titulo + min(math.log1p(paginas), 4) + (0.04 * (f["anio"] - 2000) if f["anio"] else 0)
                   + (3 if f["anio"] in anios else 0) + (1.5 if estatal and f["municipio_id"] is None else 0))
        documentos.append({**dict(f), "puntaje": round(puntaje, 3)})
    documentos.sort(key=lambda d: d["puntaje"], reverse=True)
    if not documentos and seccion:  # piden una sección ("contratos de edomex"): los más recientes de esa sección
        documentos = [{**dict(f), "puntaje": 0.1} for f in sorted(
            en_alcance(True), key=lambda f: (f["anio"] in anios, f["anio"] or 0), reverse=True)]
    return documentos[:MAX_DOCUMENTOS]


def _paginas_de_panorama(con, documento_id: int, pregunta: str, excluir: frozenset, cuantas: int) -> list[tuple]:
    """Para explicar un documento: sus primeras páginas con texto (índice, presentación) y las que tratan el tema."""
    elegidas = [n for n, t in con.execute(
        "SELECT numero, texto FROM paginas WHERE documento_id = ? AND numero <= 12 ORDER BY numero", (documento_id,))
        if len(t.strip()) >= 200][:max(1, cuantas // 2)]
    for r in buscar_fragmentos(con, pregunta, limite=cuantas * 2, excluir=excluir, documento_ids=[documento_id]):
        if len(elegidas) >= cuantas:
            break
        if r["pagina"] not in elegidas:
            elegidas.append(r["pagina"])
    return [(n, con.execute("SELECT texto FROM paginas WHERE documento_id = ? AND numero = ?", (documento_id, n))
             .fetchone()["texto"]) for n in sorted(elegidas)]


def _con_panorama(con, pregunta: str, plan: dict, uso: dict) -> dict:
    documentos = plan["documentos"]
    claro = len(documentos) == 1 or documentos[0]["puntaje"] >= 1.25 * max(documentos[1]["puntaje"], 0.01)
    fuentes, permitidas, textos = [], {}, {}
    for d in documentos[:1] if claro else documentos[:3]:
        for numero, texto in _paginas_de_panorama(con, d["id"], plan["busqueda"], plan["excluir"], 6 if claro else 2):
            n = len(fuentes) + 1
            fuentes.append(f"[Fuente {n}] {d['titulo']} ({d['lugar']}), página {numero}:\n"
                           f"{texto.strip()[:MAX_CARACTERES_PAGINA]}\n")
            permitidas[n] = (d["id"], numero)
            textos[(d["id"], numero)] = texto
    if not fuentes:
        return {"respuesta": NO_ENCONTRE, "citas": []}
    lista = "\n".join(f"- {d['titulo']} ({d['lugar']}, {d['anio'] or 'sin año'}, {d['total_paginas']} páginas, "
                      f"sección {d['seccion_nombre']})" for d in documentos)
    usuario = (f"DOCUMENTOS QUE HAY SOBRE ESO:\n{lista}\n\nFUENTES:\n\n" + "\n".join(fuentes)
               + f"\n{FORMATO_PANORAMA}\n\nPREGUNTA: {pregunta}")
    return _resultado(con, plan["busqueda"], llm.pedir_json(SISTEMA, plan["contexto"] + usuario, uso), permitidas,
                      textos, usuario)


def _documento_publico(d: dict) -> dict:
    return {k: d[k] for k in ("id", "titulo", "anio", "lugar", "seccion")}


def _entendido_publico(con, entendido: dict) -> dict:
    seccion = entendido["seccion"] and con.execute(
        "SELECT nombre FROM secciones WHERE clave = ?", (entendido["seccion"],)).fetchone()
    lugares = [l["lugar"] for l in entendido.get("lugares") or []] or [entendido["lugar"]]
    return {"lugar": " y ".join(l for l in lugares if l) or None, "seccion": seccion["nombre"] if seccion else None,
            "tipo": "comparacion" if entendido.get("comparacion") else "panorama" if entendido["panorama"] else "dato"}


# --- Comparar lugares: "compara la deuda de Jalisco y Nuevo León" ---


def _con_comparacion(con, pregunta: str, plan: dict, uso: dict) -> dict:
    """Hasta 3 páginas de cada lugar (hasta 3 lugares), primero de sus propios documentos; la IA compara."""
    fuentes, permitidas, textos, documentos, faltan = [], {}, {}, [], []
    lugares = plan["entendido"]["lugares"][:3]
    for lugar in lugares:
        if lugar["municipio_id"]:
            # Un documento estatal solo sirve para comparar al municipio si la página lo nombra.
            nombre = normalizar(con.execute("SELECT nombre FROM municipios WHERE id = ?",
                                            (lugar["municipio_id"],)).fetchone()["nombre"])
            alcances = (({"municipio_id": lugar["municipio_id"]}, None),
                        ({"municipio_y_su_estado": lugar["municipio_id"]}, nombre))
        else:  # el documento de un municipio no es "el presupuesto de Nuevo León": solo los del gobierno del estado
            alcances = (({"solo_del_estado": lugar["estado_id"]}, None),)
        paginas = []
        for alcance, debe_nombrar in alcances:
            candidatos = documentos_candidatos(con, plan["busqueda"], alcance, plan["entendido"]["seccion"],
                                               plan["excluir"], plan["anios"])
            if candidatos:
                paginas = [(c, con.execute("SELECT texto FROM paginas WHERE documento_id = ? AND numero = ?",
                                           (c["documento_id"], c["pagina"])).fetchone()["texto"])
                           for c in buscar_fragmentos(con, plan["busqueda"], limite=6, excluir=plan["excluir"],
                                                      documento_ids=[d["id"] for d in candidatos])]
                paginas = [(c, t) for c, t in paginas if not debe_nombrar or debe_nombrar in normalizar(t)][:3]
            if paginas:
                vistos = {d["id"] for d in documentos}
                usados = {c["documento_id"] for c, _ in paginas}
                documentos += [d for d in candidatos if d["id"] in usados and d["id"] not in vistos][:2]
                break
        if not paginas:
            faltan.append(lugar["lugar"])
        for c, texto in paginas:
            n = len(fuentes) + 1
            fuentes.append(f"[Fuente {n}] Sobre {lugar['lugar']}: {c['documento_titulo']} ({c['lugar']}), "
                           f"página {c['pagina']}:\n{texto.strip()[:MAX_CARACTERES_PAGINA]}\n")
            permitidas[n] = (c["documento_id"], c["pagina"])
            textos[(c["documento_id"], c["pagina"])] = texto
    plan["documentos"] = documentos
    if not fuentes:
        return {"respuesta": NO_ENCONTRE, "citas": []}
    usuario = (f"LUGARES A COMPARAR: {'; '.join(l['lugar'] for l in lugares)}\n"
               + (f"No se encontraron páginas sobre esto de: {'; '.join(faltan)}.\n" if faltan else "")
               + "\nFUENTES:\n\n" + "\n".join(fuentes) + f"\n{FORMATO_COMPARACION}\n\nPREGUNTA: {pregunta}")
    return _resultado(con, plan["busqueda"], llm.pedir_json(SISTEMA, plan["contexto"] + usuario, uso), permitidas,
                      textos, usuario)


# --- Memoria de la conversación ---

SEGUIMIENTO = re.compile(r"^(y|o|tambien|ahora|que tal|entonces|pero|igual)\b")
DE_SEGUIMIENTO = {"ahora", "entonces", "tal", "igual", "tambien", "pero", "eso", "esa", "ese", "caso", "vez"}


def _seguimiento(con, pregunta: str, historial: list) -> tuple[str, str]:
    """(texto con el que se busca, contexto para la IA).

    Una pregunta que nombra su lugar y su tema es nueva: se busca tal cual y sin contexto. Si continúa la anterior
    ("¿y en León?", "¿y en 2024?", "¿cuánto costó?"), se busca con el tema de las anteriores y la IA recibe las
    dos últimas preguntas con sus respuestas."""
    anteriores = [h for h in historial if isinstance(h, dict) and str(h.get("pregunta") or "").strip()][-3:]
    efectiva = None
    for h in anteriores:
        efectiva = _continuar(con, str(h["pregunta"]), efectiva)
    busqueda = _continuar(con, pregunta, efectiva)
    if busqueda == pregunta:
        return pregunta, ""
    contexto = "CONVERSACIÓN ANTERIOR (solo para entender a qué se refiere la pregunta):\n" + "".join(
        f"Pregunta: {' '.join(str(h['pregunta']).split())[:300]}\n"
        f"Respuesta: {' '.join(str(h.get('respuesta') or '').split())[:400]}\n" for h in anteriores[-2:]) + "\n"
    return busqueda, contexto


def _continuar(con, pregunta: str, previa: str | None) -> str:
    """La pregunta tal cual si es nueva; si continúa a `previa`, las dos juntas (con el lugar nuevo, si lo dice)."""
    pregunta = " ".join(pregunta.split())[:300]
    if not previa:
        return pregunta
    texto = normalizar(pregunta)
    propio = entender(con, pregunta)
    tema = [p for p in texto.split() if len(p) >= 3 and p not in VACIAS and p not in propio["palabras_lugar"]
            and p not in DE_SEGUIMIENTO and not p.isdigit()]
    if propio["lugares"] and tema and not SEGUIMIENTO.search(texto):
        return pregunta  # nueva y completa: "¿cuánto costó el mercado de Irapuato?"
    if propio["lugares"]:  # "¿y en León?": el tema de antes con el lugar nuevo (sin el lugar de antes)
        quitar = entender(con, previa)["palabras_lugar"]
        previa = " ".join(p for p in normalizar(previa).split() if p not in quitar)
    return f"{previa[:300]} {pregunta}"


def _anios(texto: str | None) -> frozenset:
    return frozenset(int(a) for a in re.findall(r"\b(199\d|20[0-3]\d)\b", texto or ""))


# --- Caché: la misma pregunta escrita con otras palabras ---

# Solo se quitan artículos y muletillas: "sin", "no", "más", "cuánto"... cambian la respuesta y se quedan.
RELLENO = set("""
el la los las un una unos unas lo de del al a en y e o u que es me te se le les nos mi mis tu tus su sus este esta
estos estas ese esa esos esas eso esto hay dime dame hablame habla platicame cuentame explicame explica resume
resumeme resumen dice dicen trata contiene quiero quisiera saber informacion info puedes podrias favor gracias hola
oye sobre acerca
""".split())
INTERROGATIVAS = {"cuanta": "cuanto", "cuantos": "cuanto", "cuantas": "cuanto", "quienes": "quien", "cuales": "cual"}


def _clave_pregunta(pregunta: str) -> str:
    """"¿Qué dice el presupuesto de Irapuato?" y "háblame del presupuesto de Irapuato" → "irapuato presupuesto"."""
    palabras = set()
    for p in normalizar(pregunta).split():
        if p in RELLENO:
            continue
        p = INTERROGATIVAS.get(p, p)
        palabras.add(p[:-1] if len(p) >= 5 and p.endswith("s") else p)
    return " ".join(sorted(palabras))


# --- Tope de gasto diario en IA (solo el chatbot; las cargas masivas las corre una persona a propósito) ---

_candado_gasto = threading.Lock()


def tope_diario() -> float:
    try:
        return float(os.environ.get("DEEPSEEK_TOPE_DIARIO_USD") or 3)
    except ValueError:
        return 3.0


def _archivo_gasto() -> Path:
    return Path(os.environ.get("GASTO_IA_ARCHIVO") or config.BACKEND / "gasto_ia.json")


def gasto_de_hoy() -> float:
    try:
        datos = json.loads(_archivo_gasto().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0.0
    return float(datos.get("usd", 0)) if datos.get("fecha") == time.strftime("%Y-%m-%d") else 0.0


def sumar_gasto(usd: float) -> None:
    with _candado_gasto:
        total = round(gasto_de_hoy() + usd, 6)
        try:
            _archivo_gasto().write_text(json.dumps({"fecha": time.strftime("%Y-%m-%d"), "usd": total}), encoding="utf-8")
        except OSError:
            pass


# --- Verificador de cifras ---

# En los PDF las cifras vienen pegadas al texto de la tabla ("29,076,147,169Educación") y separadas de la siguiente
# solo por un espacio ("616,742,902 538,832,783"): el espacio nunca es separador de miles.
NUMERO = re.compile(
    r"(?<![\d.,'’])(\d{1,3}(?:[,'’\u00a0\u202f]\d{3})+|\d+)(\.\d+)?(?!\d)"
    r"(\s*(?:%|por\s*ciento))?"
    r"(?:\s+(mil\s+millones|millones|millón|millon|billones|billón|billon|mil|mdp|mmdp)\b)?",
    re.IGNORECASE,
)
# La cifra tal como venga en el PDF, aunque tenga errores de captura: "$2,500.000,000.00", "13, 200".
TIRA = re.compile(r"\d(?:[\d.,'’\u00a0\u202f]|,\s(?=\d{3}\b))*\d")
MULTIPLICADOR = {"mil millones": 1e9, "millones": 1e6, "millón": 1e6, "millon": 1e6, "billones": 1e12,
                 "billón": 1e12, "billon": 1e12, "mil": 1e3, "mdp": 1e6, "mmdp": 1e9}
REFERENCIA = re.compile(r"(p[aá]g(ina)?s?\.?|fuentes?|art[ií]culos?|art\.)\s*$", re.IGNORECASE)


def cifras(texto: str) -> list[tuple[float, float, str, str]]:
    """(valor, tolerancia, como aparece, solo sus dígitos) de cada cifra que vale la pena revisar.

    "$3,200 millones" y "3,200,000,000.00" valen lo mismo; "5.3 millones" acepta de 5.25 a 5.35 millones (el
    redondeo). No cuentan los años sueltos, los números chicos sin decimales ni %, ni "página 12"."""
    salida = []
    for m in NUMERO.finditer(texto or ""):
        entero, decimales, porciento, palabra = m.groups()
        digitos = re.sub(r"\D", "", entero)
        multiplicador = MULTIPLICADOR[" ".join(palabra.lower().split())] if palabra else 1
        valor = float(digitos + (decimales or "")) * multiplicador
        simple = not (decimales or porciento or palabra)
        if simple and (valor < 100 or (len(entero) == 4 and 1990 <= valor <= 2035)):
            continue
        if REFERENCIA.search(texto[max(0, m.start() - 12):m.start()]):
            continue
        if decimales:
            unidad = 10 ** -(len(decimales) - 1)
        else:  # los ceros del final pueden ser redondeo, pero siempre quedan al menos 2 cifras significativas
            ceros = len(digitos) - len(digitos.rstrip("0"))
            unidad = 10 ** min(ceros, max(len(digitos) - 2, 0))
        salida.append((valor, unidad * multiplicador / 2 + 1e-6, m.group().strip(), digitos + (decimales or "")[1:]))
    return salida


def _en_texto(texto: str) -> tuple[list[float], set[str]]:
    """Los valores de las cifras de un texto y sus dígitos tal como vienen (para cifras mal capturadas)."""
    return [v for v, *_ in cifras(texto)], {re.sub(r"\D", "", m.group()) for m in TIRA.finditer(texto or "")}


def _esta(valor: float, tolerancia: float, digitos: str, en: tuple) -> bool:
    valores, tiras = en
    if any(abs(v - valor) <= tolerancia for v in valores):
        return True
    # "2,500,000,000.00" en la respuesta y "$2,500.000,000.00" en el PDF: los mismos dígitos
    return len(digitos) >= 4 and bool({digitos, digitos + "0", digitos + "00"} & tiras)


def _verificar_cifras(respuesta: str, textos: dict, extra: str, elegidas: list) -> list[str]:
    """Las cifras de la respuesta que no están en ninguna página que vio la IA (ni en los títulos o la pregunta).

    Si una cifra está en una página que la IA no citó, esa página se agrega a `elegidas`: todo dato lleva su página."""
    en_paginas = {ref: _en_texto(t) for ref, t in textos.items()}
    conocidas = _en_texto(extra)
    sin_verificar = []
    for valor, tolerancia, como, digitos in cifras(respuesta):
        paginas = [ref for ref, en in en_paginas.items() if _esta(valor, tolerancia, digitos, en)]
        if paginas:
            if not any(p in elegidas for p in paginas):
                elegidas.append(paginas[0])
        elif not _esta(valor, tolerancia, digitos, conocidas) and como not in sin_verificar:
            sin_verificar.append(como)
    return sin_verificar


# --- Preguntas sugeridas (también precalientan el caché para la demo: precalentar.py) ---

PLANTILLAS = {
    "informes": "Háblame del informe de gobierno de {lugar}",
    "presupuesto": "¿Qué dice el presupuesto de {lugar}?",
    "obras": "¿Qué obras públicas hay en {lugar}?",
    "contratos": "¿Qué contratos o licitaciones hay en {lugar}?",
    "actas": "¿Qué se aprobó en las sesiones de {lugar}?",
}
DEL_DOCUMENTO = ["¿De qué trata este documento?", "¿Cuáles son las cifras más importantes?",
                 "¿Quién lo publicó y de qué fecha es?"]


def sugeridas(con, estado_id: int | None = None, municipio_id: int | None = None,
              documento_id: int | None = None) -> list[str]:
    """Preguntas de ejemplo: del documento, del lugar (solo de secciones con documentos) o generales."""
    if documento_id:
        return DEL_DOCUMENTO
    if not estado_id and not municipio_id:
        return _generales(con)
    if municipio_id:
        fila = con.execute("SELECT nombre FROM municipios WHERE id = ?", (municipio_id,)).fetchone()
        where, params = filtros_sql(municipio_y_su_estado=municipio_id)
    else:
        fila = con.execute("SELECT nombre FROM estados WHERE id = ?", (estado_id,)).fetchone()
        where, params = filtros_sql(estado_id=estado_id)
    if fila is None:
        return []
    nombre = COMO_SE_DICE.get(fila["nombre"], fila["nombre"])
    secciones = [s for (s,) in con.execute(
        f"""SELECT s.clave FROM documentos d JOIN secciones s ON s.id = d.seccion_id
            WHERE d.estatus = 'listo'{where} GROUP BY s.clave ORDER BY COUNT(*) DESC""", params)]
    return [_con_lugar(PLANTILLAS[s], nombre) for s in secciones if s in PLANTILLAS][:4]


# "México" a secas es el país: en una pregunta el estado se dice "Estado de México".
COMO_SE_DICE = {"México": "el Estado de México", "Ciudad de México": "la Ciudad de México",
                "Veracruz de Ignacio de la Llave": "Veracruz", "Michoacán de Ocampo": "Michoacán",
                "Coahuila de Zaragoza": "Coahuila"}
NO_ES_EL_DOCUMENTO = ("anexo", "aviso", "diario", "comparecencia", "lineamiento", "calendario", "cronograma", "glosa",
                      "inicia", "ejemplo", "municipio")


def _estados_con(con, patron: str, cuantos: int) -> list[str]:
    """Estados cuyo gobierno tiene un documento con ese título ("%informe de gobierno%"), primero los recientes."""
    fuera = " ".join("AND lower(d.titulo) NOT LIKE ?" for _ in NO_ES_EL_DOCUMENTO)
    nombres = []
    for (nombre,) in con.execute(
        f"""SELECT e.nombre FROM documentos d JOIN estados e ON e.id = d.estado_id
            WHERE d.estatus = 'listo' AND d.municipio_id IS NULL AND lower(d.titulo) LIKE ? {fuera}
            ORDER BY lower(d.titulo) LIKE '%gobierno del estado%' DESC, d.anio DESC, d.total_paginas DESC""",
        (patron, *(f"%{p}%" for p in NO_ES_EL_DOCUMENTO)),
    ):
        if nombre not in nombres:
            nombres.append(nombre)
        if len(nombres) == cuantos:
            break
    return [COMO_SE_DICE.get(n, n) for n in nombres]


def _generales(con) -> list[str]:
    """Para la portada: preguntas que lo cargado sí puede responder bien."""
    informes = _estados_con(con, "%informe de gobierno%", 1)
    presupuestos = _estados_con(con, "%presupuesto de egresos%", 2)
    generales = [_con_lugar(PLANTILLAS["informes"], n) for n in informes]
    generales += [_con_lugar(PLANTILLAS["presupuesto"], n) for n in presupuestos[:1]]
    if len(presupuestos) == 2:
        generales.append(_con_lugar("Compara el presupuesto de {lugar}", f"{presupuestos[0]} y {presupuestos[1]}"))
    return generales


def _con_lugar(plantilla: str, lugar: str) -> str:
    return plantilla.format(lugar=lugar).replace(" de el ", " del ")  # "del Estado de México"
