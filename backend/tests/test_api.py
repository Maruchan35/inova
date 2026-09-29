def test_salud(cliente):
    assert cliente.get("/api/salud").json() == {"estado": "ok"}


def test_secciones_en_orden(cliente):
    claves = [s["clave"] for s in cliente.get("/api/secciones").json()]
    assert claves == ["informes", "presupuesto", "obras", "actas", "contratos"]


def test_estados_con_municipios(cliente):
    estados = cliente.get("/api/estados").json()
    assert estados[0]["nombre"] == "Guanajuato"
    assert "Irapuato" in [m["nombre"] for m in estados[0]["municipios"]]


def test_municipio_agrupa_documentos_por_seccion(cliente):
    datos = cliente.get("/api/municipios/1").json()
    assert (datos["tipo"], datos["nombre"], datos["estado"]["nombre"]) == ("municipio", "Irapuato", "Guanajuato")
    por_seccion = {s["clave"]: s["documentos"] for s in datos["secciones"]}
    assert len(por_seccion) == 5
    assert [d["id"] for d in por_seccion["actas"]] == [1]
    assert por_seccion["informes"] == []  # el informe estatal no aparece en el municipio


def test_estado_solo_muestra_documentos_estatales(cliente):
    datos = cliente.get("/api/estados/1").json()
    documentos = [d["id"] for s in datos["secciones"] for d in s["documentos"]]
    assert documentos == [4]
    assert len(datos["municipios"]) == 3


def test_lugar_inexistente(cliente):
    assert cliente.get("/api/municipios/99").status_code == 404
    assert cliente.get("/api/estados/99").status_code == 404


def test_documento_con_resumen_y_puntos_clave(cliente):
    doc = cliente.get("/api/documentos/2").json()
    assert doc["estatus"] == "listo"
    assert doc["resumen"]
    assert doc["seccion"]["clave"] == "presupuesto"
    assert doc["municipio"]["nombre"] == "Irapuato"
    assert all(p["pagina"] for p in doc["puntos_clave"])


def test_documento_pendiente(cliente):
    doc = cliente.get("/api/documentos/5").json()
    assert (doc["estatus"], doc["resumen"], doc["puntos_clave"]) == ("pendiente", None, [])


def test_pagina(cliente):
    assert cliente.get("/api/documentos/1/paginas/3").json()["pagina"] == 3
    assert cliente.get("/api/documentos/1/paginas/99").status_code == 404


def test_buscar_ignora_acentos_y_cita_pagina(cliente):
    primero = cliente.get("/api/buscar", params={"q": "pavimentacion Hidalgo"}).json()["resultados"][0]
    assert (primero["documento_id"], primero["pagina"], primero["lugar"]) == (1, 2, "Irapuato")
    assert "[[" in primero["fragmento"]


def test_buscar_con_filtros(cliente):
    assert cliente.get("/api/buscar", params={"q": "carreteras", "municipio_id": 1}).json()["resultados"] == []
    estatal = cliente.get("/api/buscar", params={"q": "carreteras", "estado_id": 1}).json()["resultados"]
    assert estatal[0]["documento_id"] == 4
    solo_obras = cliente.get("/api/buscar", params={"q": "Horizonte", "seccion": "obras"}).json()["resultados"]
    assert {r["seccion"] for r in solo_obras} == {"obras"}


def test_buscar_sin_resultados(cliente):
    assert cliente.get("/api/buscar", params={"q": "zz"}).json()["resultados"] == []


def test_preguntar_con_filtro(cliente):
    datos = cliente.post("/api/preguntar", json={"pregunta": "¿Cuánto costó el mercado?", "municipio_id": 1}).json()
    assert datos["citas"][0]["documento_id"] == 3


def test_concentracion(cliente):
    filas = cliente.get("/api/proveedores/concentracion", params={"municipio_id": 1}).json()
    assert filas[0]["nombre"].startswith("Constructora Horizonte")
    assert round(sum(f["porcentaje"] for f in filas)) == 100
    assert cliente.get("/api/proveedores/concentracion", params={"municipio_id": 2}).json() == []


def test_vista_previa(cliente):
    r = cliente.get("/vista")
    assert r.status_code == 200 and "CabildoAbierto" in r.text
