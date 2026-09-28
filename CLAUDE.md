# Revisor de informes de auditoría interna

Herramienta Python para las fases 7–9 del proceso de auditoría interna. Ver README.md
(uso) e INFORME_PLANTEAMIENTO.md (por qué está diseñada así).

## Principios que no se rompen
- **El modelo propone, el auditor decide.** Ninguna acción escribe fuera del expediente;
  antes de sobreescribir un fichero editable se guarda snapshot en `historial/`.
- **El criterio de estilo vive solo en `config/`**: `estilo.yaml` (reglas; editable desde la web en `/reglas` vía `reglas.py`:
  validación con `esquemas.ReglasEstilo`, escritura round-trip con ruamel que conserva comentarios, snapshot en `config/historial/`,
  y «modificar usando el chat» = el modelo PROPONE `PropuestaReglas` y el auditor guarda), `textos_informe.yaml` (frases fijas),
  `ejemplo_conclusion.md` (few-shot de `extraer`; una conclusión por prueba por defecto). El registro real
  (primera persona del plural para el equipo auditor, patrón deber ser → identificado → datos → riesgo →
  materialización) está en `docs/ESTILO_INFORMES.md` y en `SYSTEM_BASE`; no contradecirlo sin recalibrar. Se aplica de forma determinista
  (`style_checker.py`) y se inyecta en los prompts (`reglas_como_texto`). No duplicar reglas en código.
- **Formato pivote:** los esquemas Pydantic de `esquemas.py` (conclusión = incidencia → causa raíz →
  cómo se ha llegado → consecuencias → recomendación; tipo conclusion|sugerencia). Cualquier campo nuevo
  debe añadirse ahí (es lo que viaja al modelo como schema estricto), en `formato_md.py` (render y parse)
  y en `tests/test_formato_md.py`.
- **02_informe.md es WYSIWYG:** cada apartado se escribe como se leerá en su diapositiva y `ppt` exporta
  el informe entero 1:1 (`render_informe`/`parsear_informe` deben ser idempotentes: render(parse(md)) == md).
- **La recomendación del auditor se respeta al 100 %:** `recomendar` solo la formatea si se pide y
  verifica con `conserva_base`; `corregir-conclusiones` nunca la toca; `redactar-conclusiones` vuelca sin modelo.
- **Toda salida del LLM se vuelve a validar con las reglas** y queda trazada en `trazas/`.
- **KAIA:** solo se usa salida estructurada (`output_format_schema` con `to_strict_json_schema`);
  no enviar `temperature` a modelos `gpt-5*`/`o*`. Ver `kaia_client.py`.
- **PPT sobre la plantilla corporativa** (`config/plantilla_informe.pptx`, 11 diapositivas saneadas con
  `scripts/sanear_plantilla.py`; la original con comentarios/autores no se versiona): `ppt_builder.py` duplica
  y rellena diapositivas clonando párrafos de la plantilla; nunca asignar `text_frame.text`, nunca dibujar
  desde cero, sin modelo (determinista). Si cambia la plantilla, recalibrar índices/nombres de forma y `tests/test_ppt.py`.

## Mapa
`cli.py` (comandos/menú) → `acciones.py` (flujo) → `expediente.py` (ficheros) + `formato_md.py`
(Markdown ↔ dict) + `lectores.py` + `extractores/` (contexto/ y papeles_trabajo/ → Markdown; docx/pdf/pptx/xlsx con los extractores
de audit-engine, ficheros con sufijo `_` para no sombrear a python-docx/python-pptx) + `llm.py`/`kaia_client.py` (modelo) +
`style_checker.py` (reglas) + `ppt_builder.py` + `calibracion.py` (estilo.yaml vs informes aprobados) +
`comparar.py` («Últimos cambios» de la web: 02_informe.md contra un snapshot de historial/, por apartados y palabras;
el motivo del snapshot dice el origen del cambio: `cambio`=chat, `reunion`=acta, `aplicar-cambios`=buzón, `web`=edición manual…).

- Entrada: `contexto/` (design thinking; alimenta intro/resumen, solo orienta a extraer) y `papeles_trabajo/`
  (fuente de las conclusiones). `entrada/` antiguo se lee como papeles_trabajo.
