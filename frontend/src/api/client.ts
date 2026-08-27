import type { Api, Estado } from "./types";

const BASE = "/api";

class ApiError extends Error {}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) {
    let mensaje = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      mensaje = body.error ?? body.detail?.error ?? mensaje;
    } catch { /* sin cuerpo JSON */ }
    throw new ApiError(mensaje);
  }
  return (await res.json()) as T;
}

const json = (body: unknown, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const e = (ref: string) => `/expedientes/${encodeURIComponent(ref)}`;

export const clienteReal: Api = {
  listarExpedientes: () => req("/expedientes"),
  crearExpediente: (d) => req("/expedientes", json(d)),
  estado: (ref) => req(e(ref)),
  eliminarExpediente: (ref, confirmacion) => req(e(ref), json({ confirmacion }, "DELETE")),
  job: (id) => req(`/jobs/${id}`),
  documentos: (ref) => req(`${e(ref)}/documentos`),
  subir: (ref, carpeta, ficheros) => {
    const fd = new FormData();
    ficheros.forEach((f) => fd.append("ficheros", f));
    return req(`${e(ref)}/documentos/${carpeta}`, { method: "POST", body: fd });
  },
  borrarDocumento: (ref, carpeta, nombre) => req(`${e(ref)}/documentos/${carpeta}/${encodeURIComponent(nombre)}`, { method: "DELETE" }),
  redactarContexto: (ref, o) => req(`${e(ref)}/acciones/redactar-contexto`, json(o)),
  extraer: (ref, forzar) => req(`${e(ref)}/acciones/extraer`, json({ forzar })),
  conclusiones: (ref) => req(`${e(ref)}/conclusiones`),
  guardarConclusion: (ref, id, campos) => req(`${e(ref)}/conclusiones/${id}`, json(campos, "PUT")),
  guardarConclusionesMd: (ref, markdown) => req(`${e(ref)}/conclusiones`, json({ markdown }, "PUT")),
  aprobar: (ref, ids, estado: Estado) => req(`${e(ref)}/acciones/aprobar`, json({ ids, estado })),
  revisarConclusiones: (ref) => req(`${e(ref)}/acciones/revisar-conclusiones`, { method: "POST" }),
  corregirConclusiones: (ref, ids) => req(`${e(ref)}/acciones/corregir-conclusiones`, json({ ids: ids ?? [] })),
  regenerar: (ref, id, notas) => req(`${e(ref)}/acciones/regenerar`, json({ id, notas })),
  recomendar: (ref, o) => req(`${e(ref)}/acciones/recomendar`, json(o)),
  redactarConclusiones: (ref) => req(`${e(ref)}/acciones/redactar-conclusiones`, { method: "POST" }),
  informe: (ref) => req(`${e(ref)}/informe`),
  guardarInforme: (ref, d) => req(`${e(ref)}/informe`, json(d, "PUT")),
  revisar: (ref) => req(`${e(ref)}/acciones/revisar`, { method: "POST" }),
  corregir: (ref, avisos) => req(`${e(ref)}/acciones/corregir`, json({ avisos })),
  condensar: (ref, objetivo = 0.85) => req(`${e(ref)}/acciones/condensar`, json({ objetivo })),
  cambio: (ref, mensaje, soloPlan = false) => req(`${e(ref)}/acciones/cambio`, json({ mensaje, solo_plan: soloPlan })),
  instrucciones: (ref) => req(`${e(ref)}/instrucciones`),
  guardarInstrucciones: (ref, texto) => req(`${e(ref)}/instrucciones`, json({ texto }, "PUT")),
  aplicarCambios: (ref, soloPlan = false) => req(`${e(ref)}/acciones/aplicar-cambios`, json({ solo_plan: soloPlan })),
  reunion: (ref, fichero, aplicar) => {
    const fd = new FormData();
    fd.append("transcripcion", fichero);
    fd.append("aplicar", String(aplicar));
    return req(`${e(ref)}/acciones/reunion`, { method: "POST", body: fd });
  },
  historial: (ref) => req(`${e(ref)}/historial`),
  deshacer: (ref, fichero) => req(`${e(ref)}/acciones/deshacer`, json({ fichero })),
  diff: (ref, fichero) => req(`${e(ref)}/diff?fichero=${fichero}`),
  cambios: (ref) => req(`${e(ref)}/cambios`),
  reuniones: (ref) => req(`${e(ref)}/reuniones`),
  ppt: (ref) => req(`${e(ref)}/acciones/ppt`, { method: "POST" }),
  archivar: (ref) => req(`${e(ref)}/acciones/archivar`, { method: "POST" }),
  trazas: (ref) => req(`${e(ref)}/trazas`),
  traza: (ref, nombre) => req(`${e(ref)}/trazas/${encodeURIComponent(nombre)}`),
};
