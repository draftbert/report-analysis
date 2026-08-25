"""
Suite de casos adversarios de sustitución textual en `aplicar-cambios`.

Origen: en el primer uso real contra KAIA, el Gerente pidió cambiar el riesgo y
el responsable de la observación 3, y como las líneas `- Responsable: …` son
idénticas en todas las observaciones, el cambio se aplicó en la observación 1.
Este fichero es el activo de ese bug: cada caso raro que aparezca en uso real
(ficheros con estructura repetitiva, instrucciones ambiguas o contradictorias)
se añade aquí como test determinista ANTES de corregirlo. Sin LLM: se mockea
la salida del modelo (PlanCambios) y se prueba solo la lógica de aplicación.

Comportamiento definido:
- La sustitución se acota a la sección (`##`/`###`) que indica el modelo; si la
  sección lleva número, solo casan cabeceras con ese número.
- Sección indicada inexistente -> NO APLICADO (no se busca en todo el documento).
- Fragmento inexistente -> NO APLICADO; solo se admite aproximación por
  diferencias mínimas (tildes/espacios), nunca por parecido general.
- Fragmento repetido en el ámbito de búsqueda -> NO APLICADO por ambiguo.
- Cambios contradictorios sobre el mismo fragmento -> se aplican en orden; el
  segundo queda como CONFLICTO con referencia al primero, nunca pisa en silencio.
"""
from __future__ import annotations

from audit_agent.acciones import aplicar_plan
from audit_agent.esquemas import Cambio, PlanCambios
from audit_agent.formato_md import parsear_informe


def _obs(n, titulo, nivel="Medio", resp="Dirección de Compras", causa="Control manual."):
    return f"""### {n}. {titulo}

- Nivel de riesgo: {nivel}
- Responsable: {resp}

**Condición:** En la muestra analizada se identificaron incidencias.

**Criterio:** Política de Compras.

**Causa raíz:** {causa}

**Efecto:** Riesgo de gasto sin control.

**Recomendación:** Implantar un control automático en el sistema.
"""


INFORME = f"""# Resumen Ejecutivo — Prueba

## Objetivo

Evaluar el proceso de compras.

## Alcance

Pedidos de enero a marzo. Se recomienda revisar el alcance en próximos trabajos.

## Principales observaciones

{_obs(1, "Ausencia de ofertas comparativas")}
{_obs(2, "Falta de segregación de funciones")}
{_obs(3, "Falta de segregación de funciones", resp="Dirección de Sistemas")}
## Evaluación global

- Gobierno: Razonable — Impacto Bajo

Se recomienda revisar el alcance en próximos trabajos. Conclusión final.

## Próximos pasos

Seguimiento en 2027.
"""


def _cambio(seccion, original, nuevo, motivo="m", insertar_tras=""):
    return Cambio(seccion=seccion, motivo=motivo, texto_original=original, texto_nuevo=nuevo, insertar_tras=insertar_tras)


def _obs_dict(texto):
    return {o["numero"]: o for o in parsear_informe(texto)["observaciones"]}


# 1. Dos observaciones con el mismo título exacto: el número de la cabecera decide
def test_mismo_titulo_distinto_numero():
    plan = PlanCambios(cambios=[_cambio("### 3. Falta de segregación de funciones", "- Nivel de riesgo: Medio", "- Nivel de riesgo: Alto")], pendientes=[])
    nuevo, filas = aplicar_plan(INFORME, plan)
    assert filas[0]["estado"] == "aplicado"
    obs = _obs_dict(nuevo)
    assert obs[3]["nivel_riesgo"] == "Alto" and obs[2]["nivel_riesgo"] == "Medio" and obs[1]["nivel_riesgo"] == "Medio"

    plan = PlanCambios(cambios=[_cambio("### 2. Falta de segregación de funciones", "- Nivel de riesgo: Medio", "- Nivel de riesgo: Bajo")], pendientes=[])
    nuevo, filas = aplicar_plan(INFORME, plan)
    assert filas[0]["estado"] == "aplicado" and _obs_dict(nuevo)[2]["nivel_riesgo"] == "Bajo"
    assert _obs_dict(nuevo)[3]["nivel_riesgo"] == "Medio"


