"""Volver al informe con documentación nueva: qué se ha procesado ya, extraer solo de los
papeles de trabajo nuevos (añadiendo) y volcar al informe solo las observaciones nuevas sin
pisar lo editado después en el informe. También los pasos que guían la web."""
from __future__ import annotations

import pytest

from audit_agent.acciones import (accion_aprobar, accion_extraer, accion_redactar_conclusiones, estado_expediente,
                                  simular_redactar_conclusiones)
from audit_agent.esquemas import ConclusionExtraida, ExtraccionConclusiones
from audit_agent.expediente import ExpedienteError
from audit_agent.formato_md import parsear_conclusiones, parsear_informe


def _conc(titulo, prueba="2.11 a)"):
    return ConclusionExtraida(titulo=titulo, prueba=prueba, incidencia=f"Incidencia de {titulo}.", causa_raiz="Proceso manual.",
                              como_se_ha_llegado="- 6 de 45 pedidos", consecuencias="Riesgo de gasto sin control.",
                              recomendacion="Implantar un control automático.", nivel_riesgo="Medio",
                              riesgo_soportado_por_evidencia=True, recomendacion_del_pt=True)


def _extraer(ctx, *titulos, **kw):
    ctx.llm.respuestas["extraer"] = ExtraccionConclusiones(conclusiones=[_conc(t) for t in titulos])
    return accion_extraer(ctx, **kw)


def _pasos(exp):
    e = estado_expediente(exp)
    return e, {p["id"]: p for p in e["pasos"]}


def test_extraer_solo_nuevos_anade_sin_tocar_lo_revisado(contexto):
    exp = contexto.exp
    assert [p.name for p in exp.documentos_nuevos("papeles_trabajo")] == ["papel_trabajo_compras.md"]
    _extraer(contexto, "Ofertas comparativas")
    assert exp.documentos_nuevos("papeles_trabajo") == []
    accion_aprobar(exp, ["C-01"])
    # el auditor vuelve con una prueba más
    (exp.ruta / "papeles_trabajo" / "prueba_6_2.md").write_text("6.2. REVISIÓN DEL CÁLCULO DE PORTES\nCon incidencias.", encoding="utf-8")
    e, pasos = _pasos(exp)
    assert e["nuevos"]["papeles_trabajo"] == ["prueba_6_2.md"] and e["paso_sugerido"] == "observaciones"
    assert pasos["documentos"]["aviso"] == "1 documento nuevo sin procesar"
    with pytest.raises(ExpedienteError, match="--solo-nuevos"):
        _extraer(contexto, "X")
    salida = _extraer(contexto, "Cálculo de portes", solo_nuevos=True)
    prompt = contexto.llm.llamadas[-1][1]
    assert "prueba_6_2.md" in prompt and "papel_trabajo_compras.md" not in prompt   # solo el papel nuevo
    assert "C-01 · 2.11 a) · Ofertas comparativas" in prompt                        # sabe lo que ya hay
    cs = parsear_conclusiones(exp.leer("conclusiones"))
    assert [(c["id"], c["titulo"], c["estado"]) for c in cs] == [("C-01", "Ofertas comparativas", "aprobada"),
                                                                ("C-02", "Cálculo de portes", "propuesta")]
    assert "Se ha añadido 1 conclusión nueva (de prueba_6_2.md)" in salida
    assert exp.documentos_nuevos("papeles_trabajo") == []
    with pytest.raises(ExpedienteError, match="No hay papeles de trabajo nuevos"):
        _extraer(contexto, "Y", solo_nuevos=True)


def test_documento_modificado_vuelve_a_ser_nuevo(contexto):
    exp = contexto.exp
    _extraer(contexto, "A")
    (exp.ruta / "papeles_trabajo" / "papel_trabajo_compras.md").write_text("otra versión", encoding="utf-8")
    assert [p.name for p in exp.documentos_nuevos("papeles_trabajo")] == ["papel_trabajo_compras.md"]


def test_expediente_anterior_al_registro_no_marca_todo_como_nuevo(contexto):
    exp = contexto.exp
    _extraer(contexto, "A")
    (exp.ruta / exp.REGISTRO).unlink()
    assert exp.documentos_nuevos("papeles_trabajo") == []                # ya había conclusiones: se dan por procesados


