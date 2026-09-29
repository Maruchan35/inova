"""Resumen y "lo más importante" de un documento: con IA, o con un respaldo sin IA."""

import json
import re

from . import llm

# ~40k tokens por bloque: la mayoría de los documentos cabe en una sola llamada.
CARACTERES_POR_BLOQUE = 120_000
MAX_PUNTOS = 8

SISTEMA = (
    "Eres un analista que explica documentos de gobierno de México a ciudadanos comunes. "
    "Usa únicamente información del texto que se te da; nunca inventes datos. "
    "Escribe en español sencillo, sin tecnicismos. Responde solo con JSON válido."
)

FORMATO = (
    'Devuelve JSON con esta forma: {"resumen": "...", "puntos": [{"texto": "...", "pagina": N}]}. '
    f"'resumen': 2 a 4 frases que digan de qué trata el documento y qué es lo más relevante. "
    f"'puntos': máximo {MAX_PUNTOS} datos importantes, una frase cada uno, con cifras cuando existan "
    "(montos, porcentajes, fechas, obras, a qué se destina el dinero). 'pagina' es el número de "
    "[Página N] de donde sale el dato."
)


def _bloques(paginas: list[str]) -> list[str]:
    bloques, actual = [], ""
    for numero, texto in enumerate(paginas, start=1):
        pagina = f"[Página {numero}]\n{texto.strip()}\n\n"
        if actual and len(actual) + len(pagina) > CARACTERES_POR_BLOQUE:
            bloques.append(actual)
            actual = ""
        actual += pagina
    if actual:
        bloques.append(actual)
    return bloques


def _validar(datos: dict, total_paginas: int) -> tuple[str, list[dict]]:
    resumen = str(datos.get("resumen") or "").strip()
    puntos = []
    for p in datos.get("puntos") or []:
        try:
            texto, pagina = str(p["texto"]).strip(), int(p["pagina"])
        except (KeyError, TypeError, ValueError):
            continue
        if texto and 1 <= pagina <= total_paginas:  # un punto sin página válida no se publica
            puntos.append({"texto": texto, "pagina": pagina})
    if not resumen or not puntos:
        raise ValueError("La IA no devolvió un resumen con puntos válidos")
    return resumen, puntos[:MAX_PUNTOS]


def resumir_con_ia(titulo: str, paginas: list[str], uso: dict) -> tuple[str, list[dict]]:
    parciales = [
        llm.pedir_json(SISTEMA, f"Documento: {titulo}\n\n{bloque}\n{FORMATO}", uso)
        for bloque in _bloques(paginas)
    ]
    if len(parciales) == 1:
        return _validar(parciales[0], len(paginas))
    # Documento grande: se combinan los resúmenes parciales conservando la página de cada punto.
    combinar = (
        f"Documento: {titulo}\nEstos son resúmenes parciales de sus partes, en orden:\n"
        f"{json.dumps(parciales, ensure_ascii=False)}\n\n"
        f"Combínalos en un solo resultado para el documento completo. Conserva la página de cada punto. {FORMATO}"
    )
    return _validar(llm.pedir_json(SISTEMA, combinar, uso), len(paginas))


# --- Respaldo sin IA: fragmentos con cifras, para que la demo nunca se quede sin resumen ---

CIFRA = re.compile(r"\$\s?[\d,.]+(?:\s*(?:millones|mil millones|mdp|mil))?|\b[\d,.]+\s*(?:millones|mdp)\b|\b\d+(?:\.\d+)?\s?%", re.I)
PALABRAS = re.compile(r"presupuesto|total|obra|inversi[oó]n|gasto|ingreso|programa|aprob|destin", re.I)


def resumir_sin_ia(titulo: str, paginas: list[str]) -> tuple[str, list[dict]]:
    candidatos = []
    for numero, texto in enumerate(paginas, start=1):
        limpio = re.sub(r"\s+", " ", texto).strip()
        for m in CIFRA.finditer(limpio):
            inicio, fin = max(0, m.start() - 90), min(len(limpio), m.end() + 60)
            fragmento = limpio[inicio:fin].strip()
            puntaje = 3 + len(PALABRAS.findall(fragmento))
            candidatos.append((puntaje, numero, inicio, fin, fragmento))

    # Máximo 2 fragmentos por página y nunca dos que se encimen: más variedad de datos.
    puntos, elegidos = [], []
    for _, numero, inicio, fin, fragmento in sorted(candidatos, key=lambda c: (-c[0], c[1], c[2])):
        misma_pagina = [(i, f) for n, i, f in elegidos if n == numero]
        if len(misma_pagina) >= 2 or any(inicio < f and i < fin for i, f in misma_pagina):
            continue
        elegidos.append((numero, inicio, fin))
        puntos.append({"texto": f"…{fragmento}…", "pagina": numero})
        if len(puntos) == MAX_PUNTOS:
            break
    puntos.sort(key=lambda p: p["pagina"])
    resumen = (
        f"Resumen automático sin IA de «{titulo}» ({len(paginas)} páginas). "
        "Abajo están los fragmentos con cifras más relevantes, cada uno con su página."
    )
    return resumen, puntos
