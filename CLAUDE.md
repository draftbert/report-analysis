# Revisor de informes de auditoría interna

Herramienta Python para las fases 7–9 del proceso de auditoría interna. Ver README.md
(uso) e INFORME_PLANTEAMIENTO.md (por qué está diseñada así).

## Principios que no se rompen
- **El modelo propone, el auditor decide.** Ninguna acción escribe fuera del expediente;
  antes de sobreescribir un fichero editable se guarda snapshot en `historial/`.
- **El criterio de estilo vive solo en `config/estilo.yaml`.** Se aplica de forma determinista
  (`style_checker.py`) y se inyecta en los prompts (`reglas_como_texto`). No duplicar reglas en código.
- **Formato pivote:** los esquemas Pydantic de `esquemas.py` (4C + recomendación). Cualquier campo
  nuevo debe añadirse ahí (es lo que viaja al modelo como schema estricto) y en `formato_md.py`
  (render y parse), y comprobarse con el round-trip informe/observaciones.
- **Toda salida del LLM se vuelve a validar con las reglas** y queda trazada en `trazas/`.
- **KAIA:** solo se usa salida estructurada (`output_format_schema` con `to_strict_json_schema`);
  no enviar `temperature` a modelos `gpt-5*`/`o*`. Ver `kaia_client.py`.
- **python-pptx con plantilla corporativa:** asignar `run.text`, nunca `text_frame.text`.

## Mapa
`cli.py` (comandos/menú) → `acciones.py` (flujo) → `expediente.py` (ficheros) + `formato_md.py`
(Markdown ↔ dict) + `lectores.py` (entrada/ → Markdown) + `llm.py`/`kaia_client.py` (modelo) +
`style_checker.py` (reglas) + `ppt_builder.py`.

- Nivel de riesgo sin evidencia en el PT: coletilla `(propuesto por el modelo, sin evidencia en PT)`;
  la quita `aprobar`; `redactar` no admite observaciones que la conserven.
- `aplicar-cambios`: sustituciones acotadas por sección, sin aproximaciones (solo tildes/espacios),
  ambiguo = no aplicado, contradictorio = CONFLICTO. Cada caso raro nuevo va a `tests/test_aplicar_cambios.py`.

## Pruebas rápidas
`.venv/bin/python -m pytest -q tests` (determinista, sin red). `.venv/bin/python demo.py` (flujo completo con LLM). Sin LLM: `./revisor revisar-texto --fichero
ejemplos/observacion_borrador.txt --sin-llm` y los round-trips de `formato_md`.