# 2. El texto a sustituir aparece en dos secciones distintas
def test_texto_en_dos_secciones_con_seccion_indicada():
    frase = "Se recomienda revisar el alcance en próximos trabajos."
    plan = PlanCambios(cambios=[_cambio("## Evaluación global", frase, "Se recomienda ampliar el alcance.")], pendientes=[])
    nuevo, filas = aplicar_plan(INFORME, plan)
    assert filas[0]["estado"] == "aplicado"
    datos = parsear_informe(nuevo)
    assert "ampliar" in datos["evaluacion_global"]["conclusion"]
    assert frase in datos["alcance"]  # la otra sección queda intacta


def test_texto_en_dos_secciones_sin_seccion_es_ambiguo():
    frase = "Se recomienda revisar el alcance en próximos trabajos."
    plan = PlanCambios(cambios=[_cambio("", frase, "X")], pendientes=[])
    nuevo, filas = aplicar_plan(INFORME, plan)
    assert filas[0]["estado"] == "NO APLICADO" and "ambiguo" in filas[0]["detalle"] and "2 veces" in filas[0]["detalle"]
    assert nuevo == INFORME


# 3. Una instrucción que afecta a dos secciones: el modelo devuelve dos cambios
def test_dos_cambios_cada_uno_en_su_seccion():
    plan = PlanCambios(cambios=[
        _cambio("### 1. Ausencia de ofertas comparativas", "- Responsable: Dirección de Compras", "- Responsable: Dirección Financiera"),
        _cambio("### 2. Falta de segregación de funciones", "- Responsable: Dirección de Compras", "- Responsable: Dirección de Sistemas"),
    ], pendientes=[])
    nuevo, filas = aplicar_plan(INFORME, plan)
    assert [f["estado"] for f in filas] == ["aplicado", "aplicado"]
    obs = _obs_dict(nuevo)
    assert obs[1]["responsable"] == "Dirección Financiera"
    assert obs[2]["responsable"] == "Dirección de Sistemas"
    assert obs[3]["responsable"] == "Dirección de Sistemas"  # no tocada (ya lo era)


# 4. Texto inexistente: NO APLICADO, nunca aproximación por parecido general
def test_texto_inexistente_no_se_aproxima():
    plan = PlanCambios(cambios=[
        _cambio("### 1. Ausencia de ofertas comparativas", "**Causa raíz:** Control manual y falta de formación del personal.", "**Causa raíz:** X"),
        _cambio("## Próximos pasos", "Seguimiento en 2028.", "Seguimiento en 2029."),
        _cambio("## Objetivo", "Evaluar el proceso de ventas.", "Evaluar el proceso de tesorería."),
    ], pendientes=[])
    nuevo, filas = aplicar_plan(INFORME, plan)
    assert all(f["estado"] == "NO APLICADO" for f in filas), filas
    assert all("no encontrado" in f["detalle"] for f in filas), filas
    assert nuevo == INFORME


def test_diferencias_minimas_si_se_aproximan():
    # Solo tildes/espacios: el modelo copió "Politica" sin tilde
    plan = PlanCambios(cambios=[_cambio("### 1. Ausencia de ofertas comparativas", "**Criterio:** Politica de Compras.", "**Criterio:** Política de Compras v4.2.")], pendientes=[])
    nuevo, filas = aplicar_plan(INFORME, plan)
    assert filas[0]["estado"] == "aplicado (coincidencia aproximada)"
    assert _obs_dict(nuevo)[1]["criterio"] == "Política de Compras v4.2."


# 5. Texto repetido DENTRO de la misma sección: ambiguo, con motivo claro
def test_repetido_en_la_misma_seccion():
    texto = INFORME.replace("Seguimiento en 2027.", "Seguimiento en 2027. Se comunicará al área. Seguimiento en 2027.")
    plan = PlanCambios(cambios=[_cambio("## Próximos pasos", "Seguimiento en 2027.", "Seguimiento en T1 2027.")], pendientes=[])
    nuevo, filas = aplicar_plan(texto, plan)
    assert filas[0]["estado"] == "NO APLICADO"
    assert "ambiguo" in filas[0]["detalle"] and "2 veces" in filas[0]["detalle"] and "Próximos pasos" in filas[0]["detalle"]
    assert nuevo == texto


