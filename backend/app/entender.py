"""Entender la pregunta antes de buscar: de qué lugar habla, de qué sección y si pide un panorama o un dato.

    "háblame del informe de gobierno de cdmx" → Ciudad de México · informes · panorama
    "¿cuánto costó el mercado de Irapuato?"   → Irapuato (Guanajuato) · — · dato
"""

import re
import sqlite3
import threading
import unicodedata

# Abreviaturas y nombres cortos que la gente usa para los estados.
ALIAS_ESTADOS = {
    "cdmx": "Ciudad de México", "df": "Ciudad de México", "distrito federal": "Ciudad de México",
    "ciudad de mexico": "Ciudad de México", "edomex": "México", "edo mex": "México", "estado de mexico": "México",
    "coahuila": "Coahuila de Zaragoza", "michoacan": "Michoacán de Ocampo", "veracruz": "Veracruz de Ignacio de la Llave",
    "gto": "Guanajuato", "ags": "Aguascalientes", "bcs": "Baja California Sur", "chis": "Chiapas", "chih": "Chihuahua",
    "dgo": "Durango", "gro": "Guerrero", "hgo": "Hidalgo", "jal": "Jalisco", "mich": "Michoacán de Ocampo",
    "nl": "Nuevo León", "oax": "Oaxaca", "qro": "Querétaro", "qroo": "Quintana Roo", "q roo": "Quintana Roo",
    "slp": "San Luis Potosí", "tamps": "Tamaulipas", "tlax": "Tlaxcala", "yuc": "Yucatán", "zac": "Zacatecas",
}
# "México" a secas es el país: el estado solo cuenta como "estado de México" o "edomex".
NO_ES_ESTADO = {"mexico"}

# Nombres de municipio que también son palabras comunes: no se detectan solos.
COMUNES = {
    "centro", "progreso", "reforma", "libertad", "union", "paz", "victoria", "juarez", "hidalgo", "morelos",
    "guadalupe", "zaragoza", "allende", "aldama", "abasolo", "ocampo", "jimenez", "matamoros", "guerrero", "salud",
    "general", "nacional", "cultura", "educacion", "comercio", "presidio", "cuenta", "trancoso", "tepetlan",
    "isla", "mama", "mina", "suma", "tala", "jala", "mani", "ruiz", "nava", "baca", "naco", "peto",
}

# Secciones: la primera palabra que aparece en la pregunta decide.
SECCIONES = (
    ("presupuesto", r"presupuest\w*|egresos?|ingresos?|gastos?|finanzas?|deuda|cuenta publica|recaudaci\w*"),
    ("obras", r"obras?\b|construcci\w*|pavimentaci\w*|infraestructura"),
    ("actas", r"actas?\b|cabildo|sesion\w*"),
    ("contratos", r"contratos?\b|licitaci\w*|proveedor\w*|adjudicaci\w*|compras?\b"),
    ("informes", r"informes?\b|rendicion de cuentas"),
)

# Palabras que describen el tipo de documento (no el tema): si solo quedan estas, la persona pide un panorama.
DOCUMENTO = {
    "informe", "informes", "gobierno", "presupuesto", "presupuestos", "egresos", "ingresos", "documento", "documentos",
    "plan", "programa", "desarrollo", "municipal", "estatal", "anual", "cuenta", "publica", "acta", "actas", "cabildo",
    "contrato", "contratos", "licitacion", "licitaciones", "obra", "obras", "publicas", "ley", "decreto", "estado",
    "municipio", "ciudad", "alcaldia", "alcaldias", "gobernador", "gobernadora", "presidente", "presidenta", "jefa",
    "jefe", "primer", "segundo", "tercer", "cuarto", "quinto", "sexto", "ultimo", "reciente", "actual", "nuevo",
}
PANORAMA = re.compile(r"^(hablame|habla|platicame|cuentame|explicame|explica|resume|resumeme|resumen|dame un resumen"
                      r"|que es|que dice|que contiene|que hay en|de que (trata|habla|se trata)|informacion|info)\b")
DATO = re.compile(r"\b(cuanto|cuanta|cuantos|cuantas|quien|quienes|cuando|donde|monto|costo|cifra|porcentaje|total)\b")

