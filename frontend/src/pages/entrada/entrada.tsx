import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "@/api";
import type { Documentos } from "@/api";
import { FileText, Trash2 } from "lucide-react";

import { Dropzone, useNotificar } from "@/components/ui";
import { useEstado } from "@/layout/layout";

const FORMATOS = ".md, .txt, .docx, .xlsx, .pdf, .pptx";
const tam = (b: number) => (b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(0)} KB` : `${(b / 1048576).toFixed(1)} MB`);

export const Entrada = () => {
  const { ref = "" } = useParams();
  const { recargar } = useEstado();
  const notificar = useNotificar();
  const [docs, setDocs] = useState<Documentos>({ contexto: [], papeles_trabajo: [] });
  const cargar = () => api.documentos(ref).then(setDocs).catch((e) => notificar({ texto: e.message, error: true }));
  useEffect(() => { cargar(); }, [ref]);

  const [subidas, setSubidas] = useState<Record<string, { nombre: string; pct: number; carpeta: string; error?: boolean }>>({});
  const subir = async (carpeta: "contexto" | "papeles_trabajo", ficheros: File[]) => {
    if (!ficheros.length) return;
    const clave = (n: string) => `${carpeta}/${n}`;
    setSubidas((s) => ({ ...s, ...Object.fromEntries(ficheros.map((f) => [clave(f.name), { nombre: f.name, pct: 0, carpeta }])) }));
    try {
      setDocs(await api.subir(ref, carpeta, ficheros, (nombre, pct) => setSubidas((s) => ({ ...s, [clave(nombre)]: { nombre, pct, carpeta } }))));
      notificar({ texto: `${ficheros.length} fichero(s) subido(s).` }); recargar();
      window.setTimeout(() => setSubidas((s) => Object.fromEntries(Object.entries(s).filter(([k]) => !ficheros.some((f) => k === clave(f.name))))), 1200);
    } catch (e) {
      notificar({ texto: (e as Error).message, error: true });
      setSubidas((s) => Object.fromEntries(Object.entries(s).map(([k, v]) => [k, v.carpeta === carpeta && v.pct < 100 ? { ...v, error: true } : v])));
    }
  };
  const Subidas = ({ carpeta }: { carpeta: string }) => {
    const lista = Object.values(subidas).filter((s) => s.carpeta === carpeta);
    return lista.length === 0 ? null : (
      <div className="upload" aria-live="polite">
        {lista.map((s) => (
          <div key={s.nombre} className={`upload__item ${s.error ? "upload__item--error" : ""}`}>
            <span className="upload__name">{s.nombre}</span>
            <span className="upload__pct">{s.error ? "Error" : s.pct < 100 ? `${s.pct} %` : "Subido"}</span>
            <div className="progress" role="progressbar" aria-valuenow={s.pct} aria-valuemin={0} aria-valuemax={100}><div className="progress__bar" style={{ width: `${s.pct}%` }} /></div>
          </div>
        ))}
      </div>
    );
  };
  const borrar = async (carpeta: string, nombre: string) => {
    if (!window.confirm(`¿Eliminar «${nombre}»?`)) return;
    setDocs(await api.borrarDocumento(ref, carpeta, nombre)); recargar();
  };
  const Lista = ({ carpeta }: { carpeta: "contexto" | "papeles_trabajo" }) => (
    docs[carpeta].length === 0 ? <div className="detail">Sin documentos.</div> : (
      <table className="table"><tbody>
        {docs[carpeta].map((d) => (
          <tr key={d.nombre}><td><span className="row" style={{ gap: 8 }}><FileText size={16} strokeWidth={1.5} />{d.nombre}</span></td><td className="detail">{d.lector} · {tam(d.bytes)}</td><td style={{ textAlign: "right" }}><button className="btn btn--ghost btn--small" onClick={() => borrar(carpeta, d.nombre)} aria-label={`Eliminar ${d.nombre}`}><Trash2 size={14} strokeWidth={1.5} />Eliminar</button></td></tr>
        ))}
      </tbody></table>
    )
  );

  return (
    <div className="page">
      <div className="page__header"><div><h2 className="page__title">Entrada</h2><p className="page__subtitle">Al empezar la auditoría, el design thinking o la planificación; al terminar el trabajo de campo, el papel de trabajo final con todas las pruebas.</p></div></div>
      <div className="grid-2">
        <div className="stack">
          <Dropzone titulo="Contexto de la auditoría" descripcion="Design thinking, memorando de planificación, motivo, riesgos a cubrir, alcance previsto y magnitudes. Opcional: alimenta la introducción y el resumen ejecutivo." formatos={FORMATOS} onFicheros={(f) => subir("contexto", f)} />
          <Subidas carpeta="contexto" />
          <Lista carpeta="contexto" />
        </div>
        <div className="stack">
          <Dropzone titulo="Papeles de trabajo" descripcion="Un fichero por prueba (o el papel de trabajo final con todas): contexto, objetivo, pruebas realizadas y conclusiones. Es la fuente de las conclusiones. Las hojas de datos de Excel se envían resumidas (40 primeras filas)." formatos={FORMATOS} onFicheros={(f) => subir("papeles_trabajo", f)} />
          <Subidas carpeta="papeles_trabajo" />
          <Lista carpeta="papeles_trabajo" />
        </div>
      </div>
    </div>
  );
};