# 6. Instrucciones contradictorias: se aplican en orden y la segunda queda en CONFLICTO
def test_instrucciones_contradictorias():
    """Comportamiento definido: el primer cambio se aplica; el segundo, que
    apunta al mismo fragmento original (ya modificado), NO se aplica y se marca
    CONFLICTO citando el cambio que lo modificó, para que el auditor decida."""
    plan = PlanCambios(cambios=[
        _cambio("### 1. Ausencia de ofertas comparativas", "- Nivel de riesgo: Medio", "- Nivel de riesgo: Alto", motivo="Gerente: Alto"),
        _cambio("### 1. Ausencia de ofertas comparativas", "- Nivel de riesgo: Medio", "- Nivel de riesgo: Bajo", motivo="Directora: Bajo"),
    ], pendientes=[])
    nuevo, filas = aplicar_plan(INFORME, plan)
    assert filas[0]["estado"] == "aplicado"
    assert filas[1]["estado"] == "CONFLICTO" and "cambio 1" in filas[1]["detalle"]
    assert _obs_dict(nuevo)[1]["nivel_riesgo"] == "Alto"


def test_cambios_encadenados_no_son_conflicto():
    """Dos cambios distintos en la misma sección (fragmentos diferentes) no
    interfieren aunque el segundo se localice sobre el texto ya modificado."""
    plan = PlanCambios(cambios=[
        _cambio("## Próximos pasos", "Seguimiento en 2027.", "Seguimiento en el primer trimestre de 2027."),
        _cambio("## Próximos pasos", "", "Se informará al Comité de Auditoría.", insertar_tras="Seguimiento en el primer trimestre de 2027."),
    ], pendientes=[])
    nuevo, filas = aplicar_plan(INFORME, plan)
    assert [f["estado"] for f in filas] == ["aplicado", "insertado"]
    assert "Comité de Auditoría" in parsear_informe(nuevo)["proximos_pasos"]


# 7. Sección indicada por el modelo que no existe
def test_seccion_inexistente():
    plan = PlanCambios(cambios=[
        _cambio("### 4. Observación fantasma", "- Nivel de riesgo: Medio", "- Nivel de riesgo: Alto"),
        _cambio("## Anexos", "Seguimiento en 2027.", "X"),
    ], pendientes=[])
    nuevo, filas = aplicar_plan(INFORME, plan)
    assert all(f["estado"] == "NO APLICADO" and "no encontrada" in f["detalle"] for f in filas), filas
    assert nuevo == INFORME


# Caso original del bug (regresión)
def test_regresion_lineas_identicas_entre_observaciones():
    plan = PlanCambios(cambios=[
        _cambio("### 3. Falta de segregación de funciones", "- Responsable: Dirección de Sistemas", "- Responsable: Dirección de Sistemas y RRHH"),
        _cambio("### 2. Falta de segregación de funciones", "- Responsable: Dirección de Compras", "- Responsable: Dirección de Personas"),
    ], pendientes=[])
    nuevo, filas = aplicar_plan(INFORME, plan)
    assert [f["estado"] for f in filas] == ["aplicado", "aplicado"]
    obs = _obs_dict(nuevo)
    assert obs[1]["responsable"] == "Dirección de Compras"
    assert obs[2]["responsable"] == "Dirección de Personas"
    assert obs[3]["responsable"] == "Dirección de Sistemas y RRHH"


def test_eliminacion():
    plan = PlanCambios(cambios=[_cambio("## Alcance", "Se recomienda revisar el alcance en próximos trabajos.", "")], pendientes=[])
    nuevo, filas = aplicar_plan(INFORME, plan)
    assert filas[0]["estado"] == "eliminado"
    assert parsear_informe(nuevo)["alcance"] == "Pedidos de enero a marzo."

