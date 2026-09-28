/* Contrato con la API del backend (audit_agent/api.py). Los nombres de campo son los del JSON. */

export type EstadoConclusion = "propuesta" | "aprobada" | "descartada";
export type TipoConclusion = "recomendacion" | "sugerencia"; // bloque con recomendación y plan de acción | mejora sin plan
export type Riesgo = "Crítico" | "Alto" | "Medio" | "Bajo" | "";
export type Carpeta = "contexto" | "papeles_trabajo";

/** GET /api/expedientes devuelve la lista completa de estados; GET /api/expedientes/{ref}, uno. */
export interface Expediente {
  referencia: string;
  nombre: string;
  fecha: string;
  distribucion: string[];
  fase: string;            // «N · texto» (0 sin papeles … 4 entregable generado)
  siguiente: string;       // guía del flujo, redactada por la API
  contexto: string[];
  papeles: string[];
  conclusiones: {
    total: number; propuesta: number; aprobada: number; descartada: number; sugerencias: number;
    sin_recomendacion: string[]; riesgo_pendiente: string[]; con_notas: string[];
  } | null;
  informe: {
    contexto: boolean; n_conclusiones: number; n_sugerencias: number; errores: number; avisos: number;
    modificado: string; versiones: number;
  } | null;
  instrucciones_pendientes: boolean;
  ppt: { nombre: string; desactualizado: boolean } | null;
  archivos: string[];
  llm: string;
  modificado: string;
  /** Documentos que aún no han pasado por el modelo (o han cambiado desde entonces). */
  nuevos: { papeles_trabajo: string[]; contexto: string[] };
  /** Observaciones aprobadas que todavía no están en el informe. */
  sin_volcar: string[];
  pasos: Paso[];
  paso_sugerido: PasoId;
  sugerencia: string;      // qué toca hacer ahora, en lenguaje del auditor
  /** preparacion: primera pasada hasta tener observaciones en el informe; iteracion: se trabaja sobre el informe. */
  modo: "preparacion" | "iteracion";
  /** En iteración: lo pendiente en documentos/contexto/observaciones (se avisa en «Añadir más contexto»). */
  preparacion_pendiente: string;
}

export type PasoId = "documentos" | "contexto" | "observaciones" | "informe" | "reuniones" | "entrega";
/** Paso del flujo de trabajo de un informe: siempre navegable (al informe se vuelve varias veces). */
export interface Paso { id: PasoId; titulo: string; hecho: boolean; actual: boolean; resumen: string; aviso: string }

export interface NuevoExpediente { referencia: string; nombre: string; fecha: string; distribucion: string[] }
export interface Salud { estado: string; version: string; expedientes: number }

export interface Documento { nombre: string; bytes: number; lector: string; procesado: boolean }
export interface Documentos { contexto: Documento[]; papeles_trabajo: Documento[] }

export interface Conclusion {
  id: string;
  titulo: string;
  tipo: TipoConclusion;
  estado: EstadoConclusion;
  prueba: string;
  nivel_riesgo: Riesgo;
  riesgo_propuesto: boolean;
  area: string;
  responsable: string;
  plazo: string;
  referencia_recomendacion: string;
  fuente: string;
  incidencia: string;
  causa_raiz: string;
  como_se_ha_llegado: string;
  consecuencias: string;
  recomendacion: string;
  notas: string;
}

export interface Hallazgo {
  id?: string; linea?: number; tipo: string; severidad: "error" | "aviso"; fragmento: string; mensaje: string; sugerencia?: string;
  /** Solo en la revisión del informe: apartado (id de `Apartado`) y párrafo en el que cae, para resaltarlo. */
  parrafo_linea?: number; apartado?: string | null; parrafo?: string;
}
/** Cómo quedaría un párrafo con hallazgos según el modelo (no se aplica hasta que el auditor lo acepta). */
export interface PropuestaCorreccion {
  linea: number; apartado: string | null; original: string; propuesta: string;
  hallazgos: Pick<Hallazgo, "tipo" | "severidad" | "fragmento" | "mensaje" | "sugerencia">[];
  errores_restantes: string[]; lineas: LineaDiff[];
}

export interface Apartado {
  id: string; tipo: "introduccion" | "resumen" | "conclusion" | "sugerencia"; titulo: string; markdown: string; numero: number; nivel_riesgo: Riesgo;
}

