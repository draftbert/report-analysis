import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { api, esperarJob } from "@/api";
import type { Acta, Job, Reunion as ReunionT, Transcripcion } from "@/api";
import { ArrowLeft, ChevronDown, ChevronUp, Info, Trash2 } from "lucide-react";

import { Dropzone, JobButton, JobResult, Markdown, useNotificar } from "@/components/ui";
import type { JobResultado } from "@/components/ui";
import { useEstado } from "@/layout/layout";

const esAudio = (f: File | null) => /\.(mp3|wav|m4a|webm|ogg|oga|flac|mp4|mpga|mov|mkv|avi|m4v|wmv|mpe?g)$/i.test(f?.name ?? "");
const ACTUAL = "__transcripcion_actual__";   // ítem del listado que representa la transcripción con voces
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

const AYUDA_ANALIZAR = "Transcribe el audio (o usa la transcripción) y extrae los cambios para el informe en un solo paso.";
const AYUDA_TRANSCRIBIR = "Solo transcribe e identifica las voces; tú les pones nombre y, al etiquetar, se genera el acta y los cambios van a Instrucciones (Informe → Instrucciones → Aplicar cambios).";

/** El acta como contenido principal: resumen + tarjetas de cambios (seleccionables y
 *  aplicables con la mecánica de correcciones de siempre), PPT, pendientes y acuerdos. */
const ActaView = ({ refExp, acta, ocultarAplicar }: { refExp: string; acta: Acta; ocultarAplicar?: boolean }) => {
  const { recargar } = useEstado();
  const notificar = useNotificar();
  const [sel, setSel] = useState<boolean[]>(acta.cambios_texto.map(() => true));
  const [aplicando, setAplicando] = useState(false);
  const [resultado, setResultado] = useState<JobResultado | null>(null);

  const aplicarSeleccion = async () => {
    const instrucciones = acta.cambios_texto.filter((_, i) => sel[i]).map((c) => `- ${c.instruccion}${c.solicitado_por ? ` [${c.solicitado_por}]` : ""}`).join("\n");
    if (!instrucciones) { notificar({ texto: "No hay cambios seleccionados." }); return; }
    setAplicando(true);
    try {
      await api.guardarInstrucciones(refExp, instrucciones);
      const { job_id } = await api.aplicarCambios(refExp, false);
      const j = await esperarJob(job_id);
      setResultado({ estado: j.estado === "ok" ? "ok" : "error", mensaje: j.mensaje, resultado: j.resultado });
      recargar();
    } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
    finally { setAplicando(false); }
  };

  return (
    <div className="stack">
      <div className="panel panel--muted"><span className="section-title">Resumen de la reunión</span><span className="body">{acta.resumen}</span></div>
      <span className="section-title">Cambios en el texto del informe ({acta.cambios_texto.length})</span>
      {acta.cambios_texto.length === 0 && <span className="detail">Ninguno.</span>}
      {acta.cambios_texto.map((c, i) => (
        <label key={i} className="acta-card">
          <input type="checkbox" checked={!!sel[i]} onChange={(e) => setSel(sel.map((s, k) => (k === i ? e.target.checked : s)))} />
          <div className="acta-card__body">
            <span className="label label--dark">{c.seccion}{c.solicitado_por ? ` · pide: ${c.solicitado_por}` : ""}</span>
            <span className="body">{c.que_cambiar}</span>
            <span className="detail">Instrucción: {c.instruccion}</span>
            {c.cita && <span className="acta-card__cita">«{c.cita}»</span>}
          </div>
        </label>
      ))}
      {!ocultarAplicar && acta.cambios_texto.length > 0 && (
        <div className="row row--between"><span className="detail">Las instrucciones también están en el buzón de Instrucciones del informe.</span>
          <button className="btn btn--primary" onClick={aplicarSeleccion} disabled={aplicando}>{aplicando ? <><span className="spinner" />Aplicando…</> : "Aplicar los seleccionados"}</button></div>
      )}
      <JobResult r={resultado} onClose={() => setResultado(null)} />
      <span className="section-title">Cambios en la presentación (PPT) — informativo ({acta.cambios_ppt.length})</span>
      {acta.cambios_ppt.length === 0 && <span className="detail">Ninguno.</span>}
      {acta.cambios_ppt.map((c, i) => (
        <div key={i} className="acta-card acta-card--muted"><div className="acta-card__body"><span className="body">{c.que_cambiar}</span><span className="detail">{c.solicitado_por ? `Pide: ${c.solicitado_por}. ` : ""}La presentación es beta: estos cambios se ajustan a mano.</span>{c.cita && <span className="acta-card__cita">«{c.cita}»</span>}</div></div>
      ))}
      <span className="section-title">Pendientes de dato o confirmación ({acta.pendientes.length})</span>
      {acta.pendientes.length === 0 ? <span className="detail">Ninguno.</span> : acta.pendientes.map((p, i) => <div key={i} className="acta-card"><span className="body">• {p}</span></div>)}
      <span className="section-title">Acuerdos que no cambian el informe ({acta.acuerdos_sin_cambio.length})</span>
      {acta.acuerdos_sin_cambio.length === 0 ? <span className="detail">Ninguno.</span> : acta.acuerdos_sin_cambio.map((p, i) => <div key={i} className="detail">• {p}</div>)}
    </div>
  );
};

