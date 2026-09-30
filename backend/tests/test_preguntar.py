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


def test_en_un_municipio_tambien_busca_en_los_documentos_estatales(cliente, ia):
    # "escuelas" solo está en el informe estatal (documento 4), no en los documentos de Irapuato
    ia.respuesta = {"encontrado": True, "respuesta": "Se construyeron 35 escuelas.", "fuentes": [1]}
    r = preguntar(cliente, "¿Cuántas escuelas se construyeron?", municipio_id=1)
    assert [(c["documento_id"], c["pagina"]) for c in r["citas"]] == [(4, 2)]
    assert "Informe de Gobierno del Estado 2025 (ejemplo)" in ia.llamadas[0]
    assert r["detalle"]["alcance"] == "lugar"


def test_si_no_hay_nada_del_lugar_busca_en_todo_el_catalogo(cliente, ia):
    # El mercado solo aparece en un documento de Irapuato; la pregunta se hace desde León
    ia.respuesta = {"encontrado": True, "respuesta": "El mercado costó $2,300,000.", "fuentes": [1]}
    r = preguntar(cliente, "¿Cuánto costó el mercado?", municipio_id=2)
    assert r["citas"][0]["documento_id"] == 3 and r["detalle"]["alcance"] == "todo"


def test_sin_ia_tambien_busca_en_los_estatales(cliente):
    r = preguntar(cliente, "¿Cuántas escuelas se construyeron?", municipio_id=1)
    assert r["respuesta"].startswith("Encontré") and r["citas"][0]["documento_id"] == 4


def test_las_respuestas_guardadas_sobreviven_a_un_reinicio(cliente, ia):
    from app import preguntas
    from app.db import abrir

    primera = preguntar(cliente, "¿Cuánto recibe seguridad pública?", documento_id=2)
    assert primera["detalle"]["origen"] == "ia" and len(ia.llamadas) == 1
    preguntas.limpiar_cache(tambien_guardadas=False)  # como si el servidor se reiniciara
    despues = preguntar(cliente, "cuanto recibe SEGURIDAD publica", documento_id=2)
    assert despues["detalle"]["origen"] == "cache" and len(ia.llamadas) == 1  # sin volver a pagarle a la IA
    assert (despues["respuesta"], despues["citas"]) == (primera["respuesta"], primera["citas"])
    con = abrir()
    try:
        assert con.execute("SELECT COUNT(*) FROM respuestas").fetchone()[0] == 1
    finally:
        con.close()


def test_sin_ia_no_se_guarda_nada(cliente):
    from app.db import abrir

    preguntar(cliente, "¿Cuánto costó el mercado?", municipio_id=1)  # sin clave de IA: respaldo
    con = abrir()
    try:
        assert con.execute("SELECT COUNT(*) FROM respuestas").fetchone()[0] == 0
    finally:
        con.close()


def test_entiende_lugar_seccion_y_si_pide_un_panorama(cliente):
    from app.db import abrir
    from app.entender import entender

    con = abrir()
    try:
        casos = {
            "háblame del informe de gobierno de cdmx": ("Ciudad de México", "informes", True),
            "hablame de las becas en irapuato": ("Irapuato, Guanajuato", None, False),
            "¿cuánto costó el mercado de León?": ("León, Guanajuato", None, False),
            "¿Qué dice el presupuesto de egresos de Guanajuato?": ("Guanajuato", "presupuesto", True),
            "contratos de edomex": ("México", "contratos", True),
        }
        for pregunta, esperado in casos.items():
            e = entender(con, pregunta)
            assert (e["lugar"], e["seccion"], e["panorama"]) == esperado, pregunta
    finally:
        con.close()


def test_un_panorama_explica_el_documento_que_corresponde(cliente, ia):
    ia.respuesta = {"encontrado": True, "respuesta": "Es el presupuesto de Irapuato: 3,200 millones.", "fuentes": [1]}
    r = preguntar(cliente, "¿Qué dice el presupuesto de egresos de Irapuato?")  # desde la portada, sin filtros
    assert r["documentos"][0]["id"] == 2 and r["citas"][0]["documento_id"] == 2
    assert "DOCUMENTOS QUE HAY SOBRE ESO" in ia.llamadas[0] and "[Fuente 1] Presupuesto de Egresos 2026 (ejemplo)" in ia.llamadas[0]
    assert r["detalle"]["entendido"] == {"lugar": "Irapuato, Guanajuato", "seccion": "Presupuesto y finanzas", "tipo": "panorama"}
    assert r["detalle"]["modo"] == "panorama"


