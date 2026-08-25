# Guía para hacer una demo del revisor de informes

Duración orientativa: **20–25 minutos** (cada llamada al modelo tarda 20–40 s;
aprovéchalas para explicar lo que está pasando). Público: auditores y
responsables del departamento, no técnicos.

La idea que debe quedar: **el auditor trabaja en una carpeta de ficheros de
texto durante días; la herramienta propone, la persona decide, y todo queda
trazado.**

---

## 0. Preparación (10 minutos antes, fuera de cámara)

```bash
cd revisor-informes
.venv/bin/python -m pytest -q tests        # 37 passed → el entorno está bien
./revisor -e expedientes/DEMO-CNC-2026-03 estado   # comprueba que KAIA responde: "LLM: kaia · gpt-5-mini"
```

- Si `estado` dice `LLM: no disponible`, revisa `.env` (credenciales `KAIA_*`).
  Sin modelo la demo no tiene sentido: ve al **plan B** del final.
- Abre VS Code en la carpeta del repo, con el terminal integrado abajo y la
  **vista previa Markdown** a la derecha (`Ctrl+Shift+V` sobre un `.md`).
- Borra el expediente de la demo anterior para empezar limpio:

```bash
rm -rf expedientes/DEMO-VIVO && rm -f .expediente_activo
```

- Ten a mano, en un bloc de notas, el texto de la "transcripción de reunión"
  del paso 6 para pegarlo sin escribir en directo.
- Haz una pasada completa el día antes con `.venv/bin/python demo.py`: si algo
  falla, mejor saberlo entonces.

---

## 1. Crear el expediente y la entrada (2 min)

**Qué decir:** "Cada auditoría es una carpeta. Lo que viene de Pentana se deja
en `entrada/`; el resto lo va generando la herramienta y lo edita el auditor."

```bash
./revisor nuevo expedientes/DEMO-VIVO --nombre "Auditoría de Compras No Comerciales" \
    --referencia DEMO-VIVO --fecha "Mayo 2026" \
    --distribucion "Dirección de Compras, Dirección Financiera, Comité de Auditoría" --ejemplo
./revisor estado
```

**Qué enseñar:** la carpeta en el explorador de VS Code (`entrada/`,
`03_instrucciones.md`, `expediente.yaml`) y la salida de `estado`:
`Fase: 1 · Entrada lista` y el **siguiente paso sugerido**. Abre
`entrada/papel_trabajo_compras.md` en vista previa: es un papel de trabajo
normal (prueba, resultados, comentarios del área, evidencias).

> Si preguntan por formatos: `entrada/` admite Word, Excel y PDF con texto.
> Puedes soltar ahí `ejemplos/entrada_sintetica/papel_trabajo_compras.docx`
> para enseñarlo, pero para la demo basta con el `.md`.

---

## 2. Extraer observaciones y recomendaciones (3 min, 1 llamada al modelo)

```bash
./revisor extraer
```

**Mientras responde (≈30 s), qué decir:** "El modelo lee el papel de trabajo y
propone observaciones en el esquema de las 4C: condición, criterio, causa
raíz, efecto y recomendación. Tiene prohibido inventar: si el papel no dice
la causa, deja el campo vacío."

**Qué enseñar cuando termine:**
- La lista con `[Alto*]`, `[Medio*]`: el asterisco significa que el nivel de
  riesgo es **propuesto por el modelo** porque el papel de trabajo no habla de
  severidad.
- Abre `01_observaciones.md` en vista previa. Señala:
  - la línea `Nivel de riesgo: Medio (propuesto por el modelo, sin evidencia en PT)`;
  - `Fuente:` con la referencia al papel de trabajo (trazabilidad);
  - algún campo vacío (`Causa raíz:` en la de ofertas comparativas): "no lo
    dice el papel, no se lo inventa";
  - el bloque de instrucciones de la cabecera: el auditor edita aquí.

---

## 3. El auditor revisa y aprueba (3 min, sin modelo)

