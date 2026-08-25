"""
CLI del revisor de informes de auditoría interna.

    ./revisor nuevo expedientes/CNC-2026-03 --nombre "Auditoría de Compras" --referencia CNC-2026-03
    ./revisor usar expedientes/CNC-2026-03          # fija el expediente activo
    ./revisor estado                                 # dónde estoy y qué toca
    ./revisor menu                                   # menú interactivo con lo mismo

    ./revisor extraer            → 01_observaciones.md (propuestas del modelo)
    ./revisor aprobar OBS-01 OBS-03 | aprobar todas | descartar OBS-02
    ./revisor revisar-obs | corregir-obs | regenerar-obs OBS-02
    ./revisor redactar [--forzar | --secciones objetivo alcance]   → 02_informe.md
    ./revisor revisar | corregir [--avisos] | aplicar-cambios [--solo-plan]
    ./revisor diff | deshacer | historial | ppt | archivar

    ./revisor revisar-texto --fichero borrador.txt [--sin-llm]   (texto suelto, sin expediente)
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_DEFECTO = RAIZ / "config" / "estilo.yaml"
DIR_EXPEDIENTES = RAIZ / "expedientes"
FICHERO_ACTIVO = RAIZ / ".expediente_activo"

load_dotenv(RAIZ / ".env")


# ---------------------------------------------------------------- resolución del expediente
def resolver_expediente(ruta: str | None) -> Path:
    if ruta:
        return Path(ruta)
    if FICHERO_ACTIVO.exists():
        activo = Path(FICHERO_ACTIVO.read_text(encoding="utf-8").strip())
        if (activo / "expediente.yaml").exists():
            return activo
    candidatos = sorted(p.parent for p in DIR_EXPEDIENTES.glob("*/expediente.yaml")) if DIR_EXPEDIENTES.exists() else []
    if len(candidatos) == 1:
        return candidatos[0]
    if not candidatos:
        sys.exit("No hay ningún expediente. Crea uno: ./revisor nuevo expedientes/<REF> --nombre ... --referencia ...")
    sys.exit("Hay varios expedientes; indica cuál con -e <ruta> o fija uno con `./revisor usar <ruta>`:\n  "
             + "\n  ".join(str(c) for c in candidatos))


def _abrir(args):
    from .expediente import Expediente
    return Expediente(resolver_expediente(args.expediente))


def _contexto(args):
    from .acciones import Contexto
    return Contexto(_abrir(args), config=args.config, modelo=args.modelo,
                    proveedor=args.proveedor, esfuerzo=args.esfuerzo)


# ---------------------------------------------------------------- comandos
def cmd_nuevo(args):
    from .expediente import Expediente
    dist = [d.strip() for d in (args.distribucion or "").split(",") if d.strip()]
    exp = Expediente.crear(args.ruta, args.nombre, args.referencia, args.fecha or "", dist)
    if args.ejemplo:
        shutil.copy(RAIZ / "ejemplos" / "papel_trabajo_compras.md", exp.ruta / "entrada")
    FICHERO_ACTIVO.write_text(str(exp.ruta), encoding="utf-8")
    return (f"Expediente creado en {exp.ruta} y fijado como activo.\n"
            f"Copia los papeles de trabajo a {exp.ruta / 'entrada'} y ejecuta `extraer`."
            + ("\n(Se ha copiado el papel de trabajo de ejemplo.)" if args.ejemplo else ""))


def cmd_usar(args):
    ruta = Path(args.ruta).resolve()
    if not (ruta / "expediente.yaml").exists():
        sys.exit(f"{ruta} no es un expediente.")
    FICHERO_ACTIVO.write_text(str(ruta), encoding="utf-8")
    return f"Expediente activo: {ruta}"


def cmd_estado(args):
    from .acciones import accion_estado
    from .llm import ClienteLLM
    from .style_checker import StyleChecker
    try:
        llm_desc = ClienteLLM(modelo=args.modelo, proveedor=args.proveedor, esfuerzo=args.esfuerzo).descripcion()
    except Exception as exc:  # credenciales incompletas, etc.
        llm_desc = f"no disponible ({exc})"
    return accion_estado(_abrir(args), StyleChecker(args.config), llm_desc)


def cmd_extraer(args):
    from .acciones import accion_extraer
    return accion_extraer(_contexto(args), forzar=args.forzar)


def cmd_aprobar(args):
    from .acciones import accion_aprobar
    return accion_aprobar(_abrir(args), args.ids, estado=args.estado)


def cmd_revisar_obs(args):
    from .acciones import accion_revisar_obs
    return accion_revisar_obs(_contexto(args))


def cmd_corregir_obs(args):
    from .acciones import accion_corregir_obs
    return accion_corregir_obs(_contexto(args), ids=args.ids or None)


def cmd_regenerar_obs(args):
    from .acciones import accion_regenerar_obs
    return accion_regenerar_obs(_contexto(args), args.id)


def cmd_redactar(args):
    from .acciones import accion_redactar
    return accion_redactar(_contexto(args), forzar=args.forzar, secciones=args.secciones or None)


def cmd_revisar(args):
    from .acciones import accion_revisar
    return accion_revisar(_contexto(args))


def cmd_corregir(args):
    from .acciones import accion_corregir
    return accion_corregir(_contexto(args), incluir_avisos=args.avisos)


def cmd_aplicar_cambios(args):
    from .acciones import accion_aplicar_cambios
    return accion_aplicar_cambios(_contexto(args), solo_plan=args.solo_plan)


def cmd_ppt(args):
    from .acciones import accion_ppt
    return accion_ppt(_abrir(args))


def cmd_archivar(args):
    from .acciones import accion_archivar
    return accion_archivar(_abrir(args))


def cmd_diff(args):
    from .acciones import accion_diff
    return accion_diff(_abrir(args), args.fichero)


def cmd_deshacer(args):
    from .acciones import accion_deshacer
    return accion_deshacer(_abrir(args), args.fichero)


def cmd_historial(args):
    from .acciones import accion_historial
    return accion_historial(_abrir(args))


def cmd_revisar_texto(args):
    from .reviewer import AgenteRevisor
    texto = args.texto or Path(args.fichero).read_text(encoding="utf-8")
    res = AgenteRevisor(args.config, modelo=args.modelo).revisar(texto, reescribir=not args.sin_llm)
    L = ["— Revisión de estilo —"]
    if not res["hallazgos"]:
        L.append("  ✔ Sin hallazgos de estilo.")
    for h in res["hallazgos"]:
        L.append(f"  {'✖' if h['severidad'] == 'error' else '⚠'} «{h['fragmento']}» — {h['mensaje']}")
        if h.get("sugerencia"):
            L.append(f"      → {h['sugerencia']}")
    if res["propuesta"]:
        L += ["", "— Propuesta de reescritura —", res["propuesta"]]
        if res["propuesta_verificada"] is False:
            L.append("\n⚠ La propuesta aún infringe reglas; revisar manualmente.")
    return "\n".join(L)


# ---------------------------------------------------------------- menú interactivo
MENU = [
    ("estado", "Ver estado del expediente", cmd_estado, {}),
    ("extraer", "Extraer observaciones y recomendaciones de entrada/ (LLM)", cmd_extraer, {"forzar": False}),
    ("aprobar todas", "Aprobar todas las observaciones", cmd_aprobar, {"ids": ["todas"], "estado": "aprobada"}),
    ("revisar-obs", "Revisar vocabulario y estructura de las observaciones", cmd_revisar_obs, {}),
    ("corregir-obs", "Corregir con el modelo solo lo señalado en las observaciones (LLM)", cmd_corregir_obs, {"ids": None}),
    ("redactar", "Redactar el informe con las observaciones aprobadas (LLM)", cmd_redactar, {"forzar": False, "secciones": None}),
    ("revisar", "Revisar vocabulario prohibido y estilo del informe", cmd_revisar, {}),
    ("corregir", "Reescribir con el modelo los párrafos con errores (LLM)", cmd_corregir, {"avisos": False}),
    ("aplicar-cambios", "Aplicar las instrucciones de 03_instrucciones.md al informe (LLM)", cmd_aplicar_cambios, {"solo_plan": False}),
    ("diff", "Ver cambios del informe respecto a la última versión guardada", cmd_diff, {"fichero": "informe"}),
    ("deshacer", "Restaurar la versión anterior del informe", cmd_deshacer, {"fichero": "informe"}),
    ("ppt", "Generar el Resumen Ejecutivo en PowerPoint", cmd_ppt, {}),
    ("archivar", "Archivar evidencia (zip con trazas, historial, informe, PPT + manifest sha256)", cmd_archivar, {}),
]


def cmd_menu(args):
    print(cmd_estado(args))
    while True:
        print("\nAcciones:")
        for i, (nombre, desc, _, _) in enumerate(MENU, 1):
            print(f"  {i:2}. {nombre:16} {desc}")
        print("   0. Salir")
        try:
            eleccion = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            return "\nHasta luego."
        if eleccion in ("0", "q", "salir", ""):
            return "Hasta luego."
        if not eleccion.isdigit() or not 1 <= int(eleccion) <= len(MENU):
            continue
        nombre, _, fn, extra = MENU[int(eleccion) - 1]
        sub = argparse.Namespace(**vars(args), **extra)
        if nombre == "extraer" and _abrir(args).existe("observaciones"):
            sub.forzar = input("01_observaciones.md ya existe. ¿Regenerar? (se guarda snapshot) [s/N] ").strip().lower() == "s"
            if not sub.forzar:
                continue
        if nombre == "redactar" and _abrir(args).existe("informe"):
            sub.forzar = input("02_informe.md ya existe. ¿Reescribirlo entero? (se guarda snapshot) [s/N] ").strip().lower() == "s"
            if not sub.forzar:
                continue
        try:
            print("\n" + fn(sub))
        except Exception as exc:  # noqa: BLE001 — el menú no debe morir por un error de acción
            print(f"\n✖ {exc}")
        if nombre != "estado":
            print("\n" + cmd_estado(args))


# ---------------------------------------------------------------- parser
def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="revisor", description="Revisor de informes de auditoría interna")
    p.add_argument("-e", "--expediente", help="Ruta del expediente (por defecto: el activo o el único en expedientes/)")
    p.add_argument("--config", default=str(CONFIG_DEFECTO))
    p.add_argument("--modelo", help="Modelo LLM (por defecto KAIA_AGENT_MODEL_NAME)")
    p.add_argument("--proveedor", choices=["kaia", "anthropic", "dry-run"], help="Por defecto: LLM_PROVEEDOR o autodetección")
    p.add_argument("--esfuerzo", choices=["minimal", "low", "medium", "high"], help="reasoning_effort para modelos gpt-5*")
    sub = p.add_subparsers(dest="comando", required=True)

    s = sub.add_parser("nuevo", help="Crear un expediente"); s.set_defaults(fn=cmd_nuevo)
    s.add_argument("ruta"); s.add_argument("--nombre", required=True); s.add_argument("--referencia", required=True)
    s.add_argument("--fecha"); s.add_argument("--distribucion", help="Lista separada por comas")
    s.add_argument("--ejemplo", action="store_true", help="Copiar el papel de trabajo de ejemplo a entrada/")

    s = sub.add_parser("usar", help="Fijar el expediente activo"); s.set_defaults(fn=cmd_usar); s.add_argument("ruta")
    sub.add_parser("estado", help="Estado y siguiente paso").set_defaults(fn=cmd_estado)
    sub.add_parser("menu", help="Menú interactivo").set_defaults(fn=cmd_menu)

    s = sub.add_parser("extraer", help="Proponer observaciones desde entrada/ (LLM)"); s.set_defaults(fn=cmd_extraer)
    s.add_argument("--forzar", action="store_true")
    s = sub.add_parser("aprobar", help="Marcar observaciones como aprobadas"); s.set_defaults(fn=cmd_aprobar, estado="aprobada")
    s.add_argument("ids", nargs="+", help="OBS-01 OBS-02 … o `todas`")
    s = sub.add_parser("descartar", help="Marcar observaciones como descartadas"); s.set_defaults(fn=cmd_aprobar, estado="descartada")
    s.add_argument("ids", nargs="+")
    s = sub.add_parser("proponer", help="Devolver observaciones a estado propuesta"); s.set_defaults(fn=cmd_aprobar, estado="propuesta")
    s.add_argument("ids", nargs="+")
    sub.add_parser("revisar-obs", help="Reglas deterministas sobre las observaciones").set_defaults(fn=cmd_revisar_obs)
    s = sub.add_parser("corregir-obs", help="Corregir con LLM lo señalado por las reglas"); s.set_defaults(fn=cmd_corregir_obs)
    s.add_argument("ids", nargs="*")
    s = sub.add_parser("regenerar-obs", help="Rehacer una observación según «Notas del auditor» (LLM)"); s.set_defaults(fn=cmd_regenerar_obs)
    s.add_argument("id")

    s = sub.add_parser("redactar", help="Redactar el informe con las aprobadas (LLM)"); s.set_defaults(fn=cmd_redactar)
    s.add_argument("--forzar", action="store_true", help="Reescribir aunque exista 02_informe.md")
    s.add_argument("--secciones", nargs="+", help="Rehacer solo: objetivo alcance contexto observaciones evaluacion proximos")
    sub.add_parser("revisar", help="Vocabulario prohibido y estilo del informe").set_defaults(fn=cmd_revisar)
    s = sub.add_parser("corregir", help="Reescribir con LLM los párrafos con errores"); s.set_defaults(fn=cmd_corregir)
    s.add_argument("--avisos", action="store_true", help="Incluir también avisos (frases largas)")
    s = sub.add_parser("aplicar-cambios", help="Aplicar 03_instrucciones.md al informe (LLM)"); s.set_defaults(fn=cmd_aplicar_cambios)
    s.add_argument("--solo-plan", action="store_true", help="Mostrar el plan sin tocar el informe")
    sub.add_parser("ppt", help="Generar el Resumen Ejecutivo").set_defaults(fn=cmd_ppt)
    sub.add_parser("archivar", help="Zip de evidencia del expediente con manifest sha256").set_defaults(fn=cmd_archivar)

    for nombre, fn in (("diff", cmd_diff), ("deshacer", cmd_deshacer)):
        s = sub.add_parser(nombre); s.set_defaults(fn=fn)
        s.add_argument("fichero", nargs="?", default="informe", choices=["informe", "observaciones", "instrucciones"])
    sub.add_parser("historial", help="Versiones guardadas").set_defaults(fn=cmd_historial)

    s = sub.add_parser("revisar-texto", help="Revisar un texto suelto (sin expediente)"); s.set_defaults(fn=cmd_revisar_texto)
    s.add_argument("--texto"); s.add_argument("--fichero"); s.add_argument("--sin-llm", action="store_true")
    return p


def main(argv=None) -> int:
    args = construir_parser().parse_args(argv)
    try:
        salida = args.fn(args)
    except Exception as exc:  # noqa: BLE001 — mensaje limpio para el usuario final
        from .expediente import ExpedienteError
        from .llm import LLMNoDisponible
        if isinstance(exc, (ExpedienteError, LLMNoDisponible, FileNotFoundError)):
            print(f"✖ {exc}", file=sys.stderr)
            return 1
        raise
    if salida:
        print(salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