export const Reunion = () => {
  const { ref = "" } = useParams();
  const { recargar } = useEstado();
  const notificar = useNotificar();
  const [fichero, setFichero] = useState<File | null>(null);
  const [hablantes, setHablantes] = useState<{ nombre: string; muestra: File | null }[]>([]);
  const [subida, setSubida] = useState<number | null>(null);
  const [avance, setAvance] = useState<Job<Acta> | null>(null);
  const [aplicar, setAplicar] = useState(false);
  const [acta, setActa] = useState<Acta | null>(null);
  const [resultado, setResultado] = useState<JobResultado | null>(null);
  const [anteriores, setAnteriores] = useState<ReunionT[]>([]);
  const [trans, setTrans] = useState<Transcripcion | null>(null);
  const [asig, setAsig] = useState<Record<string, { nombre: string; accion: string }>>({});
  const [guardar, setGuardar] = useState<Record<string, boolean>>({});
  const [etiquetando, setEtiquetando] = useState(false);
  const [abierta, setAbierta] = useState<string | null>(null);
  const [ayuda, setAyuda] = useState(false);
  // El borrador vive en el servidor (hablantes.md + meta.json): al adoptar el estado se
  // precargan nombres/acciones/casillas y `ultimoBorrador` evita autoguardados de más.
  const ultimoBorrador = useRef<string | null>(null);
  const adoptar = (t: Transcripcion) => {
    const a: Record<string, { nombre: string; accion: string }> = {};
    const g: Record<string, boolean> = {};
    for (const h of t.hablantes) { a[h.id] = { nombre: h.nombre, accion: h.accion }; g[h.id] = h.guardar; }
    setTrans(t); setAsig(a); setGuardar(g);
    ultimoBorrador.current = JSON.stringify([a, g]);
  };
  const cargarTrans = () => api.transcripcion(ref).then(adoptar).catch(() => setTrans(null));
  const cargarReuniones = () => api.reuniones(ref).then(setAnteriores).catch(() => setAnteriores([]));
  useEffect(() => { cargarReuniones(); }, [ref, acta]);
  useEffect(() => { cargarTrans(); }, [ref]);
  useEffect(() => {
    if (!trans?.hay_transcripcion || trans.etiquetada || ultimoBorrador.current === null) return;
    const s = JSON.stringify([asig, guardar]);
    if (s === ultimoBorrador.current) return;
    const t = setTimeout(() => {
      const ids = Object.entries(guardar).filter(([, v]) => v).map(([id]) => id);
      api.borradorTranscripcion(ref, asig, ids).then(() => { ultimoBorrador.current = s; }).catch(() => { /* se reintenta al siguiente cambio */ });
    }, 800);
    return () => clearTimeout(t);
  }, [asig, guardar, trans, ref]);

  const etiquetar = async () => {
    if (!trans) return;
    setEtiquetando(true);
    try {
      const voces = Object.entries(guardar).filter(([, v]) => v).map(([id]) => asig[id]?.nombre?.trim()).filter(Boolean) as string[];
      const { job_id } = await api.etiquetar(ref, asig, voces);
      const j = await esperarJob<Acta & Transcripcion>(job_id, (t) => setAvance(t as Job<Acta>));
      setAvance(null);
      setResultado({ estado: j.estado === "ok" ? "ok" : "error", mensaje: j.mensaje, resultado: j.resultado });
      if (j.estado === "ok") {
        if (j.resultado?.cambios_texto) setActa(j.resultado);
        cargarTrans(); recargar(); cargarReuniones();
      } else notificar({ texto: j.mensaje, error: true });
    } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
    finally { setEtiquetando(false); }
  };

  const eliminarFicheros = async (nombres: string[], etiquetaConfirm: string) => {
    if (!window.confirm(`¿Eliminar ${etiquetaConfirm}? No se puede deshacer.\n\n${nombres.join("\n")}`)) return;
    try {
      let lista = anteriores;
      for (const n of nombres) lista = await api.borrarReunion(ref, n);
      setAnteriores(lista);
      if (abierta && !lista.some((r) => r.origen === abierta)) setAbierta(null);
      notificar({ texto: `${nombres.length} fichero(s) eliminado(s).` });
    } catch (err) { notificar({ texto: (err as Error).message, error: true }); }
  };

  const pendiente = !!trans?.hay_transcripcion && !trans.etiquetada;
  const item = abierta && abierta !== ACTUAL ? anteriores.find((r) => r.origen === abierta) : undefined;

  return (
    <div className="page">
      {/* 1 ─ barra de acciones */}
      <div className="page__header">
        <div>
          <h2 className="page__title">Reunión</h2>
          <button className="btn btn--ghost btn--small" onClick={() => setAyuda(!ayuda)} aria-expanded={ayuda}>
            {ayuda ? <ChevronUp size={14} strokeWidth={1.5} /> : <ChevronDown size={14} strokeWidth={1.5} />}¿Cómo funciona?</button>
        </div>
        <div className="page__actions">
          <label className="row detail"><input type="checkbox" checked={aplicar} onChange={(e) => setAplicar(e.target.checked)} /> Aplicar directamente los cambios de texto</label>
          <span className="accion-hint" title={AYUDA_ANALIZAR}>
            <JobButton<Acta> primario etiqueta="Analizar reunión" disabled={!fichero} lanzar={() => { setSubida(0); setAvance(null); return api.reunion(ref, fichero!, aplicar, esAudio(fichero) ? hablantes : [], (pct) => setSubida(pct < 100 ? pct : null)); }}
              onTick={setAvance}
              onFin={(r) => { setAvance(null); setResultado(r); if (r.estado === "ok" && r.resultado) { setActa(r.resultado); recargar(); } }} />
            <Info size={14} strokeWidth={1.5} aria-label={AYUDA_ANALIZAR} />
          </span>
          <span className="accion-hint" title={AYUDA_TRANSCRIBIR}>
            <JobButton etiqueta="Transcribir y nombrar" disabled={!fichero || !esAudio(fichero)}
              lanzar={() => { setSubida(0); return api.transcribir(ref, fichero!, (pct) => setSubida(pct < 100 ? pct : null)); }}
              onTick={setAvance}
              onFin={(r) => { setAvance(null); setResultado(r); if (r.estado === "ok") { setAbierta(null); cargarTrans(); } }} />
            <Info size={14} strokeWidth={1.5} aria-label={AYUDA_TRANSCRIBIR} />
          </span>
        </div>
      </div>
      {ayuda && (
        <div className="panel panel--muted stack">
          <span className="detail"><strong>Analizar reunión.</strong> Pasa la transcripción de Teams o el audio de la reunión (se transcribe con el modelo). El sistema separa lo que cambia el texto del informe de lo que afecta al PPT, y lo que queda pendiente de dato.</span>
          <span className="detail"><strong>Qué se puede subir.</strong> Transcripción de Teams (.txt, .docx, .vtt) o grabación de audio o vídeo (.mp3, .wav, .m4a, .mp4, .mov, .webm…; del vídeo se extrae solo el audio) de la revisión con el Gerente, la Directora o el área. Puedes subir tantas reuniones como necesites: cada una queda abajo como un ítem con su acta y su transcripción.</span>
          <span className="detail"><strong>Transcribir y nombrar.</strong> Alternativa al análisis directo: transcribe el audio con hablantes anónimos y, al terminar, aparece una tarjeta para escuchar el clip de cada hablante y ponerle nombre. Al etiquetar, la conversación se analiza como una reunión: acta con quién pide cada cosa y cambios detectados a Instrucciones (Informe → Instrucciones → Aplicar cambios). Lo que escribas se guarda como borrador (sobrevive a recargar la página). Las voces que guardes se usan en la siguiente reunión de ESTE informe y se destruyen al archivar.</span>
        </div>
      )}

      {/* 2 ─ zona de subida */}
      <Dropzone titulo="Transcripción o audio de la reunión"
        descripcion={fichero ? `Seleccionado: ${fichero.name}` : "Transcripción de Teams o grabación de audio/vídeo (del vídeo se extrae solo el audio)."}
        formatos=".txt, .docx, .vtt, .md, .mp3, .wav, .m4a, .webm, .ogg, .mp4, .mov, .mkv" multiple={false} onFicheros={(f) => setFichero(f[0] ?? null)} />
      {esAudio(fichero) && (
        <div className="panel stack">
          <span className="section-title">Quién habla (opcional, máximo 4)</span>
          <span className="detail">El audio se transcribe con separación de hablantes. Si además añades una muestra de voz de 2–10 segundos de <strong>cada</strong> persona, la transcripción saldrá con sus nombres; si falta alguna muestra, saldrán como hablantes genéricos y los nombres se usarán solo como contexto del acta. Las muestras no se conservan.</span>
          {hablantes.map((h, i) => (
            <div key={i} className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <input className="input" style={{ maxWidth: 260 }} placeholder={`Nombre del hablante ${i + 1}`} value={h.nombre}
                onChange={(e) => setHablantes(hablantes.map((x, k) => (k === i ? { ...x, nombre: e.target.value } : x)))} />
              <label className="btn btn--ghost btn--small">{h.muestra ? `Muestra: ${h.muestra.name}` : "Añadir muestra de voz"}
                <input type="file" accept=".mp3,.wav,.m4a,.webm,.ogg" style={{ display: "none" }}
                  onChange={(e) => setHablantes(hablantes.map((x, k) => (k === i ? { ...x, muestra: e.target.files?.[0] ?? null } : x)))} /></label>
              <button className="btn btn--ghost btn--small" onClick={() => setHablantes(hablantes.filter((_, k) => k !== i))}>Quitar</button>
            </div>
          ))}
          {hablantes.length < 4 && <div><button className="btn btn--small" onClick={() => setHablantes([...hablantes, { nombre: "", muestra: null }])}>+ Añadir hablante</button></div>}
        </div>
      )}
      {subida !== null && (
        <div className="upload__item" aria-live="polite">
          <span className="upload__name">Subiendo {fichero?.name}</span><span className="upload__pct">{subida} %</span>
          <div className="progress" role="progressbar" aria-valuenow={subida} aria-valuemin={0} aria-valuemax={100}><div className="progress__bar" style={{ width: `${subida}%` }} /></div>
        </div>
      )}
      {avance?.progreso && (
        <div className="panel stack" aria-live="polite">
          <div className="row row--between"><span className="label">{avance.progreso}</span>
            {avance.progreso_pct != null && <span className="detail">{avance.progreso_pct} %</span>}</div>
          {avance.progreso_partes && avance.progreso_partes.length > 1 && (
            <>
              <div className="tramos" role="progressbar" aria-valuenow={avance.progreso_partes.filter((p) => p === "hecha").length} aria-valuemin={0} aria-valuemax={avance.progreso_partes.length}>
                {avance.progreso_partes.map((p, i) => <span key={i} className={`tramos__parte tramos__parte--${p}`} title={`Parte ${i + 1}: ${p.replace("_", " ")}`} />)}
              </div>
              <span className="detail">{avance.progreso_partes.filter((p) => p === "hecha").length} de {avance.progreso_partes.length} partes transcritas
                {avance.progreso_partes.includes("en_curso") ? ` · en curso: ${avance.progreso_partes.map((p, i) => (p === "en_curso" ? i + 1 : null)).filter(Boolean).join(" y ")}` : ""}</span>
            </>
          )}
          {!avance.progreso_partes?.length && avance.progreso_pct != null && (
            <div className="progress"><div className="progress__bar" style={{ width: `${avance.progreso_pct}%` }} /></div>
          )}
        </div>
      )}
      <JobResult r={resultado} onClose={() => setResultado(null)} />
      {acta && (
        <div className="stack">
          <div className="row row--between"><span className="section-title">Resultado del análisis</span>
            <button className="btn btn--ghost btn--small" onClick={() => setActa(null)}>Cerrar</button></div>
          <ActaView refExp={ref} acta={acta} ocultarAplicar={aplicar} />
        </div>
      )}

      {/* 3 ─ tarea activa: nombrar hablantes */}
      {pendiente && trans && (
        <div className="panel tarea stack">
          <div className="row row--between">
            <span className="section-title">Pendiente: nombrar hablantes</span>
            <span className="detail">«{trans.origen}» · {trans.fecha.slice(0, 16).replace("T", " ")}</span>
          </div>
          <span className="detail">Escucha el clip de cada hablante y ponle nombre (o márcalo como fusión/ignorar). Al pulsar «Etiquetar» la conversación se analiza como una reunión: acta con quién pide cada cosa (abajo, con las demás) y cambios detectados a Instrucciones.</span>
          {trans.hablantes.filter((h) => !h.conocido).map((h) => (
            <div key={h.id} className="panel" style={{ gap: 8 }}>
              <div className="row" style={{ gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <span className="label label--dark">{h.id}</span>
                <audio controls preload="none" style={{ height: 30 }} src={`/api/expedientes/${encodeURIComponent(ref)}/audio/hablantes/${h.clip}`} />
                <span className="detail">{Math.round(h.segundos)} s de habla</span>
              </div>
              <span className="detail">«{h.muestra}»</span>
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                <input className="input" style={{ maxWidth: 240 }} placeholder="Nombre" value={asig[h.id]?.nombre ?? ""}
                  onChange={(e) => setAsig({ ...asig, [h.id]: { nombre: e.target.value, accion: asig[h.id]?.accion ?? "" } })} />
                <select className="input" style={{ maxWidth: 260 }} value={asig[h.id]?.accion ?? ""}
                  onChange={(e) => setAsig({ ...asig, [h.id]: { nombre: asig[h.id]?.nombre ?? "", accion: e.target.value } })}>
                  <option value="">usar con este nombre</option>
                  {trans.hablantes.filter((o) => o.id !== h.id && !o.conocido).map((o) => (
                    <option key={o.id} value={`fusionar con ${o.id}`}>es la misma persona que {o.id}</option>))}
                  <option value="ignorar">ignorar (ruido, hablante irrelevante)</option>
                </select>
                <label className="row detail" style={{ gap: 6 }}>
                  <input type="checkbox" checked={!!guardar[h.id]} onChange={(e) => setGuardar({ ...guardar, [h.id]: e.target.checked })} />
                  guardar su voz para próximas reuniones</label>
              </div>
            </div>
          ))}
          {trans.hablantes.some((h) => h.conocido) && (
            <span className="detail">Ya nombrados por sus voces guardadas: {trans.hablantes.filter((h) => h.conocido).map((h) => h.id).join(", ")}.</span>)}
          <div><button className="btn btn--primary" onClick={etiquetar} disabled={etiquetando}>
            {etiquetando ? <><span className="spinner" />Etiquetando y generando el acta…</> : "Etiquetar y generar acta"}</button></div>
          <span className="detail tarea__pie">El borrador se guarda solo: puedes actualizar la página o seguir otro día, y también terminar desde la consola (entrada/audio/hablantes.md).</span>
        </div>
      )}
      {trans && trans.voces.length > 0 && (
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <span className="detail">Voces del informe:</span>
          {trans.voces.map((v) => (
            <span key={v.nombre} className="label">{v.nombre} · {Math.round(v.segundos)} s
              <button className="btn btn--ghost btn--small" style={{ marginLeft: 6 }}
                onClick={async () => setTrans(await api.borrarVoz(ref, v.nombre))}>×</button></span>))}
          <span className="detail">(se destruyen al archivar)</span>
        </div>
      )}

      {/* 4 ─ reuniones del informe: vista general de ítems o detalle de uno */}
      {(trans?.hay_transcripcion || anteriores.length > 0) && !abierta && (
        <div className="stack">
          <span className="section-title">Reuniones de este informe</span>
          <table className="table"><tbody>
            {trans?.hay_transcripcion && (
              <tr key={ACTUAL} data-clickable onClick={() => setAbierta(ACTUAL)}>
                <td className="detail">{trans.fecha.slice(0, 16).replace("T", " ")}</td>
                <td><span className="label label--dark">Voces</span> {trans.origen}
                  <span className="detail">{trans.etiquetada ? " · etiquetada" : " · pendiente de nombrar hablantes"}</span></td>
                <td style={{ textAlign: "right" }} />
              </tr>
            )}
            {anteriores.map((r) => (
              <tr key={r.origen} data-clickable onClick={() => setAbierta(r.origen)}>
                <td className="detail">{r.fecha}</td>
                <td>
                  <span className="body">{r.origen.replace(/_/g, " ")}</span>{" "}
                  {r.actas.length > 0 && <span className="tag">Acta{r.actas.length > 1 ? ` ×${r.actas.length}` : ""}</span>}{" "}
                  {r.transcripciones.length > 0 && <span className="tag">Transcripción{r.transcripciones.length > 1 ? ` ×${r.transcripciones.length}` : ""}</span>}{" "}
                  {r.actas[0]?.datos && <span className="detail">{r.actas[0].datos.cambios_texto.length} cambio(s) de texto · {r.actas[0].datos.pendientes.length} pendiente(s)</span>}
                </td>
                <td style={{ textAlign: "right" }}>
                  <button className="btn btn--ghost btn--small" aria-label={`Eliminar la reunión ${r.origen}`}
                    onClick={(e) => { e.stopPropagation(); eliminarFicheros([...r.actas.map((a) => a.nombre), ...r.transcripciones.map((t) => t.nombre)], `la reunión «${r.origen.replace(/_/g, " ")}» (acta y transcripciones)`); }}>
                    <Trash2 size={14} strokeWidth={1.5} />Eliminar</button>
                </td>
              </tr>
            ))}
          </tbody></table>
        </div>
      )}
      {abierta === ACTUAL && trans && (
        <div className="stack">
          <div className="row">
            <button className="btn btn--ghost btn--small" onClick={() => setAbierta(null)}><ArrowLeft size={14} strokeWidth={1.5} />Todas las reuniones</button>
            <span className="section-title">{trans.origen}</span>
            <span className="detail">{trans.fecha.slice(0, 16).replace("T", " ")} · duración {mmss(trans.duracion_s)} · {trans.hablantes.length} hablante(s) relevante(s)
              {trans.etiquetada ? " · etiquetada" : " · pendiente de nombrar hablantes (la tarjeta de arriba)"}</span>
          </div>
          <div className="visor"><Markdown texto={trans.markdown} /></div>
        </div>
      )}
      {item && (
        <div className="stack">
          <div className="row">
            <button className="btn btn--ghost btn--small" onClick={() => setAbierta(null)}><ArrowLeft size={14} strokeWidth={1.5} />Todas las reuniones</button>
            <span className="section-title">{item.origen.replace(/_/g, " ")}</span>
            <span className="detail">{item.fecha}</span>
          </div>
          {item.actas.length === 0 && (
            <span className="detail">Esta reunión aún no tiene acta: solo transcripción (abajo). Para generar el acta, sube el fichero de la transcripción con «Analizar reunión».</span>
          )}
          {item.actas[0] && (
            item.actas[0].datos
              ? <ActaView key={item.actas[0].nombre} refExp={ref} acta={item.actas[0].datos} />
              : <div className="stack"><span className="section-title">Acta ({item.actas[0].fecha})</span><Markdown texto={item.actas[0].markdown} /></div>
          )}
          {item.actas.slice(1).map((a) => (
            <div key={a.nombre} className="stack">
              <div className="row row--between"><span className="section-title">Acta anterior de esta reunión ({a.fecha})</span>
                <button className="btn btn--ghost btn--small" onClick={() => eliminarFicheros([a.nombre], `el acta «${a.nombre}»`)}><Trash2 size={14} strokeWidth={1.5} />Eliminar</button></div>
              <div className="visor"><Markdown texto={a.markdown} /></div>
            </div>
          ))}
          {item.transcripciones.map((t) => (
            <div key={t.nombre} className="stack">
              <div className="row row--between"><span className="section-title">Transcripción ({t.fecha})</span>
                <button className="btn btn--ghost btn--small" onClick={() => eliminarFicheros([t.nombre], `la transcripción «${t.nombre}»`)}><Trash2 size={14} strokeWidth={1.5} />Eliminar</button></div>
              <div className="visor"><Markdown texto={t.markdown} /></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
