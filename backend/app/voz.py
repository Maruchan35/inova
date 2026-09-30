"""Modo por voz: qué hacer con lo que dijo la persona (el navegador ya lo convirtió a texto).

    "llévame a Irapuato"                      → ir al municipio
    "quiero ver el presupuesto de Guanajuato" → ir al estado, a la sección de presupuesto
    "regresa al inicio"                       → ir al inicio
    "¿cuánto costó el mercado de Irapuato?"   → preguntarle al chatbot

No usa IA: reutiliza `entender` (lugar y sección), así que no cuesta nada.
"""

import re
import sqlite3
import threading

from .busqueda import VACIAS
from .entender import DOCUMENTO, SECCIONES, entender, normalizar

# Palabras para pedir que te lleven a un lugar: no son el tema de una pregunta.
NAVEGAR = set("""
llevame lleva llevanos ir ve vamos vaya abre abrir abreme muestra muestrame mostrar ensename ensena ver quiero
quisiera busca buscar buscame entra entrar pagina paginas municipio estado ciudad alcaldia documento documentos
archivos archivo seccion lugar porfa informacion
""".split())
INICIO = re.compile(r"^(?:(?:ve|ir|vamos|llevame|regresa|regresar|regresame|volver|vuelve)\s+)?(?:a\s+|al\s+)?"
                    r"(?:la\s+|el\s+)?(inicio|pagina principal|pagina de inicio|portada|principio|menu principal)$")
ATRAS = re.compile(r"^(regresa|regresar|regresame|atras|volver|vuelve|ve atras|vuelve atras|ir atras|para atras"
                   r"|pagina anterior)$")
AYUDA = re.compile(r"^(ayuda|ayudame|que puedo (decir|hacer|preguntar)|como funciona( esto)?|no se que hacer"
                   r"|instrucciones)$")
# Así empieza una pregunta para el chatbot (aunque nombre un lugar): "¿qué obras hay en Irapuato?"
PREGUNTA = re.compile(r"^(que|cual|cuales|cuanto|cuanta|cuantos|cuantas|quien|quienes|como|donde|cuando|por que|hay"
                      r"|existe|hablame|habla|platicame|cuentame|explicame|explica|resume|resumeme|dime|compara"
                      r"|comparame)\b")

TEXTO_AYUDA = ("Puedes decir, por ejemplo: llévame a Irapuato. Quiero ver el presupuesto de Guanajuato. "
               "¿Cuánto costó el mercado de Irapuato? O regresa al inicio.")
NO_ESCUCHE = "No te escuché. Toca el micrófono y vuelve a intentarlo."

_lugares = None
_candado = threading.Lock()


