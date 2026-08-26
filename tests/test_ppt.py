"""Diapositiva de detalle de conclusiones: reproduce la plantilla corporativa
(banda de riesgo, título numerado, prosa, caja de detalles, recomendaciones
numeradas N.1/N.2, referencia, área/responsable/plazo)."""
from __future__ import annotations

from pptx import Presentation

from audit_agent.ppt_builder import construir_desde_datos

CONCLUSION = {
    "titulo": "Limitaciones en el mantenimiento de los tarifarios de última milla", "prueba": "2.11 b)",
    "nivel_riesgo": "Medio", "area": "FLF", "responsable": "A. Veiga", "plazo": "Fuera de plazo",
    "referencia_recomendacion": "TMSCIIF-10",
    "incidencia": "Las actualizaciones tarifarias se incorporan manualmente a la Herramienta de Costes.",
    "causa_raiz": "La comunicación de los cambios se articula mediante un proceso principalmente manual.",
    "como_se_ha_llegado": "- El volumen de tarifas a parametrizar puede superar las 5.000 combinaciones.\n- Reclamaciones por importe aproximado de 1,4 M€.",
    "consecuencias": "La manualidad del proceso incrementa el riesgo de tarifas desactualizadas.",
    "recomendacion": "Implantar un sistema para la carga y gestión de los tarifarios.\n\nEstablecer una plantilla única de comunicación de acuerdos.",
}


def _textos(slide):
    return [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text.strip()]


def test_diapositiva_detalle(tmp_path):
    datos = {"proyecto": {"nombre": "N", "referencia": "R", "fecha": "F", "distribucion": ["D"]},
             "introduccion": "I", "resumen_ejecutivo": "R", "conclusiones": [CONCLUSION] * 8,
             "sugerencias": [{**CONCLUSION, "recomendacion": "Propuesta X", "referencia_recomendacion": ""}]}
    ruta = construir_desde_datos(datos, tmp_path / "t.pptx")
    prs = Presentation(str(ruta))
    titulos = [_textos(s)[0] for s in prs.slides]
    assert titulos[:4] == ["N", "Introducción", "Resumen ejecutivo", "Detalle de conclusiones"]
    assert len(prs.slides) == 1 + 2 + 1 + 8 + 1 + 1
    octava = prs.slides[4 + 7]
    t = "\n".join(_textos(octava))
    assert "08 Limitaciones en el mantenimiento" in t
    assert "R\nI\nE\nS\nG\nO" in t and "M\nE\nD\nI\nO" in t          # banda vertical
    assert "A continuación, se muestran los detalles descriptivos" in t and "/ El volumen de tarifas" in t
    assert "Recomendación 8.1" in t and "Recomendación 8.2" in t and "Ref.-TMSCIIF-10" in t
    assert "Área\nFLF" in t.replace("\n\n", "\n") or ("Área" in t and "FLF" in t)
    assert "Responsable" in t and "A. Veiga" in t and "Plazo" in t and "Fuera de plazo" in t
    assert "**" not in t and "- El volumen" not in t                      # sin marcas Markdown
    sug = prs.slides[-1]
    ts = "\n".join(_textos(sug))
    assert "Sugerencias de mejora" in ts and "Propuesta de mejora" in ts and "Recomendación" not in ts
