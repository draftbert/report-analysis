import { useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "@/api";
import { Archive, Download, Presentation } from "lucide-react";

import { useNotificar } from "@/components/ui";
import { useEstado } from "@/layout/layout";

export const Entregables = () => {
  const { ref = "" } = useParams();
  const { estado, recargar } = useEstado();
  const notificar = useNotificar();
  const [ocupado, setOcupado] = useState<"" | "ppt" | "zip">("");
  const exportar = async () => { setOcupado("ppt"); try { const r = await api.ppt(ref); notificar({ texto: `Generado ${r.nombre}.` }); if (r.url !== "#") window.open(r.url, "_blank"); recargar(); } catch (e) { notificar({ texto: (e as Error).message, error: true }); } finally { setOcupado(""); } };
  const archivar = async () => { setOcupado("zip"); try { const r = await api.archivar(ref); notificar({ texto: `Archivo ${r.nombre} generado.` }); if (r.url !== "#") window.open(r.url, "_blank"); recargar(); } catch (e) { notificar({ texto: (e as Error).message, error: true }); } finally { setOcupado(""); } };
  const listo = !!estado?.informe && estado.informe.n_conclusiones + estado.informe.n_sugerencias > 0;

  return (
    <div className="page">
      <div className="page__header"><div><h2 className="page__title">Entregables</h2><p className="page__subtitle">Exportación del informe entero a PowerPoint y archivo de evidencia para cerrar el expediente en Pentana.</p></div></div>
      <div className="grid-2">
        <div className="panel">
          <span className="section-title">Presentación (PowerPoint)</span>
          <span className="body">Cada apartado del informe es una diapositiva: portada, índice, introducción, resumen ejecutivo con evaluación global, una diapositiva por conclusión con el diseño corporativo, sugerencias de mejora, anexo de planes de acción.</span>
          {estado?.ppt ? <span className="detail">{estado.ppt.nombre}{estado.ppt.desactualizado ? " · desactualizada respecto al informe" : " · al día"}</span> : <span className="detail">Aún no generada.</span>}
          {estado?.ppt && <a className="detail row" style={{ gap: 6 }} href={`/api/expedientes/${ref}/salidas/${estado.ppt.nombre}`}><Download size={14} strokeWidth={1.5} />Descargar la última versión</a>}
          <div><button className="btn btn--primary" onClick={exportar} disabled={!listo || ocupado !== ""}>{ocupado === "ppt" ? <><span className="spinner" />Exportando…</> : <><Presentation size={14} strokeWidth={1.5} />Exportar informe a PowerPoint</>}</button></div>
          {!listo && <span className="detail">Vuelca al menos una conclusión aprobada al informe para poder exportar.</span>}
        </div>
        <div className="panel">
          <span className="section-title">Archivo de evidencia</span>
          <span className="body">Zip con las trazas de cada llamada al modelo, el historial de versiones, el informe, las conclusiones, el registro de cambios, las actas de reunión y el PowerPoint, más un manifest.json con el sha256 de cada fichero para demostrar su integridad. Se adjunta al expediente al cerrarlo en Pentana.</span>
          <div><button className="btn btn--primary" onClick={archivar} disabled={ocupado !== ""}>{ocupado === "zip" ? <><span className="spinner" />Archivando…</> : <><Archive size={14} strokeWidth={1.5} />Archivar</>}</button></div>
          {estado?.archivos.length ? (
            <div className="stack"><span className="label">Archivos anteriores</span>{estado.archivos.map((a) => <a key={a} className="detail" href={`/api/expedientes/${ref}/salidas/${a}`}>{a}</a>)}</div>
          ) : <span className="detail">Sin archivos todavía.</span>}
        </div>
      </div>
    </div>
  );
};
