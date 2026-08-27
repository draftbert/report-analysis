import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, esperarJob } from "@/api";
import type { Apartado, Hallazgo, Informe as InformeT, ResultadoCambios, Version } from "@/api";
import { Pencil, RotateCcw, Send } from "lucide-react";

import { DiffView, JobButton, JobResult, Markdown, MarkdownEditor, Modal, SlideCard, useNotificar } from "@/components/ui";
import type { JobResultado } from "@/components/ui";
import { useEstado } from "@/layout/layout";

type Tab = "revision" | "chat" | "instrucciones" | "historial";
const clasePlan = (e: string) => (e.startsWith("aplicado") || e === "insertado" || e === "eliminado" ? "aplicado" : e === "CONFLICTO" ? "conflicto" : "no");

export const Informe = () => {
  const { ref = "" } = useParams();
  const { estado, recargar } = useEstado();
  const notificar = useNotificar();
  const [inf, setInf] = useState<InformeT | null>(null);
  const [tab, setTab] = useState<Tab>("revision");
  const [hallazgos, setHallazgos] = useState<Hallazgo[] | null>(null);
  const [resultado, setResultado] = useState<JobResultado | null>(null);
  const [diff, setDiff] = useState("");
  const [chat, setChat] = useState<{ yo?: string; r?: ResultadoCambios; mensaje?: string; error?: boolean }[]>([]);
  const [msg, setMsg] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [instr, setInstr] = useState("");
  const [historial, setHistorial] = useState<Version[]>([]);
  const [editor, setEditor] = useState<{ modo: "crudo" } | null>(null);
  const [md, setMd] = useState("");

  const cargar = async () => { const i = await api.informe(ref); setInf(i); setMd(i.markdown); };
  useEffect(() => { cargar().catch((e) => notificar({ texto: e.message, error: true })); api.instrucciones(ref).then((r) => setInstr(r.texto)); api.historial(ref).then(setHistorial); }, [ref]);
  const refrescar = () => { cargar(); recargar(); api.historial(ref).then(setHistorial); };

  const revisar = async () => { const r = await api.revisar(ref); setHallazgos(r.hallazgos); };
  const enviarCambio = async () => {
    const texto = msg.trim(); if (!texto) return;
    setChat((c) => [...c, { yo: texto }]); setMsg(""); setEnviando(true);
    try {
      const { job_id } = await api.cambio(ref, texto);
      const j = await esperarJob<ResultadoCambios>(job_id);
      setChat((c) => [...c, { r: j.resultado ?? undefined, mensaje: j.mensaje, error: j.estado !== "ok" }]);
      if (j.estado === "ok") refrescar();
    } catch (e) { setChat((c) => [...c, { mensaje: (e as Error).message, error: true }]); }
    finally { setEnviando(false); }
  };
  const deshacer = async () => { if (!window.confirm("¿Restaurar la versión anterior del informe?")) return; const r = await api.deshacer(ref, "informe"); notificar({ texto: r.mensaje }); refrescar(); };
  const verDiff = async () => { const r = await api.diff(ref, "informe"); setDiff(r.diff || "(sin diferencias)"); };
  const guardarCrudo = async () => { await api.guardarInforme(ref, { markdown: md }); setEditor(null); notificar({ texto: "Informe guardado." }); refrescar(); };

  const apartadoKicker = (a: Apartado) => (a.tipo === "conclusion" ? `Detalle de conclusiones · ${String(a.numero).padStart(2, "0")}` : a.tipo === "sugerencia" ? `Sugerencias de mejora · ${String(a.numero).padStart(2, "0")}` : "Apartado");

  return (
    <div className="page">
      <div className="page__header">
        <div><h2 className="page__title">Informe</h2><p className="page__subtitle">Cada apartado es una diapositiva del PowerPoint. Lo que se lee aquí es lo que se exporta.</p></div>
        <div className="page__actions">
          {estado?.ppt?.desactualizado && <span className="tag">PowerPoint desactualizado respecto al informe</span>}
          <button className="btn" onClick={() => setEditor({ modo: "crudo" })} disabled={!inf}><Pencil size={14} strokeWidth={1.5} />Editar informe completo</button>
        </div>
      </div>
      <JobResult r={resultado} onClose={() => setResultado(null)} />
      <div className="split">
        <div className="stack">
          {!inf?.apartados.some((a) => a.markdown) && <div className="empty">El informe está vacío. Redacta el contexto y vuelca las conclusiones aprobadas.</div>}
          {inf?.apartados.filter((a) => a.markdown).map((a) => (
            <SlideCard key={a.id} kicker={apartadoKicker(a)} titulo={a.titulo} nivel={a.tipo === "conclusion" || a.tipo === "sugerencia" ? a.nivel_riesgo : undefined}>
              <Markdown texto={a.tipo === "conclusion" || a.tipo === "sugerencia" ? a.markdown.replace(/^###[^\n]*\n/, "") : a.markdown} />
            </SlideCard>
          ))}
        </div>
        <aside className="stack">
          <div className="tabs">
            {([["revision", "Revisión"], ["chat", "Chat de cambios"], ["instrucciones", "Instrucciones"], ["historial", "Historial"]] as [Tab, string][]).map(([t, l]) => (
              <button key={t} className={`tabs__tab ${tab === t ? "tabs__tab--active" : ""}`} onClick={() => setTab(t)}>{l}</button>
            ))}
          </div>
          {tab === "revision" && (
            <div className="stack">
              <div className="row"><button className="btn" onClick={revisar}>Revisar vocabulario</button>
                <JobButton etiqueta="Corregir con el modelo" lanzar={() => api.corregir(ref, false)} onFin={(r) => { setResultado(r); if (r.estado === "ok") { refrescar(); setHallazgos(null); const d = (r.resultado as { diff?: string } | null)?.diff; if (d) setDiff(d); } }} /></div>
              {hallazgos === null ? <span className="detail">Reglas deterministas de estilo.yaml: vocabulario prohibido, primera persona del singular y frases largas.</span>
                : hallazgos.length === 0 ? <span className="detail">✔ Sin hallazgos.</span>
                : hallazgos.map((h, i) => <div key={i} className="panel" style={{ gap: 2 }}><span className={h.severidad === "error" ? "conc__hallazgo" : "detail"}>{h.severidad === "error" ? "✖" : "⚠"} L{h.linea} «{h.fragmento}»</span><span className="detail">{h.mensaje}{h.sugerencia ? ` → ${h.sugerencia}` : ""}</span></div>)}
              {diff && <DiffView diff={diff} />}
            </div>
          )}
          {tab === "chat" && (
            <div className="chat">
              <span className="detail">Cambios sencillos, uno por mensaje. Se aplican al momento y puedes deshacerlos.</span>
              {chat.map((m, i) => m.yo ? <div key={i} className="chat__msg chat__msg--user">{m.yo}</div> : (
                <div key={i} className={`chat__msg ${m.error ? "job-result--error" : ""}`}>
                  {m.r?.plan && <div className="chat__plan">{m.r.plan.map((p, k) => <span key={k}><span className={`plan-estado plan-estado--${clasePlan(p.estado)}`}>{p.estado}</span> {p.seccion} — {p.motivo}{p.detalle ? ` (${p.detalle})` : ""}</span>)}</div>}
                  {m.r?.pendientes?.length ? <div className="detail">Pendientes: {m.r.pendientes.join(" · ")}</div> : null}
                  {m.r?.diff ? <DiffView diff={m.r.diff} /> : <span className="detail">{m.mensaje}</span>}
                </div>
              ))}
              <textarea className="textarea" rows={3} value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="p. ej. Cambia el nivel de riesgo de la conclusión 1 a Alto" onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviarCambio(); } }} />
              <div className="row row--between">
                <div className="row"><button className="btn btn--small" onClick={deshacer}><RotateCcw size={13} strokeWidth={1.5} />Deshacer</button><button className="btn btn--small" onClick={verDiff}>Ver diff</button></div>
                <button className="btn btn--primary" onClick={enviarCambio} disabled={enviando || !msg.trim()}>{enviando ? <><span className="spinner" />Aplicando…</> : <><Send size={14} strokeWidth={1.5} />Aplicar cambio</>}</button>
              </div>
              {diff && tab === "chat" && <DiffView diff={diff} />}
            </div>
          )}
          {tab === "instrucciones" && (
            <div className="stack">
              <span className="detail">Buzón de instrucciones (03_instrucciones.md): comentarios del Gerente, de la Directora o detectados en una reunión. Revísalos y aplica.</span>
              <textarea className="textarea" rows={12} value={instr} onChange={(e) => setInstr(e.target.value)} />
              <div className="row row--between">
                <button className="btn btn--small" onClick={async () => { await api.guardarInstrucciones(ref, instr); notificar({ texto: "Instrucciones guardadas." }); recargar(); }}>Guardar</button>
                <div className="row">
                  <JobButton etiqueta="Solo plan" lanzar={async () => { await api.guardarInstrucciones(ref, instr); return api.aplicarCambios(ref, true); }} onFin={(r) => setResultado(r)} disabled={!instr.trim()} />
                  <JobButton primario etiqueta="Aplicar cambios" lanzar={async () => { await api.guardarInstrucciones(ref, instr); return api.aplicarCambios(ref, false); }} onFin={(r) => { setResultado(r); if (r.estado === "ok") { setInstr(""); refrescar(); const d = (r.resultado as ResultadoCambios | null)?.diff; if (d) setDiff(d); } }} disabled={!instr.trim()} />
                </div>
              </div>
              {diff && <DiffView diff={diff} />}
            </div>
          )}
          {tab === "historial" && (
            <div className="stack">
              <div className="row"><button className="btn btn--small" onClick={deshacer}><RotateCcw size={13} strokeWidth={1.5} />Deshacer última</button><button className="btn btn--small" onClick={verDiff}>Diff contra la anterior</button></div>
              {historial.length === 0 ? <span className="detail">Sin versiones anteriores.</span> : (
                <table className="table"><thead><tr><th>Fecha</th><th>Fichero</th><th>Motivo</th></tr></thead><tbody>
                  {historial.map((v) => <tr key={v.nombre}><td className="detail">{v.fecha}</td><td className="detail">{v.fichero}</td><td className="detail">{v.motivo}</td></tr>)}
                </tbody></table>
              )}
              {diff && <DiffView diff={diff} />}
            </div>
          )}
        </aside>
      </div>
      {editor && (
        <Modal titulo="Editar informe (Markdown completo)" onClose={() => setEditor(null)} acciones={<><button className="btn" onClick={() => setEditor(null)}>Cancelar</button><button className="btn btn--primary" onClick={guardarCrudo}>Guardar</button></>}>
          <span className="detail">Respeta los títulos `##`/`###`, la línea «A continuación, se muestran los detalles descriptivos…» y los párrafos **Recomendación N.1.**: es lo que permite exportar cada apartado como diapositiva.</span>
          <MarkdownEditor valor={md} onChange={setMd} filas={28} mono />
        </Modal>
      )}
    </div>
  );
};
