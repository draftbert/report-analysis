/* Informe (patrón 5 de la guía): toolbar sticky (estado y acciones), documento WYSIWYG (cada apartado
   es una diapositiva) y cajón del asistente: chat de cambios, buzón de instrucciones, revisión e historial. */
import { useCallback, useEffect, useRef, useState } from "react";
import { Archive, Check, Download, History, Pencil, Presentation, Send, Sparkles, SpellCheck } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { api } from "@/api";
import type { Apartado, Expediente, Hallazgo, Informe as InformeT, ResultadoCambios, Version } from "@/api";
import { DiffView, Loader, Markdown, MenuFlotante, Modal, PlanTag, ResultBox, RiesgoTag, SeveridadTag, SlideCard, useConfirmar, useNotificar } from "@/components/ui";
import { useJob } from "@/hooks/useJob";
import { Cabecera } from "@/layout/layout";
import { fmt } from "@/lib/formato";

const ESCALA = ["Deficiente", "Insuficiente", "Mejorable", "Razonable", "Adecuado"];
const PROMPTS: [string, string][] = [
  ["Subir el riesgo de una conclusión", "Cambia el nivel de riesgo de la conclusión 1 a Alto"],
  ["Acortar la introducción", "Acorta la introducción sin perder el alcance ni las magnitudes"],
  ["Añadir un dato a los detalles", "Añade a los detalles descriptivos de la conclusión 2 el dato: "],
  ["Corregir un responsable", "Cambia el responsable del plan de acción 1.1 a "],
];
type PestanaDrawer = "chat" | "instrucciones" | "revision" | "historial";
type Burbuja = { yo?: string; r?: ResultadoCambios | null; mensaje?: string; error?: boolean };
const kicker = (a: Apartado) => (a.tipo === "conclusion" ? `Detalle de conclusiones · ${fmt.dos(a.numero)}` : a.tipo === "sugerencia" ? `Sugerencias de mejora · ${fmt.dos(a.numero)}` : "Apartado");
/** Texto de la banda vertical: nombre de la sección y, en conclusiones y sugerencias, el riesgo. */
const banda = (a: Apartado) => (a.tipo === "conclusion" ? `Conclusión ${fmt.dos(a.numero)}${a.nivel_riesgo ? ` · Riesgo ${a.nivel_riesgo}` : ""}` : a.tipo === "sugerencia" ? `Sugerencia ${fmt.dos(a.numero)}` : a.titulo);