_catalogo = None
_candado = threading.Lock()


def normalizar(texto: str) -> str:
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", sin_acentos.casefold()))


def _cargar_catalogo(con: sqlite3.Connection) -> dict:
    global _catalogo
    with _candado:
        if _catalogo is None:
            estados = {normalizar(n): (i, n) for i, n in con.execute("SELECT id, nombre FROM estados")}
            nombres_estado = {**{k: v for k, v in estados.items() if k not in NO_ES_ESTADO},
                              **{normalizar(a): estados[normalizar(n)] for a, n in ALIAS_ESTADOS.items()
                                 if normalizar(n) in estados}}
            municipios, repetidos = {}, set()
            for i, estado_id, n in con.execute("SELECT id, estado_id, nombre FROM municipios"):
                clave = normalizar(re.sub(r"\s*\(\d+\)$", "", n))  # "San Juan Mixtepec (20208)" → "san juan mixtepec"
                if clave in municipios:
                    repetidos.add(clave)
                municipios[clave] = (i, estado_id, n)
            unicos = {k: v for k, v in municipios.items()
                      if k not in repetidos and k not in COMUNES and len(k) >= 4 and k not in nombres_estado}
            _catalogo = {
                "estados": nombres_estado,
                "patron_estados": _patron(nombres_estado),
                "municipios": unicos,
                "patron_municipios": _patron(unicos),
                "nombre_estado": {i: n for i, n in con.execute("SELECT id, nombre FROM estados")},
            }
    return _catalogo


def _patron(nombres: dict) -> re.Pattern:
    alternativas = sorted(nombres, key=len, reverse=True)  # primero los largos: "baja california sur" antes que "baja california"
    return re.compile(r"\b(" + "|".join(re.escape(a) for a in alternativas) + r")\b")


def entender(con: sqlite3.Connection, pregunta: str) -> dict:
    """{"estado_id", "municipio_id", "lugar", "seccion", "panorama", "palabras_lugar"} de la pregunta."""
    cat = _cargar_catalogo(con)
    texto = normalizar(pregunta)
    resultado = {"estado_id": None, "municipio_id": None, "lugar": None, "seccion": None, "panorama": False,
                 "palabras_lugar": set()}

    resto = texto
    if m := cat["patron_estados"].search(texto):
        estado_id, nombre = cat["estados"][m.group(1)]
        resultado.update(estado_id=estado_id, lugar=nombre)
        resultado["palabras_lugar"] |= set(m.group(1).split()) | set(normalizar(nombre).split())
        resto = texto.replace(m.group(1), " ")
    if m := cat["patron_municipios"].search(resto):
        municipio_id, estado_id, nombre = cat["municipios"][m.group(1)]
        if resultado["estado_id"] in (None, estado_id):  # "León, Guanajuato" sí; "León" dicho junto a otro estado, no
            resultado.update(municipio_id=municipio_id, estado_id=estado_id,
                             lugar=f"{nombre}, {cat['nombre_estado'][estado_id]}")
            resultado["palabras_lugar"] |= set(m.group(1).split())

    posiciones = [(m.start(), clave) for clave, patron in SECCIONES if (m := re.search(patron, texto))]
    if posiciones:
        resultado["seccion"] = min(posiciones)[1]

    # Panorama: pide "háblame de…/qué dice…" o no pide un dato, y no queda ningún tema aparte del documento y el lugar.
    tema = [p for p in texto.split() if len(p) >= 3 and p not in DOCUMENTO and p not in resultado["palabras_lugar"]
            and not p.isdigit() and not _es_vacia(p)]
    pide_panorama = bool(PANORAMA.search(texto)) or not DATO.search(texto)
    resultado["panorama"] = pide_panorama and not tema and (resultado["seccion"] is not None or "documento" in texto)
    return resultado


def _es_vacia(palabra: str) -> bool:
    from .busqueda import VACIAS
    return palabra in VACIAS or palabra in {"hablame", "sobre", "platicame", "cuentame", "explicame", "resumen",
                                            "resumeme", "trata", "dice", "contiene", "informacion", "saber"}
