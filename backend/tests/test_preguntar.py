import threading
import time
from types import SimpleNamespace

import pytest


@pytest.fixture
def ia(cliente, monkeypatch):
    """IA simulada: registra lo que se le manda y devuelve lo que diga `ia.respuesta`."""
    from app import preguntas

    falsa = SimpleNamespace(llamadas=[], espera=0, error=None,
                            respuesta={"encontrado": True, "respuesta": "Seguridad recibe 28%.", "fuentes": [2]})

    def pedir_json(sistema, usuario, uso):
        falsa.llamadas.append(usuario)
        time.sleep(falsa.espera)
        if falsa.error:
            raise falsa.error
        uso["entrada"] = uso.get("entrada", 0) + 100
        uso["llamadas"] = uso.get("llamadas", 0) + 1
        return falsa.respuesta

    monkeypatch.setenv("DEEPSEEK_API_KEY", "clave-de-prueba")
    monkeypatch.setattr(preguntas.llm, "pedir_json", pedir_json)
    preguntas.limpiar_cache()
    yield falsa
    preguntas.limpiar_cache()


def preguntar(cliente, pregunta, **filtros):
    return cliente.post("/api/preguntar", json={"pregunta": pregunta, **filtros}).json()


def test_documento_completo_con_paginas_validadas_y_respuesta_guardada(cliente, ia):
    ia.respuesta["fuentes"] = [2, 99, "x", 2]  # 99 no existe y "x" no es página: se descartan
    r = preguntar(cliente, "¿Cuánto recibe seguridad?", documento_id=2)
    assert r["respuesta"] == "Seguridad recibe 28%."
    assert [(c["documento_id"], c["pagina"]) for c in r["citas"]] == [(2, 2)]
    assert set(r["citas"][0]) == {"documento_id", "documento_titulo", "seccion", "lugar", "pagina", "fragmento"}
    assert "[[seguridad]]" in r["citas"][0]["fragmento"].lower()

    enviado = ia.llamadas[0]
    assert enviado.startswith("DOCUMENTO: Presupuesto de Egresos 2026 (ejemplo)")
    assert "[Página 1]" in enviado and "[Página 3]" in enviado
    assert enviado.endswith("PREGUNTA: ¿Cuánto recibe seguridad?")

    # La misma pregunta escrita distinto: sale del caché propio, sin llamar otra vez a la IA.
    otra = preguntar(cliente, "cuanto recibe SEGURIDAD", documento_id=2)
    assert (otra["pregunta"], otra["respuesta"], otra["citas"]) == ("cuanto recibe SEGURIDAD", r["respuesta"], r["citas"])
    assert len(ia.llamadas) == 1
    bitacora = cliente.get("/api/prueba/preguntas").json()
    assert [b["origen"] for b in bitacora[:2]] == ["caché propio", "DeepSeek"]


def test_el_documento_va_primero_y_siempre_igual_para_el_cache_de_deepseek(cliente, ia):
    preguntar(cliente, "¿Cuánto recibe salud?", documento_id=2)
    preguntar(cliente, "¿Cuál es el monto total?", documento_id=2)
    primera, segunda = (u.split("PREGUNTA:")[0] for u in ia.llamadas)
    assert primera == segunda


def test_pregunta_sobre_un_lugar_usa_las_paginas_relevantes(cliente, ia):
    ia.respuesta = {"encontrado": True, "respuesta": "El mercado costó $2,300,000.", "fuentes": [1]}
    r = preguntar(cliente, "¿Cuánto costó el mercado?", municipio_id=1)
    assert r["citas"][0]["documento_id"] == 3 and r["citas"][0]["pagina"] == 1
    assert "[Fuente 1] Programa de Obra Pública 2026 (ejemplo) (Irapuato), página 1" in ia.llamadas[0]
    assert "DOCUMENTO:" not in ia.llamadas[0]


def test_sin_paginas_relacionadas_no_se_llama_a_la_ia(cliente, ia):
    r = preguntar(cliente, "¿Cuántos astronautas hay?", municipio_id=1)
    assert (r["respuesta"], r["citas"], ia.llamadas) == ("No encontré información sobre eso en los documentos cargados.", [], [])


