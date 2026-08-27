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

## Interfaz web

```bash
cd frontend && npm install && npm run build && cd ..   # una vez (o tras cambiar el front)
./revisor web                                          # http://127.0.0.1:8000
```

`./revisor web` arranca la API REST (`audit_agent/api.py`, contrato en
`docs/SUPERPROMPT_FRONT.md`) y sirve el front compilado. Las acciones del modelo
corren como trabajos en segundo plano (`/api/jobs/{id}`), en serie por
expediente. El front (`frontend/`, Vite + React + TypeScript) replica el look &
feel corporativo (tokens `--ids-*`, CSS BEM, menú lateral) y tiene un modo mock
para verlo sin back-end (`npm run dev:mock`). Ver `frontend/README.md`.

La CLI (`./revisor …`) y la web trabajan sobre los mismos ficheros del
expediente: se pueden combinar.

## El espacio de trabajo: un expediente por auditoría

Todo el estado vive en una carpeta de ficheros de texto que se editan con
cualquier editor (VS Code es ideal: vista previa Markdown + terminal al lado):

```
expedientes/CNC-2026-03/
  expediente.yaml         nombre, referencia, fecha, distribución, notas para el modelo
  contexto/               design thinking, planificación, motivo y alcance previsto (opcional; .md/.txt/.docx/.xlsx/.pdf/.pptx)
  papeles_trabajo/        papel de trabajo final con todas las pruebas (fuente de las conclusiones); mejor un fichero por prueba.
                          De un .xlsx se envía completa la narrativa de cada hoja (la «Memo») y solo las 40 primeras filas de las
                          hojas de datos; el prompt reparte su cupo entre documentos (papeles de trabajo primero) y `extraer` avisa
                          si un fichero va recortado o si alguna prueba numerada queda sin conclusión ni «sin incidencias»
  01_conclusiones.md      conclusiones y sugerencias propuestas → el auditor edita, aprueba y recomienda
  02_informe.md           el informe: introducción · resumen ejecutivo · detalle de conclusiones · sugerencias
                          (cada apartado se escribe como se leerá en su diapositiva; `ppt` lo exporta 1:1)
  03_instrucciones.md     buzón de instrucciones: lo rellenas tú o `reunion` → `aplicar-cambios`
  reuniones/              actas de `reunion` (texto vs PPT vs pendientes vs acuerdos)
  revision.md             hallazgos de vocabulario y estilo (acumulado)
  cambios_aplicados.md    qué cambios pidió el modelo y cuáles se aplicaron
  historial/              snapshot automático antes de cada sobreescritura (`diff`, `deshacer`)
  salidas/                ResumenEjecutivo_<REF>.pptx
  trazas/                 una entrada JSON por llamada al LLM (y el texto leído de contexto/ y papeles_trabajo/)
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
#   → al empezar la auditoría: design thinking / memorando de planificación en contexto/
#   → al terminar el trabajo de campo: papel de trabajo final (todas las pruebas) en papeles_trabajo/
#     Se admite texto pegado desde Excel.

./revisor estado            # en cualquier momento: fase actual y siguiente paso sugerido
./revisor menu              # lo mismo, con menú numerado

# 1. Contexto del informe
./revisor redactar-contexto          # introducción + resumen ejecutivo desde contexto/ y papeles_trabajo/ → 02_informe.md
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
./revisor reunion transcripcion_teams.txt [--aplicar]
#   Lee la transcripción de la reunión (Teams: .txt/.docx/.vtt), la contrasta con el informe y
#   te dice qué ha detectado que hay que cambiar: (a) en el TEXTO del informe → queda como
#   instrucciones en 03_instrucciones.md para que las revises; (b) en el PPT → solo informativo
#   (la presentación es beta y se retoca a mano); más pendientes de dato y acuerdos. Acta en reuniones/.
./revisor aplicar-cambios [--solo-plan]   # aplica 03_instrucciones.md: cambios concretos, registrados
./revisor cambio "pon el riesgo de la conclusión 1 en Alto"   # un cambio suelto, aplicado al momento
./revisor chat                            # varios cambios sueltos, uno por mensaje, con diff tras cada uno
#   Ejemplos: ejemplos/transcript_reunion_teams.txt, ejemplos/transcript_reunion_tarifarios.vtt (Teams .vtt sobre el
#   informe de tarifarios) y ejemplos/mensajes_chat.txt
./revisor revisar | corregir [--avisos]   # vocabulario prohibido y estilo del informe
./revisor condensar [--objetivo 0.85]     # acorta un poco el informe con el modelo (≈15 % menos palabras) sin perder
#   hechos, cifras ni referencias; la recomendación no se toca. Cada campo solo se acepta si es más corto, conserva
#   las cifras y cumple las reglas; si no, se conserva el original y se dice. Snapshot + diff; `deshacer` lo revierte.
./revisor diff | deshacer | historial     # control de versiones

# 4. Entregable y cierre
./revisor ppt                        # exporta el informe ENTERO sobre la plantilla corporativa
#   (config/plantilla_informe.pptx): cada apartado de 02_informe.md es una diapositiva de la plantilla
#   con su texto sustituido (portada, índice, introducción por bloques, portadillas, resumen con la
#   escala de Evaluación Global, una tabla por recomendación —banda RIESGO, «NN Título», prosa, caja
#   gris de detalles, consecuencias, Recomendación N.k, Ref., Área/Responsable/Plazo; «(continuación)»
#   si no cabe—, sugerencias de mejora y anexo de planes de acción). Sin modelo: es determinista.
./revisor archivar                   # zip de evidencia con manifest sha256

# Texto suelto (p. ej. un párrafo copiado de Pentana), sin expediente:
./revisor revisar-texto --fichero borrador.txt [--sin-llm]
```

