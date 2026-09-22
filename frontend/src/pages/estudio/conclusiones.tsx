/* Pestaña Conclusiones: una tarjeta editable por conclusión (incidencia → causa raíz → cómo se ha
   llegado → consecuencias → recomendación), estados, acciones con el modelo (jobs) y el asistente
   «Recomendar». La recomendación escrita por el auditor se respeta al 100 %. */
import { useCallback, useEffect, useState } from "react";
import { Check, CheckCheck, ChevronDown, ChevronUp, FileOutput, RotateCcw, SpellCheck, Sparkles, XCircle } from "lucide-react";

import { api } from "@/api";
import type { Conclusion, EstadoConclusion, Hallazgo, Riesgo, TipoConclusion } from "@/api";
import { EstadoTag, Modal, Progreso, ResultBox, RiesgoTag, SeveridadTag, useConfirmar, useNotificar } from "@/components/ui";
import { useJob } from "@/hooks/useJob";

import type { PropsPestana } from "./estudio";

const RIESGOS: Riesgo[] = ["", "Crítico", "Alto", "Medio", "Bajo"];
const CAMPOS: { k: keyof Conclusion; label: string; filas: number }[] = [
  { k: "incidencia", label: "Incidencia detectada", filas: 5 },
  { k: "causa_raiz", label: "Causa raíz", filas: 3 },
  { k: "como_se_ha_llegado", label: "Detalles descriptivos (una viñeta «- » por dato)", filas: 5 },
  { k: "consecuencias", label: "Consecuencias", filas: 3 },
];
const META: [keyof Conclusion, string][] = [["prueba", "Prueba"], ["area", "Área"], ["responsable", "Responsable"], ["plazo", "Plazo"], ["referencia_recomendacion", "Ref. recomendación"], ["fuente", "Fuente"]];
type Mensaje = { texto: string; error: boolean } | null;

