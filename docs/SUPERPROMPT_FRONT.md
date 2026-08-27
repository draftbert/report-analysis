# SUPERPROMPT — Front del «Revisor de informes de auditoría interna»

Genera una aplicación web completa (front-end) para una herramienta interna de Auditoría Interna que ayuda a redactar el informe de auditoría a partir de los papeles de trabajo, con un modelo de lenguaje que **propone** y un auditor que **decide**. El back-end ya existe (API REST descrita más abajo); tú construyes solo el front. Lee todo antes de empezar: el contrato de API es fijo y el front debe cumplirlo tal cual.

## 1. Contexto y principios del producto

- Usuarios: auditores internos (no técnicos) y sus gerentes. Idioma de toda la interfaz: **español**.
- Unidad de trabajo: el **expediente** (una auditoría). Un auditor trabaja en él durante días: sube documentos, revisa lo que propone el modelo, aprueba, edita el informe, aplica los comentarios de reuniones, exporta a PowerPoint y archiva.
- Principio inviolable que la UI debe transmitir: **nada va al informe sin validación humana**. Todo lo que propone el modelo se muestra como propuesta (con estado, badges y acciones de aprobar/descartar); las recomendaciones que escribe el auditor se respetan literalmente; toda acción del modelo deja traza.
- Estructura del informe (siempre la misma): **Introducción → Resumen ejecutivo → Detalle de conclusiones → Sugerencias de mejora**. Cada conclusión tiene: incidencia detectada, causa raíz, «detalles descriptivos» (viñetas con datos), consecuencias y recomendación(es) numeradas N.1, N.2…, más metadatos (prueba de origen, nivel de riesgo, área, responsable, plazo, referencia a recomendación abierta).
- El informe es **WYSIWYG con la presentación**: cada apartado del informe es una diapositiva del PPT exportado. La UI debe hacer visible esa equivalencia (cada apartado se muestra como una «tarjeta-diapositiva»).

## 2. Estilo visual (Inditex corporativo)

