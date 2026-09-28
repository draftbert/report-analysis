/* Componentes compartidos (kit del front homogéneo, docs/GUIA_FRONT_HOMOGENEO.md § 4). */
import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, ChevronDown, ChevronUp, UploadCloud, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { EstadoApartadoDiff, EstadoConclusion, LineaDiff, Riesgo } from "@/api";
import { ESTADO_CAMBIO, ESTADO_CONCLUSION, planClase, riesgoClase, severidadClase } from "@/lib/formato";

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

// ---------------------------------------------------------------- markdown (con resaltado opcional de fragmentos)
/** Fragmento a resaltar dentro del texto pintado (p. ej. un hallazgo de la revisión de vocabulario). */
export interface Resalte { texto: string; clase: string; titulo?: string }

/** Parte un texto en trozos normales y <mark> para cada aparición de los fragmentos (el más largo gana si se solapan). */
const partir = (texto: string, resaltes: Resalte[]): React.ReactNode => {
  const tramos: { ini: number; fin: number; r: Resalte }[] = [];
  for (const r of resaltes) {
    if (!r.texto) continue;
    for (let i = texto.indexOf(r.texto); i >= 0; i = texto.indexOf(r.texto, i + r.texto.length)) tramos.push({ ini: i, fin: i + r.texto.length, r });
  }
  if (!tramos.length) return texto;
  tramos.sort((a, b) => a.ini - b.ini || b.fin - a.fin);
  const partes: React.ReactNode[] = [];
  let pos = 0;
  for (const t of tramos) {
    if (t.ini < pos) continue;
    if (t.ini > pos) partes.push(texto.slice(pos, t.ini));
    partes.push(<mark key={t.ini} className={t.r.clase} title={t.r.titulo}>{texto.slice(t.ini, t.fin)}</mark>);
    pos = t.fin;
  }
  if (pos < texto.length) partes.push(texto.slice(pos));
  return partes;
};
const marcar = (nodo: React.ReactNode, resaltes: Resalte[]): React.ReactNode =>
  typeof nodo === "string" ? partir(nodo, resaltes)
    : Array.isArray(nodo) ? nodo.map((n, i) => <React.Fragment key={i}>{marcar(n, resaltes)}</React.Fragment>) : nodo;

/** Único renderizador de Markdown. Con `resaltar`, marca esos fragmentos en párrafos, viñetas, celdas y negritas. */
export const Markdown = ({ texto, resaltar }: { texto: string; resaltar?: Resalte[] }) => {
  const componentes = resaltar?.length ? Object.fromEntries((["p", "li", "td", "strong", "em"] as const).map((Etiqueta) =>
    [Etiqueta, ({ children }: { children?: React.ReactNode }) => <Etiqueta>{marcar(children, resaltar)}</Etiqueta>])) : undefined;
  return <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]} components={componentes}>{texto}</ReactMarkdown></div>;
};

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

// ---------------------------------------------------------------- cambios sobre el documento (estilo GitHub)
/** Estado de un apartado comparado (añadido / modificado / eliminado). */
export const CambioTag = ({ estado }: { estado: EstadoApartadoDiff }) => { const [cls, txt] = ESTADO_CAMBIO[estado]; return <span className={`tag ${cls}`}>{txt}</span>; };
/** «+12 −4»: líneas añadidas y eliminadas. */
export const DiffCuenta = ({ nuevas, borradas }: { nuevas: number; borradas: number }) => (
  <span className="diff-cuenta" aria-label={`${nuevas} líneas añadidas, ${borradas} eliminadas`}><span className="diff-cuenta__mas">+{nuevas}</span><span className="diff-cuenta__menos">−{borradas}</span></span>
);

type TramoDiff = { lineas: LineaDiff[]; plegado: boolean };
/** Una fila por párrafo o viñeta: verde lo añadido, rojo lo eliminado y, en las líneas modificadas, las palabras
 *  que cambian más marcadas. Las tiradas largas sin cambios se pliegan dejando `contexto` líneas a cada lado,
 *  salvo con `plegar={false}` (p. ej. para leer el documento entero con los cambios marcados). */
