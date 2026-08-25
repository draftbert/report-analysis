# Calibración del criterio de estilo — 2026-08-25 15:26

Corpus: `ejemplos/corpus_calibracion` — 3 aprobado(s), 1 borrador(es), 1 pareja(s) borrador/aprobado.

> Este informe NO modifica `config/estilo.yaml`. Revisa cada propuesta y edita el YAML a mano.

## (a) Falsos positivos: reglas que disparan en informes aprobados

| Término | Regla | Veces | Ficheros | Acción sugerida |
|---|---|---:|---:|---|
| «todos los casos» | palabra_prohibida — Acotar la afirmación al alcance de la prueba. | 1 | 1 | revisar (poca evidencia) |
| «problema» | palabra_prohibida — Terminología estándar del informe. | 1 | 1 | revisar (poca evidencia) |
| «siempre» | palabra_prohibida — Absolutos no soportables con la evidencia de una muestra. | 1 | 1 | revisar (poca evidencia) |

**«todos los casos»** — contexto en aprobados:
- [informe_SCIIF-2025-11_aprobado.md] …izadas no consta evidencia de revisión por un segundo responsable. En todos los casos la conciliación estaba correctamente elaborada.

**«problema»** — contexto en aprobados:
- [informe_SCIIF-2025-11_aprobado.md] **Causa raíz:** El problema se origina en la ausencia de un campo obligatorio de revisor en la he…

**«siempre»** — contexto en aprobados:
- [informe_SCIIF-2025-11_aprobado.md] …omendación:** Incorporar la firma del revisor como campo obligatorio; siempre que se detecte una diferencia superior al umbral, escalarla al respon…

Frases por encima del límite de 45 palabras en aprobados: 0 de 51 (0.0%).

## (b) Propuestas de nuevas reglas y ajustes (modelo)

### Altas propuestas (2)

- **«Formato cuantificación de hallazgos»** [reglas] — confianza alta
  - Sugerencia: Cuando se cuantifiquen hallazgos en una muestra, incluir siempre el formato 'X de Y (Z%)' (ej.: 'En 6 de los 45 pedidos analizados (13%)...').
  - Motivo: Los informes aprobados muestran de forma consistente la cuantificación absoluta y relativa en el mismo enunciado; estandarizarlo facilita comprensión y automatización del resumen ejecutivo/PPT.
  - Evidencia: En 6 de los 45 pedidos analizados (13%), la aprobación se registró en el sistema con posterioridad a la fecha de emisión del pedido al proveedor. [obs_aprobaciones.md]
  - Evidencia: En 4 de las 20 conciliaciones analizadas no consta evidencia de revisión por un segundo responsable. [informe_SCIIF-2025-11_aprobado.md]
- **«Estructura obligatoria de observación»** [reglas] — confianza alta
  - Sugerencia: Cada observación aprobada debe seguir la estructura y campos visibles en los aprobados: título breve, 'Nivel de riesgo' y 'Responsable' (si procede), y dentro del cuerpo usar los subtítulos Condición / Criterio / Causa raíz / Efecto / Recomendación.
  - Motivo: Los informes aprobados usan de forma consistente esta estructura; formalizarla mejora la claridad y permite generar presentaciones y resúmenes de forma automática.
  - Evidencia: **Condición:** En 6 de los 45 pedidos analizados (13%), la aprobación se registró... [informe_CNC-2026-03.md]
  - Evidencia: **Causa raíz:** El procedimiento no contempla un circuito formal para compras urgentes... [obs_aprobaciones.md]
  - Evidencia: - Nivel de riesgo: Medio  - Responsable: Dirección de Compras  (encabezado usado en observaciones). [informe_CNC-2026-03.md]

### Bajas propuestas (0)

(ninguna)


### Modificaciones propuestas (4)

