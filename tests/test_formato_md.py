"""Ida y vuelta del formato Markdown: conclusiones e informe con tablas y listas."""
from __future__ import annotations

from audit_agent.formato_md import (parsear_conclusiones, parsear_informe, render_conclusiones,
                                    render_informe)

PROY = {"nombre": "N", "referencia": "R", "fecha": "F", "distribucion": ["D1", "D2"]}
C1 = {"id": "C-01", "titulo": "Tarifario desactualizado", "tipo": "conclusion", "estado": "propuesta", "prueba": "2.11 b)",
      "nivel_riesgo": "Medio", "riesgo_propuesto": True, "responsable": "Operativa", "fuente": "PT 2.11",
      "incidencia": "Inc.\n\n| Mercado | Courier |\n|---|---|\n| USA | FedEx |", "causa_raiz": "Sin plantilla común",
      "como_se_ha_llegado": "- Sesiones con el área\n- Revisión del flujo:\n  1) renegociación\n  2) carga manual",
      "consecuencias": "Error de coste", "recomendacion": "", "notas": "revisar"}
C2 = {**C1, "id": "C-02", "titulo": "Alerta manual", "tipo": "sugerencia", "estado": "aprobada", "nivel_riesgo": "",
      "riesgo_propuesto": False, "recomendacion": "Automatizar la alerta", "notas": ""}


def test_conclusiones_round_trip():
    md = render_conclusiones([C1, C2], PROY, "nota", ["2.3 limpia"])
    assert "> **Pruebas concluidas sin incidencias**" in md and "**Propuesta de mejora:** Automatizar la alerta" in md
    back = parsear_conclusiones(md)
    for k in ("id", "titulo", "tipo", "estado", "prueba", "nivel_riesgo", "riesgo_propuesto", "responsable", "fuente",
              "incidencia", "causa_raiz", "como_se_ha_llegado", "consecuencias", "recomendacion", "notas"):
        assert back[0][k] == C1[k], k
        assert back[1][k] == C2[k], k


def test_conclusiones_editadas_a_mano():
    md = render_conclusiones([C1], PROY)
    md = md.replace("- Tipo: conclusion", "- Tipo: Sugerencia de mejora").replace("- Estado: propuesta", "- estado: APROBADA")
    md = md.replace("**Recomendación:** ", "**Recomendación:** Texto del auditor\ncon dos líneas.")
    md += "\n## C-05 · Añadida a mano\n\n- Estado: aprobada\n\n**Incidencia detectada:** X\n\n**Consecuencias:** Y\n"
    back = parsear_conclusiones(md)
    assert back[0]["tipo"] == "sugerencia" and back[0]["estado"] == "aprobada"
    assert back[0]["recomendacion"] == "Texto del auditor\ncon dos líneas."
    assert back[1]["id"] == "C-05" and back[1]["incidencia"] == "X" and back[1]["causa_raiz"] == ""


def test_informe_round_trip_y_pendientes():
    datos = {"introduccion": "Intro **negrita**.\n\nSegundo párrafo.", "resumen_ejecutivo": "- p1\n- p2",
             "conclusiones": [C1], "sugerencias": [C2]}
    md = render_informe(datos, PROY)
    assert "## Introducción" in md and "## Resumen ejecutivo" in md and "## Detalle de conclusiones" in md and "## Sugerencias de mejora" in md
    assert "Fuente:" not in md and "Estado:" not in md and "**Incidencia detectada:**" not in md  # WYSIWYG: sin etiquetas de campo
    assert "*A continuación, se muestran los detalles descriptivos de la situación anterior:*" in md
    assert "**Propuesta de mejora 1.1.** Automatizar la alerta" in md
    back = parsear_informe(md)
    assert back["introduccion"] == datos["introduccion"] and back["resumen_ejecutivo"] == datos["resumen_ejecutivo"]
    c = back["conclusiones"][0]
    assert c["incidencia"] == C1["incidencia"] + "\n\n" + C1["causa_raiz"]      # prosa del cuerpo
    assert c["como_se_ha_llegado"] == "- Sesiones con el área\n- Revisión del flujo:\n- 1) renegociación\n- 2) carga manual"
    assert c["consecuencias"] == C1["consecuencias"] and c["nivel_riesgo"] == "Medio" and c["riesgo_propuesto"] is True
    assert back["sugerencias"][0]["recomendacion"] == "Automatizar la alerta"
    # render(parse(md)) == md: lo que se ve es lo que se exporta
    assert render_informe({**back, "introduccion": datos["introduccion"], "resumen_ejecutivo": datos["resumen_ejecutivo"]}, PROY) == md
    vacio = parsear_informe(render_informe({"introduccion": "", "resumen_ejecutivo": ""}, PROY))
    assert vacio == {"introduccion": "", "resumen_ejecutivo": "", "conclusiones": [], "sugerencias": []}


def test_informe_varias_recomendaciones_numeradas():
    c = {**C1, "recomendacion": "Rec uno.\n\nRec dos.", "riesgo_propuesto": False}
    md = render_informe({"introduccion": "I", "resumen_ejecutivo": "R", "conclusiones": [c, c], "sugerencias": []}, PROY)
    assert "**Recomendación 1.1.** Rec uno." in md and "**Recomendación 1.2.** Rec dos." in md and "**Recomendación 2.1.** Rec uno." in md
    back = parsear_informe(md)
    assert back["conclusiones"][1]["recomendacion"] == "Rec uno.\n\nRec dos."


def test_metadatos_plan_de_accion_round_trip():
    c = {**C1, "area": "FLF", "responsable": "A. Veiga", "plazo": "Fuera de plazo", "referencia_recomendacion": "TMSCIIF-10",
         "recomendacion": "Rec 1.\n\nRec 2."}
    md = render_conclusiones([c], PROY)
    assert "- Área: FLF" in md and "- Plazo: Fuera de plazo" in md and "- Ref. recomendación: TMSCIIF-10" in md
    back = parsear_conclusiones(md)[0]
    assert (back["area"], back["responsable"], back["plazo"], back["referencia_recomendacion"]) == ("FLF", "A. Veiga", "Fuera de plazo", "TMSCIIF-10")
    assert back["recomendacion"] == "Rec 1.\n\nRec 2."
    inf = parsear_informe(render_informe({"introduccion": "I", "resumen_ejecutivo": "R", "conclusiones": [c], "sugerencias": []}, PROY))
    assert inf["conclusiones"][0]["plazo"] == "Fuera de plazo" and inf["conclusiones"][0]["referencia_recomendacion"] == "TMSCIIF-10"
    assert inf["conclusiones"][0]["recomendacion"] == "Rec 1.\n\nRec 2."
