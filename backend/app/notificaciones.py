"""Avisos por WhatsApp: cuando un gobierno publica un documento, les llega a quienes siguen ese lugar.

1. La persona se suscribe con su número y su municipio (o estado); le llega un código por WhatsApp.
2. Con el código confirma que el número es suyo; sin eso nadie recibe avisos.
3. Al terminar de procesar un documento, se avisa a cada suscripción activa de ese lugar, una sola vez.
   El mensaje lleva lo más importante (ya calculado al procesar, sin gastar IA) y el enlace al documento.
4. Responder "BAJA" (el bot de backend/whatsapp avisa aquí) desactiva los avisos.

Los mensajes los manda el bot de backend/whatsapp. Sin WHATSAPP_BOT_URL en backend/.env se trabaja en
"modo prueba": los mensajes solo quedan en la bitácora (GET /api/prueba/avisos).
"""

import os
import re
import secrets
import sqlite3
import threading
import time
from collections import deque

import httpx

from . import config  # noqa: F401  (carga backend/.env)

# Copia de las tablas de datos/schema.sql (bloque datos): solo sirve para bases creadas antes de que
# existieran; con el esquema actual no hace nada.
TABLAS = """
CREATE TABLE IF NOT EXISTS suscripciones (
    id            INTEGER PRIMARY KEY,
    telefono      TEXT NOT NULL,               -- 52 + 10 dígitos
    estado_id     INTEGER NOT NULL REFERENCES estados(id),
    municipio_id  INTEGER REFERENCES municipios(id),  -- NULL = solo documentos estatales
    verificada    INTEGER NOT NULL DEFAULT 0,
    activa        INTEGER NOT NULL DEFAULT 1,
    codigo        TEXT,                        -- código de verificación; se borra al verificar
    codigo_expira REAL,
    token_baja    TEXT NOT NULL UNIQUE,
    creada_en     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_suscripciones_lugar ON suscripciones (telefono, estado_id, IFNULL(municipio_id, 0));
CREATE TABLE IF NOT EXISTS notificaciones (
    id             INTEGER PRIMARY KEY,
    suscripcion_id INTEGER NOT NULL REFERENCES suscripciones(id) ON DELETE CASCADE,
    documento_id   INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    estatus        TEXT NOT NULL,              -- 'enviado' | 'prueba' | 'error'
    detalle        TEXT,
    enviada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (suscripcion_id, documento_id)
);
"""

MINUTOS_CODIGO = 10
CODIGOS_POR_HORA = 3  # por número: que nadie use el bot para llenar de mensajes a un desconocido
PUNTOS_EN_AVISO = 2

BITACORA: deque = deque(maxlen=100)  # últimos mensajes (enviados o de prueba), para la demo
_pedidos: dict[str, list[float]] = {}
_candado = threading.Lock()


class ErrorAviso(ValueError):
    """Error que se muestra tal cual a la persona (número inválido, código vencido…)."""

    def __init__(self, mensaje: str, estatus: int = 400):
        super().__init__(mensaje)
        self.estatus = estatus


def asegurar_tablas(con: sqlite3.Connection) -> None:
    con.executescript(TABLAS)


def normalizar_telefono(texto: str) -> str:
    """'+52 (462) 123-4567', '462 123 4567' o '5214621234567' → '524621234567'."""
    digitos = "".join(c for c in str(texto) if c.isdigit())
    if len(digitos) == 13 and digitos.startswith("521"):
        digitos = "52" + digitos[3:]
    if len(digitos) == 10:
        digitos = "52" + digitos
    if len(digitos) != 12 or not digitos.startswith("52"):
        raise ErrorAviso("Escribe un número de celular de México de 10 dígitos.")
    return digitos


def limpiar_limites() -> None:
    with _candado:
        _pedidos.clear()


# --- Suscribirse, verificar y darse de baja ---


