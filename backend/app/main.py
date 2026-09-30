import os
import sqlite3
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from . import config, notificaciones, preguntas, procesamiento
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
    estado = con.execute("SELECT id, nombre, latitud, longitud FROM estados WHERE id = ?", (estado_id,)).fetchone()
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
        SELECT m.id, m.nombre, m.latitud, m.longitud, e.id AS estado_id, e.nombre AS estado_nombre
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
        "latitud": fila["latitud"],
        "longitud": fila["longitud"],
        "estado": {"id": fila["estado_id"], "nombre": fila["estado_nombre"]},
        "secciones": _secciones_con_documentos(con, fila["estado_id"], fila["id"]),
    }


def _pdf_original(archivo: str | None) -> Path | None:
    """El PDF que se procesó, si sigue en esta computadora. Rutas relativas: desde la raíz del repo."""
    if not archivo:
        return None
    ruta = Path(archivo)
    if not ruta.is_absolute():
        ruta = config.BACKEND.parent / ruta
    return ruta if ruta.suffix.lower() == ".pdf" and ruta.is_file() else None


@app.get("/api/documentos/{documento_id}")
def ver_documento(documento_id: int, con: Con = Depends(conectar)):
    d = con.execute(
        """
        SELECT d.id, d.titulo, d.anio, d.fecha, d.total_paginas, d.estatus, d.error, d.resumen, d.archivo,
               d.url_fuente, d.formato, d.fecha_publicacion, d.dependencia,
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
        "fuente": {k: d[k] for k in ("url_fuente", "formato", "fecha_publicacion", "dependencia")},
        "pdf_url": f"/api/documentos/{documento_id}/pdf" if _pdf_original(d["archivo"]) else None,
        "seccion": {"clave": d["seccion_clave"], "nombre": d["seccion_nombre"]},
        "estado": {"id": d["estado_id"], "nombre": d["estado_nombre"]},
        "municipio": {"id": d["municipio_id"], "nombre": d["municipio_nombre"]} if d["municipio_id"] else None,
        "puntos_clave": [dict(p) for p in puntos],
    }


@app.get("/api/documentos/{documento_id}/paginas/{numero}")
def ver_pagina(documento_id: int, numero: int, con: Con = Depends(conectar)):
    fila = con.execute(
        """
        SELECT d.id AS documento_id, d.titulo AS documento_titulo, p.numero AS pagina, p.texto,
               d.total_paginas, d.archivo
        FROM paginas p JOIN documentos d ON d.id = p.documento_id
        WHERE d.id = ? AND p.numero = ?
        """,
        (documento_id, numero),
    ).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Página no encontrada")
    pagina = {k: fila[k] for k in ("documento_id", "documento_titulo", "pagina", "texto", "total_paginas")}
    pagina["pdf_url"] = (f"/api/documentos/{documento_id}/pdf#page={numero}"
                         if _pdf_original(fila["archivo"]) else None)
    return pagina


@app.get("/api/documentos/{documento_id}/pdf")
def ver_pdf_original(documento_id: int, con: Con = Depends(conectar)):
    """El PDF original tal cual se procesó, para verificar cada dato en su página (#page=N)."""
    fila = con.execute("SELECT titulo, archivo FROM documentos WHERE id = ?", (documento_id,)).fetchone()
    ruta = _pdf_original(fila["archivo"]) if fila else None
    if ruta is None:
        raise HTTPException(status_code=404, detail="El PDF original no está disponible")
    return FileResponse(ruta, media_type="application/pdf", headers={"Content-Disposition": "inline"})


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
    historial: list[dict] = []  # la conversación: [{"pregunta": "...", "respuesta": "..."}], de la más vieja a la última


@app.post("/api/preguntar")
def preguntar(datos: Pregunta, con: Con = Depends(conectar)):
    return preguntas.responder(con, datos.pregunta, historial=datos.historial[-4:],
                               **datos.model_dump(exclude={"pregunta", "historial"}))


@app.get("/api/preguntas-sugeridas")
def preguntas_sugeridas(estado_id: int | None = None, municipio_id: int | None = None,
                        documento_id: int | None = None, con: Con = Depends(conectar)):
    """Preguntas de ejemplo para el chatbot según la página en la que se está."""
    return preguntas.sugeridas(con, estado_id, municipio_id, documento_id)


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


# --- Avisos por WhatsApp ---


class Suscripcion(BaseModel):
    telefono: str
    estado_id: int | None = None  # si viene municipio_id, el estado se toma del municipio
    municipio_id: int | None = None


class Verificacion(BaseModel):
    telefono: str
    codigo: str


class Baja(BaseModel):
    telefono: str | None = None
    token: str | None = None


def _aviso(funcion, *args):
    try:
        return funcion(*args)
    except notificaciones.ErrorAviso as e:
        raise HTTPException(status_code=e.estatus, detail=str(e))


@app.post("/api/suscripciones", status_code=202)
def suscribirse(datos: Suscripcion, con: Con = Depends(conectar)):
    """Manda un código por WhatsApp para confirmar que el número es de quien se suscribe."""
    return _aviso(notificaciones.suscribir, con, datos.telefono, datos.estado_id, datos.municipio_id)


@app.post("/api/suscripciones/verificar")
def verificar_suscripcion(datos: Verificacion, con: Con = Depends(conectar)):
    return _aviso(notificaciones.verificar, con, datos.telefono, datos.codigo)


@app.post("/api/suscripciones/baja")
def baja_suscripcion(datos: Baja, con: Con = Depends(conectar)):
    if not datos.token:
        raise HTTPException(status_code=400, detail="Falta el token de baja")
    return {"bajas": _aviso(notificaciones.baja_por_token, con, datos.token)}


@app.post("/api/interno/baja")
def baja_desde_whatsapp(datos: Baja, x_bot_token: str = Header(""), con: Con = Depends(conectar)):
    """La llama el bot de WhatsApp cuando alguien responde BAJA. Protegida con WHATSAPP_BOT_TOKEN."""
    esperado = os.environ.get("WHATSAPP_BOT_TOKEN", "")
    if not esperado or x_bot_token != esperado:
        raise HTTPException(status_code=403, detail="Token inválido")
    return {"bajas": _aviso(notificaciones.baja_por_telefono, con, datos.telefono or "")}


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


@app.get("/api/prueba/avisos")
def bitacora_avisos():
    """Últimos mensajes de WhatsApp (enviados o, sin bot, solo de prueba)."""
    return list(notificaciones.BITACORA)


@app.get("/prueba", response_class=HTMLResponse)
def pagina_prueba():
    return (Path(__file__).parent / "prueba.html").read_text(encoding="utf-8")


@app.get("/vista", response_class=HTMLResponse)
def vista_previa():
    """Vista previa provisional del lado del ciudadano, con los datos reales de la API."""
    return (Path(__file__).parent / "vista.html").read_text(encoding="utf-8")
