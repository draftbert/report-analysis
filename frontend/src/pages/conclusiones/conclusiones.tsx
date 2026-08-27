import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, esperarJob } from "@/api";
import type { Conclusion, Estado, Hallazgo, Riesgo, Tipo } from "@/api";
import { JobButton, JobResult, Modal, RiskBadge, StateChip, useNotificar } from "@/components/ui";
import type { JobResultado } from "@/components/ui";
import { useEstado } from "@/layout/layout";

import "./conclusiones.css";

const RIESGOS: Riesgo[] = ["Crítico", "Alto", "Medio", "Bajo"];
const CAMPOS: { k: keyof Conclusion; label: string; filas: number }[] = [
  { k: "incidencia", label: "Incidencia detectada", filas: 5 },
  { k: "causa_raiz", label: "Causa raíz", filas: 3 },
  { k: "como_se_ha_llegado", label: "Detalles descriptivos (una viñeta «- » por dato)", filas: 5 },
  { k: "consecuencias", label: "Consecuencias", filas: 3 },
];

const Tarjeta = ({ c, hallazgos, onGuardar, onEstado, onRegenerar }: {
  c: Conclusion; hallazgos: Hallazgo[]; onGuardar: (id: string, campos: Partial<Conclusion>) => Promise<void>;
  onEstado: (id: string, e: Estado) => void; onRegenerar: (id: string, notas: string) => Promise<{ job_id: string }>;
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
    <div className={`conc ${c.estado === "descartada" ? "conc--descartada" : ""}`}>
      <div className="conc__head">
        <span className="conc__id">{c.id}</span>
        <input className="input input--inline conc__titulo" value={v.titulo} onChange={(e) => set("titulo", e.target.value)} />
        <StateChip estado={c.estado} onChange={(e) => onEstado(c.id, e)} />
        <button className="btn btn--ghost btn--small" onClick={() => setAbierta(!abierta)}>{abierta ? "Plegar" : "Desplegar"}</button>
      </div>
      <div className="conc__meta">
        <div className="row">
          <span className="label">Tipo</span>
          {(["conclusion", "sugerencia"] as Tipo[]).map((t) => <button key={t} className={`pill ${v.tipo === t ? "pill--active" : ""}`} onClick={() => set("tipo", t)}>{t === "conclusion" ? "Conclusión" : "Sugerencia de mejora"}</button>)}
        </div>
        <div className="row">
          <RiskBadge nivel={v.nivel_riesgo} propuesto={c.riesgo_propuesto} />
          {RIESGOS.map((r) => <button key={r} className={`pill ${v.nivel_riesgo === r ? "pill--active" : ""}`} onClick={() => set("nivel_riesgo", r)}>{r}</button>)}
        </div>
      </div>
      {abierta && (
        <>
          <div className="meta-grid">
            {([["prueba", "Prueba"], ["area", "Área"], ["responsable", "Responsable"], ["plazo", "Plazo"], ["referencia_recomendacion", "Ref. recomendación"], ["fuente", "Fuente"]] as [keyof Conclusion, string][]).map(([k, l]) => (
              <div className="field" key={k}><span className="field__label">{l}</span><input className="input input--inline" value={String(v[k] ?? "")} onChange={(e) => set(k, e.target.value)} /></div>
            ))}
          </div>
          {CAMPOS.map(({ k, label, filas }) => (
            <div className="field" key={k}>
              <span className="field__label">{label}</span>
              <textarea className="textarea" rows={filas} value={String(v[k] ?? "")} onChange={(e) => set(k, e.target.value)} />
              {halls(k).map((h, i) => <span key={i} className="conc__hallazgo">✖ «{h.fragmento}» — {h.mensaje} {h.sugerencia && `→ ${h.sugerencia}`}</span>)}
            </div>
          ))}
          <div className="field">
            <span className="field__label">{esSug ? "Propuesta de mejora" : "Recomendación (un párrafo por recomendación: 1.1, 1.2…)"}</span>
            <textarea className="textarea" rows={4} value={v.recomendacion} onChange={(e) => set("recomendacion", e.target.value)} placeholder={esSug ? "Propuesta de mejora" : "Vacía: el asistente «Recomendar» te la pedirá o la propondrá el modelo"} />
            {!esSug && !v.recomendacion && <span className="detail">Sin recomendación. Se respeta al 100 % lo que escribas aquí.</span>}
          </div>
          <div className="conc__notas">
            <div className="field" style={{ flex: 1 }}><span className="field__label">Notas del auditor (para regenerar con el modelo)</span><input className="input" value={v.notas} onChange={(e) => set("notas", e.target.value)} placeholder="p. ej. usa como causa raíz la ausencia de plantilla común y acorta la incidencia" /></div>
            <JobButton pequeno etiqueta="Regenerar con estas notas" disabled={!v.notas.trim()} lanzar={async () => { await guardar(); return onRegenerar(c.id, v.notas); }} />
          </div>
          <div className="row row--between">
            <span className="detail">{sucio ? "Sin guardar" : "Guardado"}</span>
            <button className="btn btn--primary btn--small" onClick={guardar} disabled={!sucio}>Guardar</button>
          </div>
        </>
      )}
    </div>
  );
};

