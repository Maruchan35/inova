"""Precalienta el caché del chatbot con las preguntas sugeridas (portada y estados): en la demo salen al instante
y se pueden revisar antes.

    cd backend
    python precalentar.py                # portada + los 12 estados con más documentos (~50 preguntas, ~$0.10 USD)
    python precalentar.py --estados 32   # todos los estados
    python precalentar.py --ver          # además imprime cada respuesta para revisarla

Las respuestas quedan en la tabla `respuestas` (el mismo caché de /api/preguntar) mientras no cambien los documentos
de ese lugar. Lo que gaste cuenta para el tope diario del chatbot (DEEPSEEK_TOPE_DIARIO_USD).
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor

from app import config  # noqa: F401  (carga backend/.env)
from app import preguntas
from app.db import abrir
from app.procesamiento import llm

# Los mismos filtros que arma /api/preguntar: así la clave del caché es idéntica a la de la página.
SIN_FILTROS = {"estado_id": None, "municipio_id": None, "seccion": None, "documento_id": None}


def responder(pregunta: str, filtros: dict) -> dict:
    con = abrir()
    try:
        return preguntas.responder(con, pregunta, **{**SIN_FILTROS, **filtros})
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Precalienta el caché del chatbot con las preguntas sugeridas.")
    parser.add_argument("--estados", type=int, default=12, help="cuántos estados (los que tienen más documentos)")
    parser.add_argument("--hilos", type=int, default=4)
    parser.add_argument("--ver", action="store_true", help="imprime cada respuesta")
    args = parser.parse_args()
    if not llm.configurado():
        print("Falta DEEPSEEK_API_KEY en backend/.env")
        return 1

    con = abrir()
    lista = [(p, {}) for p in preguntas.sugeridas(con)]
    for (estado_id,) in con.execute(
        "SELECT estado_id FROM documentos WHERE estatus = 'listo' GROUP BY estado_id ORDER BY COUNT(*) DESC LIMIT ?",
        (args.estados,),
    ).fetchall():
        lista += [(p, {"estado_id": estado_id}) for p in preguntas.sugeridas(con, estado_id)]
    con.close()
    print(f"{len(lista)} preguntas · {args.hilos} a la vez", flush=True)

    total, por_origen = 0.0, {}
    with ThreadPoolExecutor(max_workers=args.hilos) as grupo:
        for (pregunta, filtros), r in zip(lista, grupo.map(lambda x: responder(*x), lista)):
            d = r["detalle"]
            total += d["costo_usd"]
            por_origen[d["origen"]] = por_origen.get(d["origen"], 0) + 1
            aviso = f" · cifras sin comprobar: {d['cifras_sin_verificar']}" if d["cifras_sin_verificar"] else ""
            print(f"  [{d['origen']}] {pregunta} · {len(r['citas'])} citas · ${d['costo_usd']:.4f}{aviso}", flush=True)
            if args.ver:
                print(f"      {r['respuesta'][:400]}", flush=True)
    print(f"\nListo: {por_origen} · ${total:.3f} USD (precio de hora pico; fuera de ella es la mitad)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
