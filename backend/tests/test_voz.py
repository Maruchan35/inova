import pytest


def decir(cliente, texto, **filtros):
    return cliente.post("/api/voz", json={"texto": texto, **filtros}).json()


@pytest.mark.parametrize("texto, esperado", [
    ("Llévame a Irapuato", ("ir", "municipio", 1, None)),
    ("irapuato guanajuato", ("ir", "municipio", 1, None)),
    ("Quiero ver el presupuesto de Guanajuato", ("ir", "estado", 1, "presupuesto")),
    ("abre las obras de León por favor", ("ir", "municipio", 2, "obras")),
    ("ve a la ciudad de méxico", ("ir", "estado", 10, None)),
])
def test_navegar_a_un_lugar_con_la_voz(cliente, texto, esperado):
    r = decir(cliente, texto)
    assert (r["accion"], r["tipo"], r["id"], r["seccion"]) == esperado
    assert r["decir"].startswith("Te llevo a") and r["texto"] == texto


def test_dentro_de_un_lugar_basta_decir_la_seccion(cliente):
    r = decir(cliente, "muéstrame los contratos", municipio_id=1)
    assert (r["accion"], r["tipo"], r["id"], r["seccion"]) == ("ir", "municipio", 1, "contratos")
    assert decir(cliente, "muéstrame los contratos")["accion"] == "decir"  # sin lugar: pregunta a dónde


@pytest.mark.parametrize("texto, accion", [
    ("regresa al inicio", "inicio"), ("página principal", "inicio"), ("atrás", "atras"), ("regresa", "atras"),
    ("ayuda", "decir"), ("", "decir"), ("   ", "decir"),
])
def test_ordenes_sencillas(cliente, texto, accion):
    r = decir(cliente, texto)
    assert r["accion"] == accion and r["decir"]


@pytest.mark.parametrize("texto", [
    "¿Cuánto costó el mercado de Irapuato?",
    "háblame del informe de gobierno de Guanajuato",
    "qué obras hay en Irapuato",
    "compara el presupuesto de Jalisco y Nuevo León",
    "becas para estudiantes en Irapuato",
])
def test_lo_demas_es_una_pregunta_para_el_chatbot(cliente, texto):
    r = decir(cliente, texto)
    assert (r["accion"], r["pregunta"]) == ("preguntar", texto)


def test_un_nombre_repetido_pide_el_estado(cliente):
    r = decir(cliente, "llévame a Guadalupe")  # hay varios municipios Guadalupe
    assert r["accion"] == "decir" and "Guadalupe" in r["decir"] and "estado" in r["decir"]
    r = decir(cliente, "llévame a Guadalupe, Nuevo León")
    assert (r["accion"], r["tipo"]) == ("ir", "municipio") and "Guadalupe, Nuevo León" in r["decir"]