- Flujo: redactar-contexto (intro+resumen) → extraer (conclusiones) → aprobar → recomendar →
  redactar-conclusiones → aplicar-cambios/reunion/cambio/chat/revisar/corregir → ppt → archivar.
  No es lineal: se vuelve con documentación nueva. `.procesado.json` (Expediente.registro) guarda qué documentos
  (nombre + sha256) ya pasaron por el modelo y qué observaciones están en el informe; `extraer --solo-nuevos` AÑADE
  las conclusiones de los papeles nuevos sin tocar las existentes y `redactar-conclusiones --anadir` conserva el
  detalle del informe (lo editado allí) y suma solo las aprobadas nuevas; la web simula antes (`simular`). Casos en `tests/test_volver.py`.
- Audio: `transcribir` (KAIA /transcribe/upload, diarización; genéricos = «lo que no está entre los nombres
  enviados», ver Fase 0 en `transcripcion.py`) → hablantes.md → `etiquetar-transcript` (guarda la transcripción
  etiquetada en reuniones/ y la pasa por el MISMO análisis de `reunion` → acta; sin modelo o sin 02_informe.md
  queda solo la transcripción y el acta se genera después con `reunion <txt>`). Las voces son material TEMPORAL de cada expediente (entrada/audio/voces/): sin biblioteca
  global, sin uso entre expedientes, y `archivar` destruye voces/clips/audios (constancia en el manifiesto).
- `reunion`: la transcripción NO se aplica directamente; el modelo la separa en texto / PPT (informativo) /
  pendientes / acuerdos dentro del ACTA. Los cambios de texto se aplican DESDE el acta (selección en la web o
  `reunion --aplicar`), que los pasa directos a `aplicar-cambios` (param `instrucciones=`); el buzón
  03_instrucciones.md es del auditor y el flujo de reuniones NUNCA lo escribe.
  Duplicados: huella SHA-256 por contenido en `reuniones/.huellas.json` (`reunion` y `transcribir`); repetir
  el mismo fichero avisa y bloquea salvo `--repetir` o borrando los ficheros del ítem (la web limpia la huella).
- Nivel de riesgo sin evidencia en el PT: coletilla `(propuesto por el modelo, sin evidencia en PT)`;
  la quita `aprobar`; `redactar-conclusiones` no admite conclusiones que la conserven.
- `aplicar-cambios`: sustituciones acotadas por sección, sin aproximaciones (solo tildes/espacios),
  ambiguo = no aplicado, contradictorio = CONFLICTO. Cada caso raro nuevo va a `tests/test_aplicar_cambios.py`.

- **Web:** `api.py` envuelve `acciones.py` sin lógica propia (jobs en hilo, un lock por expediente); el front
  (`frontend/`) sigue `docs/GUIA_FRONT_HOMOGENEO.md` (kit: `custom.css` + `components/ui.tsx` + `useJob` +
  `formato.ts` + `client.ts`; solo clases del catálogo § 3 y componentes de § 4; clases nuevas con nombre BEM
  y documentadas en la guía). Contrato: `src/api/types.ts` (mismos nombres que el JSON de `api.py`), todo
  endpoint es un método de `interface Api` en `client.ts`; nada llama a `fetch` fuera. Pantallas: portada `/`,
  listado `/informes`, alta `/nuevo`, espacio de trabajo `/informes/:ref?paso=` (documentos → contexto → observaciones →
  informe → entrega, siempre navegables; el estado de cada paso y el sugerido los calcula `_pasos` en `acciones.py`; el paso
  informe lleva las vistas documento · reuniones · últimos cambios) y reglas `/reglas`. Los tokens `--ids-*` de `tokens.css` se sustituyen por
  `@inditex/sewingiopdsweb-styles` en el entorno corporativo.

## Pruebas rápidas
`.venv/bin/python -m pytest -q tests` (determinista, sin red; incluye la API). Front: `cd frontend && npm run types:check && npm run build`. `.venv/bin/python demo.py` (flujo completo con LLM). Sin LLM: `./revisor revisar-texto --fichero
ejemplos/observacion_borrador.txt --sin-llm` y los round-trips de `formato_md`.
