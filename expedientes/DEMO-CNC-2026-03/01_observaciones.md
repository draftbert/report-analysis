# Observaciones y recomendaciones — DEMO-CNC-2026-03 · Auditoría de Compras No Comerciales

> Cómo trabajar este fichero:
> - Lee cada observación, corrige lo que haga falta directamente en el texto.
> - Cambia `Estado: propuesta` por `aprobada` (irá al informe) o `descartada` (se ignora).
> - Si quieres que el modelo la rehaga, escribe qué cambiar en «Notas del auditor»
>   y ejecuta `regenerar-obs OBS-XX`. Puedes añadir observaciones nuevas a mano
>   copiando la estructura de un bloque.
> - `revisar-obs` comprueba vocabulario prohibido y campos vacíos; `corregir-obs`
>   pide al modelo que corrija solo lo señalado.
> - Cuando tengas las que quieras aprobadas, ejecuta `redactar`.


## OBS-01 · Ausencia de ofertas comparativas en pedidos >30.000 €

- Estado: propuesta
- Nivel de riesgo: Medio
- Responsable: Dirección de Compras
- Fuente: papel_trabajo_compras.md — Tarea 3.2 Prueba realizada / Resultados; Anexo E3 (Expedientes de los pedidos de la muestra).

**Condición:** En 3 de los 12 pedidos con importe superior a 30.000 € no consta la documentación de las tres ofertas comparativas en el expediente (muestra de 45 pedidos, ene-mar 2026).

**Criterio:** Existencia de tres ofertas comparativas para pedidos superiores a 30.000 € (criterio verificado en la prueba realizada).

**Causa raíz:** El sistema de compras no exige adjuntar las tres ofertas para tramitar o aprobar el pedido, según reconocimiento del área.

**Efecto:** Compras sin competencia documentada, riesgo de selección inadecuada de proveedor y potencial incremento de coste.

**Recomendación:** Implementar en el sistema un control bloqueante que impida la tramitación y aprobación de pedidos >30.000 € si no están adjuntas las tres ofertas comparativas. Establecer un procedimiento formal de excepciones con aprobación documentada y trazabilidad. Revisar y completar los expedientes pendientes de la muestra.

**Notas del auditor:** 

## OBS-02 · Aprobaciones registradas después de la emisión del pedido

- Estado: aprobada
- Nivel de riesgo: Medio
- Responsable: Dirección de Compras
- Fuente: papel_trabajo_compras.md — Tarea 3.2 Resultados; Comentarios del área; Anexo E1 (Extracto del módulo de compras); Anexo E3 (Expedientes).

**Condición:** En 6 de 45 pedidos (13%) la aprobación se registró en el sistema con posterioridad a la fecha de emisión del pedido al proveedor.

**Criterio:** Aprobación previa conforme a la matriz de delegación de facultades vigente (criterio verificado en la prueba realizada).

**Causa raíz:** Aprobaciones impartidas fuera del sistema en situaciones de urgencia y registradas posteriormente en el sistema.

**Efecto:** Compromisos económicos sin autorización formal previa; riesgo de incumplimiento de la matriz de delegación y de controles de autorización.

**Recomendación:** Definir procedimiento para registrar aprobaciones de urgencia en el sistema de compras. Permitir adjuntar correos electrónicos como evidencia. Exigir registro posterior inmediato con justificación documentada y plazo máximo para el registro.

**Notas del auditor:** 

## OBS-03 · Aprobador coincide con solicitante por delegación temporal no revertida

- Estado: aprobada
- Nivel de riesgo: Medio
- Responsable: Dirección de Compras
- Fuente: papel_trabajo_compras.md — Tarea 3.2 Resultados; Comentarios del área; Anexo E2 (Matriz de delegación de facultades); Anexo E3 (Expedientes).

**Condición:** En 2 pedidos el aprobador coincidía con el solicitante debido a una delegación temporal de permisos durante vacaciones que no fue revertida.

**Criterio:** Segregación entre solicitante y aprobador exigida en las pruebas de revisión de aprobaciones y en la matriz de delegación.

**Causa raíz:** Reversión de permisos tras vacaciones gestionada manualmente y no revertida en los casos identificados.

**Efecto:** Reducción del control de segregación de funciones, aumentando el riesgo de autorizaciones inapropiadas.

**Recomendación:** Implementar control para revertir automáticamente delegaciones temporales o checklist de reapertura de permisos. Realizar revisiones periódicas de permisos activos.

**Notas del auditor:**
