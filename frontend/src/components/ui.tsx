/* Componentes compartidos (mismo BEM y tokens que la plantilla corporativa). */
import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, ChevronUp, Sparkles, UploadCloud, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { esperarJob } from "@/api";
import type { Job, Riesgo, Estado } from "@/api";

// ---------------------------------------------------------------- marca y loader
/** Marca tipográfica (el logotipo real lo aporta `Logo` de Sewing en el entorno corporativo). */
export const Logo = ({ onClick }: { onClick?: () => void }) => (
  <button type="button" className="logo" onClick={onClick} aria-label="Inditex" disabled={!onClick}>
    <svg width="112" height="14" viewBox="0 0 112 14" aria-hidden="true"><text x="0" y="12" fontFamily="Helvetica Neue, Helvetica, Arial, sans-serif" fontSize="14" fontWeight="500" letterSpacing="4.5" fill="currentColor">INDITEX</text></svg>
  </button>
);

/** Loader circular de Sewing (mismo trazo y easing que el spa-loader de la plantilla). */
export const Loader = ({ size = 40 }: { size?: number }) => (
  <span className="loader" style={{ width: size, height: size }} role="status" aria-label="Cargando"><span className="loader__progress" style={{ width: size, height: size }} /></span>
);

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
      <AnimatePresence>
        {noti && (
          <motion.div key={noti.texto} className={`notification ${noti.error ? "notification--error" : ""}`} role="status"
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2, ease: "easeOut" }}>
            {noti.texto}
          </motion.div>
        )}
      </AnimatePresence>
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
export const StateChip = ({ estado, onChange }: { estado: Estado; onChange?: (e: Estado) => void }) =>
  onChange ? (
    <button type="button" className={`state state--${estado}`} onClick={() => onChange(SIGUIENTE[estado])} title="Clic para cambiar el estado" aria-label={`Estado ${estado}`}>{estado}</button>
  ) : (
    <span className={`state state--${estado} state--static`} aria-label={`Estado ${estado}`}>{estado}</span>
  );

// ---------------------------------------------------------------- trabajos del modelo
export interface JobResultado<T = unknown> { estado: "ok" | "error"; mensaje: string; resultado: T | null }

export const JobButton = <T,>({ etiqueta, lanzar, onFin, primario, pequeno, confirmar, disabled }: {
  etiqueta: string; lanzar: () => Promise<{ job_id: string }>; onFin?: (j: JobResultado<T>) => void;
  primario?: boolean; pequeno?: boolean; confirmar?: string; disabled?: boolean;
}) => {
  const [fase, setFase] = useState<"idle" | "curso" | "hecho">("idle");
  const notificar = useNotificar();
  const click = async () => {
    if (confirmar && !window.confirm(confirmar)) return;
    setFase("curso");
    try {
      const { job_id } = await lanzar();
      const j = (await esperarJob<T>(job_id)) as Job<T>;
      onFin?.({ estado: j.estado === "ok" ? "ok" : "error", mensaje: j.mensaje, resultado: j.resultado });
      if (j.estado !== "ok") notificar({ texto: j.mensaje, error: true });
      setFase(j.estado === "ok" ? "hecho" : "idle");
      if (j.estado === "ok") window.setTimeout(() => setFase("idle"), 1400);
    } catch (err) {
      notificar({ texto: String((err as Error).message ?? err), error: true });
      onFin?.({ estado: "error", mensaje: String((err as Error).message ?? err), resultado: null });
      setFase("idle");
    }
  };
  return (
    <button type="button" className={`btn btn--model ${primario ? "btn--primary" : ""} ${pequeno ? "btn--small" : ""} ${fase === "curso" ? "btn--busy" : ""}`} onClick={click} disabled={fase !== "idle" || disabled} aria-label={etiqueta}>
      {fase === "curso" ? <><span className="spinner" />Trabajando con el modelo…</>
        : fase === "hecho" ? <><Check size={14} strokeWidth={2} />Hecho</>
        : <><Sparkles size={14} strokeWidth={1.5} />{etiqueta}</>}
    </button>
  );
};

export const JobResult = ({ r, onClose }: { r: JobResultado | null; onClose: () => void }) =>
  (
    <AnimatePresence>
      {r && (
        <motion.div className={`job-result ${r.estado === "error" ? "job-result--error" : ""}`} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.2 }}>
          <button className="job-result__close" onClick={onClose} aria-label="Cerrar"><X size={14} strokeWidth={1.5} /></button>
          {r.mensaje}
        </motion.div>
      )}
    </AnimatePresence>
  );

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
      <button className="btn btn--ghost btn--small" onClick={() => setAbierto(!abierto)}>{abierto ? <ChevronUp size={14} strokeWidth={1.5} /> : <ChevronDown size={14} strokeWidth={1.5} />}{abierto ? "Ocultar diff" : "Ver diff"}</button>
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
      <span className="drop-zone__title"><UploadCloud size={18} strokeWidth={1.5} />{titulo}</span>
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
    <motion.div className="modal__overlay" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.15 }}>
      <motion.div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={titulo} initial={{ opacity: 0, y: 12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}>
        <div className="modal__head"><h2 className="modal__title">{titulo}</h2><button className="layout__icon-btn" onClick={onClose} aria-label="Cerrar"><X size={18} strokeWidth={1.5} /></button></div>
        {children}
        {acciones && <div className="modal__actions">{acciones}</div>}
      </motion.div>
    </motion.div>
  );
};

export const SlideCard = ({ kicker, titulo, nivel, children, tools }: { kicker: string; titulo: string; nivel?: Riesgo; children: React.ReactNode; tools?: React.ReactNode }) => (
  <motion.div className={`slide ${nivel ? `slide--${claseRiesgo(nivel)}` : ""}`} initial={{ opacity: 0, y: 8 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-40px" }} transition={{ duration: 0.25 }}>
    <div className="slide__band">{nivel ? `Riesgo ${nivel}` : ""}</div>
    <div className="slide__body">
      <div className="slide__header">
        <div><div className="slide__kicker">{kicker}</div><h3 className="slide__title">{titulo}</h3></div>
        {tools && <div className="slide__tools">{tools}</div>}
      </div>
      {children}
    </div>
  </motion.div>
);

export const Guardado = ({ estado }: { estado: "limpio" | "sucio" | "guardando" | "guardado" }) => {
  const textos = { limpio: "", sucio: "Sin guardar", guardando: "Guardando…", guardado: `Guardado ${new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}` };
  return <span className="detail" aria-live="polite">{textos[estado]}</span>;
};
