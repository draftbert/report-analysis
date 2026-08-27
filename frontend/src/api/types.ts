export type Estado = "propuesta" | "aprobada" | "descartada";
export type Tipo = "conclusion" | "sugerencia";
export type Riesgo = "Crítico" | "Alto" | "Medio" | "Bajo" | "";

export interface ExpedienteResumen {
  referencia: string;
  nombre: string;
  fecha: string;
  fase: string;
  siguiente: string;
  modificado: string;
}

export interface ExpedienteEstado extends ExpedienteResumen {
  distribucion: string[];
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
}

export interface Documento { nombre: string; bytes: number; lector: string }
export interface Documentos { contexto: Documento[]; papeles_trabajo: Documento[] }

export interface Conclusion {
  id: string;
  titulo: string;
  tipo: Tipo;
  estado: Estado;
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

export interface CambioPlan { seccion: string; motivo: string; estado: string; detalle: string; texto_original?: string; texto_nuevo?: string }
export interface ResultadoCambios { plan: CambioPlan[]; pendientes: string[]; diff: string; solo_plan?: boolean }

export interface CambioTexto { seccion: string; que_cambiar: string; instruccion: string; solicitado_por: string; cita: string }
export interface CambioPPT { que_cambiar: string; solicitado_por: string; cita: string }
export interface Acta {
  acta: string; resumen: string; cambios_texto: CambioTexto[]; cambios_ppt: CambioPPT[]; pendientes: string[]; acuerdos_sin_cambio: string[];
}

export interface Job<T = unknown> { estado: "en_curso" | "ok" | "error"; accion: string; mensaje: string; resultado: T | null }
export interface Version { fichero: string; nombre: string; fecha: string; motivo: string }
export interface Traza { nombre: string; fecha: string; accion: string; modelo: string; error?: string | null; tokens: { prompt: number | null; completion: number | null } }
export interface Reunion { nombre: string; fecha: string; markdown: string }
export interface Descarga { nombre: string; url: string }

export interface Api {
  listarExpedientes(): Promise<ExpedienteResumen[]>;
  crearExpediente(d: { referencia: string; nombre: string; fecha: string; distribucion: string[] }): Promise<ExpedienteEstado>;
  estado(ref: string): Promise<ExpedienteEstado>;
  eliminarExpediente(ref: string, confirmacion: string): Promise<{ mensaje: string }>;
  job<T = unknown>(id: string): Promise<Job<T>>;
  documentos(ref: string): Promise<Documentos>;
  subir(ref: string, carpeta: "contexto" | "papeles_trabajo", ficheros: File[]): Promise<Documentos>;
  borrarDocumento(ref: string, carpeta: string, nombre: string): Promise<Documentos>;
  redactarContexto(ref: string, o: { forzar?: boolean; secciones?: string[] }): Promise<{ job_id: string }>;
  extraer(ref: string, forzar: boolean): Promise<{ job_id: string }>;
  conclusiones(ref: string): Promise<{ markdown: string; conclusiones: Conclusion[] }>;
  guardarConclusion(ref: string, id: string, campos: Partial<Conclusion>): Promise<Conclusion>;
  guardarConclusionesMd(ref: string, markdown: string): Promise<{ conclusiones: Conclusion[] }>;
  aprobar(ref: string, ids: string[], estado: Estado): Promise<{ mensaje: string }>;
  revisarConclusiones(ref: string): Promise<{ hallazgos: Hallazgo[] }>;
  corregirConclusiones(ref: string, ids?: string[]): Promise<{ job_id: string }>;
  regenerar(ref: string, id: string, notas: string): Promise<{ job_id: string }>;
  recomendar(ref: string, o: { ids?: string[]; respuestas: Record<string, string>; auto: boolean; formatear?: boolean }): Promise<{ job_id: string }>;
  redactarConclusiones(ref: string): Promise<{ mensaje: string }>;
  informe(ref: string): Promise<Informe>;
  guardarInforme(ref: string, d: { markdown?: string; introduccion?: string; resumen_ejecutivo?: string; evaluacion_global?: string }): Promise<Informe>;
  revisar(ref: string): Promise<{ hallazgos: Hallazgo[]; errores: number; avisos: number }>;
  corregir(ref: string, avisos: boolean): Promise<{ job_id: string }>;
  cambio(ref: string, mensaje: string, soloPlan?: boolean): Promise<{ job_id: string }>;
  instrucciones(ref: string): Promise<{ texto: string }>;
  guardarInstrucciones(ref: string, texto: string): Promise<{ texto: string }>;
  aplicarCambios(ref: string, soloPlan?: boolean): Promise<{ job_id: string }>;
  reunion(ref: string, fichero: File, aplicar: boolean): Promise<{ job_id: string }>;
  historial(ref: string): Promise<Version[]>;
  deshacer(ref: string, fichero: string): Promise<{ mensaje: string }>;
  diff(ref: string, fichero: string): Promise<{ diff: string; contra: string | null }>;
  cambios(ref: string): Promise<{ markdown: string }>;
  reuniones(ref: string): Promise<Reunion[]>;
  ppt(ref: string): Promise<Descarga>;
  archivar(ref: string): Promise<Descarga>;
  trazas(ref: string): Promise<Traza[]>;
  traza(ref: string, nombre: string): Promise<Record<string, unknown>>;
}
