# Informe de auditoría interna — Auditoría de Transporte e-Commerce: tarifarios y SCA

- Referencia: DEMO-TEC-2026
- Fecha: Junio 2026
- Distribución: Dirección de Transporte e-Commerce, Dirección Financiera, Comité de Auditoría

> Texto de trabajo del informe: lo que se lee aquí es lo que exporta `ppt`, apartado a
> apartado (cada `##` y cada `###` es una diapositiva). Edítalo libremente respetando los
> títulos y, en las conclusiones, la línea «A continuación, se muestran los detalles…»,
> las viñetas de datos y los párrafos `**Recomendación N.1.**`.
> Acciones: `redactar-contexto` (introducción y resumen), `redactar-conclusiones`
> (vuelca las aprobadas), `revisar`/`corregir` (vocabulario), `aplicar-cambios`
> (desde 03_instrucciones.md), `diff`, `deshacer`, `ppt` (exporta el informe entero),
> `archivar`.


## Introducción

El presente trabajo se enmarca en la auditoría de Transporte e‑Commerce (tarifarios y SCA) y evalúa la integridad de los tarifarios utilizados por los algoritmos de asignación de transportistas. El contexto incluye el desarrollo de la herramienta SCA, la Herramienta de Costes (HC) y la integración con Cost Pricing Flash (CPF), que estima costes a partir de los pedidos validados en HC.

El objetivo de la prueba fue asegurar la integridad de los tarifarios empleados por SCA en el proceso de asignación. La comprobación se centró en dos tareas: a) contrastar el tarifario negociado con los transportistas frente al valor cargado en SCA/CPF; y b) revisar la gestión del maestro de tarifas, incluyendo quién carga o modifica las tarifas y el proceso de actualización.

Pruebas realizadas:

- a) Contrastar el tarifario negociado con los transportistas frente al valor cargado en la herramienta SCA/CPF. Se emplearon como insumo los registros de la Herramienta de Costes y la tabla TRANSPORT_BUSINESS.FOUNDATION.COSTES_ECOM_DETALLE en Snowflake. Se analizaron las implicaciones de CPF, incluido el uso de históricos de 4 meses y la tabla en desarrollo TRANSPORT_BUSINESS.DATA.CPF_SIMULATION_RATES.

- b) Gestión del maestro de tarifas: revisión del flujo de mantenimiento en la HC, identificación de las funciones de los equipos de validación de facturas (BDO, Serviguide, equipo interno de China y supervisión de Central e‑Commerce) y el proceso manual de sobreescritura de tarifas a nivel de código postal, así como las alertas y revisiones semanales implementadas por Transport Business Analytics.

Durante la ejecución se documentaron las debilidades identificadas en CPF (problemas de imputación de embalaje, tratamiento de COD, consideración de linehaul, zonas remotas, variaciones por tier y diferencias de peso/volumen) y las limitaciones del mantenimiento manual de tarifarios reflejadas en las pruebas y en las sesiones con responsables.

## Resumen ejecutivo

Ámbito revisado: tarifarios usados por SCA y el proceso CPF de estimación de costes, incluyendo la Herramienta de Costes (HC) y las tablas de Snowflake referenciadas en la prueba 2.11 (a y b).

Se concluye la prueba CON INCIDENCIAS. Se ha observado que los acuerdos de tarifación alcanzados entre Operativa y proveedores no siempre se transmiten al equipo de validación. Incidencia: desactualización del maestro de tarifas. Riesgo: Alto. Consecuencia: tarifas registradas en HC y Snowflake pueden no reflejar lo pactado, afectando la asignación en SCA y el coste reportado.

Se ha observado que CPF hereda deficiencias en la valoración de casuísticas minoritarias, como Cash On Delivery y zonas remotas. Incidencia: estimaciones de coste sesgadas para esos pedidos. Riesgo: Medio. Consecuencia: asignaciones inadecuadas en SCA y posibles diferencias económicas en la operación.

Se ha observado que el mantenimiento del maestro de tarifas es manual y carece de una plantilla común, lo que impide automatizar la carga y actualización. Incidencia: procesos sujetos a error y carga operativa elevada. Riesgo: Medio. Consecuencia: limitaciones para actualizar tarifas de forma oportuna y afectar la integridad de datos usados por CPF/SCA.

Se ha observado que la actualización de extracostes variables (por ejemplo, fuel) no es viable con la capacidad manual actual. Incidencia: desajustes en tarifarios frente a la realidad de mercado. Riesgo: Bajo. Consecuencia: impacto potencial en la validación de facturas y en futuras estimaciones de CPF.

