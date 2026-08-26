"""
Expediente: la carpeta de trabajo de una auditoría.

Es el "front" de la herramienta: todo el estado vive en ficheros de texto
que el auditor edita con su editor (VS Code, Notepad++…) y la herramienta
lee y escribe. Ventajas para un trabajo de varios días: se guarda solo, se
puede versionar con git, se puede compartir por carpeta, y cada
sobreescritura deja un snapshot en `historial/` (deshacer / diff).

    expedientes/CNC-2026-03/
      expediente.yaml         metadatos del trabajo
      entrada/                papeles de trabajo exportados de Pentana (.md/.txt/.docx)
      01_conclusiones.md      conclusiones (incidencias) propuestas -> el auditor edita, aprueba y recomienda
      02_informe.md           informe: introducción, resumen ejecutivo, detalle de conclusiones, sugerencias
      03_instrucciones.md     buzón: transcripción / comentarios -> aplicar-cambios
      revision.md             último informe de vocabulario y estilo
      cambios_aplicados.md    registro de los cambios aplicados por el modelo
      historial/              snapshots automáticos antes de cada sobreescritura
      salidas/                entregables (PPT)
      trazas/                 cada llamada al LLM (prompt, respuesta, tokens)
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import yaml

from .lectores import EXTENSIONES, Documento, leer as leer_documento

ARCHIVOS = {
    "meta": "expediente.yaml",
    "conclusiones": "01_conclusiones.md",
    "informe": "02_informe.md",
    "instrucciones": "03_instrucciones.md",
    "revision": "revision.md",
    "cambios": "cambios_aplicados.md",
}
DIRECTORIOS = ("entrada", "historial", "salidas", "trazas")
EXTENSIONES_ENTRADA = EXTENSIONES  # ver lectores.py

SEPARADOR_INSTRUCCIONES = "---"

PLANTILLA_INSTRUCCIONES = """# Instrucciones de cambios — {referencia}