**Qué decir:** "Aquí es donde el auditor manda. Lee, corrige y aprueba."

1. Edita en VS Code, en directo, un texto cualquiera de una observación (por
   ejemplo, acorta una recomendación). Guarda.
2. Enseña la revisión determinista de vocabulario:

```bash
./revisor revisar-obs
```

   Señala que los hallazgos son **reglas, no modelo**: mismo texto, mismo
   resultado siempre. Abre `config/estilo.yaml`: "esta lista la mantiene el
   departamento, sin tocar código".

3. Aprueba:

```bash
./revisor aprobar todas
```

   Vuelve a `01_observaciones.md`: `Estado: aprobada` y **la coletilla del
   riesgo ha desaparecido**: "al aprobar, el auditor valida el nivel".

> Opcional si sobra tiempo: escribe en «Notas del auditor» de una observación
> "usa como causa raíz que el sistema no exige adjuntar ofertas y propón
> riesgo Medio" y ejecuta `./revisor regenerar-obs OBS-01`. Es la manera de
> pedirle al modelo que rehaga solo una observación.

---

## 4. Redactar el informe (3 min, 1 llamada)

```bash
./revisor redactar
```

**Mientras responde:** "Con las aprobadas, el modelo redacta el Resumen
Ejecutivo: objetivo, alcance, contexto, observaciones, evaluación global y
próximos pasos. No puede añadir ni quitar observaciones ni cambiar cifras."

**Qué enseñar:** `02_informe.md` en vista previa, de arriba abajo. Y el
mensaje final: `Revisión determinista: 0 errores` — ya sale cumpliendo el
vocabulario, porque las reglas del YAML también van en el prompt.

**Frase clave:** "Este fichero es donde el auditor va a vivir los próximos
días. Lo edita como quiera; la herramienta le ayuda cuando se lo pide."

---

## 5. Vocabulario prohibido y corrección dirigida (3 min, 1 llamada)

Escribe a mano en `02_informe.md`, en el párrafo de **Próximos pasos**, algo
así (deliberadamente mal):

> Obviamente el problema se repite siempre y creemos que es culpa del gestor.

Guarda y:

```bash
./revisor revisar
```

Señala los hallazgos con número de línea y sugerencia. Luego:

```bash
./revisor corregir
```

**Qué enseñar:** el **diff**: solo se ha reescrito ese párrafo, el resto del
informe no se ha tocado; y "Snapshot previo en historial/ (`deshacer` lo
restaura)". Si quieres, enséñalo:

```bash
./revisor deshacer      # vuelve al párrafo malo
./revisor corregir      # lo arregla otra vez
```

---

## 6. Aplicar los comentarios de una reunión (4 min, 1 llamada) — el momento fuerte

**Qué decir:** "Salgo de la reunión con el Gerente con notas o una
transcripción. En vez de editar a mano, lo pego aquí."

Abre `03_instrucciones.md` y pega **debajo de la línea `---`** (ten el texto
preparado):

```
Reunión de cierre con el Gerente, 26/05:
GERENTE: La observación de segregación de funciones (la de la delegación no
revertida) queda como riesgo Alto y el responsable es solo Dirección de
Sistemas. La de las ofertas comparativas, riesgo Medio. En próximos pasos
añade que el seguimiento se hará en el primer trimestre de 2027. Y pon el
importe total auditado en el contexto.
```

Guarda y:

```bash
./revisor aplicar-cambios
```

**Qué enseñar, en este orden:**
1. El **plan de cambios**: cada instrucción convertida en un cambio concreto,
   con la sección exacta donde se aplica.
2. **Pendientes**: "el importe total auditado" no está en ningún sitio → el
   modelo **no se lo inventa**, lo devuelve como pendiente para el auditor.
   (Este es el punto que más tranquiliza a un auditor: díselo.)