- Minimalismo editorial: fondo blanco (#FFFFFF), texto negro (#111111), grises neutros (#F5F5F5 superficies, #E6E6E6 líneas, #6B6B6B texto secundario). Sin degradados, sin sombras marcadas, sin bordes redondeados grandes (radio máximo 2 px), sin iconos de colores.
- Tipografía sans neutra (Helvetica Neue / Inter / system-ui), pesos 400 y 600, mucho aire. Etiquetas y navegación en **mayúsculas con tracking** (letter-spacing 0.08em, 11–12 px). Títulos grandes y finos.
- Reglas horizontales de 1 px como separadores; tablas sin zebra, con líneas finas.
- El color se reserva para el **nivel de riesgo** (Crítico #7A0C0C, Alto #B3261E, Medio #C77700, Bajo #2E7D32) y para estados (propuesta gris, aprobada negro, descartada tachado gris). Botón primario: negro con texto blanco, rectangular; secundario: borde negro 1 px.
- Densidad tipo herramienta profesional (no landing): paneles laterales, listas compactas, atajos visibles.
- Modo claro únicamente. Responsive mínimo: funciona bien a partir de 1280 px; en pantallas menores, navegación lateral colapsable.

## 3. Stack y entrega

- **React 18 + TypeScript + Vite**. Estilos con CSS Modules o Tailwind (si usas Tailwind, configura la paleta anterior; nada de temas prefabricados). Sin librerías de componentes pesadas (nada de MUI/AntD). Permitidas: `react-router-dom`, `react-markdown` (+ `remark-gfm`) para previsualizar Markdown, `diff` o `diff2html` para diffs, `zustand` o context para estado.
- Todas las llamadas a la API son **relativas a `/api`** (mismo origen). El build (`npm run build`) debe producir un `dist/` estático que el back-end servirá en `/`; usa rutas del router compatibles con eso (BrowserRouter con fallback a `index.html`).
- **Modo mock obligatorio**: con `VITE_MOCK=1`, la app funciona sin back-end usando los datos de ejemplo del apartado 8 (incluye simulación de trabajos largos con retardo de 2–3 s). Es lo que se usará para revisar el front antes de integrarlo.
- Entrega: proyecto completo con `README.md` (instalar, `npm run dev`, `npm run build`, variable `VITE_MOCK`), código tipado, sin errores de consola, y componentes reutilizables (`RiskBadge`, `StateChip`, `JobButton`, `MarkdownEditor`, `DiffView`, `Dropzone`, `SlideCard`).

## 4. Modelo de trabajos largos (obligatorio)

Toda acción que usa el modelo de lenguaje tarda 20–90 s. La API devuelve inmediatamente `{ "job_id": "…" }` y el front hace polling a `GET /api/jobs/{job_id}` cada 2 s hasta `estado` ∈ {`ok`, `error`}. Componente `JobButton`: al pulsar, se deshabilita, muestra spinner y el texto «Trabajando con el modelo…»; al terminar, muestra el `mensaje` (texto multilínea, monoespaciado suave) en un panel de resultado y refresca los datos de la pantalla. Si `error`, muestra el mensaje en rojo sin perder el estado de la pantalla. Las acciones deterministas (sin modelo) responden síncronas.

```json
GET /api/jobs/{job_id} → { "estado": "en_curso" | "ok" | "error", "accion": "extraer", "mensaje": "texto de resultado", "resultado": { ...opcional... } }
```

## 5. Contrato de API (fijo)

Base `/api`. Todas las respuestas JSON, UTF-8. `{ref}` es la referencia del expediente (p. ej. `TEC-2026`). Los errores devuelven `4xx/5xx` con `{ "error": "mensaje para el usuario" }`.

### Expedientes
- `GET /expedientes` → `[{ "referencia", "nombre", "fecha", "fase", "siguiente", "modificado" }]`
- `POST /expedientes` `{ "referencia", "nombre", "fecha", "distribucion": ["…"] }` → expediente creado.
- `GET /expedientes/{ref}` → estado completo:
```json
{ "referencia": "TEC-2026", "nombre": "Auditoría de Transporte e-Commerce", "fecha": "Junio 2026",
  "distribucion": ["Dirección de Transporte e-Commerce", "Comité de Auditoría"],
  "fase": "3 · Informe en redacción", "siguiente": "`ppt` para generar la presentación",
  "contexto": ["design_thinking.md"], "papeles": ["papel_trabajo.txt"],
  "conclusiones": { "total": 3, "propuesta": 1, "aprobada": 2, "descartada": 0, "sugerencias": 1,
                    "sin_recomendacion": ["C-02"], "riesgo_pendiente": [], "con_notas": [] },
  "informe": { "contexto": true, "n_conclusiones": 2, "n_sugerencias": 1, "errores": 0, "avisos": 2,
               "modificado": "2026-08-27T10:12:00", "versiones": 4 },
  "instrucciones_pendientes": false, "ppt": { "nombre": "ResumenEjecutivo_TEC-2026.pptx", "desactualizado": false },
  "archivos": ["TEC-2026_archivo_20260827-1015.zip"], "llm": "kaia · gpt-5-mini" }
```

### Documentos de entrada
- `GET /expedientes/{ref}/documentos` → `{ "contexto": [{ "nombre", "bytes", "lector" }], "papeles_trabajo": [...] }`
- `POST /expedientes/{ref}/documentos/{carpeta}` (multipart, campo `ficheros[]`; `carpeta` ∈ `contexto|papeles_trabajo`) → lista actualizada.
- `DELETE /expedientes/{ref}/documentos/{carpeta}/{nombre}`.
- Formatos admitidos: .md .txt .docx .xlsx .pdf .pptx (mostrar como ayuda en el dropzone; texto pegado desde Excel se admite en .txt).

### Contexto del informe (introducción + resumen)
- `POST /expedientes/{ref}/acciones/redactar-contexto` `{ "forzar": bool, "secciones": ["introduccion"|"resumen"] }` → job.

### Conclusiones
- `GET /expedientes/{ref}/conclusiones` → `{ "markdown": "…", "conclusiones": [Conclusion] }` con:
```json
{ "id": "C-01", "titulo": "…", "tipo": "conclusion" | "sugerencia", "estado": "propuesta" | "aprobada" | "descartada",
  "prueba": "2.11 b) …", "nivel_riesgo": "Alto" | "Medio" | "Bajo" | "Crítico" | "", "riesgo_propuesto": true,
  "area": "", "responsable": "", "plazo": "", "referencia_recomendacion": "TMSCIIF-10", "fuente": "…",
  "incidencia": "…", "causa_raiz": "…", "como_se_ha_llegado": "- dato 1\n- dato 2", "consecuencias": "…",
  "recomendacion": "Párrafo 1\n\nPárrafo 2", "notas": "" }
```
  `riesgo_propuesto: true` significa que el nivel lo estimó el modelo sin evidencia en el papel de trabajo: mostrar pill «propuesto por el modelo» junto al badge; desaparece al aprobar.
- `PUT /expedientes/{ref}/conclusiones/{id}` con los campos editados (parcial) → conclusión guardada.
- `PUT /expedientes/{ref}/conclusiones` `{ "markdown": "…" }` (edición en crudo del fichero completo).
- `POST /expedientes/{ref}/acciones/extraer` `{ "forzar": bool }` → job (propone conclusiones desde papeles_trabajo).
- `POST /expedientes/{ref}/acciones/aprobar` `{ "ids": ["C-01"] | ["todas"], "estado": "aprobada"|"descartada"|"propuesta" }` → síncrono `{ "mensaje" }`.
- `POST /expedientes/{ref}/acciones/revisar-conclusiones` → síncrono `{ "hallazgos": [{ "id": "C-01", "tipo", "severidad": "error"|"aviso", "fragmento", "mensaje", "sugerencia" }] }`.
- `POST /expedientes/{ref}/acciones/corregir-conclusiones` `{ "ids": [] }` → job.
- `POST /expedientes/{ref}/acciones/regenerar` `{ "id": "C-02", "notas": "qué cambiar" }` → job.
- `POST /expedientes/{ref}/acciones/recomendar` `{ "ids": [], "respuestas": { "C-02": "texto del auditor" }, "auto": bool, "formatear": bool }` → job. Semántica: para cada conclusión aprobada sin recomendación, si hay `respuestas[id]` se registra **literal**; si no y `auto` es true, la propone el modelo (y a veces una sugerencia de mejora complementaria como bloque nuevo en estado propuesta).
- `POST /expedientes/{ref}/acciones/redactar-conclusiones` → síncrono `{ "mensaje" }` (vuelca las aprobadas al informe sin modelo; bloquea las que no tengan recomendación o riesgo sin validar, y lo dice en el mensaje).

### Informe
- `GET /expedientes/{ref}/informe` → `{ "markdown": "…", "apartados": [{ "id": "introduccion"|"resumen"|"c1"|"s1", "titulo", "tipo": "introduccion"|"resumen"|"conclusion"|"sugerencia", "markdown": "…apartado…", "nivel_riesgo": "", "numero": 1 }], "evaluacion_global": "Mejorable" }`
- `PUT /expedientes/{ref}/informe` `{ "markdown": "…" }` → guardado (snapshot automático en historial).
- `POST /expedientes/{ref}/acciones/revisar` → síncrono `{ "hallazgos": [{ "linea", "severidad", "fragmento", "mensaje", "sugerencia" }], "errores": n, "avisos": n }`.
- `POST /expedientes/{ref}/acciones/corregir` `{ "avisos": bool }` → job; `resultado.diff` (unified diff).
- `POST /expedientes/{ref}/acciones/cambio` `{ "mensaje": "…", "solo_plan": bool }` → job; `resultado`: `{ "plan": [{ "seccion", "motivo", "estado": "aplicado"|"insertado"|"eliminado"|"NO APLICADO"|"CONFLICTO", "detalle" }], "pendientes": ["…"], "diff": "…" }`.
- `GET /expedientes/{ref}/instrucciones` → `{ "texto": "…pendiente…" }`; `PUT` `{ "texto" }`.
- `POST /expedientes/{ref}/acciones/aplicar-cambios` `{ "solo_plan": bool }` → job (mismo `resultado` que `cambio`).
- `POST /expedientes/{ref}/acciones/reunion` (multipart `transcripcion` + campo `aplicar`) → job; `resultado`:
```json
{ "acta": "reuniones/2026-08-27_1012_transcript.md", "resumen": "…",
  "cambios_texto": [{ "seccion", "que_cambiar", "instruccion", "solicitado_por", "cita" }],
  "cambios_ppt": [{ "que_cambiar", "solicitado_por", "cita" }],
  "pendientes": ["…"], "acuerdos_sin_cambio": ["…"] }
```
- `GET /expedientes/{ref}/historial` → `[{ "fichero": "informe"|"conclusiones"|"instrucciones", "nombre", "fecha", "motivo" }]`
- `POST /expedientes/{ref}/acciones/deshacer` `{ "fichero": "informe" }` → síncrono; `GET /expedientes/{ref}/diff?fichero=informe` → `{ "diff": "…" }`.
- `GET /expedientes/{ref}/cambios` → `{ "markdown": "…" }` (registro de cambios aplicados). `GET /expedientes/{ref}/reuniones` → `[{ "nombre", "fecha", "markdown" }]`.

### Entregables y trazabilidad
- `POST /expedientes/{ref}/acciones/ppt` → síncrono `{ "nombre", "url": "/api/expedientes/TEC-2026/salidas/ResumenEjecutivo_TEC-2026.pptx" }`.
- `POST /expedientes/{ref}/acciones/archivar` → síncrono `{ "nombre", "url" }` (zip con manifest sha256).
- `GET /expedientes/{ref}/salidas/{nombre}` → descarga.
- `GET /expedientes/{ref}/trazas` → `[{ "nombre", "fecha", "accion", "modelo", "tokens": { "prompt", "completion" } }]`; `GET /expedientes/{ref}/trazas/{nombre}` → JSON de la traza (prompt, respuesta).

## 6. Pantallas y flujos (en orden de uso)

**A. Expedientes** (`/`): lista tipo tabla (referencia, nombre, fase, siguiente paso, última modificación) + botón «Nuevo expediente» (modal: referencia, nombre, fecha, lista de distribución editable). Click → expediente.

**B. Layout del expediente** (`/expedientes/:ref/*`): cabecera con referencia y nombre, badge de fase y una línea destacada «Siguiente paso: …» (viene de la API, es la guía del flujo). Navegación lateral fija con las secciones en orden: **Entrada · Contexto del informe · Conclusiones · Informe · Reunión · Entregables · Trazas**, con un pequeño indicador de estado por sección (vacío / en curso / listo).

**C. Entrada** (`…/entrada`): dos dropzones lado a lado: «Contexto de la auditoría (design thinking, planificación) — opcional» y «Papeles de trabajo (papel de trabajo final con todas las pruebas)». Lista de ficheros con lector detectado y botón eliminar. Texto de ayuda con formatos.

**D. Contexto del informe** (`…/contexto`): dos paneles editables «Introducción» y «Resumen ejecutivo» (editor Markdown con vista previa conmutable), selector de «Evaluación global» (Deficiente/Insuficiente/Mejorable/Razonable/Adecuado). `JobButton` «Redactar con el modelo» (si ya existe texto, pedir confirmación y ofrecer «solo introducción» / «solo resumen»). Guardar → `PUT /informe` (la API conserva el resto del informe).

**E. Conclusiones** (`…/conclusiones`): barra de acciones: «Extraer del papel de trabajo» (job; si ya hay conclusiones pide confirmación de regenerar), «Aprobar todas», «Revisar vocabulario», «Corregir con el modelo» (job), «Recomendar…». Lista de tarjetas, una por conclusión, con: id, título editable, `StateChip` (propuesta/aprobada/descartada, clic para cambiar), toggle Tipo (conclusión / sugerencia de mejora), `RiskBadge` con pill «propuesto por el modelo» cuando `riesgo_propuesto`, metadatos (prueba, área, responsable, plazo, ref. recomendación) editables en línea, y los cinco bloques de texto editables (incidencia, causa raíz, detalles descriptivos como lista, consecuencias, recomendación con párrafos numerados). Campo «Notas del auditor» + botón «Regenerar con estas notas» (job). Hallazgos de vocabulario mostrados inline bajo el campo afectado. Guardado por tarjeta (`PUT /conclusiones/{id}`) con indicador «guardado». Flujo **Recomendar**: asistente modal que recorre las aprobadas sin recomendación: muestra la incidencia y pregunta «¿Tienes recomendación?» con textarea y dos botones «Usar mi texto (se respeta tal cual)» / «Que la proponga el modelo»; al final envía un único `POST /acciones/recomendar` con `respuestas` y `auto` para las no contestadas. Botón final «Volcar aprobadas al informe» (`redactar-conclusiones`, síncrono) que muestra el mensaje con las bloqueadas y por qué.

**F. Informe** (`…/informe`): vista principal en dos columnas. Izquierda: el informe como secuencia de **tarjetas-diapositiva** (`SlideCard`), una por apartado, con formato 16:9 aproximado, título del apartado, badge de riesgo si es conclusión, y el Markdown renderizado; clic en «Editar» abre el editor Markdown del apartado (o del informe completo en un modo «crudo»). Derecha: panel con pestañas: **Revisión** (botón «Revisar vocabulario» → lista de hallazgos con línea/fragmento/sugerencia, clic salta al apartado; botón «Corregir con el modelo» job con diff), **Chat de cambios** (caja de texto tipo chat: cada mensaje → `POST /acciones/cambio`; se muestra el plan con estados por color, pendientes, y el diff plegable; atajos «Deshacer» y «Ver diff»), **Instrucciones** (textarea del buzón `03_instrucciones.md` + «Aplicar cambios» job + «Solo plan»), **Historial** (versiones con fecha/motivo, «Deshacer última», diff contra la anterior). Aviso visible si el PPT está desactualizado respecto al informe.

**G. Reunión** (`…/reunion`): dropzone para la transcripción (.txt/.docx/.vtt) + checkbox «Aplicar directamente los cambios de texto». Job → pantalla de **acta** en cuatro bloques con títulos en mayúsculas: «Cambios en el texto del informe» (tarjetas con sección, qué cambiar, quién lo pide, cita en cursiva y un checkbox por cambio, todos marcados), «Cambios en la presentación (PPT) — informativo» (tarjetas grises, sin acciones, nota «la presentación se ajusta a mano»), «Pendientes de dato o confirmación», «Acuerdos que no cambian el informe». Botón «Enviar los seleccionados a Instrucciones y aplicar» (rellena `PUT /instrucciones` con las instrucciones marcadas y lanza `aplicar-cambios`). Lista de actas anteriores debajo.

**H. Entregables** (`…/entregables`): tarjeta «Presentación (PPT)»: estado (generada el…, desactualizada), botón «Exportar informe a PowerPoint» → descarga; recordatorio «cada apartado del informe es una diapositiva». Tarjeta «Archivo de evidencia»: explica qué contiene (trazas, historial, informe, PPT, manifest sha256), botón «Archivar» → descarga zip; lista de archivos anteriores.

**I. Trazas** (`…/trazas`): tabla de llamadas al modelo (fecha, acción, modelo, tokens) y detalle en drawer con prompt y respuesta en monoespaciado. Mensaje de cabecera: «Toda salida del modelo queda ligada a su entrada».

## 7. Comportamientos transversales

- Estados vacíos con guía («Sube el papel de trabajo para empezar», «Aún no hay conclusiones: extráelas del papel de trabajo»), siempre coherentes con `siguiente` de la API.
- Confirmaciones antes de acciones que sobreescriben trabajo del auditor (regenerar conclusiones, redactar de nuevo, deshacer). Nunca borrar sin confirmar.
- Guardado explícito con estado «Sin guardar / Guardando / Guardado hh:mm» en editores; atajo Ctrl/Cmd+S.
- Mensajes de resultado de los jobs siempre visibles hasta que el usuario los cierre (son la explicación de lo que hizo el modelo).
- Diff siempre como unified diff coloreado (verde/rojo suaves), plegable.
- Accesibilidad básica: foco visible, contraste AA, botones con `aria-label`.
- Textos de la UI en español, tono sobrio («Extraer», «Aprobar», «Recomendar», «Volcar al informe», «Exportar a PowerPoint», «Archivar»).

## 8. Datos de ejemplo para el modo mock

Expediente `TEC-2026` «Auditoría de Transporte e-Commerce: tarifarios y SCA», fecha «Junio 2026», distribución [«Dirección de Transporte e-Commerce», «Dirección Financiera», «Comité de Auditoría»], fase «3 · Informe en redacción», contexto [«contexto_auditoria_tarifarios.md»], papeles [«papel_trabajo.txt»].

Conclusiones:
1. `C-01` · conclusion · aprobada · riesgo Alto · prueba «2.11 b) Gestión del maestro de tarifas» · área «Transporte e-Commerce» · responsable «Pablo Nieto (1.1); Operativa (1.2)» · plazo «31/03/2027 (1.1); 31/12/2026 (1.2)» · ref «TMSCIIF-10». Título: «Mantenimiento manual y desactualización del maestro de tarifas». Incidencia: «El mantenimiento del maestro de tarifas en la Herramienta de Costes es un proceso manual sin una plantilla común. Durante nuestra revisión hemos identificado que los acuerdos alcanzados entre Operativa y los proveedores no siempre se transmiten al equipo de validación.» Causa raíz: «Proceso dependiente de tareas manuales y formatos heterogéneos por courier.» Detalles: «- Los equipos de validación (BDO, Serviguide e Inditex - China) actualizan el maestro manualmente, incluso a nivel de Código Postal.\n- Cada pedido validado se registra en Snowflake (TRANSPORT_BUSINESS.FOUNDATION.COSTES_ECOM_DETALLE).\n- Existen alertas diarias y una revisión semanal de Transport Business Analytics.» Consecuencias: «La manualidad incrementa el riesgo de tarifas desactualizadas en la Herramienta de Costes, que se traslada a CPF y a la asignación de transportistas en SCA. Respecto a la materialización, no ha sido posible cuantificar el impacto económico.» Recomendación: «Implantar un sistema para la carga y gestión de los tarifarios de todas las operativas de transporte.\n\nEstablecer un procedimiento que deje evidencia de los acuerdos alcanzados con los proveedores y garantice su trazabilidad con las tarifas cargadas.»
2. `C-02` · conclusion · propuesta · riesgo Medio con `riesgo_propuesto: true` · prueba «2.11 a) Contrastar el tarifario negociado» · sin recomendación. Título: «CPF hereda deficiencias en la valoración de casuísticas minoritarias (COD, zonas remotas)».
3. `C-03` · sugerencia · aprobada · riesgo Bajo · área «Transport Business Analytics». Título: «Documentación del control de alertas diarias y revisión semanal». Recomendación (propuesta de mejora): «Documentar y formalizar el control de alertas diarias y la revisión semanal de Transport Business Analytics.»

