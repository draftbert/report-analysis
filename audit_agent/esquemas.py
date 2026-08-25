"""
Esquemas Pydantic de las salidas estructuradas del LLM.

Son el "contrato" que viaja al modelo como `output_format_schema` (KAIA) y el
formato pivote de la herramienta: lo que se extrae de los papeles de trabajo,
lo que se revisa y lo que alimenta el informe y el PPT.

Precaución (heredada de audit-engine): las clases que viajan al modelo se
compilan con `to_strict_json_schema` -> todos los campos son obligatorios y
`additionalProperties: false` en cada nivel. Un campo que no esté aquí,
literalmente no se le pide al modelo.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

NIVELES_RIESGO = ("Alto", "Medio", "Bajo")


class Observacion(BaseModel):
    """Observación en esquema 4C + recomendación (config/estilo.yaml
    `estructura_observacion`). Cadena vacía = no deducible de la fuente."""

    titulo: str = Field(description="Título breve de la observación (una línea).")
    condicion: str = Field(description="Qué se ha observado: hecho objetivo, con los datos de la muestra.")
    criterio: str = Field(description="Contra qué se compara: norma, política interna, buena práctica.")
    causa_raiz: str = Field(description="Por qué ocurre la debilidad.")
    efecto: str = Field(description="Riesgo o impacto de la debilidad.")
    recomendacion: str = Field(description="Acción propuesta, concreta y accionable.")
    nivel_riesgo: str = Field(description="Exactamente uno de: Alto, Medio, Bajo. Vacío si no es deducible.")
    responsable: str = Field(description="Área o rol responsable del plan de acción.")
    fuente: str = Field(description="Referencia al papel de trabajo / evidencia que soporta la observación.")


class ObservacionExtraida(Observacion):
    """Observación tal como sale del extractor: añade la procedencia del
    nivel de riesgo. Si el papel de trabajo no menciona severidad/riesgo, el
    nivel es una propuesta del modelo y así se marca en 01_observaciones.md
    hasta que el auditor la valide al aprobar."""

    riesgo_soportado_por_evidencia: bool = Field(
        description="true SOLO si el papel de trabajo menciona explícitamente la severidad, criticidad o "
                    "nivel de riesgo de esta debilidad. false si el nivel es una estimación propia.")


class ExtraccionObservaciones(BaseModel):
    observaciones: list[ObservacionExtraida]
    notas: str = Field(description="Dudas, datos ambiguos o elementos del papel de trabajo que no se han podido clasificar. Vacío si no hay.")


class Magnitud(BaseModel):
    valor: str = Field(description="Cifra o dato, tal cual aparece en la fuente (p. ej. '8,4 M€').")
    etiqueta: str = Field(description="Qué mide (p. ej. 'Volumen del periodo').")


class EvaluacionGlobal(BaseModel):
    gobierno: str = Field(description="Valoración del gobierno del proceso, p. ej. 'Razonable — Impacto Bajo'.")
    gestion_riesgos: str = Field(description="Valoración de la gestión de riesgos, mismo formato.")
    entorno_control: str = Field(description="Valoración del entorno de control, mismo formato.")
    conclusion: str = Field(description="Conclusión global del trabajo (uno o dos párrafos).")


class BorradorInforme(BaseModel):
    """Texto completo del Resumen Ejecutivo. Las observaciones vienen de las
    aprobadas por el auditor: el modelo puede pulir la redacción pero no
    añadir, quitar ni alterar hechos."""

    objetivo: str
    alcance: str
    contexto: str = Field(description="Párrafo de contexto y principales magnitudes del proceso auditado.")
    magnitudes: list[Magnitud] = Field(description="Entre 2 y 4 magnitudes clave. Solo cifras presentes en la fuente.")
    observaciones: list[Observacion]
    evaluacion_global: EvaluacionGlobal
    proximos_pasos: str


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
    texto_original: str = Field(description="Fragmento EXACTO y contiguo del informe actual que se sustituye (copiado literal, sin recortar ni corregir). Vacío solo si es una inserción.")
    texto_nuevo: str = Field(description="Texto que sustituye al original (o que se inserta). Vacío si es una eliminación.")
    insertar_tras: str = Field(description="Solo para inserciones: fragmento EXACTO del informe tras el cual se inserta el texto nuevo. Vacío en sustituciones.")


class PlanCambios(BaseModel):
    cambios: list[Cambio]
    pendientes: list[str] = Field(description="Instrucciones que no se han podido aplicar (falta información, ambigüedad, contradicen la evidencia) y por qué. Vacío si no hay.")

class PropuestaRegla(BaseModel):
    """Propuesta de cambio en config/estilo.yaml derivada de informes aprobados."""

    tipo: str = Field(description="Exactamente uno de: alta (regla nueva), baja (eliminar regla), modificacion (ajustar sugerencia/motivo o añadir excepción).")
    seccion: str = Field(description="Sección del YAML afectada: palabras_prohibidas | primera_persona | reglas.")
    termino: str = Field(description="Término o expresión objeto de la regla (literal).")
    sugerencia: str = Field(description="Alternativa de redacción propuesta (para altas/modificaciones). Vacío en bajas.")
    motivo: str = Field(description="Por qué se propone, en una o dos frases.")
    evidencia: list[str] = Field(description="Fragmentos LITERALES del corpus que soportan la propuesta (con el fichero entre corchetes). Mínimo uno.")
    confianza: str = Field(description="alta | media | baja, según cuánta evidencia hay.")


class PropuestasEstilo(BaseModel):
    propuestas: list[PropuestaRegla]
    patrones_observados: str = Field(description="Rasgos de estilo consistentes en los informes aprobados que no se traducen en una regla concreta (estructura de frases, terminología, tono). Vacío si no hay.")