`.venv/bin/python demo.py` ejecuta el flujo completo sobre el papel de trabajo de
ejemplo `ejemplos/papel_trabajo_tarifarios.txt` (crea `expedientes/DEMO-TEC-2026`).

Con varios expedientes, fija el activo con `./revisor usar <ruta>` o pásalo con `-e <ruta>`.
`./revisor eliminar` borra el expediente activo (pide escribir su referencia); en la web, «Eliminar» en la
lista de expedientes, con la misma confirmación.

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

## Entrada: contexto y papeles de trabajo

`contexto/` (design thinking, planificación: alimenta introducción y resumen, y
solo orienta a `extraer`) y `papeles_trabajo/` (papel de trabajo final: fuente de
las conclusiones) admiten `.md` y `.txt` (incluido texto pegado desde Excel: se
normalizan tabulaciones y celdas entre comillas) y, a través de los extractores de
`audit_agent/extractores/`, `.docx`, `.xlsx`, `.pdf` y `.pptx`:

- **DOCX**: recorrido en el orden real del documento (párrafos y tablas
  intercalados), `Heading n` → `#`×n, listas, tablas Markdown, imágenes con OCR.
- **XLSX**: una sección por hoja; la primera fila no vacía es la cabecera de la
  tabla; valores calculados (no fórmulas).
- **PDF**: PyMuPDF a nivel de línea (tamaño y negrita para detectar encabezados;
  numeración de epígrafes; cabeceras/pies repetidos descartados; tablas
  detectadas y validadas; columnas reales por recurrencia). Páginas sin texto →
  OCR con Tesseract si está instalado (`apt install tesseract-ocr tesseract-ocr-spa`);
  si no hay texto ni OCR, error claro pidiendo otra exportación.
- **PPTX**: una sección por diapositiva (título de la diapositiva), cuadros,
  tablas, notas del orador e imágenes con OCR.

Los extractores producen bloques tipados (`models.py`) y un único renderizador
(`markdown.py`) los vuelca a Markdown, igual para todos los formatos. Cada
`extraer`/`redactar-contexto` deja en `trazas/*-entrada.json` de qué carpeta viene
cada documento, qué lector se usó y el texto exacto enviado al modelo.
`scripts/generar_ejemplos_entrada.py` genera los ficheros sintéticos de
`ejemplos/entrada_sintetica/` usados en los tests.

## Trazabilidad y retención