Informe: introducción con los bloques **Contexto:**, **Objetivo de la auditoría:** (con lista), **Riesgos a cubrir:**, **Alcance de la auditoría:**, **Principales magnitudes:** (38 couriers; 12 mercados; 41,6 M pedidos; 1,4 M€ reclamaciones) entre las frases fijas «La auditoría ha sido realizada en cumplimiento del Plan de Auditoría del año 2026, aprobado por la Comisión de Auditoría y Cumplimiento.» y «El trabajo ha sido llevado a cabo de acuerdo con las Normas Internacionales para la Práctica Profesional de Auditoría Interna…». Resumen ejecutivo con tres viñetas «/ …» y evaluación global «Mejorable». Un apartado de conclusión (C-01) y uno de sugerencia (C-03).

Hallazgos de ejemplo (revisar): línea 42, error, fragmento «problema», mensaje «Terminología estándar del informe.», sugerencia «observación / debilidad»; línea 88, aviso, frase de 61 palabras.

Acta de reunión de ejemplo: resumen «Se revisó el borrador con la Dirección y el área auditada…»; cambios_texto: (1) Resumen ejecutivo — acortar la segunda viñeta (pide Carmen Soto); (2) Conclusión 1 — elevar el riesgo a Alto; (3) Conclusión 1 — dividir la Recomendación 1.1 en 1.1 y 1.2 con área/responsable/plazo; (4) Sugerencias de mejora — añadir sugerencia sobre alertas diarias; cambios_ppt: «Magnitudes en gráfico de barras», «Plantilla corporativa nueva», «Detalles descriptivos en diapositiva aparte»; pendientes: «Importe anual facturado por los couriers — lo aporta Pablo Nieto»; acuerdos: «Conformidad del área en diez días hábiles», «Seguimiento en enero».

Trazas de ejemplo: 6 llamadas (redactar-contexto, extraer, recomendar-C-02, aplicar-cambios, reunion, corregir) con tokens.

## 9. Criterios de aceptación

1. `npm run build` genera `dist/` sin errores; `VITE_MOCK=1 npm run dev` permite recorrer todas las pantallas con los datos de ejemplo, incluidos los jobs simulados.
2. Todas las rutas y JSON del apartado 5 se usan exactamente como están (sin inventar campos; los opcionales pueden faltar).
3. El flujo completo es recorrible desde la UI: subir documentos → redactar contexto → extraer → editar/aprobar → recomendar (asistente) → volcar al informe → editar informe / chat de cambios / reunión → exportar PPT → archivar.
4. La estética cumple el apartado 2 (blanco, negro, grises, color solo en riesgo/estados, tipografía en mayúsculas con tracking en etiquetas).
5. Ningún texto del modelo se aplica sin acción explícita del usuario, salvo donde el contrato lo define (p. ej. `reunion` con «aplicar» marcado).