export const Informe = () => {
  const { ref = "" } = useParams();
  const notificar = useNotificar();
  const confirmar = useConfirmar();
  const [exp, setExp] = useState<Expediente | null>(null);
  const [inf, setInf] = useState<InformeT | null>(null);
  const [editando, setEditando] = useState(false);
  const [edicion, setEdicion] = useState({ introduccion: "", resumen_ejecutivo: "", evaluacion_global: "" });
  const [md, setMd] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [ocupado, setOcupado] = useState<"" | "ppt" | "zip">("");
  const [diff, setDiff] = useState("");
  const [mensaje, setMensaje] = useState<{ texto: string; error: boolean } | null>(null);
  const modelo = useJob<{ diff?: string }>();

  const cargar = useCallback(async () => {
    try {
      const [e, i] = await Promise.all([api.estado(ref), api.informe(ref)]);
      setExp(e); setInf(i);
      setEdicion({
        introduccion: i.apartados.find((a) => a.tipo === "introduccion")?.markdown ?? "",
        resumen_ejecutivo: i.apartados.find((a) => a.tipo === "resumen")?.markdown.replace(/\n*\*\*Evaluación global:\*\*.*$/s, "").replace(/\n*\*\*Próximos pasos:\*\*.*$/s, "") ?? "",
        evaluacion_global: i.evaluacion_global,
      });
    } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  }, [ref, notificar]);
  useEffect(() => { cargar(); }, [cargar]);

  const guardar = async () => {
    if (!editando) { setEditando(true); return; }
    try { await api.guardarInforme(ref, edicion); setEditando(false); notificar({ texto: "Informe guardado (snapshot en historial)." }); await cargar(); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };
  const guardarMd = async () => {
    if (md === null) return;
    try { await api.guardarInforme(ref, { markdown: md }); setMd(null); notificar({ texto: "Informe guardado." }); await cargar(); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };
  const correrModelo = async (fn: () => Promise<{ job_id: string }>) => {
    setMensaje(null);
    const j = await modelo.lanzar(fn);
    setMensaje({ texto: j.mensaje, error: j.estado !== "ok" });
    if (j.estado === "ok") { if (j.resultado?.diff) setDiff(j.resultado.diff); await cargar(); }
  };
  const deshacer = async () => {
    if (!(await confirmar({ titulo: "Restaurar la versión anterior", accion: "Restaurar", cuerpo: "El informe volverá al último snapshot del historial." }))) return;
    try { const r = await api.deshacer(ref, "informe"); notificar({ texto: r.mensaje }); await cargar(); } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };
  const verDiff = async () => { try { const r = await api.diff(ref, "informe"); setDiff(r.diff || ""); setDrawer(true); } catch (e) { notificar({ texto: (e as Error).message, error: true }); } };
  const exportar = async () => {
    setOcupado("ppt");
    try { const r = await api.ppt(ref); notificar({ texto: `Generado ${r.nombre}.` }); window.open(r.url, "_blank"); await cargar(); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); } finally { setOcupado(""); }
  };
  const archivar = async () => {
    if (!(await confirmar({ titulo: "Archivar el expediente", accion: "Archivar", cuerpo: "Se genera el zip de evidencia (trazas, historial, informe, conclusiones, actas y PowerPoint con manifest sha256). Las voces, clips y audios de las reuniones se destruyen." }))) return;
    setOcupado("zip");
    try { const r = await api.archivar(ref); notificar({ texto: `Archivo ${r.nombre} generado.` }); window.open(r.url, "_blank"); await cargar(); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); } finally { setOcupado(""); }
  };

  if (!exp || !inf) return <><Cabecera titulo="Informe" atras={`/informes/${encodeURIComponent(ref)}`} activo="/informes" /><div className="content-container" style={{ textAlign: "center" }}><Loader /></div></>;
  const hayInforme = inf.apartados.some((a) => a.markdown);
  const puedeExportar = !!exp.informe && exp.informe.n_conclusiones + exp.informe.n_sugerencias > 0;
  return (
    <>
      <Cabecera titulo={exp.nombre} atras={`/informes/${encodeURIComponent(ref)}`} activo="/informes" extra={<span className="badge-status">{exp.fase}</span>} />
      <div className="toolbar">
        <div className="toolbar-title">
          <span>{exp.informe ? `${exp.informe.n_conclusiones} conclusiones · ${exp.informe.n_sugerencias} sugerencias · v${exp.informe.versiones}` : "Sin informe"}</span>
          {exp.informe && <span className={`tag ${exp.informe.errores ? "tag-error" : "tag-success"}`}>{exp.informe.errores} errores · {exp.informe.avisos} avisos</span>}
          {exp.ppt?.desactualizado && <span className="tag tag-warning">PowerPoint desactualizado</span>}
          {exp.instrucciones_pendientes && <span className="tag tag-info">Instrucciones pendientes</span>}
        </div>
        <div className="toolbar-actions">
          <button className="btn btn-ghost" onClick={guardar} disabled={modelo.activo}>{editando ? <><Check strokeWidth={1.5} /> Guardar cambios</> : <><Pencil strokeWidth={1.5} /> Editar</>}</button>
          {editando && <button className="btn btn-ghost" onClick={() => { setEditando(false); cargar(); }}>Cancelar</button>}
          <MenuFlotante etiqueta={<><Sparkles strokeWidth={1.5} /> Modelo</>}>
            <button className="btn btn-ghost" onClick={() => correrModelo(() => api.corregir(ref, false))} disabled={modelo.activo || !hayInforme}>Corregir errores de estilo</button>
            <button className="btn btn-ghost" onClick={() => correrModelo(() => api.corregir(ref, true))} disabled={modelo.activo || !hayInforme}>Corregir también tono (avisos)</button>
            <button className="btn btn-ghost" onClick={() => correrModelo(() => api.condensar(ref, 0.85))} disabled={modelo.activo || !hayInforme}>Condensar un 15 %</button>
            <button className="btn btn-ghost" onClick={() => setMd(inf.markdown)}>Editar Markdown completo</button>
          </MenuFlotante>
          <button className="btn btn-ghost" onClick={deshacer} disabled={!exp.informe?.versiones} title="Vuelve a la versión anterior del informe"><History strokeWidth={1.5} /> Versión anterior</button>
          <MenuFlotante etiqueta={<><Download strokeWidth={1.5} /> Entregables</>} primario>
            <button className="btn btn-ghost" onClick={exportar} disabled={!puedeExportar || ocupado !== ""}>{ocupado === "ppt" ? <><span className="spinner" /> Exportando…</> : <><Presentation strokeWidth={1.5} /> Exportar a PowerPoint</>}</button>
            {exp.ppt && <a className="btn btn-ghost" href={api.urlSalida(ref, exp.ppt.nombre)}>Descargar {exp.ppt.nombre}</a>}
            <button className="btn btn-ghost" onClick={archivar} disabled={ocupado !== ""}>{ocupado === "zip" ? <><span className="spinner" /> Archivando…</> : <><Archive strokeWidth={1.5} /> Archivar evidencia (zip)</>}</button>
            {exp.archivos.map((a) => <a key={a} className="btn btn-ghost" href={api.urlSalida(ref, a)}>Descargar {a}</a>)}
          </MenuFlotante>
          <button className="btn btn-ghost drawer-toggle" onClick={() => setDrawer(!drawer)}><Sparkles strokeWidth={1.5} /> Asistente</button>
        </div>
      </div>

      <main className="main-layout">
        <div className={`document-container ${editando ? "editing" : ""}`}>
          {modelo.activo && <div className="result-box" style={{ marginBottom: 24 }}><span className="spinner" /> {modelo.job?.progreso || "Trabajando con el modelo…"} <button className="btn btn-ghost btn-ghost--inline small" style={{ marginLeft: 16 }} onClick={modelo.detener}>Detener</button></div>}
          {mensaje && <div style={{ marginBottom: 24 }}><ResultBox mensaje={mensaje.texto} error={mensaje.error} onClose={() => setMensaje(null)} /></div>}
          <div className="doc-header">
            <div className="section-label section-label--muted">Informe de auditoría interna</div>
            <h1 className="doc-headline">{exp.nombre}</h1>
            <div className="metadata-grid">
              <div className="meta-item"><span className="meta-key">Referencia</span><span className="meta-val">{exp.referencia}</span></div>
              <div className="meta-item"><span className="meta-key">Fecha del informe</span><span className="meta-val">{exp.fecha || "—"}</span></div>
              <div className="meta-item"><span className="meta-key">Distribución</span><span className="meta-val">{exp.distribucion.join(", ") || "—"}</span></div>
              <div className="meta-item"><span className="meta-key">Evaluación global</span>
                {editando
                  ? <select className="field-select" value={edicion.evaluacion_global} onChange={(e) => setEdicion({ ...edicion, evaluacion_global: e.target.value })} aria-label="Evaluación global"><option value="">—</option>{ESCALA.map((n) => <option key={n}>{n}</option>)}</select>
                  : <span className="meta-val">{inf.evaluacion_global || "—"}</span>}</div>
            </div>
          </div>
          {!hayInforme && <div className="empty">El informe está vacío. Redacta el contexto y vuelca las conclusiones aprobadas desde el estudio del informe.</div>}
          {inf.apartados.filter((a) => a.markdown || (editando && (a.tipo === "introduccion" || a.tipo === "resumen"))).map((a) => (
            <SlideCard key={a.id} banda={banda(a)} nivel={a.tipo === "conclusion" || a.tipo === "sugerencia" ? a.nivel_riesgo : undefined} kicker={kicker(a)} titulo={a.titulo}
              tools={(a.tipo === "conclusion" || a.tipo === "sugerencia") ? <RiesgoTag nivel={a.nivel_riesgo} /> : <span className="editable-badge">Editable</span>}>
              {editando && a.tipo === "introduccion" && <textarea className="textarea-doc" rows={16} value={edicion.introduccion} onChange={(e) => setEdicion({ ...edicion, introduccion: e.target.value })} aria-label="Introducción" />}
              {editando && a.tipo === "resumen" && <textarea className="textarea-doc" rows={12} value={edicion.resumen_ejecutivo} onChange={(e) => setEdicion({ ...edicion, resumen_ejecutivo: e.target.value })} aria-label="Resumen ejecutivo" />}
              {!(editando && (a.tipo === "introduccion" || a.tipo === "resumen")) && <Markdown texto={a.tipo === "conclusion" || a.tipo === "sugerencia" ? a.markdown.replace(/^###[^\n]*\n/, "") : a.markdown} />}
            </SlideCard>))}
          {editando && <p className="small muted">Las conclusiones se editan en el estudio del informe (pestaña Conclusiones) y se vuelcan de nuevo; aquí solo la introducción, el resumen y la evaluación global. Para todo lo demás, «Editar Markdown completo».</p>}
        </div>
        <Asistente refExp={ref} exp={exp} abierto={drawer} diff={diff} setDiff={setDiff} onCambio={cargar} verDiff={verDiff} deshacer={deshacer} />
      </main>

      {md !== null && (
        <Modal ancho titulo="Editar informe (Markdown completo)" onClose={() => setMd(null)} acciones={<><button className="btn btn-secondary" onClick={() => setMd(null)}>Cancelar</button><button className="btn btn-primary" onClick={guardarMd}>Guardar</button></>}>
          <p className="small muted">Respeta los títulos ##/###, la línea «A continuación, se muestran los detalles descriptivos…» y los párrafos **Recomendación N.1.**: es lo que permite exportar cada apartado como diapositiva.</p>
          <textarea className="textarea-notas" rows={28} value={md} onChange={(e) => setMd(e.target.value)} spellCheck={false} aria-label="Markdown del informe" />
        </Modal>)}
    </>
  );
};

// ---------------------------------------------------------------- cajón del asistente
const Asistente = ({ refExp, exp, abierto, diff, setDiff, onCambio, verDiff, deshacer }: {
  refExp: string; exp: Expediente; abierto: boolean; diff: string; setDiff: (d: string) => void; onCambio: () => Promise<void>; verDiff: () => void; deshacer: () => void;
}) => {
  const notificar = useNotificar();
  const [pestana, setPestana] = useState<PestanaDrawer>("chat");
  const [texto, setTexto] = useState("");
  const [chat, setChat] = useState<Burbuja[]>([]);
  const [instr, setInstr] = useState("");
  const [instrGuardada, setInstrGuardada] = useState("");
  const [hallazgos, setHallazgos] = useState<Hallazgo[] | null>(null);
  const [historial, setHistorial] = useState<Version[]>([]);
  const [resultado, setResultado] = useState<{ texto: string; error: boolean } | null>(null);
  const cambio = useJob<ResultadoCambios>();
  const buzon = useJob<ResultadoCambios>();
  const fin = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.instrucciones(refExp).then((r) => { setInstr(r.texto); setInstrGuardada(r.texto); }).catch(() => {});
    api.historial(refExp).then(setHistorial).catch(() => setHistorial([]));
  }, [refExp, exp]);
  useEffect(() => { fin.current?.scrollIntoView({ block: "end" }); }, [chat, cambio.activo]);

  const enviar = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const q = texto.trim();
    if (!q || cambio.activo) return;
    setChat((c) => [...c, { yo: q }]); setTexto("");
    const j = await cambio.lanzar(() => api.cambio(refExp, q));
    setChat((c) => [...c, { r: j.resultado, mensaje: j.mensaje, error: j.estado !== "ok" }]);
    if (j.estado === "ok") await onCambio();
  };
  const guardarInstr = async () => {
    try { const r = await api.guardarInstrucciones(refExp, instr); setInstr(r.texto); setInstrGuardada(r.texto); notificar({ texto: "Instrucciones guardadas." }); await onCambio(); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };
  const aplicarBuzon = async (soloPlan: boolean) => {
    setResultado(null);
    try { if (instr !== instrGuardada) { const r = await api.guardarInstrucciones(refExp, instr); setInstrGuardada(r.texto); } } catch (e) { notificar({ texto: (e as Error).message, error: true }); return; }
    const j = await buzon.lanzar(() => api.aplicarCambios(refExp, soloPlan));
    setResultado({ texto: j.mensaje, error: j.estado !== "ok" });
    if (j.estado === "ok") { if (j.resultado?.diff) setDiff(j.resultado.diff); if (!soloPlan) { setInstr(""); setInstrGuardada(""); } await onCambio(); }
  };
  const revisar = async () => { try { const r = await api.revisar(refExp); setHallazgos(r.hallazgos); } catch (e) { notificar({ texto: (e as Error).message, error: true }); } };
  const plan = (r: ResultadoCambios | null | undefined) => r?.plan?.length ? (
    <ul className="summary-bullets" style={{ marginTop: 8 }}>{r.plan.map((p, k) => <li key={k}><PlanTag estado={p.estado} /> {p.seccion} — {p.motivo}{p.detalle ? ` (${p.detalle})` : ""}</li>)}</ul>) : null;

  return (
    <aside className={`ai-drawer ${abierto ? "abierto" : ""}`}>
      <div className="drawer-header">
        <div className="drawer-title"><Sparkles size={18} strokeWidth={1.5} /> Asistente del informe</div>
        <span className="tag tag-neutral">{exp.llm.split("(")[0].trim() || "modelo"}</span>
      </div>
      <div className="tab-row" role="tablist" style={{ marginBottom: 0, gap: 16 }}>
        {([["chat", "Cambios"], ["instrucciones", "Buzón"], ["revision", "Revisión"], ["historial", "Historial"]] as [PestanaDrawer, string][]).map(([k, n]) => (
          <button key={k} className={`tab-item ${pestana === k ? "active" : ""}`} role="tab" aria-selected={pestana === k} onClick={() => setPestana(k)}>{n}{k === "historial" && historial.length > 0 && <span className="count">{historial.length}</span>}</button>))}
      </div>
      <div className="drawer-body">
        {pestana === "chat" && <>
          <div className="prompt-section-label">Cambios sencillos, uno por mensaje</div>
          <div className="prompt-chips">{PROMPTS.map(([n, p]) => <button key={n} className="prompt-chip" onClick={() => setTexto(p)}>"{n}"</button>)}</div>
          <div className="chat-history">
            {chat.length === 0 && !cambio.activo && <div className="small muted">Se aplican al momento sobre el informe, con snapshot en historial; puedes deshacerlos.</div>}
            {chat.map((m, i) => m.yo
              ? <div key={i} className="chat-bubble chat-bubble-user">{m.yo}</div>
              : <div key={i} className={`chat-bubble chat-bubble-ai ${m.error ? "error" : ""}`} style={m.error ? { borderLeftColor: "var(--c-error-fg)" } : undefined}>
                  <span style={{ whiteSpace: "pre-wrap" }}>{m.mensaje}</span>{plan(m.r)}
                  {m.r?.pendientes?.length ? <div className="small muted" style={{ marginTop: 8 }}>Pendientes: {m.r.pendientes.join(" · ")}</div> : null}
                  {m.r?.diff && <DiffView diff={m.r.diff} abiertoInicial={false} />}
                </div>)}
            {cambio.activo && <div className="chat-bubble chat-bubble-ai"><span className="spinner" /> {cambio.job?.progreso || "Aplicando…"}</div>}
            <div ref={fin} />
          </div>
          <div className="row"><button className="btn btn-ghost btn-ghost--inline small" onClick={deshacer}>Deshacer</button><button className="btn btn-ghost btn-ghost--inline small" onClick={verDiff}>Ver diff</button></div>
        </>}
        {pestana === "instrucciones" && <>
          <div className="prompt-section-label">Buzón del auditor (03_instrucciones.md)</div>
          <p className="small muted">Comentarios del Gerente, de la Directora o del área. Se revisan aquí y se aplican al informe; las reuniones nunca escriben en este buzón.</p>
          <textarea className="textarea-notas" rows={12} value={instr} onChange={(e) => setInstr(e.target.value)} aria-label="Instrucciones pendientes" />
          <div className="row">
            <button className="btn btn-ghost" onClick={guardarInstr} disabled={instr === instrGuardada}>Guardar</button>
            <button className="btn btn-secondary" onClick={() => aplicarBuzon(true)} disabled={buzon.activo || !instr.trim()}>Solo plan</button>
            <button className="btn btn-primary" onClick={() => aplicarBuzon(false)} disabled={buzon.activo || !instr.trim()}>{buzon.activo ? <><span className="spinner" /> Aplicando…</> : "Aplicar cambios"}</button>
          </div>
          {buzon.activo && <div className="small muted"><span className="spinner" /> {buzon.job?.progreso || "Aplicando…"}</div>}
          {resultado && <ResultBox mensaje={resultado.texto} error={resultado.error} onClose={() => setResultado(null)} />}
          {plan(buzon.job?.resultado)}
        </>}
        {pestana === "revision" && <>
          <div className="prompt-section-label">Reglas deterministas de estilo.yaml</div>
          <p className="small muted">Vocabulario prohibido y primera persona del singular (errores); tono, adjetivos y frases largas (avisos, se valoran según el contexto).</p>
          <div><button className="btn btn-secondary" onClick={revisar}><SpellCheck strokeWidth={1.5} /> Revisar vocabulario</button></div>
          {hallazgos !== null && (hallazgos.length === 0 ? <p className="small">Sin hallazgos.</p> : (
            <div className="agreements-list">{hallazgos.map((h, i) => (
              <div key={i} className="agreement-card" style={{ padding: 12 }}><div className="agreement-tag"><SeveridadTag severidad={h.severidad} /> línea {h.linea}</div><div className="small">«{h.fragmento}»</div><div className="agreement-meta">{h.mensaje}{h.sugerencia ? ` → ${h.sugerencia}` : ""}</div></div>))}</div>))}
          {diff && <><div className="prompt-section-label">Último diff</div><DiffView diff={diff} /></>}
        </>}
        {pestana === "historial" && <>
          <div className="row"><button className="btn btn-ghost btn-ghost--inline small" onClick={deshacer}><History strokeWidth={1.5} /> Deshacer última</button><button className="btn btn-ghost btn-ghost--inline small" onClick={verDiff}>Diff contra la anterior</button></div>
          {historial.length === 0 ? <p className="small muted">Sin versiones anteriores.</p> : (
            <div className="table-wrapper"><table className="ids-table ids-table--muted"><thead><tr><th>Fecha</th><th>Fichero</th><th>Motivo</th></tr></thead>
              <tbody>{historial.map((v) => <tr key={v.nombre}><td className="small">{v.fecha}</td><td className="small">{v.fichero}</td><td className="small">{v.motivo}</td></tr>)}</tbody></table></div>)}
          {diff && <DiffView diff={diff} />}
        </>}
      </div>
      {pestana === "chat" && (
        <div className="drawer-input-area">
          <form className="input-wrapper" onSubmit={enviar}>
            <input className="ai-input" placeholder="Pide un cambio al informe…" value={texto} onChange={(e) => setTexto(e.target.value)} disabled={cambio.activo} autoComplete="off" aria-label="Cambio a aplicar" />
            <button className="send-btn" type="submit" title="Aplicar cambio" aria-label="Aplicar cambio"><Send size={16} strokeWidth={1.5} /></button>
          </form>
        </div>)}
      <p className="small muted" style={{ padding: "8px 0" }}><Link to={`/informes/${encodeURIComponent(refExp)}?pestana=reunion`}>Reuniones</Link> · <Link to={`/informes/${encodeURIComponent(refExp)}?pestana=trazas`}>Trazas</Link></p>
    </aside>
  );
};
