import type { Api, Carpeta, Documentos, Salud } from "./types";

const BASE = "/api";

export class ApiError extends Error {}

const aLogin = () => {
  // sesión caducada: con nginx, recargar sirve la pantalla de acceso en esta misma URL;
  // con vite (desarrollo) vamos a la página estática de public/.
  if (import.meta.env.DEV) window.location.href = "/acceso.html";
  else window.location.reload();
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (res.status === 401) {
    aLogin();
    throw new ApiError("Sesión caducada; vuelve a entrar.");
  }
  if (!res.ok) {
    let mensaje = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      mensaje = body.error ?? body.detail?.error ?? (typeof body.detail === "string" ? body.detail : mensaje);
    } catch { /* sin cuerpo JSON */ }
    throw new ApiError(mensaje);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (body: unknown, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const e = (ref: string) => `/expedientes/${encodeURIComponent(ref)}`;
const acc = (ref: string, accion: string) => `${e(ref)}/acciones/${accion}`;

/** POST multipart con XMLHttpRequest para tener el progreso real de subida (fetch no lo expone). */
const postConProgreso = <T,>(url: string, fd: FormData, onProgreso?: (pct: number) => void) =>
  new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.upload.onprogress = (ev) => { if (ev.lengthComputable) onProgreso?.(Math.round((ev.loaded / ev.total) * 100)); };
    xhr.onload = () => {
      if (xhr.status === 401) { aLogin(); reject(new ApiError("Sesión caducada; vuelve a entrar.")); return; }
      if (xhr.status >= 200 && xhr.status < 300) { onProgreso?.(100); resolve(JSON.parse(xhr.responseText) as T); return; }
      let mensaje = `${xhr.status} ${xhr.statusText}`;
      try { const body = JSON.parse(xhr.responseText); mensaje = body.error ?? body.detail?.error ?? mensaje; } catch { /* sin JSON */ }
      reject(new ApiError(xhr.status === 413 ? "El fichero supera el límite de subida del servidor." : mensaje));
    };
    xhr.onerror = () => reject(new ApiError("Error de red durante la subida (¿fichero demasiado grande o conexión cortada?)."));
    xhr.open("POST", url);
    xhr.send(fd);
  });

let saludPromesa: Promise<Salud> | null = null;

