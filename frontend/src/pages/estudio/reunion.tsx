/* Pestaña Reunión: transcripción o audio → acta (el modelo separa texto / PPT / pendientes / acuerdos);
   los cambios de texto se aplican DESDE el acta. Alternativa «Transcribir y nombrar» con clips por
   hablante. El buzón 03_instrucciones.md nunca se toca desde aquí. */
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, ChevronDown, ChevronUp, FileText, Sparkles, Trash2 } from "lucide-react";

import { api } from "@/api";
import type { Acta, Asignaciones, Reunion as ReunionT, Transcripcion } from "@/api";
import { Dropzone, Markdown, Modal, Progreso, ResultBox, Switch, useConfirmar, useNotificar } from "@/components/ui";
import { useJob } from "@/hooks/useJob";
import { esAudioOVideo, esTranscripcion, esVideo, fmt } from "@/lib/formato";

import type { PropsPestana } from "./estudio";

const FORMATOS = ".txt,.docx,.vtt,.md,.mp3,.wav,.m4a,.flac,.ogg,.oga,.webm,.mp4,.mov,.mkv,.avi,.m4v,.wmv,.mpg,.mpeg";
const tipoFichero = (f: File) => (esVideo(f.name) ? "Vídeo · se extrae solo el audio" : esAudioOVideo(f.name) ? "Audio" : esTranscripcion(f.name) ? "Transcripción" : "Formato no reconocido");
const ACTUAL = "__transcripcion_actual__";
type Modo = "analizar" | "transcribir";

// ---- transcripción como conversación (hora · quién · qué dijo) ----
const RE_SEG_CRUDA = /^- \[(\d+:\d{2})[–-][^\]]*\] ([^:]{1,60}): (.*)$/;
const RE_DIALOGO = /^([^:\n]{1,60}): (.*)$/;
const parsearDialogo = (texto: string) => {
  const filas: { hora?: string; quien: string; texto: string }[] = [];
  for (const linea of texto.split("\n")) {
    const l = linea.trim();
    if (!l || l.startsWith("#") || l.startsWith(">")) continue;
    let m = l.match(RE_SEG_CRUDA);
    if (m) { filas.push({ hora: m[1], quien: m[2].trim(), texto: m[3] }); continue; }
    if (l.startsWith("- ")) continue;
    m = l.match(RE_DIALOGO);
    if (m && !/^\d+$/.test(m[1].trim()) && !/^https?/i.test(m[1])) { filas.push({ quien: m[1].trim(), texto: m[2] }); continue; }
    if (filas.length) filas[filas.length - 1].texto += " " + l;
  }
  return filas;
};
const TranscriptView = ({ texto }: { texto: string }) => {
  const filas = parsearDialogo(texto);
  if (filas.length < 2) return <div className="executive-summary-box"><Markdown texto={texto} /></div>;
  return (
    <div className="transcript-stream">
      {filas.map((f, i) => (
        <div key={i} className="transcript-item">
          <div><div className="speaker-name">{f.quien}</div>{f.hora && <div className="speaker-time">{f.hora}</div>}</div>
          <div className="transcript-text">{f.texto}</div>
        </div>))}
    </div>
  );
};

