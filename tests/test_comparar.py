"""Comparación del informe por apartados («Últimos cambios» de la web)."""
from __future__ import annotations

from audit_agent.comparar import comparar_informes, origen_cambio
from audit_agent.formato_md import render_informe

PROY = {"nombre": "N", "referencia": "R", "fecha": "F", "distribucion": ["D"]}
C = {"titulo": "Tarifario desactualizado", "tipo": "recomendacion", "prueba": "2.11 b)", "nivel_riesgo": "Medio",
     "responsable": "Operativa", "incidencia": "Durante nuestra revisión hemos identificado 12 tarifas sin actualizar.",
     "causa_raiz": "Sin plantilla común.", "como_se_ha_llegado": "- 12 tarifas\n- 3 mercados",
     "consecuencias": "Riesgo de error de coste.", "recomendacion": "Implantar una plantilla común."}
D = {**C, "titulo": "Alerta manual", "incidencia": "La alerta de vencimiento se lanza a mano.", "nivel_riesgo": "Bajo"}


def _md(conclusiones, intro="Intro.", resumen="Res.", evaluacion="", sugerencias=()):
    return render_informe({"introduccion": intro, "resumen_ejecutivo": resumen, "evaluacion_global": evaluacion,
                           "conclusiones": list(conclusiones), "sugerencias": list(sugerencias)}, PROY)


def _por_titulo(r):
    return {a["titulo"]: a for a in r["apartados"]}


def test_sin_cambios_todo_igual():
    md = _md([C])
    r = comparar_informes(md, md)
    assert {a["estado"] for a in r["apartados"]} == {"igual"}
    assert r["lineas_nuevas"] == r["lineas_borradas"] == 0


def test_palabra_cambiada_marca_solo_esa_palabra():
    r = comparar_informes(_md([C]), _md([{**C, "incidencia": C["incidencia"].replace("12", "15")}]))
    ap = _por_titulo(r)["Tarifario desactualizado"]
    assert ap["estado"] == "modificado" and (ap["lineas_nuevas"], ap["lineas_borradas"]) == (1, 1)
    borrada, nueva = [l for l in ap["lineas"] if l["tipo"] != "igual"]
    assert borrada["tipo"] == "del" and nueva["tipo"] == "add"             # primero lo eliminado, luego lo nuevo
    assert [s["texto"] for s in nueva["segmentos"] if s["cambio"]] == ["15"]
    assert [s["texto"] for s in borrada["segmentos"] if s["cambio"]] == ["12"]
    assert "".join(s["texto"] for s in nueva["segmentos"]) == nueva["texto"]
    assert _por_titulo(r)["Introducción"]["estado"] == "igual"


def test_linea_reescrita_entera_sin_marcas_de_palabra():
    r = comparar_informes(_md([C]), _md([{**C, "causa_raiz": "Proceso íntegramente manual en otra herramienta."}]))
    cambiadas = [l for l in _por_titulo(r)["Tarifario desactualizado"]["lineas"] if l["tipo"] != "igual"]
    assert cambiadas and all(l["segmentos"] is None for l in cambiadas)


def test_conclusion_anadida_y_eliminada():
    r = comparar_informes(_md([C, D]), _md([D]))
    ap = _por_titulo(r)
    assert ap["Tarifario desactualizado"]["estado"] == "eliminado"
    assert all(l["tipo"] == "del" for l in ap["Tarifario desactualizado"]["lineas"])
    assert ap["Tarifario desactualizado"]["id"].startswith("antes-")      # no choca con el id del apartado actual
    # «Alerta manual» pasa de ser la 2 a la 1: solo cambia la numeración (título y recomendación), no se trata como nueva
    alerta = ap["Alerta manual"]
    assert alerta["estado"] == "modificado" and alerta["lineas_nuevas"] == 2
    assert {s["texto"] for l in alerta["lineas"] if l["tipo"] == "add" for s in l["segmentos"] if s["cambio"]} == {"1"}
    r = comparar_informes(_md([D]), _md([D, C]))
    assert _por_titulo(r)["Tarifario desactualizado"]["estado"] == "nuevo"
    assert [a["titulo"] for a in r["apartados"]][-2:] == ["Alerta manual", "Tarifario desactualizado"]


def test_titulo_cambiado_se_empareja_como_modificado():
    r = comparar_informes(_md([C]), _md([{**C, "titulo": "Tarifario sin actualizar"}]))
    estados = {a["titulo"]: a["estado"] for a in r["apartados"]}
    assert estados["Tarifario sin actualizar"] == "modificado" and "Tarifario desactualizado" not in estados


def test_conclusion_sustituida_por_otra_distinta_no_se_empareja():
    E = {**C, "titulo": "Accesos privilegiados sin revisión", "nivel_riesgo": "Alto",
         "incidencia": "Los accesos privilegiados al sistema no se revisan periódicamente.",   # misma causa raíz que D
         "como_se_ha_llegado": "- 9 usuarios administradores", "consecuencias": "Riesgo de modificaciones no autorizadas.",
         "recomendacion": "Revisar trimestralmente los accesos."}
    r = comparar_informes(_md([C, D]), _md([C, E]))
    estados = {a["titulo"]: a["estado"] for a in r["apartados"]}
    assert estados["Alerta manual"] == "eliminado" and estados["Accesos privilegiados sin revisión"] == "nuevo"
    assert estados["Tarifario desactualizado"] == "igual"


def test_evaluacion_global_se_compara_en_el_resumen():
    r = comparar_informes(_md([C], evaluacion="Mejorable"), _md([C], evaluacion="Razonable"))
    res = _por_titulo(r)["Resumen ejecutivo"]
    assert res["estado"] == "modificado"
    assert any(l["tipo"] == "add" and "Razonable" in l["texto"] for l in res["lineas"])


def test_cambio_fuera_de_los_apartados_muestra_el_documento():
    md = _md([C])
    r = comparar_informes(md, md + "\nNota suelta al final.\n")
    doc = [a for a in r["apartados"] if a["id"] == "documento"]
    assert doc and doc[0]["lineas_nuevas"] >= 1


def test_origen_de_cada_motivo():
    assert origen_cambio("cambio") == "Chat del asistente"
    assert origen_cambio("reunion") == "Acta de reunión"
    assert origen_cambio("web") == "Edición manual"
    assert origen_cambio("otro-motivo") == "Otro motivo"
