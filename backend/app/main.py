import sqlite3
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import config, preguntas, procesamiento
from .busqueda import buscar_fragmentos, filtros_sql
from .db import abrir, conectar
from .procesamiento import llm

app = FastAPI(title="CabildoAbierto AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Con = sqlite3.Connection


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
    return preguntas.responder(con, datos.pregunta, **datos.model_dump(exclude={"pregunta"}))


@app.get("/api/proveedores/concentracion")
def concentracion(
    estado_id: int | None = None,
    municipio_id: int | None = None,
    con: Con = Depends(conectar),
):
    where, params = filtros_sql(estado_id=estado_id, municipio_id=municipio_id)
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


# --- Subida y procesamiento de documentos ---


def _procesar_en_segundo_plano(documento_id: int, ruta: Path) -> None:
    con = abrir()
    try:
        procesamiento.procesar(con, documento_id, ruta)
    finally:
        con.close()


@app.post("/api/documentos", status_code=201)
async def subir_documento(
    tareas: BackgroundTasks,
    archivo: UploadFile = File(...),
    estado_id: int = Form(...),
    municipio_id: str = Form(""),  # vacío = documento estatal
    seccion: str = Form(...),
    titulo: str = Form(...),
    anio: str = Form(""),
    con: Con = Depends(conectar),
):
    contenido = await archivo.read()
    if not contenido.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="El archivo no es un PDF")
    municipio = int(municipio_id) if municipio_id.strip() else None
    if not con.execute("SELECT 1 FROM estados WHERE id = ?", (estado_id,)).fetchone():
        raise HTTPException(status_code=400, detail="Estado no existe")
    if municipio and not con.execute(
        "SELECT 1 FROM municipios WHERE id = ? AND estado_id = ?", (municipio, estado_id)
    ).fetchone():
        raise HTTPException(status_code=400, detail="El municipio no existe en ese estado")
    fila_seccion = con.execute("SELECT id FROM secciones WHERE clave = ?", (seccion,)).fetchone()
    if not fila_seccion:
        raise HTTPException(status_code=400, detail="Sección no existe")

    cursor = con.execute(
        "INSERT INTO documentos (estado_id, municipio_id, seccion_id, titulo, anio) VALUES (?, ?, ?, ?, ?)",
        (estado_id, municipio, fila_seccion["id"], titulo.strip(), int(anio) if anio.strip() else None),
    )
    documento_id = cursor.lastrowid
    config.SUBIDOS_DIR.mkdir(parents=True, exist_ok=True)
    ruta = config.SUBIDOS_DIR / f"{documento_id}.pdf"
    ruta.write_bytes(contenido)
    con.execute("UPDATE documentos SET archivo = ? WHERE id = ?", (str(ruta), documento_id))
    con.commit()

    tareas.add_task(_procesar_en_segundo_plano, documento_id, ruta)
    return {"id": documento_id, "estatus": "pendiente"}


# --- Página de prueba del motor (solo para desarrollo; no es parte del contrato) ---


@app.get("/api/prueba/motor")
def estado_motor():
    return {"ia_configurada": llm.configurado(), "modelo": llm.modelo()}


@app.get("/api/prueba/documentos/{documento_id}")
def bitacora_documento(documento_id: int):
    return procesamiento.BITACORA.get(documento_id) or {}


@app.get("/api/prueba/preguntas")
def bitacora_preguntas():
    """Últimas preguntas: de dónde salió la respuesta (caché propio, DeepSeek o respaldo), tiempo y costo."""
    return list(preguntas.BITACORA)


@app.get("/prueba", response_class=HTMLResponse)
def pagina_prueba():
    return (Path(__file__).parent / "prueba.html").read_text(encoding="utf-8")


@app.get("/vista", response_class=HTMLResponse)
def vista_previa():
    """Vista previa provisional del lado del ciudadano, con los datos reales de la API."""
    return (Path(__file__).parent / "vista.html").read_text(encoding="utf-8")