/** El acta: resumen + cambios de texto seleccionables (se aplican directos con aplicar-cambios), PPT, pendientes y acuerdos. */
const ActaView = ({ refExp, acta, ocultarAplicar, recargar }: { refExp: string; acta: Acta; ocultarAplicar?: boolean; recargar: () => Promise<void> }) => {
  const notificar = useNotificar();
  const job = useJob();
  const [sel, setSel] = useState<boolean[]>(acta.cambios_texto.map(() => true));
  const [mensaje, setMensaje] = useState<{ texto: string; error: boolean } | null>(null);
  const aplicar = async () => {
    const instrucciones = acta.cambios_texto.filter((_, i) => sel[i]).map((c) => `- ${c.instruccion}${c.solicitado_por ? ` [${c.solicitado_por}]` : ""}`).join("\n");
    if (!instrucciones) { notificar({ texto: "No hay cambios seleccionados." }); return; }
    const j = await job.lanzar(() => api.aplicarCambios(refExp, false, instrucciones));
    setMensaje({ texto: j.mensaje, error: j.estado !== "ok" });
    if (j.estado === "ok") await recargar();
  };
  const bloque = (titulo: string, n: number) => <h2 className="section-header-sm" style={{ marginTop: 32 }}>{titulo} <span className="badge-status">{n}</span></h2>;
  return (
    <div>
      <div className="executive-summary-box">{acta.resumen}</div>
      {bloque("Cambios en el texto del informe", acta.cambios_texto.length)}
      <div className="options-grid">
        {acta.cambios_texto.length === 0 && <p className="small muted">Ninguno.</p>}
        {acta.cambios_texto.map((c, i) => (
          <button type="button" key={i} className={`option-card ${sel[i] ? "selected" : ""}`} style={{ alignItems: "flex-start" }} onClick={() => setSel(sel.map((s, k) => (k === i ? !s : s)))} aria-pressed={!!sel[i]}>
            <div className="option-info"><span className="agreement-tag">{c.seccion}{c.solicitado_por ? ` · pide: ${c.solicitado_por}` : ""}</span><span className="option-name">{c.que_cambiar}</span><span className="option-desc">Instrucción: {c.instruccion}</span>{c.cita && <span className="cita">«{c.cita}»</span>}</div>
            <div className="check-box" /></button>))}
      </div>
      {!ocultarAplicar && acta.cambios_texto.length > 0 && (
        <div className="row" style={{ justifyContent: "space-between", marginTop: 16 }}>
          <span className="small muted">Se aplican solo los cambios marcados, directamente sobre el informe (con snapshot en historial).</span>
          <button className="btn btn-primary" onClick={aplicar} disabled={job.activo}>{job.activo ? <><span className="spinner" /> Aplicando…</> : "Aplicar los seleccionados"}</button>
        </div>)}
      {job.activo && <Progreso texto={job.job?.progreso || "Aplicando cambios…"} pct={job.job?.progreso_pct} onDetener={job.detener} />}
      {mensaje && <div style={{ marginTop: 16 }}><ResultBox mensaje={mensaje.texto} error={mensaje.error} onClose={() => setMensaje(null)} /></div>}
      {bloque("Cambios en la presentación (PPT) — informativo", acta.cambios_ppt.length)}
      <div className="agreements-list">
        {acta.cambios_ppt.length === 0 && <p className="small muted">Ninguno.</p>}
        {acta.cambios_ppt.map((c, i) => <div key={i} className="topic-card"><div className="topic-title">{c.que_cambiar}</div><div className="topic-desc">{c.solicitado_por ? `Pide: ${c.solicitado_por}. ` : ""}La presentación se ajusta a mano.</div>{c.cita && <div className="cita">«{c.cita}»</div>}</div>)}
      </div>
      {bloque("Pendientes de dato o confirmación", acta.pendientes.length)}
      <ul className="summary-bullets">{acta.pendientes.length === 0 ? <p className="small muted">Ninguno.</p> : acta.pendientes.map((p, i) => <li key={i}>{p}</li>)}</ul>
      {bloque("Acuerdos que no cambian el informe", acta.acuerdos_sin_cambio.length)}
      <ul className="summary-bullets">{acta.acuerdos_sin_cambio.length === 0 ? <p className="small muted">Ninguno.</p> : acta.acuerdos_sin_cambio.map((p, i) => <li key={i}>{p}</li>)}</ul>
    </div>
  );
};

