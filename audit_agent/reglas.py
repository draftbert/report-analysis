"""
Edición del criterio de estilo (config/estilo.yaml) desde la web.

El YAML sigue siendo EL punto de mantenimiento del criterio: aquí solo se lee, se
valida y se escribe conservando los comentarios (ruamel round-trip), con snapshot
previo en config/historial/. «Modificar usando el chat» pide al modelo una
propuesta de reglas completas (esquema `PropuestaReglas`); el auditor la revisa y
la guarda él: el modelo propone, el auditor decide.
"""
from __future__ import annotations

import difflib
import io
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .esquemas import PropuestaReglas, ReglasEstilo
from .expediente import ExpedienteError
from .llm import ClienteLLM
from .style_checker import StyleChecker, reglas_como_texto

RAIZ = Path(__file__).resolve().parent.parent
RUTA_ESTILO = RAIZ / "config" / "estilo.yaml"
DIR_HISTORIAL = RAIZ / "config" / "historial"
_RE_SNAPSHOT = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})_estilo_(.*)\.yaml$")

SYSTEM_REGLAS = """Eres el responsable del criterio de estilo de los informes del Departamento de Auditoría Interna.
Recibes las reglas actuales (JSON con la misma estructura que config/estilo.yaml) y una petición del auditor.
Devuelve las reglas COMPLETAS con la petición aplicada, la lista de cambios concretos y una respuesta breve.
Normas:
- Aplica exactamente lo pedido y nada más: no reescribas, reordenes ni «mejores» reglas que no se mencionan.
- Términos y expresiones en minúsculas; sugerencias y alternativas en el tono constructivo del resto de reglas.
- Si la petición es ambigua o contradice otra regla, no cambies nada: explícalo y pregunta en `respuesta`.
- Si la petición no tiene que ver con las reglas de estilo, dilo en `respuesta` y devuelve las reglas sin cambios."""


def _rt() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def leer_texto(ruta: Path | None = None) -> str:
    return (ruta or RUTA_ESTILO).read_text(encoding="utf-8")


def leer(ruta: Path | None = None) -> dict:
    """Reglas como dict plano (lo que devuelve la API), validadas contra el esquema."""
    datos = yaml.safe_load(leer_texto(ruta)) or {}
    return ReglasEstilo.model_validate(datos).model_dump()


def validar_texto(texto: str) -> dict:
    """Comprueba que un YAML es cargable, cumple el esquema y el checker lo entiende."""
    try:
        datos = yaml.safe_load(texto)
    except yaml.YAMLError as exc:
        raise ExpedienteError(f"YAML no válido: {exc}") from exc
    if not isinstance(datos, dict):
        raise ExpedienteError("El YAML de reglas debe ser un mapa con las secciones del criterio.")
    try:
        reglas = ReglasEstilo.model_validate(datos)
    except Exception as exc:  # noqa: BLE001 — pydantic ValidationError, legible para el auditor
        raise ExpedienteError(f"Las reglas no cumplen la estructura esperada: {exc}") from exc
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(texto)
        tmp = Path(f.name)
    try:
        reglas_como_texto(StyleChecker(tmp))
    except Exception as exc:  # noqa: BLE001
        raise ExpedienteError(f"El revisor de estilo no puede usar estas reglas: {exc}") from exc
    finally:
        tmp.unlink(missing_ok=True)
    return reglas.model_dump()


def _plano(x):
    return json.loads(json.dumps(x, ensure_ascii=False))


def _fusionar(viejo, nuevo):
    """Aplica `nuevo` (plano) sobre `viejo` (árbol ruamel) tocando solo lo que cambia, para
    que comentarios, comillas y orden de lo que no cambia se conserven en el YAML."""
    if isinstance(nuevo, dict) and isinstance(viejo, CommentedMap):
        for k in [k for k in viejo if k not in nuevo]:
            del viejo[k]
        for k, v in nuevo.items():
            viejo[k] = _fusionar(viejo[k], v) if k in viejo else v
        return viejo
    if isinstance(nuevo, list) and isinstance(viejo, CommentedSeq):
        # Los ítems se emparejan por su clave (termino / campo / antes / el propio valor), no por
        # posición: así un borrado o una inserción no desplaza los comentarios a otro ítem.
        viejos: dict = {}
        for i, it in enumerate(viejo):
            viejos.setdefault(_clave_item(it), []).append((i, it))
        comentarios_seq = dict(viejo.ca.items)
        resultado, comentarios = [], {}
        for v in nuevo:
            candidatos = viejos.get(_clave_item(v))
            if candidatos:
                i, it = candidatos.pop(0)
                nodo = _fusionar(it, v) if isinstance(v, (dict, list)) else (it if _plano(it) == v else v)
                if i in comentarios_seq:
                    comentarios[len(resultado)] = comentarios_seq[i]
                resultado.append(nodo)
            else:
                resultado.append(v)
        viejo[:] = resultado
        viejo.ca.items.clear()
        viejo.ca.items.update(comentarios)
        return viejo
    return viejo if _plano(viejo) == nuevo else nuevo


