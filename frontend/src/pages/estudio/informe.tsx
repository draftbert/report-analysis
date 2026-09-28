/* Informe en el espacio de trabajo (patrón 5 de la guía): toolbar sticky (estado y acciones), dos vistas
   —Documento (WYSIWYG, cada apartado es una diapositiva) y Últimos cambios (apartados cambiados en verde/rojo,
   como un diff de GitHub)— y dos paneles propios a la derecha, cerrados por defecto y excluyentes (como en el
   generador de actas): «Revisar vocabulario» (resaltado + propuestas) y «Modificar con el chat» (chat y buzón).
   Las reuniones y la exportación son pasos hermanos de la iteración (ver estudio.tsx). */
import { useCallback, useEffect, useRef, useState } from "react";
import { Check, History, MessageSquare, Pencil, Send, Sparkles, SpellCheck, X } from "lucide-react";

import { api } from "@/api";
import type { Apartado, ComparacionInforme, Expediente, Hallazgo, Informe as InformeT, PropuestaCorreccion, ResultadoCambios } from "@/api";
import { Aviso, CambioTag, DiffCuenta, DiffDocumento, EsqueletoDocumento, Markdown, MenuFlotante, Modal, PlanTag, ResultBox, RiesgoTag, SeveridadTag, SlideCard, useConfirmar, useNotificar } from "@/components/ui";
import type { Resalte } from "@/components/ui";
import { useJob } from "@/hooks/useJob";
import { fmt } from "@/lib/formato";

import type { PropsPestana } from "./estudio";

const ESCALA = ["Deficiente", "Insuficiente", "Mejorable", "Razonable", "Adecuado"];
const PROMPTS: [string, string][] = [
  ["Subir el riesgo de una observación", "Cambia el nivel de riesgo de la conclusión 1 a Alto"],
  ["Acortar la introducción", "Acorta la introducción sin perder el alcance ni las magnitudes"],
  ["Añadir un dato a los detalles", "Añade a los detalles descriptivos de la conclusión 2 el dato: "],
  ["Corregir un responsable", "Cambia el responsable del plan de acción 1.1 a "],
];
type Panel = "" | "chat" | "revision";
type Burbuja = { yo?: string; r?: ResultadoCambios | null; mensaje?: string; error?: boolean };
type CabeceraApartado = Pick<Apartado, "numero" | "titulo" | "nivel_riesgo"> & { tipo: string };
const kicker = (a: CabeceraApartado) => (a.tipo === "conclusion" ? `Detalle de conclusiones · Observación ${fmt.dos(a.numero)}` : a.tipo === "sugerencia" ? `Sugerencias de mejora · Observación ${fmt.dos(a.numero)}` : "Apartado");
/** Texto de la banda vertical: el riesgo es de la OBSERVACIÓN (cada una lleva vinculada una recomendación o una sugerencia de mejora). */
const banda = (a: CabeceraApartado) => (a.tipo === "conclusion" || a.tipo === "sugerencia" ? `Observación ${fmt.dos(a.numero)}${a.nivel_riesgo ? ` · Riesgo ${a.nivel_riesgo}` : ""}` : a.titulo);

export type Vista = "documento" | "cambios";
const VISTAS: [Vista, string][] = [["documento", "Documento"], ["cambios", "Últimos cambios"]];