export const Reunion = ({ refExp, recargar }: PropsPestana) => {
  const notificar = useNotificar();
  const confirmar = useConfirmar();
  const job = useJob<Acta>();
  const [ayuda, setAyuda] = useState(false);
  const [fichero, setFichero] = useState<File | null>(null);
  const [subida, setSubida] = useState<number | null>(null);
  const [aplicar, setAplicar] = useState(false);
  const [acta, setActa] = useState<Acta | null>(null);
  const [mensaje, setMensaje] = useState<{ texto: string; error: boolean } | null>(null);
  const [anteriores, setAnteriores] = useState<ReunionT[]>([]);
  const [trans, setTrans] = useState<Transcripcion | null>(null);
  const [asig, setAsig] = useState<Asignaciones>({});
  const [guardar, setGuardar] = useState<Record<string, boolean>>({});
  const [abierta, setAbierta] = useState<string | null>(null);
  const [dupe, setDupe] = useState<{ modo: Modo; aviso: string } | null>(null);
  const [procesando, setProcesando] = useState<Modo | "etiquetar" | null>(null);

  // El borrador del etiquetado vive en el servidor: `ultimoBorrador` evita autoguardados de más.
  const ultimoBorrador = useRef<string | null>(null);
  const adoptar = (t: Transcripcion) => {
    const a: Asignaciones = {}; const g: Record<string, boolean> = {};
    for (const h of t.hablantes) { a[h.id] = { nombre: h.nombre, accion: h.accion }; g[h.id] = h.guardar; }
    setTrans(t); setAsig(a); setGuardar(g);
    ultimoBorrador.current = JSON.stringify([a, g]);
  };
  const cargarTrans = useCallback(() => api.transcripcion(refExp).then(adoptar).catch(() => setTrans(null)), [refExp]);
  const cargarReuniones = useCallback(() => api.reuniones(refExp).then(setAnteriores).catch(() => setAnteriores([])), [refExp]);
  useEffect(() => { cargarReuniones(); cargarTrans(); }, [cargarReuniones, cargarTrans]);
  useEffect(() => {
    if (!trans?.hay_transcripcion || trans.etiquetada || ultimoBorrador.current === null) return;
    const s = JSON.stringify([asig, guardar]);
    if (s === ultimoBorrador.current) return;
    const t = setTimeout(() => {
      const ids = Object.entries(guardar).filter(([, v]) => v).map(([id]) => id);
      api.borradorTranscripcion(refExp, asig, ids).then(() => { ultimoBorrador.current = s; }).catch(() => { /* se reintenta al siguiente cambio */ });
    }, 800);
    return () => clearTimeout(t);
  }, [asig, guardar, trans, refExp]);

  const procesar = async (modo: Modo, repetir = false) => {
    if (!fichero) return;
    setProcesando(modo); setSubida(0); setMensaje(null);
    const alSubir = (pct: number) => setSubida(pct < 100 ? pct : null);
    const j = await job.lanzar(() => modo === "analizar" ? api.reunion(refExp, fichero, aplicar, alSubir, repetir) : api.transcribir(refExp, fichero, alSubir, repetir));
    setProcesando(null); setSubida(null);
    if (j.estado === "ok") {
      notificar({ texto: j.mensaje.split("\n")[0] });
      setMensaje({ texto: j.mensaje, error: false });
      if (modo === "analizar" && j.resultado?.cambios_texto) setActa(j.resultado);
      if (modo === "transcribir") { setAbierta(null); cargarTrans(); }
      setFichero(null); await recargar(); cargarReuniones();
    } else if (j.mensaje.includes("Reunión repetida") && !repetir) {
      setDupe({ modo, aviso: j.mensaje.split(/ (?:Si quieres|Transcribirla de nuevo)/)[0].replace(/^⚠\s*/, "") });
    } else setMensaje({ texto: j.mensaje, error: true });
  };
  const etiquetar = async () => {
    setProcesando("etiquetar"); setMensaje(null);
    const voces = Object.entries(guardar).filter(([, v]) => v).map(([id]) => asig[id]?.nombre?.trim()).filter(Boolean) as string[];
    const j = await job.lanzar(() => api.etiquetar(refExp, asig, voces));
    setProcesando(null);
    if (j.estado === "ok") {
      setMensaje({ texto: j.mensaje, error: false });
      if (j.resultado?.cambios_texto) setActa(j.resultado);
      cargarTrans(); await recargar(); cargarReuniones();
    } else setMensaje({ texto: j.mensaje, error: true });
  };
  const detener = async () => {
    if (!(await confirmar({ titulo: "Detener el procesamiento", peligro: true, accion: "Detener", cuerpo: "Lo hecho en esta ejecución se descarta (se corta al acabar la parte en curso)." }))) return;
    try { await job.detener(); } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };
  const eliminarFicheros = async (nombres: string[], que: string) => {
    if (!(await confirmar({ titulo: "Eliminar", peligro: true, accion: "Eliminar", cuerpo: `Se eliminará ${que}. No se puede deshacer.\n\n${nombres.join("\n")}` }))) return;
    try {
      let lista = anteriores;
      for (const n of nombres) lista = await api.borrarReunion(refExp, n);
      setAnteriores(lista);
      if (abierta && !lista.some((r) => r.origen === abierta)) setAbierta(null);
      notificar({ texto: `${nombres.length} fichero(s) eliminado(s).` });
    } catch (err) { notificar({ texto: (err as Error).message, error: true }); }
  };
  const borrarVoz = async (nombre: string) => {
    if (!(await confirmar({ titulo: "Eliminar voz guardada", peligro: true, accion: "Eliminar", cuerpo: `Se elimina la voz de «${nombre}» de este informe.` }))) return;
    try { setTrans(await api.borrarVoz(refExp, nombre)); } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };

  const pendiente = !!trans?.hay_transcripcion && !trans.etiquetada;
  const item = abierta && abierta !== ACTUAL ? anteriores.find((r) => r.origen === abierta) : undefined;
  const conocido = fichero ? tipoFichero(fichero) !== "Formato no reconocido" : false;

  return (
    <div>
      <h2 className="section-header-sm">Reuniones
        <button className="btn btn-ghost" onClick={() => setAyuda(!ayuda)} aria-expanded={ayuda}>{ayuda ? <ChevronUp strokeWidth={1.5} /> : <ChevronDown strokeWidth={1.5} />} ¿Cómo funciona?</button></h2>
      {ayuda && (
        <div className="topic-card" style={{ marginBottom: 24 }}>
          <p className="small" style={{ marginBottom: 8 }}><strong>Analizar reunión.</strong> Pasa la transcripción de Teams o el audio de la reunión (se transcribe con el modelo). El sistema separa lo que cambia el texto del informe de lo que afecta al PPT y lo que queda pendiente de dato. Los cambios de texto se aplican desde el acta, marcando los que quieras.</p>
          <p className="small" style={{ marginBottom: 8 }}><strong>Qué se puede subir.</strong> Transcripción (.txt, .docx, .vtt) o grabación de audio o vídeo (.mp3, .wav, .m4a, .mp4, .mov, .webm…; del vídeo se extrae solo el audio). Cada reunión queda abajo como un ítem con su acta y su transcripción.</p>
          <p className="small"><strong>Transcribir y nombrar.</strong> Transcribe el audio con hablantes anónimos y muestra un clip por hablante para ponerle nombre. Al etiquetar, la conversación se analiza como una reunión y se genera su acta. El borrador se guarda solo. Las voces guardadas valen para las siguientes reuniones de ESTE informe y se destruyen al archivar.</p>
        </div>)}

      <Dropzone titulo="Transcripción o audio de la reunión" accept={FORMATOS} onFichero={setFichero}
        descripcion="Transcripción de Teams (.txt, .docx, .vtt) o grabación de audio/vídeo; del vídeo se extrae solo el audio." />
      {fichero && (
        <div className="uploaded-file-preview" aria-live="polite">
          <div className="file-info"><FileText size={20} strokeWidth={1.5} /><div style={{ minWidth: 0 }}><div className="file-name">{fichero.name}</div><div className="file-size">{fmt.bytes(fichero.size)} · {tipoFichero(fichero)}</div></div></div>
          <button type="button" className="btn btn-ghost btn-ghost--inline small" onClick={() => setFichero(null)} disabled={!!procesando}>Quitar</button>
        </div>)}
      {fichero && !conocido && <p className="small" style={{ color: "var(--c-error-fg)", marginTop: 8 }}>Formato no reconocido. Admitidos: {FORMATOS.replace(/,/g, ", ")}.</p>}
      <div className="switch-container" style={{ marginTop: 16 }}>
        <span className="switch-label-text">Aplicar directamente los cambios de texto (sin pasar por la selección en el acta)</span>
        <Switch checked={aplicar} onChange={setAplicar} label="Aplicar directamente los cambios de texto" />
      </div>
      <div className="row" style={{ marginBottom: 24 }}>
        <button className="btn btn-primary" disabled={!fichero || !conocido || !!procesando} onClick={() => procesar("analizar")} title="Transcribe el audio (o usa la transcripción) y extrae los cambios para el informe en un solo paso.">
          {procesando === "analizar" ? <><span className="spinner" /> Analizando…</> : <><Sparkles strokeWidth={1.5} /> Analizar reunión</>}</button>
        <button className="btn btn-secondary" disabled={!fichero || !esAudioOVideo(fichero.name) || !!procesando} onClick={() => procesar("transcribir")} title="Solo transcribe e identifica las voces; tú les pones nombre y al etiquetar se genera el acta.">
          {procesando === "transcribir" ? <><span className="spinner" /> Transcribiendo…</> : <><Sparkles strokeWidth={1.5} /> Transcribir y nombrar</>}</button>
      </div>
      {subida !== null && <><div className="progress-bar"><div style={{ width: `${subida}%` }} /></div><p className="small muted">Subiendo {fichero?.name}… {subida} %</p></>}
      {job.activo && subida === null && <Progreso texto={job.job?.progreso || "Procesando…"} pct={job.job?.progreso_pct} partes={job.job?.progreso_partes} onDetener={detener} />}
      {mensaje && <div style={{ marginBottom: 24 }}><ResultBox mensaje={mensaje.texto} error={mensaje.error} onClose={() => setMensaje(null)} /></div>}
      {acta && (
        <section className="doc-section">
          <h2 className="section-header-sm">Resultado del análisis <button className="btn btn-ghost" onClick={() => setActa(null)}>Cerrar</button></h2>
          <ActaView refExp={refExp} acta={acta} ocultarAplicar={aplicar} recargar={recargar} />
        </section>)}

      {pendiente && trans && (
        <section className="doc-section">
          <h2 className="section-header-sm">Pendiente: nombrar hablantes <span className="small muted">«{trans.origen}» · {fmt.fechaHora(trans.fecha)}</span></h2>
          <p className="small muted" style={{ marginBottom: 12 }}>Escucha el clip de cada hablante y ponle nombre (o márcalo como fusión o ignorar). Al pulsar «Etiquetar» la conversación se analiza como una reunión y se genera su acta. El borrador se guarda solo.</p>
          <div className="table-wrapper"><table className="ids-table ids-table--muted hablantes-table">
            <thead><tr><th>ID</th><th>Escuchar</th><th>Muestra</th><th>Habla</th><th style={{ width: 200 }}>Nombre</th><th>Acción</th><th>Guardar voz</th></tr></thead>
            <tbody>
              {trans.hablantes.filter((h) => !h.conocido).map((h) => (
                <tr key={h.id}>
                  <td className="mono small">{h.id}</td>
                  <td><audio controls preload="none" src={api.urlClip(refExp, h.clip)} /></td>
                  <td className="small">«{h.muestra}»</td>
                  <td className="num small">{fmt.mmss(h.segundos)}</td>
                  <td><input className="text-input text-input--small" placeholder="Nombre" value={asig[h.id]?.nombre ?? ""} onChange={(e) => setAsig({ ...asig, [h.id]: { nombre: e.target.value, accion: asig[h.id]?.accion ?? "" } })} aria-label={`Nombre de ${h.id}`} /></td>
                  <td><select className="select-input text-input--small" value={asig[h.id]?.accion ?? ""} onChange={(e) => setAsig({ ...asig, [h.id]: { nombre: asig[h.id]?.nombre ?? "", accion: e.target.value } })} aria-label={`Acción para ${h.id}`}>
                    <option value="">usar con este nombre</option>
                    {trans.hablantes.filter((o) => o.id !== h.id && !o.conocido).map((o) => <option key={o.id} value={`fusionar con ${o.id}`}>es la misma persona que {o.id}</option>)}
                    <option value="ignorar">ignorar (ruido, irrelevante)</option>
                  </select></td>
                  <td><Switch checked={!!guardar[h.id]} onChange={(v) => setGuardar({ ...guardar, [h.id]: v })} label={`Guardar la voz de ${h.id}`} /></td>
                </tr>))}
            </tbody></table></div>
          {trans.hablantes.some((h) => h.conocido) && <p className="small muted" style={{ marginTop: 8 }}>Ya nombrados por sus voces guardadas: {trans.hablantes.filter((h) => h.conocido).map((h) => h.id).join(", ")}.</p>}
          <div style={{ marginTop: 16 }}><button className="btn btn-primary" onClick={etiquetar} disabled={!!procesando}>{procesando === "etiquetar" ? <><span className="spinner" /> Etiquetando y generando el acta…</> : "Etiquetar y generar acta"}</button></div>
        </section>)}
      {trans && trans.voces.length > 0 && (
        <div className="tag-container" style={{ marginBottom: 24 }}>
          <span className="small muted">Voces del informe (se destruyen al archivar):</span>
          {trans.voces.map((v) => <span key={v.nombre} className="chip">{v.nombre} · {Math.round(v.segundos)} s <button type="button" className="chip-remove" aria-label={`Eliminar voz de ${v.nombre}`} onClick={() => borrarVoz(v.nombre)}>×</button></span>)}
        </div>)}

      {(pendiente || anteriores.length > 0) && !abierta && (
        <section className="doc-section">
          <h2 className="section-header-sm">Reuniones de este informe</h2>
          <div className="table-wrapper"><table className="ids-table">
            <thead><tr><th>Fecha</th><th>Reunión</th><th>Contenido</th><th className="col-right">Acciones</th></tr></thead>
            <tbody>
              {pendiente && trans && (
                <tr key={ACTUAL}><td>{fmt.fechaHora(trans.fecha)}</td><td className="td-title">{trans.origen}</td><td><span className="tag tag-warning">Pendiente de nombrar hablantes</span></td>
                  <td className="col-right td-acciones"><button className="btn btn-ghost" onClick={() => setAbierta(ACTUAL)}>Ver transcripción</button></td></tr>)}
              {anteriores.map((r) => (
                <tr key={r.origen}>
                  <td>{r.fecha}</td>
                  <td className="td-title">{r.origen.replace(/_/g, " ")}</td>
                  <td><span className="row">
                    {r.actas.length > 0 && <span className="tag tag-success">Acta{r.actas.length > 1 ? ` ×${r.actas.length}` : ""}</span>}
                    {r.transcripciones.length > 0 && <span className="tag tag-neutral">Transcripción{r.transcripciones.length > 1 ? ` ×${r.transcripciones.length}` : ""}</span>}
                    {r.actas[0]?.datos && <span className="small muted">{r.actas[0].datos.cambios_texto.length} cambio(s) de texto · {r.actas[0].datos.pendientes.length} pendiente(s)</span>}</span></td>
                  <td className="col-right td-acciones">
                    <button className="btn btn-ghost" onClick={() => setAbierta(r.origen)}>Ver</button>
                    <button className="icon-btn" aria-label={`Eliminar la reunión ${r.origen}`} title="Eliminar" onClick={() => eliminarFicheros([...r.actas.map((a) => a.nombre), ...r.transcripciones.map((t) => t.nombre)], `la reunión «${r.origen.replace(/_/g, " ")}» (acta y transcripciones)`)}><Trash2 size={16} strokeWidth={1.5} /></button>
                  </td>
                </tr>))}
            </tbody></table></div>
        </section>)}
      {abierta === ACTUAL && trans && (
        <section className="doc-section">
          <h2 className="section-header-sm"><span className="row"><button className="btn btn-ghost" onClick={() => setAbierta(null)}><ArrowLeft strokeWidth={1.5} /> Todas las reuniones</button>{trans.origen}</span>
            <span className="small muted">{fmt.fechaHora(trans.fecha)} · {fmt.mmss(trans.duracion_s)} · {trans.hablantes.length} hablante(s){trans.etiquetada ? " · etiquetada" : " · pendiente de nombrar"}</span></h2>
          <TranscriptView texto={trans.markdown} />
        </section>)}
      {item && (
        <section className="doc-section">
          <h2 className="section-header-sm"><span className="row"><button className="btn btn-ghost" onClick={() => setAbierta(null)}><ArrowLeft strokeWidth={1.5} /> Todas las reuniones</button>{item.origen.replace(/_/g, " ")}</span><span className="small muted">{item.fecha}</span></h2>
          {item.actas.length === 0 && <p className="small muted" style={{ marginBottom: 16 }}>Esta reunión aún no tiene acta: solo transcripción. Para generar el acta, sube el fichero con «Analizar reunión».</p>}
          {item.actas[0] && (item.actas[0].datos
            ? <ActaView key={item.actas[0].nombre} refExp={refExp} acta={item.actas[0].datos} recargar={recargar} />
            : <div className="executive-summary-box"><Markdown texto={item.actas[0].markdown} /></div>)}
          {item.actas.slice(1).map((a) => (
            <div key={a.nombre} style={{ marginTop: 32 }}>
              <h2 className="section-header-sm">Acta anterior ({a.fecha}) <button className="btn btn-ghost" onClick={() => eliminarFicheros([a.nombre], `el acta «${a.nombre}»`)}><Trash2 strokeWidth={1.5} /> Eliminar</button></h2>
              <div className="executive-summary-box"><Markdown texto={a.markdown} /></div>
            </div>))}
          {item.transcripciones.map((t) => (
            <div key={t.nombre} style={{ marginTop: 32 }}>
              <h2 className="section-header-sm">Transcripción ({t.fecha}) <button className="btn btn-ghost" onClick={() => eliminarFicheros([t.nombre], `la transcripción «${t.nombre}»`)}><Trash2 strokeWidth={1.5} /> Eliminar</button></h2>
              <TranscriptView texto={t.markdown} />
            </div>))}
        </section>)}
      {dupe && (
        <Modal titulo="Reunión ya procesada" onClose={() => setDupe(null)} acciones={<><button className="btn btn-secondary" onClick={() => setDupe(null)}>Cancelar</button><button className="btn btn-primary" onClick={() => { const m = dupe.modo; setDupe(null); procesar(m, true); }}>Volver a procesarla</button></>}>
          <p>{dupe.aviso}</p>
          {dupe.modo === "transcribir" && <p className="small muted">Transcribirla de nuevo cuesta lo mismo que la primera vez.</p>}
          <p className="small muted">Su resultado anterior sigue abajo, en «Reuniones de este informe»; si no era tu intención, cancela.</p>
        </Modal>)}
    </div>
  );
};
