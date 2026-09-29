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


def _consulta_fts(texto: str) -> str:
    # Palabras de 3+ letras, entre comillas para que FTS5 no las interprete como operadores.
    palabras = [p for p in re.findall(r"\w+", texto, flags=re.UNICODE) if len(p) >= 3]
    return " OR ".join(f'"{p}"' for p in palabras)


def buscar_fragmentos(con: sqlite3.Connection, texto: str, limite: int = 10) -> list[dict]:
    consulta = _consulta_fts(texto)
    if not consulta:
        return []
    filas = con.execute(
        """
        SELECT a.id AS acta_id, a.titulo AS acta_titulo, p.numero AS pagina,
               snippet(paginas_fts, 0, '[[', ']]', '…', 24) AS fragmento
        FROM paginas_fts
        JOIN paginas p ON p.id = paginas_fts.rowid
        JOIN actas a ON a.id = p.acta_id
        WHERE paginas_fts MATCH ?
        ORDER BY bm25(paginas_fts)
        LIMIT ?
        """,
        (consulta, limite),
    ).fetchall()
    return [dict(f) for f in filas]


@app.get("/api/salud")
def salud():
    return {"estado": "ok"}


@app.get("/api/actas")
def listar_actas(con: sqlite3.Connection = Depends(conectar)):
    filas = con.execute(
        """
        SELECT a.id, a.titulo, a.fecha, a.municipio, COUNT(p.id) AS paginas
        FROM actas a LEFT JOIN paginas p ON p.acta_id = a.id
        GROUP BY a.id ORDER BY a.fecha DESC
        """
    ).fetchall()
    return [dict(f) for f in filas]


@app.get("/api/actas/{acta_id}/paginas/{numero}")
def ver_pagina(acta_id: int, numero: int, con: sqlite3.Connection = Depends(conectar)):
    fila = con.execute(
        """
        SELECT a.id AS acta_id, a.titulo AS acta_titulo, p.numero AS pagina, p.texto
        FROM paginas p JOIN actas a ON a.id = p.acta_id
        WHERE a.id = ? AND p.numero = ?
        """,
        (acta_id, numero),
    ).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Página no encontrada")
    return dict(fila)


@app.get("/api/buscar")
def buscar(q: str, con: sqlite3.Connection = Depends(conectar)):
    return {"consulta": q, "resultados": buscar_fragmentos(con, q)}


class Pregunta(BaseModel):
    pregunta: str


@app.post("/api/preguntar")
def preguntar(datos: Pregunta, con: sqlite3.Connection = Depends(conectar)):
    citas = buscar_fragmentos(con, datos.pregunta, limite=5)
    if not citas:
        respuesta = "No encontré información sobre eso en las actas cargadas."
    else:
        respuesta = f"Encontré {len(citas)} fragmento(s) relevante(s) en las actas."
    return {"pregunta": datos.pregunta, "respuesta": respuesta, "citas": citas}


@app.get("/api/proveedores/concentracion")
def concentracion(con: sqlite3.Connection = Depends(conectar)):
    filas = con.execute(
        """
        SELECT pr.id, pr.nombre, COUNT(c.id) AS contratos, SUM(c.monto) AS monto_total
        FROM contratos c JOIN proveedores pr ON pr.id = c.proveedor_id
        GROUP BY pr.id ORDER BY monto_total DESC
        """
    ).fetchall()
    total = sum(f["monto_total"] for f in filas) or 1
    return [
        {**dict(f), "porcentaje": round(100 * f["monto_total"] / total, 1)}
        for f in filas
    ]
