import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, esperarJob } from "@/api";
import type { Acta, Job, Reunion as ReunionT } from "@/api";
import { Dropzone, JobButton, JobResult, Markdown, useNotificar } from "@/components/ui";
import type { JobResultado } from "@/components/ui";
import { useEstado } from "@/layout/layout";

const esAudio = (f: File | null) => /\.(mp3|wav|m4a|webm|ogg|oga|flac|mp4|mpga|mov|mkv|avi|m4v|wmv|mpe?g)$/i.test(f?.name ?? "");

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
  const [abierta, setAbierta] = useState<string | null>(null);
  const [aplicando, setAplicando] = useState(false);
  useEffect(() => { api.reuniones(ref).then(setAnteriores).catch(() => setAnteriores([])); }, [ref, acta]);

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
      {anteriores.length > 0 && (
        <div className="stack">
          <span className="section-title">Actas anteriores</span>
          <table className="table"><tbody>
            {anteriores.map((r) => <tr key={r.nombre} data-clickable onClick={() => setAbierta(abierta === r.nombre ? null : r.nombre)}><td className="detail">{r.fecha}</td><td>{r.nombre}</td></tr>)}
          </tbody></table>
          {abierta && <div className="panel"><Markdown texto={anteriores.find((r) => r.nombre === abierta)?.markdown ?? ""} /></div>}
        </div>
      )}
    </div>
  );
};
