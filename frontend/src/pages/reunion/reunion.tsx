import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { api, esperarJob } from "@/api";
import type { Acta, Job, Reunion as ReunionT, Transcripcion } from "@/api";
import { Trash2 } from "lucide-react";

import { Dropzone, JobButton, JobResult, Markdown, useNotificar } from "@/components/ui";
import type { JobResultado } from "@/components/ui";
import { useEstado } from "@/layout/layout";

const esAudio = (f: File | null) => /\.(mp3|wav|m4a|webm|ogg|oga|flac|mp4|mpga|mov|mkv|avi|m4v|wmv|mpe?g)$/i.test(f?.name ?? "");
const ACTUAL = "__transcripcion_actual__";   // fila del listado que representa la transcripción con voces

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
  const [sel, setSel] = useState<boolean[]>([]);
  const [resultado, setResultado] = useState<JobResultado | null>(null);
  const [anteriores, setAnteriores] = useState<ReunionT[]>([]);
  const [trans, setTrans] = useState<Transcripcion | null>(null);
  const [asig, setAsig] = useState<Record<string, { nombre: string; accion: string }>>({});
  const [guardar, setGuardar] = useState<Record<string, boolean>>({});
  const [etiquetando, setEtiquetando] = useState(false);
  const [abierta, setAbierta] = useState<string | null>(null);
  const [aplicando, setAplicando] = useState(false);
  // El borrador vive en el servidor (hablantes.md + meta.json): al adoptar el estado se
  // precargan nombres/acciones/casillas y `ultimoBorrador` evita autoguardados de más.
  const ultimoBorrador = useRef<string | null>(null);
  const adoptar = (t: Transcripcion) => {
    const a: Record<string, { nombre: string; accion: string }> = {};
    const g: Record<string, boolean> = {};
    for (const h of t.hablantes) { a[h.id] = { nombre: h.nombre, accion: h.accion }; g[h.id] = h.guardar; }
    setTrans(t); setAsig(a); setGuardar(g);
    ultimoBorrador.current = JSON.stringify([a, g]);
    if (t.hay_transcripcion && !t.etiquetada) setAbierta((prev) => prev ?? ACTUAL);
  };
  const cargarTrans = () => api.transcripcion(ref).then(adoptar).catch(() => setTrans(null));
  useEffect(() => { api.reuniones(ref).then(setAnteriores).catch(() => setAnteriores([])); }, [ref, acta]);
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
      const r = await api.etiquetar(ref, asig, voces);
      notificar({ texto: r.mensaje.split("\n")[0] });
      adoptar(r); recargar();
    } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
    finally { setEtiquetando(false); }
  };

  const aplicarSeleccion = async () => {
    if (!acta) return;
    const instrucciones = acta.cambios_texto.filter((_, i) => sel[i]).map((c) => `- ${c.instruccion}${c.solicitado_por ? ` [${c.solicitado_por}]` : ""}`).join("\n");
    if (!instrucciones) { notificar({ texto: "No hay cambios seleccionados." }); return; }
    setAplicando(true);
    try {
      await api.guardarInstrucciones(ref, instrucciones);
      const { job_id } = await api.aplicarCambios(ref, false);
      const j = await esperarJob(job_id);
      setResultado({ estado: j.estado === "ok" ? "ok" : "error", mensaje: j.mensaje, resultado: j.resultado });
      recargar();
    } catch (e) { notificar({ texto: (e as Error).message, error: true }); }
    finally { setAplicando(false); }
  };

  return (
    <div className="page">
      <div className="page__header">
        <div><h2 className="page__title">Reunión</h2><p className="page__subtitle">Pasa la transcripción de Teams o el audio de la reunión (se transcribe con el modelo). El sistema separa lo que cambia el texto del informe de lo que afecta al PPT, y lo que queda pendiente de dato.</p></div>
        <div className="page__actions">
          <label className="row detail"><input type="checkbox" checked={aplicar} onChange={(e) => setAplicar(e.target.checked)} /> Aplicar directamente los cambios de texto</label>
          <JobButton<Acta> primario etiqueta={esAudio(fichero) ? "Transcribir y analizar" : "Analizar la reunión"} disabled={!fichero} lanzar={() => { setSubida(0); setAvance(null); return api.reunion(ref, fichero!, aplicar, esAudio(fichero) ? hablantes : [], (pct) => setSubida(pct < 100 ? pct : null)); }}
            onTick={setAvance}
            onFin={(r) => { setAvance(null); setResultado(r); if (r.estado === "ok" && r.resultado) { setActa(r.resultado); setSel(r.resultado.cambios_texto.map(() => true)); recargar(); } }} />
        </div>
      </div>
      <Dropzone titulo="Transcripción o audio de la reunión" descripcion={fichero ? `Seleccionado: ${fichero.name}` : "Transcripción de Teams (.txt, .docx, .vtt) o grabación de audio o vídeo (.mp3, .wav, .m4a, .mp4, .mov, .webm…; del vídeo se extrae solo el audio) de la revisión con el Gerente, la Directora o el área."} formatos=".txt, .docx, .vtt, .md, .mp3, .wav, .m4a, .webm, .ogg, .mp4, .mov, .mkv" multiple={false} onFicheros={(f) => setFichero(f[0] ?? null)} />
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
          <div className="panel panel--muted"><span className="section-title">Resumen de la reunión</span><span className="body">{acta.resumen}</span></div>
          <span className="section-title">Cambios en el texto del informe ({acta.cambios_texto.length})</span>
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
          {!aplicar && acta.cambios_texto.length > 0 && (
            <div className="row row--between"><span className="detail">Las instrucciones también están en el buzón de Instrucciones del informe.</span>
              <button className="btn btn--primary" onClick={aplicarSeleccion} disabled={aplicando}>{aplicando ? <><span className="spinner" />Aplicando…</> : "Aplicar los seleccionados"}</button></div>
          )}
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
      )}
      <div className="panel stack">
        <span className="section-title">Identificación de hablantes (transcribir ahora, nombrar después)</span>
        <span className="detail">Alternativa al análisis directo: transcribe el audio con hablantes anónimos y, al terminar, la transcripción aparece abajo con las demás; ábrela para escuchar el clip de cada hablante, ponerle nombre y volcar la conversación a Instrucciones (Informe → Instrucciones → Aplicar cambios). Lo que escribas se guarda como borrador (sobrevive a recargar la página). Las voces que guardes se usan en la siguiente reunión de ESTE informe y se destruyen al archivar.</span>
        <div className="row">
          <JobButton etiqueta="Solo transcribir (nombrar hablantes)" disabled={!fichero || !esAudio(fichero)}
            lanzar={() => { setSubida(0); return api.transcribir(ref, fichero!, (pct) => setSubida(pct < 100 ? pct : null)); }}
            onTick={setAvance}
            onFin={(r) => { setAvance(null); setResultado(r); if (r.estado === "ok") { setAbierta(null); cargarTrans(); } }} />
          {trans?.hay_transcripcion && (
            <span className="detail">Transcripción actual: «{trans.origen}» {trans.etiquetada ? "(ya etiquetada)" : "(pendiente de nombrar hablantes — está abajo, con las transcripciones)"}</span>)}
        </div>
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
      </div>
      {(trans?.hay_transcripcion || anteriores.length > 0) && (
        <div className="stack">
          <span className="section-title">Actas y transcripciones</span>
          <table className="table"><tbody>
            {trans?.hay_transcripcion && (
              <tr key={ACTUAL} data-clickable onClick={() => setAbierta(abierta === ACTUAL ? null : ACTUAL)}>
                <td className="detail">{trans.fecha.slice(0, 16).replace("T", " ")}</td>
                <td><span className="label label--dark">Voces</span> {trans.origen}
                  <span className="detail">{trans.etiquetada ? " · etiquetada y volcada a Instrucciones" : " · pendiente de nombrar hablantes"}</span></td>
                <td style={{ textAlign: "right" }} />
              </tr>
            )}
            {anteriores.map((r) => (
              <tr key={r.nombre} data-clickable onClick={() => setAbierta(abierta === r.nombre ? null : r.nombre)}>
                <td className="detail">{r.fecha}</td>
                <td><span className="label">{r.tipo === "acta" ? "Acta" : "Transcripción"}</span> {r.nombre}</td>
                <td style={{ textAlign: "right" }}>
                  <button className="btn btn--ghost btn--small" aria-label={`Eliminar ${r.nombre}`}
                    onClick={async (e) => {
                      e.stopPropagation();
                      if (!window.confirm(`¿Eliminar ${r.tipo === "acta" ? "el acta" : "la transcripción"} «${r.nombre}»? No se puede deshacer.`)) return;
                      try { setAnteriores(await api.borrarReunion(ref, r.nombre)); if (abierta === r.nombre) setAbierta(null); notificar({ texto: `${r.nombre} eliminado.` }); }
                      catch (err) { notificar({ texto: (err as Error).message, error: true }); }
                    }}><Trash2 size={14} strokeWidth={1.5} />Eliminar</button>
                </td>
              </tr>
            ))}
          </tbody></table>
          {abierta === ACTUAL && trans && (
            <div className="panel stack">
              {!trans.etiquetada && (
                <div className="stack">
                  <span className="detail">Escucha el clip de cada hablante y ponle nombre (o márcalo como fusión/ignorar). El borrador
                    se guarda solo: puedes actualizar la página o seguir otro día, y también terminar desde la consola
                    (entrada/audio/hablantes.md). Al pulsar «Etiquetar» la conversación se vuelca a Instrucciones.</span>
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
                    {etiquetando ? <><span className="spinner" />Etiquetando…</> : "Etiquetar y volcar a Instrucciones"}</button></div>
                </div>
              )}
              <Markdown texto={trans.markdown} />
            </div>
          )}
          {abierta && abierta !== ACTUAL && <div className="panel"><Markdown texto={anteriores.find((r) => r.nombre === abierta)?.markdown ?? ""} /></div>}
        </div>
      )}
    </div>
  );
};