def test_el_lugar_que_dice_la_pregunta_gana_a_la_pagina(cliente, ia):
    ia.respuesta = {"encontrado": True, "respuesta": "El mercado costó $2,300,000.", "fuentes": [1]}
    r = preguntar(cliente, "¿Cuánto costó el mercado de Irapuato?", municipio_id=2)  # desde la página de León
    assert r["citas"][0]["documento_id"] == 3 and r["detalle"]["alcance"] == "lugar"
    assert r["detalle"]["entendido"]["lugar"] == "Irapuato, Guanajuato"
    assert 3 in [d["id"] for d in r["documentos"]]


def test_sin_ia_tambien_devuelve_documentos(cliente):
    r = preguntar(cliente, "¿Qué dice el presupuesto de egresos de Irapuato?")
    assert r["documentos"][0]["id"] == 2 and r["detalle"]["entendido"]["tipo"] == "panorama"


# --- Cerebro v3: verificador de cifras, memoria, comparaciones, caché más listo, tope de gasto, sugeridas ---


def test_verificador_de_cifras_cita_la_pagina_que_falto_y_avisa_lo_que_no_esta(cliente, ia):
    # La IA solo citó la página 1, pero los $704 millones salen de la página 3; los $999,000 no están en ninguna.
    ia.respuesta = {"encontrado": True, "fuentes": [1],
                    "respuesta": "El total es $3,200,000,000.00; a obra pública van $704 millones y a deporte $999,000."}
    r = preguntar(cliente, "¿Cuánto es el presupuesto?", documento_id=2)
    assert [(c["documento_id"], c["pagina"]) for c in r["citas"]] == [(2, 1), (2, 3)]
    assert r["detalle"]["cifras_sin_verificar"] == ["999,000"]


def test_cifras_redondeadas_o_en_millones_cuentan_como_verificadas():
    from app.preguntas import cifras

    def valores(texto):
        return [round(v) for v, *_ in cifras(texto)]

    pagina = "Monto total: $3,200,000,000.00 pesos. Seguridad 28%. Se asignan $5,347,783.25 en 2025 (página 123)."
    assert valores(pagina) == [3_200_000_000, 28, 5_347_783]  # sin el año ni "página 123"
    for dicho, esperado in (("3,200 millones", 3_200_000_000), ("$3.2 mil millones", 3_200_000_000),
                            ("5.3 millones", 5_300_000), ("28%", 28)):
        (valor, tolerancia, como, _), = cifras(dicho)
        assert round(valor) == esperado and como in dicho
        assert any(abs(v - valor) <= tolerancia for v, *_ in cifras(pagina)), dicho
    (valor, tolerancia, *_), = cifras("5.4 millones")
    assert not any(abs(v - valor) <= tolerancia for v, *_ in cifras(pagina))  # 5,347,783 no es 5.4 millones


def test_cifras_como_vienen_en_los_pdf():
    from app.preguntas import _verificar_cifras

    # Pegadas al texto de la tabla, dos cifras separadas por un espacio, con errores de captura y "13, 200".
    pagina = ("5,947,829Turismo\n29,076,147,169Educación Pública\nTotal 612,800,000 616,742,902 538,832,783\n"
              "por un monto de hasta $2,500.000,000.00 (Dos mil quinientos millones)\nAcompañamos a más de 13, 200 personas")
    respuesta = ("Educación recibe 29,076,147,169; el total es 616,742,902; se invitó por $2,500,000,000.00; "
                 "se acompañó a 13,200 personas y 999,999 no está.")
    elegidas = [(1, 1)]
    assert _verificar_cifras(respuesta, {(1, 1): pagina}, "", elegidas) == ["999,999"]


def test_memoria_sigue_el_tema_de_la_conversacion(cliente, ia):
    ia.respuesta = {"encontrado": True, "respuesta": "Se construyeron 35 escuelas.", "fuentes": [1]}
    primera = preguntar(cliente, "¿Cuántas escuelas se construyeron en Irapuato?")
    historial = [{"pregunta": "¿Cuántas escuelas se construyeron en Irapuato?", "respuesta": primera["respuesta"]}]
    r = cliente.post("/api/preguntar", json={"pregunta": "¿y en Celaya?", "historial": historial}).json()
    # "¿y en Celaya?" no dice de qué: se busca "escuelas" en Celaya (y en los estatales de Guanajuato)
    assert [(c["documento_id"], c["pagina"]) for c in r["citas"]] == [(4, 2)]
    assert r["detalle"]["entendido"]["lugar"] == "Celaya, Guanajuato" and r["detalle"]["alcance"] == "lugar"
    assert "CONVERSACIÓN ANTERIOR" in ia.llamadas[-1] and ia.llamadas[-1].endswith("PREGUNTA: ¿y en Celaya?")
    assert "escuelas" in cliente.get("/api/prueba/preguntas").json()[0]["busqueda"]


