/* Componentes compartidos (mismo BEM y tokens que la plantilla corporativa). */
import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { esperarJob } from "@/api";
import type { Job, Riesgo, Estado } from "@/api";

// ---------------------------------------------------------------- notificaciones
type Noti = { texto: string; error?: boolean } | null;
const NotiCtx = React.createContext<(n: Noti) => void>(() => {});
export const useNotificar = () => React.useContext(NotiCtx);

export const NotificacionesProvider = ({ children }: { children: React.ReactNode }) => {
  const [noti, setNoti] = useState<Noti>(null);
  const timer = useRef<number>();
  const notificar = (n: Noti) => {
    setNoti(n);
    window.clearTimeout(timer.current);
    if (n) timer.current = window.setTimeout(() => setNoti(null), n.error ? 6000 : 3000);
  };
  return (
    <NotiCtx.Provider value={notificar}>
      {children}
      {noti && <div className={`notification ${noti.error ? "notification--error" : ""}`}>{noti.texto}</div>}
    </NotiCtx.Provider>
  );
};

// ---------------------------------------------------------------- badges
const claseRiesgo = (r: Riesgo) => ({ "Crítico": "critico", Alto: "alto", Medio: "medio", Bajo: "bajo", "": "" }[r] ?? "");
export const RiskBadge = ({ nivel, propuesto }: { nivel: Riesgo; propuesto?: boolean }) => (
  <span className={`risk risk--${claseRiesgo(nivel)}`}>
    <span className="risk__dot" />
    {nivel ? `Riesgo ${nivel}` : "Riesgo N/D"}
    {propuesto && nivel && <span className="risk__propuesto">propuesto por el modelo</span>}
  </span>
);

const SIGUIENTE: Record<Estado, Estado> = { propuesta: "aprobada", aprobada: "descartada", descartada: "propuesta" };
export const StateChip = ({ estado, onChange }: { estado: Estado; onChange?: (e: Estado) => void }) => (
  <button type="button" className={`state state--${estado}`} onClick={() => onChange?.(SIGUIENTE[estado])} title="Clic para cambiar el estado" aria-label={`Estado ${estado}`}>
    {estado}
  </button>
);

// ---------------------------------------------------------------- trabajos del modelo
export interface JobResultado<T = unknown> { estado: "ok" | "error"; mensaje: string; resultado: T | null }

export const JobButton = <T,>({ etiqueta, lanzar, onFin, primario, pequeno, confirmar, disabled }: {
  etiqueta: string; lanzar: () => Promise<{ job_id: string }>; onFin?: (j: JobResultado<T>) => void;
  primario?: boolean; pequeno?: boolean; confirmar?: string; disabled?: boolean;
}) => {
  const [enCurso, setEnCurso] = useState(false);
  const notificar = useNotificar();
  const click = async () => {
    if (confirmar && !window.confirm(confirmar)) return;
    setEnCurso(true);
    try {
      const { job_id } = await lanzar();
      const j = (await esperarJob<T>(job_id)) as Job<T>;
      onFin?.({ estado: j.estado === "ok" ? "ok" : "error", mensaje: j.mensaje, resultado: j.resultado });
      if (j.estado !== "ok") notificar({ texto: j.mensaje, error: true });
    } catch (err) {
      notificar({ texto: String((err as Error).message ?? err), error: true });
      onFin?.({ estado: "error", mensaje: String((err as Error).message ?? err), resultado: null });
    } finally {
      setEnCurso(false);
    }
  };
  return (
    <button type="button" className={`btn ${primario ? "btn--primary" : ""} ${pequeno ? "btn--small" : ""}`} onClick={click} disabled={enCurso || disabled} aria-label={etiqueta}>
      {enCurso ? <><span className="spinner" />Trabajando con el modelo…</> : etiqueta}
    </button>
  );
};

export const JobResult = ({ r, onClose }: { r: JobResultado | null; onClose: () => void }) =>
  r ? (
    <div className={`job-result ${r.estado === "error" ? "job-result--error" : ""}`}>
      <button className="job-result__close" onClick={onClose} aria-label="Cerrar">×</button>
      {r.mensaje}
    </div>
  ) : null;

// ---------------------------------------------------------------- markdown y diff
export const Markdown = ({ texto }: { texto: string }) => (
  <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{texto}</ReactMarkdown></div>
);

