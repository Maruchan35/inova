import re
import sqlite3

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import conectar

app = FastAPI(title="CabildoAbierto AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Con = sqlite3.Connection


def _filtros(estado_id=None, municipio_id=None, seccion=None, documento_id=None):
    """Condiciones WHERE opcionales sobre documentos (d) y secciones (s)."""
    condiciones, params = [], []
    for valor, sql in (
        (estado_id, "d.estado_id = ?"),
        (municipio_id, "d.municipio_id = ?"),
        (seccion, "s.clave = ?"),
        (documento_id, "d.id = ?"),
    ):
        if valor is not None:
            condiciones.append(sql)
            params.append(valor)
    return "".join(f" AND {c}" for c in condiciones), params


def _consulta_fts(texto: str) -> str:
    # Palabras de 3+ letras, entre comillas para que FTS5 no las interprete como operadores.
    palabras = [p for p in re.findall(r"\w+", texto, flags=re.UNICODE) if len(p) >= 3]
    return " OR ".join(f'"{p}"' for p in palabras)


def buscar_fragmentos(con: Con, texto: str, limite: int = 10, **filtros) -> list[dict]:
    consulta = _consulta_fts(texto)
    if not consulta:
        return []
    where, params = _filtros(**filtros)
    filas = con.execute(
        f"""
        SELECT d.id AS documento_id, d.titulo AS documento_titulo, s.clave AS seccion,
               COALESCE(m.nombre, e.nombre) AS lugar, p.numero AS pagina,
               snippet(paginas_fts, 0, '[[', ']]', '…', 24) AS fragmento
        FROM paginas_fts
        JOIN paginas p ON p.id = paginas_fts.rowid
        JOIN documentos d ON d.id = p.documento_id
        JOIN secciones s ON s.id = d.seccion_id
        JOIN estados e ON e.id = d.estado_id
        LEFT JOIN municipios m ON m.id = d.municipio_id
        WHERE paginas_fts MATCH ?{where}
        ORDER BY bm25(paginas_fts)
        LIMIT ?
        """,
        (consulta, *params, limite),
    ).fetchall()
    return [dict(f) for f in filas]


def _secciones_con_documentos(con: Con, estado_id: int, municipio_id: int | None) -> list[dict]:
    secciones = [dict(s) for s in con.execute("SELECT id, clave, nombre FROM secciones ORDER BY orden")]
    documentos = con.execute(
        """
        SELECT id, seccion_id, titulo, anio, fecha, total_paginas, estatus
        FROM documentos
        WHERE estado_id = ? AND municipio_id IS ?
        ORDER BY fecha DESC
        """,
        (estado_id, municipio_id),
    ).fetchall()
    for s in secciones:
        s["documentos"] = [
            {k: d[k] for k in d.keys() if k != "seccion_id"} for d in documentos if d["seccion_id"] == s["id"]
        ]
        del s["id"]
    return secciones


@app.get("/api/salud")
def salud():
    return {"estado": "ok"}


@app.get("/api/secciones")
def listar_secciones(con: Con = Depends(conectar)):
    return [dict(f) for f in con.execute("SELECT clave, nombre FROM secciones ORDER BY orden")]


@app.get("/api/estados")
def listar_estados(con: Con = Depends(conectar)):
    estados = [dict(e) for e in con.execute("SELECT id, nombre FROM estados ORDER BY nombre")]
    for e in estados:
        e["municipios"] = [
            dict(m)
            for m in con.execute("SELECT id, nombre FROM municipios WHERE estado_id = ? ORDER BY nombre", (e["id"],))
        ]
    return estados


@app.get("/api/estados/{estado_id}")
def ver_estado(estado_id: int, con: Con = Depends(conectar)):
    estado = con.execute("SELECT id, nombre FROM estados WHERE id = ?", (estado_id,)).fetchone()
    if estado is None:
        raise HTTPException(status_code=404, detail="Estado no encontrado")
    municipios = con.execute(
        "SELECT id, nombre FROM municipios WHERE estado_id = ? ORDER BY nombre", (estado_id,)
    ).fetchall()
    return {
        "tipo": "estado",
        **dict(estado),
        "municipios": [dict(m) for m in municipios],
        "secciones": _secciones_con_documentos(con, estado_id, None),
    }


@app.get("/api/municipios/{municipio_id}")
def ver_municipio(municipio_id: int, con: Con = Depends(conectar)):
    fila = con.execute(
        """
        SELECT m.id, m.nombre, e.id AS estado_id, e.nombre AS estado_nombre
        FROM municipios m JOIN estados e ON e.id = m.estado_id WHERE m.id = ?
        """,
        (municipio_id,),
    ).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Municipio no encontrado")
    return {
        "tipo": "municipio",
        "id": fila["id"],
        "nombre": fila["nombre"],
        "estado": {"id": fila["estado_id"], "nombre": fila["estado_nombre"]},
        "secciones": _secciones_con_documentos(con, fila["estado_id"], fila["id"]),
    }


@app.get("/api/documentos/{documento_id}")
def ver_documento(documento_id: int, con: Con = Depends(conectar)):
    d = con.execute(
        """
        SELECT d.id, d.titulo, d.anio, d.fecha, d.total_paginas, d.estatus, d.error, d.resumen,
               s.clave AS seccion_clave, s.nombre AS seccion_nombre,
               e.id AS estado_id, e.nombre AS estado_nombre,
               m.id AS municipio_id, m.nombre AS municipio_nombre
        FROM documentos d
        JOIN secciones s ON s.id = d.seccion_id
        JOIN estados e ON e.id = d.estado_id
        LEFT JOIN municipios m ON m.id = d.municipio_id
        WHERE d.id = ?
        """,
        (documento_id,),
    ).fetchone()
    if d is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    puntos = con.execute(
        "SELECT texto, pagina FROM puntos_clave WHERE documento_id = ? ORDER BY orden", (documento_id,)
    ).fetchall()
    return {
        **{k: d[k] for k in ("id", "titulo", "anio", "fecha", "total_paginas", "estatus", "error", "resumen")},
        "seccion": {"clave": d["seccion_clave"], "nombre": d["seccion_nombre"]},
        "estado": {"id": d["estado_id"], "nombre": d["estado_nombre"]},
        "municipio": {"id": d["municipio_id"], "nombre": d["municipio_nombre"]} if d["municipio_id"] else None,
        "puntos_clave": [dict(p) for p in puntos],
    }


@app.get("/api/documentos/{documento_id}/paginas/{numero}")
def ver_pagina(documento_id: int, numero: int, con: Con = Depends(conectar)):
    fila = con.execute(
        """
        SELECT d.id AS documento_id, d.titulo AS documento_titulo, p.numero AS pagina, p.texto
        FROM paginas p JOIN documentos d ON d.id = p.documento_id
        WHERE d.id = ? AND p.numero = ?
        """,
        (documento_id, numero),
    ).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Página no encontrada")
    return dict(fila)


@app.get("/api/buscar")
def buscar(
    q: str,
    estado_id: int | None = None,
    municipio_id: int | None = None,
    seccion: str | None = None,
    documento_id: int | None = None,
    con: Con = Depends(conectar),
):
    resultados = buscar_fragmentos(
        con, q, estado_id=estado_id, municipio_id=municipio_id, seccion=seccion, documento_id=documento_id
    )
    return {"consulta": q, "resultados": resultados}


class Pregunta(BaseModel):
    pregunta: str
    estado_id: int | None = None
    municipio_id: int | None = None
    seccion: str | None = None
    documento_id: int | None = None


@app.post("/api/preguntar")
def preguntar(datos: Pregunta, con: Con = Depends(conectar)):
    citas = buscar_fragmentos(con, datos.pregunta, limite=5, **datos.model_dump(exclude={"pregunta"}))
    if not citas:
        respuesta = "No encontré información sobre eso en los documentos cargados."
    else:
        respuesta = f"Encontré {len(citas)} fragmento(s) relevante(s) en los documentos."
    return {"pregunta": datos.pregunta, "respuesta": respuesta, "citas": citas}


@app.get("/api/proveedores/concentracion")
def concentracion(
    estado_id: int | None = None,
    municipio_id: int | None = None,
    con: Con = Depends(conectar),
):
    where, params = _filtros(estado_id=estado_id, municipio_id=municipio_id)
    filas = con.execute(
        f"""
        SELECT pr.id, pr.nombre, COUNT(c.id) AS contratos, SUM(c.monto) AS monto_total
        FROM contratos c
        JOIN proveedores pr ON pr.id = c.proveedor_id
        JOIN documentos d ON d.id = c.documento_id
        JOIN secciones s ON s.id = d.seccion_id
        WHERE 1 = 1{where}
        GROUP BY pr.id ORDER BY monto_total DESC
        """,
        params,
    ).fetchall()
    total = sum(f["monto_total"] for f in filas) or 1
    return [{**dict(f), "porcentaje": round(100 * f["monto_total"] / total, 1)} for f in filas]
