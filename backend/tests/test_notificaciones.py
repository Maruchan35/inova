import re

import pytest

from test_procesamiento import subir


@pytest.fixture
def avisos(cliente, monkeypatch):
    """Captura los WhatsApps en lugar de mandarlos."""
    from app import notificaciones

    enviados = []

    def enviar(telefono, texto):
        enviados.append((telefono, texto))
        return "enviado", None

    monkeypatch.setattr(notificaciones, "enviar", enviar)
    notificaciones.limpiar_limites()
    return enviados


def suscribir_y_verificar(cliente, avisos, telefono, **lugar):
    r = cliente.post("/api/suscripciones", json={"telefono": telefono, **lugar})
    assert r.status_code == 202 and r.json()["estatus"] == "codigo_enviado"
    codigo = re.search(r"\*(\d{6})\*", avisos[-1][1]).group(1)
    assert cliente.post("/api/suscripciones/verificar", json={"telefono": telefono, "codigo": codigo}).json()["estatus"] == "activa"


def mensajes_a(avisos, telefono):
    return [texto for tel, texto in avisos if tel == telefono]


def test_normalizar_telefono():
    from app.notificaciones import ErrorAviso, normalizar_telefono

    for texto in ("462 111 2233", "+52 (462) 111-2233", "524621112233", "5214621112233"):
        assert normalizar_telefono(texto) == "524621112233"
    for malo in ("12345", "1 555 123 4567", ""):
        with pytest.raises(ErrorAviso):
            normalizar_telefono(malo)


def test_suscribirse_verificar_y_recibir_aviso_de_documento_nuevo(cliente, avisos):
    r = cliente.post("/api/suscripciones", json={"telefono": "462 111 2233", "estado_id": 1, "municipio_id": 2})
    assert r.json() == {"estatus": "codigo_enviado", "lugar": "León"}
    assert cliente.post("/api/suscripciones/verificar", json={"telefono": "4621112233", "codigo": "000000"}).status_code == 400
    codigo = re.search(r"\*(\d{6})\*", avisos[-1][1]).group(1)
    assert cliente.post("/api/suscripciones/verificar", json={"telefono": "4621112233", "codigo": codigo}).json()["estatus"] == "activa"
    assert "Gobierno de León" in avisos[-1][1] and "BAJA" in avisos[-1][1]

    antes = len(avisos)
    assert cliente.post("/api/suscripciones", json={"telefono": "4621112233", "estado_id": 1, "municipio_id": 2}).json()["estatus"] == "ya_suscrito"
    assert len(avisos) == antes  # ya suscrito: no se manda otro código

    doc_id = subir(cliente, municipio_id="2", titulo="Presupuesto León 2026").json()["id"]
    (aviso,) = mensajes_a(avisos[antes:], "524621112233")
    assert "Gobierno de León" in aviso and "*Presupuesto León 2026*" in aviso
    assert "(pág. " in aviso and aviso.count("• ") == 2  # lo más importante, con su página
    assert f"/documento/{doc_id}" in aviso and "BAJA" in aviso

    from app import notificaciones
    from app.db import abrir

    con = abrir()
    try:
        assert notificaciones.notificar_documento(con, doc_id) == 0  # nunca dos veces el mismo documento
    finally:
        con.close()


def test_documentos_estatales_llegan_a_quien_sigue_un_municipio_y_no_al_reves(cliente, avisos):
    suscribir_y_verificar(cliente, avisos, "4622223344", estado_id=1, municipio_id=2)  # sigue a León
    suscribir_y_verificar(cliente, avisos, "4623334455", estado_id=1)                  # sigue al estado
    antes = len(avisos)
    subir(cliente, municipio_id="", titulo="Informe estatal")
    assert len(mensajes_a(avisos[antes:], "524622223344")) == 1
    assert len(mensajes_a(avisos[antes:], "524623334455")) == 1

    antes = len(avisos)
    subir(cliente, municipio_id="2", titulo="Acta de León")
    assert len(mensajes_a(avisos[antes:], "524622223344")) == 1
    assert mensajes_a(avisos[antes:], "524623334455") == []  # quien sigue al estado no recibe lo municipal


def test_no_se_puede_usar_para_llenar_de_codigos_un_numero(cliente, avisos):
    for _ in range(3):
        assert cliente.post("/api/suscripciones", json={"telefono": "4624445566", "estado_id": 1, "municipio_id": 1}).status_code == 202
    r = cliente.post("/api/suscripciones", json={"telefono": "4624445566", "estado_id": 1, "municipio_id": 1})
    assert r.status_code == 429


def test_datos_invalidos(cliente, avisos):
    assert cliente.post("/api/suscripciones", json={"telefono": "123", "estado_id": 1}).status_code == 400
    assert cliente.post("/api/suscripciones", json={"telefono": "4625556677", "estado_id": 1, "municipio_id": 99}).status_code == 400
    assert avisos == []


def test_baja_desde_whatsapp_requiere_el_token_del_bot(cliente, avisos, monkeypatch):
    monkeypatch.setenv("WHATSAPP_BOT_TOKEN", "secreto")
    suscribir_y_verificar(cliente, avisos, "4626667788", estado_id=1, municipio_id=2)
    assert cliente.post("/api/interno/baja", json={"telefono": "4626667788"}, headers={"X-Bot-Token": "otro"}).status_code == 403
    r = cliente.post("/api/interno/baja", json={"telefono": "524626667788"}, headers={"X-Bot-Token": "secreto"})
    assert r.json() == {"bajas": 1}
    antes = len(avisos)
    subir(cliente, municipio_id="2", titulo="Otro documento de León")
    assert mensajes_a(avisos[antes:], "524626667788") == []


def test_si_el_bot_no_responde_se_avisa_y_queda_en_la_bitacora(cliente, monkeypatch):
    from app import notificaciones

    notificaciones.limpiar_limites()
    monkeypatch.setenv("WHATSAPP_BOT_URL", "http://127.0.0.1:9")  # nadie escucha en ese puerto
    r = cliente.post("/api/suscripciones", json={"telefono": "4627778899", "estado_id": 1, "municipio_id": 1})
    assert r.status_code == 503
    assert cliente.get("/api/prueba/avisos").json()[0]["estatus"] == "error"
