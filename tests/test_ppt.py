"""Exportación del informe a PowerPoint con la estructura de los informes
aprobados: carátula, índice, portadillas, introducción, resumen ejecutivo
(evaluación global + próximos pasos), detalle de conclusiones con el diseño
corporativo, sugerencias de mejora (RIESGO BAJO + párrafo fijo), anexo de
planes de acción y cierre."""
from __future__ import annotations

from pptx import Presentation

from audit_agent.ppt_builder import construir_desde_datos

CONCLUSION = {
    "titulo": "Limitaciones en el mantenimiento de los tarifarios de última milla", "prueba": "2.11 b)",
    "nivel_riesgo": "Medio", "area": "Transporte", "responsable": "A. Pérez", "plazo": "Fuera de plazo",
    "referencia_recomendacion": "TMSCIIF-10",
    "incidencia": "Las actualizaciones tarifarias se incorporan manualmente a la Herramienta de Costes.",
    "causa_raiz": "La comunicación de los cambios se articula mediante un proceso principalmente manual.",
    "como_se_ha_llegado": "- El volumen de tarifas a parametrizar puede superar las 5.000 combinaciones.\n- Reclamaciones por importe aproximado de 1,4 M€.",
    "consecuencias": "La manualidad del proceso incrementa el riesgo de tarifas desactualizadas.",
    "recomendacion": "Implantar un sistema para la carga y gestión de los tarifarios.\n\nEstablecer una plantilla única de comunicación de acuerdos.",
}


def _textos(slide):
    return [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text.strip()]


def _todo(prs):
    return ["\n".join(_textos(s)) for s in prs.slides]


def test_estructura_y_diapositiva_detalle(tmp_path):
    datos = {"proyecto": {"nombre": "Auditoría X", "referencia": "2025_787", "fecha": "Mayo 2025", "distribucion": ["Control de Stock", "Operaciones tienda"]},
             "introduccion": "I", "resumen_ejecutivo": "R", "evaluacion_global": "Mejorable",
             "conclusiones": [CONCLUSION] * 8,
             "sugerencias": [{**CONCLUSION, "nivel_riesgo": "Bajo", "recomendacion": "Propuesta X", "referencia_recomendacion": ""}]}
    ruta = construir_desde_datos(datos, tmp_path / "t.pptx")
    prs = Presentation(str(ruta))
    todo = _todo(prs)
    # carátula e índice
    assert "CONFIDENCIAL" in todo[0] and "Informe de Auditoría Interna" in todo[0] and "Lista de Distribución" in todo[0]
    assert "Control de Stock" in todo[0] and "Ref.: 2025_787" in todo[0]
    assert todo[1].split("\n") == ["Introducción", "Resumen ejecutivo", "Detalle de conclusiones", "Sugerencias de mejora", "Anexos"]
    # resumen: evaluación global y próximos pasos fijos
    resumen = next(t for t in todo if t.startswith("Resumen ejecutivo\n"))
    assert "Evaluación Global" in resumen and "Mejorable" in resumen and "Los destinatarios del presente informe" in resumen
    # detalle 08
    octava = next(t for t in todo if "08 Limitaciones en el mantenimiento" in t)
    assert "R\nI\nE\nS\nG\nO" in octava and "M\nE\nD\nI\nO" in octava
    assert "A continuación, se muestran los detalles descriptivos" in octava and "/ El volumen de tarifas" in octava
    assert "Recomendación 8.1" in octava and "Recomendación 8.2" in octava and "Ref.-TMSCIIF-10" in octava
    assert "Área" in octava and "Transporte" in octava and "Responsable" in octava and "A. Pérez" in octava and "Fuera de plazo" in octava
    assert "**" not in octava and "- El volumen" not in octava
    # sugerencia: RIESGO BAJO, párrafo fijo y sin recomendación/plazo
    sug = next(t for t in todo if "Sugerencia de mejora 1" in t)
    assert "B\nA\nJ\nO" in sug and "dado su impacto limitado" in sug and "Recomendación" not in sug and "Plazo" not in sug
    # anexo de planes de acción: una fila por recomendación
    assert any("Anexo: planes de acción" in t for t in todo)
    anexo = next(s for s in prs.slides if any(sh.has_text_frame and sh.text_frame.text.startswith("Anexo") for sh in s.shapes))
    tabla = next(sh.table for sh in anexo.shapes if sh.has_table)
    assert [c.text for c in tabla.rows[0].cells] == ["N.º", "Observación", "Rec. N.º", "Plan de Acción", "Persona y Área Responsable", "Plazo"]
    assert [c.text for c in tabla.rows[1].cells][:3] == ["01", CONCLUSION["titulo"], "1.1"] and tabla.cell(1, 4).text == "A. Pérez · Transporte"
    assert tabla.cell(2, 2).text == "1.2" and tabla.cell(2, 0).text == ""
    assert todo[-1] == "Gracias"
    # carátula+índice, portadilla+intro, portadilla+resumen, portadilla+índice+8 detalles,
    # portadilla+1 sugerencia, portadilla+anexo en 2 páginas (16 recomendaciones), gracias
    assert len(prs.slides) == 2 + 2 + 2 + (2 + 8) + (1 + 1) + (1 + 2) + 1  # 22
