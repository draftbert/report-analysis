"""calibrar-estilo: falsos positivos deterministas y exclusión del propio informe del corpus."""
from __future__ import annotations

from pathlib import Path

from audit_agent.calibracion import calibrar, cargar_corpus, falsos_positivos
from audit_agent.style_checker import StyleChecker

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "ejemplos" / "corpus_calibracion"


def test_corpus_excluye_informes_de_calibracion_y_empareja(tmp_path):
    (tmp_path / "informe_x.md").write_text("Texto aprobado sin fallo alguno.\n", encoding="utf-8")
    (tmp_path / "informe_x_borrador.md").write_text("Hemos visto un fallo grave.\n", encoding="utf-8")
    (tmp_path / "calibracion_estilo.md").write_text("| «fallo» | palabra_prohibida |\n", encoding="utf-8")
    (tmp_path / "calibracion_estilo_trazas").mkdir()
    (tmp_path / "calibracion_estilo_trazas" / "x.md").write_text("fallo fraude culpa\n", encoding="utf-8")
    aprobados, borradores, avisos = cargar_corpus(tmp_path)
    assert [n for n, _ in aprobados] == ["informe_x.md"]
    assert [n for n, _ in borradores] == ["informe_x_borrador.md"] and avisos == []


def test_falsos_positivos_con_contexto_y_recuento():
    checker = StyleChecker(RAIZ / "config" / "estilo.yaml")
    aprobados, _, _ = cargar_corpus(CORPUS)
    fp = falsos_positivos(checker, aprobados)
    assert set(fp) == {"todos los casos", "problema", "siempre"}
    assert fp["siempre"]["n"] == 1 and fp["siempre"]["ficheros"] == {"informe_SCIIF-2025-11_aprobado.md"}
    assert "siempre que se detecte" in fp["siempre"]["ejemplos"][0][1]


def test_calibrar_sin_llm_genera_informe_y_no_toca_yaml(tmp_path):
    yaml_antes = (RAIZ / "config" / "estilo.yaml").read_bytes()
    salida = tmp_path / "calibracion_estilo.md"
    resumen = calibrar(CORPUS, StyleChecker(RAIZ / "config" / "estilo.yaml"), None, salida)
    assert "Falsos positivos: 3" in resumen and "NO se ha modificado" in resumen
    texto = salida.read_text(encoding="utf-8")
    assert "## (a) Falsos positivos" in texto and "«siempre»" in texto and "No disponible: sin proveedor LLM" in texto
    assert (RAIZ / "config" / "estilo.yaml").read_bytes() == yaml_antes