def suscribir(con: sqlite3.Connection, telefono: str, estado_id: int | None, municipio_id: int | None) -> dict:
    asegurar_tablas(con)
    telefono = normalizar_telefono(telefono)
    if municipio_id and not estado_id:  # el municipio ya dice de qué estado es
        fila = con.execute("SELECT estado_id FROM municipios WHERE id = ?", (municipio_id,)).fetchone()
        if fila is None:
            raise ErrorAviso("El municipio no existe.")
        estado_id = fila["estado_id"]
    if not estado_id:
        raise ErrorAviso("Elige un estado o un municipio.")
    lugar = _nombre_lugar(con, estado_id, municipio_id)
    existente = con.execute(
        "SELECT id, verificada, activa FROM suscripciones WHERE telefono = ? AND estado_id = ? AND IFNULL(municipio_id, 0) = ?",
        (telefono, estado_id, municipio_id or 0),
    ).fetchone()
    if existente and existente["verificada"] and existente["activa"]:
        return {"estatus": "ya_suscrito", "lugar": lugar}
    _contar_pedido(telefono)

    codigo = f"{secrets.randbelow(1_000_000):06d}"
    expira = time.time() + MINUTOS_CODIGO * 60
    if existente:
        con.execute("UPDATE suscripciones SET codigo = ?, codigo_expira = ?, activa = 1 WHERE id = ?", (codigo, expira, existente["id"]))
    else:
        con.execute(
            "INSERT INTO suscripciones (telefono, estado_id, municipio_id, codigo, codigo_expira, token_baja) VALUES (?, ?, ?, ?, ?, ?)",
            (telefono, estado_id, municipio_id, codigo, expira, secrets.token_urlsafe(16)),
        )
    con.commit()
    estatus, _ = enviar(telefono, f"Tu código de CabildoAbierto es *{codigo}*. Vence en {MINUTOS_CODIGO} minutos.\n"
                                  "Si no lo pediste, ignora este mensaje.")
    if estatus == "error":
        raise ErrorAviso("No pudimos mandarte el WhatsApp en este momento. Inténtalo en unos minutos.", 503)
    return {"estatus": "codigo_enviado", "lugar": lugar}


def verificar(con: sqlite3.Connection, telefono: str, codigo: str) -> dict:
    asegurar_tablas(con)
    telefono = normalizar_telefono(telefono)
    fila = con.execute(
        """
        SELECT id, estado_id, municipio_id FROM suscripciones
        WHERE telefono = ? AND codigo = ? AND codigo_expira > ? ORDER BY id DESC LIMIT 1
        """,
        (telefono, str(codigo).strip(), time.time()),
    ).fetchone()
    if fila is None:
        raise ErrorAviso("El código es incorrecto o ya venció. Pide uno nuevo.")
    con.execute("UPDATE suscripciones SET verificada = 1, activa = 1, codigo = NULL, codigo_expira = NULL WHERE id = ?", (fila["id"],))
    con.commit()
    lugar = _nombre_lugar(con, fila["estado_id"], fila["municipio_id"])
    enviar(telefono, f"Listo: te avisaremos por aquí cuando el *{_gobierno(lugar)}* publique documentos nuevos.\n\n"
                     "Para dejar de recibir avisos, responde BAJA.")
    return {"estatus": "activa", "lugar": lugar}


def baja_por_telefono(con: sqlite3.Connection, telefono: str) -> int:
    asegurar_tablas(con)
    cursor = con.execute("UPDATE suscripciones SET activa = 0 WHERE telefono = ?", (normalizar_telefono(telefono),))
    con.commit()
    return cursor.rowcount


def baja_por_token(con: sqlite3.Connection, token: str) -> int:
    asegurar_tablas(con)
    cursor = con.execute("UPDATE suscripciones SET activa = 0 WHERE token_baja = ?", (token,))
    con.commit()
    return cursor.rowcount


# --- Avisar de un documento nuevo ---


def notificar_documento(con: sqlite3.Connection, documento_id: int) -> int:
    """Avisa a las suscripciones activas del lugar del documento. Devuelve cuántos avisos nuevos se mandaron.

    Suscripción a un municipio: documentos de ese municipio y documentos estatales de su estado.
    Suscripción a un estado (sin municipio): documentos estatales.
    """
    asegurar_tablas(con)
    doc = con.execute(
        """
        SELECT d.id, d.titulo, d.estado_id, d.municipio_id, d.estatus, e.nombre AS estado, m.nombre AS municipio
        FROM documentos d JOIN estados e ON e.id = d.estado_id LEFT JOIN municipios m ON m.id = d.municipio_id
        WHERE d.id = ?
        """,
        (documento_id,),
    ).fetchone()
    if doc is None or doc["estatus"] != "listo":
        return 0
    if doc["municipio_id"] is None:
        destino = "s.estado_id = ?"
        params = [doc["estado_id"]]
    else:
        destino = "s.municipio_id = ?"
        params = [doc["municipio_id"]]
    suscripciones = con.execute(
        f"""
        SELECT s.id, s.telefono FROM suscripciones s
        WHERE s.verificada = 1 AND s.activa = 1 AND {destino}
          AND NOT EXISTS (SELECT 1 FROM notificaciones n WHERE n.suscripcion_id = s.id AND n.documento_id = ?)
        """,
        (*params, documento_id),
    ).fetchall()
    if not suscripciones:
        return 0
    texto = _mensaje_documento(con, doc)
    for s in {s["telefono"]: s for s in suscripciones}.values():  # un solo mensaje por teléfono
        estatus, detalle = enviar(s["telefono"], texto)
        con.executemany(
            "INSERT OR IGNORE INTO notificaciones (suscripcion_id, documento_id, estatus, detalle) VALUES (?, ?, ?, ?)",
            [(x["id"], documento_id, estatus, detalle) for x in suscripciones if x["telefono"] == s["telefono"]],
        )
    con.commit()
    return len({s["telefono"] for s in suscripciones})


