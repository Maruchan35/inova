"""Reclasifica los documentos con IA: sección correcta, título claro, año y una descripción de 1 o 2 frases.

    cd backend
    python reclasificar.py --muestra 15     # muestra lo que cambiaría en 15 documentos al azar, sin guardar
    python reclasificar.py                  # todos los documentos listos que falten (se puede interrumpir)

Usa el título, el lugar, la liga oficial y el texto de las primeras páginas (~1,500 tokens por documento,
unos $0.0003 USD fuera de hora pico). Los documentos de ejemplo no se tocan. El avance se guarda en
documentos/_catalogo/reclasificados.json para retomar donde se quedó.
"""

import argparse
import json
import random
import sqlite3
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from app import config  # noqa: F401  (carga backend/.env)
from app import db
from app.procesamiento import llm

RAIZ = Path(__file__).resolve().parents[1]
AVANCE = RAIZ / "documentos" / "_catalogo" / "reclasificados.json"
SECCIONES = ("informes", "presupuesto", "obras", "actas", "contratos")
CARACTERES = 4_000

SISTEMA = ("Eres un archivista que clasifica documentos oficiales de gobiernos de México para una plataforma "
           "ciudadana. Usa solo lo que dicen el título y el texto; no inventes. Responde solo con JSON válido.")
INSTRUCCIONES = """Devuelve JSON: {"seccion": "...", "titulo": "...", "anio": 2025, "descripcion": "..."}.
- seccion, una de: "informes" (informes de gobierno, de actividades, de gestión o de avance; planes de desarrollo),
  "presupuesto" (presupuestos de egresos, leyes de ingresos, cuenta pública, estados financieros, deuda, balanzas),
  "obras" (programas, reportes, fichas o avances de obra pública e infraestructura),
  "actas" (actas, minutas y sesiones de cabildo o del congreso),
  "contratos" (contratos, licitaciones, convocatorias de compras, adjudicaciones, padrones de proveedores).
- titulo: nombre claro del documento, máximo 90 caracteres, en español; incluye el tipo de documento y el año si
  aparece. Sin palabras como "Archivo", "PDF", "descargar" o "aquí".
- anio: el año al que se refiere el documento si aparece en el texto; si no, null.
- descripcion: 1 o 2 frases sencillas: qué es el documento y qué contiene."""


def leer_avance() -> set:
    try:
        return set(json.loads(AVANCE.read_text(encoding="utf-8")))
    except (FileNotFoundError, ValueError):
        return set()


def documentos_pendientes(con: sqlite3.Connection, hechos: set) -> list[dict]:
    filas = con.execute(
        """
        SELECT d.id, d.titulo, d.anio, d.url_fuente, d.municipio_id, s.clave AS seccion,
               COALESCE(m.nombre, e.nombre) AS lugar
        FROM documentos d JOIN secciones s ON s.id = d.seccion_id JOIN estados e ON e.id = d.estado_id
        LEFT JOIN municipios m ON m.id = d.municipio_id
        WHERE d.estatus = 'listo' AND d.titulo NOT LIKE '%(ejemplo)%'
        """
    ).fetchall()
    docs = []
    for f in filas:
        if f["id"] in hechos:
            continue
        texto = ""
        for (t,) in con.execute("SELECT texto FROM paginas WHERE documento_id = ? ORDER BY numero LIMIT 6", (f["id"],)):
            if len(t.strip()) >= 50:
                texto += " ".join(t.split()) + "\n"
            if len(texto) >= CARACTERES:
                break
        docs.append({**dict(f), "texto": texto[:CARACTERES]})
    return docs


def clasificar(doc: dict) -> tuple[dict, dict]:
    uso = {}
    usuario = (f"Título actual: {doc['titulo']}\nLugar: {doc['lugar']} "
               f"({'municipio' if doc['municipio_id'] else 'gobierno del estado'})\n"
               f"Liga oficial: {doc['url_fuente'] or 'no hay'}\nSección actual: {doc['seccion']}\n\n"
               f"Texto de las primeras páginas:\n{doc['texto']}\n\n{INSTRUCCIONES}")
    datos = llm.pedir_json(SISTEMA, usuario, uso)
    return datos, uso