- **«todos los casos»** [palabras_prohibidas] — confianza alta
  - Sugerencia: Permitir 'en todos los casos' cuando se usa para calificar la totalidad de la muestra analizada y la frase aclara el alcance (ej. 'En todos los casos la conciliación estaba correctamente elaborada'). En otros usos, mantener la recomendación de acotar la afirmación al alcance de la prueba (p. ej. 'la totalidad de la muestra analizada').
  - Motivo: En los informes aprobados se usa 'En todos los casos' para referirse de forma legítima y acotada a la totalidad de la muestra analizada; prohibirlo sin matiz impide esa redacción clara.
  - Evidencia: En todos los casos la conciliación estaba correctamente elaborada. [informe_SCIIF-2025-11_aprobado.md]
- **«problema»** [palabras_prohibidas] — confianza alta
  - Sugerencia: Mantener la preferencia por 'observación' / 'debilidad' en las secciones de hallazgos, pero permitir 'problema' cuando aparece en explicaciones de causa raíz o en lenguaje corriente dentro de la sección de causa (p. ej. 'Causa raíz: El problema se origina...').
  - Motivo: En informes aprobados 'problema' se utiliza de forma aceptada dentro de la sección de causa raíz; la regla actual que lo prohíbe sin excepción es demasiado rígida.
  - Evidencia: Causa raíz: El problema se origina en la ausencia de un campo obligatorio de revisor en la herramienta de conciliación. [informe_SCIIF-2025-11_aprobado.md]
- **«siempre»** [palabras_prohibidas] — confianza alta
  - Sugerencia: Prohibir 'siempre' cuando se usa como absoluto sin soporte; permitir construcciones condicionales o relativas como 'siempre que...' o aclaraciones que limiten el alcance ('siempre que se detecte...', 'en los casos analizados...').
  - Motivo: Los aprobados usan 'siempre que...' en recetas/recomendaciones; distinguir usos absolutos (a prohibir) de construcciones condicionales evita falsos positivos.
  - Evidencia: Recomendación: Incorporar la firma del revisor como campo obligatorio; siempre que se detecte una diferencia superior al umbral, escalarla al responsable de Tesorería. [informe_SCIIF-2025-11_aprobado.md]
  - Evidencia: Borrador: '...el responsable de compras siempre aprueba los pedidos...' (ejemplo de uso absoluto que sí se corrigió). [obs_aprobaciones_borrador.txt]
- **«error del responsable»** [palabras_prohibidas] — confianza alta
  - Sugerencia: Ampliar la redacción a: prohibir atribuciones de fallos a personas concretas ('error del responsable', 'culpa de X'); exigir formular la observación en términos de condición/debilidad del proceso o control (p. ej. 'la reversión de delegaciones temporales no fue revertida' -> 'gestión de delegaciones manual sin fecha de caducidad').
  - Motivo: Las aprobaciones sustituyeron expresiones que atribuían responsabilidad personal por descripciones objetivas del hecho y de la causa raíz; la regla debe dirigirse a evitar atribuciones personales más que a una frase concreta.
  - Evidencia: Borrador: '...algo que consideramos un error del responsable de la gestión de accesos...' [obs_aprobaciones_borrador.txt]
  - Evidencia: Aprobado: 'En 2 pedidos de la muestra, el aprobador coincidía con el solicitante como consecuencia de una delegación temporal de permisos...' [obs_aprobaciones.md]

### Patrones de estilo observados en los aprobados

Informes aprobados mantienen voz impersonal y estructura homogénea por observación (título breve + Nivel de riesgo / Responsable + subtítulos Condición / Criterio / Causa raíz / Efecto / Recomendación). Las cuantificaciones combinan siempre el absoluto y el relativo ('X de Y (Z%)'). Se evita atribuir fallos a personas, prefiriendo describir condiciones y causas del proceso. Se emplean condicionales precisas ('siempre que...') y se evitan muletillas valorativas (p. ej. 'obviamente').

### Cómo trasladarlo al YAML

```yaml
palabras_prohibidas:
  - termino: "<término>"
    sugerencia: "<alternativa>"
    motivo: "<motivo>"
```
Bajas: eliminar la entrada. Modificaciones: ajustar `sugerencia`/`motivo`.