def _mensaje_documento(con: sqlite3.Connection, doc: sqlite3.Row) -> str:
    lugar = doc["municipio"] or f"Estado de {doc['estado']}"
    puntos = con.execute(
        "SELECT texto, pagina FROM puntos_clave WHERE documento_id = ? ORDER BY orden LIMIT ?", (doc["id"], PUNTOS_EN_AVISO)
    ).fetchall()
    lineas = [f"📢 El *{_gobierno(lugar)}* publicó un documento nuevo:", f"*{doc['titulo']}*", ""]
    if puntos:
        lineas += ["Lo más importante:"] + [f"• {p['texto']}" + (f" (pág. {p['pagina']})" if p["pagina"] else "") for p in puntos] + [""]
    lineas += ["Léelo explicado y pregúntale a la IA:", enlace_documento(doc["id"]), "", "Para dejar de recibir avisos, responde BAJA."]
    return "\n".join(lineas)


def enlace_documento(documento_id: int) -> str:
    return os.environ.get("ENLACE_DOCUMENTO", "http://localhost:5173/documento/{id}").replace("{id}", str(documento_id))


def _gobierno(lugar: str) -> str:
    return f"Gobierno del {lugar}" if lugar.startswith("Estado de") else f"Gobierno de {lugar}"


def _nombre_lugar(con: sqlite3.Connection, estado_id: int, municipio_id: int | None) -> str:
    if municipio_id:
        fila = con.execute("SELECT nombre FROM municipios WHERE id = ? AND estado_id = ?", (municipio_id, estado_id)).fetchone()
        if fila is None:
            raise ErrorAviso("El municipio no existe en ese estado.")
        return fila["nombre"]
    fila = con.execute("SELECT nombre FROM estados WHERE id = ?", (estado_id,)).fetchone()
    if fila is None:
        raise ErrorAviso("El estado no existe.")
    return f"Estado de {fila['nombre']}"


def _contar_pedido(telefono: str) -> None:
    ahora = time.time()
    with _candado:
        recientes = [t for t in _pedidos.get(telefono, []) if ahora - t < 3600]
        if len(recientes) >= CODIGOS_POR_HORA:
            raise ErrorAviso("Ya pediste varios códigos para este número. Espera una hora e inténtalo de nuevo.", 429)
        _pedidos[telefono] = recientes + [ahora]


# --- Envío ---


def enviar(telefono: str, texto: str) -> tuple[str, str | None]:
    """Manda un mensaje por el bot de WhatsApp. Devuelve (estatus, detalle). Nunca lanza errores."""
    url = os.environ.get("WHATSAPP_BOT_URL", "").strip()
    # La bitácora se puede ver desde fuera: nunca guarda el código de verificación ni el número completo.
    oculto = re.sub(r"\*\d{6}\*", "*••••••*", texto)
    registro = {"telefono": f"{telefono[:4]}******{telefono[-2:]}", "texto": oculto, "hora": time.strftime("%H:%M:%S")}
    if not url:
        estatus, detalle = "prueba", "Sin WHATSAPP_BOT_URL: el mensaje no se envió"
    else:
        try:
            r = httpx.post(f"{url.rstrip('/')}/enviar", json={"telefono": telefono, "texto": texto},
                           headers={"X-Bot-Token": os.environ.get("WHATSAPP_BOT_TOKEN", "")}, timeout=10)
            estatus, detalle = ("enviado", None) if r.status_code == 202 else ("error", r.text[:200])
        except httpx.HTTPError as e:
            estatus, detalle = "error", f"El bot de WhatsApp no responde ({type(e).__name__})"
    BITACORA.appendleft({**registro, "estatus": estatus, "detalle": detalle})
    return estatus, detalle
