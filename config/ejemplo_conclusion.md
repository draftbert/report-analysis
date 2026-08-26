# Ejemplo de referencia de una conclusión (registro y estructura objetivo)

> Este fichero se inyecta en el prompt de `extraer` como ejemplo del resultado esperado
> para UNA prueba del papel de trabajo. El equipo puede sustituirlo por otro ejemplo
> aprobado. Las cifras y nombres de este ejemplo pertenecen a OTRA auditoría: el modelo
> tiene prohibido reutilizarlos; solo copia el registro, la estructura y el nivel de detalle.

## Limitaciones en el mantenimiento de los tarifarios de última milla

**Incidencia detectada:** Las actualizaciones tarifarias de los couriers se incorporan manualmente a la Herramienta de Costes mediante ficheros Excel remitidos por el equipo de Transporte. La comunicación y traslado de estos cambios a los equipos de validación de facturas no se realiza siempre de forma sincronizada, pudiendo producirse desfases en la actualización de las tarifas.

**Causa raíz:** La comunicación y trazabilidad de los cambios tarifarios se articula mediante un proceso principalmente manual, condicionado además por la diversidad de formatos utilizados por los couriers y por las funcionalidades actuales de la Herramienta de Costes, que requieren parametrizar manualmente actualizaciones masivas, porcentuales o basadas en reglas.

**Cómo se ha llegado:**
- El volumen de tarifas a parametrizar puede superar las 5.000 combinaciones.
- Determinados componentes tarifarios requieren actualizaciones recurrentes, como los recargos de combustible (fuel surcharge) y los rappels trimestrales, semestrales o anuales.
- Durante los primeros seis meses del ejercicio se han tramitado reclamaciones relacionadas con tarifas por un importe aproximado de 1,4 M€, sin que pueda atribuirse de forma directa la totalidad de dicho importe a incidencias en el mantenimiento de los tarifarios.

**Consecuencias:** La manualidad del proceso y las dificultades de sincronización incrementan el riesgo de que las tarifas cargadas estén desactualizadas o no coincidan con las condiciones acordadas. Este riesgo se ha materializado en discrepancias entre las tarifas aplicadas en la Herramienta de Costes y las condiciones acordadas con los proveedores, si bien no ha sido posible cuantificar su impacto económico.

**Recomendación:** Implantar un sistema para la carga y gestión de los tarifarios de todas las operativas de transporte, así como la evidencia de los acuerdos alcanzados con los proveedores para garantizar la trazabilidad de estos con las tarifas cargadas.

- Ref. recomendación: TMSCIIF-10
- Nivel de riesgo: Medio
