"""
Demo del flujo completo sobre el papel de trabajo de ejemplo.

    .venv/bin/python demo.py            (o ./revisor … paso a paso)

Crea expedientes/DEMO-CNC-2026-03, extrae observaciones con el modelo,
las aprueba todas, redacta el informe, lo revisa, aplica una instrucción
de cambio de ejemplo y genera el PPT. Requiere credenciales KAIA (o
ANTHROPIC_API_KEY) en .env; sin ellas se detiene en `extraer` con un
mensaje claro.
"""
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")

from audit_agent.cli import main  # noqa: E402

RUTA = RAIZ / "expedientes" / "DEMO-CNC-2026-03"


def paso(titulo, argv):
    print("\n" + "=" * 78 + f"\n{titulo}\n" + "=" * 78)
    if main(argv) != 0:
        sys.exit("Demo interrumpida.")


if RUTA.exists():
    shutil.rmtree(RUTA)
E = ["-e", str(RUTA)]
paso("1. Crear expediente con el papel de trabajo de ejemplo",
     ["nuevo", str(RUTA), "--nombre", "Auditoría de Compras No Comerciales", "--referencia", "DEMO-CNC-2026-03",
      "--fecha", "Mayo 2026", "--distribucion", "Dirección de Compras, Dirección Financiera, Comité de Auditoría",
      "--ejemplo"])
paso("2. Estado", E + ["estado"])
paso("3. Extraer observaciones y recomendaciones (LLM)", E + ["extraer"])
paso("4. Revisar observaciones (reglas deterministas)", E + ["revisar-obs"])
paso("5. Aprobar todas (en uso real: el auditor edita y aprueba una a una)", E + ["aprobar", "todas"])
paso("6. Redactar el informe (LLM)", E + ["redactar"])
paso("7. Revisar vocabulario y estilo del informe", E + ["revisar"])

instr = RUTA / "03_instrucciones.md"
instr.write_text(instr.read_text(encoding="utf-8") + """
Transcripción (extracto) de la reunión de cierre con el Gerente, 26/05:

GERENTE: La observación de segregación de funciones tiene que quedar como riesgo Alto, y el
responsable del plan de acción es solo Dirección de Sistemas, no compartido con Compras.
AUDITOR: De acuerdo.
GERENTE: En próximos pasos añade que el seguimiento se hará en el primer trimestre de 2027.
Y la conclusión global es demasiado larga, resúmela en un párrafo.
""", encoding="utf-8")
paso("8. Aplicar cambios desde la transcripción de una reunión (LLM)", E + ["aplicar-cambios"])
paso("9. Generar el Resumen Ejecutivo (PPT)", E + ["ppt"])
paso("10. Estado final", E + ["estado"])
print(f"\nDemo completada. Abre {RUTA} en el editor para ver los ficheros de trabajo.")