export const MarkdownEditor = ({ valor, onChange, filas = 14, mono }: { valor: string; onChange: (v: string) => void; filas?: number; mono?: boolean }) => {
  const [vista, setVista] = useState<"editar" | "vista">("editar");
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--ids-size-50)" }}>
      <div style={{ display: "flex", gap: "var(--ids-size-50)" }}>
        <button className={`pill ${vista === "editar" ? "pill--active" : ""}`} onClick={() => setVista("editar")}>Editar</button>
        <button className={`pill ${vista === "vista" ? "pill--active" : ""}`} onClick={() => setVista("vista")}>Vista previa</button>
      </div>
      {vista === "editar"
        ? <textarea className={`textarea ${mono ? "textarea--mono" : ""}`} rows={filas} value={valor} onChange={(e) => onChange(e.target.value)} />
        : <div className="panel"><Markdown texto={valor || "_(vacío)_"} /></div>}
    </div>
  );
};

export const DiffView = ({ diff }: { diff: string }) => {
  const [abierto, setAbierto] = useState(true);
  if (!diff) return <span className="detail">Sin diferencias.</span>;
  return (
    <div>
      <button className="btn btn--ghost btn--small" onClick={() => setAbierto(!abierto)}>{abierto ? "Ocultar diff" : "Ver diff"}</button>
      {abierto && (
        <div className="diff">
          {diff.split("\n").map((l, i) => {
            const cls = l.startsWith("+") && !l.startsWith("+++") ? "diff__add" : l.startsWith("-") && !l.startsWith("---") ? "diff__del" : l.startsWith("@@") || l.startsWith("+++") || l.startsWith("---") ? "diff__meta" : "";
            return <span key={i} className={cls}>{l}{"\n"}</span>;
          })}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------- drop zone
export const Dropzone = ({ titulo, descripcion, formatos, onFicheros, multiple = true }: {
  titulo: string; descripcion: string; formatos: string; onFicheros: (f: File[]) => void; multiple?: boolean;
}) => {
  const [activo, setActivo] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className={`drop-zone ${activo ? "drop-zone--active" : ""}`} onClick={() => input.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setActivo(true); }} onDragLeave={() => setActivo(false)}
      onDrop={(e) => { e.preventDefault(); setActivo(false); onFicheros(Array.from(e.dataTransfer.files)); }}
      role="button" aria-label={titulo}>
      <span className="drop-zone__title">{titulo}</span>
      <span className="drop-zone__desc">{descripcion}</span>
      <span className="drop-zone__cta">Arrastra aquí o haz clic para seleccionar · {formatos}</span>
      <input ref={input} type="file" multiple={multiple} accept={formatos.replace(/\s/g, "").split(",").map((x) => (x.startsWith(".") ? x : "." + x)).join(",")} style={{ display: "none" }}
        onChange={(e) => { onFicheros(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
    </div>
  );
};

// ---------------------------------------------------------------- modal y tarjeta-diapositiva
export const Modal = ({ titulo, children, onClose, acciones }: { titulo: string; children: React.ReactNode; onClose: () => void; acciones?: React.ReactNode }) => {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  return (
    <div className="modal__overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={titulo}>
        <h2 className="modal__title">{titulo}</h2>
        {children}
        {acciones && <div className="modal__actions">{acciones}</div>}
      </div>
    </div>
  );
};

export const SlideCard = ({ kicker, titulo, nivel, children, tools }: { kicker: string; titulo: string; nivel?: Riesgo; children: React.ReactNode; tools?: React.ReactNode }) => (
  <div className={`slide ${nivel ? `slide--${claseRiesgo(nivel)}` : ""}`}>
    <div className="slide__band">{nivel ? `Riesgo ${nivel}` : ""}</div>
    <div className="slide__body">
      <div className="slide__header">
        <div><div className="slide__kicker">{kicker}</div><h3 className="slide__title">{titulo}</h3></div>
        {tools && <div className="slide__tools">{tools}</div>}
      </div>
      {children}
    </div>
  </div>
);

export const Guardado = ({ estado }: { estado: "limpio" | "sucio" | "guardando" | "guardado" }) => {
  const textos = { limpio: "", sucio: "Sin guardar", guardando: "Guardando…", guardado: `Guardado ${new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}` };
  return <span className="detail" aria-live="polite">{textos[estado]}</span>;
};