def test_una_pregunta_nueva_y_completa_no_arrastra_la_conversacion(cliente, ia):
    ia.respuesta = {"encontrado": True, "respuesta": "El mercado costó $2,300,000.", "fuentes": [1]}
    historial = [{"pregunta": "Háblame del informe de gobierno de la CDMX", "respuesta": "Es el informe..."}]
    r = cliente.post("/api/preguntar", json={"pregunta": "¿Cuánto costó el mercado de Irapuato?",
                                             "historial": historial}).json()
    assert r["citas"][0]["documento_id"] == 3 and "CONVERSACIÓN ANTERIOR" not in ia.llamadas[-1]


def test_compara_lugares_con_fuentes_de_cada_uno(cliente, ia):
    ia.respuesta = {"encontrado": True, "respuesta": "Irapuato: 3,200 millones; de Celaya no hay datos.", "fuentes": [1]}
    r = preguntar(cliente, "Compara el presupuesto de Irapuato y Celaya")
    enviado = ia.llamadas[-1]
    assert "LUGARES A COMPARAR: Irapuato, Guanajuato; Celaya, Guanajuato" in enviado
    assert "No se encontraron páginas sobre esto de: Celaya, Guanajuato" in enviado
    assert "[Fuente 1] Sobre Irapuato, Guanajuato: Presupuesto de Egresos 2026 (ejemplo) (Irapuato), página 1" in enviado
    assert "Sobre Celaya" not in enviado  # el informe estatal no nombra a Celaya: no cuenta como dato de Celaya
    assert r["detalle"]["modo"] == "comparación" and r["citas"][0]["documento_id"] == 2
    assert r["detalle"]["entendido"]["tipo"] == "comparacion"
    assert r["detalle"]["entendido"]["lugar"] == "Irapuato, Guanajuato y Celaya, Guanajuato"
    assert r["detalle"]["cifras_sin_verificar"] == []  # "3,200 millones" = $3,200,000,000.00 de la página 1


def test_entiende_varios_lugares(cliente):
    from app.db import abrir
    from app.entender import entender

    con = abrir()
    try:
        e = entender(con, "compara el gasto en salud de Jalisco y Nuevo León")
        assert [l["lugar"] for l in e["lugares"]] == ["Jalisco", "Nuevo León"] and e["comparacion"]
        e = entender(con, "becas en León, Guanajuato")  # el municipio precisa al estado: un solo lugar
        assert (e["lugar"], e["comparacion"]) == ("León, Guanajuato", False)
    finally:
        con.close()


def test_la_misma_pregunta_con_otras_palabras_sale_del_cache(cliente, ia):
    ia.respuesta = {"encontrado": True, "respuesta": "Es el presupuesto de Irapuato.", "fuentes": [1]}
    preguntar(cliente, "¿Qué dice el presupuesto de egresos de Irapuato?")
    r = preguntar(cliente, "Háblame sobre el presupuesto de egresos de Irapuato")
    assert r["detalle"]["origen"] == "cache" and len(ia.llamadas) == 1
    preguntar(cliente, "¿Qué no dice el presupuesto de egresos de Irapuato?")  # "no" cambia la pregunta
    assert len(ia.llamadas) == 2


def test_tope_diario_de_gasto_en_ia(cliente, ia, monkeypatch):
    from app import preguntas

    antes = preguntas.gasto_de_hoy()
    preguntar(cliente, "¿Cuánto recibe seguridad?", documento_id=2)
    assert preguntas.gasto_de_hoy() > antes  # cada llamada a la IA suma al gasto del día
    monkeypatch.setenv("DEEPSEEK_TOPE_DIARIO_USD", "0")
    r = preguntar(cliente, "¿Cuánto recibe salud?", documento_id=2)
    assert r["detalle"]["origen"] == "sin_ia" and "tope diario" in r["detalle"]["motivo"]
    assert len(ia.llamadas) == 1
    assert preguntar(cliente, "¿Cuánto recibe seguridad?", documento_id=2)["detalle"]["origen"] == "cache"


def test_preguntas_sugeridas_segun_la_pagina(cliente):
    del_municipio = cliente.get("/api/preguntas-sugeridas", params={"municipio_id": 1}).json()
    assert "¿Qué dice el presupuesto de Irapuato?" in del_municipio and len(del_municipio) == 4
    assert cliente.get("/api/preguntas-sugeridas", params={"documento_id": 2}).json()[0] == "¿De qué trata este documento?"
    # En la portada, solo estados cuyo gobierno tiene el documento (el de ejemplo no cuenta).
    assert cliente.get("/api/preguntas-sugeridas").json() == []


def test_la_respuesta_no_trae_numeros_de_fuente(cliente, ia):
    ia.respuesta = {"encontrado": True, "fuentes": [1], "respuesta": "Seguridad recibe 28% (Fuente 1) y salud 12% [Fuentes 1 y 2]."}
    r = preguntar(cliente, "¿Cuánto reciben seguridad y salud?", documento_id=2)
    assert r["respuesta"] == "Seguridad recibe 28% y salud 12%."
