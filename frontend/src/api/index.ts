import { clienteReal } from "./client";
import type { Api, Job } from "./types";

export const api: Api = clienteReal;

/** Espera a que termine un trabajo (polling cada 2 s). */
export async function esperarJob<T = unknown>(jobId: string, onTick?: (j: Job<T>) => void): Promise<Job<T>> {
  for (;;) {
    const j = await api.job<T>(jobId);
    onTick?.(j);
    if (j.estado !== "en_curso") return j;
    await new Promise((r) => setTimeout(r, 2000));
  }
}

export * from "./types";
