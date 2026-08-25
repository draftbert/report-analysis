"""
Generador del Resumen Ejecutivo en PowerPoint (python-pptx).

Sigue la estructura de la plantilla descrita en el procedimiento:
  1. Carátula (proyecto, distribución, fecha, referencia, confidencialidad)
  2. Objetivo y alcance
  3. Principales magnitudes / contexto
  4. Principales observaciones (índice)
  5..N. Detalle de cada observación (riesgo, descripción, recomendación, responsable)
  N+1. Evaluación global
  N+2. Próximos pasos

NOTA para producción: lo ideal es partir de la .potx corporativa real y
rellenarla (python-pptx puede abrir la plantilla con Presentation("plantilla.pptx")
y este mismo código funciona sobre ella). Este módulo genera un diseño sobrio
autónomo para el piloto.

Aviso python-pptx: nunca asignar text_frame.text sobre texto ya formateado de
una plantilla (colapsa el formato); asignar run.text en su lugar.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# Paleta sobria
INK = RGBColor(0x1A, 0x1A, 0x1A)
GRIS = RGBColor(0x6B, 0x6B, 0x6B)
BLANCO = RGBColor(0xFF, 0xFF, 0xFF)
COLOR_RIESGO = {
    "Alto": RGBColor(0xB3, 0x26, 0x1E),
    "Medio": RGBColor(0xC7, 0x77, 0x00),
    "Bajo": RGBColor(0x2E, 0x7D, 0x32),
}

ANCHO, ALTO = Inches(13.333), Inches(7.5)


def _caja(slide, x, y, w, h, texto, tam=14, negrita=False, color=INK,
          alineacion=PP_ALIGN.LEFT, interlineado=None):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    lineas = texto.split("\n")
    for i, linea in enumerate(lineas):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = alineacion
        if interlineado:
            p.space_after = Pt(interlineado)
        r = p.add_run()
        r.text = linea
        r.font.size = Pt(tam)
        r.font.bold = negrita
        r.font.color.rgb = color
        r.font.name = "Calibri"
    return tb


class ConstructorResumenEjecutivo:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width = ANCHO
        self.prs.slide_height = ALTO
        self._blank = self.prs.slide_layouts[6]

    def _nueva(self):
        return self.prs.slides.add_slide(self._blank)

    # ------------------------------------------------------- 1. Carátula
    def caratula(self, proyecto: str, referencia: str, fecha: str,
                 distribucion: list[str]):
        s = self._nueva()
        fondo = s.shapes.add_shape(1, 0, 0, ANCHO, ALTO)  # rectángulo
        fondo.fill.solid()
        fondo.fill.fore_color.rgb = RGBColor(0x12, 0x2A, 0x3F)
        fondo.line.fill.background()

        _caja(s, Inches(0.9), Inches(2.2), Inches(11.5), Inches(1.6),
              proyecto, tam=40, negrita=True, color=BLANCO)
        _caja(s, Inches(0.9), Inches(3.9), Inches(11.5), Inches(0.5),
              "Resumen Ejecutivo — Auditoría Interna", tam=18, color=RGBColor(0xB8, 0xC7, 0xD4))
        _caja(s, Inches(0.9), Inches(5.6), Inches(7.0), Inches(1.4),
              f"Referencia: {referencia}\n{fecha}\nDistribución: {', '.join(distribucion)}",
              tam=12, color=RGBColor(0xB8, 0xC7, 0xD4), interlineado=4)
        _caja(s, Inches(0.9), Inches(6.9), Inches(11.5), Inches(0.4),
              "CONFIDENCIAL — Uso interno", tam=10, color=RGBColor(0x8A, 0x9B, 0xAA))

    # -------------------------------------------- 2. Objetivo y alcance
    def objetivo_alcance(self, objetivo: str, alcance: str):
        s = self._nueva()
        _caja(s, Inches(0.7), Inches(0.5), Inches(11.9), Inches(0.7),
              "Objetivo y alcance", tam=28, negrita=True)
        _caja(s, Inches(0.7), Inches(1.6), Inches(11.9), Inches(0.4),
              "Objetivo", tam=15, negrita=True, color=GRIS)
        _caja(s, Inches(0.7), Inches(2.1), Inches(11.9), Inches(1.6), objetivo, tam=14)
        _caja(s, Inches(0.7), Inches(3.9), Inches(11.9), Inches(0.4),
              "Alcance", tam=15, negrita=True, color=GRIS)
        _caja(s, Inches(0.7), Inches(4.4), Inches(11.9), Inches(2.4), alcance, tam=14)

    # ------------------------------------- 3. Magnitudes / contexto
    def contexto(self, texto: str, magnitudes: list[tuple[str, str]] | None = None):
        s = self._nueva()
        _caja(s, Inches(0.7), Inches(0.5), Inches(11.9), Inches(0.7),
              "Principales magnitudes y contexto", tam=28, negrita=True)
        if magnitudes:
            n = len(magnitudes)
            w = Inches(11.9 / max(n, 1))
            for i, (valor, etiqueta) in enumerate(magnitudes):
                x = Inches(0.7) + i * w
                _caja(s, x, Inches(1.7), w - Inches(0.3), Inches(0.8),
                      valor, tam=32, negrita=True, alineacion=PP_ALIGN.CENTER)
                _caja(s, x, Inches(2.5), w - Inches(0.3), Inches(0.6),
                      etiqueta, tam=12, color=GRIS, alineacion=PP_ALIGN.CENTER)
        _caja(s, Inches(0.7), Inches(3.5), Inches(11.9), Inches(3.4), texto, tam=14)

    # ------------------------------- 4. Índice de observaciones
    def indice_observaciones(self, observaciones: list[dict]):
        s = self._nueva()
        _caja(s, Inches(0.7), Inches(0.5), Inches(11.9), Inches(0.7),
              "Principales observaciones", tam=28, negrita=True)
        y = Inches(1.7)
        for i, obs in enumerate(observaciones, 1):
            nivel = str(obs.get("nivel_riesgo", "")).capitalize()
            chip = s.shapes.add_shape(1, Inches(0.7), y, Inches(1.0), Inches(0.45))
            chip.fill.solid()
            chip.fill.fore_color.rgb = COLOR_RIESGO.get(nivel, GRIS)
            chip.line.fill.background()
            tf = chip.text_frame
            tf.word_wrap = False
            r = tf.paragraphs[0].add_run()
            tf.paragraphs[0].alignment = PP_ALIGN.CENTER
            r.text = nivel or "N/D"
            r.font.size = Pt(11)
            r.font.bold = True
            r.font.color.rgb = BLANCO
            _caja(s, Inches(1.9), y, Inches(10.6), Inches(0.5),
                  f"{i}. {obs.get('titulo', '(sin título)')}", tam=15)
            y += Inches(0.65)

    # --------------------------------- 5. Detalle de observación
    def detalle_observacion(self, num: int, obs: dict):
        s = self._nueva()
        nivel = str(obs.get("nivel_riesgo", "")).capitalize()
        _caja(s, Inches(0.7), Inches(0.5), Inches(9.8), Inches(1.0),
              f"Observación {num}: {obs.get('titulo', '')}", tam=22, negrita=True)
        chip = s.shapes.add_shape(1, Inches(10.9), Inches(0.55), Inches(1.7), Inches(0.5))
        chip.fill.solid()
        chip.fill.fore_color.rgb = COLOR_RIESGO.get(nivel, GRIS)
        chip.line.fill.background()
        p = chip.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = f"Riesgo {nivel}" if nivel else "Riesgo N/D"
        r.font.size = Pt(12); r.font.bold = True; r.font.color.rgb = BLANCO

        bloques = [
            ("Descripción", f"{obs.get('condicion', '')}\nCriterio: {obs.get('criterio', '')}".strip()),
            ("Causa raíz", obs.get("causa_raiz", "")),
            ("Efecto / riesgo", obs.get("efecto", "")),
            ("Recomendación", obs.get("recomendacion", "")),
        ]
        y = Inches(1.75)
        alturas = [Inches(1.5), Inches(1.0), Inches(0.95), Inches(1.15)]
        for (titulo, cuerpo), h in zip(bloques, alturas):
            _caja(s, Inches(0.7), y, Inches(2.4), Inches(0.4),
                  titulo, tam=13, negrita=True, color=GRIS)
            _caja(s, Inches(3.2), y, Inches(9.4), h, cuerpo, tam=12.5)
            y += h + Inches(0.12)
        _caja(s, Inches(0.7), Inches(6.95), Inches(11.9), Inches(0.4),
              f"Responsable del plan de acción: {obs.get('responsable', 'Pendiente de asignar')}",
              tam=12, negrita=True)

    # ------------------------------------------ Evaluación global
    def evaluacion_global(self, gobierno: str, gestion_riesgos: str,
                          entorno_control: str, conclusion: str, n_observaciones: int):
        s = self._nueva()
        _caja(s, Inches(0.7), Inches(0.5), Inches(11.9), Inches(0.7),
              "Evaluación global", tam=28, negrita=True)
        filas = [("Gobierno", gobierno),
                 ("Gestión de riesgos", gestion_riesgos),
                 ("Entorno de control", entorno_control)]
        y = Inches(1.7)
        for etiqueta, valor in filas:
            _caja(s, Inches(0.7), y, Inches(4.2), Inches(0.5), etiqueta, tam=15, negrita=True)
            _caja(s, Inches(5.1), y, Inches(7.5), Inches(0.5), valor, tam=15)
            y += Inches(0.65)
        _caja(s, Inches(0.7), y + Inches(0.2), Inches(11.9), Inches(0.5),
              f"Observaciones emitidas: {n_observaciones}", tam=14, color=GRIS)
        _caja(s, Inches(0.7), y + Inches(0.9), Inches(11.9), Inches(2.4), conclusion, tam=13.5)

    # -------------------------------------------- Próximos pasos
    def proximos_pasos(self, texto: str):
        s = self._nueva()
        _caja(s, Inches(0.7), Inches(0.5), Inches(11.9), Inches(0.7),
              "Próximos pasos", tam=28, negrita=True)
        _caja(s, Inches(0.7), Inches(1.7), Inches(11.9), Inches(4.8), texto, tam=14)
        _caja(s, Inches(0.7), Inches(6.8), Inches(11.9), Inches(0.4),
              "El plan de acción detallado con plazos se recoge en el Anexo.",
              tam=11, color=GRIS)

    # ----------------------------------------------------------------
    def guardar(self, ruta: str | Path) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(str(ruta))
        return ruta


def construir_desde_datos(datos: dict, ruta_salida: str | Path) -> Path:
    """Construye el PPT completo desde un dict (ver ejemplos/informe.json)."""
    c = ConstructorResumenEjecutivo()
    p = datos["proyecto"]
    c.caratula(p["nombre"], p["referencia"], p["fecha"], p["distribucion"])
    c.objetivo_alcance(datos["objetivo"], datos["alcance"])
    ctx = datos.get("contexto", {})
    c.contexto(ctx.get("texto", ""), [tuple(m) for m in ctx.get("magnitudes", [])])
    obs = datos.get("observaciones", [])
    c.indice_observaciones(obs)
    for i, o in enumerate(obs, 1):
        c.detalle_observacion(i, o)
    ev = datos.get("evaluacion_global", {})
    c.evaluacion_global(ev.get("gobierno", ""), ev.get("gestion_riesgos", ""),
                        ev.get("entorno_control", ""), ev.get("conclusion", ""),
                        len(obs))
    c.proximos_pasos(datos.get("proximos_pasos", ""))
    return c.guardar(ruta_salida)
