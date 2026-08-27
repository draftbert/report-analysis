"""`condensar`: acorta un poco el informe con el modelo, campo a campo, y solo acepta
cada versión si es más corta, conserva cifras/referencias/frases fijas y cumple las
reglas; la recomendación nunca viaja al modelo. Snapshot y diff como el resto."""
from __future__ import annotations

import json

from audit_agent.acciones import ULTIMO_RESULTADO, _acepta_condensado, _cifras, accion_condensar
from audit_agent.esquemas import ApartadoCondensado, InformeCondensado
from audit_agent.formato_md import parsear_informe, render_informe

INTRO = ("La auditoría ha sido realizada en cumplimiento del Plan de Auditoría del año 2026, aprobado por la Comisión de Auditoría y Cumplimiento.\n\n"
         "**Contexto:**\nEl área gestiona más de 360 couriers en 200 mercados, con un volumen elevado y creciente de envíos.\n\n"
         "El trabajo ha sido llevado a cabo de acuerdo con las Normas Internacionales para la Práctica Profesional de Auditoría Interna, según certificado emitido por el Instituto de Auditores Internos.")
CONC = {"titulo": "Mantenimiento manual del maestro de tarifas", "nivel_riesgo": "Medio", "prueba": "2.11", "area": "Transporte",
        "responsable": "A. Pérez", "plazo": "31/12/2026", "referencia_recomendacion": "TMSCIIF-10",
        "incidencia": "El control debe garantizar la carga estandarizada de las tarifas. Durante nuestra revisión hemos identificado que el proceso es mayoritariamente manual y que carece de una plantilla común, lo que dificulta la trazabilidad de los cambios realizados.",
        "como_se_ha_llegado": "- El maestro se actualiza a mano por los equipos de validación de facturas.\n- Las reclamaciones ascienden a 1,4 M€ en 2025.",
        "consecuencias": "La manualidad incrementa el riesgo de tarifas desactualizadas, pudiendo derivar en una asignación subóptima de couriers.",
        "recomendacion": "Implantar un sistema para la carga y gestión de los tarifarios."}


def _informe(exp):
    exp.escribir("informe", render_informe({"introduccion": INTRO, "resumen_ejecutivo": "Resumen largo del informe con 3 conclusiones.\n\n/ Primera conclusión relevante.",
                                            "evaluacion_global": "Mejorable", "conclusiones": [CONC], "sugerencias": []}, exp.proyecto), "test")


def test_condensa_acepta_lo_valido_y_conserva_lo_que_pierde_cifras(contexto):
    exp = contexto.exp
    _informe(exp)
    contexto.llm.respuestas["condensar"] = InformeCondensado(
        introduccion=INTRO.replace("con un volumen elevado y creciente de envíos", "con gran volumen de envíos"),
        resumen_ejecutivo="Resumen más largo todavía del informe con sus 3 conclusiones y más palabras.\n\n/ Primera conclusión relevante.",  # más largo: se conserva
        conclusiones=[ApartadoCondensado(
            numero=1,
            incidencia="El control debe garantizar la carga estandarizada de las tarifas. Durante nuestra revisión hemos identificado un proceso mayoritariamente manual y sin plantilla común, lo que dificulta la trazabilidad de los cambios.",
            como_se_ha_llegado="- El maestro se actualiza a mano por validación de facturas.\n- Las reclamaciones ascienden a 1,4 M€.",  # pierde «2025»
            consecuencias="La manualidad eleva el riesgo de tarifas desactualizadas y de asignación subóptima de couriers.")])
    msg = accion_condensar(contexto, objetivo=0.85)
    assert "Informe condensado" in msg and "Snapshot previo" in msg
    assert "resumen ejecutivo (la versión nueva es más larga)" in msg and "como_se_ha_llegado (pierde cifras o referencias: 2025)" in msg
    datos = parsear_informe(exp.leer("informe"))
    c = datos["conclusiones"][0]
    assert "sin plantilla común" in c["incidencia"] and "ascienden a 1,4 M€ en 2025" in c["como_se_ha_llegado"]
    assert c["recomendacion"] == CONC["recomendacion"] and c["referencia_recomendacion"] == "TMSCIIF-10" and c["plazo"] == "31/12/2026"
    assert "con gran volumen de envíos" in datos["introduccion"] and datos["introduccion"].startswith("La auditoría ha sido realizada")
    assert datos["resumen_ejecutivo"].startswith("Resumen largo") and datos["evaluacion_global"] == "Mejorable"
    assert ULTIMO_RESULTADO["palabras_despues"] < ULTIMO_RESULTADO["palabras_antes"] and ULTIMO_RESULTADO["diff"]
    assert set(ULTIMO_RESULTADO["aplicados"]) == {"introducción", "conclusión 1 · incidencia", "conclusión 1 · consecuencias"}
    assert (exp.ruta / "historial").exists() and any("condensar" in p.name for p in (exp.ruta / "historial").iterdir())
    # la recomendación no viaja al modelo; la extensión orientativa sí va en el sistema
    accion, user = contexto.llm.llamadas[-1]
    assert accion == "condensar" and "Implantar un sistema" not in user and json.loads(user.split("\n\n", 2)[-1].split("\n", 0)[0] or "{}") is not None
    assert "EXTENSIÓN ORIENTATIVA" in contexto.system and "≈ 110 palabras" in contexto.system


def test_sin_cambios_no_escribe(contexto):
    exp = contexto.exp
    _informe(exp)
    antes = exp.leer("informe")
    contexto.llm.respuestas["condensar"] = InformeCondensado(introduccion=INTRO, resumen_ejecutivo="Resumen largo del informe con 3 conclusiones.\n\n/ Primera conclusión relevante.",
                                                             conclusiones=[ApartadoCondensado(numero=1, incidencia=CONC["incidencia"], como_se_ha_llegado=CONC["como_se_ha_llegado"], consecuencias=CONC["consecuencias"])])
    assert accion_condensar(contexto).startswith("No se ha condensado")
    assert exp.leer("informe") == antes


def test_criterios_de_aceptacion(contexto):
    assert _cifras("El 1,8 % de 5.000 casos en 2024 (ref. TMSCIIF-10): 1) alta; 2) baja") == {"1,8", "5.000", "2024", "TMSCIIF-10"}
    assert _acepta_condensado(contexto, "Texto con 12 casos.", "Texto con 12 casos") is None
    assert "más larga" in _acepta_condensado(contexto, "Corto.", "Mucho más largo que el original.")
    assert "pierde cifras" in _acepta_condensado(contexto, "Hubo 12 casos.", "Hubo casos.")
    assert "vacío" in _acepta_condensado(contexto, "Algo.", "")
    assert "estilo" in _acepta_condensado(contexto, "Hubo una debilidad relevante.", "Hubo un fallo.")
    assert "frase fija" in _acepta_condensado(contexto, "La auditoría ha sido realizada en cumplimiento del Plan. Más.", "Más.", ("La auditoría ha sido realizada",))
