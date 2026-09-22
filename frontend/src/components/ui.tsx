/* Componentes compartidos (kit del front homogéneo, docs/GUIA_FRONT_HOMOGENEO.md § 4). */
import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronUp, UploadCloud, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { EstadoConclusion, Riesgo } from "@/api";
import { ESTADO_CONCLUSION, planClase, riesgoClase, severidadClase } from "@/lib/formato";

// ---------------------------------------------------------------- marca y loader
/** Logotipo corporativo del CDN de AMIGA; si no carga (fuera de la red), marca tipográfica. */
export const Logo = ({ onClick, grande }: { onClick?: () => void; grande?: boolean }) => {
  const [fallo, setFallo] = useState(false);
  return (
    <button type="button" className="logo" onClick={onClick} aria-label="Inditex" disabled={!onClick}>
      {fallo
        ? <span className="brand-text">INDITEX</span>
        : <img className={`brand-logo ${grande ? "brand-logo--grande" : ""}`} src="https://amgassets.inditex.com/amigaweb/logos/inditex.svg" alt="Inditex" onError={() => setFallo(true)} />}
    </button>
  );
};

export const Loader = ({ size = 40 }: { size?: number }) => (
  <span className="loader" style={{ width: size, height: size }} role="status" aria-label="Cargando"><span className="loader__progress" style={{ width: size, height: size }} /></span>
);

export const Spinner = () => <span className="spinner" aria-hidden="true" />;

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
    if (n) timer.current = window.setTimeout(() => setNoti(null), n.error ? 6000 : 3500);
  };
  return (
    <NotiCtx.Provider value={notificar}>
      {children}
      <AnimatePresence>
        {noti && (
          <motion.div key={noti.texto} className={`toast ${noti.error ? "toast--error" : ""}`} role="status"
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} transition={{ duration: 0.2, ease: "easeOut" }}>
            {noti.texto}
          </motion.div>
        )}
      </AnimatePresence>
    </NotiCtx.Provider>
  );
};

// ---------------------------------------------------------------- confirmaciones (modal propio)
type Confirmacion = { titulo: string; cuerpo?: React.ReactNode; accion?: string; peligro?: boolean };
const ConfirmCtx = React.createContext<(c: Confirmacion) => Promise<boolean>>(() => Promise.resolve(false));
export const useConfirmar = () => React.useContext(ConfirmCtx);

export const ConfirmProvider = ({ children }: { children: React.ReactNode }) => {
  const [conf, setConf] = useState<(Confirmacion & { resolver: (v: boolean) => void }) | null>(null);
  const confirmar = (c: Confirmacion) => new Promise<boolean>((resolver) => setConf({ ...c, resolver }));
  const cerrar = (v: boolean) => { conf?.resolver(v); setConf(null); };
  return (
    <ConfirmCtx.Provider value={confirmar}>
      {children}
      {conf && (
        <Modal titulo={conf.titulo} onClose={() => cerrar(false)} acciones={
          <>
            <button className="btn btn-secondary" onClick={() => cerrar(false)}>Cancelar</button>
            <button className={`btn ${conf.peligro ? "btn-danger" : "btn-primary"}`} onClick={() => cerrar(true)} autoFocus>{conf.accion ?? "Continuar"}</button>
          </>}>
          {typeof conf.cuerpo === "string" ? <p style={{ whiteSpace: "pre-wrap" }}>{conf.cuerpo}</p> : conf.cuerpo}
        </Modal>
      )}
    </ConfirmCtx.Provider>
  );
};

/** Diálogo genérico (Escape cierra); `ancho` para contenido extenso (trazas, editor Markdown). */
export const Modal = ({ titulo, children, onClose, acciones, ancho }: { titulo: string; children: React.ReactNode; onClose: () => void; acciones?: React.ReactNode; ancho?: boolean }) => {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  return (
    <motion.div className="modal-overlay" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.15 }}>
      <motion.div className={`modal ${ancho ? "modal--ancho" : ""}`} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={titulo}
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
        <div className="modal__head"><h3>{titulo}</h3><button className="icon-btn" onClick={onClose} aria-label="Cerrar"><X size={18} strokeWidth={1.5} /></button></div>
        {children}
        {acciones && <div className="modal-actions">{acciones}</div>}
      </motion.div>
    </motion.div>
  );
};

