/* Estudio del informe (patrón 4 de la guía, a una columna): panel con pestañas Entrada, Contexto,
   Conclusiones, Reunión, Entregables y Trazas; el siguiente paso y el acceso al informe van en la barra. */
import { useCallback, useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api";
import type { Expediente } from "@/api";
import { Loader } from "@/components/ui";
import { Cabecera } from "@/layout/layout";
import { faseNum, fmt, textoSiguiente } from "@/lib/formato";

import { Conclusiones } from "./conclusiones";
import { Contexto } from "./contexto";
import { Entrada } from "./entrada";
import { Entregables } from "./entregables";
import { Reunion } from "./reunion";
import { Trazas } from "./trazas";

export type Pestana = "entrada" | "contexto" | "conclusiones" | "reunion" | "entregables" | "trazas";
export interface PropsPestana { refExp: string; exp: Expediente; recargar: () => Promise<void> }

const PESTANAS: Pestana[] = ["entrada", "contexto", "conclusiones", "reunion", "entregables", "trazas"];
const porFase = (fase: string): Pestana => (faseNum(fase) === 0 ? "entrada" : faseNum(fase) === 1 ? "contexto" : "conclusiones");

export const Estudio = () => {
  const { ref = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const [exp, setExp] = useState<Expediente | null>(null);
  const [error, setError] = useState("");

  const recargar = useCallback(async () => {
    try { setExp(await api.estado(ref)); setError(""); } catch (e) { setError((e as Error).message); }
  }, [ref]);
  useEffect(() => { recargar(); }, [recargar]);

  const p = params.get("pestana");
  const pestana: Pestana = PESTANAS.includes(p as Pestana) ? (p as Pestana) : exp ? porFase(exp.fase) : "entrada";
  const irA = (t: Pestana) => setParams({ pestana: t });

  const etiqueta = (t: Pestana) => {
    if (!exp) return null;
    const n = { entrada: exp.contexto.length + exp.papeles.length, contexto: null, conclusiones: exp.conclusiones?.total ?? 0, reunion: null, entregables: null, trazas: null }[t];
    return n ? <span className="count">{n}</span> : null;
  };

  return (
    <>
      <Cabecera titulo={exp?.nombre ?? "Informe"} atras="/informes" activo="/informes" extra={exp && <span className="badge-status">{exp.fase}</span>} />
      {error && <section className="progress-panel"><div className="section-label" style={{ marginBottom: 8 }}>No se ha podido abrir el informe</div><div className="result-box error">{error}</div><div className="row" style={{ marginTop: 16 }}><button className="btn btn-primary" onClick={recargar}>Reintentar</button><Link className="btn btn-ghost" to="/informes">Informes</Link></div></section>}
      {!exp && !error && <div className="content-container" style={{ textAlign: "center" }}><Loader /></div>}
      {exp && (
        <main className="main-container main-container--una-columna">
          <section className="extraction-panel">
            <div className="panel-toolbar">
              <div className="meta-info-strip">
                <div className="meta-item"><span className="meta-label">Referencia</span><span className="meta-value">{exp.referencia}</span></div>
                <div className="meta-item"><span className="meta-label">Fecha del informe</span><span className="meta-value">{exp.fecha || "—"}</span></div>
                <div className="meta-item"><span className="meta-label">Distribución</span><span className="meta-value">{exp.distribucion.join(", ") || "—"}</span></div>
                <div className="meta-item"><span className="meta-label">Última actividad</span><span className="meta-value">{fmt.relativa(exp.modificado)}</span></div>
                <div className="meta-item" style={{ flex: 1, minWidth: 240 }}><span className="meta-label">Siguiente paso</span><span className="meta-value small">{textoSiguiente(exp.siguiente)}</span></div>
                <div className="meta-item" style={{ marginLeft: "auto", justifyContent: "center" }}>
                  <Link className={`btn ${exp.informe ? "btn-primary" : "btn-secondary"}`} to={`/informes/${encodeURIComponent(ref)}/informe`} aria-disabled={!exp.informe} onClick={(e) => { if (!exp.informe) e.preventDefault(); }}><FileText strokeWidth={1.5} /> Ver informe</Link>
                </div>
              </div>
              <div className="tab-row" role="tablist">
                {([["entrada", "Entrada"], ["contexto", "Contexto del informe"], ["conclusiones", "Conclusiones"], ["reunion", "Reunión"], ["entregables", "Entregables"], ["trazas", "Trazas"]] as [Pestana, string][]).map(([k, n]) => (
                  <button key={k} className={`tab-item ${pestana === k ? "active" : ""}`} role="tab" aria-selected={pestana === k} onClick={() => irA(k)}>{n}{etiqueta(k)}</button>))}
              </div>
            </div>
            <div className="tab-content-container">
              {pestana === "entrada" && <Entrada refExp={ref} exp={exp} recargar={recargar} />}
              {pestana === "contexto" && <Contexto refExp={ref} exp={exp} recargar={recargar} />}
              {pestana === "conclusiones" && <Conclusiones refExp={ref} exp={exp} recargar={recargar} />}
              {pestana === "reunion" && <Reunion refExp={ref} exp={exp} recargar={recargar} />}
              {pestana === "entregables" && <Entregables refExp={ref} exp={exp} recargar={recargar} />}
              {pestana === "trazas" && <Trazas refExp={ref} exp={exp} recargar={recargar} />}
            </div>
          </section>
        </main>
      )}
    </>
  );
};
