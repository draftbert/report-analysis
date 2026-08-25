# Informe de planteamiento: agente IA de apoyo al proceso de auditoría interna

## 1. Qué problema se resuelve y dónde

Del procedimiento documentado se desprende que el mayor esfuerzo y la mayor repetitividad se concentran en la segunda mitad del proceso: documentación de papeles de trabajo (Fase 6), extracción de observaciones y recomendaciones (Fase 7), limpieza y estandarización del lenguaje (Fase 8), volcado al PPT (Fase 9) y las iteraciones de aprobación con Gerente y Directora (Fases 10–11). La fase de aprobación de Dirección es, según el propio procedimiento, la más costosa, y buena parte de esas iteraciones son correcciones de estilo, estructura y homogeneidad que se pueden anticipar antes de escalar. Ahí es donde un agente revisor tiene retorno inmediato: cada infracción de estilo detectada antes de la revisión del Gerente es una ida y vuelta que no ocurre.

Las fases iniciales (design thinking de riesgos, revisión normativa) también son candidatas, pero de segunda ola: en temas maduros el valor está en reutilizar el histórico, y para eso primero hace falta que el histórico esté estructurado, que es justo lo que producen las fases 7–9 asistidas por el agente. El orden correcto de implantación es, por tanto, empezar por el final del proceso.

## 2. Decisión de arquitectura: Python propio vs. plataforma GenAI interna

La duda planteada era si construirlo en Python o sobre el sistema de flujos GenAI interno. La recomendación es un enfoque híbrido con el núcleo en Python, por estas razones:

**A favor de Python propio.** El corazón de la herramienta no es el LLM: es la lógica determinista (palabras prohibidas, estructura obligatoria de la observación, validación de niveles de riesgo) y la generación de ficheros (PPTX). Las reglas deterministas deben ser reproducibles y auditables —el mismo texto debe producir siempre el mismo dictamen, algo esencial en un contexto de auditoría— y eso se consigue con código versionado, no con prompts. La generación del PPT sobre la plantilla corporativa real requiere python-pptx o manipulación de OOXML, que un orquestador de flujos no hace bien. Y el guardado de estados intermedios (JSON de observaciones, versiones del borrador) es trivial en ficheros o una base de datos ligera, mientras que en plataformas de flujos suele ser incómodo, como ya intuías.

**A favor de la plataforma interna.** Probablemente resuelve dos cosas que no conviene reinventar: el acceso autorizado y gobernado al modelo (claves, cuotas, logging, cumplimiento de la política interna de IA) y, en su caso, la interfaz de usuario para auditores no técnicos. Además, usar el canal corporativo aprobado evita fricciones de seguridad de la información: los papeles de trabajo son confidenciales y no deberían salir por una clave de API personal.

**Conclusión práctica.** Núcleo en Python (este piloto), con el cliente LLM encapsulado en un único módulo (`llm.py`) de modo que cambiar "API de Claude directa" por "endpoint de la plataforma interna" sea tocar un solo fichero. Si más adelante la plataforma interna permite exponer el agente como flujo para el resto del equipo, el Python se envuelve como servicio y el flujo interno solo orquesta.

## 3. Arquitectura del agente

El diseño sigue un patrón de tres capas que conviene mantener al escalar:

**Capa 1 — Reglas deterministas (sin LLM).** `style_checker.py` + `config/estilo.yaml`. Detecta palabras prohibidas, primera persona, frases largas, campos ausentes y niveles de riesgo inválidos. Es instantánea, gratuita, y constituye el "contrato" verificable del estilo corporativo. El YAML es el punto de mantenimiento: los auditores añaden términos sin tocar código.

**Capa 2 — LLM dirigido.** El modelo no reescribe "a su gusto": recibe las infracciones concretas detectadas por la capa 1 y las instrucciones de estilo, y su salida se vuelve a pasar por la capa 1 antes de mostrarse. Una reescritura que siga infringiendo reglas se marca, nunca se da por buena. Este bucle regla→LLM→regla es lo que hace al agente fiable.

