"""
Revisor determinista de estilo.

Primera línea de defensa: comprobaciones baratas, instantáneas y 100%
reproducibles (importante en auditoría: el mismo texto siempre produce
el mismo resultado). El LLM se reserva para lo que las reglas no cubren.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml


@dataclass
class Hallazgo:
    tipo: str            # "palabra_prohibida" | "primera_persona" | "frase_larga" | "estructura"
    severidad: str       # "error" | "aviso"
    fragmento: str
    posicion: int        # índice del carácter donde empieza (o -1 si no aplica)
    mensaje: str
    sugerencia: str = ""


@dataclass
class ResultadoRevision:
    hallazgos: list[Hallazgo] = field(default_factory=list)

    @property
    def limpio(self) -> bool:
        return not any(h.severidad == "error" for h in self.hallazgos)

    def to_dict(self) -> dict:
        return {"limpio": self.limpio, "hallazgos": [asdict(h) for h in self.hallazgos]}


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para casar 'fallo' con 'Fallo', etc."""
    nfkd = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


class StyleChecker:
    def __init__(self, ruta_config: str | Path):
        with open(ruta_config, encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

    # ------------------------------------------------------------------
    def revisar_texto(self, texto: str) -> ResultadoRevision:
        res = ResultadoRevision()
        norm = _normalizar(texto)

        # 1) Palabras prohibidas (con límites de palabra, insensible a tildes)
        for regla in self.cfg.get("palabras_prohibidas", []):
            patron = r"\b" + re.escape(_normalizar(regla["termino"])) + r"\b"
            for m in re.finditer(patron, norm):
                res.hallazgos.append(Hallazgo(
                    tipo="palabra_prohibida",
                    severidad="error",
                    fragmento=texto[m.start():m.end()],
                    posicion=m.start(),
                    mensaje=regla.get("motivo", "Término no permitido en informes."),
                    sugerencia=regla.get("sugerencia", ""),
                ))

        # 2) Primera persona
        for termino in self.cfg.get("primera_persona", []):
            patron = r"\b" + re.escape(_normalizar(termino)) + r"\b"
            for m in re.finditer(patron, norm):
                res.hallazgos.append(Hallazgo(
                    tipo="primera_persona",
                    severidad="error",
                    fragmento=texto[m.start():m.end()],
                    posicion=m.start(),
                    mensaje="El informe se redacta en impersonal.",
                    sugerencia="Reformular: «se ha observado…», «se recomienda…».",
                ))

        # 3) Frases demasiado largas
        limite = int(self.cfg.get("reglas", {}).get("longitud_maxima_frase", 45))
        for frase in re.split(r"(?<=[.!?])\s+", texto.strip()):
            n = len(frase.split())
            if n > limite:
                res.hallazgos.append(Hallazgo(
                    tipo="frase_larga",
                    severidad="aviso",
                    fragmento=(frase[:80] + "…") if len(frase) > 80 else frase,
                    posicion=texto.find(frase),
                    mensaje=f"Frase de {n} palabras (límite {limite}). Dificulta la lectura.",
                    sugerencia="Dividir en dos o tres frases.",
                ))

        res.hallazgos.sort(key=lambda h: h.posicion)
        return res

    # ------------------------------------------------------------------
    def revisar_conclusion(self, obs: dict) -> ResultadoRevision:
        """Revisa una conclusión estructurada: campos exigidos por
        `estructura_conclusion` (error si `requerido`, aviso si no) + nivel de
        riesgo válido + estilo de cada campo de texto."""
        res = ResultadoRevision()
        for campo in self.cfg.get("estructura_conclusion", []):
            nombre = campo["campo"]
            if not str(obs.get(nombre, "") or "").strip():
                requerido = campo.get("requerido", True)
                res.hallazgos.append(Hallazgo(
                    tipo="estructura", severidad="error" if requerido else "aviso", fragmento=nombre, posicion=-1,
                    mensaje=(f"Falta el campo obligatorio «{nombre}» ({campo['descripcion']})." if requerido
                             else f"Campo «{nombre}» pendiente ({campo['descripcion']})."),
                    sugerencia="Completar antes de volcar al informe." if requerido else "",
                ))

        # Nivel de riesgo válido
        validos = self.cfg.get("reglas", {}).get("niveles_riesgo_validos", [])
        nivel = str(obs.get("nivel_riesgo", "")).strip()
        from .formato_md import separar_coletilla  # import tardío: evita ciclo
        nivel = separar_coletilla(nivel)[0].capitalize()  # «Medio (propuesto por el modelo…)» es válido
        if validos and nivel and nivel not in validos:
            res.hallazgos.append(Hallazgo(
                tipo="estructura", severidad="error", fragmento=nivel, posicion=-1,
                mensaje=f"Nivel de riesgo no válido. Valores permitidos: {', '.join(validos)}.",
            ))

        # Estilo de los campos de texto
        for nombre, valor in obs.items():
            if isinstance(valor, str) and valor.strip() and nombre != "notas":
                for h in self.revisar_texto(valor).hallazgos:
                    h.mensaje = f"[{nombre}] " + h.mensaje
                    res.hallazgos.append(h)
        return res


# ---------------------------------------------------------------------------
# Revisión de documentos Markdown (ficheros del expediente)
# ---------------------------------------------------------------------------
def revisar_markdown(checker: StyleChecker, texto: str) -> list[dict]:
    """Aplica las reglas párrafo a párrafo sobre un Markdown, devolviendo
    hallazgos con nº de línea. Ignora blockquotes (instrucciones al auditor)
    y elimina las marcas Markdown antes de contar palabras."""
    from .formato_md import parrafos_con_lineas  # import tardío: evita ciclo

    hallazgos = []
    for linea, parrafo in parrafos_con_lineas(texto):
        if parrafo.lstrip().startswith("#"):
            continue  # cabeceras: títulos cortos, no prosa
        limpio = re.sub(r"\*\*[^*]+?:\*\*\s*", "", parrafo)   # etiquetas **Campo:**
        limpio = re.sub(r"^\s*[-*]\s+", "", limpio, flags=re.M)  # viñetas
        for h in checker.revisar_texto(limpio).hallazgos:
            d = asdict(h)
            d["linea"] = linea + limpio[:max(h.posicion, 0)].count("\n")
            d["parrafo_linea"] = linea
            hallazgos.append(d)
    return hallazgos


def reglas_como_texto(checker: StyleChecker) -> str:
    """Resumen del criterio de estilo para incluirlo en los prompts, de modo
    que el modelo redacte conforme al YAML desde el primer intento."""
    cfg = checker.cfg
    lineas = ["TÉRMINOS PROHIBIDOS (usar la alternativa indicada):"]
    for r in cfg.get("palabras_prohibidas", []):
        lineas.append(f"- «{r['termino']}» → {r.get('sugerencia', '')} ({r.get('motivo', '')})")
    pp = cfg.get("primera_persona", [])
    if pp:
        lineas.append("PRIMERA PERSONA PROHIBIDA (redacción impersonal): " + ", ".join(pp))
    lim = cfg.get("reglas", {}).get("longitud_maxima_frase")
    if lim:
        lineas.append(f"Frases de como máximo {lim} palabras.")
    niveles = cfg.get("reglas", {}).get("niveles_riesgo_validos", [])
    if niveles:
        lineas.append("Nivel de riesgo: exactamente uno de " + " / ".join(niveles) + ".")
    return "\n".join(lineas)
