"""Catálogo oficial de los 32 estados y todos sus municipios, directo del INEGI.

    python recolector/catalogo.py

Escribe documentos/_catalogo/estados.csv y documentos/_catalogo/municipios.csv con la clave INEGI de cada lugar
(la misma que usan el Censo, Transparencia Presupuestaria y la Plataforma Nacional de Transparencia).
Fuente: Catálogo Único de Claves Geoestadísticas, https://gaia.inegi.org.mx/wscatgeo/v2/
"""

import httpx

from comun import AGENTE, FUENTES, escribir_csv

API = "https://gaia.inegi.org.mx/wscatgeo/v2"


def descargar(cliente: httpx.Client, ruta: str) -> list[dict]:
    r = cliente.get(f"{API}/{ruta}")
    r.raise_for_status()
    return r.json()["datos"]


def main() -> None:
    with httpx.Client(headers={"User-Agent": AGENTE}, timeout=60) as cliente:
        estados = descargar(cliente, "mgee/")
        municipios = []
        for e in estados:
            for m in descargar(cliente, f"mgem/{e['cve_ent']}"):
                municipios.append({
                    "clave_inegi": m["cvegeo"],
                    "clave_estado": m["cve_ent"],
                    "estado": e["nomgeo"],
                    "clave_municipio": m["cve_mun"],
                    "municipio": m["nomgeo"],
                    "cabecera": m.get("nom_cab", ""),
                    "poblacion": m.get("pob_total", ""),
                })
            print(f"{e['cve_ent']} {e['nomgeo']}: {sum(1 for m in municipios if m['clave_estado'] == e['cve_ent'])} municipios")

    escribir_csv(
        FUENTES / "estados.csv",
        [{"clave_estado": e["cve_ent"], "estado": e["nomgeo"], "abreviatura": e["nom_abrev"],
          "poblacion": e["pob_total"]} for e in estados],
        ["clave_estado", "estado", "abreviatura", "poblacion"],
    )
    escribir_csv(FUENTES / "municipios.csv", municipios, list(municipios[0]))
    print(f"\n{len(estados)} estados y {len(municipios)} municipios → {FUENTES}")


if __name__ == "__main__":
    main()
