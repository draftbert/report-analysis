"""Lectores de entrada/: .md/.txt, .docx (tablas), .xlsx, .pdf con y sin texto."""
from __future__ import annotations

from pathlib import Path

import pytest

from audit_agent.lectores import LecturaError, leer

RAIZ = Path(__file__).resolve().parent.parent
SINTETICOS = RAIZ / "ejemplos" / "entrada_sintetica"
FRASES_CLAVE = ["45 pedidos", "6 de los 45 pedidos", "delegación temporal de permisos", "tres ofertas comparativas",
                "Comentarios del área", "Anexo E2"]


@pytest.mark.parametrize("ext,lector", [("md", "texto"), ("docx", "docx"), ("xlsx", "xlsx"), ("pdf", "pdf")])
def test_lectura_conserva_contenido(ext, lector):
    ruta = (RAIZ / "ejemplos" / "papel_trabajo_compras.md") if ext == "md" else SINTETICOS / f"papel_trabajo_compras.{ext}"
    doc = leer(ruta)
    assert doc.lector == lector and doc.avisos == []
    for frase in FRASES_CLAVE:
        assert frase in doc.texto, (ext, frase)


def test_docx_conserva_estructura_y_tablas():
    texto = leer(SINTETICOS / "papel_trabajo_compras.docx").texto
    assert "## Papel de trabajo" in texto and "#### Resultados" in texto
    assert "| Ref. | Resultado | Evidencia |" in texto and "|---|---|---|" in texto
    assert "| R2 |" in texto
    assert "- Extracto del módulo de compras (Anexo E1)" in texto  # viñeta


def test_xlsx_hojas_como_secciones_y_tabla():
    texto = leer(SINTETICOS / "papel_trabajo_compras.xlsx").texto
    assert "## Hoja: Tarea 3.2" in texto and "## Hoja: Resultados" in texto
    assert "| Ref. | Resultado | Evidencia |" in texto
    assert "### Prueba realizada" in texto


def test_pdf_sin_texto_error_claro(tmp_path):
    vacio = tmp_path / "escaneo.pdf"
    vacio.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
                      b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>\nendobj\n"
                      b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
                      b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n")
    with pytest.raises(LecturaError, match="capa de texto"):
        leer(vacio)


def test_formato_no_soportado(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a,b", encoding="utf-8")
    with pytest.raises(LecturaError, match="no soportado"):
        leer(f)


def test_expediente_lee_entrada_con_lectores(expediente_tmp):
    import shutil
    shutil.copy(SINTETICOS / "papel_trabajo_compras.docx", expediente_tmp.ruta / "entrada")
    docs = expediente_tmp.leer_entrada()
    assert [(d.nombre, d.lector) for d in docs] == [("papel_trabajo_compras.docx", "docx"), ("papel_trabajo_compras.md", "texto")]


def test_extraer_registra_lector_y_texto_en_trazas(contexto):
    from audit_agent.acciones import accion_extraer
    from audit_agent.esquemas import ExtraccionObservaciones
    import json
    contexto.llm.respuestas["extraer"] = ExtraccionObservaciones(observaciones=[], notas="")
    accion_extraer(contexto)
    traza = next(contexto.exp.ruta.glob("trazas/*_extraer-entrada.json"))
    d = json.loads(traza.read_text(encoding="utf-8"))
    assert d["documentos"][0]["lector"] == "texto" and "6 de los 45 pedidos" in d["documentos"][0]["texto_normalizado"]