def validar(doc: dict, datos: dict) -> dict:
    """Solo se aceptan valores que tienen sentido; lo demás se queda como estaba."""
    cambios = {}
    seccion = str(datos.get("seccion") or "").strip().lower()
    if seccion in SECCIONES and seccion != doc["seccion"]:
        cambios["seccion"] = seccion
    titulo = " ".join(str(datos.get("titulo") or "").split())
    if 8 <= len(titulo) <= 120 and titulo != doc["titulo"]:
        cambios["titulo"] = titulo
    try:
        anio = int(datos.get("anio"))
        if 1990 <= anio <= 2030 and anio != doc["anio"]:
            cambios["anio"] = anio
    except (TypeError, ValueError):
        pass
    descripcion = " ".join(str(datos.get("descripcion") or "").split())
    if 20 <= len(descripcion) <= 500:
        cambios["descripcion"] = descripcion
    return cambios


def guardar(con: sqlite3.Connection, doc: dict, cambios: dict) -> None:
    if "seccion" in cambios:
        con.execute("UPDATE documentos SET seccion_id = (SELECT id FROM secciones WHERE clave = ?) WHERE id = ?",
                    (cambios["seccion"], doc["id"]))
    if "titulo" in cambios:
        con.execute("UPDATE documentos SET titulo = ? WHERE id = ?", (cambios["titulo"], doc["id"]))
    if "anio" in cambios:
        con.execute("UPDATE documentos SET anio = ? WHERE id = ?", (cambios["anio"], doc["id"]))
    if "descripcion" in cambios:  # solo reemplaza el resumen automático sin IA; un resumen hecho por la IA se queda
        con.execute("UPDATE documentos SET resumen = ? WHERE id = ? AND (resumen IS NULL OR resumen LIKE 'Resumen automático sin IA%')",
                    (cambios["descripcion"], doc["id"]))
    con.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Reclasifica los documentos con IA.")
    parser.add_argument("--muestra", type=int, default=0, help="solo muestra lo que cambiaría en N documentos al azar")
    parser.add_argument("--hilos", type=int, default=8)
    args = parser.parse_args()
    if not llm.configurado():
        print("Falta DEEPSEEK_API_KEY en backend/.env")
        return 1
    con = db.abrir()
    hechos = leer_avance()
    docs = documentos_pendientes(con, hechos)
    if args.muestra:
        docs = random.Random(7).sample(docs, min(args.muestra, len(docs)))
    print(f"{len(docs)} documentos por reclasificar ({len(hechos)} ya hechos) · {args.hilos} a la vez", flush=True)
    inicio, uso_total, conteo = time.time(), {}, Counter()
    with ThreadPoolExecutor(max_workers=args.hilos) as grupo:
        tareas = {grupo.submit(clasificar, d): d for d in docs}
        for n, tarea in enumerate(as_completed(tareas), start=1):
            doc = tareas[tarea]
            try:
                datos, uso = tarea.result()
            except Exception as e:
                print(f"  [{doc['id']}] la IA falló: {type(e).__name__}: {e}")
                continue
            for k, v in uso.items():
                uso_total[k] = uso_total.get(k, 0) + v
            cambios = validar(doc, datos)
            if "seccion" in cambios:
                conteo[f"{doc['seccion']} → {cambios['seccion']}"] += 1
            conteo["título nuevo"] += "titulo" in cambios
            if args.muestra:
                print(f"\n[{doc['id']}] {doc['titulo'][:80]} ({doc['seccion']}, {doc['lugar']})\n"
                      f"   → {cambios.get('titulo', '(mismo título)')} | sección: {cambios.get('seccion', 'igual')}"
                      f" | año: {cambios.get('anio', 'igual')}\n   {cambios.get('descripcion', '')}")
                continue
            guardar(con, doc, cambios)
            hechos.add(doc["id"])
            if n % 50 == 0 or n == len(docs):
                AVANCE.write_text(json.dumps(sorted(hechos)), encoding="utf-8")
                print(f"  {n}/{len(docs)} · ${llm.costo_usd(uso_total):.3f} USD", flush=True)
    con.close()
    print(f"\nTerminado en {time.time() - inicio:.0f} s · costo aprox. ${llm.costo_usd(uso_total):.3f} USD "
          f"(precio de hora pico; fuera de ella es la mitad)")
    for cambio, cuantos in conteo.most_common():
        print(f"  {cambio}: {cuantos}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
