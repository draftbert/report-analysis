"""contexto/ y papeles_trabajo/: qué alimenta a cada acción y cómo lo ve el modelo."""
from __future__ import annotations

import pytest

from audit_agent.acciones import accion_extraer, accion_redactar_contexto, estado_expediente
from audit_agent.esquemas import ContextoInforme, ExtraccionConclusiones
from audit_agent.expediente import ExpedienteError


def test_extraer_agrupa_contexto_y_papeles_en_el_prompt(contexto):
    (contexto.exp.ruta / "contexto" / "design_thinking.md").write_text("Motivo: revisar compras.", encoding="utf-8")
    contexto.llm.respuestas["extraer"] = ExtraccionConclusiones(conclusiones=[])
    salida = accion_extraer(contexto)
    prompt = contexto.llm.llamadas[-1][1]
    assert prompt.index("########## CONTEXTO DE LA AUDITORÍA ##########") < prompt.index("########## PAPEL DE TRABAJO ##########")
    assert "Motivo: revisar compras." in prompt and "6 de los 45 pedidos" in prompt
    assert "NO generan conclusiones" in prompt
    assert "design_thinking.md [contexto, texto]" in salida and "papel_trabajo_compras.md [papeles_trabajo, texto]" in salida


def test_redactar_contexto_sin_contexto_avisa(contexto):
    contexto.llm.respuestas["redactar-contexto"] = ContextoInforme(introduccion="I", resumen_ejecutivo="R", evaluacion_global="Razonable")
    salida = accion_redactar_contexto(contexto)
    assert "0 documento(s) de contexto y 1 papel(es) de trabajo" in salida and "Sin documentos en contexto/" in salida


def test_extraer_exige_papeles_de_trabajo(contexto):
    for f in (contexto.exp.ruta / "papeles_trabajo").iterdir():
        f.unlink()
    (contexto.exp.ruta / "contexto" / "dt.md").write_text("solo contexto", encoding="utf-8")
    with pytest.raises(ExpedienteError, match="papeles_trabajo"):
        accion_extraer(contexto)


def test_estado_distingue_carpetas(expediente_tmp):
    e = estado_expediente(expediente_tmp)
    assert e["papeles"] == ["papel_trabajo_compras.md"] and e["contexto"] == []
    for f in (expediente_tmp.ruta / "papeles_trabajo").iterdir():
        f.unlink()
    e = estado_expediente(expediente_tmp)
    assert e["fase"].startswith("0") and "papeles_trabajo" in e["siguiente"] and "contexto" in e["siguiente"]


def test_presupuesto_reparte_entre_documentos_y_prioriza_papeles():
    from audit_agent import acciones
    from audit_agent.lectores import Documento
    docs = [Documento("dt.pptx", "pptx", "c" * 200_000, [], "contexto"),
            Documento("2.11.xlsx", "xlsx", "a" * 400_000, [], "papeles_trabajo"),
            Documento("6.2.xlsx", "xlsx", "b" * 20_000, [], "papeles_trabajo")]
    cupo = acciones._presupuesto(docs)
    assert cupo[2] == 20_000                                   # el pequeño entra entero
    assert cupo[1] == acciones.MAX_CHARS_DOCUMENTO            # el grande, a su tope
    assert cupo[0] == acciones.MAX_CHARS_ENTRADA - 20_000 - acciones.MAX_CHARS_DOCUMENTO  # el contexto, con el resto
    assert sum(cupo.values()) <= acciones.MAX_CHARS_ENTRADA
    texto = acciones._texto_entrada(docs)
    assert texto.count("[... documento recortado") == 2 and "bbbb" in texto
    assert texto.index("===== DOCUMENTO: 2.11.xlsx") < texto.index("===== DOCUMENTO: 6.2.xlsx")
    avisos = acciones._avisos_entrada(docs)
    assert len(avisos) == 2 and avisos[1].startswith("⚠ 2.11.xlsx: enviado recortado (150.000 de 400.000")


def test_extraer_avisa_de_pruebas_sin_cubrir(contexto):
    from audit_agent.esquemas import ConclusionExtraida
    pt = contexto.exp.ruta / "papeles_trabajo"
    (pt / "6.2_recalculo.md").write_text("6.2. REVISIÓN DEL CÁLCULO DEL COSTE PARA LOS ARRASTRES\n\nCONTEXTO\nTexto.\n\nCONCLUSIONES\nCon incidencias.\n", encoding="utf-8")
    (pt / "2.11_tarifas.md").write_text("2.11. PROCESO DE ACTUALIZACIÓN DE TARIFARIOS\n\nCONCLUSIONES\nCon incidencias.\n", encoding="utf-8")
    contexto.llm.respuestas["extraer"] = ExtraccionConclusiones(conclusiones=[ConclusionExtraida(
        titulo="Mantenimiento manual", prueba="2.11 PROCESO DE ACTUALIZACIÓN DE TARIFARIOS", incidencia="I", causa_raiz="C",
        como_se_ha_llegado="- d", consecuencias="K", nivel_riesgo="Medio", riesgo_soportado_por_evidencia=False)])
    salida = accion_extraer(contexto)
    assert "no ha cubierto" in salida and "6.2 REVISIÓN DEL CÁLCULO" in salida and "2.11" not in salida.split("no ha cubierto")[1].split("\n")[0].replace("2.11 PROCESO", "")
    assert "cada fichero de PAPEL DE TRABAJO suele ser una prueba distinta" in contexto.llm.llamadas[-1][1]
