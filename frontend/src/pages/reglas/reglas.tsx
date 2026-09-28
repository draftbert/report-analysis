/* Reglas de estilo (patrón 5 de la guía: documento + cajón): edición directa del criterio de
   config/estilo.yaml (palabras prohibidas, primera persona, tono, extensión, reglas cuantitativas,
   estructura de conclusión) y cajón «Modificar usando el chat», donde el modelo propone y el auditor
   carga la propuesta en el editor y guarda. Todo guardado deja snapshot en config/historial/. */
import { useCallback, useEffect, useRef, useState } from "react";
import { Check, History, Pencil, Plus, Send, Sparkles, Trash2, X } from "lucide-react";

import { api } from "@/api";
import type { ClaveExtension, EstadoReglas, PropuestaReglas, Reglas as ReglasT } from "@/api";
import { DiffView, Esqueleto, EsqueletoDocumento, MenuFlotante, Modal, Switch, useConfirmar, useNotificar } from "@/components/ui";
import { useJob } from "@/hooks/useJob";
import { Cabecera } from "@/layout/layout";
import { fmt } from "@/lib/formato";

const EXTENSION: [ClaveExtension, string][] = [
  ["intro_bloque", "Cada bloque de la introducción"], ["resumen_total", "Resumen ejecutivo completo"], ["resumen_vineta", "Cada viñeta del resumen"],
  ["incidencia", "Incidencia (deber ser + identificado)"], ["causa_raiz", "Causa raíz"], ["detalle_vineta", "Cada viñeta de detalles"],
  ["detalles_max", "Máximo de viñetas de detalles"], ["consecuencias", "Consecuencias"], ["recomendacion", "Recomendación propuesta por el modelo"],
];
const PROMPTS: [string, string][] = [
  ["Prohibir una palabra", "Añade a las palabras prohibidas «» con la sugerencia «» y el motivo «»"],
  ["Acortar las frases", "Baja la longitud máxima de frase a 40 palabras"],
  ["Cuestionar una expresión", "Añade a las expresiones a cuestionar «» con la alternativa «»"],
  ["Ajustar la extensión", "Sube la extensión del resumen ejecutivo a 300 palabras"],
];
let cacheReglas: EstadoReglas | null = null;   // última versión conocida (se refresca al montar)
type Burbuja = { yo?: string; p?: PropuestaReglas | null; mensaje?: string; error?: boolean };
const igual = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

// ---------------------------------------------------------------- piezas del editor (privadas de la página)
const Fila = ({ children, onQuitar }: { children: React.ReactNode; onQuitar: () => void }) => (
  <div className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start", marginBottom: 8 }}>
    <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
    <button type="button" className="icon-btn" onClick={onQuitar} aria-label="Quitar" title="Quitar"><Trash2 size={16} strokeWidth={1.5} /></button>
  </div>
);

const ListaTexto = ({ valores, onChange, largo, placeholder }: { valores: string[]; onChange: (v: string[]) => void; largo?: boolean; placeholder?: string }) => (
  <div>
    {valores.map((v, i) => (
      <Fila key={i} onQuitar={() => onChange(valores.filter((_, j) => j !== i))}>
        {largo
          ? <textarea className="textarea-doc" rows={2} value={v} onChange={(e) => onChange(valores.map((x, j) => (j === i ? e.target.value : x)))} aria-label={`Elemento ${i + 1}`} />
          : <input className="text-input text-input--small" value={v} onChange={(e) => onChange(valores.map((x, j) => (j === i ? e.target.value : x)))} aria-label={`Elemento ${i + 1}`} />}
      </Fila>))}
    <button type="button" className="btn btn-ghost" onClick={() => onChange([...valores, ""])}><Plus strokeWidth={1.5} /> Añadir{placeholder ? ` ${placeholder}` : ""}</button>
  </div>
);

