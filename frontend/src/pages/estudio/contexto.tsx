/* Pestaña Contexto del informe: introducción y resumen ejecutivo (Markdown con vista previa),
   evaluación global y redacción con el modelo (job con progreso). */
import { useCallback, useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

import { api } from "@/api";
import { Markdown, Progreso, ResultBox, useConfirmar, useNotificar } from "@/components/ui";
import { useJob } from "@/hooks/useJob";

import type { PropsPestana } from "./estudio";

const ESCALA = ["Deficiente", "Insuficiente", "Mejorable", "Razonable", "Adecuado"];
const SECCIONES: [string, string][] = [["introduccion", "Introducción"], ["resumen", "Resumen ejecutivo"]];
type Guardado = "limpio" | "sucio" | "guardando" | "guardado";

const Editor = ({ id, titulo, valor, onChange, filas }: { id: string; titulo: string; valor: string; onChange: (v: string) => void; filas: number }) => {
  const [vista, setVista] = useState<"editar" | "vista">("editar");
  return (
    <section className="doc-section">
      <div className="section-label section-label--muted">{titulo}
        <span className="row" style={{ gap: 16 }}>
          <button type="button" className={`tab-item ${vista === "editar" ? "active" : ""}`} style={{ paddingBottom: 0 }} onClick={() => setVista("editar")}>Editar</button>
          <button type="button" className={`tab-item ${vista === "vista" ? "active" : ""}`} style={{ paddingBottom: 0 }} onClick={() => setVista("vista")}>Vista previa</button>
        </span></div>
      {vista === "editar"
        ? <textarea id={id} className="textarea-doc" rows={filas} value={valor} onChange={(e) => onChange(e.target.value)} aria-label={titulo} />
        : <div className="executive-summary-box"><Markdown texto={valor || "_(vacío)_"} /></div>}
    </section>
  );
};

export const Contexto = ({ refExp, exp, recargar }: PropsPestana) => {
  const notificar = useNotificar();
  const confirmar = useConfirmar();
  const job = useJob();
  const [intro, setIntro] = useState("");
  const [resumen, setResumen] = useState("");
  const [evaluacion, setEvaluacion] = useState("");
  const [guardado, setGuardado] = useState<Guardado>("limpio");
  const [secciones, setSecciones] = useState<string[]>(["introduccion", "resumen"]);
  const [mensaje, setMensaje] = useState<{ texto: string; error: boolean } | null>(null);

  const cargar = useCallback(async () => {
    try {
      const inf = await api.informe(refExp);
      setIntro(inf.apartados.find((a) => a.tipo === "introduccion")?.markdown ?? "");
      setResumen(inf.apartados.find((a) => a.tipo === "resumen")?.markdown.replace(/\n*\*\*Evaluación global:\*\*.*$/s, "").replace(/\n*\*\*Próximos pasos:\*\*.*$/s, "") ?? "");
      setEvaluacion(inf.evaluacion_global);
      setGuardado("limpio");
    } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  }, [refExp, notificar]);
  useEffect(() => { cargar(); }, [cargar]);

  const guardar = useCallback(async () => {
    if (guardado !== "sucio") return;
    setGuardado("guardando");
    try { await api.guardarInforme(refExp, { introduccion: intro, resumen_ejecutivo: resumen, evaluacion_global: evaluacion }); setGuardado("guardado"); await recargar(); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); setGuardado("sucio"); }
  }, [guardado, refExp, intro, resumen, evaluacion, recargar, notificar]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); guardar(); } };
    window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h);
  }, [guardar]);

  const hayTexto = !!(intro || resumen);
  const redactar = async () => {
    if (hayTexto && !(await confirmar({ titulo: "Redactar de nuevo con el modelo", accion: "Redactar", cuerpo: `Se regenerará: ${secciones.map((s) => SECCIONES.find(([k]) => k === s)?.[1]).join(" y ")}. El texto actual queda en el historial.` }))) return;
    setMensaje(null);
    const j = await job.lanzar(() => api.redactarContexto(refExp, { forzar: true, secciones }));
    setMensaje({ texto: j.mensaje, error: j.estado !== "ok" });
    if (j.estado === "ok") { await cargar(); await recargar(); }
  };
  const marcar = (v: string) => setSecciones((x) => (x.includes(v) ? x.filter((y) => y !== v) : [...x, v]));
  const textoGuardado = { limpio: "", sucio: "Sin guardar", guardando: "Guardando…", guardado: `Guardado ${new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}` }[guardado];

  return (
    <div>
      <h2 className="section-header-sm">Introducción y resumen ejecutivo
        <span className="row">
          <span className="small muted" aria-live="polite">{textoGuardado}</span>
          <button className="btn btn-secondary" onClick={guardar} disabled={guardado !== "sucio"}>Guardar</button>
          <button className="btn btn-primary" onClick={redactar} disabled={job.activo || !exp.papeles.length}>
            {job.activo ? <><span className="spinner" /> Redactando…</> : <><Sparkles strokeWidth={1.5} /> {hayTexto ? "Redactar de nuevo" : "Redactar con el modelo"}</>}</button>
        </span></h2>
      <p className="small muted" style={{ marginBottom: 24 }}>El modelo redacta la introducción y el resumen ejecutivo a partir del contexto y del papel de trabajo; el auditor los deja a su gusto. Ctrl/Cmd+S guarda.</p>
      {!exp.papeles.length && <div className="empty" style={{ marginBottom: 24 }}>Sube el papel de trabajo en Entrada para poder redactar la introducción y el resumen.</div>}
      {hayTexto && (
        <div className="config-group"><span className="config-group-title">Qué regenerar</span>
          <div className="row">{SECCIONES.map(([k, n]) => (
            <button type="button" key={k} className={`option-card ${secciones.includes(k) ? "selected" : ""}`} style={{ width: "auto" }} onClick={() => marcar(k)}><span className="option-name">{n}</span><div className="check-box" /></button>))}</div>
        </div>)}
      {job.activo && <Progreso texto={job.job?.progreso || "Redactando con el modelo…"} pct={job.job?.progreso_pct} partes={job.job?.progreso_partes} onDetener={job.detener} />}
      {mensaje && <div style={{ marginBottom: 24 }}><ResultBox mensaje={mensaje.texto} error={mensaje.error} onClose={() => setMensaje(null)} /></div>}
      <Editor id="intro" titulo="Introducción" valor={intro} onChange={(v) => { setIntro(v); setGuardado("sucio"); }} filas={18} />
      <Editor id="resumen" titulo="Resumen ejecutivo" valor={resumen} onChange={(v) => { setResumen(v); setGuardado("sucio"); }} filas={14} />
      <section className="doc-section">
        <div className="section-label section-label--muted">Evaluación global</div>
        <div className="tone-selector">{ESCALA.map((n) => <button type="button" key={n} className={`tone-btn ${evaluacion === n ? "selected" : ""}`} onClick={() => { setEvaluacion(n); setGuardado("sucio"); }}>{n}</button>)}</div>
      </section>
    </div>
  );
};