const Tarjeta = ({ c, hallazgos, onGuardar, onEstado, onRegenerar, ocupado }: {
  c: Conclusion; hallazgos: Hallazgo[]; onGuardar: (id: string, campos: Partial<Conclusion>) => Promise<void>;
  onEstado: (id: string, e: EstadoConclusion) => void; onRegenerar: (id: string, notas: string) => Promise<void>; ocupado: boolean;
}) => {
  const [v, setV] = useState<Conclusion>(c);
  const [sucio, setSucio] = useState(false);
  const [abierta, setAbierta] = useState(c.estado !== "descartada");
  useEffect(() => { setV(c); setSucio(false); }, [c]);
  const set = (k: keyof Conclusion, val: string) => { setV({ ...v, [k]: val }); setSucio(true); };
  const guardar = async () => { const { id, ...campos } = v; await onGuardar(id, campos); setSucio(false); };
  const esSug = v.tipo === "sugerencia";
  const halls = (campo: string) => hallazgos.filter((h) => h.id === c.id && (h.mensaje.includes(`«${campo}»`) || h.mensaje.startsWith(`[${campo}]`)));

  return (
    <div className="agreement-card" style={c.estado === "descartada" ? { opacity: 0.7 } : undefined}>
      <div className="agreement-tag">{c.id} <EstadoTag estado={c.estado} /> <RiesgoTag nivel={v.nivel_riesgo} propuesto={c.riesgo_propuesto} /> <span className="tag tag-neutral">{esSug ? "Sugerencia de mejora" : "Recomendación"}</span>
        <button type="button" className="icon-btn" style={{ marginLeft: "auto", height: 24 }} onClick={() => setAbierta(!abierta)} aria-label={abierta ? "Plegar" : "Desplegar"}>{abierta ? <ChevronUp size={16} strokeWidth={1.5} /> : <ChevronDown size={16} strokeWidth={1.5} />}</button>
      </div>
      <input className="inline-edit" style={{ fontSize: 14, fontWeight: 325 }} value={v.titulo} onChange={(e) => set("titulo", e.target.value)} aria-label={`Título de ${c.id}`} />
      {abierta && (
        <div style={{ marginTop: 16 }}>
          <div className="metadata-grid" style={{ marginTop: 0, marginBottom: 16 }}>
            <div className="meta-item"><span className="meta-key">Tipo</span>
              <select className="inline-edit" value={v.tipo} onChange={(e) => set("tipo", e.target.value as TipoConclusion)} aria-label="Tipo"><option value="recomendacion">Recomendación</option><option value="sugerencia">Sugerencia de mejora</option></select></div>
            <div className="meta-item"><span className="meta-key">Nivel de riesgo</span>
              <select className="inline-edit" value={v.nivel_riesgo} onChange={(e) => set("nivel_riesgo", e.target.value as Riesgo)} aria-label="Nivel de riesgo">{RIESGOS.map((r) => <option key={r} value={r}>{r || "Sin nivel"}</option>)}</select></div>
            {META.map(([k, l]) => <div className="meta-item" key={k}><span className="meta-key">{l}</span><input className="inline-edit" value={String(v[k] ?? "")} onChange={(e) => set(k, e.target.value)} aria-label={l} /></div>)}
          </div>
          {CAMPOS.map(({ k, label, filas }) => (
            <div className="form-group" key={k} style={{ marginBottom: 16 }}>
              <label className="input-label" htmlFor={`${c.id}-${k}`}>{label}</label>
              <textarea id={`${c.id}-${k}`} className="textarea-doc" rows={filas} value={String(v[k] ?? "")} onChange={(e) => set(k, e.target.value)} />
              {halls(k).map((h, i) => <p key={i} className="small" style={{ marginTop: 4 }}><SeveridadTag severidad={h.severidad} /> «{h.fragmento}» — {h.mensaje}{h.sugerencia && ` → ${h.sugerencia}`}</p>)}
            </div>))}
          <div className="form-group" style={{ marginBottom: 16 }}>
            <label className="input-label" htmlFor={`${c.id}-recomendacion`}>{esSug ? "Propuesta de mejora" : "Recomendación (un párrafo por recomendación: 1.1, 1.2…)"}</label>
            <textarea id={`${c.id}-recomendacion`} className="textarea-doc" rows={4} value={v.recomendacion} onChange={(e) => set("recomendacion", e.target.value)} placeholder={esSug ? "Propuesta de mejora" : "Vacía: el asistente «Recomendar» te la pedirá o la propondrá el modelo"} />
            {!esSug && !v.recomendacion && <p className="small muted" style={{ marginTop: 4 }}>Sin recomendación. Lo que escribas aquí se respeta al 100 %.</p>}
          </div>
          <div className="form-group" style={{ marginBottom: 16 }}>
            <label className="input-label" htmlFor={`${c.id}-notas`}>Notas del auditor (para regenerar con el modelo)</label>
            <div className="row" style={{ flexWrap: "nowrap" }}>
              <input id={`${c.id}-notas`} className="text-input text-input--small" value={v.notas} onChange={(e) => set("notas", e.target.value)} placeholder="p. ej. usa como causa raíz la ausencia de plantilla común y acorta la incidencia" />
              <button className="btn btn-ghost" disabled={!v.notas.trim() || ocupado} onClick={async () => { await guardar(); await onRegenerar(c.id, v.notas); }}><Sparkles strokeWidth={1.5} /> Regenerar</button>
            </div>
          </div>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="row">
              {c.estado !== "aprobada" && <button className="btn btn-primary" onClick={() => onEstado(c.id, "aprobada")} aria-label={`Aprobar ${c.id}`}><Check strokeWidth={1.5} /> Aprobar</button>}
              {c.estado !== "descartada" && <button className="btn btn-secondary" onClick={() => onEstado(c.id, "descartada")} aria-label={`Descartar ${c.id}`}><XCircle strokeWidth={1.5} /> Descartar</button>}
              {c.estado !== "propuesta" && <button className="btn btn-ghost" onClick={() => onEstado(c.id, "propuesta")} aria-label={`Volver a propuesta ${c.id}`}><RotateCcw strokeWidth={1.5} /> Propuesta</button>}
            </span>
            <span className="row"><span className="small muted">{sucio ? "Sin guardar" : "Guardada"}</span><button className="btn btn-secondary" onClick={guardar} disabled={!sucio}>Guardar</button></span>
          </div>
        </div>)}
    </div>
  );
};