def test_anadir_al_informe_conserva_lo_editado_y_solo_suma_las_nuevas(contexto):
    exp = contexto.exp
    _extraer(contexto, "Ofertas comparativas", "Segregación de funciones")
    accion_aprobar(exp, ["C-01"])
    accion_redactar_conclusiones(contexto)
    assert exp.registro()["volcadas"] == ["C-01"]
    # después se edita el informe (chat, reunión o a mano)
    exp.escribir("informe", exp.leer("informe").replace("Incidencia de Ofertas comparativas.", "Texto pulido en la reunión."), "reunion")
    accion_aprobar(exp, ["C-02"])
    e, pasos = _pasos(exp)
    assert e["sin_volcar"] == ["C-02"] and pasos["observaciones"]["aviso"] == "1 aprobada sin pasar al informe"
    # la simulación enseña qué cambiaría y no escribe
    antes = exp.leer("informe")
    sim = simular_redactar_conclusiones(contexto, "anadir")
    assert exp.leer("informe") == antes
    assert sim["entran"] == ["C-02 · Segregación de funciones"]
    assert {a["titulo"]: a["estado"] for a in sim["apartados"] if a["estado"] != "igual"} == {"Segregación de funciones": "nuevo"}
    # rehacer, en cambio, pisaría lo editado: la simulación lo muestra como modificado
    rehacer = simular_redactar_conclusiones(contexto, "rehacer")
    assert any(a["titulo"] == "Ofertas comparativas" and a["estado"] == "modificado" for a in rehacer["apartados"])
    accion_redactar_conclusiones(contexto, modo="anadir")
    inf = parsear_informe(exp.leer("informe"))
    assert [c["titulo"] for c in inf["conclusiones"]] == ["Ofertas comparativas", "Segregación de funciones"]
    assert "Texto pulido en la reunión." in exp.leer("informe")
    assert sorted(exp.registro()["volcadas"]) == ["C-01", "C-02"]
    with pytest.raises(ExpedienteError, match="ya están en el informe"):
        accion_redactar_conclusiones(contexto, modo="anadir")


def test_volcadas_sin_registro_se_deducen_por_titulo(contexto):
    exp = contexto.exp
    _extraer(contexto, "Ofertas comparativas", "Segregación de funciones")
    accion_aprobar(exp, ["todas"])
    accion_redactar_conclusiones(contexto)
    reg = exp.registro(); reg.pop("volcadas")
    (exp.ruta / exp.REGISTRO).write_text(__import__("json").dumps(reg), encoding="utf-8")
    assert estado_expediente(exp)["sin_volcar"] == []


def test_volcadas_sin_registro_aunque_el_titulo_se_cambiara_en_el_informe(contexto):
    """Caso real (MEP-2027): expediente anterior al registro cuyo título se retocó en el informe
    después de volcarlo; no puede salir como «aprobada sin pasar al informe»."""
    exp = contexto.exp
    _extraer(contexto, "Mantenimiento manual y descoordinado del maestro de tarifarios que impacta la inferencia de costes")
    accion_aprobar(exp, ["C-01"])
    accion_redactar_conclusiones(contexto)
    exp.escribir("informe", exp.leer("informe").replace("descoordinado del maestro de tarifarios que impacta la inferencia de costes",
                                                         "no estandarizado del maestro de tarifarios que impacta la estimación de costes"), "cambio")
    reg = exp.registro(); reg.pop("volcadas")
    (exp.ruta / exp.REGISTRO).write_text(__import__("json").dumps(reg), encoding="utf-8")
    assert estado_expediente(exp)["sin_volcar"] == []
    # una aprobada que de verdad no está sigue saliendo
    _extraer(contexto, "Accesos privilegiados sin revisión periódica", solo_nuevos=False, forzar=True)
    accion_aprobar(exp, ["C-01"])
    assert estado_expediente(exp)["sin_volcar"] == ["C-01"]


def test_pasos_guian_de_principio_a_fin(contexto):
    exp = contexto.exp
    e, pasos = _pasos(exp)
    assert [p["id"] for p in e["pasos"]] == ["documentos", "contexto", "observaciones", "informe", "entrega"]
    assert e["paso_sugerido"] == "contexto" and pasos["documentos"]["hecho"] and not pasos["contexto"]["hecho"]
    assert "`" not in e["sugerencia"]                                     # lenguaje del auditor, no comandos del CLI
    assert sum(p["actual"] for p in e["pasos"]) == 1
