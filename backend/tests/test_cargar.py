import sqlite3
import subprocess
import sys

import pytest

from conftest import RAIZ
from test_procesamiento import PAGINAS, pdf_con_texto


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Base temporal propia, carpeta de PDFs y el módulo `cargar`.

    `cargar` se importa aquí y no arriba: importa app.db, que fija DB_PATH al importarse, y los
    tests de la API necesitan que eso pase después de que conftest apunte DB_PATH a su base temporal.
    """
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")  # nunca la IA real
    ruta_db = tmp_path / "carga.db"
    subprocess.run([sys.executable, str(RAIZ / "datos" / "init_db.py"), str(ruta_db)], check=True)
    con = sqlite3.connect(ruta_db)
    con.row_factory = sqlite3.Row
    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    (pdfs / "presupuesto-leon.pdf").write_bytes(pdf_con_texto(PAGINAS))
    (pdfs / "informe-estatal.pdf").write_bytes(pdf_con_texto(["Informe estatal de salud 2025"]))
    (pdfs / "falso.pdf").write_bytes(b"no soy un pdf")
    import cargar

    yield cargar, con, tmp_path, pdfs
    con.close()


def escribir_csv(carpeta, texto, encoding="utf-8"):
    ruta = carpeta / "documentos.csv"
    ruta.write_text(texto, encoding=encoding)
    return ruta


def documentos(con, archivo_like="%pdfs/%"):
    return con.execute("SELECT * FROM documentos WHERE archivo LIKE ? ORDER BY id", (archivo_like,)).fetchall()


def test_carga_valida_y_reporta_filas_invalidas(entorno, capsys):
    cargar, con, carpeta, pdfs = entorno
    csv = escribir_csv(carpeta, (
        "archivo,estado,municipio,seccion,titulo,anio\n"
        "presupuesto-leon.pdf,guanajuato,LEON,presupuesto,Presupuesto León 2026,2026\n"
        "informe-estatal.pdf,Guanajuato,,informes,Informe estatal 2025,\n"
        "falso.pdf,Guanajuato,,informes,Falso,2025\n"
        "no-existe.pdf,Guanajuato,Irapuato,informes,No existe,2025\n"
        "informe-estatal.pdf,Inexistente,,chismes,Repetido,dos mil\n"
    ))
    r = cargar.cargar(con, csv, pdfs)
    assert (r["procesados"], r["saltados"], r["fallidos"], r["invalidos"]) == (2, 0, 0, 3)

    leon, estatal = documentos(con)
    assert (leon["municipio_id"], leon["seccion_id"], leon["estatus"], leon["total_paginas"]) == (2, 2, "listo", 3)
    assert (estatal["municipio_id"], estatal["anio"], estatal["estatus"]) == (None, None, "listo")
    assert con.execute("SELECT COUNT(*) FROM puntos_clave WHERE documento_id = ?", (leon["id"],)).fetchone()[0] > 0

    salida = capsys.readouterr().out
    assert "Línea 4" in salida and "no es un PDF" in salida
    assert "Línea 5" in salida and "no existe" in salida
    assert all(x in salida for x in ("Línea 6", "Inexistente", "chismes", "dos mil"))


def test_volver_a_ejecutar_no_duplica_y_retoma_los_que_fallaron(entorno):
    cargar, con, carpeta, pdfs = entorno
    csv = escribir_csv(carpeta, "archivo,estado,municipio,seccion,titulo,anio\n"
                                "presupuesto-leon.pdf,Guanajuato,León,presupuesto,Presupuesto,2026\n")
    cargar.cargar(con, csv, pdfs)
    (doc,) = documentos(con)

    assert cargar.cargar(con, csv, pdfs)["saltados"] == 1
    con.execute("UPDATE documentos SET estatus = 'error' WHERE id = ?", (doc["id"],))  # simula un fallo
    con.commit()
    assert cargar.cargar(con, csv, pdfs)["procesados"] == 1
    assert cargar.cargar(con, csv, pdfs, reprocesar=True)["procesados"] == 1
    assert [d["id"] for d in documentos(con)] == [doc["id"]]
    assert con.execute("SELECT COUNT(*) FROM paginas WHERE documento_id = ?", (doc["id"],)).fetchone()[0] == 3


def test_acepta_csv_de_excel_en_espanol(entorno):
    # Excel en español guarda con punto y coma, en cp1252 y con encabezados con acentos.
    cargar, con, carpeta, pdfs = entorno
    csv = escribir_csv(carpeta, "Archivo;Estado;Municipio;Sección;Título;Año\n"
                                "presupuesto-leon.pdf;Guanajuato;León;presupuesto;Presupuesto León;2026\n",
                       encoding="cp1252")
    assert cargar.cargar(con, csv, pdfs)["procesados"] == 1
    assert documentos(con)[0]["titulo"] == "Presupuesto León"


def test_solo_revisar_no_toca_la_base(entorno):
    cargar, con, carpeta, pdfs = entorno
    csv = escribir_csv(carpeta, "archivo,estado,municipio,seccion,titulo,anio\n"
                                "presupuesto-leon.pdf,Guanajuato,León,presupuesto,Presupuesto,2026\n")
    r = cargar.cargar(con, csv, pdfs, solo_revisar=True)
    assert (r["procesados"], r["invalidos"]) == (0, 0)
    assert documentos(con) == []


def con_metadatos(datos: bytes, meta: dict) -> bytes:
    import io

    from pypdf import PdfReader, PdfWriter

    w = PdfWriter(clone_from=PdfReader(io.BytesIO(datos)))
    w.add_metadata(meta)
    salida = io.BytesIO()
    w.write(salida)
    return salida.getvalue()


def test_metadatos_oficiales_y_huella_sha256(entorno, capsys):
    import hashlib

    cargar, con, carpeta, pdfs = entorno
    huella = hashlib.sha256((pdfs / "presupuesto-leon.pdf").read_bytes()).hexdigest()
    (pdfs / "tabla.xlsx").write_bytes(b"PK\x03\x04 hoja de calculo")
    csv = escribir_csv(carpeta, (
        "archivo,estado,municipio,seccion,titulo,anio,url_fuente,formato,sha256,fecha_publicacion,dependencia\n"
        f"presupuesto-leon.pdf,Guanajuato,León,presupuesto,Presupuesto,2026,https://leon.gob.mx/p.pdf,pdf,{huella},2026-01-10,Tesorería\n"
        f"informe-estatal.pdf,Guanajuato,,informes,Informe,2025,,pdf,{'0' * 64},,\n"
        "tabla.xlsx,Guanajuato,,presupuesto,Tabla,2025,,xlsx,,,\n"
    ))
    r = cargar.cargar(con, csv, pdfs)
    assert (r["procesados"], r["invalidos"]) == (1, 2)
    (doc,) = documentos(con)
    assert (doc["url_fuente"], doc["formato"], doc["sha256"], doc["fecha_publicacion"], doc["dependencia"]) == (
        "https://leon.gob.mx/p.pdf", "pdf", huella, "2026-01-10", "Tesorería")
    salida = capsys.readouterr().out
    assert "Línea 3" in salida and "no coincide con su sha256" in salida
    assert "Línea 4" in salida and "xlsx todavía no se procesa" in salida


def test_avisa_si_el_pdf_parece_impreso_desde_un_navegador(entorno, capsys):
    cargar, con, carpeta, pdfs = entorno
    (pdfs / "impreso.pdf").write_bytes(con_metadatos(pdf_con_texto(PAGINAS), {"/Producer": "Skia/PDF m136", "/Creator": "Chromium"}))
    csv = escribir_csv(carpeta, "archivo,estado,municipio,seccion,titulo,anio\nimpreso.pdf,Guanajuato,,informes,Impreso,2025\n")
    r = cargar.cargar(con, csv, pdfs)
    assert (r["procesados"], r["avisos"]) == (1, 1)  # se carga, pero se marca para revisarlo a mano
    assert "REVISAR" in capsys.readouterr().out


def test_procesa_varios_a_la_vez(entorno):
    cargar, con, carpeta, pdfs = entorno
    filas = []
    for i in range(6):
        (pdfs / f"doc{i}.pdf").write_bytes(pdf_con_texto([f"Documento {i} con presupuesto de ${i + 1},000 pesos"] * 3))
        filas.append(f"doc{i}.pdf,Guanajuato,,informes,Documento {i},2025")
    csv = escribir_csv(carpeta, "archivo,estado,municipio,seccion,titulo,anio\n" + "\n".join(filas) + "\n")
    r = cargar.cargar(con, csv, pdfs, hilos=3)
    assert (r["procesados"], r["fallidos"]) == (6, 0)
    assert {d["estatus"] for d in documentos(con)} == {"listo"}
    assert con.execute("SELECT COUNT(*) FROM paginas p JOIN documentos d ON d.id = p.documento_id WHERE d.titulo LIKE 'Documento %'").fetchone()[0] == 18


def test_puede_omitir_los_pdf_escaneados(entorno):
    cargar, con, carpeta, pdfs = entorno
    (pdfs / "escaneado.pdf").write_bytes(pdf_con_texto([""]))  # una página sin texto
    csv = escribir_csv(carpeta, "archivo,estado,municipio,seccion,titulo,anio\n"
                                "escaneado.pdf,Guanajuato,,informes,Escaneado,2025\n"
                                "informe-estatal.pdf,Guanajuato,,informes,Informe,2025\n")
    r = cargar.cargar(con, csv, pdfs, omitir_escaneados=True)
    assert (r["procesados"], r["fallidos"], len(r["escaneados"])) == (1, 0, 1)
    assert [d["titulo"] for d in documentos(con)] == ["Informe"]  # el escaneado no queda en la base


def test_procesa_con_varios_procesos(entorno):
    cargar, con, carpeta, pdfs = entorno
    filas = []
    for i in range(4):
        (pdfs / f"proc{i}.pdf").write_bytes(pdf_con_texto([f"Documento {i} con presupuesto de ${i + 1},000 pesos"] * 2))
        filas.append(f"proc{i}.pdf,Guanajuato,,informes,Proceso {i},2025")
    csv = escribir_csv(carpeta, "archivo,estado,municipio,seccion,titulo,anio\n" + "\n".join(filas) + "\n")
    r = cargar.cargar(con, csv, pdfs, procesos=2)
    assert (r["procesados"], r["fallidos"]) == (4, 0)
    assert cargar.cargar(con, csv, pdfs, procesos=2)["saltados"] == 4  # volver a correrlo no duplica


def test_los_escaneados_se_anotan_y_no_se_vuelven_a_leer(entorno):
    cargar, con, carpeta, pdfs = entorno
    (pdfs / "escaneado.pdf").write_bytes(pdf_con_texto([""]))
    csv = escribir_csv(carpeta, "archivo,estado,municipio,seccion,titulo,anio\nescaneado.pdf,Guanajuato,,informes,Escaneado,2025\n")
    lista = carpeta / "pendientes_ocr.txt"
    r = cargar.cargar(con, csv, pdfs, omitir_escaneados=True, lista_escaneados=lista)
    assert len(r["escaneados"]) == 1 and lista.read_text(encoding="utf-8").strip().endswith("escaneado.pdf")
    otra = cargar.cargar(con, csv, pdfs, omitir_escaneados=True, lista_escaneados=lista)
    assert (otra["escaneados_previos"], otra["escaneados"], otra["procesados"]) == (1, [], 0)
