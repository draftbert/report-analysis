/* Formato de fechas, duraciones y tamaños; clases de etiquetas por valor. */
import type { EstadoApartadoDiff, EstadoConclusion, Riesgo } from "@/api";

export const fmt = {
  fecha(iso: string | undefined | null): string {
    if (!iso) return "—";
    const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" }).replace(".", "").toUpperCase();
  },
  fechaHora(iso: string | undefined | null): string {
    if (!iso) return "—";
    return iso.slice(0, 16).replace("T", " ");
  },
  relativa(iso: string | undefined | null): string {
    if (!iso) return "—";
    const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
    if (Number.isNaN(d)) return iso;
    if (d <= 0) return "hoy";
    if (d === 1) return "ayer";
    if (d < 30) return `hace ${d} días`;
    return `hace ${Math.floor(d / 30)} mes${d >= 60 ? "es" : ""}`;
  },
  duracion(s: number | undefined | null): string {
    const seg = Math.round(s || 0);
    if (!seg) return "—";
    if (seg < 60) return `${seg} S`;
    const m = Math.round(seg / 60);
    return m < 60 ? `${m} MIN` : `${Math.floor(m / 60)} H ${String(m % 60).padStart(2, "0")} MIN`;
  },
  mmss: (s: number | undefined | null) => `${String(Math.floor((s || 0) / 60)).padStart(2, "0")}:${String(Math.floor((s || 0) % 60)).padStart(2, "0")}`,
  bytes: (b: number) => (b > 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`),
  n: (x: number | undefined | null) => (x ?? 0).toLocaleString("es-ES"),
  dos: (x: number) => String(x).padStart(2, "0"),
};

/** Número de fase de `expediente.fase` («2 · Conclusiones» → 2). */
export const faseNum = (fase: string) => parseInt(fase, 10) || 0;
/** Fase 4 = entregable generado: el informe está emitido. */
export const esEmitido = (fase: string) => faseNum(fase) >= 4;
/** «`redactar-contexto`: …» → texto sin los acentos graves del CLI. */
export const textoSiguiente = (s: string) => s.replace(/`/g, "");

export const ESTADO_CONCLUSION: Record<EstadoConclusion, [string, string]> = {
  propuesta: ["status-pending", "Propuesta"], aprobada: ["status-completed", "Aprobada"], descartada: ["status-error", "Descartada"],
};
/** Estado de un apartado en «Últimos cambios» del informe. */
export const ESTADO_CAMBIO: Record<EstadoApartadoDiff, [string, string]> = {
  igual: ["tag-neutral", "Sin cambios"], modificado: ["tag-warning", "Modificado"], nuevo: ["tag-success", "Añadido"], eliminado: ["tag-error", "Eliminado"],
};
export const riesgoClase = (r: Riesgo | string) =>
  ({ crítico: "tag-error", critico: "tag-error", alto: "tag-warning", medio: "tag-info", bajo: "tag-neutral" } as Record<string, string>)[(r || "").toLowerCase()] ?? "tag-neutral";
export const severidadClase = (s: "error" | "aviso") => (s === "error" ? "tag-error" : "tag-warning");
/** Estado de cada línea del plan de `aplicar-cambios`/`cambio`. */
export const planClase = (estado: string) =>
  estado.startsWith("aplicado") || estado === "insertado" || estado === "eliminado" ? "tag-success" : estado === "CONFLICTO" ? "tag-error" : "tag-neutral";

export const esAudioOVideo = (nombre: string) => /\.(mp3|wav|m4a|webm|ogg|oga|flac|mp4|mpga|mov|mkv|avi|m4v|wmv|mpe?g)$/i.test(nombre);
export const esVideo = (nombre: string) => /\.(mp4|webm|mov|mkv|avi|m4v|wmv|mpe?g)$/i.test(nombre);
export const esTranscripcion = (nombre: string) => /\.(txt|docx|vtt|md)$/i.test(nombre);
/** Documentos de entrada que sabe leer el backend (papeles de trabajo y contexto). */
export const FORMATOS_DOCUMENTO = ".md,.txt,.docx,.xlsx,.pdf,.pptx";
export const esDocumento = (nombre: string) => /\.(md|txt|docx|xlsx|pdf|pptx)$/i.test(nombre);
/** Grabación de audio o vídeo por extensión o, si el nombre no la trae (descargas de Teams, móviles…), por tipo MIME. */
export const tipoMedio = (f: File): "video" | "audio" | null =>
  esVideo(f.name) || (!esAudioOVideo(f.name) && f.type.startsWith("video/")) ? "video" : esAudioOVideo(f.name) || f.type.startsWith("audio/") ? "audio" : null;
/** Si el nombre no lleva la extensión de su tipo, se la añade (el backend decide por la extensión). */
export const conExtension = (f: File): File => {
  if (esAudioOVideo(f.name) || !tipoMedio(f)) return f;
  const ext = (f.type.split("/")[1] || "").replace("quicktime", "mov").replace("x-matroska", "mkv").replace("mpeg", f.type.startsWith("audio") ? "mp3" : "mpeg");
  return ext ? new File([f], `${f.name}.${ext}`, { type: f.type, lastModified: f.lastModified }) : f;
};
