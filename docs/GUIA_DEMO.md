# Guía para hacer una demo del revisor de informes

Duración orientativa: **25–30 minutos** (cada llamada al modelo tarda 20–40 s;
aprovéchalas para explicar lo que está pasando). Público: auditores y
responsables del departamento, no técnicos.

La idea que debe quedar: **el auditor trabaja en una carpeta de ficheros de
texto durante días; la herramienta propone, la persona decide, y todo queda
trazado.**

---

## 0. Preparación (10 minutos antes, fuera de cámara)

```bash
cd revisor-informes
.venv/bin/python -m pytest -q tests        # todo en verde → el entorno está bien
./revisor -e expedientes/DEMO-TEC-2026 estado   # comprueba que KAIA responde: "LLM: kaia · gpt-5-mini"
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
  del paso 7 para pegarlo sin escribir en directo.
- Haz una pasada completa el día antes con `.venv/bin/python demo.py`: si algo
  falla, mejor saberlo entonces.

---

## 1. Crear el expediente y la entrada (2 min)

**Qué decir:** "Cada auditoría es una carpeta. Al empezar, el design thinking o
el memorando de planificación va a `contexto/`; cuando termina el trabajo de
campo, el papel de trabajo final (todas las pruebas) va a `papeles_trabajo/`;
el resto lo va generando la herramienta y lo edita el auditor."

```bash
./revisor nuevo expedientes/DEMO-VIVO --nombre "Auditoría de Transporte e-Commerce: tarifarios y SCA" \
    --referencia DEMO-VIVO --fecha "Junio 2026" \
    --distribucion "Dirección de Transporte e-Commerce, Dirección Financiera, Comité de Auditoría"
