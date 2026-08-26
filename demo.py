"""
Demo del flujo completo sobre el papel de trabajo de ejemplo (prueba 2.11,
tarifarios y SCA, pegado desde Excel).

    .venv/bin/python demo.py            (o ./revisor … paso a paso)

Crea expedientes/DEMO-TEC-2026, redacta introducción y resumen ejecutivo,
extrae las conclusiones, las aprueba, obtiene recomendaciones (respetando la
que ya trae el papel de trabajo), las vuelca al informe, aplica una
instrucción de cambio de ejemplo, genera el PPT y archiva la evidencia.
Requiere credenciales KAIA (o ANTHROPIC_API_KEY) en .env.
"""
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")

from audit_agent.cli import main  # noqa: E402

RUTA = RAIZ / "expedientes" / "DEMO-TEC-2026"


def paso(titulo, argv):
    print("\n" + "=" * 78 + f"\n{titulo}\n" + "=" * 78)
    if main(argv) != 0:
        sys.exit("Demo interrumpida.")


if RUTA.exists():
    shutil.rmtree(RUTA)
E = ["-e", str(RUTA)]
paso("1. Crear expediente; copiar el design thinking a contexto/ y el papel de trabajo final a papeles_trabajo/",
     ["nuevo", str(RUTA), "--nombre", "Auditoría de Transporte e-Commerce: tarifarios y SCA", "--referencia", "DEMO-TEC-2026",
      "--fecha", "Junio 2026", "--distribucion", "Dirección de Transporte e-Commerce, Dirección Financiera, Comité de Auditoría"])
shutil.copy(RAIZ / "ejemplos" / "contexto_auditoria_tarifarios.md", RUTA / "contexto")
shutil.copy(RAIZ / "ejemplos" / "papel_trabajo_tarifarios.txt", RUTA / "papeles_trabajo")
(RAIZ / ".expediente_activo").unlink(missing_ok=True)
paso("2. Estado", E + ["estado"])
paso("3. Introducción y resumen ejecutivo (LLM)", E + ["redactar-contexto"])
paso("4. Extraer conclusiones y sugerencias de mejora (LLM)", E + ["extraer"])
paso("5. Revisar conclusiones (reglas deterministas)", E + ["revisar-conclusiones"])
paso("6. Aprobar todas (en uso real: el auditor edita y aprueba una a una)", E + ["aprobar", "todas"])
paso("7. Recomendaciones: se respetan las del PT/auditor, se proponen las que faltan (LLM)", E + ["recomendar", "--auto"])
paso("8. Volcar las conclusiones aprobadas al informe (sin modelo)", E + ["redactar-conclusiones"])
paso("9. Resumen ejecutivo con las conclusiones validadas (LLM)", E + ["redactar-contexto", "--secciones", "resumen"])

instr = RUTA / "03_instrucciones.md"
instr.write_text(instr.read_text(encoding="utf-8") + """
Reunión de cierre con el Gerente:
GERENTE: La conclusión sobre los acuerdos con proveedores que no se transparentan al equipo de validación
queda como riesgo Alto y el responsable del plan de acción es Operativa e-Commerce. En el resumen ejecutivo
menciona explícitamente que la recomendación TMSCIIF-10 sigue abierta. Y añade el importe anual facturado
por los couriers en la introducción.
""", encoding="utf-8")
paso("10. Aplicar cambios desde la transcripción de una reunión (LLM)", E + ["aplicar-cambios"])
paso("11. Generar la presentación (PPT)", E + ["ppt"])
paso("12. Archivar la evidencia", E + ["archivar"])
paso("13. Estado final", E + ["estado"])
print(f"\nDemo completada. Abre {RUTA} en el editor para ver los ficheros de trabajo.")
