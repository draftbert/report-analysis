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
GRIS_BANDA = RGBColor(0xA6, 0xA6, 0xA6)
GRIS_CAJA = RGBColor(0xF2, 0xF2, 0xF2)
GRIS_CLARO = RGBColor(0xD9, 0xD9, 0xD9)
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


def _altura(texto: str, ancho, tam: float):
    """Altura estimada de un texto a `tam` puntos en un cuadro de `ancho` EMU
    (aprox. 0.55·tam puntos por carácter; interlineado 1.25)."""
    chars_por_linea = max(20, int(ancho / Pt(tam * 0.55)))
    lineas = sum(max(1, -(-len(l) // chars_por_linea)) for l in texto.splitlines() or [""])
    return Pt(tam * 1.25) * lineas + Pt(8)


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
        """Reproduce la diapositiva corporativa de «Detalle de conclusiones»:
        banda lateral con el riesgo en vertical, título numerado, cuerpo en
        prosa (incidencia + causa), caja de «detalles descriptivos», párrafo de
        consecuencias y columna derecha con recomendación numerada N.1, N.2…,
        referencia, área, responsable y plazo."""
        s = self._nueva()
        nivel = str(c.get("nivel_riesgo", "")).strip().capitalize()
        _caja(s, Inches(0.7), Inches(0.25), Inches(11.9), Inches(0.8),
              "Sugerencias de mejora" if es_sugerencia else "Detalle de conclusiones", tam=30, color=INK)
        # Línea superior y banda lateral con el riesgo en vertical (letra por línea, como la plantilla)
        linea = s.shapes.add_shape(1, Inches(0.55), Inches(1.15), Inches(12.2), Pt(1.5))
        linea.fill.solid(); linea.fill.fore_color.rgb = GRIS_CLARO; linea.line.fill.background()
        banda = s.shapes.add_shape(1, Inches(0.55), Inches(1.2), Inches(0.32), Inches(5.6))
        banda.fill.solid(); banda.fill.fore_color.rgb = GRIS_BANDA; banda.line.fill.background()
        etiqueta = "SUGERENCIA" if es_sugerencia else ("RIESGO\n\n" + (nivel.upper() if nivel else "N/D"))
        tf = banda.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = 0
        for k, letra in enumerate("\n".join(" " if ch == " " else ch for ch in etiqueta.replace("\n", " ")).split("\n")):
            par = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
            par.alignment = PP_ALIGN.CENTER
            r = par.add_run(); r.text = letra; r.font.size = Pt(8); r.font.color.rgb = BLANCO; r.font.name = "Calibri"

        X, W = Inches(1.05), Inches(8.3)   # columna principal
        _caja(s, X, Inches(1.3), W, Inches(0.55), f"{num:02d} {c.get('titulo', '')}", tam=15, negrita=True)
        prosa = "\n\n".join(t for t in (_md_plano(c.get("incidencia", "")), _md_plano(c.get("causa_raiz", ""))) if t)
        y = Inches(1.95)
        h_prosa = _altura(prosa, W, 11)
        _caja(s, X, y, W, h_prosa, prosa, tam=11, interlineado=4)
        y += h_prosa + Inches(0.1)
        detalles = c.get("como_se_ha_llegado", "").strip()
        if detalles:
            items = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", l).strip() for l in _md_plano(detalles).splitlines() if l.strip()]
            cuerpo = "A continuación, se muestran los detalles descriptivos de la situación anterior:\n" + \
                     "\n".join(f"  / {it}" for it in items)
            h_det = _altura(cuerpo, W - Inches(0.3), 10.5)
            caja = s.shapes.add_shape(1, X, y, W, h_det)
            caja.fill.solid(); caja.fill.fore_color.rgb = GRIS_CAJA
            caja.line.color.rgb = GRIS_BANDA; caja.line.width = Pt(0.75)
            _caja(s, X + Inches(0.1), y + Inches(0.05), W - Inches(0.2), h_det - Inches(0.1), cuerpo, tam=10.5, interlineado=3)
            y += h_det + Inches(0.12)
        consecuencias = _md_plano(c.get("consecuencias", ""))
        if consecuencias:
            _caja(s, X, y, W, min(_altura(consecuencias, W, 11), Inches(6.9) - y), consecuencias, tam=11)

        # Columna derecha: recomendación(es), referencia, área / responsable / plazo
        XR, WR = Inches(9.55), Inches(1.95)
        recs = [r.strip() for r in re.split(r"\n\s*\n|\n(?=\s*[-*•]\s)", c.get("recomendacion", "").strip()) if r.strip()]
        recs = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", r) for r in recs]
        yr = Inches(1.3)
        for k, rec in enumerate(recs, 1):
            titulo = f"{'Propuesta' if es_sugerencia else 'Recomendación'} {num}.{k}" if len(recs) > 1 or not es_sugerencia \
                else "Propuesta de mejora"
            _caja(s, XR, yr, WR, Inches(0.3), titulo, tam=10.5, negrita=True)
            yr += Inches(0.3)
            h = _altura(rec, WR, 9.5)
            _caja(s, XR, yr, WR, h, rec, tam=9.5)
            yr += h + Inches(0.08)
        if c.get("referencia_recomendacion"):
            _caja(s, XR, yr, WR, Inches(0.3), f"Ref.-{c['referencia_recomendacion']}", tam=9.5, color=GRIS)
        if not es_sugerencia:
            XM, WM = Inches(11.6), Inches(1.5)
            ym = Inches(1.3)
            for etiqueta, clave in (("Área", "area"), ("Responsable", "responsable"), ("Plazo", "plazo")):
                _caja(s, XM, ym, WM, Inches(0.3), etiqueta, tam=10, color=GRIS)
                _caja(s, XM, ym + Inches(0.27), WM, Inches(0.5), c.get(clave) or "Pendiente", tam=10.5)
                ym += Inches(0.85)

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