export interface Informe {
  markdown: string;
  apartados: Apartado[];
  evaluacion_global: string;
  conclusiones: Conclusion[];
  sugerencias: Conclusion[];
}
export interface InformeEdicion { markdown?: string; introduccion?: string; resumen_ejecutivo?: string; evaluacion_global?: string }

export interface CambioPlan { seccion: string; motivo: string; estado: string; detalle: string; texto_original?: string; texto_nuevo?: string }
export interface ResultadoCambios { plan: CambioPlan[]; pendientes: string[]; diff: string; solo_plan?: boolean }

export interface CambioTexto { seccion: string; que_cambiar: string; instruccion: string; solicitado_por: string; cita: string }
export interface CambioPPT { que_cambiar: string; solicitado_por: string; cita: string }
export interface Acta {
  acta?: string; resumen: string; cambios_texto: CambioTexto[]; cambios_ppt: CambioPPT[]; pendientes: string[]; acuerdos_sin_cambio: string[];
  /** Cambios de texto ya aplicados al informe, por índice en `cambios_texto` (dejan de salir como pendientes). */
  aplicados?: Record<string, { fecha: string; resumen: string }>;
}

export interface Job<T = unknown> {
  estado: "en_curso" | "ok" | "error"; accion: string; mensaje: string; resultado: T | null;
  progreso?: string; progreso_pct?: number | null; progreso_partes?: ("pendiente" | "en_curso" | "hecha" | "error")[] | null;
}
/** Snapshot de historial/. `motivo` es el de la escritura que vino después; `origen`, ese cambio en lenguaje del auditor. */
export interface Version { fichero: string; nombre: string; fecha: string; motivo: string; origen: string }
/** Trozo de una línea modificada: `cambio` marca las palabras que difieren de su pareja. */
export interface SegmentoDiff { texto: string; cambio: boolean }
export interface LineaDiff { tipo: "igual" | "add" | "del"; texto: string; segmentos: SegmentoDiff[] | null }
export type EstadoApartadoDiff = "igual" | "modificado" | "nuevo" | "eliminado";
export interface ApartadoDiff {
  id: string; tipo: Apartado["tipo"] | "documento"; titulo: string; numero: number; nivel_riesgo: Riesgo; estado: EstadoApartadoDiff;
  lineas: LineaDiff[]; lineas_nuevas: number; lineas_borradas: number;
}
/** El informe actual comparado apartado a apartado con un snapshot (`contra`; sin él, el último cambio). */
export type ModoVolcado = "rehacer" | "anadir";
/** Cómo quedaría el informe al pasar las observaciones aprobadas (no escribe nada). */
export interface SimulacionVolcado { modo: ModoVolcado; entran: string[]; bloqueadas: string[]; apartados: ApartadoDiff[]; lineas_nuevas: number; lineas_borradas: number }
export interface ComparacionInforme { contra: Version | null; versiones: Version[]; apartados: ApartadoDiff[]; lineas_nuevas: number; lineas_borradas: number }
export interface Traza { nombre: string; fecha: string; accion: string; modelo: string; error?: string | null; tokens: { prompt: number | null; completion: number | null } }
export interface ReunionActa { nombre: string; fecha: string; markdown: string; datos: (Acta & { transcripcion?: string | null }) | null }
export interface ReunionTranscripcion { nombre: string; fecha: string; markdown: string }
/** Ítem del listado de reuniones: agrupa el acta (con su estructura si existe) y las transcripciones del mismo origen. */
export interface Reunion { origen: string; fecha: string; actas: ReunionActa[]; transcripciones: ReunionTranscripcion[] }
export interface HablanteTranscripcion { id: string; clip: string; muestra: string; segundos: number; conocido: boolean; nombre: string; accion: string; guardar: boolean }
export interface Voz { nombre: string; segundos: number; origen: string; fecha: string }
export interface Transcripcion { hay_transcripcion: boolean; etiquetada: boolean; origen: string; fecha: string; duracion_s: number; markdown: string; hablantes: HablanteTranscripcion[]; voces: Voz[] }
export type Asignaciones = Record<string, { nombre: string; accion: string }>;
export interface Descarga { nombre: string; url: string }

