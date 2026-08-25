# Resumen Ejecutivo — Auditoría de Compras No Comerciales

- Referencia: CNC-2026-03
- Fecha: Mayo 2026
- Distribución: Dirección de Compras, Dirección Financiera, Comité de Auditoría

> Este es el texto de trabajo del informe. Edítalo libremente respetando los
> títulos `##` de sección y la estructura de cada observación (`###` + campos en
> negrita): es lo que permite generar el PPT y aplicar cambios automáticamente.
> Acciones: `revisar` (vocabulario/estilo), `corregir` (reescritura dirigida de
> lo señalado), `aplicar-cambios` (desde 03_instrucciones.md), `diff`,
> `deshacer`, `ppt`.


## Objetivo

Evaluar el diseño y la eficacia operativa de los controles del proceso de compras no comerciales, con especial atención a la aprobación de pedidos conforme a la matriz de delegación de facultades, la segregación de funciones y la obtención de ofertas comparativas.

## Alcance

Pedidos de compra no comercial emitidos entre enero y marzo de 2026 por importe superior a 10.000 €. Se ha analizado una muestra de 45 pedidos, incluyendo la totalidad de los 12 pedidos superiores a 30.000 €. Quedan fuera del alcance las compras comerciales y los contratos marco plurianuales.

## Contexto y principales magnitudes

- 8,4 M€ — Volumen del periodo
- 612 — Pedidos emitidos
- 45 — Pedidos en muestra
- 41% — Importe cubierto

El volumen de compras no comerciales del periodo asciende a 8,4 M€, distribuido en 612 pedidos. El proceso se soporta en el módulo de compras del ERP, con aprobación electrónica conforme a la matriz de delegación de facultades v4.2. La muestra analizada representa el 41% del importe total del periodo.

## Principales observaciones

### 1. Aprobaciones registradas con posterioridad a la emisión del pedido

- Nivel de riesgo: Medio
- Responsable: Dirección de Compras

**Condición:** En 6 de los 45 pedidos analizados (13%), la aprobación se registró en el sistema con posterioridad a la fecha de emisión del pedido al proveedor. El área auditada indica que se trata de pedidos urgentes de mantenimiento con autorización previa por correo electrónico, fuera del sistema.

**Criterio:** Matriz de delegación de facultades v4.2 y Política de Compras, que exigen aprobación previa en el sistema antes de la emisión del pedido.

**Causa raíz:** El procedimiento no contempla un circuito formal para compras urgentes, lo que provoca aprobaciones fuera del sistema y su regularización posterior.

**Efecto:** Riesgo de compromiso de gasto sin autorización efectiva y pérdida de trazabilidad de la aprobación.

**Recomendación:** Definir un circuito de aprobación urgente dentro del sistema (aprobación simplificada con ratificación posterior) y bloquear la emisión de pedidos sin aprobación registrada.

### 2. Falta de segregación entre solicitante y aprobador

- Nivel de riesgo: Alto
- Responsable: Dirección de Sistemas / Dirección de Compras

**Condición:** En 2 pedidos de la muestra, el aprobador coincidía con el solicitante como consecuencia de una delegación temporal de permisos durante un periodo vacacional que no fue revertida a su finalización.

**Criterio:** Política de segregación de funciones y matriz de delegación de facultades v4.2.

**Causa raíz:** La reversión de delegaciones temporales de permisos se gestiona de forma manual, sin fecha de caducidad automática ni revisión periódica de delegaciones activas.

**Efecto:** Riesgo de aprobación de gasto sin control independiente.

**Recomendación:** Configurar caducidad automática de las delegaciones temporales en el sistema e implantar una revisión trimestral de delegaciones activas.

### 3. Ausencia de ofertas comparativas en pedidos de importe elevado

- Nivel de riesgo: Medio
- Responsable: Dirección de Compras

**Condición:** En 3 de los 12 pedidos superiores a 30.000 € no consta en el expediente la documentación acreditativa de las tres ofertas comparativas requeridas.

**Criterio:** Política de Compras, apartado de concurrencia de ofertas para importes superiores a 30.000 €.

**Causa raíz:** El sistema no exige adjuntar la documentación de ofertas como requisito para tramitar el pedido; el control depende de la diligencia del gestor.

**Efecto:** Riesgo de contratación en condiciones no óptimas y de incumplimiento de la política interna de concurrencia.

**Recomendación:** Incorporar en el sistema un control bloqueante que exija adjuntar las ofertas comparativas (o la justificación de excepción aprobada) antes de tramitar pedidos superiores a 30.000 €.

## Evaluación global

- Gobierno: Razonable — Impacto Bajo
- Gestión de riesgos: Mejorable — Impacto Medio
- Entorno de control: Mejorable — Impacto Medio

El proceso de compras no comerciales presenta un diseño de control adecuado en su definición, si bien su eficacia operativa se ve limitada por la ausencia de controles automáticos en tres puntos: aprobación previa bloqueante, caducidad de delegaciones y exigencia documental de ofertas. Las causas raíz identificadas son de naturaleza común (dependencia de controles manuales sobre un proceso soportado en sistema), por lo que las recomendaciones se orientan a su automatización, con un esfuerzo de implantación estimado como moderado.

## Próximos pasos

El área auditada ha manifestado su conformidad con las observaciones y recomendaciones emitidas. Se ha acordado un plan de acción con los responsables designados, con horizonte de implantación entre septiembre y diciembre de 2026. Auditoría Interna realizará el seguimiento de la implantación de las recomendaciones conforme al procedimiento de follow-up, con una primera verificación en enero de 2027.