def test_si_el_documento_no_lo_dice_no_hay_citas(cliente, ia):
    ia.respuesta = {"encontrado": False, "respuesta": "El documento no habla de deporte.", "fuentes": []}
    r = preguntar(cliente, "¿Cuánto se gasta en deporte?", documento_id=2)
    assert (r["respuesta"], r["citas"]) == ("El documento no habla de deporte.", [])


def test_respuesta_parcial_conserva_sus_paginas(cliente, ia):
    ia.respuesta = {"encontrado": False, "respuesta": "Solo dice que salud recibe 12%, no el monto.", "fuentes": [2]}
    r = preguntar(cliente, "¿Cuántos pesos recibe salud?", documento_id=2)
    assert [(c["documento_id"], c["pagina"]) for c in r["citas"]] == [(2, 2)]


@pytest.mark.parametrize("problema", ["sin páginas", "error"])
def test_si_la_ia_falla_se_usa_el_respaldo_y_no_se_guarda(cliente, ia, problema):
    if problema == "error":
        ia.error = RuntimeError("DeepSeek no responde")
    else:
        ia.respuesta = {"encontrado": True, "respuesta": "Son 5 mil millones.", "fuentes": []}  # dato sin página
    for _ in range(2):
        r = preguntar(cliente, "¿Cuánto costó el mercado?", municipio_id=1)
        assert r["respuesta"].startswith("Encontré") and r["citas"][0]["documento_id"] == 3
    assert len(ia.llamadas) == 2  # no se guardó: se vuelve a intentar con la IA
    assert cliente.get("/api/prueba/preguntas").json()[0]["origen"] == "respaldo sin IA"


def test_misma_pregunta_al_mismo_tiempo_llama_una_sola_vez_a_la_ia(cliente, ia):
    from app import preguntas
    from app.db import abrir

    ia.espera = 0.3
    ia.respuesta = {"encontrado": True, "respuesta": "El mercado costó $2,300,000.", "fuentes": [1]}
    filtros = {"estado_id": None, "municipio_id": 1, "seccion": None, "documento_id": None}
    respuestas = []

    def ciudadano():
        con = abrir()
        try:
            respuestas.append(preguntas.responder(con, "¿Cuánto costó el mercado?", **filtros)["respuesta"])
        finally:
            con.close()

    hilos = [threading.Thread(target=ciudadano) for _ in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert respuestas == ["El mercado costó $2,300,000."] * 8
    assert len(ia.llamadas) == 1


def test_un_documento_nuevo_en_el_lugar_invalida_la_respuesta_guardada(cliente, ia):
    from app.db import abrir

    ia.respuesta = {"encontrado": True, "respuesta": "El mercado costó $2,300,000.", "fuentes": [1]}
    preguntar(cliente, "¿Cuánto costó el mercado?", municipio_id=1)
    con = abrir()
    try:
        nuevo = con.execute(
            "INSERT INTO documentos (estado_id, municipio_id, seccion_id, titulo, estatus) VALUES (1, 1, 3, 'Nuevo', 'listo')"
        ).lastrowid
        con.commit()
        preguntar(cliente, "¿Cuánto costó el mercado?", municipio_id=1)
        assert len(ia.llamadas) == 2
    finally:
        con.execute("DELETE FROM documentos WHERE id = ?", (nuevo,))
        con.commit()
        con.close()


def test_cada_respuesta_dice_de_donde_salio(cliente, ia):
    primera = preguntar(cliente, "¿Cuánto recibe seguridad?", documento_id=2)["detalle"]
    repetida = preguntar(cliente, "¿cuanto recibe seguridad?", documento_id=2)["detalle"]
    assert (primera["origen"], primera["modo"], repetida["origen"]) == ("ia", "documento completo", "cache")
    assert primera["costo_usd"] > 0 and repetida["costo_usd"] == 0 and primera["motivo"] is None
    ia.error = RuntimeError("sin conexión")
    falla = preguntar(cliente, "¿Cuánto costó el mercado?", municipio_id=1)["detalle"]
    assert falla["origen"] == "sin_ia" and "no está disponible" in falla["motivo"]


def test_sin_clave_de_ia_lo_dice(cliente):
    detalle = preguntar(cliente, "¿Cuánto costó el mercado?", municipio_id=1)["detalle"]
    assert detalle["origen"] == "sin_ia" and detalle["motivo"]
