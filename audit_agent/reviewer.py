"""
Revisión de un texto suelto (fuera de expediente): p. ej. una conclusión
copiada de Pentana. Reglas deterministas -> reescritura dirigida por LLM ->
verificación con las mismas reglas. La persona ve original + hallazgos +
propuesta y decide.
"""
from __future__ import annotations

from pathlib import Path

from .esquemas import TextoLibre
from .llm import ClienteLLM
from .style_checker import StyleChecker, reglas_como_texto

SYSTEM_REVISOR = """Eres un revisor experto de informes de auditoría interna.
Reescribes textos de conclusiones e incidencias para que cumplan el estilo corporativo:
- Impersonal ("se ha observado", "se recomienda"), sin primera persona.
- Orientado a proceso, nunca a personas: sin culpabilizar.
- Objetivo y soportado por evidencia: sin absolutos ni juicios de valor.
- La severidad se expresa solo mediante el nivel de riesgo (Alto/Medio/Bajo).
- Frases cortas y claras. Terminología: "incidencia", "conclusión", "debilidad", "recomendación".
- Conserva TODOS los datos objetivos (cifras, fechas, muestras, referencias): no inventes ni elimines hechos.

{reglas}"""


class AgenteRevisor:
    def __init__(self, ruta_config: str | Path, modelo: str | None = None, llm: ClienteLLM | None = None):
        self.checker = StyleChecker(ruta_config)
        self.llm = llm or ClienteLLM(modelo)
        self.system = SYSTEM_REVISOR.format(reglas=reglas_como_texto(self.checker))

    def revisar(self, texto: str, reescribir: bool = True) -> dict:
        diagnostico = self.checker.revisar_texto(texto)
        salida = {"original": texto, "limpio": diagnostico.limpio,
                  "hallazgos": diagnostico.to_dict()["hallazgos"],
                  "propuesta": None, "propuesta_verificada": None}
        if reescribir and not diagnostico.limpio and not self.llm.dry_run:
            hallazgos_txt = "\n".join(f"- «{h.fragmento}»: {h.mensaje} Sugerencia: {h.sugerencia}"
                                      for h in diagnostico.hallazgos)
            user = ("Reescribe el siguiente texto corrigiendo exactamente estas infracciones detectadas "
                    f"por el validador de estilo:\n{hallazgos_txt}\n\nTEXTO ORIGINAL:\n{texto}")
            propuesta = self.llm.completar_estructurado("revisar-texto", self.system, user, TextoLibre,
                                                        esfuerzo="low").texto
            salida["propuesta"] = propuesta
            verif = self.checker.revisar_texto(propuesta)
            salida["propuesta_verificada"] = verif.limpio
            if not verif.limpio:
                salida["hallazgos_propuesta"] = verif.to_dict()["hallazgos"]
        return salida
