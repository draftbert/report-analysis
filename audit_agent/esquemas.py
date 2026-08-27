"""
Esquemas Pydantic de las salidas estructuradas del LLM.

Son el "contrato" que viaja al modelo como `output_format_schema` (KAIA) y el
formato pivote de la herramienta: lo que se extrae de los papeles de trabajo,
lo que se revisa y lo que alimenta el informe y el PPT.

Estructura de cada conclusión (detalle de conclusiones del informe):
  incidencia detectada -> causa raíz -> cómo se ha llegado (datos, tablas)
  -> consecuencias -> recomendación (validada o aportada por el auditor).
Las sugerencias de mejora comparten estructura, con «propuesta de mejora» en
lugar de recomendación y sin plan de acción obligatorio.

Precaución (heredada de audit-engine): las clases que viajan al modelo se
compilan con `to_strict_json_schema` -> todos los campos son obligatorios y
`additionalProperties: false` en cada nivel. Un campo que no esté aquí,
literalmente no se le pide al modelo.

Los campos "opcionales" llevan `default`: el schema que viaja sigue listándolos
como required (el compilador estricto ignora el default), pero la validación
de la respuesta no falla si el backend los omite. Visto en vivo (2026-08-25):
KAIA devolvió `PlanCambios` sin `insertar_tras` en dos ítems pese al strict.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

NIVELES_RIESGO = ("Crítico", "Alto", "Medio", "Bajo")
ESCALA_EVALUACION_GLOBAL = ("Deficiente", "Insuficiente", "Mejorable", "Razonable", "Adecuado")
TIPOS_CONCLUSION = ("conclusion", "sugerencia")


class Conclusion(BaseModel):
    """Una incidencia del papel de trabajo en la estructura del detalle de
    conclusiones. Cadena vacía = no deducible de la fuente."""

    titulo: str = Field(description="Título breve de la incidencia (una línea).")
    tipo: str = Field(default="conclusion", description="'conclusion' si la incidencia requiere recomendación y plan de acción; 'sugerencia' si es una mejora sin plan de acción obligatorio.")
    prueba: str = Field(default="", description="Referencia de la prueba del papel de trabajo de la que procede (número y título, p. ej. '2.11 a) Contrastar el tarifario negociado…').")
    incidencia: str = Field(description="Qué incidencia se ha detectado: uno o dos párrafos en prosa que describen la situación (qué ocurre y cómo se hace hoy), con los datos del papel de trabajo. Sin viñetas.")
    causa_raiz: str = Field(description="Por qué ha pasado: párrafo en prosa con la causa raíz inferida del papel de trabajo (proceso manual, falta de plantilla, limitaciones de la herramienta…). Vacío si no se puede inferir.")
    como_se_ha_llegado: str = Field(description="Detalles descriptivos de la situación anterior: lista Markdown de viñetas (`- `) con los datos concretos que la soportan: volúmenes, importes, muestras, componentes afectados, tablas del papel de trabajo. Solo datos presentes en la fuente; cada viñeta una frase.")
    consecuencias: str = Field(description="Párrafo de cierre: qué riesgo genera la incidencia, si se ha materializado (con evidencia del papel de trabajo) y si ha podido cuantificarse su impacto.")
    recomendacion: str = Field(default="", description="Recomendación (o propuesta de mejora si tipo=sugerencia). Si hay varias, cada una en un párrafo separado por línea en blanco (se numerarán N.1, N.2…). Solo si el papel de trabajo la contiene o referencia; si no, vacía: la aportará el auditor o se propondrá después.")
    referencia_recomendacion: str = Field(default="", description="Código de la recomendación abierta de otra auditoría a la que se remite, si el papel de trabajo lo indica (p. ej. 'TMSCIIF-10'). Vacío si no hay.")
    nivel_riesgo: str = Field(default="", description="Exactamente uno de: Crítico, Alto, Medio, Bajo. Vacío si no procede.")
    area: str = Field(default="", description="Área o unidad organizativa responsable del plan de acción, si el papel de trabajo lo indica.")
    responsable: str = Field(default="", description="Persona o rol responsable del plan de acción, si el papel de trabajo lo indica.")
    plazo: str = Field(default="", description="Plazo del plan de acción (fecha, trimestre o 'Fuera de plazo'), si el papel de trabajo lo indica.")
    fuente: str = Field(default="", description="Documento y apartado del papel de trabajo que soporta la conclusión.")


class ConclusionExtraida(Conclusion):
    """Conclusión tal como sale del extractor: añade la procedencia del nivel
    de riesgo y de la recomendación."""

    riesgo_soportado_por_evidencia: bool = Field(
        default=False,  # si el backend omite el campo, se trata como propuesta (conservador)
        description="true SOLO si el papel de trabajo menciona explícitamente la severidad, criticidad o "
                    "nivel de riesgo de esta incidencia. false si el nivel es una estimación propia.")
    recomendacion_del_pt: bool = Field(
        default=False,
        description="true SOLO si `recomendacion` está copiada o referenciada literalmente del papel de trabajo "
                    "(p. ej. una recomendación abierta de otra auditoría). false si está vacía o es propia.")


class ExtraccionConclusiones(BaseModel):
    conclusiones: list[ConclusionExtraida]
    pruebas_sin_incidencia: list[str] = Field(default_factory=list, description="Referencias de las pruebas del papel de trabajo concluidas sin incidencias (no generan conclusión).")
    notas: str = Field(default="", description="Dudas, datos ambiguos o elementos que no se han podido clasificar. Vacío si no hay.")


class RecomendacionPropuesta(BaseModel):
    """Salida de `recomendar` cuando el auditor no aporta recomendación."""

    recomendacion: str = Field(description="Recomendación concreta y accionable para la incidencia.")
    sugerencia_mejora_titulo: str = Field(default="", description="Si además procede una sugerencia de mejora complementaria (sin plan de acción), su título. Vacío si no procede.")
    sugerencia_mejora_texto: str = Field(default="", description="Texto de la sugerencia de mejora complementaria. Vacío si no procede.")


class RecomendacionFormateada(BaseModel):
    """Salida de `recomendar` cuando el auditor SÍ aporta recomendación: solo formato."""

    recomendacion: str = Field(description="La misma recomendación del auditor, con formato de informe (impersonal, frases claras). Mismos hechos, mismas acciones, mismas cifras: nada añadido ni quitado.")


class ContextoInforme(BaseModel):
    """Introducción y resumen ejecutivo del informe."""

    introduccion: str = Field(description="Introducción del informe en Markdown con los bloques **Contexto:**, **Objetivo de la auditoría:** (con la lista de aspectos revisados), **Riesgos a cubrir:**, **Alcance de la auditoría:** y, si constan cifras, **Principales magnitudes:**; empieza y termina con las frases fijas indicadas.")
    resumen_ejecutivo: str = Field(description="Resumen ejecutivo para Dirección en Markdown: párrafo de contexto, valoración general del control, una viñeta por conclusión (debilidad + efecto) y párrafo final de valoración. Solo hechos presentes en la fuente.")
    evaluacion_global: str = Field(default="", description="Evaluación global del proceso: exactamente uno de Deficiente, Insuficiente, Mejorable, Razonable, Adecuado; vacío si no se puede sostener con la evidencia.")


class TextoLibre(BaseModel):
    """Envoltorio para pedir texto libre por el mismo canal estructurado
    (único formato de respuesta probado contra KAIA)."""

    texto: str


class ParrafoCorregido(BaseModel):
    id: int = Field(description="Identificador del párrafo, tal cual se recibió.")
    texto: str = Field(description="Párrafo reescrito completo, en el mismo formato Markdown que el original.")


class Correcciones(BaseModel):
    parrafos: list[ParrafoCorregido]


class Cambio(BaseModel):
    seccion: str = Field(description="Cabecera literal del informe (`## …` o `### N. …`) bajo la que está el fragmento a cambiar.")
    motivo: str = Field(description="Qué instrucción o comentario origina el cambio, en una frase.")
    texto_original: str = Field(default="", description="Fragmento EXACTO y contiguo del informe actual que se sustituye (copiado literal, sin recortar ni corregir). Vacío solo si es una inserción.")
    texto_nuevo: str = Field(default="", description="Texto que sustituye al original (o que se inserta). Vacío si es una eliminación.")
    insertar_tras: str = Field(default="", description="Solo para inserciones: fragmento EXACTO del informe tras el cual se inserta el texto nuevo. Vacío en sustituciones.")


class PlanCambios(BaseModel):
    cambios: list[Cambio]
    pendientes: list[str] = Field(default_factory=list, description="Instrucciones que no se han podido aplicar (falta información, ambigüedad, contradicen la evidencia) y por qué. Vacío si no hay.")


class PropuestaRegla(BaseModel):
    """Propuesta de cambio en config/estilo.yaml derivada de informes aprobados."""

    tipo: str = Field(description="Exactamente uno de: alta (regla nueva), baja (eliminar regla), modificacion (ajustar sugerencia/motivo o añadir excepción).")
    seccion: str = Field(description="Sección del YAML afectada: palabras_prohibidas | primera_persona | reglas.")
    termino: str = Field(description="Término o expresión objeto de la regla (literal).")
    sugerencia: str = Field(default="", description="Alternativa de redacción propuesta (para altas/modificaciones). Vacío en bajas.")
    motivo: str = Field(description="Por qué se propone, en una o dos frases.")
    evidencia: list[str] = Field(default_factory=list, description="Fragmentos LITERALES del corpus que soportan la propuesta (con el fichero entre corchetes). Mínimo uno.")
    confianza: str = Field(default="media", description="alta | media | baja, según cuánta evidencia hay.")


class PropuestasEstilo(BaseModel):
    propuestas: list[PropuestaRegla]
    patrones_observados: str = Field(default="", description="Rasgos de estilo consistentes en los informes aprobados que no se traducen en una regla concreta (estructura de frases, terminología, tono). Vacío si no hay.")


class CambioTextoDetectado(BaseModel):
    """Petición de una reunión que afecta al TEXTO del informe."""

    seccion: str = Field(description="Apartado del informe afectado: Introducción, Resumen ejecutivo, Conclusión N (título), Sugerencia N, Anexo…")
    que_cambiar: str = Field(description="Qué hay que cambiar, explicado al auditor en una o dos frases.")
    instruccion: str = Field(description="Instrucción AUTOCONTENIDA en imperativo para aplicarla sobre 02_informe.md sin leer la transcripción: nombra el apartado y, si el interlocutor dio la redacción, cítala literal. Ej.: «En la conclusión 1, dividir la Recomendación 1.1 en dos: 1.1 … y 1.2 …».")
    solicitado_por: str = Field(default="", description="Quién lo pidió (nombre o rol), si consta.")
    cita: str = Field(default="", description="Fragmento literal de la transcripción que lo soporta.")


class CambioPPTDetectado(BaseModel):
    """Petición que afecta solo a la presentación (maquetación, orden, gráficos…)."""

    que_cambiar: str = Field(description="Qué se pidió cambiar en el PPT (diseño, orden de diapositivas, gráficos, plantilla, colores, imágenes).")
    solicitado_por: str = Field(default="")
    cita: str = Field(default="")


class AnalisisReunion(BaseModel):
    resumen: str = Field(description="Resumen de la reunión en 3-5 frases: qué se revisó y qué se acordó.")
    cambios_texto: list[CambioTextoDetectado] = Field(default_factory=list)
    cambios_ppt: list[CambioPPTDetectado] = Field(default_factory=list)
    pendientes: list[str] = Field(default_factory=list, description="Peticiones que no pueden aplicarse sin un dato o confirmación que no consta (indicar qué falta y quién debe aportarlo).")
    acuerdos_sin_cambio: list[str] = Field(default_factory=list, description="Acuerdos de la reunión que no modifican el informe (plazos de conformidad, seguimiento, reparto de tareas).")
