# Estilo de los informes de auditoría interna (notas de calibración)

Fuente: tres informes aprobados (Gestión de sobrante de campaña, Gobierno de
accesos SAP, Integridad de datos en sistemas informacionales; 2025), leídos
diapositiva a diapositiva, más la calibración determinista de `estilo.yaml`
sobre ellos (`./revisor calibrar-estilo docs/referencia/informes_aprobados`).
Estas notas son la base del registro que se inyecta en los prompts
(`SYSTEM_BASE` en `acciones.py`), de los textos fijos (`config/textos_informe.yaml`)
y de la exportación a PPT (`ppt_builder.py`, sobre la plantilla corporativa
`config/plantilla_informe.pptx`, que fija fuentes, colores y tablas).

## 1. Estructura del informe (idéntica en los tres)

1. **Portada**: «CONFIDENCIAL» · «Informe de Auditoría Interna» · título · «Lista de
   Distribución» (áreas) · mes y año · «Ref.: 2025_787».
2. **Índice**: Introducción · Resumen ejecutivo · Detalle de conclusiones ·
   Sugerencias de mejora · Anexos (y una portadilla de sección antes de cada bloque).
3. **Introducción** (una diapositiva), con bloques etiquetados:
   - Frase fija inicial: «La auditoría ha sido realizada en cumplimiento del Plan de
     Auditoría del año 2025, aprobado por la Comisión de Auditoría y Cumplimiento.»
   - **Contexto:** · **Objetivo de la auditoría:** (con «Entre otros, los principales
     aspectos que se han revisado están relacionados con:» y lista «/») ·
     **Riesgos** / **Riesgos a cubrir:** · **Alcance de la auditoría:** (sistemas,
     mercados, periodo).
   - Panel «**Principales magnitudes**» con cifras clave (usuarios activos, stock,
     cargas, importes…).
   - Pie fijo: «El trabajo ha sido llevado a cabo de acuerdo con las Normas
     Internacionales para la Práctica Profesional de Auditoría Interna, según
     certificado emitido por el Instituto de Auditores Internos.» y «La explicación de
     los conceptos clave e instrucciones para la remisión de los planes de acción se
     incluyen en: [enlace]».
4. **Resumen ejecutivo** (una diapositiva): texto a la izquierda; a la derecha
   «Nº de observaciones emitidas» (tabla área × Crítico/Alto/Medio/Bajo),
   «**Evaluación Global**» en la escala Deficiente / Insuficiente / Mejorable /
   Razonable / Adecuado, y «**Próximos pasos**» con texto fijo: «Los destinatarios del
   presente informe deberán remitir su conformidad sobre el mismo al Departamento de
   Auditoría Interna. En el Anexo se recogerán los planes de acción a implantar para
   solventar las incidencias identificadas acorde al plazo acordado de implantación.»
5. **Detalle de conclusiones**: una por diapositiva (con «(Continuación)» si no cabe;
   a veces el título de la diapositiva es el tema: «Integridad y Calidad»). Banda
   lateral «RIESGO ALTO/MEDIO/…», «NN Título», cuerpo, y columna derecha con
   «Recomendación NN.1», «NN.2»… (cada una con su Área / Responsable / Plazo, y a
   veces estado «En proceso de implantación»).
6. **Sugerencias de mejora**: párrafo fijo «A continuación, se muestran las debilidades
   identificadas para las que, dado su impacto limitado, no se exigirá la elaboración
   de un plan de acción específico, si bien se exponen para su consideración con el
   objetivo de mejorar el nivel de control.» Después, bloques «RIESGO BAJO» · «NN
   Título» · cuerpo breve · «Sugerencia de mejora N» · Área (sin responsable ni plazo).
7. **Anexo: planes de acción**: tabla N.º · Observación · Rec. N.º · Plan de Acción ·
   Persona y Área Responsable · Plazo. Cierre «Gracias».

## 2. Tono y registro

- **Primera persona del plural para las actuaciones del equipo auditor** («hemos
  revisado», «hemos identificado», «durante nuestra revisión», «validamos»,
  «confirmamos», «destacamos», «resaltamos», «consideramos», «sugerimos») e
  **impersonal para los hechos y el "deber ser"** («se ha identificado», «debe
  apoyarse en», «se observa»). Calibración: 32 «hemos» en los aprobados → la regla
  de primera persona del YAML inicial era un falso positivo y se ha retirado.
