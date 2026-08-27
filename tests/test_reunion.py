"""`reunion`: transcripción de Teams → acta (texto vs PPT vs pendientes) e
instrucciones de texto en 03_instrucciones.md; `cambio`/`chat`: instrucciones
directas sin tocar el buzón."""
from __future__ import annotations

from pathlib import Path

import pytest

from audit_agent.acciones import accion_aplicar_cambios, accion_reunion
from audit_agent.esquemas import (AnalisisReunion, Cambio, CambioPPTDetectado, CambioTextoDetectado,
                                  PlanCambios)
from audit_agent.expediente import ExpedienteError
from audit_agent.formato_md import parsear_informe, render_informe

RAIZ = Path(__file__).resolve().parent.parent
CONCLUSION = {"titulo": "Mantenimiento manual del maestro de tarifas", "prueba": "2.11", "nivel_riesgo": "Medio",
              "incidencia": "El mantenimiento es manual.", "causa_raiz": "", "como_se_ha_llegado": "- PackPro acierta el 98%.\n- Alertas diarias.",
              "consecuencias": "Riesgo de tarifas desactualizadas.", "recomendacion": "Implantar un sistema de carga y evidencia de acuerdos."}


@pytest.fixture
def con_informe(contexto):
    datos = {"introduccion": "Intro.", "resumen_ejecutivo": "Resumen.\n\n/ Segunda viñeta larguísima.", "evaluacion_global": "Mejorable",
             "conclusiones": [CONCLUSION], "sugerencias": []}
    contexto.exp.archivo("informe").write_text(render_informe(datos, contexto.exp.proyecto), encoding="utf-8")
    return contexto


ANALISIS = AnalisisReunion(
    resumen="Se revisó el borrador y se acordaron cambios.",
    cambios_texto=[
        CambioTextoDetectado(seccion="Conclusión 1", que_cambiar="Subir el riesgo a Alto", instruccion="En la conclusión 1, cambiar el nivel de riesgo de Medio a Alto.", solicitado_por="Carmen Soto", cita="yo lo pondría en Alto"),
        CambioTextoDetectado(seccion="Conclusión 1", que_cambiar="Quitar la viñeta de PackPro", instruccion="En la conclusión 1, eliminar la viñeta de detalles que menciona PackPro y el 98%.", solicitado_por="Pablo Nieto"),
    ],
    cambios_ppt=[CambioPPTDetectado(que_cambiar="Magnitudes en gráfico de barras y plantilla corporativa nueva", solicitado_por="Carmen Soto", cita="quiero que las magnitudes vayan en un gráfico")],
    pendientes=["Importe anual facturado por los couriers: lo aporta Pablo Nieto esta semana."],
    acuerdos_sin_cambio=["Conformidad del área en diez días hábiles."])


def test_reunion_genera_acta_y_rellena_instrucciones(con_informe):
    ctx = con_informe
    ctx.llm.respuestas["reunion"] = ANALISIS
    salida = accion_reunion(ctx, RAIZ / "ejemplos" / "transcript_reunion_teams.txt")
    assert "2 cambio(s) en el TEXTO" in salida and "1 cambio(s) en el PPT" in salida and "solo informativo" in salida
    assert "Subir el riesgo a Alto (pide: Carmen Soto)" in salida and "Importe anual facturado" in salida
    prompt = ctx.llm.llamadas[-1][1]
    assert "[16:34:30] Carmen Soto" in prompt and "INFORME ACTUAL" in prompt
    actas = list((ctx.exp.ruta / "reuniones").glob("*.md"))
    assert len(actas) == 1 and "transcript_reunion_teams" in actas[0].name
    acta = actas[0].read_text(encoding="utf-8")
    assert "## Cambios en el texto del informe (2)" in acta and "## Cambios en la presentación (PPT) — informativo" in acta
    assert "Cita: «yo lo pondría en Alto»" in acta and "## Pendientes de dato o confirmación (1)" in acta
    pendientes = ctx.exp.instrucciones_pendientes()
    assert "- En la conclusión 1, cambiar el nivel de riesgo de Medio a Alto. [Carmen Soto]" in pendientes
    assert "borra o edita las que no procedan" in pendientes
    assert "gráfico de barras" not in pendientes  # lo de PPT no va al buzón
    assert ctx.exp.leer("informe").count("Nivel de riesgo: Medio") == 1  # sin --aplicar no se toca el informe


def test_reunion_aplicar_encadena_aplicar_cambios(con_informe):
    ctx = con_informe
    ctx.llm.respuestas["reunion"] = ANALISIS
    ctx.llm.respuestas["aplicar-cambios"] = PlanCambios(cambios=[
        Cambio(seccion="### 1. Mantenimiento manual del maestro de tarifas", motivo="riesgo", texto_original="- Nivel de riesgo: Medio", texto_nuevo="- Nivel de riesgo: Alto"),
        Cambio(seccion="### 1. Mantenimiento manual del maestro de tarifas", motivo="viñeta", texto_original="- PackPro acierta el 98%.\n", texto_nuevo="")])
    salida = accion_reunion(ctx, RAIZ / "ejemplos" / "transcript_reunion_teams.txt", aplicar=True)
    assert "=== aplicar-cambios ===" in salida and "Aplicados 2 de 2" in salida
    inf = parsear_informe(ctx.exp.leer("informe"))
    assert inf["conclusiones"][0]["nivel_riesgo"] == "Alto" and "PackPro" not in inf["conclusiones"][0]["como_se_ha_llegado"]
    assert ctx.exp.instrucciones_pendientes() == ""  # el buzón se vacía al aplicar
    assert "aplicar-cambios" in ctx.llm.llamadas[-1][0]


def test_reunion_sin_informe_o_sin_fichero(contexto):
    with pytest.raises(ExpedienteError, match="02_informe.md"):
        accion_reunion(contexto, RAIZ / "ejemplos" / "transcript_reunion_teams.txt")
    contexto.exp.archivo("informe").write_text("# x\n", encoding="utf-8")
    with pytest.raises(ExpedienteError, match="No existe"):
        accion_reunion(contexto, "/no/existe.txt")


def test_cambio_directo_no_toca_el_buzon(con_informe):
    ctx = con_informe
    ctx.exp.anexar_registro("instrucciones", "\nAlgo pendiente de otra reunión.\n")
    ctx.llm.respuestas["aplicar-cambios"] = PlanCambios(cambios=[
        Cambio(seccion="### 1. Mantenimiento manual del maestro de tarifas", motivo="riesgo", texto_original="- Nivel de riesgo: Medio", texto_nuevo="- Nivel de riesgo: Alto")])
    salida = accion_aplicar_cambios(ctx, instrucciones="Cambia el nivel de riesgo de la conclusión 1 a Alto.", origen="chat")
    assert "Aplicados 1 de 1" in salida and "03_instrucciones.md vaciado" not in salida
    assert ctx.exp.instrucciones_pendientes() == "Algo pendiente de otra reunión."
    assert parsear_informe(ctx.exp.leer("informe"))["conclusiones"][0]["nivel_riesgo"] == "Alto"
    assert "(chat)" in ctx.exp.leer("cambios")
    assert "Cambia el nivel de riesgo" in ctx.llm.llamadas[-1][1]
    with pytest.raises(ExpedienteError, match="Mensaje vacío"):
        accion_aplicar_cambios(ctx, instrucciones="   ")
