import { clienteReal } from "./client";
import { clienteMock } from "./mock";
import type { Api, Job } from "./types";

export const MOCK = import.meta.env.VITE_MOCK === "1";
export const api: Api = MOCK ? clienteMock : clienteReal;

/** Espera a que termine un trabajo del modelo (polling cada 2 s). */
export async function esperarJob<T = unknown>(jobId: string, onTick?: (j: Job<T>) => void): Promise<Job<T>> {
  for (;;) {
    const j = await api.job<T>(jobId);
    onTick?.(j);
    if (j.estado !== "en_curso") return j;
    await new Promise((r) => setTimeout(r, MOCK ? 700 : 2000));
  }
}

export * from "./types";