export const InformePaso = ({ refExp: ref, exp, recargar, irA, vista, cabecera, pie }: PropsPestana & { vista: Vista; cabecera: React.ReactNode; pie: React.ReactNode }) => {
  const notificar = useNotificar();
  const confirmar = useConfirmar();
  const [inf, setInf] = useState<InformeT | null>(null);
  const [editando, setEditando] = useState(false);
  const [edicion, setEdicion] = useState({ introduccion: "", resumen_ejecutivo: "", evaluacion_global: "" });
  const [md, setMd] = useState<string | null>(null);
  const [panel, setPanel] = useState<Panel>("");   // un solo panel abierto a la vez
  // Revisión de vocabulario: hallazgos resaltados en el documento y propuestas del modelo en el cajón (no escriben nada).
  const [revision, setRevision] = useState<{ hallazgos: Hallazgo[]; propuestas: PropuestaCorreccion[] | null } | null>(null);
  const [aplicandoRevision, setAplicandoRevision] = useState(false);
  const proponer = useJob<{ propuestas?: PropuestaCorreccion[] }>();
  const [mensaje, setMensaje] = useState<{ texto: string; error: boolean } | null>(null);
  const [contra, setContra] = useState("");   // "" = el último cambio; si no, nombre del snapshot desde el que acumular
  const [cambios, setCambios] = useState<ComparacionInforme | null>(null);
  const modelo = useJob<{ diff?: string }>();

  const cargar = useCallback(async () => {
    try {
      const i = await api.informe(ref);
      setInf(i);
      setEdicion({
        introduccion: i.apartados.find((a) => a.tipo === "introduccion")?.markdown ?? "",
        resumen_ejecutivo: i.apartados.find((a) => a.tipo === "resumen")?.markdown.replace(/\n*\*\*Evaluación global:\*\*.*$/s, "").replace(/\n*\*\*Próximos pasos:\*\*.*$/s, "") ?? "",
        evaluacion_global: i.evaluacion_global,
      });
    } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
    await recargar();
  }, [ref, notificar, recargar]);
  useEffect(() => { cargar(); }, [cargar]);
  // se recalcula tras cada cambio (inf) mientras la vista de cambios está abierta
  useEffect(() => {
    if (vista !== "cambios") return;
    let vivo = true;
    api.comparacionInforme(ref, contra || undefined).then((c) => { if (vivo) setCambios(c); })
      .catch((e) => { if (vivo) { notificar({ texto: (e as Error).message, error: true }); setContra(""); } });
    return () => { vivo = false; };
  }, [vista, contra, inf, ref, notificar]);
  const verVista = (v: Vista, desde = "") => {
    if (v === "cambios") { setContra(desde); setCambios(null); }
    setEditando(false);
    irA?.("informe", v);
  };

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
    if (j.estado === "ok") await cargar();
  };
  const deshacer = async () => {
    if (!(await confirmar({ titulo: "Restaurar la versión anterior", accion: "Restaurar", cuerpo: "El informe volverá al último snapshot del historial." }))) return;
    try { const r = await api.deshacer(ref, "informe"); notificar({ texto: r.mensaje }); await cargar(); } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };
  const refrescarHallazgos = async () => {
    try { const r = await api.revisar(ref); setRevision((x) => x && { ...x, hallazgos: r.hallazgos }); } catch { /* se ve al volver a revisar */ }
  };
  const lanzarPropuestas = async () => {
    setRevision((x) => x && { ...x, propuestas: null });
    const j = await proponer.lanzar(() => api.proponerCorrecciones(ref));
    if (j.estado !== "ok") notificar({ texto: j.mensaje, error: true });
    setRevision((x) => x && { ...x, propuestas: j.estado === "ok" ? j.resultado?.propuestas ?? [] : [] });
  };
  const cerrarRevision = () => { setRevision(null); setPanel(""); };
  const abrirChat = () => { if (panel === "chat") { setPanel(""); return; } setRevision(null); setPanel("chat"); };
  const revisarVocabulario = async () => {
    if (panel === "revision") { cerrarRevision(); return; }
    setEditando(false);
    if (vista !== "documento") irA?.("informe");
    try {
      const r = await api.revisar(ref);
      setRevision({ hallazgos: r.hallazgos, propuestas: r.hallazgos.length ? null : [] });
      setPanel("revision");
      if (r.hallazgos.length) await lanzarPropuestas();
    } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };
  const aplicarPropuestas = async (lista: PropuestaCorreccion[]) => {
    setAplicandoRevision(true);
    let hechas = 0;
    for (const p of lista) {
      try { await api.aplicarCorreccion(ref, p.original, p.propuesta); hechas++; setRevision((x) => x && { ...x, propuestas: (x.propuestas ?? []).filter((q) => q !== p) }); }
      catch (e) { notificar({ texto: (e as Error).message, error: true }); }
    }
    if (hechas) { notificar({ texto: hechas === 1 ? "Corrección aplicada al informe." : `${hechas} correcciones aplicadas al informe.` }); await cargar(); await refrescarHallazgos(); }
    setAplicandoRevision(false);
  };
  const descartarPropuesta = (p: PropuestaCorreccion) => setRevision((x) => x && { ...x, propuestas: (x.propuestas ?? []).filter((q) => q !== p) });
  const resaltesDe = (id: string): Resalte[] | undefined => revision?.hallazgos.filter((h) => h.apartado === id).map((h) => ({
    texto: h.fragmento.replace(/…$/, ""), clase: `marca-revision marca-revision--${h.severidad}`, titulo: `${h.mensaje}${h.sugerencia ? ` → ${h.sugerencia}` : ""}` }));

  if (!inf) return <main className="main-layout"><div className="document-container">{cabecera}<EsqueletoDocumento bloques={4} /></div></main>;
  const hayInforme = inf.apartados.some((a) => a.markdown);
  return (
    <>
      <div className="toolbar">
        <div className="toolbar-title">
          <span>{exp.informe ? `${fmt.plural(exp.informe.n_conclusiones + exp.informe.n_sugerencias, "observación", "observaciones")} · ${fmt.plural(exp.informe.n_conclusiones, "recomendación", "recomendaciones")} · ${fmt.plural(exp.informe.n_sugerencias, "sugerencia de mejora", "sugerencias de mejora")} · v${exp.informe.versiones}` : "Sin informe"}</span>
          {exp.informe && <span className={`tag ${exp.informe.errores ? "tag-error" : "tag-success"}`}>{exp.informe.errores} errores · {exp.informe.avisos} avisos</span>}
          {exp.instrucciones_pendientes && <span className="tag tag-info">Instrucciones pendientes</span>}
        </div>
        <div className="toolbar-actions">
          {vista === "documento" && <button className="btn btn-ghost" onClick={guardar} disabled={modelo.activo || !hayInforme || !!revision}>{editando ? <><Check strokeWidth={1.5} /> Guardar cambios</> : <><Pencil strokeWidth={1.5} /> Editar</>}</button>}
          <button className={`btn ${panel === "revision" ? "btn-secondary" : "btn-ghost"}`} onClick={revisarVocabulario} disabled={!hayInforme || modelo.activo || editando} aria-pressed={panel === "revision"}
            title="Abre el panel de revisión: resalta en el informe lo que marcan las reglas de estilo y propone cómo cambiarlo">
            <SpellCheck strokeWidth={1.5} /> Revisar vocabulario{revision && revision.hallazgos.length > 0 && <span className="tag tag-warning" style={{ marginLeft: 4 }}>{revision.hallazgos.length}</span>}</button>
          <button className={`btn ${panel === "chat" ? "btn-secondary" : "btn-ghost"}`} onClick={abrirChat} disabled={editando} aria-pressed={panel === "chat"}
            title="Abre el chat para pedir cambios al informe (y el buzón de instrucciones)"><MessageSquare strokeWidth={1.5} /> Modificar con el chat</button>
          {editando && <button className="btn btn-ghost" onClick={() => { setEditando(false); cargar(); }}>Cancelar</button>}
          <MenuFlotante etiqueta={<><Sparkles strokeWidth={1.5} /> Modelo</>}>
            <button className="btn btn-ghost" onClick={() => correrModelo(() => api.corregir(ref, false))} disabled={modelo.activo || !hayInforme}>Corregir errores de estilo</button>
            <button className="btn btn-ghost" onClick={() => correrModelo(() => api.corregir(ref, true))} disabled={modelo.activo || !hayInforme}>Corregir también tono (avisos)</button>
            <button className="btn btn-ghost" onClick={() => correrModelo(() => api.condensar(ref, 0.85))} disabled={modelo.activo || !hayInforme}>Condensar un 15 %</button>
            <button className="btn btn-ghost" onClick={() => setMd(inf.markdown)}>Editar Markdown completo</button>
          </MenuFlotante>
          <button className="btn btn-ghost" onClick={deshacer} disabled={!exp.informe?.versiones} title="Vuelve a la versión anterior del informe"><History strokeWidth={1.5} /> Versión anterior</button>
        </div>
      </div>

      <main className="main-layout aparece">
        <div className={`document-container ${editando ? "editing" : ""}`}>
          {cabecera}
          {exp.ppt?.desactualizado && <Aviso tipo="aviso" accion={<button className="btn btn-ghost btn-ghost--inline small" onClick={() => irA?.("entrega")}>Ir a Exportación</button>}>El informe ha cambiado desde el último PowerPoint.</Aviso>}
          <div className="tab-row" role="tablist" aria-label="Vistas del informe">
            {VISTAS.map(([k, n]) => <button key={k} type="button" role="tab" className={`tab-item ${vista === k ? "active" : ""}`} aria-selected={vista === k} onClick={() => verVista(k)}>{n}</button>)}
          </div>
          {modelo.activo && <div className="result-box" style={{ marginBottom: 24 }}><span className="spinner" /> {modelo.job?.progreso || "Trabajando con el modelo…"} <button className="btn btn-ghost btn-ghost--inline small" style={{ marginLeft: 16 }} onClick={modelo.detener}>Detener</button></div>}
          {mensaje && <div style={{ marginBottom: 24 }}><ResultBox mensaje={mensaje.texto} error={mensaje.error} onClose={() => setMensaje(null)} /></div>}
          {vista === "cambios" && <Cambios c={cambios} contra={contra} setContra={(v) => { setCambios(null); setContra(v); }} />}
          {vista === "documento" && <>
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
            {!hayInforme && <Aviso accion={<><button className="btn btn-ghost btn-ghost--inline small" onClick={() => irA?.("contexto")}>Ir a Contexto</button><button className="btn btn-ghost btn-ghost--inline small" onClick={() => irA?.("observaciones")}>Ir a Observaciones</button></>}>
              El informe todavía está vacío: se llena con la introducción y el resumen (paso Contexto) y con las observaciones aprobadas (paso Observaciones).</Aviso>}
            {inf.apartados.filter((a) => a.markdown || (editando && (a.tipo === "introduccion" || a.tipo === "resumen"))).map((a) => (
              <SlideCard key={a.id} banda={banda(a)} nivel={a.tipo === "conclusion" || a.tipo === "sugerencia" ? a.nivel_riesgo : undefined} kicker={kicker(a)} titulo={a.titulo}
                tools={(a.tipo === "conclusion" || a.tipo === "sugerencia") ? <><span className="tag tag-neutral">{a.tipo === "conclusion" ? "Recomendación" : "Sugerencia de mejora"}</span><RiesgoTag nivel={a.nivel_riesgo} /></> : <span className="editable-badge">Editable</span>}>
                {editando && a.tipo === "introduccion" && <textarea className="textarea-doc" rows={16} value={edicion.introduccion} onChange={(e) => setEdicion({ ...edicion, introduccion: e.target.value })} aria-label="Introducción" />}
                {editando && a.tipo === "resumen" && <textarea className="textarea-doc" rows={12} value={edicion.resumen_ejecutivo} onChange={(e) => setEdicion({ ...edicion, resumen_ejecutivo: e.target.value })} aria-label="Resumen ejecutivo" />}
                {!(editando && (a.tipo === "introduccion" || a.tipo === "resumen")) && <Markdown texto={a.tipo === "conclusion" || a.tipo === "sugerencia" ? a.markdown.replace(/^###[^\n]*\n/, "") : a.markdown} resaltar={resaltesDe(a.id)} />}
              </SlideCard>))}
            {editando && <p className="small muted">Aquí se editan la introducción, el resumen y la evaluación global. El texto de cada observación se cambia con el asistente, con «Editar Markdown completo» o en el paso Observaciones (y se vuelve a pasar al informe).</p>}
          </>}
          {pie}
        </div>
        <aside className={`ai-drawer ${panel === "revision" ? "abierto" : ""}`} aria-label="Revisar vocabulario" aria-hidden={panel !== "revision"}>
          <div className="drawer-header">
            <div className="drawer-title"><SpellCheck size={18} strokeWidth={1.5} /> Revisar vocabulario</div>
            <div className="drawer-header__acciones"><button type="button" className="icon-btn" onClick={cerrarRevision} aria-label="Cerrar la revisión" title="Cerrar (quita el resaltado)"><X size={18} strokeWidth={1.5} /></button></div>
          </div>
          <div className="drawer-body">
            <PanelRevision revision={revision} proponiendo={proponer.activo} progreso={proponer.job?.progreso} aplicando={aplicandoRevision}
              apartados={inf.apartados} onRevisar={revisarVocabulario} onRepetir={lanzarPropuestas} onAplicar={aplicarPropuestas} onDescartar={descartarPropuesta} />
          </div>
        </aside>
        <PanelChat refExp={ref} exp={exp} abierto={panel === "chat"} onCerrar={() => setPanel("")} onCambio={cargar} deshacer={deshacer} verCambios={() => verVista("cambios")} irA={irA} />
      </main>

      {md !== null && (
        <Modal ancho titulo="Editar informe (Markdown completo)" onClose={() => setMd(null)} acciones={<><button className="btn btn-secondary" onClick={() => setMd(null)}>Cancelar</button><button className="btn btn-primary" onClick={guardarMd}>Guardar</button></>}>
          <p className="small muted">Respeta los títulos ##/###, la línea «A continuación, se muestran los detalles descriptivos…» y los párrafos **Recomendación N.1.**: es lo que permite exportar cada apartado como diapositiva.</p>
          <textarea className="textarea-notas" rows={28} value={md} onChange={(e) => setMd(e.target.value)} spellCheck={false} aria-label="Markdown del informe" />
        </Modal>)}
    </>
  );
};

// ---------------------------------------------------------------- últimos cambios (en lugar del documento)
const Cambios = ({ c, contra, setContra }: { c: ComparacionInforme | null; contra: string; setContra: (v: string) => void }) => {
  if (!c) return <div aria-busy="true" aria-label="Cargando"><span className="esqueleto esqueleto--titulo" style={{ width: "60%" }} /><span className="esqueleto esqueleto--bloque" /><span className="esqueleto esqueleto--bloque" /></div>;
  if (!c.contra) return <div className="empty">Todavía no hay cambios: cada cambio que hagas (chat, buzón, acta de reunión, edición manual o acciones del modelo) guarda la versión anterior y aquí se verá lo que ha cambiado.</div>;
  const cambiados = c.apartados.filter((a) => a.estado !== "igual");
  const iguales = c.apartados.length - cambiados.length;
  return (
    <div className="aparece">
      <div className="diff-resumen">
        <div className="diff-resumen__texto">
          <strong>{contra ? "Cambios acumulados" : "Último cambio"}</strong>
          <span className="tag tag-neutral">{c.contra.origen}</span>
          <span className="small muted">{c.contra.fecha.slice(0, 16)}</span>
          <DiffCuenta nuevas={c.lineas_nuevas} borradas={c.lineas_borradas} />
          <span className="small muted">{cambiados.length} {cambiados.length === 1 ? "apartado cambiado" : "apartados cambiados"}{iguales ? ` · ${iguales} sin cambios (ocultos)` : ""}</span>
        </div>
        <select className="select-input" value={contra} onChange={(e) => setContra(e.target.value)} aria-label="Comparar desde el cambio">
          <option value="">Solo el último cambio</option>
          {c.versiones.map((v) => <option key={v.nombre} value={v.nombre}>Desde {v.fecha.slice(0, 16)} · {v.origen}</option>)}
        </select>
      </div>
      {cambiados.length === 0
        ? <div className="empty">Sin diferencias con esa versión.</div>
        : cambiados.map((a) => (
          <SlideCard key={a.id} banda={a.tipo === "documento" ? "Documento" : banda(a)} nivel={a.tipo === "conclusion" || a.tipo === "sugerencia" ? a.nivel_riesgo : undefined}
            kicker={a.tipo === "documento" ? "Cambios fuera de los apartados" : kicker(a)} titulo={a.titulo}
            tools={<><CambioTag estado={a.estado} /><DiffCuenta nuevas={a.lineas_nuevas} borradas={a.lineas_borradas} /></>}>
            <DiffDocumento lineas={a.lineas} />
          </SlideCard>))}
    </div>
  );
};

// ---------------------------------------------------------------- revisión de vocabulario (pestaña del cajón)
const PanelRevision = ({ revision, proponiendo, progreso, aplicando, apartados, onRevisar, onRepetir, onAplicar, onDescartar }: {
  revision: { hallazgos: Hallazgo[]; propuestas: PropuestaCorreccion[] | null } | null; proponiendo: boolean; progreso?: string; aplicando: boolean;
  apartados: Apartado[]; onRevisar: () => void; onRepetir: () => void; onAplicar: (p: PropuestaCorreccion[]) => void; onDescartar: (p: PropuestaCorreccion) => void;
}) => {
  const nombre = (id: string | null) => {
    const a = apartados.find((x) => x.id === id);
    return a ? (a.tipo === "conclusion" || a.tipo === "sugerencia" ? `Observación ${fmt.dos(a.numero)} · ${a.titulo}` : a.titulo) : "Informe";
  };
  if (!revision) return (<>
    <p className="small muted">Resalta en el informe lo que marcan las reglas de estilo (vocabulario prohibido y primera persona: errores; tono, adjetivos y frases largas: avisos) y el modelo propone cómo quedaría cada párrafo. Nada se cambia hasta que lo apliques.</p>
    <div><button className="btn btn-secondary" onClick={onRevisar}><SpellCheck strokeWidth={1.5} /> Revisar vocabulario</button></div>
  </>);
  const { hallazgos, propuestas } = revision;
  const errores = hallazgos.filter((h) => h.severidad === "error").length;
  const conPropuesta = new Set((propuestas ?? []).map((p) => p.original));
  const sinPropuesta = propuestas ? hallazgos.filter((h) => !conPropuesta.has(h.parrafo ?? "")) : [];
  return (<>
    {hallazgos.length === 0
      ? <p className="small">Sin hallazgos: el informe cumple las reglas de estilo.</p>
      : <>
        <div className="row"><span className="tag tag-error">{fmt.plural(errores, "error", "errores")}</span><span className="tag tag-warning">{fmt.plural(hallazgos.length - errores, "aviso", "avisos")}</span></div>
        <p className="small muted">En el informe: <mark className="marca-revision marca-revision--error">rojo</mark> hay que cambiarlo; <mark className="marca-revision marca-revision--aviso">ámbar</mark> valorar según el contexto. Pasa el ratón por encima para ver el motivo.</p>
      </>}
    {proponiendo && <div className="small muted"><span className="spinner" /> {progreso || "El modelo está redactando las propuestas…"}</div>}
    {propuestas && propuestas.length > 0 && (
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="small muted">{fmt.plural(propuestas.length, "propuesta", "propuestas")} de cambio</span>
        <button className="btn btn-primary" onClick={() => onAplicar(propuestas)} disabled={aplicando}>{aplicando ? <><span className="spinner" /> Aplicando…</> : `Aplicar todas (${propuestas.length})`}</button>
      </div>)}
    <div className="agreements-list">
      {(propuestas ?? []).map((p) => (
        <div key={`${p.linea}-${p.original.slice(0, 24)}`} className="agreement-card">
          <div className="agreement-tag">{nombre(p.apartado)}</div>
          <ul className="summary-bullets" style={{ margin: "4px 0 8px" }}>{p.hallazgos.map((h, i) => <li key={i} className="small"><SeveridadTag severidad={h.severidad} /> «{h.fragmento}» — {h.mensaje}</li>)}</ul>
          <DiffDocumento lineas={p.lineas} />
          {p.errores_restantes.length > 0 && <p className="small" style={{ color: "var(--c-warning-fg)", marginTop: 8 }}>La propuesta aún contiene: {p.errores_restantes.join(", ")}.</p>}
          <div className="row" style={{ marginTop: 8 }}>
            <button className="btn btn-secondary" onClick={() => onAplicar([p])} disabled={aplicando}>Aplicar</button>
            <button className="btn btn-ghost" onClick={() => onDescartar(p)} disabled={aplicando}>Descartar</button>
          </div>
        </div>))}
    </div>
    {sinPropuesta.length > 0 && <>
      <div className="prompt-section-label">Sin propuesta de cambio</div>
      <p className="small muted">El modelo propone dejarlos como están (los avisos de tono se valoran según el contexto) o se descartó su propuesta.</p>
      <div className="agreements-list">{sinPropuesta.map((h, i) => (
        <div key={i} className="agreement-card" style={{ padding: 12 }}><div className="agreement-tag"><SeveridadTag severidad={h.severidad} /> {nombre(h.apartado ?? null)}</div><div className="small">«{h.fragmento}»</div><div className="agreement-meta">{h.mensaje}{h.sugerencia ? ` → ${h.sugerencia}` : ""}</div></div>))}</div>
    </>}
    {propuestas && hallazgos.length > 0 && !proponiendo && <div><button className="btn btn-ghost btn-ghost--inline small" onClick={onRepetir}>Proponer de nuevo</button></div>}
  </>);
};

// ---------------------------------------------------------------- «Modificar con el chat» (cajón propio, como en el generador de actas)
const PanelChat = ({ refExp, exp, abierto, onCerrar, onCambio, deshacer, verCambios, irA }: {
  refExp: string; exp: Expediente; abierto: boolean; onCerrar: () => void; onCambio: () => Promise<void>; deshacer: () => void;
  verCambios: () => void; irA: PropsPestana["irA"];
}) => {
  const notificar = useNotificar();
  const [modo, setModo] = useState<"chat" | "buzon">("chat");
  const [texto, setTexto] = useState("");
  const [chat, setChat] = useState<Burbuja[]>([]);
  const [instr, setInstr] = useState("");
  const [instrGuardada, setInstrGuardada] = useState("");
  const [resultado, setResultado] = useState<{ texto: string; error: boolean } | null>(null);
  const cambio = useJob<ResultadoCambios>();
  const buzon = useJob<ResultadoCambios>();
  const fin = useRef<HTMLDivElement>(null);
  const caja = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { api.instrucciones(refExp).then((r) => { setInstr(r.texto); setInstrGuardada(r.texto); }).catch(() => {}); }, [refExp, exp]);
  useEffect(() => { fin.current?.scrollIntoView({ block: "end" }); }, [chat, cambio.activo]);
  // la caja crece con el texto hasta 200 px (Intro envía, Mayús + Intro añade una línea)
  useEffect(() => { const c = caja.current; if (c) { c.style.height = "auto"; c.style.height = `${Math.min(c.scrollHeight, 200)}px`; } }, [texto]);
  useEffect(() => { if (abierto && modo === "chat") caja.current?.focus(); }, [abierto, modo]);

  const enviar = async (ev?: React.FormEvent) => {
    ev?.preventDefault();
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
    if (j.estado === "ok") { if (!soloPlan) { setInstr(""); setInstrGuardada(""); } await onCambio(); }
  };
  // con plan, una línea de resumen (la lista va debajo); sin plan (error, nada que aplicar), el mensaje de la API
  const resumenRespuesta = (m: Burbuja) => {
    const pl = m.r?.plan ?? [];
    if (m.error || !pl.length) return (m.mensaje ?? "").split("\n\n")[0];
    const ok = pl.filter((x) => /^(aplicado|insertado|eliminado)/.test(x.estado)).length;
    return `${ok} de ${fmt.plural(pl.length, "cambio aplicado", "cambios aplicados")} al informe.`;
  };
  const plan = (r: ResultadoCambios | null | undefined) => r?.plan?.length ? (
    <ul className="summary-bullets" style={{ marginTop: 8 }}>{r.plan.map((p, k) => <li key={k}><PlanTag estado={p.estado} /> {p.seccion} — {p.motivo}{p.detalle ? ` (${p.detalle})` : ""}</li>)}</ul>) : null;

  return (
    <aside className={`ai-drawer ${abierto ? "abierto" : ""}`} aria-label="Modificar con el chat" aria-hidden={!abierto}>
      <div className="drawer-header">
        <div className="drawer-title"><Sparkles size={18} strokeWidth={1.5} /> Modificar con el chat</div>
        <div className="drawer-header__acciones">
          <span className="tag tag-neutral">{exp.llm.split("(")[0].trim() || "modelo"}</span>
          <button type="button" className="icon-btn" onClick={onCerrar} aria-label="Cerrar el chat" title="Cerrar"><X size={18} strokeWidth={1.5} /></button>
        </div>
      </div>
      <div className="tab-row" role="tablist" style={{ marginBottom: 0, gap: 24 }}>
        {([["chat", "Pedir un cambio"], ["buzon", "Buzón de instrucciones"]] as ["chat" | "buzon", string][]).map(([k, n]) => (
          <button key={k} type="button" className={`tab-item ${modo === k ? "active" : ""}`} role="tab" aria-selected={modo === k} onClick={() => setModo(k)}>{n}</button>))}
      </div>
      <div className="drawer-body">
        {modo === "chat" && <>
          <div className="prompt-section-label">Prompts sugeridos</div>
          <div className="prompt-chips">{PROMPTS.map(([n, p]) => <button key={n} type="button" className="prompt-chip" onClick={() => { setTexto(p); caja.current?.focus(); }}>"{n}"</button>)}</div>
          <div className="prompt-section-label">Historial</div>
          <div className="chat-history">
            {chat.length === 0 && !cambio.activo && <div className="small muted">Un cambio por mensaje. Se aplica al momento sobre el informe y queda en el historial: puedes verlo en «Últimos cambios» y deshacerlo.</div>}
            {chat.map((m, i) => m.yo
              ? <div key={i} className="chat-bubble chat-bubble-user" style={{ whiteSpace: "pre-wrap" }}>{m.yo}</div>
              : <div key={i} className={`chat-bubble chat-bubble-ai ${m.error ? "error" : ""}`} style={m.error ? { borderLeftColor: "var(--c-error-fg)" } : undefined}>
                  <span style={{ whiteSpace: "pre-wrap" }}>{resumenRespuesta(m)}</span>{plan(m.r)}
                  {m.r?.pendientes?.length ? <div className="small muted" style={{ marginTop: 8 }}>Pendientes: {m.r.pendientes.join(" · ")}</div> : null}
                  {!m.error && i === chat.length - 1 && <div className="row" style={{ marginTop: 8 }}>
                    <button type="button" className="btn btn-ghost btn-ghost--inline small" onClick={verCambios}>Ver en «Últimos cambios»</button>
                    <button type="button" className="btn btn-ghost btn-ghost--inline small" onClick={deshacer}>Deshacer</button></div>}
                </div>)}
            {cambio.activo && <div className="chat-bubble chat-bubble-ai"><span className="spinner" /> {cambio.job?.progreso || "Aplicando…"}</div>}
            <div ref={fin} />
          </div>
        </>}
        {modo === "buzon" && <>
          <p className="small muted">Pega aquí los comentarios del Gerente, de la Directora o del área y aplícalos de una vez. Las reuniones nunca escriben en este buzón.</p>
          <textarea className="textarea-notas" rows={12} value={instr} onChange={(e) => setInstr(e.target.value)} aria-label="Instrucciones pendientes" />
          <div className="row">
            <button className="btn btn-ghost" onClick={guardarInstr} disabled={instr === instrGuardada}>Guardar</button>
            <button className="btn btn-secondary" onClick={() => aplicarBuzon(true)} disabled={buzon.activo || !instr.trim()}>Solo plan</button>
            <button className="btn btn-primary" onClick={() => aplicarBuzon(false)} disabled={buzon.activo || !instr.trim()}>{buzon.activo ? <><span className="spinner" /> Aplicando…</> : "Aplicar cambios"}</button>
          </div>
          {buzon.activo && <div className="small muted"><span className="spinner" /> {buzon.job?.progreso || "Aplicando…"}</div>}
          {resultado && <ResultBox mensaje={resultado.texto.split("\n\n")[0]} error={resultado.error} onClose={() => setResultado(null)} />}
          {plan(buzon.job?.resultado)}
          <p className="small muted">¿Cambios acordados en una reunión? <button type="button" className="btn btn-ghost btn-ghost--inline small" onClick={() => irA?.("reuniones")}>Reuniones</button></p>
        </>}
      </div>
      {modo === "chat" && (
        <div className="drawer-input-area">
          <form className="input-wrapper" onSubmit={enviar}>
            <textarea ref={caja} className="ai-input" rows={1} placeholder="Pide un cambio en el informe…" value={texto} onChange={(e) => setTexto(e.target.value)} disabled={cambio.activo} aria-label="Cambio a aplicar"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void enviar(); } }} />
            <button className="send-btn" type="submit" title="Enviar" aria-label="Enviar"><Send size={16} strokeWidth={1.5} /></button>
          </form>
          <div className="ai-input-ayuda">Intro para enviar · Mayús + Intro para nueva línea</div>
        </div>)}
    </aside>
  );
};