const Chips = ({ valores, onChange, placeholder }: { valores: string[]; onChange: (v: string[]) => void; placeholder: string }) => {
  const [texto, setTexto] = useState("");
  const anadir = () => { const v = texto.trim(); if (v && !valores.includes(v)) onChange([...valores, v]); setTexto(""); };
  return (
    <div>
      <input className="text-input text-input--small" style={{ maxWidth: 360 }} placeholder={placeholder} value={texto} onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); anadir(); } }} onBlur={anadir} aria-label={placeholder} />
      <div className="tag-container">
        {valores.map((v) => <span className="chip" key={v}>{v} <button type="button" className="chip-remove" aria-label={`Quitar ${v}`} onClick={() => onChange(valores.filter((x) => x !== v))}>×</button></span>)}
      </div>
    </div>
  );
};

function Tabla<T extends Record<string, string>>({ filas, columnas, onChange, nuevo, etiqueta }: {
  filas: T[]; columnas: [keyof T & string, string][]; onChange: (v: T[]) => void; nuevo: T; etiqueta: string;
}) {
  const set = (i: number, k: keyof T, v: string) => onChange(filas.map((f, j) => (j === i ? { ...f, [k]: v } : f)));
  return (
    <div className="table-wrapper">
      <table className="ids-table ids-table--muted">
        <thead><tr>{columnas.map(([k, n]) => <th key={k}>{n}</th>)}<th /></tr></thead>
        <tbody>
          {filas.map((f, i) => (
            <tr key={i}>
              {columnas.map(([k, n]) => <td key={k}><input className="inline-edit" value={f[k]} placeholder={n} onChange={(e) => set(i, k, e.target.value)} aria-label={`${n} ${i + 1}`} /></td>)}
              <td className="col-right"><button type="button" className="icon-btn" onClick={() => onChange(filas.filter((_, j) => j !== i))} aria-label="Quitar" title="Quitar"><Trash2 size={16} strokeWidth={1.5} /></button></td>
            </tr>))}
        </tbody>
      </table>
      <button type="button" className="btn btn-ghost" style={{ marginTop: 8 }} onClick={() => onChange([...filas, { ...nuevo }])}><Plus strokeWidth={1.5} /> Añadir {etiqueta}</button>
    </div>
  );
}

const Seccion = ({ titulo, ayuda, ancha, children }: { titulo: string; ayuda?: string; ancha?: boolean; children: React.ReactNode }) => (
  <section className={`doc-section topic-card ${ancha ? "section-grid__ancha" : ""}`}>
    <div className="section-label section-label--muted">{titulo}</div>
    {ayuda && <p className="small muted" style={{ marginBottom: 12 }}>{ayuda}</p>}
    {children}
  </section>
);