export const DiffDocumento = ({ lineas, contexto = 2, plegar = true }: { lineas: LineaDiff[]; contexto?: number; plegar?: boolean }) => {
  const [abiertos, setAbiertos] = useState<Set<number>>(new Set());
  const tramos: TramoDiff[] = [];
  for (let i = 0; i < lineas.length;) {
    let j = i;
    while (j < lineas.length && lineas[j].tipo === "igual") j++;
    const iguales = lineas.slice(i, j);
    const ini = i === 0 ? 0 : contexto, fin = j === lineas.length ? 0 : contexto;
    if (plegar && iguales.length > ini + fin + 1) {
      if (ini) tramos.push({ lineas: iguales.slice(0, ini), plegado: false });
      tramos.push({ lineas: iguales.slice(ini, iguales.length - fin), plegado: true });
      if (fin) tramos.push({ lineas: iguales.slice(iguales.length - fin), plegado: false });
    } else if (iguales.length) tramos.push({ lineas: iguales, plegado: false });
    let k = j;
    while (k < lineas.length && lineas[k].tipo !== "igual") k++;
    if (k > j) tramos.push({ lineas: lineas.slice(j, k), plegado: false });
    i = k;
  }
  const fila = (l: LineaDiff, key: string) => (
    <div key={key} className={`diff-doc__fila ${l.tipo === "add" ? "diff-doc__fila--add" : l.tipo === "del" ? "diff-doc__fila--del" : ""}`}>
      <span className="diff-doc__signo" aria-hidden="true">{l.tipo === "add" ? "+" : l.tipo === "del" ? "−" : ""}</span>
      <span className="diff-doc__texto">
        {l.tipo !== "igual" && <span className="diff-doc__lector">{l.tipo === "add" ? "Añadido: " : "Eliminado: "}</span>}
        {l.segmentos ? l.segmentos.map((s, i) => s.cambio ? <mark key={i} className="diff-doc__marca">{s.texto}</mark> : <React.Fragment key={i}>{s.texto}</React.Fragment>) : l.texto}
      </span>
    </div>);
  return (
    <div className="diff-doc">
      {tramos.map((t, i) => t.plegado && !abiertos.has(i)
        ? <button key={i} type="button" className="diff-doc__plegado" onClick={() => setAbiertos(new Set(abiertos).add(i))}>
            <ChevronDown size={14} strokeWidth={1.5} /> {t.lineas.length} líneas sin cambios</button>
        : t.lineas.map((l, j) => fila(l, `${i}-${j}`)))}
    </div>
  );
};

// ---------------------------------------------------------------- pasos de un flujo (siempre navegables)
export interface PasoFlujo { id: string; titulo: string; hecho: boolean; actual: boolean; resumen: string; aviso: string }
/** Barra de pasos con el aspecto de las pestañas (`tab-item`): número, título, estado en una línea (en color
 *  de aviso si hay algo nuevo o pendiente) y la etiqueta «Siguiente» en el paso sugerido. Todos se pueden abrir
 *  en cualquier momento: el trabajo no es lineal. */
export const Pasos = ({ pasos, activo, onIr, extra }: { pasos: PasoFlujo[]; activo: string; onIr: (id: string) => void; extra?: React.ReactNode }) => (
  <nav className="pasos" aria-label="Pasos del informe">
    <ol className="pasos__lista">
      {pasos.map((p, i) => (
        <li key={p.id} className="pasos__li">
          <button type="button" onClick={() => onIr(p.id)} aria-current={p.id === activo ? "step" : undefined}
            className={`pasos__item ${p.id === activo ? "pasos__item--activo" : ""} ${p.hecho ? "pasos__item--hecho" : ""} ${p.aviso ? "pasos__item--aviso" : ""}`}>
            <span className="pasos__titulo"><span className="pasos__num">{String(i + 1).padStart(2, "0")}</span>{p.titulo}{p.actual && <span className="tag tag-info pasos__siguiente">Siguiente</span>}</span>
            <span className="pasos__resumen">{p.aviso || p.resumen}</span>
          </button>
        </li>))}
    </ol>
    {extra && <div className="pasos__extra">{extra}</div>}
  </nav>
);

