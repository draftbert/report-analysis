/* Alta de informe (patrón 3 de la guía): a la izquierda los documentos de entrada (contexto y papeles
   de trabajo), a la derecha los metadatos del expediente y el botón de creación con progreso de subida. */
import { useState } from "react";
import { FileText, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api";
import type { Carpeta } from "@/api";
import { Dropzone, useNotificar } from "@/components/ui";
import { Cabecera } from "@/layout/layout";
import { FORMATOS_DOCUMENTO, esDocumento, fmt, tipoMedio } from "@/lib/formato";

import "./nuevo.css";

const FORMATOS = FORMATOS_DOCUMENTO;
const DESCRIPCION: Record<Carpeta, string> = {
  contexto: "Design thinking, memorando de planificación, motivo, riesgos a cubrir, alcance previsto y magnitudes. Opcional: alimenta la introducción y el resumen ejecutivo.",
  papeles_trabajo: "Un fichero por prueba (o el papel de trabajo final con todas): contexto, objetivo, pruebas realizadas y conclusiones. Es la fuente de las conclusiones. Las hojas de Excel se envían resumidas.",
};

export const Nuevo = () => {
  const navigate = useNavigate();
  const notificar = useNotificar();
  const [modo, setModo] = useState<Carpeta>("papeles_trabajo");
  const [ficheros, setFicheros] = useState<Record<Carpeta, File[]>>({ contexto: [], papeles_trabajo: [] });
  const [referencia, setReferencia] = useState("");
  const [nombre, setNombre] = useState("");
  const [fecha, setFecha] = useState("");
  const [destinatario, setDestinatario] = useState("");
  const [distribucion, setDistribucion] = useState<string[]>([]);
  const [enviando, setEnviando] = useState(false);
  const [subida, setSubida] = useState<{ nombre: string; pct: number } | null>(null);

  // Se valida al añadir (al arrastrar, el navegador no aplica `accept`): nada se sube para fallar al final.
  const anadir = (carpeta: Carpeta, todos: File[]) => {
    const grab = todos.filter((f) => tipoMedio(f)).map((f) => f.name);
    const otros = todos.filter((f) => !tipoMedio(f) && !esDocumento(f.name)).map((f) => f.name);
    if (grab.length) notificar({ texto: `${grab.join(", ")}: es una grabación de reunión. Crea el informe y súbela después en Reuniones.`, error: true });
    else if (otros.length) notificar({ texto: `${otros.join(", ")}: formato no admitido. Admitidos: ${FORMATOS.replace(/,/g, ", ")}.`, error: true });
    const fs = todos.filter((f) => esDocumento(f.name));
    setFicheros((prev) => ({ ...prev, [carpeta]: [...prev[carpeta], ...fs.filter((f) => !prev[carpeta].some((p) => p.name === f.name && p.size === f.size))] }));
  };
  const quitar = (carpeta: Carpeta, i: number) => setFicheros((prev) => ({ ...prev, [carpeta]: prev[carpeta].filter((_, j) => j !== i) }));
  const addDestinatario = () => { const v = destinatario.trim().replace(/,$/, ""); if (v && !distribucion.includes(v)) setDistribucion([...distribucion, v]); setDestinatario(""); };
  const total = ficheros.contexto.length + ficheros.papeles_trabajo.length;

  const enviar = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setEnviando(true);
    try {
      const exp = await api.crearExpediente({ referencia: referencia.trim(), nombre: nombre.trim(), fecha: fecha.trim(), distribucion });
      for (const carpeta of ["contexto", "papeles_trabajo"] as Carpeta[]) {
        if (ficheros[carpeta].length) await api.subir(exp.referencia, carpeta, ficheros[carpeta], (n, pct) => setSubida({ nombre: n, pct }));
      }
      notificar({ texto: `Informe ${exp.referencia} creado${total ? ` con ${total} documento(s)` : ""}.` });
      navigate(`/informes/${encodeURIComponent(exp.referencia)}`);
    } catch (e) { notificar({ texto: (e as Error).message, error: true }); setEnviando(false); setSubida(null); }
  };

  const lista = (carpeta: Carpeta) => ficheros[carpeta].map((f, i) => (
    <div className="uploaded-file-preview" key={f.name + f.size}>
      <div className="file-info"><FileText size={20} strokeWidth={1.5} /><div style={{ minWidth: 0 }}><div className="file-name">{f.name}</div><div className="file-size">{fmt.bytes(f.size)}</div></div></div>
      <button type="button" className="icon-btn" aria-label={`Quitar ${f.name}`} onClick={() => quitar(carpeta, i)}><Trash2 size={16} strokeWidth={1.5} /></button>
    </div>));

  return (
    <>
      <Cabecera titulo="Nuevo informe" atras="/informes" activo="/nuevo" />
      <main className="page-container">
        <form className="workspace-grid" onSubmit={enviar} autoComplete="off">
          <section>
            <div className="section-label">1. Documentos de entrada</div>
            <div className="input-mode-tabs" role="tablist">
              <button type="button" className={`tab-item ${modo === "papeles_trabajo" ? "active" : ""}`} role="tab" aria-selected={modo === "papeles_trabajo"} onClick={() => setModo("papeles_trabajo")}>Papeles de trabajo{ficheros.papeles_trabajo.length > 0 && <span className="count">{ficheros.papeles_trabajo.length}</span>}</button>
              <button type="button" className={`tab-item ${modo === "contexto" ? "active" : ""}`} role="tab" aria-selected={modo === "contexto"} onClick={() => setModo("contexto")}>Contexto de la auditoría{ficheros.contexto.length > 0 && <span className="count">{ficheros.contexto.length}</span>}</button>
            </div>
            <Dropzone key={modo} titulo={modo === "contexto" ? "Contexto de la auditoría (opcional)" : "Papeles de trabajo"} accept={FORMATOS} onFicheros={(fs) => anadir(modo, fs)}
              descripcion={<>{DESCRIPCION[modo]}<br />Formatos: {FORMATOS.replace(/,/g, ", ")}.</>} />
            {lista(modo)}
            <p className="small muted" style={{ marginTop: 24 }}>Los documentos se pueden añadir o quitar después, desde el paso Documentos del informe; las grabaciones de reuniones, en Reuniones. Los papeles de trabajo son la fuente de las conclusiones; el contexto solo orienta la introducción y el resumen ejecutivo.</p>
          </section>

          <section>
            <div className="section-label">2. Datos del informe</div>
            <div className="form-group"><label className="input-label" htmlFor="ref">Referencia</label>
              <input id="ref" className="text-input" placeholder="Ej. TEC-2026" value={referencia} onChange={(e) => setReferencia(e.target.value)} required autoFocus /></div>
            <div className="form-group"><label className="input-label" htmlFor="nombre">Nombre de la auditoría</label>
              <input id="nombre" className="text-input" placeholder="Ej. Auditoría de Transporte e-Commerce: tarifarios y SCA" value={nombre} onChange={(e) => setNombre(e.target.value)} required /></div>
            <div className="form-group"><label className="input-label" htmlFor="fecha">Fecha del informe</label>
              <input id="fecha" className="text-input" placeholder="Ej. Junio 2026" value={fecha} onChange={(e) => setFecha(e.target.value)} /></div>
            <div className="form-group">
              <label className="input-label" htmlFor="destinatario">Lista de distribución</label>
              <input id="destinatario" className="text-input" placeholder="Añadir destinatario y pulsar Intro…" value={destinatario} onChange={(e) => setDestinatario(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addDestinatario(); } }} onBlur={addDestinatario} />
              <div className="tag-container">
                {distribucion.map((d) => <span className="chip" key={d}>{d} <button type="button" className="chip-remove" aria-label={`Quitar ${d}`} onClick={() => setDistribucion(distribucion.filter((x) => x !== d))}>×</button></span>)}
              </div>
            </div>
            <div style={{ marginTop: 48 }}>
              <button type="submit" className="btn btn-primary btn-block" disabled={enviando || !referencia.trim() || !nombre.trim()}>
                {enviando ? <><span className="spinner" /> {subida ? "Subiendo documentos…" : "Creando…"}</> : "Crear informe"}
              </button>
              {subida && <>
                <div className="progress-bar"><div style={{ width: `${subida.pct}%` }} /></div>
                <p className="small muted">{subida.nombre} · {subida.pct} %</p>
              </>}
            </div>
          </section>
        </form>
      </main>
    </>
  );
};