/** Criterio de estilo (config/estilo.yaml), mismas claves que el YAML. */
export interface PalabraProhibida { termino: string; sugerencia: string; motivo: string }
export interface ExpresionAlternativa { termino: string; alternativa: string }
export interface EjemploAbsoluto { antes: string; despues: string }
export type ClaveExtension = "intro_bloque" | "resumen_total" | "resumen_vineta" | "incidencia" | "causa_raiz" | "detalle_vineta" | "detalles_max" | "consecuencias" | "recomendacion";
export interface Reglas {
  palabras_prohibidas: PalabraProhibida[];
  primera_persona: string[];
  tono: {
    principios: string[]; expresiones_a_cuestionar: ExpresionAlternativa[]; formulas_constructivas: string[];
    absolutos: { criterio: string; ejemplos: EjemploAbsoluto[] }; adjetivos_a_cuestionar: ExpresionAlternativa[]; tiempos_verbales: string[];
  };
  extension: Record<ClaveExtension, number>;
  reglas: { longitud_maxima_frase: number; requiere_nivel_riesgo: boolean; niveles_riesgo_validos: string[]; escala_evaluacion_global: string[] };
  estructura_conclusion: { campo: string; descripcion: string; requerido: boolean }[];
}
export interface VersionReglas { nombre: string; fecha: string; motivo: string }
export interface EstadoReglas { reglas: Reglas; yaml: string; historial: VersionReglas[]; modificado: string }
/** Resultado del job de «modificar usando el chat»: el modelo propone, el auditor guarda. */
export interface PropuestaReglas { respuesta: string; cambios: string[]; reglas: Reglas; diff: string; sin_cambios: boolean }

export interface Api {
  logout(): Promise<void>;
  salud(): Promise<Salud>;
  job<T = unknown>(id: string): Promise<Job<T>>;
  /** Pide detener un trabajo en curso; el corte llega en el siguiente punto de control. */
  detenerJob(id: string): Promise<{ mensaje: string }>;

  listarExpedientes(): Promise<Expediente[]>;
  crearExpediente(d: NuevoExpediente): Promise<Expediente>;
  estado(ref: string): Promise<Expediente>;
  /** Borra el expediente entero; `confirmacion` debe ser la referencia exacta. */
  eliminarExpediente(ref: string, confirmacion: string): Promise<{ mensaje: string }>;

  documentos(ref: string): Promise<Documentos>;
  /** Sube los ficheros uno a uno; `onProgreso(nombre, pct)` recibe el avance real (0-100) de cada uno. */
  subir(ref: string, carpeta: Carpeta, ficheros: File[], onProgreso?: (nombre: string, pct: number) => void): Promise<Documentos>;
  borrarDocumento(ref: string, carpeta: Carpeta, nombre: string): Promise<Documentos>;

  redactarContexto(ref: string, o: { forzar?: boolean; secciones?: string[] }): Promise<{ job_id: string }>;
  /** `soloNuevos`: solo los papeles de trabajo aún no procesados; sus observaciones se añaden a las existentes. */
  extraer(ref: string, forzar: boolean, soloNuevos?: boolean): Promise<{ job_id: string }>;
  conclusiones(ref: string): Promise<{ markdown: string; conclusiones: Conclusion[] }>;
  guardarConclusion(ref: string, id: string, campos: Partial<Conclusion>): Promise<Conclusion>;
  aprobar(ref: string, ids: string[], estado: EstadoConclusion): Promise<{ mensaje: string }>;
  revisarConclusiones(ref: string): Promise<{ hallazgos: Hallazgo[] }>;
  corregirConclusiones(ref: string, ids?: string[]): Promise<{ job_id: string }>;
  regenerar(ref: string, id: string, notas: string): Promise<{ job_id: string }>;
  recomendar(ref: string, o: { ids?: string[]; respuestas: Record<string, string>; auto: boolean; formatear?: boolean }): Promise<{ job_id: string }>;
  /** Pasa las aprobadas al informe: `anadir` conserva el detalle actual y suma las nuevas; `rehacer` lo reconstruye. */
  redactarConclusiones(ref: string, modo?: ModoVolcado): Promise<{ mensaje: string }>;
  simularVolcado(ref: string, modo: ModoVolcado): Promise<SimulacionVolcado>;

