/* Pestaña Entrada: documentos de contexto y papeles de trabajo, con subida (progreso real) y borrado. */
import { useCallback, useEffect, useState } from "react";
import { FileText, Trash2 } from "lucide-react";

import { api } from "@/api";
import type { Carpeta, Documentos } from "@/api";
import { Dropzone, useConfirmar, useNotificar } from "@/components/ui";
import { fmt } from "@/lib/formato";

import type { PropsPestana } from "./estudio";

const FORMATOS = ".md,.txt,.docx,.xlsx,.pdf,.pptx";
const TITULO: Record<Carpeta, string> = { contexto: "Contexto de la auditoría (opcional)", papeles_trabajo: "Papeles de trabajo" };
const DESCRIPCION: Record<Carpeta, string> = {
  contexto: "Design thinking, memorando de planificación, motivo, riesgos a cubrir, alcance previsto y magnitudes. Alimenta la introducción y el resumen ejecutivo.",
  papeles_trabajo: "Un fichero por prueba (o el papel de trabajo final con todas): contexto, objetivo, pruebas realizadas y conclusiones. Es la fuente de las conclusiones. Las hojas de Excel se envían resumidas (40 primeras filas).",
};
type Subida = { nombre: string; pct: number; carpeta: Carpeta; error?: boolean };

export const Entrada = ({ refExp, recargar }: PropsPestana) => {
  const notificar = useNotificar();
  const confirmar = useConfirmar();
  const [docs, setDocs] = useState<Documentos>({ contexto: [], papeles_trabajo: [] });
  const [subidas, setSubidas] = useState<Subida[]>([]);
  const cargar = useCallback(() => api.documentos(refExp).then(setDocs).catch((e) => notificar({ texto: (e as Error).message, error: true })), [refExp, notificar]);
  useEffect(() => { cargar(); }, [cargar]);

  const subir = async (carpeta: Carpeta, ficheros: File[]) => {
    setSubidas((s) => [...s.filter((x) => x.carpeta !== carpeta), ...ficheros.map((f) => ({ nombre: f.name, pct: 0, carpeta }))]);
    try {
      setDocs(await api.subir(refExp, carpeta, ficheros, (nombre, pct) => setSubidas((s) => s.map((x) => (x.carpeta === carpeta && x.nombre === nombre ? { ...x, pct } : x)))));
      notificar({ texto: `${ficheros.length} fichero(s) subido(s).` });
      await recargar();
      window.setTimeout(() => setSubidas((s) => s.filter((x) => x.carpeta !== carpeta)), 1200);
    } catch (e) {
      notificar({ texto: (e as Error).message, error: true });
      setSubidas((s) => s.map((x) => (x.carpeta === carpeta && x.pct < 100 ? { ...x, error: true } : x)));
    }
  };
  const borrar = async (carpeta: Carpeta, nombre: string) => {
    if (!(await confirmar({ titulo: "Eliminar documento", cuerpo: `Se eliminará «${nombre}» de ${TITULO[carpeta].toLowerCase()}.`, accion: "Eliminar", peligro: true }))) return;
    try { setDocs(await api.borrarDocumento(refExp, carpeta, nombre)); await recargar(); notificar({ texto: "Documento eliminado." }); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };

  const bloque = (carpeta: Carpeta) => (
    <div>
      <div className="section-label section-label--muted">{TITULO[carpeta]} <span className="editable-badge">{docs[carpeta].length} fichero(s)</span></div>
      <Dropzone titulo={`Subir ${carpeta === "contexto" ? "contexto" : "papeles de trabajo"}`} accept={FORMATOS} onFicheros={(fs) => subir(carpeta, fs)}
        descripcion={<>{DESCRIPCION[carpeta]}<br />Formatos: {FORMATOS.replace(/,/g, ", ")}.</>} />
      {subidas.filter((s) => s.carpeta === carpeta).map((s) => (
        <div className="uploaded-file-preview" key={s.nombre} aria-live="polite">
          <div className="file-info" style={{ flex: 1 }}><div style={{ minWidth: 0, flex: 1 }}><div className="file-name">{s.nombre}</div>
            <div className="progress-bar" style={{ margin: "8px 0 0" }}><div style={{ width: `${s.pct}%` }} /></div></div></div>
          <span className={`tag ${s.error ? "tag-error" : s.pct < 100 ? "tag-info" : "tag-success"}`}>{s.error ? "Error" : s.pct < 100 ? `${s.pct} %` : "Subido"}</span>
        </div>))}
      <div className="table-wrapper" style={{ marginTop: 16 }}>
        <table className="ids-table ids-table--muted">
          <thead><tr><th>Documento</th><th>Lector</th><th className="col-right">Tamaño</th><th className="col-right" /></tr></thead>
          <tbody>
            {docs[carpeta].map((d) => (
              <tr key={d.nombre}>
                <td className="td-title"><span className="row" style={{ gap: 8, flexWrap: "nowrap" }}><FileText size={16} strokeWidth={1.5} />{d.nombre}</span></td>
                <td className="muted">{d.lector}</td>
                <td className="col-right num">{fmt.bytes(d.bytes)}</td>
                <td className="col-right td-acciones"><button className="icon-btn" onClick={() => borrar(carpeta, d.nombre)} aria-label={`Eliminar ${d.nombre}`} title="Eliminar"><Trash2 size={16} strokeWidth={1.5} /></button></td>
              </tr>))}
          </tbody>
        </table>
        {docs[carpeta].length === 0 && <div className="empty">{carpeta === "papeles_trabajo" ? "Sube el papel de trabajo para poder extraer las conclusiones." : "Sin documentos de contexto. Es opcional."}</div>}
      </div>
    </div>
  );

  return (
    <div>
      <h2 className="section-header-sm">Documentos de entrada</h2>
      <p className="small muted" style={{ marginBottom: 24 }}>Al empezar la auditoría, el design thinking o la planificación; al terminar el trabajo de campo, el papel de trabajo final con todas las pruebas.</p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 48 }}>
        {bloque("papeles_trabajo")}
        {bloque("contexto")}
      </div>
    </div>
  );
};
