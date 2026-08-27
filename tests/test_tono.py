"""Tono y lenguaje (sección `tono` de estilo.yaml): avisos deterministas en el checker
(nunca errores), texto inyectado en los prompts y `corregir --avisos` que los pasa al
modelo con la instrucción de evaluar el contexto."""
from __future__ import annotations

from pathlib import Path

from audit_agent.acciones import accion_corregir
from audit_agent.esquemas import Correcciones, ParrafoCorregido
from audit_agent.style_checker import StyleChecker, reglas_como_texto, tono_como_texto

CONFIG = Path(__file__).resolve().parent.parent / "config" / "estilo.yaml"


def test_expresiones_y_adjetivos_son_avisos_no_errores():
    c = StyleChecker(CONFIG)
    r = c.revisar_texto("No existe un proceso de revisión y hay una falta de control clara con debilidades significativas, "
                        "y no se dispone de evidencia; el control es inadecuado.")
    tipos = [(h.tipo, h.fragmento.lower()) for h in r.hallazgos]
    assert ("tono", "no existe") in tipos and ("tono", "falta de") in tipos and ("tono", "no se dispone de") in tipos and ("tono", "inadecuado") in tipos
    assert ("adjetivo", "clara") in tipos and ("adjetivo", "significativas") in tipos
    assert all(h.severidad == "aviso" for h in r.hallazgos if h.tipo in ("tono", "adjetivo")) and r.limpio
    assert any("oportunidades de mejora" in h.sugerencia for h in r.hallazgos if h.fragmento.lower() == "no existe")
    # una fórmula constructiva no dispara nada
    assert not StyleChecker(CONFIG).revisar_texto("Se han observado oportunidades de mejora en el proceso de revisión.").hallazgos


def test_tono_en_los_prompts():
    c = StyleChecker(CONFIG)
    t = tono_como_texto(c)
    assert t.startswith("TONO Y LENGUAJE:") and "No apliques las sustituciones de forma automática" in t
    assert "«falta de»" in t and "«se han identificado oportunidades de mejora en…»" in t
    assert "permitiría reforzar la mitigación" in t and "Tiempos verbales:" in t and "«clara»" in t
    assert t in reglas_como_texto(c)


def test_corregir_pasa_los_avisos_de_tono_solo_con_avisos(contexto):
    exp = contexto.exp
    exp.escribir("informe", "# Informe\n\n## Introducción\n\nNo existe un proceso de revisión de tarifas.\n\n## Resumen ejecutivo\n\nR.\n", "test")
    contexto.llm.respuestas["corregir"] = Correcciones(parrafos=[ParrafoCorregido(id=1, texto="Se han observado oportunidades de mejora en el proceso de revisión de tarifas.")])
    assert accion_corregir(contexto).startswith("No hay párrafos que corregir")          # sin --avisos: el tono no es error
    salida = accion_corregir(contexto, incluir_avisos=True)
    assert "Párrafos reescritos: 1 de 1" in salida
    user = contexto.llm.llamadas[-1][1]
    assert "«No existe»" in user and "oportunidades de mejora" in user and "se EVALÚAN según el contexto" in user
    assert "Se han observado oportunidades de mejora en el proceso de revisión de tarifas." in exp.leer("informe")