// ---------------------------------------------------------------- etiquetas (mapas en lib/formato.ts)
export const EstadoTag = ({ estado }: { estado: EstadoConclusion }) => {
  const [cls, txt] = ESTADO_CONCLUSION[estado] ?? ["tag-neutral", estado];
  return <span className={`status-tag ${cls}`}>{txt}</span>;
};
/** Nivel de riesgo; con `propuesto`, el modelo lo propuso sin evidencia en el papel de trabajo (lo quita «Aprobar»). */
export const RiesgoTag = ({ nivel, propuesto }: { nivel: Riesgo | string; propuesto?: boolean }) =>
  nivel ? <span className={`tag ${riesgoClase(nivel)}`} title={propuesto ? "Propuesto por el modelo, sin evidencia en el papel de trabajo" : undefined}>Riesgo {nivel}{propuesto ? " · propuesto" : ""}</span> : <span className="tag tag-neutral">Riesgo N/D</span>;
export const SeveridadTag = ({ severidad }: { severidad: "error" | "aviso" }) => <span className={`tag ${severidadClase(severidad)}`}>{severidad}</span>;
/** Estado de una línea del plan de cambios (aplicado / no aplicado / CONFLICTO). */
export const PlanTag = ({ estado }: { estado: string }) => <span className={`tag ${planClase(estado)}`}>{estado}</span>;

// ---------------------------------------------------------------- markdown
export const Markdown = ({ texto }: { texto: string }) => (
  <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{texto}</ReactMarkdown></div>
);

// ---------------------------------------------------------------- diff unificado (plegable)
export const DiffView = ({ diff, abiertoInicial = true }: { diff: string; abiertoInicial?: boolean }) => {
  const [abierto, setAbierto] = useState(abiertoInicial);
  if (!diff.trim()) return <p className="small muted">Sin diferencias.</p>;
  const clase = (l: string) => l.startsWith("+") && !l.startsWith("+++") ? "diff-view__add"
    : l.startsWith("-") && !l.startsWith("---") ? "diff-view__del"
    : l.startsWith("@@") || l.startsWith("+++") || l.startsWith("---") ? "diff-view__meta" : "";
  return (
    <div>
      <button type="button" className="btn btn-ghost btn-ghost--inline small" onClick={() => setAbierto(!abierto)} aria-expanded={abierto}>
        {abierto ? <ChevronUp size={14} strokeWidth={1.5} /> : <ChevronDown size={14} strokeWidth={1.5} />}{abierto ? "Ocultar diff" : "Ver diff"}</button>
      {abierto && <pre className="diff-view">{diff.split("\n").map((l, i) => <span key={i} className={clase(l)}>{l}{"\n"}</span>)}</pre>}
    </div>
  );
};

// ---------------------------------------------------------------- tarjeta-diapositiva (banda vertical con el nombre del apartado, color por riesgo)
export const SlideCard = ({ banda, nivel, kicker, titulo, tools, children }: { banda: string; nivel?: Riesgo | string; kicker?: string; titulo?: string; tools?: React.ReactNode; children: React.ReactNode }) => {
  const mod = nivel ? ({ crítico: "critico", critico: "critico", alto: "alto", medio: "medio", bajo: "bajo" } as Record<string, string>)[nivel.toLowerCase()] ?? "neutro" : "neutro";
  return (
    <section className={`slide-card slide-card--${mod}`}>
      <div className="slide-card__band" aria-hidden="true">{banda}</div>
      <div className="slide-card__body">
        {(kicker || titulo || tools) && (
          <div className="slide-card__header">
            <div>{kicker && <div className="slide-card__kicker">{kicker}</div>}{titulo && <h2 className="slide-card__title">{titulo}</h2>}</div>
            {tools && <div className="row">{tools}</div>}
          </div>)}
        {children}
      </div>
    </section>
  );
};

