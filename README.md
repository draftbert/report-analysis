# Revisor de informes de auditoría interna — v0.3 (espacio de trabajo)

Herramienta de apoyo a la redacción del informe una vez terminado el trabajo de
campo: a partir del **papel de trabajo final** (todas las pruebas, con su
contexto, objetivo, pruebas realizadas y conclusiones) y del contexto de la
auditoría, redacta la **introducción y el resumen ejecutivo**, extrae el
**detalle de conclusiones** (incidencia detectada → causa raíz → cómo se ha
llegado → consecuencias) y las **sugerencias de mejora**, gestiona las
**recomendaciones** respetando las del auditor, y acompaña la edición durante
los días que dure el trabajo: vocabulario prohibido, reescritura dirigida,
aplicación de comentarios de una reunión, historial de versiones, PowerPoint y
archivo de evidencia.

**Principio:** el modelo propone, el auditor decide. Nada se escribe en Pentana
ni se emite sin revisión humana. Las reglas de estilo son deterministas
(`config/estilo.yaml`); el LLM (KAIA, `gpt-5-mini` por defecto) se usa para
extraer, redactar y reescribir, y su salida vuelve a pasar por las reglas.
Toda llamada al modelo queda trazada en `trazas/` con su prompt, respuesta y tokens.

## Instalación

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.ejemplo .env      # y rellenar las credenciales KAIA_*
```

`./revisor` es el lanzador (`./revisor <comando>`); equivale a
`.venv/bin/python -m audit_agent.cli <comando>`. En Windows: `.venv\Scripts\python -m audit_agent.cli …`.

## El espacio de trabajo: un expediente por auditoría

Todo el estado vive en una carpeta de ficheros de texto que se editan con
cualquier editor (VS Code es ideal: vista previa Markdown + terminal al lado):

```
expedientes/CNC-2026-03/
  expediente.yaml         nombre, referencia, fecha, distribución, notas para el modelo
  entrada/                papel de trabajo final, contexto de la auditoría, anexos (.md, .txt, .docx, .xlsx, .pdf)
  01_conclusiones.md      conclusiones y sugerencias propuestas → el auditor edita, aprueba y recomienda
  02_informe.md           el informe: introducción · resumen ejecutivo · detalle de conclusiones · sugerencias
                          (cada apartado se escribe como se leerá en su diapositiva; `ppt` lo exporta 1:1)
  03_instrucciones.md     buzón: pega la transcripción / comentarios → `aplicar-cambios`
  revision.md             hallazgos de vocabulario y estilo (acumulado)
  cambios_aplicados.md    qué cambios pidió el modelo y cuáles se aplicaron
  historial/              snapshot automático antes de cada sobreescritura (`diff`, `deshacer`)
  salidas/                ResumenEjecutivo_<REF>.pptx
  trazas/                 una entrada JSON por llamada al LLM (y el texto leído de entrada/)
  <REF>_archivo_<fecha>.zip  evidencia archivada al cierre (`archivar`)
```

## Flujo de trabajo

Estructura del informe: **Introducción → Resumen ejecutivo → Detalle de
conclusiones → Sugerencias de mejora**. Cada conclusión sigue siempre la misma
estructura: qué incidencia se ha detectado, por qué ha pasado (causa raíz),
cómo se ha llegado a ella (datos, tablas), consecuencias y recomendación.

```bash
./revisor nuevo expedientes/TEC-2026 --nombre "Auditoría de Transporte e-Commerce" \
         --referencia TEC-2026 --distribucion "Dirección de Transporte, Comité de Auditoría"
#   → copia a entrada/ el papel de trabajo final (todas las pruebas), el contexto de la
#     auditoría, anexos, design thinking… Se admite texto pegado desde Excel.

./revisor estado            # en cualquier momento: fase actual y siguiente paso sugerido
./revisor menu              # lo mismo, con menú numerado

# 1. Contexto del informe
./revisor redactar-contexto          # introducción + resumen ejecutivo desde entrada/ → 02_informe.md
#   El auditor los lee y edita hasta que encajen (`--secciones resumen` rehace solo una).

# 2. Conclusiones y sugerencias de mejora
./revisor extraer                    # recorre todas las pruebas; solo las concluidas CON INCIDENCIAS.
#   Por defecto UNA conclusión por prueba (sintetiza su bloque CONCLUSIONES); varias solo si son
#   incidencias independientes. El registro y el nivel de detalle se guían por el ejemplo de
#   referencia config/ejemplo_conclusion.md (editable por el equipo; sus cifras no se reutilizan).
#   → 01_conclusiones.md: por incidencia, Tipo (conclusion|sugerencia), Prueba, riesgo, Área /
#     Responsable / Plazo / Ref. recomendación, y los bloques Incidencia / Causa raíz /
#     Cómo se ha llegado (viñetas con datos) / Consecuencias / Recomendación (varias = varios párrafos).
#   Si el PT no habla de severidad, el riesgo lleva "(propuesto por el modelo, sin evidencia en PT)":
#   `aprobar` quita la coletilla (el auditor lo ha validado).
./revisor aprobar C-01 C-03          # o `aprobar todas`, `descartar C-04`
./revisor recomendar                 # por cada aprobada sin recomendación pregunta al auditor:
#   si la tiene, se registra tal cual (100 % respetada; `--formatear` solo le da formato y se verifica
#   que conserva la base); si no, el modelo la propone y, si procede, una sugerencia de mejora.
#   `--auto` no pregunta. Las recomendaciones que ya vienen del PT se respetan siempre.
./revisor revisar-conclusiones       # vocabulario prohibido + campos (sin LLM)
./revisor corregir-conclusiones      # el modelo corrige solo lo señalado (nunca la recomendación)
./revisor regenerar C-02             # rehace una según «Notas del auditor»
./revisor redactar-conclusiones      # vuelca las aprobadas al informe TAL CUAL (sin modelo), ya como apartados
#   con la lectura de la diapositiva: prosa, «detalles descriptivos» en viñetas, consecuencias, Recomendación N.1…
./revisor redactar-contexto --secciones resumen   # opcional: resumen ejecutivo con las conclusiones validadas