Referencia a recomendaciones abiertas: se remite a la recomendación TMSCIIF-10 (Auditoría de Controles SCIIF 2022), que sigue abierta, sobre implantar un sistema para la carga y gestión de tarifarios y garantizar la evidencia de los acuerdos con proveedores. Las conclusiones validadas incluyen también acciones orientadas a adaptar los procesos de datos y el entrenamiento de CPF para incorporar desglose de COD y estandarización de zonas remotas.

## Detalle de conclusiones

### 1. Acuerdos de tarifación no se transmiten al equipo de validación, provocando desactualización de tarifarios

- Prueba: 2.11 b) Gestión del maestro de tarifas (quién las carga/modifica); revisar proceso de carga y actualización de tarifas
- Nivel de riesgo: Alto
- Área: 
- Responsable: Operativa e‑Commerce
- Plazo: 
- Ref. recomendación: 

Se han identificado casos en los que los acuerdos alcanzados entre Operativa y los proveedores no se transparentan al equipo de validación, lo que implica desactualización del maestro de tarifas y errores en la valoración del coste de transporte.

Falta de trazabilidad y evidencia formalizada de los acuerdos entre Operativa y los equipos de validación (ausencia de un sistema/plantilla común para registrar modificaciones).

*A continuación, se muestran los detalles descriptivos de la situación anterior:*
- Revisión del flujo general de mantenimiento del maestro de tarifas descrito en la prueba (actualización manual por equipos de validación: BDO, Serviguide e Inditex - China; pasos 1 a 6).
- Identificación en las conclusiones del papel de trabajo de la afirmación: "en determinadas ocasiones, los acuerdos alcanzados entre Operativa y los proveedores no se transparentan al equipo de validación".
- Referencias técnicas del proceso: datos grabados en Snowflake (TRANSPORT_BUSINESS.FOUNDATION.COSTES_ECOM_DETALLE) y uso posterior por CPF/SCA para estimación de costes.
- Observación de la recomendación referenciada (Auditoría SCIIF 2022 TMSCIIF-10) que propone implantar un sistema para la carga y gestión de tarifarios y la evidencia de acuerdos.

Registro de tarifas desactualizadas en la Herramienta de Costes y en Snowflake, estimaciones de coste erróneas y potenciales imputaciones incorrectas en SCA, con impacto en la asignación de transportistas y en el coste reportado.

**Recomendación 1.1.** Implantar un sistema para la carga y gestión de los tarifarios de todas las operativas de transporte, así como la evidencia de los acuerdos alcanzados con los proveedores para garantizar la trazabilidad de estos con las tarifas cargadas.

### 2. CPF hereda deficiencias en la valoración de casuísticas minoritarias (COD, zonas remotas) que impactan la asignación en SCA

- Prueba: 2.11 a) Contrastar el tarifario negociado con los transportistas, frente al valor cargado en la herramienta SCA/CPF
- Nivel de riesgo: Medio
- Área: 
- Responsable: 
- Plazo: 
- Ref. recomendación: 

El algoritmo CPF no considera correctamente determinadas casuísticas (por ejemplo, Cash On Delivery y entregas en zonas remotas), lo que provoca que SCA reciba estimaciones de coste sesgadas que afectan la asignación de transportistas.

Limitaciones del método de inferencia de CPF y de los datos de entrada (CPF entrena con facturas en bruto y no desglosa conceptos como COD; discrepancias en definición de zonas remotas entre couriers).

*A continuación, se muestran los detalles descriptivos de la situación anterior:*
- Descripción del funcionamiento de CPF: toma histórico de últimos 4 meses y aplica método de inferencia; no requiere el tarifario asociado al transportista, sino costes reales de pedidos.
- Debilidades identificadas en el apartado "Debilidades del algoritmo CPF":
- COD no desglosado en factura y genera extracargos no imputados correctamente.
- Definición inconsistente de "zona remota" entre couriers, y asignación por Customer state que unifica conceptos.
- CPF entrena respecto de facturas en bruto, penalizando couriers con COD incluido.
- Referencia a tablas y flujos: datos de pedidos almacenados en TRANSPORT_BUSINESS.FOUNDATION.COSTES_ECOM_DETALLE y uso por CPF/CPF_SIMULATION_RATES.

Estimaciones de coste incompletas o sesgadas para pedidos con COD o en zonas remotas, generando una asignación inadecuada de transportistas en SCA y posibles diferencias económicas en la operación.