/** Cabecera de un paso: dónde estás (`kicker`, p. ej. «Paso 2 de 4»), título, para qué sirve y, si es el paso
 *  sugerido, qué toca hacer ahora; `aviso` para una franja con acción (p. ej. lo pendiente en otro paso). */
export const PasoCabecera = ({ kicker, titulo, ayuda, sugerencia, aviso }: { kicker: string; titulo: string; ayuda: React.ReactNode; sugerencia?: string; aviso?: React.ReactNode }) => (
  <header className="paso-cabecera">
    <div className="paso-cabecera__kicker">{kicker}</div>
    <h1 className="paso-cabecera__titulo">{titulo}</h1>
    <p className="paso-cabecera__ayuda">{ayuda}</p>
    {sugerencia && <Aviso tipo="info">{sugerencia}</Aviso>}
    {aviso}
  </header>
);

/** Franja de aviso dentro de un paso (info: qué toca; aviso: algo nuevo o pendiente), con acción opcional. */
export const Aviso = ({ tipo = "info", children, accion }: { tipo?: "info" | "aviso"; children: React.ReactNode; accion?: React.ReactNode }) => (
  <div className={`aviso-paso aviso-paso--${tipo}`} role="status"><span className="aviso-paso__texto">{children}</span>{accion && <span className="aviso-paso__accion">{accion}</span>}</div>
);

/** Pie de un paso: volver al anterior y continuar al siguiente. */
export const PasoPie = ({ anterior, siguiente }: { anterior?: { titulo: string; ir: () => void }; siguiente?: { titulo: string; ir: () => void } }) => (
  <footer className="paso-pie">
    {anterior ? <button type="button" className="btn btn-ghost" onClick={anterior.ir}><ArrowLeft strokeWidth={1.5} /> {anterior.titulo}</button> : <span />}
    {siguiente && <button type="button" className="btn btn-secondary" onClick={siguiente.ir}>Continuar: {siguiente.titulo} <ArrowRight strokeWidth={1.5} /></button>}
  </footer>
);

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

// ---------------------------------------------------------------- esqueletos (silueta con la forma del contenido mientras carga)
export const Esqueleto = ({ ancho = 100, titulo }: { ancho?: number; titulo?: boolean }) =>
  <span className={`esqueleto ${titulo ? "esqueleto--titulo" : ""}`} style={{ width: `${ancho}%` }} aria-hidden="true" />;

/** Filas fantasma de una tabla: `anchos` en % por columna (imitar la tabla real). */
export const EsqueletoFilas = ({ anchos, filas = 5 }: { anchos: number[]; filas?: number }) => (
  <tbody aria-busy="true">{Array.from({ length: filas }, (_, i) => (
    <tr key={i}>{anchos.map((w, j) => <td key={j}><Esqueleto ancho={Math.min(100, w * (0.8 + ((i + j) % 3) * 0.1))} /></td>)}</tr>))}</tbody>
);

/** Documento: cabecera con metadatos y `bloques` tarjetas. */
export const EsqueletoDocumento = ({ bloques = 3 }: { bloques?: number }) => (
  <div aria-busy="true" aria-label="Cargando">
    <Esqueleto ancho={22} /><Esqueleto titulo ancho={55} />
    <div className="metadata-grid" style={{ marginBottom: 40 }}>{[40, 50, 60, 35].map((w, i) => <div key={i}><Esqueleto ancho={w} /><Esqueleto ancho={w + 20} /></div>)}</div>
    {Array.from({ length: bloques }, (_, i) => <span key={i} className="esqueleto esqueleto--bloque" />)}
  </div>
);

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