def interpretar(con: sqlite3.Connection, texto: str, estado_id: int | None = None, municipio_id: int | None = None,
                documento_id: int | None = None) -> dict:
    """{"accion": "ir" | "inicio" | "atras" | "preguntar" | "decir", "decir": lo que la página dice en voz alta, ...}.

    "ir" trae `tipo` ("estado" o "municipio"), `id` y, si se pidió, `seccion`; "preguntar" trae `pregunta`."""
    dicho = " ".join((texto or "").split())[:300]
    t = normalizar(dicho)
    if not t:
        return _respuesta("decir", dicho, NO_ESCUCHE)
    if INICIO.match(t):
        return _respuesta("inicio", dicho, "Vamos al inicio.")
    if ATRAS.match(t):
        return _respuesta("atras", dicho, "Regresamos a la página anterior.")
    if AYUDA.match(t):
        return _respuesta("decir", dicho, TEXTO_AYUDA)

    e = entender(con, dicho)
    if PREGUNTA.search(t) or e["comparacion"]:
        return _respuesta("preguntar", dicho, "", pregunta=dicho)
    seccion = _seccion(con, e["seccion"])
    # Lo que queda al quitar el lugar, la sección y las palabras de "llévame a…": si no queda nada, es navegar.
    resto = [p for p in t.split() if len(p) >= 3 and p not in VACIAS and p not in NAVEGAR and p not in DOCUMENTO
             and p not in e["palabras_lugar"] and not p.isdigit() and not _es_de_seccion(p)]
    if not resto:
        if e["lugar"]:
            tipo, id_ = ("municipio", e["municipio_id"]) if e["municipio_id"] else ("estado", e["estado_id"])
            return _ir(dicho, tipo, id_, e["lugar"], seccion)
        if seccion and (municipio_id or estado_id):  # "muéstrame las obras", ya dentro de un lugar
            tipo, id_ = ("municipio", municipio_id) if municipio_id else ("estado", estado_id)
            return _respuesta("ir", dicho, f"Te muestro {seccion['nombre']} de este lugar.", tipo=tipo, id=id_,
                              seccion=seccion["clave"])
        return _respuesta("decir", dicho, "¿A qué estado o municipio quieres ir? " + TEXTO_AYUDA)

    # "Llévame a Guadalupe": un nombre que `entender` no toma solo porque hay varios o es una palabra común.
    if len(resto) <= 4:
        palabras = [p for p in t.split() if p not in NAVEGAR and p not in DOCUMENTO and p not in e["palabras_lugar"]
                    and not _es_de_seccion(p)]
        while palabras and (len(palabras[0]) < 3 or palabras[0] in VACIAS):  # "a", "al", "de" de las orillas
            palabras.pop(0)
        while palabras and (len(palabras[-1]) < 3 or palabras[-1] in VACIAS):
            palabras.pop()
        nombre = " ".join(palabras)  # conserva lo de en medio: "san juan del rio"
        candidatos = [l for l in _catalogo(con).get(nombre, []) if e["estado_id"] in (None, l["estado_id"])]
        if len(candidatos) == 1:
            l = candidatos[0]
            return _ir(dicho, "municipio", l["id"], f"{l['nombre']}, {l['estado']}", seccion)
        if len(candidatos) > 1:
            estados = ", ".join(sorted({l["estado"] for l in candidatos})[:5])
            return _respuesta("decir", dicho, f"Hay {len(candidatos)} municipios que se llaman {candidatos[0]['nombre']}, "
                                              f"en {estados}. Dime el nombre con su estado.")
    return _respuesta("preguntar", dicho, "", pregunta=dicho)


def _respuesta(accion: str, dicho: str, decir: str, **extra) -> dict:
    return {"accion": accion, "texto": dicho, "decir": decir, "tipo": None, "id": None, "seccion": None,
            "pregunta": None, **extra}


def _ir(dicho: str, tipo: str, id_: int, lugar: str, seccion: dict | None) -> dict:
    decir = ("Te llevo al Estado de México" if lugar == "México" else f"Te llevo a {lugar}") + (f", a la sección {seccion['nombre']}." if seccion else ".")
    return _respuesta("ir", dicho, decir, tipo=tipo, id=id_, seccion=seccion["clave"] if seccion else None)


def _seccion(con, clave: str | None) -> dict | None:
    fila = clave and con.execute("SELECT clave, nombre FROM secciones WHERE clave = ?", (clave,)).fetchone()
    return dict(fila) if fila else None


def _es_de_seccion(palabra: str) -> bool:
    return any(re.fullmatch(patron, palabra) for _, patron in SECCIONES)


def _catalogo(con) -> dict:
    """Municipios por nombre sin acentos: {"guadalupe": [{id, nombre, estado_id, estado}, …]}."""
    global _lugares
    with _candado:
        if _lugares is None:
            _lugares = {}
            for f in con.execute("""SELECT m.id, m.nombre, m.estado_id, e.nombre AS estado
                                    FROM municipios m JOIN estados e ON e.id = m.estado_id"""):
                clave = normalizar(re.sub(r"\s*\(\d+\)$", "", f["nombre"]))
                _lugares.setdefault(clave, []).append(dict(f))
    return _lugares