**Recomendación 2.1.** Se recomienda actualizar el proceso de datos y el entrenamiento de CPF para incorporar la desagregación de COD y la estandarización de zonas remotas. Pasos mínimos: 1) adaptar ETL para registrar en TRANSPORT_BUSINESS.FOUNDATION.COSTES_ECOM_DETALLE campos desagregados: indicador_COD, importe_COD y código_zona_remota estandarizado; 2) acordar y documentar una definición única de "zona remota" y un mapa de correspondencia entre couriers; 3) retrenar CPF incorporando las nuevas variables y variables indicadoras por courier para COD y remotas; 4) implementar en SCA una regla de validación que contraste la estimación CPF con el tarifario negociado y que active una asignación alternativa o revisión cuando la estimación esté sesgada por ausencia de desglose COD o por inconsistencias de zona; 5) establecer monitorización periódica de desviaciones por COD y zonas remotas y reportes de rendimiento del modelo para ajuste continuo.

### 3. Mantenimiento del tarifario manual y sin plantilla común que impide automatización

- Prueba: 2.11 b) Gestión del maestro de tarifas (quién las carga/modifica); revisar proceso de carga y actualización de tarifas
- Nivel de riesgo: Medio
- Área: 
- Responsable: 
- Plazo: 
- Ref. recomendación: 

El mantenimiento del maestro de tarifas se realiza de forma manual y no existe una plantilla común para la grabación de modificaciones en la Herramienta de Costes, lo que impide automatizar el proceso.

Ausencia de formatos estandarizados y de un sistema centralizado para la carga y gestión de tarifarios.

*A continuación, se muestran los detalles descriptivos de la situación anterior:*
- Revisión del flujo descrito: Operaciones renegocia y facilita plantillas (formato diferente por courier); los equipos de validación sobreescriben manualmente los datos en la Herramienta de Costes (pasos 1 y 2 del flujo general).
- Observación en CONCLUSIONES: "El mantenimiento del tarifario no es automatizable, debido a que no existe una plantilla común para la grabación de modificaciones".
- Referencias técnicas: entradas manuales por Código Postal y registro de costes en Snowflake (TRANSPORT_BUSINESS.FOUNDATION.COSTES_ECOM_DETALLE) para su uso por CPF.

Riesgo de inconsistencias y errores en la carga de tarifarios, mayor carga operativa manual y limitaciones para actualizar tarifas de forma oportuna, afectando la integridad de los datos utilizados por CPF/SCA.

**Recomendación 3.1.** Implantar un sistema para la carga y gestión de los tarifarios de todas las operativas de transporte, así como la evidencia de los acuerdos alcanzados con los proveedores para garantizar la trazabilidad de estos con las tarifas cargadas.

### 4. Actualización de extracostes (p. ej. fuel) inviable por capacidad manual, generando desajustes

- Prueba: 2.11 b) Gestión del maestro de tarifas (quién las carga/modifica); revisar proceso de carga y actualización de tarifas
- Nivel de riesgo: Bajo
- Área: 
- Responsable: 
- Plazo: 
- Ref. recomendación: 

Determinados extracostes, como los vinculados a variaciones del precio del fuel, no pueden actualizarse de manera efectiva debido a la capacidad manual del equipo de validación.

Volatilidad de conceptos (p. ej. fuel) que requieren actualizaciones frecuentes; proceso manual de mantenimiento del tarifario que no soporta actualizaciones con la cadencia necesaria.

*A continuación, se muestran los detalles descriptivos de la situación anterior:*
- Identificación en el apartado "Debilidades reportadas en el mantenimiento de los tarifarios": dificultades en la actualización de tarifarios en USA por imputación de gastos de fuel que se actualizan semanalmente.
- Flujo general de mantenimiento: paso manual de solicitud de plantilla y sobrescritura en la Herramienta de Costes; limitación operativa para cambios frecuentes.

Posible registro de costes no alineados con la realidad de mercado en la Herramienta de Costes, afectando la validación de facturas y la estimación de costes por CPF en futuros despliegues.

**Recomendación 4.1.** Se recomienda automatizar la actualización de extracostes variables (p. ej. fuel) en la Herramienta de Costes. Configurar integración automatizada con una o varias fuentes de precios de mercado para ingestión directa de valores. Parametrizar la cadencia de actualización según la volatilidad (p. ej. semanal donde proceda) y habilitar actualización programada en la herramienta. Implementar un flujo de validación y aprobación que incluya conciliación automática entre la fuente y el tarifario, registro de cambios y alertas por desviaciones significativas. Asignar responsabilidades operativas y SLAs para supervisión, control y gestión de excepciones.

## Sugerencias de mejora

_(ninguna)_
