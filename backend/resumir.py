"""Resúmenes con IA ("En resumen" y "Lo más importante") para los documentos que solo tienen el automático.

    cd backend
    python resumir.py --muestra 3     # resume 3 documentos al azar y muestra el resultado, sin guardar
    python resumir.py                 # todos los que falten (se puede interrumpir y retomar)
    python resumir.py --max-caracteres 60000   # lee menos de cada documento: más barato

Por defecto lee hasta 120 mil caracteres de cada documento (las primeras ~40-60 páginas, una sola llamada a la IA):
todo el texto de los 1,454 documentos cuesta ~$7 USD fuera de hora pico; con el tope, ~$3.

Usa el texto que ya está en la base (no vuelve a leer los PDF). Un documento tiene resumen automático cuando
sus puntos clave son fragmentos ("…texto…") o no tiene puntos. El avance queda en
documentos/_catalogo/resumidos.json.
"""

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from app import config  # noqa: F401  (carga backend/.env)
from app import db
from app.procesamiento import llm
from app.procesamiento.resumen import resumir_con_ia

RAIZ = Path(__file__).resolve().parents[1]
AVANCE = RAIZ / "documentos" / "_catalogo" / "resumidos.json"


def pendientes(con, hechos: set) -> list[dict]:
    filas = con.execute(
        """
        SELECT d.id, d.titulo FROM documentos d
        WHERE d.estatus = 'listo' AND d.titulo NOT LIKE '%(ejemplo)%'
          AND (NOT EXISTS (SELECT 1 FROM puntos_clave p WHERE p.documento_id = d.id)
               OR EXISTS (SELECT 1 FROM puntos_clave p WHERE p.documento_id = d.id AND p.texto LIKE '…%'))
        """
    ).fetchall()
    return [dict(f) for f in filas if f["id"] not in hechos]


def resumir(documento: dict, max_caracteres: int = 120_000) -> tuple:
    con = db.abrir()
    try:
        paginas, total = [], 0
        for (t,) in con.execute("SELECT texto FROM paginas WHERE documento_id = ? ORDER BY numero", (documento["id"],)):
            if total >= max_caracteres:
                break
            paginas.append(t)  # completas y en orden: los puntos citan su número de página
            total += len(t)
    finally:
        con.close()
    if sum(len(p.strip()) for p in paginas) < 300:
        return None, None, {}
    uso = {}
    resumen, puntos = resumir_con_ia(documento["titulo"], paginas, uso)
    return resumen, puntos, uso


def main() -> int:
    parser = argparse.ArgumentParser(description="Resúmenes con IA de los documentos que no los tienen.")
    parser.add_argument("--muestra", type=int, default=0)
    parser.add_argument("--hilos", type=int, default=4)
    parser.add_argument("--max-caracteres", type=int, default=120_000)
    args = parser.parse_args()
    if not llm.configurado():
        print("Falta DEEPSEEK_API_KEY en backend/.env")
        return 1
    try:
        hechos = set(json.loads(AVANCE.read_text(encoding="utf-8")))
    except (FileNotFoundError, ValueError):
        hechos = set()
    con = db.abrir()
    docs = pendientes(con, hechos)
    if args.muestra:
        docs = random.Random(3).sample(docs, min(args.muestra, len(docs)))
    print(f"{len(docs)} documentos por resumir ({len(hechos)} ya hechos) · {args.hilos} a la vez", flush=True)
    inicio, uso_total, hechos_ahora, fallas = time.time(), {}, 0, 0
    with ThreadPoolExecutor(max_workers=args.hilos) as grupo:
        tareas = {grupo.submit(resumir, d, args.max_caracteres): d for d in docs}
        for n, tarea in enumerate(as_completed(tareas), start=1):
            doc = tareas[tarea]
            try:
                resumen, puntos, uso = tarea.result()
            except Exception as e:  # la IA falló o no dio puntos con página válida: se queda el automático
                fallas += 1
                print(f"  [{doc['id']}] no se pudo resumir: {type(e).__name__}: {str(e)[:120]}", flush=True)
                if "402" in str(e):  # sin saldo en DeepSeek: no tiene caso seguir
                    print("DeepSeek no tiene saldo (402). Recarga y vuelve a correr: sigue donde se quedó.", flush=True)
                    grupo.shutdown(wait=False, cancel_futures=True)
                    break
                continue
            for k, v in uso.items():
                uso_total[k] = uso_total.get(k, 0) + v
            if resumen is None:
                continue
            if args.muestra:
                print(f"\n[{doc['id']}] {doc['titulo']}\n  {resumen}\n" +
                      "\n".join(f"  • {p['texto']} (pág. {p['pagina']})" for p in puntos))
                continue
            con.execute("UPDATE documentos SET resumen = ? WHERE id = ?", (resumen, doc["id"]))
            con.execute("DELETE FROM puntos_clave WHERE documento_id = ?", (doc["id"],))
            con.executemany("INSERT INTO puntos_clave (documento_id, orden, texto, pagina) VALUES (?, ?, ?, ?)",
                            [(doc["id"], i, p["texto"], p["pagina"]) for i, p in enumerate(puntos, start=1)])
            con.commit()
            hechos.add(doc["id"])
            hechos_ahora += 1
            if n % 25 == 0 or n == len(docs):
                AVANCE.write_text(json.dumps(sorted(hechos)), encoding="utf-8")
                print(f"  {n}/{len(docs)} · {hechos_ahora} resumidos · ${llm.costo_usd(uso_total):.3f} USD · "
                      f"{time.time() - inicio:.0f} s", flush=True)
    con.close()
    print(f"\nTerminado: {hechos_ahora} resumidos, {fallas} sin resumir, en {time.time() - inicio:.0f} s · "
          f"costo aprox. ${llm.costo_usd(uso_total):.3f} USD (precio de hora pico; fuera de ella es la mitad)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