// ---------------------------------------------------------------- resultado de un job
export const ResultBox = ({ mensaje, error, onClose }: { mensaje: string; error?: boolean; onClose?: () => void }) => (
  <div className={`result-box ${error ? "error" : ""}`}>
    {onClose && <button className="icon-btn result-box__close" onClick={onClose} aria-label="Cerrar"><X size={14} strokeWidth={1.5} /></button>}
    {mensaje}
  </div>
);

// ---------------------------------------------------------------- drop zone (un fichero)
export const Dropzone = ({ titulo, descripcion, accept, onFichero, onFicheros }: { titulo: string; descripcion: React.ReactNode; accept: string; onFichero?: (f: File) => void; onFicheros?: (f: File[]) => void }) => {
  const entregar = (lista: FileList | null) => { const fs = Array.from(lista ?? []); if (!fs.length) return; if (onFicheros) onFicheros(fs); else onFichero?.(fs[0]); };
  const [activo, setActivo] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className={`file-uploader ${activo ? "over" : ""}`} onClick={() => input.current?.click()} tabIndex={0} role="button" aria-label={titulo}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.current?.click(); } }}
      onDragOver={(e) => { e.preventDefault(); setActivo(true); }} onDragLeave={() => setActivo(false)}
      onDrop={(e) => { e.preventDefault(); setActivo(false); entregar(e.dataTransfer.files); }}>
      <UploadCloud size={32} strokeWidth={1.5} />
      <div className="uploader-title">{titulo}</div>
      <div className="uploader-desc">{descripcion}</div>
      <input ref={input} type="file" accept={accept} multiple={!!onFicheros} hidden onChange={(e) => { entregar(e.target.files); e.target.value = ""; }} />
    </div>
  );
};

// ---------------------------------------------------------------- interruptor y menú flotante
export const Switch = ({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) => (
  <label className="switch"><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} aria-label={label} /><span className="slider" /></label>
);

export const MenuFlotante = ({ etiqueta, primario, children }: { etiqueta: React.ReactNode; primario?: boolean; children: React.ReactNode }) => {
  const [abierto, setAbierto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setAbierto(false); };
    document.addEventListener("click", fuera);
    return () => document.removeEventListener("click", fuera);
  }, [abierto]);
  return (
    <div className={`menu-flotante ${abierto ? "open" : ""}`} ref={ref}>
      <button className={`btn ${primario ? "btn-primary" : "btn-ghost"}`} onClick={() => setAbierto(!abierto)} aria-haspopup="menu" aria-expanded={abierto}>{etiqueta}<ChevronDown size={14} strokeWidth={1.5} /></button>
      <div className="menu-flotante__lista" role="menu" onClick={() => setAbierto(false)}>{children}</div>
    </div>
  );
};

/** Progreso de un trabajo largo (transcripción por partes, modelo). */
export const Progreso = ({ texto, pct, partes, onDetener }: { texto?: string; pct?: number | null; partes?: string[] | null; onDetener?: () => void }) => (
  <div className="progress-panel">
    <div className="section-label" style={{ marginBottom: 8 }}>Procesamiento IA <span className="badge-status">{pct ?? 0} %</span></div>
    <p className="muted">{texto || "Preparando…"}</p>
    <div className="progress-bar"><div style={{ width: `${pct ?? 0}%` }} /></div>
    {partes && partes.length > 1 && <div className="progress-parts">{partes.map((p, i) => <span key={i} className={p} title={p} />)}</div>}
    {onDetener && <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
      <button className="btn btn-secondary" onClick={onDetener}>Detener</button>
      <a className="btn btn-ghost" href="/">Volver al inicio (sigue en segundo plano)</a>
    </div>}
  </div>
);
