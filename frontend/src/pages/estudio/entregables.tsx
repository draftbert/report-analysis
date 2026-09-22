/* Pestaña Entregables: exportación del informe a PowerPoint y archivo de evidencia (zip con manifest). */
import { useState } from "react";
import { Archive, Download, Presentation } from "lucide-react";

import { api } from "@/api";
import { useConfirmar, useNotificar } from "@/components/ui";
import { fmt } from "@/lib/formato";

import type { PropsPestana } from "./estudio";

export const Entregables = ({ refExp, exp, recargar }: PropsPestana) => {
  const notificar = useNotificar();
  const confirmar = useConfirmar();
  const [ocupado, setOcupado] = useState<"" | "ppt" | "zip">("");
  const listo = !!exp.informe && exp.informe.n_conclusiones + exp.informe.n_sugerencias > 0;

  const exportar = async () => {
    setOcupado("ppt");
    try { const r = await api.ppt(refExp); notificar({ texto: `Generado ${r.nombre}.` }); window.open(r.url, "_blank"); await recargar(); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
    finally { setOcupado(""); }
  };
  const archivar = async () => {
    if (!(await confirmar({ titulo: "Archivar el expediente", accion: "Archivar", cuerpo: "Se genera el zip de evidencia (trazas, historial, informe, conclusiones, actas y PowerPoint con manifest sha256). Las voces, clips y audios de las reuniones se destruyen al archivar." }))) return;
    setOcupado("zip");
    try { const r = await api.archivar(refExp); notificar({ texto: `Archivo ${r.nombre} generado.` }); window.open(r.url, "_blank"); await recargar(); }
    catch (e) { notificar({ texto: (e as Error).message, error: true }); }
    finally { setOcupado(""); }
  };

  return (
    <div>
      <h2 className="section-header-sm">Entregables</h2>
      <p className="small muted" style={{ marginBottom: 24 }}>Exportación del informe entero a PowerPoint y archivo de evidencia para cerrar el expediente en Pentana.</p>
      <div className="template-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))" }}>
        <div className="template-card">
          <div>
            <span className="template-badge">Presentación</span>
            <h3 className="template-title">PowerPoint</h3>
            <p className="template-desc">Cada apartado del informe es una diapositiva: portada, índice, introducción, resumen ejecutivo con evaluación global, una diapositiva por conclusión con el diseño corporativo, sugerencias de mejora y anexo de planes de acción.</p>
            <div className="row" style={{ marginBottom: 16 }}>
              {exp.ppt ? <span className={`tag ${exp.ppt.desactualizado ? "tag-warning" : "tag-success"}`}>{exp.ppt.desactualizado ? "Desactualizada respecto al informe" : "Al día"}</span> : <span className="tag tag-neutral">Aún no generada</span>}
              {exp.informe && <span className="small muted">informe modificado {fmt.fechaHora(exp.informe.modificado)}</span>}
            </div>
            {exp.ppt && <p className="small"><a className="btn btn-ghost btn-ghost--inline" href={api.urlSalida(refExp, exp.ppt.nombre)}><Download strokeWidth={1.5} /> {exp.ppt.nombre}</a></p>}
            {!listo && <p className="small muted">Vuelca al menos una conclusión aprobada al informe para poder exportar.</p>}
          </div>
          <div className="template-footer">
            <span className="template-meta">Sin modelo, determinista</span>
            <button className="btn btn-primary" onClick={exportar} disabled={!listo || ocupado !== ""}>{ocupado === "ppt" ? <><span className="spinner" /> Exportando…</> : <><Presentation strokeWidth={1.5} /> Exportar a PowerPoint</>}</button>
          </div>
        </div>
        <div className="template-card">
          <div>
            <span className="template-badge">Cierre del expediente</span>
            <h3 className="template-title">Archivo de evidencia</h3>
            <p className="template-desc">Zip con las trazas de cada llamada al modelo, el historial de versiones, el informe, las conclusiones, el registro de cambios, las actas de reunión y el PowerPoint, más un manifest.json con el sha256 de cada fichero. Las voces, clips y audios de las reuniones se destruyen al archivar.</p>
            {exp.archivos.length > 0
              ? <div className="small"><span className="muted">Archivos anteriores:</span>{exp.archivos.map((a) => <a key={a} href={api.urlSalida(refExp, a)} style={{ display: "block" }}>{a}</a>)}</div>
              : <p className="small muted">Sin archivos todavía.</p>}
          </div>
          <div className="template-footer">
            <span className="template-meta">Se adjunta al expediente</span>
            <button className="btn btn-secondary" onClick={archivar} disabled={ocupado !== ""}>{ocupado === "zip" ? <><span className="spinner" /> Archivando…</> : <><Archive strokeWidth={1.5} /> Archivar</>}</button>
          </div>
        </div>
      </div>
    </div>
  );
};
