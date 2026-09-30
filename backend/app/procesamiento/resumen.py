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


# --- Respaldo sin IA: oraciones completas con cifras y contexto fluido ---

CIFRA = re.compile(
    r"\$\s?[\d,.]+(?:\s*(?:millones|mil millones|mdp|mil|billones))?|\b[\d,.]+\s*(?:millones|mil millones|mdp)\b|\b\d+(?:\.\d+)?\s?%",
    re.I,
)
PALABRAS = re.compile(
    r"presupuesto|total|obra|inversi[oó]n|gasto|ingreso|programa|aprob|destin|apoyo|benefici|ejerc|recurso|financ|adquisici",
    re.I,
)


def _extraer_oracion_cifra(texto_limpio: str, match: re.Match) -> str:
    """Extrae la oración o cláusula completa que contiene la cifra, respetando límites de puntuación."""
    m_start = match.start()
    m_end = match.end()

    # 1. Delimitadores hacia atrás: buscar último límite de oración o viñeta
    limite_atras = max(0, m_start - 300)
    sub_atras = texto_limpio[limite_atras:m_start]

    seps_atras = [m.end() for m in re.finditer(r'(?:\.\s+|[■▪•]\s*|;\s*|\n\s*)', sub_atras)]
    if seps_atras:
        inicio = limite_atras + seps_atras[-1]
    else:
        # Retroceder al límite de palabra anterior a ~140 caracteres
        pos = max(0, m_start - 140)
        sp = texto_limpio.find(" ", pos)
        inicio = (sp + 1) if (sp != -1 and sp < m_start) else pos

    # 2. Delimitadores hacia adelante: buscar fin de oración o siguiente viñeta
    limite_adelante = min(len(texto_limpio), m_end + 300)
    sub_adelante = texto_limpio[m_end:limite_adelante]

    seps_adelante = [m.start() for m in re.finditer(r'(?:\.(?:\s+|$)|[■▪•]|\n)', sub_adelante)]
    if seps_adelante:
        sep_pos = seps_adelante[0]
        if sub_adelante[sep_pos] == ".":
            fin = m_end + sep_pos + 1
        else:
            fin = m_end + sep_pos
    else:
        pos = min(len(texto_limpio), m_end + 120)
        sp = texto_limpio.find(" ", pos)
        fin = sp if sp != -1 else len(texto_limpio)

    fragmento = texto_limpio[inicio:fin].strip()

    # Limpieza de viñetas, guiones y signos huérfanos
    fragmento = re.sub(r"^[■▪•\s,.:;-]+", "", fragmento)
    fragmento = re.sub(r"[■▪•\s,;:-]+$", "", fragmento)
    fragmento = re.sub(r"\s+", " ", fragmento).strip()
    fragmento = re.sub(r"\s*[■▪•]\s*", " — ", fragmento)

    # Si empieza con fragmento mutilado en minúscula seguido de mayúscula
    m_mut = re.match(r"^[a-záéíóúñ]{1,12}\s+([A-ZÁÉÍÓÚÑ].*)", fragmento)
    if m_mut:
        fragmento = m_mut.group(1)

    if fragmento:
        fragmento = fragmento[0].upper() + fragmento[1:]
        if not fragmento.endswith("."):
            fragmento += "."

    return fragmento


def resumir_sin_ia(titulo: str, paginas: list[str]) -> tuple[str, list[dict]]:
    candidatos = []
    for numero, texto in enumerate(paginas, start=1):
        limpio = re.sub(r"\s+", " ", texto).strip()
        for m in CIFRA.finditer(limpio):
            fragmento = _extraer_oracion_cifra(limpio, m)
            if len(fragmento) >= 30 and len(fragmento) <= 350:
                puntaje = 3 + len(PALABRAS.findall(fragmento))
                candidatos.append((puntaje, numero, fragmento))

    # Máximo 2 fragmentos por página y evitar duplicados o encimados
    puntos, elegidos = [], []
    for _, numero, fragmento in sorted(candidatos, key=lambda c: (-c[0], c[1])):
        misma_pagina = [f for n, f in elegidos if n == numero]
        if len(misma_pagina) >= 2 or any(fragmento in f or f in fragmento for f in misma_pagina):
            continue
        elegidos.append((numero, fragmento))
        puntos.append({"texto": fragmento, "pagina": numero})
        if len(puntos) == MAX_PUNTOS:
            break
    puntos.sort(key=lambda p: p["pagina"])
    resumen = (
        f"Resumen de «{titulo}» ({len(paginas)} páginas). "
        "A continuación se desglosan los puntos clave y cifras presupuestales más relevantes del expediente."
    )
    return resumen, puntos
