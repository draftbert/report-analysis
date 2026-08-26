# Detalle de conclusiones y sugerencias de mejora — DEMO-TEC-2026 · Auditoría de Transporte e-Commerce: tarifarios y SCA

> Cómo trabajar este fichero:
> - Cada bloque es una incidencia detectada en los papeles de trabajo: qué se ha
>   detectado, por qué (causa raíz), cómo se ha llegado (datos y tablas) y consecuencias.
> - `Tipo: conclusion` lleva recomendación y plan de acción; `Tipo: sugerencia` es una
>   mejora sin plan de acción (irá a «Sugerencias de mejora»). Cámbialo si procede.
> - Corrige el texto directamente y cambia `Estado: propuesta` por `aprobada` o `descartada`.
> - Recomendación: si la tienes, escríbela en «Recomendación:» y se respetará tal cual
>   (`recomendar` solo le da formato). Si la dejas vacía, `recomendar` la propone.
> - Si quieres que el modelo rehaga un bloque, escribe qué cambiar en «Notas del auditor»
>   y ejecuta `regenerar C-XX`. `revisar-conclusiones` comprueba vocabulario y campos.
> - Cuando estén aprobadas y con recomendación, ejecuta `redactar-conclusiones`.


## C-01 · Acuerdos de tarifario no comunicados al equipo de validación

- Tipo: conclusion
- Estado: propuesta
- Prueba: 2.11 b) Gestión del maestro de tarifas (quién las carga/modifica)
- Nivel de riesgo: Alto (propuesto por el modelo, sin evidencia en PT)
- Responsable: Operaciones (negociación) y equipos de validación de facturas (BDO, Serviguide, Inditex - China) con supervisión de Central e-Commerce
- Fuente: papel_trabajo_tarifarios.txt, apartado 2.11 (Flujo general; Conclusiones)

**Incidencia detectada:** En determinadas ocasiones, los acuerdos alcanzados entre Operativa y los proveedores no se transmiten al equipo de validación, provocando desactualización del maestro de tarifas y errores en la valoración de los costes de transporte.

**Causa raíz:** Falta de trazabilidad y evidencia formalizada de los acuerdos entre Operativa y el equipo de validación (ausencia de un mecanismo único y obligatorio de comunicación/registro).

**Cómo se ha llegado:**
- Revisión del flujo general de mantenimiento del maestro de tarifas descrito en el PT: pasos 1) a 4) (negociación por Operaciones, solicitud de plantilla a Operativa, sobreescritura manual en la Herramienta de Costes, grabación en Snowflake).
- Evidencia documental en el PT: ausencia de plantilla común y tareas manuales realizadas por equipos externos e internos (BDO, Serviguide, Inditex - China) bajo supervisión de Central e-Commerce.
- Tablas y objetos referenciados: TRANSPORT_BUSINESS.FOUNDATION.COSTES_ECOM_DETALLE (Snowflake) como destino de los costes validados.
- Conclusiones del PT que señalan la falta de transparencia y la consiguiente desactualización del tarifario.

**Consecuencias:** Registro de tarifas desactualizadas en la Herramienta de Costes y Snowflake; valoración incorrecta de costes; imputaciones erróneas en CPF y SCA que pueden provocar asignaciones inapropiadas de transportistas y afectación del coste operativo.

**Recomendación:** Implantar un sistema para la carga y gestión de los tarifarios de todas las operativas de transporte, así como la evidencia de los acuerdos alcanzados con los proveedores para garantizar la trazabilidad de estos con las tarifas cargadas.

**Notas del auditor:** 

## C-02 · CPF hereda y no corrige casuísticas minoritarias (COD y zonas remotas)

- Tipo: conclusion
- Estado: propuesta
- Prueba: 2.11 a) Contrastar el tarifario negociado con los transportistas, frente al valor cargado en la herramienta SCA/CPF
- Nivel de riesgo: Medio (propuesto por el modelo, sin evidencia en PT)
- Responsable: Equipo de Desarrollo de CPF y Transport Business Analytics
- Fuente: papel_trabajo_tarifarios.txt, apartado 2.11 (Debilidades del algoritmo CPF; Conclusiones)

**Incidencia detectada:** CPF no valora correctamente casuísticas minoritarias como el Cash On Delivery (COD) y entregas en zonas remotas, trasladando estas deficiencias al algoritmo de asignación de proveedores (SCA).

**Causa raíz:** Limitaciones del modelo de inferencia de CPF y ausencia de desagregación/normalización consistente de conceptos específicos (p. ej. desglose de costes COD, definición única de zonas remotas).

