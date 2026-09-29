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
        "informe-estatal.pdf,Jalisco,,chismes,Repetido,dos mil\n"
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
    assert all(x in salida for x in ("Línea 6", "Jalisco", "chismes", "dos mil"))


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
