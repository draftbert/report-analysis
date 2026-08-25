# Revisor de informes de auditoría interna — v0.2 (espacio de trabajo)

Herramienta de apoyo a las fases 7–9 del proceso de auditoría: a partir de los
papeles de trabajo exportados de Pentana, **propone observaciones y
recomendaciones**, **redacta el informe** con las que el auditor aprueba, y
acompaña la edición durante los días que dure el trabajo: revisión de
vocabulario prohibido, reescritura dirigida, aplicación de comentarios de una
reunión, historial de versiones y generación del Resumen Ejecutivo en PowerPoint.

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
  entrada/                papeles de trabajo de Pentana (.md, .txt, .docx, .xlsx, .pdf con texto)
  01_observaciones.md     propuestas del modelo → el auditor edita y marca `Estado: aprobada`
  02_informe.md           texto del informe → se edita durante días
  03_instrucciones.md     buzón: pega la transcripción / comentarios → `aplicar-cambios`
  revision.md             hallazgos de vocabulario y estilo (acumulado)
  cambios_aplicados.md    qué cambios pidió el modelo y cuáles se aplicaron
  historial/              snapshot automático antes de cada sobreescritura (`diff`, `deshacer`)
  salidas/                ResumenEjecutivo_<REF>.pptx
  trazas/                 una entrada JSON por llamada al LLM (y el texto leído de entrada/)
  <REF>_archivo_<fecha>.zip  evidencia archivada al cierre (`archivar`)
```

## Flujo de trabajo

```bash
./revisor nuevo expedientes/CNC-2026-03 --nombre "Auditoría de Compras No Comerciales" \
         --referencia CNC-2026-03 --distribucion "Dirección de Compras, Comité de Auditoría"
#   → copia los papeles de trabajo a expedientes/CNC-2026-03/entrada/

./revisor estado            # en cualquier momento: fase actual y siguiente paso sugerido
./revisor menu              # lo mismo, con menú numerado (para no memorizar comandos)

# 1. Observaciones y recomendaciones
./revisor extraer           # el modelo propone → 01_observaciones.md
#   El auditor lee, corrige el texto, y en cada bloque pone Estado: aprobada / descartada.
#   Si el papel de trabajo no habla de severidad, el nivel de riesgo aparece como
#   "Medio (propuesto por el modelo, sin evidencia en PT)": `aprobar` quita la coletilla
#   (el auditor lo ha validado) y `redactar` no admite observaciones que la conserven.
#   Si quiere que el modelo rehaga una: escribe en «Notas del auditor» y…
./revisor regenerar-obs OBS-02
./revisor aprobar OBS-01 OBS-03      # o `aprobar todas`, `descartar OBS-04`
./revisor revisar-obs                # vocabulario prohibido + campos vacíos (sin LLM)
./revisor corregir-obs               # el modelo corrige solo lo señalado y se re-verifica

# 2. Informe
./revisor redactar                   # con las aprobadas → 02_informe.md
./revisor redactar --secciones evaluacion proximos   # rehacer solo algunas secciones
#   ... días de edición del informe en el editor ...
./revisor revisar                    # vocabulario prohibido y estilo, con nº de línea → revision.md
./revisor corregir [--avisos]        # reescribe solo los párrafos con errores; muestra el diff
#   Pega en 03_instrucciones.md la transcripción de la reunión / comentarios del Gerente y…
./revisor aplicar-cambios [--solo-plan]   # cambios concretos, aplicados y registrados
./revisor diff | deshacer | historial     # control de versiones del informe

# 3. Entregable y cierre
./revisor ppt                        # salidas/ResumenEjecutivo_CNC-2026-03.pptx
./revisor archivar                   # zip de evidencia con manifest sha256 (ver Trazabilidad y retención)

# Texto suelto (p. ej. una observación copiada de Pentana), sin expediente:
./revisor revisar-texto --fichero borrador.txt [--sin-llm]
```

`.venv/bin/python demo.py` ejecuta el flujo completo sobre el ejemplo incluido
(crea `expedientes/DEMO-CNC-2026-03`).

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
(`estado`, `revisar`, `revisar-obs`, `aprobar`, `diff`, `deshacer`, `ppt`).

## Entrada: exportaciones de Pentana

`entrada/` admite `.md`, `.txt`, `.docx` (tablas conservadas como tablas Markdown),
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
  cada observación**.
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
riesgo propuesto/validado, suite de sustituciones ambiguas de `aplicar-cambios`
(`tests/test_aplicar_cambios.py`, que crece con cada caso raro visto en uso real),
archivado con hashes y lectores de entrada.

## Mantenimiento del criterio de estilo

Todo el criterio vive en `config/estilo.yaml`: palabras prohibidas con
sugerencia y motivo, expresiones en primera persona, longitud máxima de frase y
estructura obligatoria de la observación. Se inyecta automáticamente en los
prompts, así que ampliar el YAML cambia a la vez lo que se detecta y lo que el
modelo evita al redactar.

## Estructura del código

```
config/estilo.yaml          Criterio de estilo (editable por el equipo)
audit_agent/expediente.py   Carpeta de trabajo: ficheros, snapshots, trazas
audit_agent/formato_md.py   Markdown de ida y vuelta (render ↔ parse) de observaciones e informe
audit_agent/acciones.py     Las acciones del flujo (extraer, redactar, revisar, corregir, aplicar-cambios, ppt…)
audit_agent/esquemas.py     Salidas estructuradas del LLM (Pydantic) — formato pivote
audit_agent/style_checker.py  Reglas deterministas (texto y Markdown)
audit_agent/lectores.py     Lectura de entrada/ (.md/.txt/.docx/.xlsx/.pdf) a Markdown normalizado
audit_agent/calibracion.py  Calibración de estilo.yaml contra informes aprobados
audit_agent/llm.py          Cliente LLM unificado (kaia | anthropic | dry-run) con trazas
audit_agent/kaia_client.py  Transporte KAIA (OAuth2 + invoke con output_format_schema)
audit_agent/reviewer.py     Revisión de texto suelto
audit_agent/ppt_builder.py  Resumen Ejecutivo PPT
audit_agent/cli.py          Comandos y menú interactivo
ejemplos/                   Papel de trabajo, borrador, datos de informe, entrada sintética y corpus de calibración
scripts/                    Generación de ficheros de entrada sintéticos
tests/                      Suite determinista (pytest)
docs/referencia/            Proveedor KAIA original de audit-engine (referencia)
```

## Siguientes pasos

- Sustituir el PPT autónomo por la plantilla `.potx` corporativa (mismo código;
  asignar `run.text`, nunca `text_frame.text`).
- Añadir el lector específico del formato real de exportación de Pentana en `lectores.py`.
- Calibrar `estilo.yaml` con informes aprobados reales (`calibrar-estilo`).
- Memoria histórica: sugerir observaciones similares de auditorías cerradas.
- Interfaz web (Streamlit) sobre las mismas acciones si el equipo no quiere terminal.
