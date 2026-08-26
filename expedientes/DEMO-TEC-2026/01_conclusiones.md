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


## C-01 · Acuerdos de tarifación no se transmiten al equipo de validación, provocando desactualización de tarifarios

- Tipo: conclusion
- Estado: aprobada
- Prueba: 2.11 b) Gestión del maestro de tarifas (quién las carga/modifica); revisar proceso de carga y actualización de tarifas
- Nivel de riesgo: Alto
- Responsable: 
- Fuente: papel_trabajo_tarifarios.txt - 2.11. PROCESO DE ACTUALIZACIÓN DE TARIFARIOS Y VOLCADO EN LAS HERRAMIENTAS DE E-COMMERCE; apartado "Flujo general" y CONCLUSIONES

**Incidencia detectada:** Se han identificado casos en los que los acuerdos alcanzados entre Operativa y los proveedores no se transparentan al equipo de validación, lo que implica desactualización del maestro de tarifas y errores en la valoración del coste de transporte.

**Causa raíz:** Falta de trazabilidad y evidencia formalizada de los acuerdos entre Operativa y los equipos de validación (ausencia de un sistema/plantilla común para registrar modificaciones).

**Cómo se ha llegado:**
- Revisión del flujo general de mantenimiento del maestro de tarifas descrito en la prueba (actualización manual por equipos de validación: BDO, Serviguide e Inditex - China; pasos 1 a 6).
- Identificación en las conclusiones del papel de trabajo de la afirmación: "en determinadas ocasiones, los acuerdos alcanzados entre Operativa y los proveedores no se transparentan al equipo de validación".
- Referencias técnicas del proceso: datos grabados en Snowflake (TRANSPORT_BUSINESS.FOUNDATION.COSTES_ECOM_DETALLE) y uso posterior por CPF/SCA para estimación de costes.
- Observación de la recomendación referenciada (Auditoría SCIIF 2022 TMSCIIF-10) que propone implantar un sistema para la carga y gestión de tarifarios y la evidencia de acuerdos.

**Consecuencias:** Registro de tarifas desactualizadas en la Herramienta de Costes y en Snowflake, estimaciones de coste erróneas y potenciales imputaciones incorrectas en SCA, con impacto en la asignación de transportistas y en el coste reportado.

**Recomendación:** Implantar un sistema para la carga y gestión de los tarifarios de todas las operativas de transporte, así como la evidencia de los acuerdos alcanzados con los proveedores para garantizar la trazabilidad de estos con las tarifas cargadas.

**Notas del auditor:** 

## C-02 · CPF hereda deficiencias en la valoración de casuísticas minoritarias (COD, zonas remotas) que impactan la asignación en SCA

- Tipo: conclusion
- Estado: aprobada
- Prueba: 2.11 a) Contrastar el tarifario negociado con los transportistas, frente al valor cargado en la herramienta SCA/CPF
- Nivel de riesgo: Medio
- Responsable: 
- Fuente: papel_trabajo_tarifarios.txt - 2.11. PROCESO...; apartado "Debilidades del algoritmo CPF" y CONCLUSIONES

**Incidencia detectada:** El algoritmo CPF no considera correctamente determinadas casuísticas (por ejemplo, Cash On Delivery y entregas en zonas remotas), lo que provoca que SCA reciba estimaciones de coste sesgadas que afectan la asignación de transportistas.

**Causa raíz:** Limitaciones del método de inferencia de CPF y de los datos de entrada (CPF entrena con facturas en bruto y no desglosa conceptos como COD; discrepancias en definición de zonas remotas entre couriers).

**Cómo se ha llegado:**
- Descripción del funcionamiento de CPF: toma histórico de últimos 4 meses y aplica método de inferencia; no requiere el tarifario asociado al transportista, sino costes reales de pedidos.
- Debilidades identificadas en el apartado "Debilidades del algoritmo CPF":
  1) COD no desglosado en factura y genera extracargos no imputados correctamente.
  2) Definición inconsistente de "zona remota" entre couriers, y asignación por Customer state que unifica conceptos.
  3) CPF entrena respecto de facturas en bruto, penalizando couriers con COD incluido.
- Referencia a tablas y flujos: datos de pedidos almacenados en TRANSPORT_BUSINESS.FOUNDATION.COSTES_ECOM_DETALLE y uso por CPF/CPF_SIMULATION_RATES.

**Consecuencias:** Estimaciones de coste incompletas o sesgadas para pedidos con COD o en zonas remotas, generando una asignación inadecuada de transportistas en SCA y posibles diferencias económicas en la operación.

