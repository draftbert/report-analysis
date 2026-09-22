import { useCallback, useRef, useState } from "react";

import { api, esperarJob } from "@/api";
import type { Job } from "@/api";

const fallo = <T,>(mensaje: string): Job<T> => ({ estado: "error", accion: "", mensaje, resultado: null });

/** Sigue un trabajo del backend: progreso en vivo, resultado final y botón de detener. */
export function useJob<T = unknown>() {
  const [job, setJob] = useState<Job<T> | null>(null);
  const [activo, setActivo] = useState(false);
  const jobId = useRef<string | null>(null);

  const seguir = useCallback(async (id: string): Promise<Job<T>> => {
    jobId.current = id;
    setActivo(true);
    try {
      const j = await esperarJob<T>(id, (tick) => setJob(tick));
      setJob(j);
      return j;
    } catch (e) {
      const j = fallo<T>((e as Error).message);
      setJob(j);
      return j;
    } finally {
      setActivo(false);
      jobId.current = null;
    }
  }, []);

  const lanzar = useCallback(async (fn: () => Promise<{ job_id: string }>): Promise<Job<T>> => {
    setActivo(true);
    setJob(null);
    try {
      const { job_id } = await fn();
      return await seguir(job_id);
    } catch (e) {
      const j = fallo<T>((e as Error).message);
      setJob(j);
      setActivo(false);
      return j;
    }
  }, [seguir]);

  const detener = useCallback(async () => { if (jobId.current) await api.detenerJob(jobId.current); }, []);

  return { job, activo, lanzar, seguir, detener };
}
