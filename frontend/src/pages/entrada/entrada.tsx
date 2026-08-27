import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "@/api";
import type { Documentos } from "@/api";
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

  const subir = async (carpeta: "contexto" | "papeles_trabajo", ficheros: File[]) => {
    if (!ficheros.length) return;
    try { setDocs(await api.subir(ref, carpeta, ficheros)); notificar({ texto: `${ficheros.length} fichero(s) subido(s).` }); recargar(); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
  };
  const borrar = async (carpeta: string, nombre: string) => {
    if (!window.confirm(`¿Eliminar «${nombre}»?`)) return;
    setDocs(await api.borrarDocumento(ref, carpeta, nombre)); recargar();
  };
  const Lista = ({ carpeta }: { carpeta: "contexto" | "papeles_trabajo" }) => (
    docs[carpeta].length === 0 ? <div className="detail">Sin documentos.</div> : (
      <table className="table"><tbody>
        {docs[carpeta].map((d) => (
          <tr key={d.nombre}><td>{d.nombre}</td><td className="detail">{d.lector} · {tam(d.bytes)}</td><td style={{ textAlign: "right" }}><button className="btn btn--ghost btn--small" onClick={() => borrar(carpeta, d.nombre)}>Eliminar</button></td></tr>
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
          <Lista carpeta="contexto" />
        </div>
        <div className="stack">
          <Dropzone titulo="Papeles de trabajo" descripcion="Papel de trabajo final con todas las pruebas (contexto, objetivo, pruebas realizadas, conclusiones). Es la fuente de las conclusiones. Se admite el texto pegado desde Excel en .txt." formatos={FORMATOS} onFicheros={(f) => subir("papeles_trabajo", f)} />
          <Lista carpeta="papeles_trabajo" />
        </div>
      </div>
    </div>
  );
};