**Recomendación:** Se recomienda actualizar el proceso de datos y el entrenamiento de CPF para incorporar la desagregación de COD y la estandarización de zonas remotas. Pasos mínimos: 1) adaptar ETL para registrar en TRANSPORT_BUSINESS.FOUNDATION.COSTES_ECOM_DETALLE campos desagregados: indicador_COD, importe_COD y código_zona_remota estandarizado; 2) acordar y documentar una definición única de "zona remota" y un mapa de correspondencia entre couriers; 3) retrenar CPF incorporando las nuevas variables y variables indicadoras por courier para COD y remotas; 4) implementar en SCA una regla de validación que contraste la estimación CPF con el tarifario negociado y que active una asignación alternativa o revisión cuando la estimación esté sesgada por ausencia de desglose COD o por inconsistencias de zona; 5) establecer monitorización periódica de desviaciones por COD y zonas remotas y reportes de rendimiento del modelo para ajuste continuo.

**Notas del auditor:** 

## C-03 · Mantenimiento del tarifario manual y sin plantilla común que impide automatización

- Tipo: conclusion
- Estado: aprobada
- Prueba: 2.11 b) Gestión del maestro de tarifas (quién las carga/modifica); revisar proceso de carga y actualización de tarifas
- Nivel de riesgo: Medio
- Responsable: 
- Fuente: papel_trabajo_tarifarios.txt - 2.11. PROCESO...; apartado "Flujo general" y CONCLUSIONES

**Incidencia detectada:** El mantenimiento del maestro de tarifas se realiza de forma manual y no existe una plantilla común para la grabación de modificaciones en la Herramienta de Costes, lo que impide automatizar el proceso.

**Causa raíz:** Ausencia de formatos estandarizados y de un sistema centralizado para la carga y gestión de tarifarios.

**Cómo se ha llegado:**
- Revisión del flujo descrito: Operaciones renegocia y facilita plantillas (formato diferente por courier); los equipos de validación sobreescriben manualmente los datos en la Herramienta de Costes (pasos 1 y 2 del flujo general).
- Observación en CONCLUSIONES: "El mantenimiento del tarifario no es automatizable, debido a que no existe una plantilla común para la grabación de modificaciones".
- Referencias técnicas: entradas manuales por Código Postal y registro de costes en Snowflake (TRANSPORT_BUSINESS.FOUNDATION.COSTES_ECOM_DETALLE) para su uso por CPF.

**Consecuencias:** Riesgo de inconsistencias y errores en la carga de tarifarios, mayor carga operativa manual y limitaciones para actualizar tarifas de forma oportuna, afectando la integridad de los datos utilizados por CPF/SCA.

**Recomendación:** Implantar un sistema para la carga y gestión de los tarifarios de todas las operativas de transporte, así como la evidencia de los acuerdos alcanzados con los proveedores para garantizar la trazabilidad de estos con las tarifas cargadas.

**Notas del auditor:** 

## C-04 · Actualización de extracostes (p. ej. fuel) inviable por capacidad manual, generando desajustes

- Tipo: conclusion
- Estado: aprobada
- Prueba: 2.11 b) Gestión del maestro de tarifas (quién las carga/modifica); revisar proceso de carga y actualización de tarifas
- Nivel de riesgo: Bajo
- Responsable: 
- Fuente: papel_trabajo_tarifarios.txt - 2.11. PROCESO...; apartado "Debilidades reportadas en el mantenimiento de los tarifarios" y CONCLUSIONES

**Incidencia detectada:** Determinados extracostes, como los vinculados a variaciones del precio del fuel, no pueden actualizarse de manera efectiva debido a la capacidad manual del equipo de validación.

**Causa raíz:** Volatilidad de conceptos (p. ej. fuel) que requieren actualizaciones frecuentes; proceso manual de mantenimiento del tarifario que no soporta actualizaciones con la cadencia necesaria.

**Cómo se ha llegado:**
- Identificación en el apartado "Debilidades reportadas en el mantenimiento de los tarifarios": dificultades en la actualización de tarifarios en USA por imputación de gastos de fuel que se actualizan semanalmente.
- Flujo general de mantenimiento: paso manual de solicitud de plantilla y sobrescritura en la Herramienta de Costes; limitación operativa para cambios frecuentes.

**Consecuencias:** Posible registro de costes no alineados con la realidad de mercado en la Herramienta de Costes, afectando la validación de facturas y la estimación de costes por CPF en futuros despliegues.

**Recomendación:** Se recomienda automatizar la actualización de extracostes variables (p. ej. fuel) en la Herramienta de Costes. Configurar integración automatizada con una o varias fuentes de precios de mercado para ingestión directa de valores. Parametrizar la cadencia de actualización según la volatilidad (p. ej. semanal donde proceda) y habilitar actualización programada en la herramienta. Implementar un flujo de validación y aprobación que incluya conciliación automática entre la fuente y el tarifario, registro de cambios y alertas por desviaciones significativas. Asignar responsabilidades operativas y SLAs para supervisión, control y gestión de excepciones.

**Notas del auditor:**
