"""
Generador de la presentación del informe en PowerPoint (python-pptx).

Estructura del informe de auditoría interna:
  1. Carátula (proyecto, distribución, fecha, referencia, confidencialidad)
  2. Introducción
  3. Resumen ejecutivo
  4. Detalle de conclusiones (índice)
  5..N. Detalle de cada conclusión (incidencia, causa raíz, cómo se ha llegado,
        consecuencias, recomendación, responsable)
  N+1.. Sugerencias de mejora

NOTA para producción: lo ideal es partir de la .potx corporativa real y
rellenarla (python-pptx puede abrir la plantilla con Presentation("plantilla.pptx")
y este mismo código funciona sobre ella). Este módulo genera un diseño sobrio
autónomo para el piloto.

Aviso python-pptx: nunca asignar text_frame.text sobre texto ya formateado de
una plantilla (colapsa el formato); asignar run.text en su lugar.
"""
from __future__ import annotations

import re
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


def _md_plano(texto: str) -> str:
    """Markdown sencillo -> texto para la diapositiva (negritas, viñetas, tablas)."""
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", texto or "")
    t = re.sub(r"^\s*#+\s*", "", t, flags=re.M)
    t = re.sub(r"^\s*[-*]\s+", "• ", t, flags=re.M)
    t = re.sub(r"^\|?\s*-{3,}\s*(\|\s*-{3,}\s*)*\|?\s*$", "", t, flags=re.M)  # separadores de tabla
    t = re.sub(r"^\|\s*(.*?)\s*\|\s*$", lambda m: " · ".join(x.strip() for x in m.group(1).split("|")), t, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _resumir(texto: str, maximo: int) -> str:
    return texto if len(texto) <= maximo else texto[:maximo].rsplit(" ", 1)[0] + " […]"


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
              "Informe de Auditoría Interna", tam=18, color=RGBColor(0xB8, 0xC7, 0xD4))
        _caja(s, Inches(0.9), Inches(5.6), Inches(7.0), Inches(1.4),
              f"Referencia: {referencia}\n{fecha}\nDistribución: {', '.join(distribucion)}",
              tam=12, color=RGBColor(0xB8, 0xC7, 0xD4), interlineado=4)
        _caja(s, Inches(0.9), Inches(6.9), Inches(11.5), Inches(0.4),
              "CONFIDENCIAL — Uso interno", tam=10, color=RGBColor(0x8A, 0x9B, 0xAA))

    # --------------------------------------------- 2/3. Texto largo (introducción, resumen)
    def texto_largo(self, titulo: str, texto: str, tam: float = 13):
        """Una o varias diapositivas con un texto Markdown sencillo (párrafos y viñetas)."""
        parrafos = [p.strip() for p in re.split(r"\n\s*\n", _md_plano(texto)) if p.strip()]
        paginas, actual, largo = [], [], 0
        for par in parrafos:
            if actual and largo + len(par) > 1500:
                paginas.append(actual)
                actual, largo = [], 0
            actual.append(par)
            largo += len(par)
        if actual:
            paginas.append(actual)
        for n, pagina in enumerate(paginas or [[""]], 1):
            s = self._nueva()
            sufijo = f" ({n}/{len(paginas)})" if len(paginas) > 1 else ""
            _caja(s, Inches(0.7), Inches(0.5), Inches(11.9), Inches(0.7), titulo + sufijo, tam=28, negrita=True)
            _caja(s, Inches(0.7), Inches(1.5), Inches(11.9), Inches(5.6), "\n\n".join(pagina), tam=tam, interlineado=6)

    # ------------------------------- 4. Índice de conclusiones
    def indice_conclusiones(self, conclusiones: list[dict], titulo: str = "Detalle de conclusiones"):
        s = self._nueva()
        _caja(s, Inches(0.7), Inches(0.5), Inches(11.9), Inches(0.7), titulo, tam=28, negrita=True)
        y = Inches(1.7)
        for i, c in enumerate(conclusiones, 1):
            nivel = str(c.get("nivel_riesgo", "")).capitalize()
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
                  f"{i}. {c.get('titulo', '(sin título)')}" + (f"  ·  {c['prueba']}" if c.get("prueba") else ""), tam=14)
            y += Inches(0.6)

    # --------------------------------- 5. Detalle de conclusión / sugerencia
    def detalle_conclusion(self, num: int, c: dict, es_sugerencia: bool = False):
        s = self._nueva()
        nivel = str(c.get("nivel_riesgo", "")).capitalize()
        prefijo = "Sugerencia de mejora" if es_sugerencia else "Conclusión"
        _caja(s, Inches(0.7), Inches(0.4), Inches(9.8), Inches(0.9),
              f"{prefijo} {num}: {c.get('titulo', '')}", tam=20, negrita=True)
        if not es_sugerencia:
            chip = s.shapes.add_shape(1, Inches(10.9), Inches(0.45), Inches(1.7), Inches(0.5))
            chip.fill.solid()
            chip.fill.fore_color.rgb = COLOR_RIESGO.get(nivel, GRIS)
            chip.line.fill.background()
            p = chip.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = f"Riesgo {nivel}" if nivel else "Riesgo N/D"
            r.font.size = Pt(12); r.font.bold = True; r.font.color.rgb = BLANCO
        if c.get("prueba"):
            _caja(s, Inches(0.7), Inches(1.25), Inches(11.9), Inches(0.35), f"Prueba: {c['prueba']}", tam=11, color=GRIS)
        bloques = [
            ("Incidencia detectada", c.get("incidencia", "")),
            ("Causa raíz", c.get("causa_raiz", "")),
            ("Cómo se ha llegado", _resumir(_md_plano(c.get("como_se_ha_llegado", "")), 600)),
            ("Consecuencias", c.get("consecuencias", "")),
            ("Propuesta de mejora" if es_sugerencia else "Recomendación", c.get("recomendacion", "")),
        ]
        y = Inches(1.65)
        alturas = [Inches(1.05), Inches(0.8), Inches(1.25), Inches(0.8), Inches(1.0)]
        for (titulo, cuerpo), h in zip(bloques, alturas):
            _caja(s, Inches(0.7), y, Inches(2.4), Inches(0.4), titulo, tam=12, negrita=True, color=GRIS)
            _caja(s, Inches(3.2), y, Inches(9.4), h, _md_plano(cuerpo), tam=11)
            y += h + Inches(0.08)
        if not es_sugerencia:
            _caja(s, Inches(0.7), Inches(6.95), Inches(11.9), Inches(0.4),
                  f"Responsable del plan de acción: {c.get('responsable') or 'Pendiente de asignar'}",
                  tam=12, negrita=True)

    # ----------------------------------------------------------------
    def guardar(self, ruta: str | Path) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(str(ruta))
        return ruta


def construir_desde_datos(datos: dict, ruta_salida: str | Path) -> Path:
    """Construye la presentación completa desde el dict de formato_md.parsear_informe
    (+ `proyecto`): introduccion, resumen_ejecutivo, conclusiones, sugerencias."""
    c = ConstructorResumenEjecutivo()
    p = datos["proyecto"]
    c.caratula(p["nombre"], p["referencia"], p["fecha"], p.get("distribucion", []))
    c.texto_largo("Introducción", datos.get("introduccion", ""))
    c.texto_largo("Resumen ejecutivo", datos.get("resumen_ejecutivo", ""))
    conclusiones = datos.get("conclusiones", [])
    sugerencias = datos.get("sugerencias", [])
    if conclusiones:
        c.indice_conclusiones(conclusiones)
        for i, x in enumerate(conclusiones, 1):
            c.detalle_conclusion(i, x)
    if sugerencias:
        c.indice_conclusiones(sugerencias, titulo="Sugerencias de mejora")
        for i, x in enumerate(sugerencias, 1):
            c.detalle_conclusion(i, x, es_sugerencia=True)
    return c.guardar(ruta_salida)
