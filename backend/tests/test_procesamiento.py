import pytest

from app.procesamiento import llm, resumen

PAGINAS = [
    "Presupuesto Ciudadano 2026 del municipio",
    "El presupuesto total es de $3,200 millones de pesos para el ejercicio",
    "Salud recibe 12% y seguridad publica recibe 28% del gasto total",
]


def pdf_con_texto(paginas: list[str]) -> bytes:
    """PDF mínimo válido con una línea de texto por página (solo ASCII, sin paréntesis)."""
    n = len(paginas)
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(n))}] /Count {n} >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, texto in enumerate(paginas):
        stream = f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET"
        objetos.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>"
        )
        objetos.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    salida, offsets = "%PDF-1.4\n", []
    for i, obj in enumerate(objetos, start=1):
        offsets.append(len(salida))
        salida += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
    return salida.encode("latin-1")


def subir(cliente, paginas=PAGINAS, **extra):
    datos = {"estado_id": "1", "municipio_id": "3", "seccion": "presupuesto", "titulo": "Prueba", "anio": "2026", **extra}
    return cliente.post("/api/documentos", data=datos, files={"archivo": ("p.pdf", pdf_con_texto(paginas), "application/pdf")})


def test_subir_y_procesar_sin_ia(cliente):
    r = subir(cliente)
    assert r.status_code == 201 and r.json()["estatus"] == "pendiente"
    doc = cliente.get(f"/api/documentos/{r.json()['id']}").json()
    assert (doc["estatus"], doc["total_paginas"], doc["municipio"]["nombre"]) == ("listo", 3, "Celaya")
    assert doc["puntos_clave"] and all(1 <= p["pagina"] <= 3 for p in doc["puntos_clave"])
    assert cliente.get(f"/api/prueba/documentos/{doc['id']}").json()["motor"] == "respaldo sin IA"
    citas = cliente.get("/api/buscar", params={"q": "seguridad", "documento_id": doc["id"]}).json()["resultados"]
    assert citas[0]["pagina"] == 3


def test_rechaza_archivos_que_no_son_pdf(cliente):
    r = cliente.post("/api/documentos", data={"estado_id": "1", "seccion": "presupuesto", "titulo": "x"},
                     files={"archivo": ("x.pdf", b"hola", "application/pdf")})
    assert r.status_code == 400


def test_rechaza_municipio_de_otro_estado(cliente):
    assert subir(cliente, municipio_id="99").status_code == 400


def test_con_ia_descarta_puntos_sin_pagina_valida(cliente, monkeypatch):
    respuesta = {"resumen": "El municipio gastará 3,200 millones.", "puntos": [
        {"texto": "Presupuesto de 3,200 millones", "pagina": 2},
        {"texto": "Dato inventado", "pagina": 99},
        {"texto": "Sin página"},
    ]}
    monkeypatch.setattr(llm, "configurado", lambda: True)
    monkeypatch.setattr(llm, "pedir_json", lambda sistema, usuario, uso: respuesta)
    doc = cliente.get(f"/api/documentos/{subir(cliente).json()['id']}").json()
    assert doc["resumen"] == "El municipio gastará 3,200 millones."
    assert doc["puntos_clave"] == [{"texto": "Presupuesto de 3,200 millones", "pagina": 2}]


def test_si_la_ia_falla_usa_el_respaldo(cliente, monkeypatch):
    def falla(*_):
        raise RuntimeError("sin conexión")
    monkeypatch.setattr(llm, "configurado", lambda: True)
    monkeypatch.setattr(llm, "pedir_json", falla)
    documento_id = subir(cliente).json()["id"]
    assert cliente.get(f"/api/documentos/{documento_id}").json()["estatus"] == "listo"
    bitacora = cliente.get(f"/api/prueba/documentos/{documento_id}").json()
    assert bitacora["motor"] == "respaldo sin IA" and "sin conexión" in bitacora["aviso"]


def test_documento_grande_se_divide_en_bloques_y_se_combina(monkeypatch):
    llamadas = []
    def falso(sistema, usuario, uso):
        llamadas.append(usuario)
        return {"resumen": "ok", "puntos": [{"texto": "dato", "pagina": 1}]}
    monkeypatch.setattr(resumen, "CARACTERES_POR_BLOQUE", 80)
    monkeypatch.setattr(llm, "pedir_json", falso)
    resumen.resumir_con_ia("Doc", PAGINAS, {})
    assert len(llamadas) == 4  # 3 bloques + 1 combinación
    assert "resúmenes parciales" in llamadas[-1]


def test_pdf_sin_texto_marca_error(cliente):
    documento_id = subir(cliente, paginas=[""]).json()["id"]
    doc = cliente.get(f"/api/documentos/{documento_id}").json()
    assert doc["estatus"] == "error" and "OCR" in doc["error"]


def test_llm_pide_json_sin_modo_pensar(monkeypatch):
    enviado = {}

    class Respuesta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"ok": true}'}}],
                    "usage": {"prompt_tokens": 10, "prompt_cache_hit_tokens": 8, "completion_tokens": 5}}

    def post(url, headers, json, timeout):
        enviado.update(json)
        return Respuesta()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "clave-de-prueba")
    monkeypatch.delenv("DEEPSEEK_THINKING", raising=False)
    monkeypatch.setattr(llm.httpx, "post", post)
    uso = {}
    assert llm.pedir_json("s", "u", uso) == {"ok": True}
    assert enviado["thinking"] == {"type": "disabled"}
    assert enviado["response_format"] == {"type": "json_object"}
    assert uso == {"entrada": 10, "cache": 8, "salida": 5, "llamadas": 1}
    # 2 tokens sin caché + 8 del caché de DeepSeek (50 veces más baratos) + 5 de salida
    assert llm.costo_usd(uso) == pytest.approx((2 * 0.30 + 8 * 0.006 + 5 * 1.20) / 1_000_000)


def test_documento_enlaza_a_su_pdf_original_y_su_fuente(cliente):
    doc_id = subir(cliente).json()["id"]
    doc = cliente.get(f"/api/documentos/{doc_id}").json()
    assert doc["pdf_url"] == f"/api/documentos/{doc_id}/pdf"
    assert set(doc["fuente"]) == {"url_fuente", "formato", "fecha_publicacion", "dependencia"}
    pdf = cliente.get(doc["pdf_url"])
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    pagina = cliente.get(f"/api/documentos/{doc_id}/paginas/2").json()
    assert (pagina["total_paginas"], pagina["pdf_url"]) == (3, f"/api/documentos/{doc_id}/pdf#page=2")
    assert "archivo" not in pagina  # nunca se muestra la ruta del archivo en el servidor


def test_documento_sin_pdf_en_el_servidor(cliente):
    assert cliente.get("/api/documentos/2").json()["pdf_url"] is None  # datos de ejemplo: no hay PDF
    assert cliente.get("/api/documentos/2/pdf").status_code == 404
    assert cliente.get("/api/documentos/2/paginas/1").json()["pdf_url"] is None


def test_llm_reintenta_si_deepseek_dice_que_vamos_muy_rapido(monkeypatch):
    estados = [429, 200]

    class Respuesta:
        def __init__(self):
            self.status_code = estados.pop(0)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(self.status_code)

        def json(self):
            return {"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {}}

    monkeypatch.setenv("DEEPSEEK_API_KEY", "clave-de-prueba")
    monkeypatch.setattr(llm.httpx, "post", lambda url, headers, json, timeout: Respuesta())
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    assert llm.pedir_json("s", "u", {}) == {"ok": True} and estados == []
