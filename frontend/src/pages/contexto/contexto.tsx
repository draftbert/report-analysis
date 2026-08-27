import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "@/api";
import { Guardado, JobButton, JobResult, MarkdownEditor, useNotificar } from "@/components/ui";
import type { JobResultado } from "@/components/ui";
import { useEstado } from "@/layout/layout";

const ESCALA = ["Deficiente", "Insuficiente", "Mejorable", "Razonable", "Adecuado"];

export const Contexto = () => {
  const { ref = "" } = useParams();
  const { estado, recargar } = useEstado();
  const notificar = useNotificar();
  const [intro, setIntro] = useState("");
  const [resumen, setResumen] = useState("");
  const [evaluacion, setEvaluacion] = useState("");
  const [guardado, setGuardado] = useState<"limpio" | "sucio" | "guardando" | "guardado">("limpio");
  const [resultado, setResultado] = useState<JobResultado | null>(null);
  const [secciones, setSecciones] = useState<string[]>(["introduccion", "resumen"]);

  const cargar = async () => {
    const inf = await api.informe(ref);
    setIntro(inf.apartados.find((a) => a.tipo === "introduccion")?.markdown ?? "");
    setResumen(inf.apartados.find((a) => a.tipo === "resumen")?.markdown.replace(/\n*\*\*Evaluación global:\*\*.*$/s, "").replace(/\n*\*\*Próximos pasos:\*\*.*$/s, "") ?? "");
    setEvaluacion(inf.evaluacion_global);
    setGuardado("limpio");
  };
  useEffect(() => { cargar().catch((e) => notificar({ texto: e.message, error: true })); }, [ref]);

  const guardar = async () => {
    setGuardado("guardando");
    try { await api.guardarInforme(ref, { introduccion: intro, resumen_ejecutivo: resumen, evaluacion_global: evaluacion }); setGuardado("guardado"); recargar(); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); setGuardado("sucio"); }
  };
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); guardar(); } };
    window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h);
  });
  const hayTexto = !!(intro || resumen);
  const toggle = (s: string) => setSecciones((x) => (x.includes(s) ? x.filter((y) => y !== s) : [...x, s]));

  return (
    <div className="page">
      <div className="page__header">
        <div><h2 className="page__title">Contexto del informe</h2><p className="page__subtitle">Introducción y resumen ejecutivo. El modelo los redacta a partir del contexto y del papel de trabajo; tú los dejas a tu gusto.</p></div>
        <div className="page__actions">
          <Guardado estado={guardado} />
          <button className="btn" onClick={guardar} disabled={guardado !== "sucio"}>Guardar</button>
          <JobButton primario etiqueta={hayTexto ? "Redactar de nuevo con el modelo" : "Redactar con el modelo"}
            confirmar={hayTexto ? `Se regenerarán: ${secciones.join(" y ")}. El texto actual se guarda en historial. ¿Continuar?` : undefined}
            lanzar={() => api.redactarContexto(ref, { forzar: true, secciones })}
            onFin={(r) => { setResultado(r); if (r.estado === "ok") { cargar(); recargar(); } }} />
        </div>
      </div>
      {hayTexto && (
        <div className="row"><span className="label">Regenerar</span>
          {["introduccion", "resumen"].map((s) => <button key={s} className={`pill ${secciones.includes(s) ? "pill--active" : ""}`} onClick={() => toggle(s)}>{s === "introduccion" ? "Introducción" : "Resumen ejecutivo"}</button>)}
        </div>
      )}
      <JobResult r={resultado} onClose={() => setResultado(null)} />
      {!estado?.papeles.length && <div className="empty">Sube el papel de trabajo en Entrada para poder redactar la introducción y el resumen.</div>}
      <div className="grid-2">
        <div className="stack"><span className="section-title">Introducción</span><MarkdownEditor valor={intro} onChange={(v) => { setIntro(v); setGuardado("sucio"); }} filas={22} /></div>
        <div className="stack">
          <span className="section-title">Resumen ejecutivo</span>
          <MarkdownEditor valor={resumen} onChange={(v) => { setResumen(v); setGuardado("sucio"); }} filas={16} />
          <div className="field"><span className="field__label">Evaluación global</span>
            <div className="row">{ESCALA.map((n) => <button key={n} className={`pill ${evaluacion === n ? "pill--active" : ""}`} onClick={() => { setEvaluacion(n); setGuardado("sucio"); }}>{n}</button>)}</div>
          </div>
        </div>
      </div>
    </div>
  );
};