# 3. Cambios durante la revisión (Gerente, Directora, reunión con el área)
#   Pega en 03_instrucciones.md la transcripción / comentarios y…
./revisor aplicar-cambios [--solo-plan]   # cambios concretos, aplicados y registrados
./revisor revisar | corregir [--avisos]   # vocabulario prohibido y estilo del informe
./revisor diff | deshacer | historial     # control de versiones

# 4. Entregable y cierre
./revisor ppt                        # exporta el informe ENTERO: cada apartado de 02_informe.md es una
#   diapositiva (introducción, resumen, una por conclusión con el diseño corporativo de «Detalle de
#   conclusiones» —banda de riesgo, título numerado, prosa, detalles descriptivos, consecuencias,
#   Recomendación N.1/N.2, Ref., Área/Responsable/Plazo—, y las sugerencias de mejora)
./revisor archivar                   # zip de evidencia con manifest sha256

# Texto suelto (p. ej. un párrafo copiado de Pentana), sin expediente:
./revisor revisar-texto --fichero borrador.txt [--sin-llm]
```

`.venv/bin/python demo.py` ejecuta el flujo completo sobre el papel de trabajo de
ejemplo `ejemplos/papel_trabajo_tarifarios.txt` (crea `expedientes/DEMO-TEC-2026`).

Con varios expedientes, fija el activo con `./revisor usar <ruta>` o pásalo con `-e <ruta>`.

## Configuración del LLM (.env)

| Variable | Uso |
|---|---|
| `KAIA_TENANT_ID`, `KAIA_CLIENT_ID`, `KAIA_CLIENT_SECRET`, `KAIA_RESOURCE`, `KAIA_AGENT_BASE_URL` | Credenciales del agente KAIA (OAuth2 client-credentials contra Azure AD) |
| `KAIA_AGENT_MODEL_NAME` | Modelo (`gpt-5-mini` por defecto; `--modelo` lo cambia por comando) |
| `KAIA_AGENT_TEMPERATURE` | Solo se envía a modelos no-reasoning (los `gpt-5*` la rechazan) |
| `LLM_REASONING_EFFORT` | `minimal/low/medium/high` para `gpt-5*` (por defecto `medium`; `corregir` usa `low`) |
| `LLM_PROVEEDOR` | `kaia` (defecto si hay credenciales), `anthropic` (requiere `ANTHROPIC_API_KEY` y `pip install anthropic`) o `dry-run` |

Sin proveedor configurado, todo lo determinista sigue funcionando
(`estado`, `revisar`, `revisar-conclusiones`, `aprobar`, `redactar-conclusiones`, `diff`, `deshacer`, `ppt`, `archivar`).

## Entrada: exportaciones de Pentana

`entrada/` admite `.md`, `.txt` (incluido texto pegado desde Excel: se normalizan
tabulaciones y celdas entre comillas), `.docx` (tablas conservadas como tablas Markdown),
`.xlsx` (cada hoja como sección; bloques tabulares como tablas, celdas largas como
párrafos) y `.pdf` con capa de texto (sin OCR: un PDF escaneado da un error claro
pidiendo otra exportación). La capa de lectura está en `audit_agent/lectores.py`:
dada una ruta devuelve Markdown normalizado conservando la estructura que exista,
sin inventar secciones. Cada `extraer` deja en `trazas/*_extraer-entrada.json` qué
lector se usó y el texto exacto enviado al modelo, para auditar la fidelidad de la
lectura. Cuando se conozca el formato real de Pentana, añadir un lector es una
función más registrada en `LECTORES`. `scripts/generar_ejemplos_entrada.py` genera
los ficheros sintéticos de `ejemplos/entrada_sintetica/` usados en los tests.

## Trazabilidad y retención

- `trazas/` guarda, por cada llamada al modelo, un JSON con fecha, acción, modelo,
  prompt completo, respuesta estructurada y tokens; y por cada lectura de
  `entrada/`, el texto normalizado enviado. Es la evidencia de **cómo se redactó
  cada conclusión**.
- `historial/` guarda cada versión anterior de los ficheros de trabajo antes de que
  la herramienta los sobreescriba (`diff`, `deshacer`).
- Ninguna de las dos carpetas se versiona en git (`.gitignore`): contienen datos del
  trabajo y crecen con el uso.
- Al cerrar el trabajo, `./revisor archivar` genera `<REF>_archivo_<fecha>.zip` con
  `trazas/`, `historial/`, `expediente.yaml`, los tres Markdown de trabajo,
  `revision.md`, `cambios_aplicados.md` y `salidas/`, más un `manifest.json` con la
  lista de ficheros y el sha256 de cada uno. Ese zip se adjunta al expediente en
  Pentana; la integridad se demuestra recalculando los hashes contra el manifiesto
  (`audit_agent.acciones.verificar_archivo`). `estado` sugiere archivar cuando el
  PPT está generado y al día.

## Calibración del criterio de estilo con informes reales

Las palabras prohibidas iniciales son plausibles pero inventadas. Para calibrarlas
con el criterio real del departamento:

```bash
./revisor calibrar-estilo <carpeta_con_informes_aprobados> [--salida calibracion.md] [--sin-llm]
```

La carpeta contiene informes ya aprobados por Dirección (Markdown, texto, Word,
Excel o PDF con texto). Si además hay borradores previos con el mismo nombre y
sufijo `_borrador` (p. ej. `informe_X_borrador.docx` junto a `informe_X.docx`), se
comparan por parejas. El comando produce `calibracion_estilo.md` con:

- **(a) Falsos positivos** (determinista): términos de `estilo.yaml` que SÍ aparecen
  en informes aprobados, con recuento, ficheros y contexto — señal de que la regla
  sobra o necesita excepción. También la proporción de frases que superan el límite.
- **(b) Propuestas del modelo** (salida estructurada): altas, bajas y modificaciones
  de reglas, cada una con evidencia literal del corpus y nivel de confianza, más los
  patrones de estilo observados.

El comando **nunca modifica `config/estilo.yaml`**: el equipo revisa el informe y
edita el YAML a mano. Ejemplo con el corpus de prueba del repo:
`./revisor calibrar-estilo ejemplos/corpus_calibracion`.

## Tests

```bash
.venv/bin/python -m pytest -q tests
```

Deterministas y sin red (el LLM se sustituye por respuestas preparadas):
formato Markdown de ida y vuelta, riesgo propuesto/validado, recomendaciones (respeto de las del
auditor), suite de sustituciones ambiguas de `aplicar-cambios`
(`tests/test_aplicar_cambios.py`, que crece con cada caso raro visto en uso real),
archivado con hashes y lectores de entrada.

## Mantenimiento del criterio de estilo

Todo el criterio vive en `config/estilo.yaml`: palabras prohibidas con
sugerencia y motivo, expresiones en primera persona, longitud máxima de frase y
estructura obligatoria de la conclusión. Se inyecta automáticamente en los
prompts, así que ampliar el YAML cambia a la vez lo que se detecta y lo que el
modelo evita al redactar.

## Estructura del código

```
config/estilo.yaml          Criterio de estilo (editable por el equipo)
config/ejemplo_conclusion.md  Ejemplo de referencia de una conclusión (registro objetivo; se inyecta en `extraer`)
audit_agent/expediente.py   Carpeta de trabajo: ficheros, snapshots, trazas
audit_agent/formato_md.py   Markdown de ida y vuelta (render ↔ parse) de conclusiones e informe
audit_agent/acciones.py     Las acciones del flujo (redactar-contexto, extraer, recomendar, redactar-conclusiones, aplicar-cambios, ppt…)
audit_agent/esquemas.py     Salidas estructuradas del LLM (Pydantic) — formato pivote
audit_agent/style_checker.py  Reglas deterministas (texto y Markdown)
audit_agent/lectores.py     Lectura de entrada/ (.md/.txt/.docx/.xlsx/.pdf) a Markdown normalizado
audit_agent/calibracion.py  Calibración de estilo.yaml contra informes aprobados
audit_agent/llm.py          Cliente LLM unificado (kaia | anthropic | dry-run) con trazas
audit_agent/kaia_client.py  Transporte KAIA (OAuth2 + invoke con output_format_schema)
audit_agent/reviewer.py     Revisión de texto suelto
audit_agent/ppt_builder.py  Presentación del informe (PPT)
audit_agent/cli.py          Comandos y menú interactivo
ejemplos/                   Papel de trabajo real (tarifarios), borrador, entrada sintética y corpus de calibración
scripts/                    Generación de ficheros de entrada sintéticos
tests/                      Suite determinista (pytest)
docs/referencia/            Proveedor KAIA original de audit-engine (referencia)
```

## Siguientes pasos

- Sustituir el PPT autónomo por la plantilla `.potx` corporativa (mismo código;
  asignar `run.text`, nunca `text_frame.text`).
- Añadir el lector específico del formato real de exportación de Pentana en `lectores.py`.
- Calibrar `estilo.yaml` con informes aprobados reales (`calibrar-estilo`).
- Memoria histórica: sugerir conclusiones similares de auditorías cerradas.
- Interfaz web (Streamlit) sobre las mismas acciones si el equipo no quiere terminal.