def _clave_item(item) -> tuple:
    if isinstance(item, dict):
        for k in ("termino", "campo", "antes"):
            if k in item:
                return ("k", str(item[k]))
        return ("j", json.dumps(_plano(item), sort_keys=True, ensure_ascii=False))
    return ("v", json.dumps(_plano(item), ensure_ascii=False))


def texto_desde_reglas(reglas: dict, base: str | None = None) -> str:
    """Vuelca `reglas` sobre el YAML actual conservando comentarios: solo se reescribe lo que
    cambia; el resto queda como estaba."""
    base = base if base is not None else leer_texto()
    rt = _rt()
    doc = rt.load(base)
    if doc is None:
        doc = CommentedMap()
    nuevas = ReglasEstilo.model_validate(reglas).model_dump()
    _fusionar(doc, nuevas)
    salida = io.StringIO()
    rt.dump(doc, salida)
    return salida.getvalue()


def historial() -> list[dict]:
    if not DIR_HISTORIAL.exists():
        return []
    salida = []
    for p in sorted(DIR_HISTORIAL.glob("*_estilo_*.yaml"), reverse=True):
        m = _RE_SNAPSHOT.match(p.name)
        if m:
            fecha = m.group(1)
            salida.append({"nombre": p.name, "fecha": fecha[:10] + " " + fecha[11:].replace("-", ":"), "motivo": m.group(2)})
    return salida


def _snapshot(motivo: str) -> Path:
    DIR_HISTORIAL.mkdir(parents=True, exist_ok=True)
    motivo = re.sub(r"[^A-Za-z0-9_-]+", "-", motivo).strip("-") or "web"
    destino = DIR_HISTORIAL / f"{datetime.now():%Y-%m-%dT%H-%M-%S}_estilo_{motivo}.yaml"
    destino.write_text(leer_texto(), encoding="utf-8")
    return destino


def guardar_texto(texto: str, motivo: str = "web") -> dict:
    """Valida y escribe el YAML completo (snapshot previo). Devuelve las reglas guardadas."""
    reglas = validar_texto(texto)
    if texto != leer_texto():
        _snapshot(motivo)
        RUTA_ESTILO.write_text(texto if texto.endswith("\n") else texto + "\n", encoding="utf-8")
    return reglas


def guardar(reglas: dict, motivo: str = "web") -> dict:
    """Guarda las reglas estructuradas (desde la web) conservando los comentarios del YAML."""
    return guardar_texto(texto_desde_reglas(reglas), motivo)


def restaurar(nombre: str) -> dict:
    ruta = DIR_HISTORIAL / Path(nombre).name
    if not ruta.is_file() or not _RE_SNAPSHOT.match(ruta.name):
        raise ExpedienteError(f"No existe la versión {Path(nombre).name} en config/historial/.")
    return guardar_texto(ruta.read_text(encoding="utf-8"), motivo="restaurar")


def diff_yaml(antes: str, despues: str) -> str:
    return "".join(difflib.unified_diff(antes.splitlines(True), despues.splitlines(True), "estilo.yaml (actual)", "estilo.yaml (propuesta)"))


def estado() -> dict:
    """Lo que devuelve GET /api/reglas."""
    texto = leer_texto()
    return {"reglas": ReglasEstilo.model_validate(yaml.safe_load(texto) or {}).model_dump(), "yaml": texto,
            "historial": historial(), "modificado": datetime.fromtimestamp(RUTA_ESTILO.stat().st_mtime).isoformat(timespec="seconds")}


def _trazar(accion: str, registro: dict) -> None:
    dir_trazas = DIR_HISTORIAL / "trazas"
    dir_trazas.mkdir(parents=True, exist_ok=True)
    (dir_trazas / f"{datetime.now():%Y-%m-%dT%H-%M-%S}_{accion}.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def cliente_llm() -> ClienteLLM:
    return ClienteLLM(trazador=_trazar)


def chat(mensaje: str, reglas_base: dict | None = None, llm: ClienteLLM | None = None) -> dict:
    """Pide al modelo una propuesta de reglas a partir de `mensaje`. No escribe nada: devuelve
    la respuesta, los cambios, las reglas propuestas y el diff del YAML resultante."""
    mensaje = (mensaje or "").strip()
    if not mensaje:
        raise ExpedienteError("Escribe qué regla quieres cambiar.")
    base = ReglasEstilo.model_validate(reglas_base if reglas_base is not None else leer()).model_dump()
    user = ("REGLAS ACTUALES (JSON):\n" + json.dumps(base, ensure_ascii=False, indent=2)
            + "\n\nPETICIÓN DEL AUDITOR:\n" + mensaje)
    llm = llm or cliente_llm()
    prop = llm.completar_estructurado("reglas-chat", SYSTEM_REGLAS, user, PropuestaReglas)
    propuestas = prop.reglas.model_dump()
    texto_base = texto_desde_reglas(base)
    texto_prop = texto_desde_reglas(propuestas, base=texto_base)
    return {"respuesta": prop.respuesta, "cambios": list(prop.cambios), "reglas": propuestas,
            "diff": diff_yaml(texto_base, texto_prop), "sin_cambios": propuestas == base}
