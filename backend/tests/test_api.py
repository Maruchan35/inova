def test_salud(cliente):
    assert cliente.get("/api/salud").json() == {"estado": "ok"}


def test_actas(cliente):
    actas = cliente.get("/api/actas").json()
    assert len(actas) == 2
    assert {"id", "titulo", "fecha", "municipio", "paginas"} <= actas[0].keys()


def test_buscar_ignora_acentos_y_cita_pagina(cliente):
    datos = cliente.get("/api/buscar", params={"q": "pavimentacion Hidalgo"}).json()
    primero = datos["resultados"][0]
    assert (primero["acta_id"], primero["pagina"]) == (1, 2)
    assert "[[" in primero["fragmento"]


def test_buscar_sin_resultados(cliente):
    assert cliente.get("/api/buscar", params={"q": "zz"}).json()["resultados"] == []


def test_preguntar(cliente):
    datos = cliente.post("/api/preguntar", json={"pregunta": "¿Quién rehabilitó el mercado?"}).json()
    assert datos["citas"][0]["acta_id"] == 2


def test_pagina(cliente):
    assert cliente.get("/api/actas/1/paginas/3").json()["pagina"] == 3
    assert cliente.get("/api/actas/1/paginas/99").status_code == 404


def test_concentracion(cliente):
    filas = cliente.get("/api/proveedores/concentracion").json()
    assert filas[0]["nombre"].startswith("Constructora Horizonte")
    assert round(sum(f["porcentaje"] for f in filas)) == 100