// ---------------------------------------------------------------- página
export const Reglas = () => {
  const notificar = useNotificar();
  const confirmar = useConfirmar();
  const [estado, setEstadoBase] = useState<EstadoReglas | null>(cacheReglas);
  const [r, setR] = useState<ReglasT | null>(cacheReglas?.reglas ?? null);
  const setEstado = (e: EstadoReglas) => { cacheReglas = e; setEstadoBase(e); };
  const [yamlEd, setYamlEd] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    try { const e = await api.reglas(); setEstado(e); setR(e.reglas); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  }, [notificar]);
  useEffect(() => { cargar(); }, [cargar]);

  const sucio = !!estado && !!r && !igual(estado.reglas, r);
  const guardar = useCallback(async () => {
    if (!r || !sucio) return;
    if (!(await confirmar({ titulo: "Guardar el criterio de estilo", accion: "Guardar", cuerpo: "Se sobreescribe config/estilo.yaml (la versión actual queda en config/historial/). Las reglas nuevas se aplican a partir de la siguiente acción con el modelo y a la siguiente revisión." }))) return;
    setGuardando(true);
    try { const e = await api.guardarReglas({ reglas: r, motivo: "web" }); setEstado(e); setR(e.reglas); notificar({ texto: "Reglas guardadas." }); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
    finally { setGuardando(false); }
  }, [r, sucio, confirmar, notificar]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); guardar(); } };
    window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h);
  }, [guardar]);
  const guardarYaml = async () => {
    if (yamlEd === null) return;
    try { const e = await api.guardarReglas({ yaml: yamlEd, motivo: "yaml" }); setEstado(e); setR(e.reglas); setYamlEd(null); notificar({ texto: "YAML guardado." }); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };
  const restaurar = async (nombre: string, fecha: string) => {
    if (!(await confirmar({ titulo: "Restaurar una versión anterior", accion: "Restaurar", cuerpo: `Las reglas volverán a la versión del ${fecha}. La versión actual queda guardada en el historial.` }))) return;
    try { const e = await api.restaurarReglas(nombre); setEstado(e); setR(e.reglas); notificar({ texto: "Versión restaurada." }); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };

  if (!estado || !r) return <><Cabecera titulo="Reglas de estilo" atras="/" activo="/reglas" /><main className="main-layout"><div className="document-container document-container--ancho"><EsqueletoDocumento bloques={0} /><div className="section-grid">{[0, 1, 2, 3].map((i) => <div key={i} className="topic-card"><Esqueleto ancho={40} /><Esqueleto /><Esqueleto ancho={80} /><Esqueleto ancho={65} /></div>)}</div></div></main></>;
  const set = (parche: Partial<ReglasT>) => setR({ ...r, ...parche });
  const setTono = (parche: Partial<ReglasT["tono"]>) => setR({ ...r, tono: { ...r.tono, ...parche } });
  const setCuant = (parche: Partial<ReglasT["reglas"]>) => setR({ ...r, reglas: { ...r.reglas, ...parche } });

  return (
    <>
      <Cabecera titulo="Reglas de estilo" atras="/" activo="/reglas" />
      <div className="toolbar">
        <div className="toolbar-title">
          <span>config/estilo.yaml · modificado {fmt.fechaHora(estado.modificado)}</span>
          <span className={`tag ${sucio ? "tag-warning" : "tag-success"}`}>{sucio ? "Sin guardar" : "Guardado"}</span>
          <span className="tag tag-neutral">{r.palabras_prohibidas.length} prohibidas · {r.tono.expresiones_a_cuestionar.length} a cuestionar · frases ≤ {r.reglas.longitud_maxima_frase}</span>
        </div>
        <div className="toolbar-actions">
          {sucio && <button className="btn btn-ghost" onClick={() => setR(estado.reglas)}>Descartar cambios</button>}
          <button className="btn btn-ghost" onClick={() => setYamlEd(estado.yaml)}><Pencil strokeWidth={1.5} /> Editar YAML</button>
          <MenuFlotante etiqueta={<><History strokeWidth={1.5} /> Historial{estado.historial.length ? ` (${estado.historial.length})` : ""}</>}>
            {estado.historial.length === 0 && <span className="btn btn-ghost" style={{ cursor: "default" }}>Sin versiones anteriores</span>}
            {estado.historial.slice(0, 12).map((v) => <button key={v.nombre} className="btn btn-ghost" onClick={() => restaurar(v.nombre, v.fecha)}>{v.fecha} · {v.motivo}</button>)}
          </MenuFlotante>
          <button className="btn btn-primary" onClick={guardar} disabled={!sucio || guardando}>{guardando ? <><span className="spinner" /> Guardando…</> : <><Check strokeWidth={1.5} /> Guardar</>}</button>
          <button className="btn btn-secondary drawer-toggle drawer-toggle--fijo" onClick={() => setDrawer(!drawer)} aria-expanded={drawer}><Sparkles strokeWidth={1.5} /> Modificar usando el chat</button>
        </div>
      </div>

      <main className="main-layout aparece">
        <div className="document-container document-container--ancho">
          <div className="doc-header">
            <div className="section-label section-label--muted">Criterio de estilo del informe</div>
            <h1 className="doc-headline">Reglas</h1>
            <p className="small muted">Se aplican de forma determinista en cada revisión (errores y avisos) y se inyectan en todos los prompts del modelo. Los cambios se guardan en config/estilo.yaml con copia previa en el historial. Ctrl/Cmd+S guarda.</p>
          </div>

          <div className="section-grid">
          <Seccion ancha titulo="Palabras y expresiones prohibidas" ayuda="Error en la revisión. «Sugerencia» es la sustitución que propone el modelo; «motivo», por qué está prohibida.">
            <Tabla filas={r.palabras_prohibidas} columnas={[["termino", "Término"], ["sugerencia", "Sugerencia"], ["motivo", "Motivo"]]} nuevo={{ termino: "", sugerencia: "", motivo: "" }} etiqueta="palabra" onChange={(v) => set({ palabras_prohibidas: v })} />
          </Seccion>

          <Seccion titulo="Primera persona del singular" ayuda="Formas que se señalan como error. El plural del equipo auditor («hemos revisado», «consideramos») sí se admite.">
            <Chips valores={r.primera_persona} onChange={(v) => set({ primera_persona: v })} placeholder="Añadir forma y pulsar Intro…" />
          </Seccion>

          <Seccion titulo="Tono y lenguaje · principios" ayuda="Se inyectan en todos los prompts de redacción.">
            <ListaTexto valores={r.tono.principios} onChange={(v) => setTono({ principios: v })} largo placeholder="principio" />
          </Seccion>
          <Seccion titulo="Expresiones a cuestionar" ayuda="Aviso en la revisión (nunca error): se valoran según el contexto, con la fórmula constructiva que suele sustituirlas.">
            <Tabla filas={r.tono.expresiones_a_cuestionar} columnas={[["termino", "Expresión"], ["alternativa", "Alternativa"]]} nuevo={{ termino: "", alternativa: "" }} etiqueta="expresión" onChange={(v) => setTono({ expresiones_a_cuestionar: v })} />
          </Seccion>
          <Seccion titulo="Fórmulas constructivas">
            <ListaTexto valores={r.tono.formulas_constructivas} onChange={(v) => setTono({ formulas_constructivas: v })} placeholder="fórmula" />
          </Seccion>
          <Seccion titulo="Absolutos y formulaciones excesivas">
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="input-label" htmlFor="absolutos-criterio">Criterio</label>
              <textarea id="absolutos-criterio" className="textarea-doc" rows={3} value={r.tono.absolutos.criterio} onChange={(e) => setTono({ absolutos: { ...r.tono.absolutos, criterio: e.target.value } })} />
            </div>
            <Tabla filas={r.tono.absolutos.ejemplos} columnas={[["antes", "Antes"], ["despues", "Después"]]} nuevo={{ antes: "", despues: "" }} etiqueta="ejemplo" onChange={(v) => setTono({ absolutos: { ...r.tono.absolutos, ejemplos: v } })} />
          </Seccion>
          <Seccion titulo="Adjetivos calificativos a cuestionar" ayuda="Aviso: subjetividad o intensificación sin evidencia adicional.">
            <Tabla filas={r.tono.adjetivos_a_cuestionar} columnas={[["termino", "Adjetivo"], ["alternativa", "Alternativa"]]} nuevo={{ termino: "", alternativa: "" }} etiqueta="adjetivo" onChange={(v) => setTono({ adjetivos_a_cuestionar: v })} />
          </Seccion>
          <Seccion titulo="Tiempos verbales">
            <ListaTexto valores={r.tono.tiempos_verbales} onChange={(v) => setTono({ tiempos_verbales: v })} largo placeholder="regla" />
          </Seccion>

          <Seccion titulo="Extensión orientativa (palabras)" ayuda="El informe se lee en diapositivas y la letra debe caber. Se inyecta en los prompts del modelo.">
            <div className="metadata-grid" style={{ marginTop: 0 }}>
              {EXTENSION.map(([k, n]) => (
                <div className="meta-item" key={k}><label className="meta-key" htmlFor={`ext-${k}`}>{n}</label>
                  <input id={`ext-${k}`} type="number" min={1} className="text-input text-input--small" value={r.extension[k]} onChange={(e) => set({ extension: { ...r.extension, [k]: Number(e.target.value) } })} /></div>))}
            </div>
          </Seccion>

          <Seccion titulo="Reglas cuantitativas">
            <div className="metadata-grid" style={{ marginTop: 0, marginBottom: 16 }}>
              <div className="meta-item"><label className="meta-key" htmlFor="long-frase">Longitud máxima de frase (palabras, aviso)</label>
                <input id="long-frase" type="number" min={5} className="text-input text-input--small" value={r.reglas.longitud_maxima_frase} onChange={(e) => setCuant({ longitud_maxima_frase: Number(e.target.value) })} /></div>
              <div className="meta-item"><span className="meta-key">Toda conclusión debe tener nivel de riesgo</span>
                <div className="switch-container" style={{ justifyContent: "flex-start", gap: 12 }}><Switch checked={r.reglas.requiere_nivel_riesgo} onChange={(v) => setCuant({ requiere_nivel_riesgo: v })} label="Requiere nivel de riesgo" /><span className="switch-label-text">{r.reglas.requiere_nivel_riesgo ? "Sí" : "No"}</span></div></div>
            </div>
            <div className="form-group" style={{ marginBottom: 16 }}><span className="input-label">Niveles de riesgo válidos</span>
              <Chips valores={r.reglas.niveles_riesgo_validos} onChange={(v) => setCuant({ niveles_riesgo_validos: v })} placeholder="Añadir nivel…" /></div>
            <div className="form-group" style={{ marginBottom: 0 }}><span className="input-label">Escala de evaluación global</span>
              <Chips valores={r.reglas.escala_evaluacion_global} onChange={(v) => setCuant({ escala_evaluacion_global: v })} placeholder="Añadir grado…" /></div>
          </Seccion>

          <Seccion titulo="Estructura exigible a cada conclusión" ayuda="Requerido = error si falta; si no, solo aviso hasta redactar el informe. Los nombres de campo son los del formato pivote.">
            <div className="table-wrapper">
              <table className="ids-table ids-table--muted">
                <thead><tr><th>Campo</th><th>Descripción</th><th>Requerido</th></tr></thead>
                <tbody>
                  {r.estructura_conclusion.map((c, i) => (
                    <tr key={c.campo}>
                      <td className="mono small">{c.campo}</td>
                      <td><input className="inline-edit" value={c.descripcion} onChange={(e) => set({ estructura_conclusion: r.estructura_conclusion.map((x, j) => (j === i ? { ...x, descripcion: e.target.value } : x)) })} aria-label={`Descripción de ${c.campo}`} /></td>
                      <td><Switch checked={c.requerido} onChange={(v) => set({ estructura_conclusion: r.estructura_conclusion.map((x, j) => (j === i ? { ...x, requerido: v } : x)) })} label={`Requerido ${c.campo}`} /></td>
                    </tr>))}
                </tbody>
              </table>
            </div>
          </Seccion>
          </div>
        </div>

        <Chat abierto={drawer} onCerrar={() => setDrawer(false)} reglas={r} onCargar={(p) => { setR(p); notificar({ texto: "Propuesta cargada en el editor: revísala y pulsa Guardar." }); }} />
      </main>

      {yamlEd !== null && (
        <Modal ancho titulo="Editar config/estilo.yaml" onClose={() => setYamlEd(null)} acciones={<><button className="btn btn-secondary" onClick={() => setYamlEd(null)}>Cancelar</button><button className="btn btn-primary" onClick={guardarYaml}>Guardar YAML</button></>}>
          <p className="small muted">Editor avanzado: se valida la estructura antes de guardar y la versión actual queda en el historial. Los comentarios se conservan.</p>
          <textarea className="textarea-notas" rows={30} value={yamlEd} onChange={(e) => setYamlEd(e.target.value)} spellCheck={false} aria-label="YAML de reglas" />
        </Modal>)}
    </>
  );
};

// ---------------------------------------------------------------- cajón «Modificar usando el chat»
const Chat = ({ abierto, onCerrar, reglas, onCargar }: { abierto: boolean; onCerrar: () => void; reglas: ReglasT; onCargar: (r: ReglasT) => void }) => {
  const [texto, setTexto] = useState("");
  const [chat, setChat] = useState<Burbuja[]>([]);
  const job = useJob<PropuestaReglas>();
  const fin = useRef<HTMLDivElement>(null);
  useEffect(() => { fin.current?.scrollIntoView({ block: "end" }); }, [chat, job.activo]);

  const enviar = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const q = texto.trim();
    if (!q || job.activo) return;
    setChat((c) => [...c, { yo: q }]); setTexto("");
    const j = await job.lanzar(() => api.chatReglas(q, reglas));
    setChat((c) => [...c, { p: j.resultado, mensaje: j.mensaje, error: j.estado !== "ok" }]);
  };

  return (
    <aside className={`ai-drawer ai-drawer--plegable ${abierto ? "abierto" : ""}`} aria-label="Modificar usando el chat">
      <div className="drawer-header">
        <div className="drawer-title"><Sparkles size={18} strokeWidth={1.5} /> Modificar usando el chat</div>
        <button className="icon-btn" onClick={onCerrar} aria-label="Cerrar"><X size={18} strokeWidth={1.5} /></button>
      </div>
      <div className="drawer-body">
        <p className="small muted">Pide el cambio en lenguaje natural. El modelo propone las reglas modificadas; tú las cargas en el editor, las revisas y las guardas.</p>
        <div className="prompt-section-label">Ejemplos</div>
        <div className="prompt-chips">{PROMPTS.map(([n, p]) => <button key={n} className="prompt-chip" onClick={() => setTexto(p)}>"{n}"</button>)}</div>
        <div className="chat-history">
          {chat.map((m, i) => m.yo
            ? <div key={i} className="chat-bubble chat-bubble-user">{m.yo}</div>
            : <div key={i} className="chat-bubble chat-bubble-ai" style={m.error ? { borderLeftColor: "var(--c-error-fg)" } : undefined}>
                <span style={{ whiteSpace: "pre-wrap" }}>{m.p?.respuesta ?? m.mensaje}</span>
                {m.p && m.p.cambios.length > 0 && <ul className="summary-bullets" style={{ marginTop: 8 }}>{m.p.cambios.map((c, k) => <li key={k}>{c}</li>)}</ul>}
                {m.p && !m.p.sin_cambios && <>
                  <DiffView diff={m.p.diff} abiertoInicial={false} />
                  <button className="btn btn-secondary" onClick={() => onCargar(m.p!.reglas)}>Cargar la propuesta en el editor</button>
                </>}
              </div>)}
          {job.activo && <div className="chat-bubble chat-bubble-ai"><span className="spinner" /> {job.job?.progreso || "Preparando la propuesta…"}</div>}
          <div ref={fin} />
        </div>
      </div>
      <div className="drawer-input-area">
        <form className="input-wrapper" onSubmit={enviar}>
          <input className="ai-input" placeholder="Qué regla quieres cambiar…" value={texto} onChange={(e) => setTexto(e.target.value)} disabled={job.activo} autoComplete="off" aria-label="Petición de cambio de reglas" />
          <button className="send-btn" type="submit" title="Enviar" aria-label="Enviar"><Send size={16} strokeWidth={1.5} /></button>
        </form>
      </div>
    </aside>
  );
};