3. El diff: el riesgo Alto ha ido a la observación correcta, no a la primera.
4. `cambios_aplicados.md`: registro de lo que se pidió, lo que se cambió y lo
   que no; `03_instrucciones.md` ha quedado vacío y lo pegado está en
   `historial/`.

> Si preguntan "¿y si dos instrucciones se contradicen?": se aplica la primera
> y la segunda queda marcada como CONFLICTO con referencia a la primera; nunca
> se pisa en silencio.

---

## 7. Entregable y cierre con evidencia (2 min, sin modelo)

```bash
./revisor ppt
./revisor archivar
./revisor estado
```

**Qué enseñar:**
- Abre el `.pptx` de `salidas/`: carátula, objetivo/alcance, magnitudes,
  índice de observaciones, una diapositiva por observación con su chip de
  riesgo, evaluación global, próximos pasos. "Es un diseño sobrio; lo
  siguiente es rellenar la plantilla corporativa real con este mismo código."
- El zip de `archivar`: `trazas/` (cada llamada al modelo con su prompt y
  respuesta), `historial/` (cada versión), informe y PPT, y `manifest.json`
  con el sha256 de cada fichero. "Esto se adjunta al expediente en Pentana:
  se puede demostrar cómo se redactó cada observación y que nada se ha
  alterado."
- Abre una traza JSON de `trazas/` medio segundo: prompt, respuesta, tokens.

---

## 8. Cierre (1 min)

Tres mensajes:
1. **Propone, no decide**: ningún texto va al informe sin pasar por el auditor.
2. **Determinista donde importa**: el vocabulario y la estructura son reglas
   del departamento (`estilo.yaml`), reproducibles y auditables.
3. **Trazable**: cada salida del modelo queda ligada a su entrada, y se archiva
   con el expediente.

Y el siguiente paso: calibrar el vocabulario con informes reales
(`./revisor calibrar-estilo <carpeta_de_informes_aprobados>`) y conectar la
exportación real de Pentana.

---

## Alternativa sin terminal: el menú

Si el público se incomoda con comandos, haz toda la demo desde el menú
numerado, que muestra el estado y el siguiente paso en cada vuelta:

```bash
./revisor menu
```

Las opciones siguen el mismo orden que esta guía (extraer → aprobar todas →
redactar → revisar → corregir → aplicar-cambios → ppt → archivar).

## Plan B: sin acceso al modelo

- **Todo lo determinista funciona igual**: `estado`, `revisar-obs`, `aprobar`,
  `revisar`, `diff`, `deshacer`, `historial`, `ppt`, `archivar`. Puedes hacer
  los pasos 3, 5 (solo `revisar`), 7 y 8 sobre el expediente
  `expedientes/DEMO-CNC-2026-03`, que ya trae observaciones e informe
  generados por el modelo en una ejecución anterior.
- Para enseñar el resultado de los pasos con modelo, abre en vista previa los
  ficheros de ese expediente y su `cambios_aplicados.md`.
- `./revisor revisar-texto --fichero ejemplos/observacion_borrador.txt --sin-llm`
  es un buen abridor: un párrafo con nueve infracciones detectadas al instante.

## Errores típicos en directo

| Síntoma | Causa | Qué hacer |
|---|---|---|
| `LLM: no disponible` en `estado` | `.env` sin credenciales o token caducado | Revisar `.env`; la demo determinista sigue siendo posible |
| `01_observaciones.md ya existe...` | Repetir `extraer` sobre un expediente usado | `--forzar` (guarda snapshot) o expediente nuevo |
| `No hay observaciones con Estado: aprobada` | Se saltó el paso 3 | `./revisor aprobar todas` |
| `03_instrucciones.md está vacío` | El texto se pegó encima de la línea `---` | Pegarlo debajo del `---` |
| Una llamada tarda más de un minuto | Cola en KAIA | Esperar; mientras, enseñar `config/estilo.yaml` o una traza |
| `Hay varios expedientes; indica cuál` | Más de un expediente sin activo fijado | `./revisor usar expedientes/DEMO-VIVO` |
