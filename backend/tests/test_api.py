def test_salud(cliente):
    assert cliente.get("/api/salud").json() == {"estado": "ok"}


def test_secciones_en_orden(cliente):
    claves = [s["clave"] for s in cliente.get("/api/secciones").json()]
    assert claves == ["informes", "presupuesto", "obras", "actas", "contratos"]


def test_estados_con_municipios(cliente):
    estados = {e["nombre"]: e for e in cliente.get("/api/estados").json()}
    assert "Irapuato" in [m["nombre"] for m in estados["Guanajuato"]["municipios"]]


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
    assert {"Irapuato", "León", "Celaya"} <= {m["nombre"] for m in datos["municipios"]}


def test_lugares_traen_coordenadas_reales(cliente):
    irapuato = cliente.get("/api/municipios/1").json()
    assert round(irapuato["latitud"], 1) == 20.7 and round(irapuato["longitud"], 1) == -101.4
    guanajuato = cliente.get("/api/estados/1").json()
    assert guanajuato["latitud"] and guanajuato["longitud"]


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


def test_buscar_encuentra_singular_y_plural(cliente):
    # El acta dice "luminarias"; se busca en singular
    citas = cliente.get("/api/buscar", params={"q": "luminaria"}).json()["resultados"]
    assert (citas[0]["documento_id"], citas[0]["pagina"]) == (1, 3)
    assert "[[luminarias]]" in citas[0]["fragmento"]


def test_buscar_ignora_palabras_vacias_y_prefiere_paginas_con_todas_las_palabras(cliente):
    assert cliente.get("/api/buscar", params={"q": "¿qué hay?"}).json()["resultados"] == []
    citas = cliente.get("/api/buscar", params={"q": "háblame de la pavimentación de la calle Hidalgo"}).json()["resultados"]
    assert (citas[0]["documento_id"], citas[0]["pagina"]) == (1, 2)