export const Conclusiones = () => {
  const { ref = "" } = useParams();
  const { estado, recargar } = useEstado();
  const notificar = useNotificar();
  const [lista, setLista] = useState<Conclusion[]>([]);
  const [hallazgos, setHallazgos] = useState<Hallazgo[]>([]);
  const [resultado, setResultado] = useState<JobResultado | null>(null);
  const [asistente, setAsistente] = useState<{ pendientes: Conclusion[]; idx: number; respuestas: Record<string, string>; auto: string[]; texto: string } | null>(null);

  const cargar = async () => { setLista((await api.conclusiones(ref)).conclusiones); };
  useEffect(() => { cargar().catch((e) => notificar({ texto: e.message, error: true })); }, [ref]);
  const fin = (r: JobResultado) => { setResultado(r); if (r.estado === "ok") { cargar(); recargar(); } };

  const guardar = async (id: string, campos: Partial<Conclusion>) => { await api.guardarConclusion(ref, id, campos); notificar({ texto: `${id} guardada.` }); cargar(); recargar(); };
  const cambiarEstado = async (id: string, e: Estado) => { await api.aprobar(ref, [id], e); cargar(); recargar(); };
  const aprobarTodas = async () => { const r = await api.aprobar(ref, ["todas"], "aprobada"); notificar({ texto: r.mensaje }); cargar(); recargar(); };
  const revisar = async () => { const r = await api.revisarConclusiones(ref); setHallazgos(r.hallazgos); notificar({ texto: `${r.hallazgos.filter((h) => h.severidad === "error").length} errores, ${r.hallazgos.filter((h) => h.severidad === "aviso").length} avisos.` }); };
  const volcar = async () => { try { const r = await api.redactarConclusiones(ref); setResultado({ estado: "ok", mensaje: r.mensaje, resultado: null }); recargar(); } catch (e) { setResultado({ estado: "error", mensaje: (e as Error).message, resultado: null }); } };

  const abrirAsistente = () => {
    const pendientes = lista.filter((c) => c.estado === "aprobada" && c.tipo === "conclusion" && !c.recomendacion.trim());
    if (!pendientes.length) { notificar({ texto: "Todas las conclusiones aprobadas tienen recomendación." }); return; }
    setAsistente({ pendientes, idx: 0, respuestas: {}, auto: [], texto: "" });
  };
  const pasoAsistente = (modo: "texto" | "modelo") => {
    if (!asistente) return;
    const c = asistente.pendientes[asistente.idx];
    const respuestas = { ...asistente.respuestas }; const auto = [...asistente.auto];
    if (modo === "texto" && asistente.texto.trim()) respuestas[c.id] = asistente.texto.trim(); else auto.push(c.id);
    if (asistente.idx + 1 < asistente.pendientes.length) setAsistente({ ...asistente, idx: asistente.idx + 1, respuestas, auto, texto: "" });
    else { setAsistente(null); lanzarRecomendar(respuestas, auto); }
  };
  const lanzarRecomendar = async (respuestas: Record<string, string>, auto: string[]) => {
    try {
      const { job_id } = await api.recomendar(ref, { respuestas, auto: auto.length > 0, ids: [...Object.keys(respuestas), ...auto] });
      const j = await esperarJob(job_id);
      fin({ estado: j.estado === "ok" ? "ok" : "error", mensaje: j.mensaje, resultado: j.resultado });
    } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };

  const c = estado?.conclusiones;
  return (
    <div className="page">
      <div className="page__header">
        <div><h2 className="page__title">Conclusiones</h2><p className="page__subtitle">Una por incidencia del papel de trabajo: incidencia, causa raíz, detalles, consecuencias y recomendación. Aquí manda el auditor.</p></div>
        <div className="page__actions">
          <JobButton etiqueta={lista.length ? "Extraer de nuevo" : "Extraer del papel de trabajo"} primario={!lista.length} confirmar={lista.length ? "Se regenerarán todas las conclusiones (el fichero actual se guarda en historial). ¿Continuar?" : undefined} lanzar={() => api.extraer(ref, true)} onFin={fin} />
          <button className="btn" onClick={aprobarTodas} disabled={!lista.length}>Aprobar todas</button>
          <button className="btn" onClick={revisar} disabled={!lista.length}>Revisar vocabulario</button>
          <JobButton etiqueta="Corregir con el modelo" lanzar={() => api.corregirConclusiones(ref)} onFin={fin} disabled={!lista.length} />
          <button className="btn" onClick={abrirAsistente} disabled={!lista.length}>Recomendar…</button>
          <button className="btn btn--primary" onClick={volcar} disabled={!c?.aprobada}>Volcar aprobadas al informe</button>
        </div>
      </div>
      {c && (
        <div className="kpis">
          <div className="kpi"><div className="kpi__value">{c.total}</div><div className="kpi__label">Conclusiones</div></div>
          <div className="kpi"><div className="kpi__value">{c.aprobada}</div><div className="kpi__label">Aprobadas</div></div>
          <div className="kpi"><div className="kpi__value">{c.sin_recomendacion.length}</div><div className="kpi__label">Sin recomendación</div></div>
          <div className="kpi"><div className="kpi__value">{c.sugerencias}</div><div className="kpi__label">Sugerencias de mejora</div></div>
        </div>
      )}
      <JobResult r={resultado} onClose={() => setResultado(null)} />
      {!lista.length && <div className="empty">Aún no hay conclusiones: extráelas del papel de trabajo.</div>}
      <div className="stack">
        {lista.map((x) => <Tarjeta key={x.id + x.estado + x.recomendacion.length} c={x} hallazgos={hallazgos} onGuardar={guardar} onEstado={cambiarEstado} onRegenerar={(id, notas) => api.regenerar(ref, id, notas)} />)}
      </div>
      {asistente && (() => {
        const actual = asistente.pendientes[asistente.idx];
        return (
          <Modal titulo={`Recomendar · ${actual.id} (${asistente.idx + 1} de ${asistente.pendientes.length})`} onClose={() => setAsistente(null)}
            acciones={<><button className="btn" onClick={() => pasoAsistente("modelo")}>Que la proponga el modelo</button><button className="btn btn--primary" onClick={() => pasoAsistente("texto")} disabled={!asistente.texto.trim()}>Usar mi texto (se respeta tal cual)</button></>}>
            <div className="section-title">{actual.titulo}</div>
            <p className="body">{actual.incidencia}</p>
            <p className="detail">{actual.consecuencias}</p>
            <div className="field"><span className="field__label">¿Tienes recomendación?</span><textarea className="textarea" rows={5} value={asistente.texto} onChange={(e) => setAsistente({ ...asistente, texto: e.target.value })} placeholder="Escríbela aquí; se registrará literalmente. Si la dejas vacía, el modelo la propone." /></div>
          </Modal>
        );
      })()}
    </div>
  );
};