cp ejemplos/contexto_auditoria_tarifarios.md expedientes/DEMO-VIVO/contexto/
cp ejemplos/papel_trabajo_tarifarios.txt expedientes/DEMO-VIVO/papeles_trabajo/
./revisor estado
```

**Qué enseñar:** la carpeta en el explorador y la salida de `estado`:
`Fase: 1 · Contexto del informe`, los documentos de cada carpeta y el
**siguiente paso sugerido**. Abre `contexto/contexto_auditoria_tarifarios.md`
(el design thinking) y `papeles_trabajo/papel_trabajo_tarifarios.txt`: es la prueba 2.11 tal cual se pegó
desde Excel (contexto, objetivo, pruebas realizadas, conclusiones "CON
INCIDENCIAS" y referencia a la recomendación abierta TMSCIIF-10).

> Si preguntan por formatos: las dos carpetas admiten Word, Excel, PDF con texto, PowerPoint y
> texto pegado desde Excel (se normaliza solo).

---

## 2. Introducción y resumen ejecutivo (3 min, 1 llamada al modelo)

```bash
./revisor redactar-contexto
```

**Mientras responde (≈30 s), qué decir:** "El informe tiene cuatro partes:
introducción, resumen ejecutivo, detalle de conclusiones y sugerencias de
mejora. Empezamos por las dos primeras: el contexto, objetivo, riesgos y
magnitudes salen del design thinking; las pruebas y conclusiones, del papel de
trabajo. El auditor las lee y las deja a su gusto antes de seguir."

**Qué enseñar:** `02_informe.md` en vista previa: introducción y resumen ya
redactados; detalle y sugerencias marcados como *(pendiente)*. Edita una frase
en directo y guarda: "esto es un fichero de trabajo, no una salida".

---

## 3. Extraer las conclusiones (3 min, 1 llamada)

```bash
./revisor extraer
```

**Mientras responde:** "Recorre todas las pruebas del papel de trabajo. Solo
las concluidas CON INCIDENCIAS generan conclusiones, y cada una sigue siempre
la misma estructura: qué incidencia se ha detectado, por qué ha pasado, cómo
se ha llegado a ella (con los datos y tablas del papel) y sus consecuencias.
Tiene prohibido inventar."

**Qué enseñar cuando termine:**
- La lista: `[conc]`/`[suge]` (conclusión con recomendación vs sugerencia de
  mejora), el riesgo con asterisco (**propuesto por el modelo**, porque el
  papel no habla de severidad) y `rec. del PT` / `sin recomendación`.
- Abre `01_conclusiones.md`. Señala en un bloque los cinco campos, la línea
  `Prueba: 2.11 …` (trazabilidad), la coletilla del riesgo y, en la conclusión
  sobre el tarifario, que la **recomendación TMSCIIF-10 viene literal del
  papel** y no se ha reescrito.

---

## 4. El auditor revisa, aprueba y recomienda (4 min, 0–1 llamadas)

**Qué decir:** "Aquí manda el auditor: corrige, cambia el tipo si algo es solo
una sugerencia, aprueba, y decide las recomendaciones."

1. Edita en VS Code un texto cualquiera (o cambia `Tipo: conclusion` por
   `sugerencia` en una menor). Guarda.
2. `./revisor revisar-conclusiones` → reglas deterministas (vocabulario y
   campos), sin modelo. Abre `config/estilo.yaml`: "esta lista la mantiene el
   departamento".
3. `./revisor aprobar todas` → vuelve al fichero: `Estado: aprobada` y **la
   coletilla del riesgo ha desaparecido**. El mensaje avisa de cuáles no
   tienen recomendación.
4. `./revisor recomendar` → por cada aprobada sin recomendación **pregunta**:
   - en una, pega una frase tuya y Enter: "se registra tal cual, el modelo no
     la toca";
   - en otra, Enter en blanco: el modelo la propone y, si procede, añade una
     sugerencia de mejora complementaria (aparece como bloque nuevo en
     estado *propuesta*).

   Muestra el fichero: la tuya está literal; la del modelo, marcada para
   revisar.

---

## 5. Volcar las conclusiones al informe (1 min, sin modelo)

```bash
./revisor redactar-conclusiones
./revisor redactar-contexto --secciones resumen      # opcional, 1 llamada
```

**Qué decir:** "El volcado no pasa por el modelo: lo que el auditor aprobó va
tal cual al informe. Si alguna aprobada no tiene recomendación o conserva el
riesgo sin validar, no entra y se avisa." El segundo comando rehace solo el
resumen ejecutivo apoyándose en las conclusiones ya validadas.

**Qué enseñar:** `02_informe.md` completo en vista previa, de arriba abajo:
cada apartado de conclusión ya se lee como su diapositiva (título numerado,
prosa, «A continuación, se muestran los detalles descriptivos…», consecuencias,
**Recomendación N.1**). "Aquí es donde el auditor va a vivir los próximos días;
lo que se ve aquí es exactamente lo que exporta el botón de PPT."

---

## 6. Vocabulario prohibido y corrección dirigida (3 min, 1 llamada)

Escribe a mano en `02_informe.md`, en el resumen ejecutivo, algo así
(deliberadamente mal):

> Obviamente el problema se repite siempre y creemos que es culpa del gestor.

Guarda y:

```bash
./revisor revisar
./revisor corregir
```

**Qué enseñar:** el **diff**: solo se ha reescrito ese párrafo; y "Snapshot
previo en historial/ (`deshacer` lo restaura)".

---

## 7. La reunión de revisión: transcripción de Teams (4 min, 1–2 llamadas) — el momento fuerte

**Qué decir:** "Salgo de la reunión con el Gerente y la Directora con la
transcripción de Teams. Se la paso tal cual."

```bash
./revisor reunion ejemplos/transcript_reunion_teams.txt
```

**Qué enseñar, en este orden:**
1. El sistema **cuenta lo que ha detectado**, separado en dos: cambios en el
   **texto del informe** (dividir la recomendación 1.1 en dos con área,
   responsable y plazo, riesgo Alto, acortar una viñeta del resumen, quitar la
   viñeta de PackPro, nueva sugerencia de mejora…) y cambios en el **PPT**
   (gráfico de magnitudes, plantilla nueva, detalles en diapositiva aparte),
   que solo informa porque la presentación es beta.
2. **Pendientes**: el importe anual facturado no está en ningún sitio → no se
   inventa; queda como pendiente con quién lo aporta. Y los **acuerdos** que no
   tocan el informe (conformidad en diez días, seguimiento en enero).
3. El acta en `reuniones/` y las instrucciones de texto en
   `03_instrucciones.md`: "el auditor borra o edita lo que no proceda".
4. `./revisor aplicar-cambios` → plan, diff y registro (`reunion --aplicar` lo
   hace de una vez).

> Si preguntan "¿y si dos instrucciones se contradicen?": se aplica la primera
> y la segunda queda marcada como CONFLICTO; nunca se pisa en silencio.

**Y los cambios sueltos del día a día (1 min):**

```bash
./revisor cambio "En el resumen ejecutivo, sustituye 'que requieren mejora' por 'relevantes'"
./revisor chat            # o en modo chat: un mensaje, un diff; `deshacer` si no convence
```
(más mensajes de ejemplo en `ejemplos/mensajes_chat.txt`).

---

## 8. Entregable y cierre con evidencia (2 min, sin modelo)

```bash
./revisor ppt
./revisor archivar
./revisor estado
```

**Qué decir:** "`ppt` exporta el informe entero: cada apartado, una diapositiva."

**Qué enseñar:** el `.pptx` generado **sobre la plantilla corporativa real**
(`config/plantilla_informe.pptx`: mismas fuentes, imágenes, tablas y colores):
carátula (CONFIDENCIAL, lista de distribución, fecha y ref.), índice y portadillas,
introducción con la frase fija del plan y los bloques Contexto / Objetivo /
Riesgos a cubrir / Alcance / Principales magnitudes, resumen ejecutivo con el
punto en la escala de **Evaluación Global** y próximos pasos, **una tabla por
recomendación** (banda RIESGO, «NN Título», prosa, caja gris de detalles
descriptivos, consecuencias, Recomendación N.1, Ref., Área / Responsable /
Plazo; «(continuación)» si no cabe), sugerencias de mejora (RIESGO BAJO y
párrafo fijo), anexo de planes de acción; el zip de `archivar` con `trazas/`,
`historial/`, informe, PPT y `manifest.json` con sha256 ("esto se adjunta al
expediente en Pentana"); y una traza JSON medio segundo: prompt, respuesta,
tokens.

---

## 9. Cierre (1 min)

Tres mensajes:
1. **Propone, no decide**: ningún texto va al informe sin pasar por el auditor,
   y su recomendación se respeta al 100 %.
2. **Determinista donde importa**: vocabulario y estructura son reglas del
   departamento (`estilo.yaml`); el volcado al informe no pasa por el modelo.
3. **Trazable**: cada salida del modelo queda ligada a su entrada y se archiva
   con el expediente.

Siguiente paso: calibrar el vocabulario con informes reales
(`./revisor calibrar-estilo <carpeta>`) y conectar la exportación real de Pentana.

---

## Alternativa sin terminal: el menú

Si el público se incomoda con comandos, haz toda la demo desde el menú
numerado, que muestra el estado y el siguiente paso en cada vuelta:

```bash
./revisor menu
```

Las opciones siguen el mismo orden que esta guía (redactar-contexto → extraer →
aprobar todas → recomendar → redactar-conclusiones → revisar → corregir →
aplicar-cambios → reunion → chat → ppt → archivar).

## Plan B: sin acceso al modelo

- **Todo lo determinista funciona igual**: `estado`, `revisar-conclusiones`,
  `aprobar`, `redactar-conclusiones`, `revisar`, `diff`, `deshacer`, `historial`,
  `ppt`, `archivar`. Puedes hacer los pasos 4 (sin `recomendar`), 5, 6 (solo
  `revisar`) y 8 sobre el expediente `expedientes/DEMO-TEC-2026`, que trae
  conclusiones e informe generados por el modelo en una ejecución anterior.
- Para enseñar el resultado de los pasos con modelo, abre en vista previa los
  ficheros de ese expediente y su `cambios_aplicados.md`.
- `./revisor revisar-texto --fichero ejemplos/observacion_borrador.txt --sin-llm`
  es un buen abridor: un párrafo con ocho infracciones detectadas al instante.

## Errores típicos en directo

| Síntoma | Causa | Qué hacer |
|---|---|---|
| `LLM: no disponible` en `estado` | `.env` sin credenciales o token caducado | Revisar `.env`; la demo determinista sigue siendo posible |
| `01_conclusiones.md ya existe...` | Repetir `extraer` sobre un expediente usado | `--forzar` (guarda snapshot) o expediente nuevo |
| `02_informe.md ya tiene introducción/resumen` | Repetir `redactar-contexto` | `--forzar` o `--secciones resumen` |
| `No hay conclusiones con Estado: aprobada` | Se saltó el paso 4 | `./revisor aprobar todas` |
| `Ninguna conclusión aprobada está lista` | Falta recomendación o el riesgo sigue «propuesto» | `./revisor recomendar` / `aprobar` |
| `03_instrucciones.md está vacío` | El texto se pegó encima de la línea `---` | Pegarlo debajo del `---` |
| Una llamada tarda más de un minuto | Cola en KAIA | Esperar; mientras, enseñar `config/estilo.yaml` o una traza |
| `Hay varios expedientes; indica cuál` | Más de un expediente sin activo fijado | `./revisor usar expedientes/DEMO-VIVO` |