**Cómo se ha llegado:**
- Revisión de la sección 'Debilidades del algoritmo CPF' del PT donde se detallan las problemáticas: 2) COD no desglosado en factura y penalización del courier; 4) definición variable de zonas remotas entre couriers y falta de implementación en la herramienta.
- Descripción técnica en el PT: CPF entrena sobre facturas en bruto (histórico 4 meses) y no siempre dispone de los desgloses necesarios; la tabla en desarrollo TRANSPORT_BUSINESS.DATA.CPF_SIMULATION_RATES está prevista para mitigar cambios de tarifario.
- Referencias a sistemas: PackPro (embalaje), Snowflake (tabla COSTES_ECOM_DETALLE), y el método de inferencia de CPF.

**Consecuencias:** Asignaciones de proveedor subóptimas en SCA; posibles desviaciones en el coste estimado por pedido que afectan a la competitividad del pricing y al control del gasto logístico.

**Recomendación:** 

**Notas del auditor:** 

## C-03 · Mantenimiento del tarifario no automatizable por ausencia de plantilla común

- Tipo: conclusion
- Estado: propuesta
- Prueba: 2.11 b) Gestión del maestro de tarifas (quién las carga/modifica)
- Nivel de riesgo: Medio (propuesto por el modelo, sin evidencia en PT)
- Responsable: Equipos de validación de facturas (BDO, Serviguide, Inditex - China) con supervisión de Central e-Commerce
- Fuente: papel_trabajo_tarifarios.txt, apartado 2.11 (Flujo general; Conclusiones)

**Incidencia detectada:** El mantenimiento del maestro de tarifas se realiza de forma manual y no es automatizable por inexistencia de una plantilla común para la grabación de modificaciones en la Herramienta de Costes.

**Causa raíz:** Proceso manual con formatos heterogéneos por courier y ausencia de un formato estándar para la carga/actualización de tarifas en la Herramienta de Costes.

**Cómo se ha llegado:**
- Examen del 'Flujo general' del PT que describe el proceso manual: 1) renegociación por Operaciones; 2) solicitud de plantilla y sobreescritura manual por equipos de validación; 3) contraste y validación de importes; 4) grabación en Snowflake.
- Ejemplo práctico en el PT: pestaña 'Ej. tarifario - FedEx' que ilustra la introducción manual de tarifas por código postal y rangos de peso.
- Observaciones del PT sobre la heterogeneidad de formatos y la carga a nivel de CP indicada en el mantenimiento manual.

**Consecuencias:** Riesgo de inconsistencias y errores de captura en el maestro de tarifas; mayor esfuerzo operativo y limitación para escalar o actualizar tarifas con rapidez ante cambios comerciales.

**Recomendación:** 

**Notas del auditor:** 

## C-04 · Extracostes (p. ej. fuel) cuya actualización es inviable manualmente

- Tipo: conclusion
- Estado: propuesta
- Prueba: 2.11 b) Gestión del maestro de tarifas (quién las carga/modifica)
- Nivel de riesgo: Medio (propuesto por el modelo, sin evidencia en PT)
- Responsable: Equipos de validación de facturas (BDO, Serviguide, Inditex - China)
- Fuente: papel_trabajo_tarifarios.txt, apartado 2.11 (Debilidades reportadas en el mantenimiento de los tarifarios; Conclusiones)

**Incidencia detectada:** Determinados extracostes, como los derivados del precio del fuel que varían con frecuencia, no pueden actualizarse de forma viable mediante el proceso manual existente, superando la capacidad del equipo de validación.

**Causa raíz:** Volatilidad de ciertos conceptos tarifarios (p. ej. fuel) combinada con un proceso manual y recursos limitados para actualizaciones frecuentes.

**Cómo se ha llegado:**
- Identificación en el PT de las casuísticas particulares en el mantenimiento: dificultad en la actualización de tarifarios en USA por imputación de gastos de fuel que se actualizan semanalmente.
- Relación con el proceso manual descrito en el 'Flujo general' donde las actualizaciones son sobreescritas manualmente por los equipos de validación.
- Referencias a que el mercado afectado no está aún implementado en CPF, por lo que el impacto operativo descrito se limita al mantenimiento de la HC.

**Consecuencias:** Riesgo de desalineamiento entre tarifas aplicables y costes reales por cambios frecuentes en extracostes; aumento de ajustes y refacturaciones, y potencial impacto en la eficiencia de la validación de facturas.

**Recomendación:** 

**Notas del auditor:**