> Pega debajo de la línea todo lo que quieras que se aplique al informe:
> la transcripción de una reunión, los comentarios del Gerente o la Directora,
> notas sueltas ("acortar la conclusión 2", "cambiar el responsable de la 3
> a Dirección Financiera", "suavizar la conclusión")…
> Después ejecuta `aplicar-cambios`. La herramienta interpreta el texto,
> propone cambios concretos, los aplica sobre 02_informe.md (con snapshot en
> historial/) y deja el detalle en cambios_aplicados.md.
> Al terminar, este fichero se vacía y lo que pegaste queda en historial/.

---

"""


class ExpedienteError(RuntimeError):
    pass


class Expediente:
    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta).resolve()
        if not (self.ruta / ARCHIVOS["meta"]).exists():
            raise ExpedienteError(
                f"{self.ruta} no es un expediente (falta {ARCHIVOS['meta']}). "
                "Crea uno con: python -m audit_agent.cli nuevo <ruta> --nombre ... --referencia ...")
        for d in DIRECTORIOS:
            (self.ruta / d).mkdir(exist_ok=True)
        self.meta = yaml.safe_load((self.ruta / ARCHIVOS["meta"]).read_text(encoding="utf-8")) or {}

    # ------------------------------------------------------------ creación
    @classmethod
    def crear(cls, ruta: str | Path, nombre: str, referencia: str, fecha: str = "",
              distribucion: list[str] | None = None) -> "Expediente":
        ruta = Path(ruta)
        if (ruta / ARCHIVOS["meta"]).exists():
            raise ExpedienteError(f"Ya existe un expediente en {ruta}")
        ruta.mkdir(parents=True, exist_ok=True)
        for d in DIRECTORIOS:
            (ruta / d).mkdir(exist_ok=True)
        meta = {
            "proyecto": {
                "nombre": nombre,
                "referencia": referencia,
                "fecha": fecha or datetime.now().strftime("%B %Y").capitalize(),
                "distribucion": distribucion or [],
            },
            "creado": datetime.now().isoformat(timespec="seconds"),
            "notas": "Contexto adicional para el modelo (opcional): objetivo previsto, alcance, hitos…",
        }
        (ruta / ARCHIVOS["meta"]).write_text(
            yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")
        (ruta / ARCHIVOS["instrucciones"]).write_text(
            PLANTILLA_INSTRUCCIONES.format(referencia=referencia), encoding="utf-8")
        (ruta / "entrada" / "LEEME.txt").write_text(
            "Deja aquí el papel de trabajo final (todas las pruebas), el contexto de la auditoría, anexos, design\n"
            "thinking… (.md, .txt, .docx, .xlsx o .pdf con texto). Todo lo que hay aquí se envía al modelo en\n"
            "`redactar-contexto` y `extraer`.\n", encoding="utf-8")
        return cls(ruta)

    # ------------------------------------------------------------ rutas
    def archivo(self, clave: str) -> Path:
        return self.ruta / ARCHIVOS[clave]

    @property
    def proyecto(self) -> dict:
        return self.meta.get("proyecto", {})

    @property
    def referencia(self) -> str:
        return str(self.proyecto.get("referencia", self.ruta.name))

    def existe(self, clave: str) -> bool:
        return self.archivo(clave).exists()

    def leer(self, clave: str) -> str:
        p = self.archivo(clave)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    # ------------------------------------------------------------ escritura con historial
    def snapshot(self, clave: str, motivo: str) -> Path | None:
        origen = self.archivo(clave)
        if not origen.exists():
            return None
        marca = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        motivo_slug = re.sub(r"[^a-z0-9]+", "-", motivo.lower()).strip("-")[:40]
        destino = self.ruta / "historial" / f"{marca}_{origen.stem}_{motivo_slug}{origen.suffix}"
        shutil.copy2(origen, destino)
        return destino

    def escribir(self, clave: str, contenido: str, motivo: str) -> Path | None:
        """Guarda snapshot del contenido anterior (si lo hay) y escribe."""
        snap = self.snapshot(clave, motivo)
        self.archivo(clave).write_text(contenido, encoding="utf-8")
        return snap

    def historial(self, clave: str) -> list[Path]:
        stem = self.archivo(clave).stem
        return sorted((self.ruta / "historial").glob(f"*_{stem}_*"))

    def restaurar(self, clave: str, snapshot: Path | None = None) -> Path:
        versiones = self.historial(clave)
        if not versiones:
            raise ExpedienteError(f"No hay versiones anteriores de {ARCHIVOS[clave]} en historial/.")
        origen = snapshot or versiones[-1]
        self.snapshot(clave, "antes-de-deshacer")
        shutil.copy2(origen, self.archivo(clave))
        return origen

    # ------------------------------------------------------------ entrada
    def ficheros_entrada(self) -> list[Path]:
        return sorted(p for p in (self.ruta / "entrada").iterdir()
                      if p.suffix.lower() in EXTENSIONES_ENTRADA and p.name.lower() != "leeme.txt")

    def leer_entrada(self) -> list[Documento]:
        """Lee todos los documentos de entrada/ con la capa de lectores
        (texto normalizado a Markdown, con el nombre del lector usado)."""
        return [leer_documento(p) for p in self.ficheros_entrada()]

    # ------------------------------------------------------------ instrucciones
    def instrucciones_pendientes(self) -> str:
        texto = self.leer("instrucciones")
        if SEPARADOR_INSTRUCCIONES in texto:
            texto = texto.split(SEPARADOR_INSTRUCCIONES, 1)[1]
        return texto.strip()

    def vaciar_instrucciones(self) -> None:
        self.snapshot("instrucciones", "aplicadas")
        self.archivo("instrucciones").write_text(
            PLANTILLA_INSTRUCCIONES.format(referencia=self.referencia), encoding="utf-8")

    # ------------------------------------------------------------ trazas
    def trazar(self, accion: str, registro: dict) -> Path:
        marca = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        destino = self.ruta / "trazas" / f"{marca}_{accion}.json"
        destino.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
        return destino

    def anexar_registro(self, clave: str, texto: str) -> None:
        p = self.archivo(clave)
        previo = p.read_text(encoding="utf-8") if p.exists() else ""
        p.write_text(previo + texto, encoding="utf-8")

    # ------------------------------------------------------------ salidas
    def ruta_ppt(self) -> Path:
        return self.ruta / "salidas" / f"ResumenEjecutivo_{self.referencia}.pptx"
