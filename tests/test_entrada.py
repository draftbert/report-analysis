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