- Formal, sobrio, orientado a proceso y control; sin culpabilizar a personas.
- **Cuantificado**: cifras, porcentajes, importes, fechas y periodos integrados en la
  prosa («En concreto, durante 2024, el 1,8 % de los MCC vendidos…, que asciende a 8k
  MCC de un total de 458k»; «3.586 veces… una media de 38 accesos al día»).
- Frases largas bien puntuadas son habituales (7,9 % superan 45 palabras) → límite
  orientativo subido a 55.
- Conectores característicos: «Durante nuestra revisión», «En concreto», «Cabe
  destacar», «Por otro lado», «Asimismo», «No obstante», «Sin embargo», «Por último»,
  «Respecto a la materialización».
- Terminología: observación / conclusión, debilidad, deficiencia de control,
  incidencia, aspecto de mejora, riesgo (Crítico/Alto/Medio/Bajo), control
  mitigante, factores mitigantes, materialización, plan de acción, recomendación,
  sugerencia de mejora, área responsable, plazo. «Grupo ITX», «la Compañía».
- «grave», «fraude», «problema», «siempre» aparecen puntualmente en usos legítimos
  («incidente grave», «riesgo de fraude», «siempre que sea posible»): no son
  prohibiciones absolutas sino avisos a revisar.

## 3. Patrón de una conclusión (cuerpo)

1. **El «deber ser»** del control, en impersonal: «La venta de mercancía a salderos
   debe estar regulada por un contrato bilateral que…», «Estos terceros deben ser
   analizados inicial y periódicamente…».
2. **Lo identificado**: «Durante nuestra revisión hemos identificado…», «Hemos
   revisado…, obteniendo que…». Varias debilidades → viñetas «/» (sub-puntos «a.»,
   «b.», «_»).
3. **Datos y evidencia** con cifras (muestras, recuentos, porcentajes, periodos,
   sistemas, usuarios).
4. **Efecto y riesgo**, enlazado en la prosa: «lo que genera: ambigüedad…», «lo que
   incrementa el riesgo de error…», «pudiendo derivar en costes operativos
   adicionales o reputacionales».
5. **Materialización y factores mitigantes**: «Respecto a la materialización, tras la
   revisión de logs… validamos que no se han ejecutado…», «Cabe destacar que existen
   factores mitigantes, como: i. … ii. …», «no ha sido posible cuantificar su impacto».

Títulos: frase nominal específica de la debilidad («Usuarios con permisos de
modificación en BBDD SAP HANA», «Elevado uso de accesos de emergencia con permisos
privilegiados en sistemas productivos SAP»); a veces oración completa.

## 4. Recomendaciones

Infinitivo, concretas y accionables: «Implantar…», «Definir…», «Establecer…»,
«Revisar…», «Migrar…», «Evaluar la viabilidad de…», «Reforzar…». Numeradas NN.1,
NN.2 (una por área/responsable), con sub-viñetas «_» cuando tienen varios puntos;
pueden remitir a una recomendación abierta anterior («Ref.-TMSCIIF-10») o llevar
estado («En proceso de implantación»). Sugerencias de mejora: «Sugerencia de mejora
N» + Área.

## 5. Resumen ejecutivo

Un párrafo de contexto (qué hace el área, iniciativas en curso); valoración general
(«A pesar de que el proceso cuenta con un elevado componente manual no se han
detectado deficiencias de control significativas. No obstante, se han identificado
determinadas mejoras operativas que se detallan a continuación:»); una viñeta «/» por
conclusión con una frase (debilidad + efecto); y, si procede, valoración de madurez
por ámbito y evaluación global explícita («consideramos que la evaluación del proceso
es insuficiente en su conjunto…»).

## 6. Qué se ha trasladado a la herramienta

- `config/estilo.yaml`: retirada la regla de primera persona («hemos», «nuestro/a»);
  escala de riesgo con «Crítico»; escala de evaluación global; límite de frase 55.
- `config/textos_informe.yaml`: frases fijas (plan de auditoría, normas, próximos
  pasos, intro de sugerencias, marcador de detalles).
- `SYSTEM_BASE` y prompts de `extraer` / `redactar-contexto`: registro, patrón de la
  conclusión, bloques de la introducción y del resumen ejecutivo, evaluación global.
- `02_informe.md` y `ppt`: portada, índice, portadillas, evaluación global, próximos
  pasos, párrafo fijo de sugerencias, anexo de planes de acción.
- `config/ejemplo_conclusion.md`: segundo ejemplo tomado de un informe aprobado.
