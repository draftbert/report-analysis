"""`recomendar`: respeta al 100 % la recomendación del auditor, solo formatea
si se pide (y verifica que conserva la base), propone si falta y puede
añadir una sugerencia de mejora complementaria. `redactar-conclusiones`
bloquea conclusiones sin recomendación."""
from __future__ import annotations

import pytest

from audit_agent.acciones import (accion_aprobar, accion_extraer, accion_recomendar,
                                  accion_redactar_conclusiones, conserva_base)
from audit_agent.esquemas import (ConclusionExtraida, ExtraccionConclusiones, RecomendacionFormateada,
                                  RecomendacionPropuesta)
from audit_agent.expediente import ExpedienteError
from audit_agent.formato_md import parsear_conclusiones, parsear_informe


def _conc(titulo, rec="", tipo="conclusion"):
    return ConclusionExtraida(titulo=titulo, tipo=tipo, prueba="2.11 b)", incidencia="Tarifario desactualizado en la HC.",
                              causa_raiz="Sin plantilla común de carga", como_se_ha_llegado="Sesiones con el área.",
                              consecuencias="Error en la valoración de costes", recomendacion=rec, nivel_riesgo="Medio",
                              responsable="", fuente="PT", riesgo_soportado_por_evidencia=True, recomendacion_del_pt=bool(rec))


REC_PT = "Implantar un sistema para la carga y gestión de los tarifarios (TMSCIIF-10)."


@pytest.fixture
def con_conclusiones(contexto):
    contexto.llm.respuestas["extraer"] = ExtraccionConclusiones(
        conclusiones=[_conc("Con rec del PT", REC_PT), _conc("Sin rec"), _conc("Sugerencia", "Mejorar X", tipo="sugerencia"),
                      _conc("Sugerencia vacía", tipo="sugerencia")])
    accion_extraer(contexto)
    accion_aprobar(contexto.exp, ["todas"])
    return contexto


def _recs(exp):
    return {c["id"]: c["recomendacion"] for c in parsear_conclusiones(exp.leer("conclusiones"))}


def test_respeta_recomendacion_existente_y_texto_del_auditor(con_conclusiones):
    ctx = con_conclusiones
    salida = accion_recomendar(ctx, ids=["C-01", "C-02", "C-03"],
                               preguntar=lambda c: "  Revisar los tarifarios trimestralmente con Operativa. " if c["id"] == "C-02" else None)
    assert "C-01: recomendación ya presente" in salida and "C-02: recomendación del auditor registrada" in salida
    recs = _recs(ctx.exp)
    assert recs["C-01"] == REC_PT
    assert recs["C-02"] == "Revisar los tarifarios trimestralmente con Operativa."
    assert recs["C-03"] == "Mejorar X"  # las sugerencias con propuesta no se tocan
    assert ctx.llm.llamadas[-1][0] == "extraer"  # ninguna llamada al modelo


def test_propone_si_falta_y_anade_sugerencia_complementaria(con_conclusiones):
    ctx = con_conclusiones
    ctx.llm.respuestas["recomendar-"] = RecomendacionPropuesta(
        recomendacion="Definir una plantilla única de carga de tarifas.",
        sugerencia_mejora_titulo="Alertas de tarifa desactualizada", sugerencia_mejora_texto="Automatizar la alerta semanal.")
    salida = accion_recomendar(ctx, preguntar=None)
    assert "C-02: recomendación propuesta por el modelo" in salida and "Alertas de tarifa desactualizada" in salida
    assert "C-04: propuesta de mejora propuesta por el modelo" in salida
    cs = parsear_conclusiones(ctx.exp.leer("conclusiones"))
    assert _recs(ctx.exp)["C-02"] == "Definir una plantilla única de carga de tarifas."
    assert _recs(ctx.exp)["C-04"] == "Definir una plantilla única de carga de tarifas."  # misma respuesta falsa
    assert cs[-1]["id"] == "C-05" and cs[-1]["tipo"] == "sugerencia" and cs[-1]["estado"] == "propuesta"
    assert cs[-1]["recomendacion"] == "Automatizar la alerta semanal." and "derivada de C-02" in cs[-1]["fuente"]
    assert [a for a, _ in ctx.llm.llamadas if a.startswith("recomendar-")] == ["recomendar-C-02", "recomendar-C-04"]
    assert "SUGERENCIA:" in ctx.llm.llamadas[-1][1]  # a una sugerencia no se le piden complementarias


def test_formatear_conserva_la_base_o_no_toca(con_conclusiones):
    ctx = con_conclusiones
    ctx.llm.respuestas["formatear-recomendacion-"] = RecomendacionFormateada(
        recomendacion="Se recomienda implantar un sistema para la carga y gestión de los tarifarios (TMSCIIF-10).")
    salida = accion_recomendar(ctx, ids=["C-01"], formatear=True)
    assert "base conservada" in salida
    assert _recs(ctx.exp)["C-01"].startswith("Se recomienda implantar")
    # una "formateada" que cambia el contenido se rechaza
    ctx.llm.respuestas["formatear-recomendacion-"] = RecomendacionFormateada(recomendacion="Contratar más personal.")
    salida = accion_recomendar(ctx, ids=["C-01"], formatear=True)
    assert "NO conservaba la base" in salida and _recs(ctx.exp)["C-01"].startswith("Se recomienda implantar")


def test_conserva_base():
    assert conserva_base("Implantar un sistema de carga de tarifarios", "Se recomienda implantar un sistema de carga de tarifarios.")
    assert not conserva_base("Implantar un sistema de carga de tarifarios", "Contratar personal adicional.")


def test_redactar_bloquea_sin_recomendacion_y_vuelca_el_resto(con_conclusiones):
    ctx = con_conclusiones
    salida = accion_redactar_conclusiones(ctx)
    assert "C-02" in salida and "sin recomendación" in salida and "C-04 (sin propuesta de mejora)" in salida
    inf = parsear_informe(ctx.exp.leer("informe"))
    assert [c["titulo"] for c in inf["conclusiones"]] == ["Con rec del PT"]
    assert [s["titulo"] for s in inf["sugerencias"]] == ["Sugerencia"] and inf["sugerencias"][0]["recomendacion"] == "Mejorar X"
    assert inf["conclusiones"][0]["recomendacion"] == REC_PT


def test_redactar_falla_si_ninguna_lista(contexto):
    contexto.llm.respuestas["extraer"] = ExtraccionConclusiones(conclusiones=[_conc("Sin rec")])
    accion_extraer(contexto)
    accion_aprobar(contexto.exp, ["todas"])
    with pytest.raises(ExpedienteError, match="sin recomendación"):
        accion_redactar_conclusiones(contexto)