**Capa 3 — Generación de entregables.** El JSON estructurado de observaciones (esquema 4C: condición, criterio, causa raíz, efecto, más recomendación, riesgo y responsable) es el formato pivote de todo el sistema: es lo que se extrae de los papeles de trabajo, lo que se revisa, y lo que alimenta el PPT. Formalizar este esquema tiene un beneficio lateral importante que ya apuntaba tu propio análisis comparativo con los marcos del IIA/COSO: fuerza la vinculación observación–criterio–causa–recomendación que hoy no siempre es sistemática.

**Principio de gobernanza transversal:** el agente propone y el auditor dispone. Nada se escribe en Pentana automáticamente, ningún texto va al informe sin validación humana, y toda salida del LLM queda trazada junto a su entrada (imprescindible si algún día hay que explicar cómo se redactó una observación).

## 4. Hoja de ruta propuesta

**Fase piloto (este entregable, 2–4 semanas de uso real).** El revisor de estilo y el generador de PPT en línea de comandos, usados por 1–2 auditores en una auditoría real. Objetivo: calibrar el YAML de estilo con las palabras prohibidas reales del departamento (las incluidas son plausibles pero inventadas) y medir cuántas correcciones de Gerente/Directora se anticipan.

**Iteración 2 — Plantilla real y entrada Pentana.** Sustituir el PPT autónomo por la `.potx` corporativa (mismo código, abriendo la plantilla) y alimentar el extractor con exportaciones reales de papeles de trabajo de Pentana (probablemente Excel/Word/PDF, según lo que Pentana permita exportar). Aquí conviene añadir una interfaz mínima (una app Streamlit sirve) para que lo use todo el equipo sin terminal.

**Iteración 3 — Memoria histórica.** Indexar observaciones de auditorías cerradas y, al redactar una nueva, sugerir observaciones y recomendaciones similares del histórico. Es la funcionalidad de mayor valor para temas maduros (SCIIF) y responde directamente al punto 6 de tu comparación con los marcos estándar. Técnicamente: embeddings + búsqueda semántica sobre el JSON estructurado que las iteraciones anteriores ya habrán ido acumulando.

**Iteración 4 — Apoyo a planificación.** Con histórico estructurado, el agente puede generar borradores de matriz de riesgos y plan de pruebas para temas recurrentes (Fase 2 "madura") y actuar como sparring de brainstorming en temas nuevos.

**Qué medir desde el día uno:** nº de infracciones detectadas por observación, nº de iteraciones con Gerente/Directora antes y después, tiempo de la Fase 8–9 por informe. Sin esa línea base no podrás justificar la inversión de las iteraciones siguientes (punto 7 de tu propio análisis).

## 5. Trabajo con Claude Code y Fable

Para desarrollar sobre este piloto con Claude Code, lo más eficaz es crear en la raíz del proyecto un fichero `CLAUDE.md` con el contexto que el agente de código debe respetar: el principio "propone, no decide", que el criterio de estilo vive solo en `config/estilo.yaml`, que el esquema de observación es el formato pivote y no debe romperse, y las precauciones de python-pptx con plantillas (asignar `run.text`, nunca `text_frame.text`). Con eso, peticiones del tipo "añade soporte para leer exportaciones Excel de Pentana al extractor" salen alineadas con la arquitectura. La documentación de Claude Code está en https://docs.claude.com/en/docs/claude-code/overview y la de la API (para `llm.py`) en https://docs.claude.com/en/api/overview.

Sobre el modelo: el piloto usa `claude-sonnet-4-6` por equilibrio coste/calidad para reescritura y extracción; para la conclusión de la evaluación global o casos complejos puede elevarse el modelo puntualmente, ya que es un parámetro del cliente.

## 6. Riesgos y salvaguardas

Confidencialidad: los papeles de trabajo no deben enviarse a servicios no aprobados; validar con Seguridad de la Información el canal de acceso al modelo antes de usar datos reales (de ahí la conveniencia de la plataforma interna como transporte). Alucinación: el extractor tiene instrucción explícita de dejar campos vacíos antes que inventar, y la revisión humana es obligatoria; aun así, conviene una regla adicional en la capa determinista que verifique que toda cifra presente en la salida existe en el papel de trabajo de origen (buena mejora para la iteración 2). Dependencia: el YAML y el esquema garantizan que el conocimiento del estilo queda en el repositorio, no en las cabezas ni en el modelo.