- `reuniones/` guarda el acta de cada transcripción analizada.
- `trazas/` guarda, por cada llamada al modelo, un JSON con fecha, acción, modelo,
  prompt completo, respuesta estructurada y tokens; y por cada lectura de
  `contexto/` y `papeles_trabajo/`, el texto normalizado enviado. Es la evidencia de **cómo se redactó
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

Todo el criterio vive en `config/estilo.yaml` (palabras prohibidas con
sugerencia y motivo, primera persona del singular, longitud máxima de frase,
escalas de riesgo y de evaluación global, estructura obligatoria de la
conclusión), `config/textos_informe.yaml` (frases fijas del informe) y
`config/ejemplo_conclusion.md` (ejemplos de referencia). El registro (primera
persona del plural para las actuaciones del equipo, «deber ser» + lo
identificado + datos + riesgo + materialización, recomendaciones en infinitivo)
está documentado en [docs/ESTILO_INFORMES.md](docs/ESTILO_INFORMES.md), calibrado
con tres informes aprobados, y se inyecta en los prompts. Se inyecta automáticamente en los
prompts, así que ampliar el YAML cambia a la vez lo que se detecta y lo que el
modelo evita al redactar.

## Estructura del código

```
config/estilo.yaml          Criterio de estilo (editable por el equipo)
config/textos_informe.yaml  Frases fijas del informe (plan de auditoría, normas, próximos pasos, sugerencias)
docs/ESTILO_INFORMES.md     Notas de estilo calibradas con informes aprobados
config/ejemplo_conclusion.md  Ejemplo de referencia de una conclusión (registro objetivo; se inyecta en `extraer`)
audit_agent/expediente.py   Carpeta de trabajo: ficheros, snapshots, trazas
audit_agent/formato_md.py   Markdown de ida y vuelta (render ↔ parse) de conclusiones e informe
audit_agent/acciones.py     Las acciones del flujo (redactar-contexto, extraer, recomendar, redactar-conclusiones, aplicar-cambios, ppt…)
audit_agent/esquemas.py     Salidas estructuradas del LLM (Pydantic) — formato pivote
audit_agent/style_checker.py  Reglas deterministas (texto y Markdown)
audit_agent/lectores.py     Lectura de contexto/ y papeles_trabajo/ a Markdown (.md/.txt aquí; el resto vía extractores)
audit_agent/extractores/    Extractores DOCX/PDF/PPTX/XLSX (bloques tipados + Markdown + OCR)
audit_agent/calibracion.py  Calibración de estilo.yaml contra informes aprobados
audit_agent/llm.py          Cliente LLM unificado (kaia | anthropic | dry-run) con trazas
audit_agent/kaia_client.py  Transporte KAIA (OAuth2 + invoke con output_format_schema)
audit_agent/reviewer.py     Revisión de texto suelto
audit_agent/ppt_builder.py  Exportación del informe sobre la plantilla corporativa (config/plantilla_informe.pptx)
scripts/sanear_plantilla.py Saneado de la plantilla PPT (comentarios, autores, think-cell, metadatos) antes de versionarla
audit_agent/cli.py          Comandos y menú interactivo
audit_agent/api.py          API REST (FastAPI) para el front; `./revisor web`
frontend/                   Front (Vite + React + TS, look & feel corporativo, modo mock)
ejemplos/                   Papel de trabajo real (tarifarios), contexto de ejemplo, borrador, entrada sintética y corpus
scripts/                    Generación de ficheros de entrada sintéticos
tests/                      Suite determinista (pytest)
docs/referencia/            Proveedor KAIA original de audit-engine (referencia)
```

## Siguientes pasos

- Plantilla PPT: si el departamento cambia la plantilla, pasarla por
  `scripts/sanear_plantilla.py` y comprobar que las 11 diapositivas mantienen el
  orden y los nombres de forma que espera `ppt_builder.py` (`tests/test_ppt.py`).
- Añadir el lector específico del formato real de exportación de Pentana en `lectores.py`.
- Calibrar `estilo.yaml` con informes aprobados reales (`calibrar-estilo`).
- Memoria histórica: sugerir conclusiones similares de auditorías cerradas.
- Interfaz web (Streamlit) sobre las mismas acciones si el equipo no quiere terminal.
