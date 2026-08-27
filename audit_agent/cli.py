"""
CLI del revisor de informes de auditoría interna.

    ./revisor nuevo expedientes/CNC-2026-03 --nombre "Auditoría de Compras" --referencia CNC-2026-03
    ./revisor usar expedientes/CNC-2026-03          # fija el expediente activo
    ./revisor estado                                 # dónde estoy y qué toca
    ./revisor web                                    # interfaz web (API + front) en http://127.0.0.1:8000
    ./revisor menu                                   # menú interactivo con lo mismo

    ./revisor redactar-contexto [--forzar | --secciones introduccion resumen]  → introducción + resumen ejecutivo
    ./revisor extraer            → 01_conclusiones.md (incidencias y sugerencias de mejora de todas las pruebas)
    ./revisor aprobar C-01 C-03 | aprobar todas | descartar C-02
    ./revisor revisar-conclusiones | corregir-conclusiones | regenerar C-02
    ./revisor recomendar [C-01 ...] [--auto] [--formatear]     → recomendaciones (respeta las del auditor)
    ./revisor redactar-conclusiones                            → vuelca las aprobadas a 02_informe.md
    ./revisor revisar | corregir [--avisos] | aplicar-cambios [--solo-plan]
    ./revisor reunion transcripcion.txt [--aplicar]   → acta: cambios de texto vs PPT
    ./revisor cambio "pon el riesgo de la conclusión 1 en Alto"  |  ./revisor chat
    ./revisor diff | deshacer | historial | ppt | archivar
    ./revisor calibrar-estilo <carpeta_informes_aprobados> [--salida x.md] [--sin-llm]

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
        shutil.copy(RAIZ / "ejemplos" / "papel_trabajo_tarifarios.txt", exp.ruta / "papeles_trabajo")
        shutil.copy(RAIZ / "ejemplos" / "contexto_auditoria_tarifarios.md", exp.ruta / "contexto")
    FICHERO_ACTIVO.write_text(str(exp.ruta), encoding="utf-8")
    return (f"Expediente creado en {exp.ruta} y fijado como activo.\n"
            f"Copia el design thinking / contexto a {exp.ruta / 'contexto'} (opcional) y el papel de trabajo final a "
            f"{exp.ruta / 'papeles_trabajo'}; después `redactar-contexto` y `extraer`."
            + ("\n(Se ha copiado el papel de trabajo de ejemplo.)" if args.ejemplo else ""))


def cmd_usar(args):
    ruta = Path(args.ruta).resolve()
    if not (ruta / "expediente.yaml").exists():
        sys.exit(f"{ruta} no es un expediente.")
    FICHERO_ACTIVO.write_text(str(ruta), encoding="utf-8")
    return f"Expediente activo: {ruta}"


def cmd_eliminar(args):
    """Borra un expediente entero; pide escribir la referencia como confirmación."""
    import shutil
    exp = _abrir(args)
    print(f"Se eliminará {exp.ruta} con todo su contenido (documentos, informe, historial, trazas, salidas).")
    try:
        escrito = args.confirmar or input(f"Escribe la referencia «{exp.referencia}» para confirmar: ").strip()
    except EOFError:
        escrito = ""
    if escrito != exp.referencia:
        sys.exit("Confirmación incorrecta: no se ha eliminado nada.")
    shutil.rmtree(exp.ruta)
    if FICHERO_ACTIVO.exists() and FICHERO_ACTIVO.read_text(encoding="utf-8").strip() == str(exp.ruta):
        FICHERO_ACTIVO.unlink()
    return f"Expediente {exp.referencia} eliminado."


def cmd_estado(args):
    from .acciones import accion_estado
    from .llm import ClienteLLM
    from .style_checker import StyleChecker
    try:
        llm_desc = ClienteLLM(modelo=args.modelo, proveedor=args.proveedor, esfuerzo=args.esfuerzo).descripcion()
    except Exception as exc:  # credenciales incompletas, etc.
        llm_desc = f"no disponible ({exc})"
    return accion_estado(_abrir(args), StyleChecker(args.config), llm_desc)


def cmd_redactar_contexto(args):
    from .acciones import accion_redactar_contexto
    return accion_redactar_contexto(_contexto(args), secciones=args.secciones or None, forzar=args.forzar)


def cmd_extraer(args):
    from .acciones import accion_extraer
    return accion_extraer(_contexto(args), forzar=args.forzar)


def cmd_aprobar(args):
    from .acciones import accion_aprobar
    return accion_aprobar(_abrir(args), args.ids, estado=args.estado)


def cmd_revisar_conclusiones(args):
    from .acciones import accion_revisar_conclusiones
    return accion_revisar_conclusiones(_contexto(args))


def cmd_corregir_conclusiones(args):
    from .acciones import accion_corregir_conclusiones
    return accion_corregir_conclusiones(_contexto(args), ids=args.ids or None)


def cmd_regenerar(args):
    from .acciones import accion_regenerar
    return accion_regenerar(_contexto(args), args.id)


def _preguntar_recomendacion(c):
    print(f"\n{c['id']} · {c['titulo']}\n  Incidencia: {c['incidencia'][:300]}")
    try:
        r = input("  ¿Tienes recomendación? Pégala y Enter (Enter en blanco = la propone el modelo): ").strip()
    except EOFError:
        return None
    return r or None


def cmd_recomendar(args):
    from .acciones import accion_recomendar
    return accion_recomendar(_contexto(args), ids=args.ids or None,
                             preguntar=None if args.auto else _preguntar_recomendacion,
                             formatear=args.formatear, solo_aprobadas=not args.todas)


def cmd_redactar_conclusiones(args):
    from .acciones import accion_redactar_conclusiones
    return accion_redactar_conclusiones(_contexto(args))


def cmd_revisar(args):
    from .acciones import accion_revisar
    return accion_revisar(_contexto(args))


def cmd_corregir(args):
    from .acciones import accion_corregir
    return accion_corregir(_contexto(args), incluir_avisos=args.avisos)


def cmd_condensar(args):
    from .acciones import accion_condensar
    return accion_condensar(_contexto(args), objetivo=args.objetivo)


def cmd_aplicar_cambios(args):
    from .acciones import accion_aplicar_cambios
    return accion_aplicar_cambios(_contexto(args), solo_plan=args.solo_plan)


def cmd_reunion(args):
    from .acciones import accion_reunion
    return accion_reunion(_contexto(args), args.transcripcion, aplicar=args.aplicar)


def cmd_cambio(args):
    from .acciones import accion_aplicar_cambios
    mensaje = " ".join(args.mensaje).strip()
    if mensaje == "-" or not mensaje:
        mensaje = sys.stdin.read().strip()
    return accion_aplicar_cambios(_contexto(args), solo_plan=args.solo_plan, instrucciones=mensaje, origen="mensaje")


def cmd_chat(args):
    """Cambios sencillos como en un chat: cada mensaje se aplica al informe y
    se muestra el diff. `deshacer`, `diff`, `estado` y `salir` son atajos."""
    from .acciones import accion_aplicar_cambios, accion_deshacer, accion_diff
    ctx = _contexto(args)
    print(f"Chat de cambios sobre {ctx.exp.archivo('informe').name} (Enter vacío o `salir` para terminar; "
          "`deshacer`, `diff`, `estado` como atajos).")
    while True:
        try:
            mensaje = input("\ncambio> ").strip()
        except (EOFError, KeyboardInterrupt):
            return "\nHasta luego."
        if mensaje.lower() in ("", "salir", "exit", "q"):
            return "Hasta luego."
        try:
            if mensaje.lower() == "deshacer":
                print(accion_deshacer(ctx.exp))
            elif mensaje.lower() == "diff":
                print(accion_diff(ctx.exp))
            elif mensaje.lower() == "estado":
                print(cmd_estado(args))
            else:
                print(accion_aplicar_cambios(ctx, instrucciones=mensaje, origen="chat"))
        except Exception as exc:  # noqa: BLE001 — el chat no debe morir por un error de acción
            print(f"✖ {exc}")


def cmd_ppt(args):
    from .acciones import accion_ppt
    return accion_ppt(_abrir(args))


def cmd_archivar(args):
    from .acciones import accion_archivar
    return accion_archivar(_abrir(args))


def cmd_calibrar_estilo(args):
    from .calibracion import calibrar
    from .llm import ClienteLLM
    from .style_checker import StyleChecker
    carpeta = Path(args.carpeta)
    if not carpeta.is_dir():
        sys.exit(f"{carpeta} no es una carpeta.")
    salida = Path(args.salida) if args.salida else carpeta / "calibracion_estilo.md"
    trazas = salida.with_name(salida.stem + "_trazas")

    def trazar(accion, registro):
        import json
        trazas.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        (trazas / f"{datetime.now():%Y-%m-%dT%H-%M-%S}_{accion}.json").write_text(
            json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")

    llm = None
    if not args.sin_llm:
        try:
            llm = ClienteLLM(modelo=args.modelo, proveedor=args.proveedor, trazador=trazar, esfuerzo=args.esfuerzo)
        except Exception as exc:  # noqa: BLE001
            print(f"(LLM no disponible: {exc}; solo análisis determinista)", file=sys.stderr)
    return calibrar(carpeta, StyleChecker(args.config), llm, salida)


def cmd_diff(args):
    from .acciones import accion_diff
    return accion_diff(_abrir(args), args.fichero)


def cmd_deshacer(args):
    from .acciones import accion_deshacer
    return accion_deshacer(_abrir(args), args.fichero)


def cmd_historial(args):
    from .acciones import accion_historial
    return accion_historial(_abrir(args))


def cmd_web(args):
    """Servidor web: API REST + front compilado (frontend/dist)."""
    import uvicorn
    from .api import DIST
    if not DIST.exists():
        print("Aviso: frontend/dist no existe (compila el front con `npm run build` en frontend/); la API sí está disponible en /api.",
              file=sys.stderr)
    print(f"Revisor de informes en http://{args.host}:{args.puerto}  (Ctrl+C para parar)")
    uvicorn.run("audit_agent.api:app", host=args.host, port=args.puerto, log_level="info")
    return ""


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
    ("redactar-contexto", "Introducción y resumen ejecutivo desde contexto/ y papeles_trabajo/ (LLM)", cmd_redactar_contexto, {"secciones": None, "forzar": False}),
    ("extraer", "Extraer conclusiones y sugerencias de mejora de todas las pruebas (LLM)", cmd_extraer, {"forzar": False}),
    ("aprobar todas", "Aprobar todas las conclusiones", cmd_aprobar, {"ids": ["todas"], "estado": "aprobada"}),
    ("revisar-conclusiones", "Revisar vocabulario y campos de las conclusiones", cmd_revisar_conclusiones, {}),
    ("corregir-conclusiones", "Corregir con el modelo solo lo señalado (LLM)", cmd_corregir_conclusiones, {"ids": None}),
    ("recomendar", "Recomendaciones: pregunta al auditor; si no la tiene, la propone (LLM)", cmd_recomendar, {"ids": None, "auto": False, "formatear": False, "todas": False}),
    ("redactar-conclusiones", "Volcar las conclusiones aprobadas al informe (sin modelo)", cmd_redactar_conclusiones, {}),
    ("revisar", "Revisar vocabulario prohibido y estilo del informe", cmd_revisar, {}),
    ("corregir", "Reescribir con el modelo los párrafos con errores (LLM)", cmd_corregir, {"avisos": False}),
    ("condensar", "Acortar un poco el informe conservando hechos y cifras (LLM)", cmd_condensar, {"objetivo": 0.85}),
    ("aplicar-cambios", "Aplicar las instrucciones de 03_instrucciones.md al informe (LLM)", cmd_aplicar_cambios, {"solo_plan": False}),
    ("reunion", "Analizar una transcripción de Teams: cambios de texto vs PPT (LLM)", cmd_reunion, {"transcripcion": None, "aplicar": False}),
    ("chat", "Cambios sencillos tipo chat, aplicados al momento (LLM)", cmd_chat, {}),
    ("diff", "Ver cambios del informe respecto a la última versión guardada", cmd_diff, {"fichero": "informe"}),
    ("deshacer", "Restaurar la versión anterior del informe", cmd_deshacer, {"fichero": "informe"}),
    ("ppt", "Exportar el informe entero a PowerPoint (un apartado = una diapositiva)", cmd_ppt, {}),
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
        if nombre == "extraer" and _abrir(args).existe("conclusiones"):
            sub.forzar = input("01_conclusiones.md ya existe. ¿Regenerar? (se guarda snapshot) [s/N] ").strip().lower() == "s"
            if not sub.forzar:
                continue
        if nombre == "reunion":
            sub.transcripcion = input("Ruta de la transcripción (.txt/.docx/.vtt): ").strip()
            if not sub.transcripcion:
                continue
        if nombre == "redactar-contexto" and _abrir(args).existe("informe"):
            sub.forzar = input("02_informe.md ya tiene introducción/resumen. ¿Regenerarlos? (se guarda snapshot) [s/N] ").strip().lower() == "s"
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
    s.add_argument("--ejemplo", action="store_true", help="Copiar el papel de trabajo y el contexto de ejemplo")

    s = sub.add_parser("usar", help="Fijar el expediente activo"); s.set_defaults(fn=cmd_usar); s.add_argument("ruta")
    sub.add_parser("estado", help="Estado y siguiente paso").set_defaults(fn=cmd_estado)
    s = sub.add_parser("eliminar", help="Eliminar un expediente (pide escribir su referencia)"); s.set_defaults(fn=cmd_eliminar)
    s.add_argument("--confirmar", help="Referencia del expediente, para no preguntar (scripts)")
    sub.add_parser("menu", help="Menú interactivo").set_defaults(fn=cmd_menu)

    s = sub.add_parser("redactar-contexto", help="Introducción y resumen ejecutivo desde contexto/ y papeles_trabajo/ (LLM)"); s.set_defaults(fn=cmd_redactar_contexto)
    s.add_argument("--forzar", action="store_true", help="Regenerar aunque ya existan")
    s.add_argument("--secciones", nargs="+", help="Rehacer solo: introduccion resumen")
    s = sub.add_parser("extraer", help="Conclusiones y sugerencias de mejora desde papeles_trabajo/ (LLM)"); s.set_defaults(fn=cmd_extraer)
    s.add_argument("--forzar", action="store_true")
    s = sub.add_parser("aprobar", help="Marcar conclusiones como aprobadas (valida el nivel de riesgo)"); s.set_defaults(fn=cmd_aprobar, estado="aprobada")
    s.add_argument("ids", nargs="+", help="C-01 C-02 … o `todas`")
    s = sub.add_parser("descartar", help="Marcar conclusiones como descartadas"); s.set_defaults(fn=cmd_aprobar, estado="descartada")
    s.add_argument("ids", nargs="+")
    s = sub.add_parser("proponer", help="Devolver conclusiones a estado propuesta"); s.set_defaults(fn=cmd_aprobar, estado="propuesta")
    s.add_argument("ids", nargs="+")
    sub.add_parser("revisar-conclusiones", help="Reglas deterministas sobre las conclusiones").set_defaults(fn=cmd_revisar_conclusiones)
    s = sub.add_parser("corregir-conclusiones", help="Corregir con LLM lo señalado por las reglas"); s.set_defaults(fn=cmd_corregir_conclusiones)
    s.add_argument("ids", nargs="*")
    s = sub.add_parser("regenerar", help="Rehacer una conclusión según «Notas del auditor» (LLM)"); s.set_defaults(fn=cmd_regenerar)
    s.add_argument("id")
    s = sub.add_parser("recomendar", help="Recomendaciones: respeta las del auditor, propone las que falten (LLM)"); s.set_defaults(fn=cmd_recomendar)
    s.add_argument("ids", nargs="*")
    s.add_argument("--auto", action="store_true", help="No preguntar: proponer con el modelo las que falten")
    s.add_argument("--formatear", action="store_true", help="Dar formato (sin cambiar la base) a las aportadas por el auditor")
    s.add_argument("--todas", action="store_true", help="Incluir también las conclusiones en estado propuesta")
    sub.add_parser("redactar-conclusiones", help="Volcar las conclusiones aprobadas al informe (sin modelo)").set_defaults(fn=cmd_redactar_conclusiones)
    sub.add_parser("revisar", help="Vocabulario prohibido y estilo del informe").set_defaults(fn=cmd_revisar)
    s = sub.add_parser("corregir", help="Reescribir con LLM los párrafos con errores"); s.set_defaults(fn=cmd_corregir)
    s.add_argument("--avisos", action="store_true", help="Incluir también avisos (frases largas)")
    s = sub.add_parser("condensar", help="Acortar un poco el informe con LLM (mismos hechos y cifras; la recomendación no se toca)"); s.set_defaults(fn=cmd_condensar)
    s.add_argument("--objetivo", type=float, default=0.85, help="Fracción de palabras a conservar (0.85 = un 15 %% menos)")
    s = sub.add_parser("aplicar-cambios", help="Aplicar 03_instrucciones.md al informe (LLM)"); s.set_defaults(fn=cmd_aplicar_cambios)
    s.add_argument("--solo-plan", action="store_true", help="Mostrar el plan sin tocar el informe")
    s = sub.add_parser("reunion", help="Transcripción de Teams → acta: cambios de texto (a 03_instrucciones.md) y de PPT (informativo)")
    s.set_defaults(fn=cmd_reunion)
    s.add_argument("transcripcion", help="Fichero de la transcripción (.txt, .docx, .vtt…)")
    s.add_argument("--aplicar", action="store_true", help="Aplicar directamente los cambios de texto detectados")
    s = sub.add_parser("cambio", help="Aplicar un cambio sencillo escrito como mensaje (LLM)"); s.set_defaults(fn=cmd_cambio)
    s.add_argument("mensaje", nargs="*", help="Texto del cambio; `-` o vacío para leerlo de stdin")
    s.add_argument("--solo-plan", action="store_true")
    sub.add_parser("chat", help="Cambios sencillos en modo chat sobre el informe (LLM)").set_defaults(fn=cmd_chat)
    sub.add_parser("ppt", help="Exportar el informe entero a PowerPoint (un apartado = una diapositiva)").set_defaults(fn=cmd_ppt)
    sub.add_parser("archivar", help="Zip de evidencia del expediente con manifest sha256").set_defaults(fn=cmd_archivar)

    s = sub.add_parser("calibrar-estilo", help="Contrastar estilo.yaml con informes aprobados (no modifica el YAML)")
    s.set_defaults(fn=cmd_calibrar_estilo)
    s.add_argument("carpeta", help="Carpeta con informes aprobados (y opcionalmente *_borrador.*)")
    s.add_argument("--salida", help="Ruta del informe Markdown (por defecto <carpeta>/calibracion_estilo.md)")
    s.add_argument("--sin-llm", action="store_true", help="Solo falsos positivos deterministas")

    for nombre, fn in (("diff", cmd_diff), ("deshacer", cmd_deshacer)):
        s = sub.add_parser(nombre); s.set_defaults(fn=fn)
        s.add_argument("fichero", nargs="?", default="informe", choices=["informe", "conclusiones", "instrucciones"])
    sub.add_parser("historial", help="Versiones guardadas").set_defaults(fn=cmd_historial)

    s = sub.add_parser("web", help="Arrancar el servidor web (API + front)"); s.set_defaults(fn=cmd_web)
    s.add_argument("--puerto", type=int, default=8000); s.add_argument("--host", default="127.0.0.1")
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
