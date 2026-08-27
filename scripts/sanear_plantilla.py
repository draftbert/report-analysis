"""Sanea la plantilla corporativa de PowerPoint antes de versionarla en config/.

Elimina todo lo que no hace falta para generar informes y que puede contener
datos personales o metadatos de revisión: comentarios y autores, notas,
historial de cambios/revisiones, customXml, propiedades personalizadas,
miniatura, objetos think-cell (OLE + tags) y las propiedades de autor del
documento. Las diapositivas, diseños, imágenes, tema y tabla de estilos se
conservan intactos.

Uso: .venv/bin/python scripts/sanear_plantilla.py "Plantilla Informe.pptx" config/plantilla_informe.pptx
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

from pptx import Presentation

R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
TIPOS_SLIDE = ("/comments", "/notesSlide", "/tags", "/oleObject")
TIPOS_PRESENTACION = ("/authors", "/commentAuthors", "/changesInfo", "/revisionInfo", "/customXml")
TIPOS_PAQUETE = ("/custom-properties", "/thumbnail", "/classificationlabels")


def _ids_referenciados(elemento) -> dict:
    """{rId: [elementos que lo referencian]} dentro de un árbol XML."""
    refs: dict = {}
    for el in elemento.iter():
        for k, v in el.attrib.items():
            if k.startswith(R):
                refs.setdefault(v, []).append(el)
    return refs


def _quitar_referencias(elemento, ids: set[str]) -> None:
    """Elimina los elementos que referencian relaciones borradas, subiendo al
    contenedor adecuado (marco OLE, lista de tags, extensión de comentarios)."""
    for rid, elementos in _ids_referenciados(elemento).items():
        if rid not in ids:
            continue
        for el in elementos:
            objetivo = el
            for anc in el.iterancestors():
                nombre = anc.tag.split("}")[1]
                if nombre in ("graphicFrame", "custDataLst", "ext"):
                    objetivo = anc
                    break
            padre = objetivo.getparent()
            if padre is not None:
                padre.remove(objetivo)


def _quitar_rels(parte, sufijos: tuple[str, ...]) -> set[str]:
    """Quita las relaciones de los tipos indicados (sin contar referencias:
    `drop_rel` no borra las que el XML cita más de una vez, como los OLE)."""
    rels = getattr(parte, "rels", None) or parte._rels
    borrados = {rid for rid, rel in list(rels.items()) if rel.reltype.endswith(sufijos)}
    for rid in borrados:
        rels.pop(rid)
    return borrados


def sanear(origen: Path, destino: Path) -> Path:
    prs = Presentation(str(origen))
    for slide in prs.slides:
        borrados = _quitar_rels(slide.part, TIPOS_SLIDE)
        _quitar_referencias(slide._element, borrados)
    borrados = _quitar_rels(prs.part, TIPOS_PRESENTACION)
    _quitar_referencias(prs.part._element, borrados)
    _quitar_rels(prs.part.package, TIPOS_PAQUETE)
    cp = prs.core_properties
    cp.author = ""
    cp.last_modified_by = ""
    cp.title = "Plantilla de informe de auditoría interna"
    cp.subject = cp.keywords = cp.comments = cp.category = ""
    cp.revision = 1
    destino.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(destino))
    return destino


def comprobar(destino: Path, palabras: list[str]) -> list[str]:
    """Devuelve las partes del paquete que aún contienen alguna palabra sensible."""
    hallazgos = []
    with zipfile.ZipFile(destino) as z:
        for nombre in z.namelist():
            if nombre.endswith((".xml", ".rels")):
                texto = z.read(nombre).decode("utf8", "ignore")
                for palabra in palabras:
                    if palabra.lower() in texto.lower():
                        hallazgos.append(f"{nombre}: {palabra}")
    return hallazgos


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    salida = sanear(Path(sys.argv[1]), Path(sys.argv[2]))
    restos = comprobar(salida, sys.argv[3:])
    print(f"Plantilla saneada: {salida} ({salida.stat().st_size:,} bytes)")
    if restos:
        print("AVISO, quedan referencias:", *restos, sep="\n  ")