export const Conclusiones = ({ refExp, exp, recargar }: PropsPestana) => {
  const notificar = useNotificar();
  const confirmar = useConfirmar();
  const job = useJob();
  const [lista, setLista] = useState<Conclusion[]>([]);
  const [hallazgos, setHallazgos] = useState<Hallazgo[]>([]);
  const [mensaje, setMensaje] = useState<Mensaje>(null);
  const [asistente, setAsistente] = useState<{ pendientes: Conclusion[]; idx: number; respuestas: Record<string, string>; auto: string[]; texto: string } | null>(null);

  const cargar = useCallback(async () => {
    try { setLista((await api.conclusiones(refExp)).conclusiones); } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  }, [refExp, notificar]);
  useEffect(() => { cargar(); }, [cargar]);

  const correr = async (fn: () => Promise<{ job_id: string }>) => {
    setMensaje(null);
    const j = await job.lanzar(fn);
    setMensaje({ texto: j.mensaje, error: j.estado !== "ok" });
    if (j.estado === "ok") { await cargar(); await recargar(); }
  };
  const extraer = async () => {
    if (lista.length && !(await confirmar({ titulo: "Extraer de nuevo", accion: "Extraer", cuerpo: "Se regenerarán todas las conclusiones a partir del papel de trabajo. El fichero actual queda en el historial." }))) return;
    await correr(() => api.extraer(refExp, true));
  };
  const guardar = async (id: string, campos: Partial<Conclusion>) => {
    try { await api.guardarConclusion(refExp, id, campos); notificar({ texto: `${id} guardada.` }); await cargar(); await recargar(); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };
  const cambiarEstado = async (id: string, e: EstadoConclusion) => {
    try { const r = await api.aprobar(refExp, [id], e); notificar({ texto: r.mensaje }); await cargar(); await recargar(); }
    catch (err) { notificar({ texto: (err as Error).message, error: true }); }
  };
  const aprobarTodas = async () => {
    if (!(await confirmar({ titulo: "Aprobar todas las conclusiones", accion: "Aprobar", cuerpo: "Se marcan como aprobadas todas las propuestas; al aprobar se valida el nivel de riesgo propuesto por el modelo." }))) return;
    try { const r = await api.aprobar(refExp, ["todas"], "aprobada"); notificar({ texto: r.mensaje }); await cargar(); await recargar(); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };
  const revisar = async () => {
    try { const r = await api.revisarConclusiones(refExp); setHallazgos(r.hallazgos); notificar({ texto: `${r.hallazgos.filter((h) => h.severidad === "error").length} errores, ${r.hallazgos.filter((h) => h.severidad === "aviso").length} avisos.` }); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };
  const volcar = async () => {
    try { const r = await api.redactarConclusiones(refExp); setMensaje({ texto: r.mensaje, error: false }); await recargar(); }
    catch (e) { setMensaje({ texto: (e as Error).message, error: true }); }
  };

  const abrirAsistente = () => {
    const pendientes = lista.filter((c) => c.estado === "aprobada" && c.tipo === "recomendacion" && !c.recomendacion.trim());
    if (!pendientes.length) { notificar({ texto: "Todas las conclusiones aprobadas tienen recomendación." }); return; }
    setAsistente({ pendientes, idx: 0, respuestas: {}, auto: [], texto: "" });
  };
  const pasoAsistente = (modo: "texto" | "modelo") => {
    if (!asistente) return;
    const c = asistente.pendientes[asistente.idx];
    const respuestas = { ...asistente.respuestas }; const auto = [...asistente.auto];
    if (modo === "texto" && asistente.texto.trim()) respuestas[c.id] = asistente.texto.trim(); else auto.push(c.id);
    if (asistente.idx + 1 < asistente.pendientes.length) setAsistente({ ...asistente, idx: asistente.idx + 1, respuestas, auto, texto: "" });
    else { setAsistente(null); correr(() => api.recomendar(refExp, { respuestas, auto: auto.length > 0, ids: [...Object.keys(respuestas), ...auto] })); }
  };

  const c = exp.conclusiones;
  return (
    <div>
      <h2 className="section-header-sm">Conclusiones
        <span className="row">
          <button className="btn btn-ghost" onClick={extraer} disabled={job.activo || !exp.papeles.length}><Sparkles strokeWidth={1.5} /> {lista.length ? "Extraer de nuevo" : "Extraer del papel de trabajo"}</button>
          <button className="btn btn-ghost" onClick={aprobarTodas} disabled={!lista.length}><CheckCheck strokeWidth={1.5} /> Aprobar todas</button>
          <button className="btn btn-ghost" onClick={revisar} disabled={!lista.length}><SpellCheck strokeWidth={1.5} /> Revisar vocabulario</button>
          <button className="btn btn-ghost" onClick={() => correr(() => api.corregirConclusiones(refExp))} disabled={job.activo || !lista.length}><Sparkles strokeWidth={1.5} /> Corregir con el modelo</button>
          <button className="btn btn-secondary" onClick={abrirAsistente} disabled={job.activo || !lista.length}>Recomendar…</button>
          <button className="btn btn-primary" onClick={volcar} disabled={!c?.aprobada}><FileOutput strokeWidth={1.5} /> Volcar aprobadas al informe</button>
        </span></h2>
      <p className="small muted" style={{ marginBottom: 16 }}>Una por incidencia del papel de trabajo: incidencia, causa raíz, detalles, consecuencias y recomendación. Cada bloque es una recomendación (con plan de acción) o una sugerencia de mejora. Aquí manda el auditor.</p>
      {c && (
        <div className="kpi-row kpi-row--compact">
          <div className="kpi-item" style={{ marginRight: 48 }}><span className="kpi-label">Recomendaciones</span><span className="kpi-value">{c.total - c.sugerencias}</span></div>
          <div className="kpi-item" style={{ marginRight: 48 }}><span className="kpi-label">Aprobadas</span><span className="kpi-value">{c.aprobada}</span></div>
          <div className="kpi-item" style={{ marginRight: 48 }}><span className="kpi-label">Sin recomendación</span><span className="kpi-value">{c.sin_recomendacion.length}</span></div>
          <div className="kpi-item"><span className="kpi-label">Sugerencias de mejora</span><span className="kpi-value">{c.sugerencias}</span></div>
        </div>)}
      {job.activo && <Progreso texto={job.job?.progreso || "Trabajando con el modelo…"} pct={job.job?.progreso_pct} partes={job.job?.progreso_partes} onDetener={job.detener} />}
      {mensaje && <div style={{ marginBottom: 24 }}><ResultBox mensaje={mensaje.texto} error={mensaje.error} onClose={() => setMensaje(null)} /></div>}
      {!lista.length && <div className="empty">{exp.papeles.length ? "Aún no hay conclusiones: extráelas del papel de trabajo." : "Sube el papel de trabajo en Entrada para poder extraer las conclusiones."}</div>}
      <div className="agreements-list">
        {lista.map((x) => <Tarjeta key={x.id + x.estado + x.recomendacion.length} c={x} hallazgos={hallazgos} ocupado={job.activo} onGuardar={guardar} onEstado={cambiarEstado} onRegenerar={(id, notas) => correr(() => api.regenerar(refExp, id, notas))} />)}
      </div>
      {asistente && (() => {
        const actual = asistente.pendientes[asistente.idx];
        return (
          <Modal ancho titulo={`Recomendar · ${actual.id} (${asistente.idx + 1} de ${asistente.pendientes.length})`} onClose={() => setAsistente(null)}
            acciones={<><button className="btn btn-secondary" onClick={() => pasoAsistente("modelo")}>Que la proponga el modelo</button><button className="btn btn-primary" onClick={() => pasoAsistente("texto")} disabled={!asistente.texto.trim()}>Usar mi texto (se respeta tal cual)</button></>}>
            <div className="topic-card"><div className="topic-title">{actual.titulo}</div><div className="topic-desc">{actual.incidencia}</div>{actual.consecuencias && <p className="small muted" style={{ marginTop: 8 }}>{actual.consecuencias}</p>}</div>
            <div className="form-group" style={{ marginBottom: 0 }}><label className="input-label" htmlFor="recom">¿Tienes recomendación?</label>
              <textarea id="recom" className="textarea-doc" rows={6} value={asistente.texto} onChange={(e) => setAsistente({ ...asistente, texto: e.target.value })} placeholder="Escríbela aquí; se registrará literalmente. Si la dejas vacía, el modelo la propone." autoFocus /></div>
          </Modal>);
      })()}
    </div>
  );
};
