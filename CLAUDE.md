# Revisor de informes de auditoría interna

Herramienta Python para las fases 7–9 del proceso de auditoría interna. Ver README.md
(uso) e INFORME_PLANTEAMIENTO.md (por qué está diseñada así).

## Principios que no se rompen
- **El modelo propone, el auditor decide.** Ninguna acción escribe fuera del expediente;
  antes de sobreescribir un fichero editable se guarda snapshot en `historial/`.
- **El criterio de estilo vive solo en `config/`**: `estilo.yaml` (reglas), `textos_informe.yaml` (frases fijas),
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
- **python-pptx con plantilla corporativa:** asignar `run.text`, nunca `text_frame.text`.

## Mapa
`cli.py` (comandos/menú) → `acciones.py` (flujo) → `expediente.py` (ficheros) + `formato_md.py`
(Markdown ↔ dict) + `lectores.py` + `extractores/` (contexto/ y papeles_trabajo/ → Markdown; docx/pdf/pptx/xlsx con los extractores
de audit-engine, ficheros con sufijo `_` para no sombrear a python-docx/python-pptx) + `llm.py`/`kaia_client.py` (modelo) +
`style_checker.py` (reglas) + `ppt_builder.py` + `calibracion.py` (estilo.yaml vs informes aprobados).

- Entrada: `contexto/` (design thinking; alimenta intro/resumen, solo orienta a extraer) y `papeles_trabajo/`
  (fuente de las conclusiones). `entrada/` antiguo se lee como papeles_trabajo.
- Flujo: redactar-contexto (intro+resumen) → extraer (conclusiones) → aprobar → recomendar →
  redactar-conclusiones → aplicar-cambios/reunion/cambio/chat/revisar/corregir → ppt → archivar.
- `reunion`: la transcripción NO se aplica directamente; el modelo la separa en texto (→ 03_instrucciones.md,
  el auditor revisa) / PPT (informativo) / pendientes / acuerdos, y `aplicar-cambios` hace el resto.
- Nivel de riesgo sin evidencia en el PT: coletilla `(propuesto por el modelo, sin evidencia en PT)`;
  la quita `aprobar`; `redactar-conclusiones` no admite conclusiones que la conserven.
- `aplicar-cambios`: sustituciones acotadas por sección, sin aproximaciones (solo tildes/espacios),
  ambiguo = no aplicado, contradictorio = CONFLICTO. Cada caso raro nuevo va a `tests/test_aplicar_cambios.py`.

## Pruebas rápidas
`.venv/bin/python -m pytest -q tests` (determinista, sin red). `.venv/bin/python demo.py` (flujo completo con LLM). Sin LLM: `./revisor revisar-texto --fichero
ejemplos/observacion_borrador.txt --sin-llm` y los round-trips de `formato_md`.
