"""Nivel de riesgo «propuesto por el modelo, sin evidencia en PT»: se marca al
extraer, lo quita `aprobar` (validación del auditor) y `redactar-conclusiones`
no admite conclusiones que sigan marcadas."""
from __future__ import annotations

import pytest

from audit_agent.acciones import accion_aprobar, accion_extraer, accion_redactar_conclusiones
from audit_agent.esquemas import ConclusionExtraida, ExtraccionConclusiones
from audit_agent.expediente import ExpedienteError
from audit_agent.formato_md import COLETILLA_RIESGO_PROPUESTO, parsear_conclusiones, parsear_informe

COLETILLA = COLETILLA_RIESGO_PROPUESTO


def _conc(titulo, nivel, soportado, rec="Implantar un control automático.", tipo="conclusion"):
    return ConclusionExtraida(titulo=titulo, tipo=tipo, prueba="2.11 a)", incidencia="En 6 de 45 pedidos la aprobación fue posterior.",
                              causa_raiz="Sin circuito de urgencia", como_se_ha_llegado="Muestra de 45 pedidos.",
                              consecuencias="Gasto sin autorización efectiva", recomendacion=rec, nivel_riesgo=nivel,
                              responsable="Dirección de Compras", fuente="PT 2.11",
                              riesgo_soportado_por_evidencia=soportado, recomendacion_del_pt=bool(rec))


def _extraer(ctx):
    ctx.llm.respuestas["extraer"] = ExtraccionConclusiones(
        conclusiones=[_conc("Con evidencia", "Alto", True), _conc("Sin evidencia", "Medio", False)],
        pruebas_sin_incidencia=["2.3 Prueba limpia"], notas="")
    return accion_extraer(ctx)


def _lineas_nivel(exp):
    return [l for l in exp.leer("conclusiones").splitlines() if l.startswith("- Nivel de riesgo")]


def test_extraer_marca_solo_el_nivel_sin_evidencia(contexto):
    salida = _extraer(contexto)
    assert _lineas_nivel(contexto.exp) == ["- Nivel de riesgo: Alto", f"- Nivel de riesgo: Medio {COLETILLA}"]
    assert "Medio*" in salida and "(*)" in salida and "2.3 Prueba limpia" in salida
    assert "riesgo_soportado_por_evidencia" in contexto.llm.llamadas[0][1]
    assert "CON INCIDENCIAS" in contexto.llm.llamadas[0][1]
    cs = parsear_conclusiones(contexto.exp.leer("conclusiones"))
    assert cs[0]["riesgo_propuesto"] is False and cs[1]["riesgo_propuesto"] is True
    assert cs[1]["nivel_riesgo"] == "Medio" and cs[1]["prueba"] == "2.11 a)"


def test_extraer_sin_nivel_no_pone_coletilla(contexto):
    contexto.llm.respuestas["extraer"] = ExtraccionConclusiones(conclusiones=[_conc("Vacío", "", False)])
    accion_extraer(contexto)
    assert _lineas_nivel(contexto.exp) == ["- Nivel de riesgo: "]


def test_validador_acepta_nivel_con_coletilla(contexto):
    _extraer(contexto)
    c = parsear_conclusiones(contexto.exp.leer("conclusiones"))[1]
    r = contexto.checker.revisar_conclusion({**c, "nivel_riesgo": f"Medio {COLETILLA}"})
    assert not [h for h in r.hallazgos if h.tipo == "estructura" and h.severidad == "error"], r.to_dict()


def test_aprobar_quita_la_coletilla(contexto):
    _extraer(contexto)
    salida = accion_aprobar(contexto.exp, ["C-02"])
    assert "C-02" in salida
    assert _lineas_nivel(contexto.exp) == ["- Nivel de riesgo: Alto", "- Nivel de riesgo: Medio"]
    cs = parsear_conclusiones(contexto.exp.leer("conclusiones"))
    assert cs[1]["estado"] == "aprobada" and cs[1]["riesgo_propuesto"] is False
    assert cs[0]["estado"] == "propuesta"


def test_aprobar_admite_ids_flexibles(contexto):
    _extraer(contexto)
    assert "C-01, C-02" in accion_aprobar(contexto.exp, ["c-1", "OBS-02"])


def test_descartar_no_toca_la_coletilla(contexto):
    _extraer(contexto)
    accion_aprobar(contexto.exp, ["C-02"], estado="descartada")
    assert COLETILLA in _lineas_nivel(contexto.exp)[1]


def test_redactar_bloquea_aprobadas_con_riesgo_propuesto(contexto):
    _extraer(contexto)
    texto = contexto.exp.leer("conclusiones").replace("- Estado: propuesta", "- Estado: aprobada")
    contexto.exp.archivo("conclusiones").write_text(texto, encoding="utf-8")
    salida = accion_redactar_conclusiones(contexto)
    assert "C-02" in salida and "propuesto por el modelo" in salida
    informe = parsear_informe(contexto.exp.leer("informe"))
    assert [c["titulo"] for c in informe["conclusiones"]] == ["Con evidencia"]
    assert not [a for a, _ in contexto.llm.llamadas if a.startswith("redactar")]  # volcado sin modelo


def test_redactar_falla_si_todas_las_aprobadas_estan_pendientes(contexto):
    contexto.llm.respuestas["extraer"] = ExtraccionConclusiones(conclusiones=[_conc("Sin evidencia", "Bajo", False)])
    accion_extraer(contexto)
    texto = contexto.exp.leer("conclusiones").replace("- Estado: propuesta", "- Estado: aprobada")
    contexto.exp.archivo("conclusiones").write_text(texto, encoding="utf-8")
    with pytest.raises(ExpedienteError, match="C-01"):
        accion_redactar_conclusiones(contexto)


def test_redactar_tras_aprobar_incluye_todo(contexto):
    _extraer(contexto)
    accion_aprobar(contexto.exp, ["todas"])
    salida = accion_redactar_conclusiones(contexto)
    assert "Detalle de conclusiones (2)" in salida and "NO incluidas" not in salida
    assert COLETILLA not in contexto.exp.leer("informe")


def test_prompt_extraer_pide_una_conclusion_por_prueba_con_ejemplo(contexto):
    _extraer(contexto)
    prompt = contexto.llm.llamadas[0][1]
    assert "UNA conclusión por prueba" in prompt and "EJEMPLO DE REFERENCIA" in prompt
    assert "Limitaciones en el mantenimiento de los tarifarios" in prompt   # config/ejemplo_conclusion.md
    assert "no deben reutilizarse" in prompt
