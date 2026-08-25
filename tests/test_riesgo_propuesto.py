"""Nivel de riesgo «propuesto por el modelo, sin evidencia en PT»: se marca al
extraer, lo quita `aprobar` (validación del auditor) y `redactar` no admite
observaciones que sigan marcadas."""
from __future__ import annotations

import pytest

from audit_agent.acciones import accion_aprobar, accion_extraer, accion_redactar
from audit_agent.esquemas import (BorradorInforme, EvaluacionGlobal, ExtraccionObservaciones,
                                  Magnitud, Observacion, ObservacionExtraida)
from audit_agent.expediente import ExpedienteError
from audit_agent.formato_md import COLETILLA_RIESGO_PROPUESTO, parsear_observaciones

COLETILLA = COLETILLA_RIESGO_PROPUESTO


def _obs(titulo, nivel, soportado):
    return ObservacionExtraida(titulo=titulo, condicion="En 6 de 45 pedidos la aprobación fue posterior.",
                               criterio="Matriz de delegación v4.2", causa_raiz="Sin circuito de urgencia",
                               efecto="Gasto sin autorización efectiva", recomendacion="Definir circuito urgente",
                               nivel_riesgo=nivel, responsable="Dirección de Compras", fuente="PT T3.2",
                               riesgo_soportado_por_evidencia=soportado)


def _extraer(ctx):
    ctx.llm.respuestas["extraer"] = ExtraccionObservaciones(
        observaciones=[_obs("Con evidencia", "Alto", True), _obs("Sin evidencia", "Medio", False)], notas="")
    return accion_extraer(ctx)


def _lineas_nivel(exp):
    return [l for l in exp.leer("observaciones").splitlines() if l.startswith("- Nivel de riesgo")]


def test_extraer_marca_solo_el_nivel_sin_evidencia(contexto):
    salida = _extraer(contexto)
    lineas = _lineas_nivel(contexto.exp)
    assert lineas == ["- Nivel de riesgo: Alto", f"- Nivel de riesgo: Medio {COLETILLA}"]
    assert "Medio*" in salida and "(*)" in salida
    # el prompt pide explícitamente el booleano
    assert "riesgo_soportado_por_evidencia" in contexto.llm.llamadas[0][1]
    obs = parsear_observaciones(contexto.exp.leer("observaciones"))
    assert obs[0]["riesgo_propuesto"] is False and obs[1]["riesgo_propuesto"] is True
    assert obs[1]["nivel_riesgo"] == "Medio"  # el nivel se lee limpio, la coletilla es un flag


def test_extraer_sin_nivel_no_pone_coletilla(contexto):
    contexto.llm.respuestas["extraer"] = ExtraccionObservaciones(observaciones=[_obs("Vacío", "", False)], notas="")
    accion_extraer(contexto)
    assert _lineas_nivel(contexto.exp) == ["- Nivel de riesgo: "]


def test_validador_acepta_nivel_con_coletilla(contexto):
    _extraer(contexto)
    obs = parsear_observaciones(contexto.exp.leer("observaciones"))[1]
    r = contexto.checker.revisar_observacion({**obs, "nivel_riesgo": f"Medio {COLETILLA}"})
    assert not [h for h in r.hallazgos if h.tipo == "estructura"], r.to_dict()


def test_aprobar_quita_la_coletilla(contexto):
    _extraer(contexto)
    salida = accion_aprobar(contexto.exp, ["OBS-02"])
    assert "OBS-02" in salida
    assert _lineas_nivel(contexto.exp) == ["- Nivel de riesgo: Alto", "- Nivel de riesgo: Medio"]
    obs = parsear_observaciones(contexto.exp.leer("observaciones"))
    assert obs[1]["estado"] == "aprobada" and obs[1]["riesgo_propuesto"] is False
    assert obs[0]["estado"] == "propuesta"  # no se toca lo no pedido


def test_descartar_no_toca_la_coletilla(contexto):
    _extraer(contexto)
    accion_aprobar(contexto.exp, ["OBS-02"], estado="descartada")
    assert COLETILLA in _lineas_nivel(contexto.exp)[1]


def _borrador(obs_list):
    return BorradorInforme(objetivo="Obj", alcance="Alc", contexto="Ctx", magnitudes=[Magnitud(valor="45", etiqueta="pedidos")],
                           observaciones=[Observacion(**{k: getattr(o, k) for k in Observacion.model_fields}) for o in obs_list],
                           evaluacion_global=EvaluacionGlobal(gobierno="Razonable — Impacto Bajo", gestion_riesgos="Mejorable — Impacto Medio",
                                                              entorno_control="Mejorable — Impacto Medio", conclusion="Conclusión."),
                           proximos_pasos="Seguimiento.")


def test_redactar_bloquea_aprobadas_con_riesgo_propuesto(contexto):
    _extraer(contexto)
    # El auditor aprueba a mano las dos, pero deja la coletilla en OBS-02
    texto = contexto.exp.leer("observaciones").replace("- Estado: propuesta", "- Estado: aprobada")
    contexto.exp.archivo("observaciones").write_text(texto, encoding="utf-8")
    contexto.llm.respuestas["redactar"] = lambda accion, user: _borrador([_obs("Con evidencia", "Alto", True)])
    salida = accion_redactar(contexto)
    assert "OBS-02" in salida and "propuesto por el modelo" in salida
    assert '"titulo": "Sin evidencia"' not in contexto.llm.llamadas[-1][1]  # no se envía al modelo
    assert "con 1 observaciones" in salida


def test_redactar_falla_si_todas_las_aprobadas_estan_pendientes(contexto):
    contexto.llm.respuestas["extraer"] = ExtraccionObservaciones(observaciones=[_obs("Sin evidencia", "Bajo", False)], notas="")
    accion_extraer(contexto)
    texto = contexto.exp.leer("observaciones").replace("- Estado: propuesta", "- Estado: aprobada")
    contexto.exp.archivo("observaciones").write_text(texto, encoding="utf-8")
    with pytest.raises(ExpedienteError, match="OBS-01"):
        accion_redactar(contexto)
    assert not [a for a, _ in contexto.llm.llamadas if a == "redactar"]


def test_redactar_tras_aprobar_incluye_la_observacion(contexto):
    _extraer(contexto)
    accion_aprobar(contexto.exp, ["todas"])
    contexto.llm.respuestas["redactar"] = lambda accion, user: _borrador(
        [_obs("Con evidencia", "Alto", True), _obs("Sin evidencia", "Medio", False)])
    salida = accion_redactar(contexto)
    assert "con 2 observaciones" in salida and "NO incluidas" not in salida
    assert COLETILLA not in contexto.exp.leer("informe")