  informe(ref: string): Promise<Informe>;
  guardarInforme(ref: string, d: InformeEdicion): Promise<Informe>;
  revisar(ref: string): Promise<{ hallazgos: Hallazgo[]; errores: number; avisos: number }>;
  /** Job: propuestas de corrección por párrafo (resultado `{ propuestas }`); `soloErrores` deja fuera los avisos. */
  proponerCorrecciones(ref: string, soloErrores?: boolean): Promise<{ job_id: string }>;
  /** Aplica al informe la corrección aceptada de un párrafo (falla si el párrafo ha cambiado desde la revisión). */
  aplicarCorreccion(ref: string, original: string, propuesta: string): Promise<{ mensaje: string }>;
  corregir(ref: string, avisos: boolean): Promise<{ job_id: string }>;
  condensar(ref: string, objetivo?: number): Promise<{ job_id: string }>;
  cambio(ref: string, mensaje: string, soloPlan?: boolean): Promise<{ job_id: string }>;
  instrucciones(ref: string): Promise<{ texto: string }>;
  guardarInstrucciones(ref: string, texto: string): Promise<{ texto: string }>;
  /** Sin `texto`, aplica el buzón 03_instrucciones.md; con `texto` (cambios de un acta), directo y sin tocar el buzón. */
  aplicarCambios(ref: string, soloPlan?: boolean, texto?: string, desdeActa?: { acta: string; indices: number[] }): Promise<{ job_id: string }>;
  /** Devuelve a pendientes (`aplicado=false`) cambios de texto de un acta; responde la estructura del acta. */
  marcarCambiosActa(ref: string, acta: string, indices: number[], aplicado: boolean): Promise<Acta>;
  historial(ref: string): Promise<Version[]>;
  deshacer(ref: string, fichero: string): Promise<{ mensaje: string }>;
  diff(ref: string, fichero: string): Promise<{ diff: string; contra: string | null }>;
  /** Cambios del informe por apartados contra `contra` (nombre de un snapshot); sin él, contra el último cambio. */
  comparacionInforme(ref: string, contra?: string): Promise<ComparacionInforme>;

  /** Transcripción (.txt/.docx/.vtt) o audio/vídeo. `onProgreso(pct)` es la subida; `repetir` salta el aviso de duplicado. */
  reunion(ref: string, fichero: File, aplicar: boolean, onProgreso?: (pct: number) => void, repetir?: boolean): Promise<{ job_id: string }>;
  reuniones(ref: string): Promise<Reunion[]>;
  borrarReunion(ref: string, nombre: string): Promise<Reunion[]>;
  transcribir(ref: string, fichero: File, onProgreso?: (pct: number) => void, repetir?: boolean): Promise<{ job_id: string }>;
  transcripcion(ref: string): Promise<Transcripcion>;
  /** Autoguarda el borrador del etiquetado. `guardarIds` = ids de hablante con «guardar voz». */
  borradorTranscripcion(ref: string, asignaciones: Asignaciones, guardarIds: string[]): Promise<Transcripcion>;
  /** Job: etiqueta en local, guarda la transcripción en reuniones/ y la analiza como reunión (acta). */
  etiquetar(ref: string, asignaciones: Asignaciones, guardarVoces: string[]): Promise<{ job_id: string }>;
  borrarVoz(ref: string, nombre: string): Promise<Transcripcion>;

  reglas(): Promise<EstadoReglas>;
  /** Guarda el criterio (snapshot previo en config/historial/): reglas estructuradas o el YAML completo. */
  guardarReglas(d: { reglas?: Reglas; yaml?: string; motivo?: string }): Promise<EstadoReglas>;
  restaurarReglas(nombre: string): Promise<EstadoReglas>;
  /** Job: propuesta del modelo a partir de `mensaje` sobre `reglas` (las del editor) o las guardadas. */
  chatReglas(mensaje: string, reglas?: Reglas): Promise<{ job_id: string }>;

  ppt(ref: string): Promise<Descarga>;
  archivar(ref: string): Promise<Descarga>;
  trazas(ref: string): Promise<Traza[]>;
  traza(ref: string, nombre: string): Promise<Record<string, unknown>>;

  /** URLs de descarga/clips (se abren con el navegador, con la cookie de sesión). */
  urlSalida(ref: string, nombre: string): string;
  urlClip(ref: string, fichero: string): string;
}