export const clienteReal: Api = {
  logout: () => req("/acceso/logout", { method: "POST" }),
  salud: () => (saludPromesa ??= req<Salud>("/salud").catch((e) => { saludPromesa = null; throw e; })),
  job: (id) => req(`/jobs/${id}`),
  detenerJob: (id) => req(`/jobs/${id}/detener`, { method: "POST" }),

  listarExpedientes: () => req("/expedientes"),
  crearExpediente: (d) => req("/expedientes", json(d)),
  estado: (ref) => req(e(ref)),
  eliminarExpediente: (ref, confirmacion) => req(e(ref), json({ confirmacion }, "DELETE")),

  documentos: (ref) => req(`${e(ref)}/documentos`),
  subir: async (ref, carpeta: Carpeta, ficheros, onProgreso) => {
    let docs: Documentos = { contexto: [], papeles_trabajo: [] };
    for (const f of ficheros) {
      const fd = new FormData();
      fd.append("ficheros", f, f.name);
      docs = await postConProgreso<Documentos>(`${BASE}${e(ref)}/documentos/${carpeta}`, fd, (pct) => onProgreso?.(f.name, pct));
    }
    return docs;
  },
  borrarDocumento: (ref, carpeta, nombre) => req(`${e(ref)}/documentos/${carpeta}/${encodeURIComponent(nombre)}`, { method: "DELETE" }),

  redactarContexto: (ref, o) => req(acc(ref, "redactar-contexto"), json(o)),
  extraer: (ref, forzar, soloNuevos = false) => req(acc(ref, "extraer"), json({ forzar, solo_nuevos: soloNuevos })),
  conclusiones: (ref) => req(`${e(ref)}/conclusiones`),
  guardarConclusion: (ref, id, campos) => req(`${e(ref)}/conclusiones/${encodeURIComponent(id)}`, json(campos, "PUT")),
  aprobar: (ref, ids, estado) => req(acc(ref, "aprobar"), json({ ids, estado })),
  revisarConclusiones: (ref) => req(acc(ref, "revisar-conclusiones"), { method: "POST" }),
  corregirConclusiones: (ref, ids) => req(acc(ref, "corregir-conclusiones"), json({ ids: ids ?? null })),
  regenerar: (ref, id, notas) => req(acc(ref, "regenerar"), json({ id, notas })),
  recomendar: (ref, o) => req(acc(ref, "recomendar"), json(o)),
  redactarConclusiones: (ref, modo = "rehacer") => req(acc(ref, "redactar-conclusiones"), json({ modo })),
  simularVolcado: (ref, modo) => req(acc(ref, "redactar-conclusiones"), json({ modo, simular: true })),

  informe: (ref) => req(`${e(ref)}/informe`),
  guardarInforme: (ref, d) => req(`${e(ref)}/informe`, json(d, "PUT")),
  revisar: (ref) => req(acc(ref, "revisar"), { method: "POST" }),
  corregir: (ref, avisos) => req(acc(ref, "corregir"), json({ avisos })),
  condensar: (ref, objetivo = 0.85) => req(acc(ref, "condensar"), json({ objetivo })),
  cambio: (ref, mensaje, soloPlan = false) => req(acc(ref, "cambio"), json({ mensaje, solo_plan: soloPlan })),
  instrucciones: (ref) => req(`${e(ref)}/instrucciones`),
  guardarInstrucciones: (ref, texto) => req(`${e(ref)}/instrucciones`, json({ texto }, "PUT")),
  aplicarCambios: (ref, soloPlan = false, texto) => req(acc(ref, "aplicar-cambios"), json({ solo_plan: soloPlan, texto: texto ?? null })),
  historial: (ref) => req(`${e(ref)}/historial`),
  deshacer: (ref, fichero) => req(acc(ref, "deshacer"), json({ fichero })),
  diff: (ref, fichero) => req(`${e(ref)}/diff?fichero=${encodeURIComponent(fichero)}`),
  comparacionInforme: (ref, contra) => req(`${e(ref)}/informe/comparacion${contra ? `?contra=${encodeURIComponent(contra)}` : ""}`),

  reunion: (ref, fichero, aplicar, onProgreso, repetir = false) => {
    const fd = new FormData();
    fd.append("transcripcion", fichero, fichero.name);
    fd.append("aplicar", String(aplicar));
    fd.append("repetir", String(repetir));
    return postConProgreso(`${BASE}${acc(ref, "reunion")}`, fd, onProgreso);
  },
  reuniones: (ref) => req(`${e(ref)}/reuniones`),
  borrarReunion: (ref, nombre) => req(`${e(ref)}/reuniones/${encodeURIComponent(nombre)}`, { method: "DELETE" }),
  transcribir: (ref, fichero, onProgreso, repetir = false) => {
    const fd = new FormData();
    fd.append("fichero", fichero, fichero.name);
    fd.append("repetir", String(repetir));
    return postConProgreso(`${BASE}${acc(ref, "transcribir")}`, fd, onProgreso);
  },
  transcripcion: (ref) => req(`${e(ref)}/transcripcion`),
  borradorTranscripcion: (ref, asignaciones, guardarIds) => req(`${e(ref)}/transcripcion/borrador`, json({ asignaciones, guardar_voces: guardarIds }, "PUT")),
  etiquetar: (ref, asignaciones, guardarVoces) => req(acc(ref, "etiquetar"), json({ asignaciones, guardar_voces: guardarVoces })),
  borrarVoz: (ref, nombre) => req(`${e(ref)}/voces/${encodeURIComponent(nombre)}`, { method: "DELETE" }),

  reglas: () => req("/reglas"),
  guardarReglas: (d) => req("/reglas", json(d, "PUT")),
  restaurarReglas: (nombre) => req("/reglas/restaurar", json({ nombre })),
  chatReglas: (mensaje, reglas) => req("/reglas/chat", json({ mensaje, reglas: reglas ?? null })),

  ppt: (ref) => req(acc(ref, "ppt"), { method: "POST" }),
  archivar: (ref) => req(acc(ref, "archivar"), { method: "POST" }),
  trazas: (ref) => req(`${e(ref)}/trazas`),
  traza: (ref, nombre) => req(`${e(ref)}/trazas/${encodeURIComponent(nombre)}`),

  urlSalida: (ref, nombre) => `${BASE}${e(ref)}/salidas/${encodeURIComponent(nombre)}`,
  urlClip: (ref, fichero) => `${BASE}${e(ref)}/audio/hablantes/${encodeURIComponent(fichero)}`,
};
