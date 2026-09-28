/* Espacio de trabajo de un informe: una sola pantalla con los pasos Documentos → Contexto → Observaciones →
   Informe → Entrega, siempre navegables (al informe se vuelve varias veces: un papel de trabajo nuevo, una
   reunión con el área…). La API dice el estado de cada paso y cuál toca ahora (`pasos`, `sugerencia`).
   El paso va en la URL (`?paso=`; en el informe, también `&vista=documento|reuniones|cambios`). */
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useLocation, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api";
import type { Expediente, PasoId } from "@/api";
import { Esqueleto, EsqueletoDocumento, PasoCabecera, PasoPie, Pasos } from "@/components/ui";
import { Cabecera } from "@/layout/layout";

import { Conclusiones } from "./conclusiones";
import { Contexto } from "./contexto";
import { Entrada } from "./entrada";
import { Entregables } from "./entregables";
import { InformePaso, type Vista } from "./informe";
import { Trazas } from "./trazas";

/** Lo que recibe cada paso: el expediente, cómo recargarlo y cómo ir a otro paso. */
export interface PropsPestana { refExp: string; exp: Expediente; recargar: () => Promise<void>; irA?: (paso: PasoId | "trazas", vista?: Vista) => void }

const ORDEN: PasoId[] = ["documentos", "contexto", "observaciones", "informe", "entrega"];
const AYUDA: Record<PasoId, string> = {
  documentos: "El papel de trabajo final es la fuente de las observaciones; el contexto de la auditoría (design thinking, planificación) es opcional y alimenta la introducción. Puedes volver cuando quieras a añadir más: lo nuevo queda «Sin procesar» y se incorpora sin rehacer lo que ya has revisado.",
  contexto: "El modelo redacta la introducción y el resumen ejecutivo a partir del contexto y del papel de trabajo; tú los dejas a tu gusto y calificas la evaluación global.",
  observaciones: "Una observación por incidencia del papel de trabajo. Revisa lo que propone el modelo, completa la recomendación, aprueba y pásalas al informe. Aquí manda el auditor.",
  informe: "El informe tal como se leerá en el PowerPoint, un apartado por diapositiva. Cámbialo a mano, con el asistente o con lo acordado en una reunión con el área; «Últimos cambios» enseña qué ha cambiado.",
  entrega: "Genera el PowerPoint sobre la plantilla corporativa y archiva la evidencia para cerrar el expediente en Pentana.",
};
/** Enlaces antiguos (`?pestana=`) → paso nuevo. */
const PESTANA_A_PASO: Record<string, [PasoId | "trazas", Vista?]> = {
  entrada: ["documentos"], contexto: ["contexto"], conclusiones: ["observaciones"], reunion: ["informe", "reuniones"], entregables: ["entrega"], trazas: ["trazas"],
};
/** Último estado conocido de cada expediente (sobrevive a la navegación; se refresca al montar). */
const cacheEstado = new Map<string, Expediente>();

export const Estudio = () => {
  const { ref = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const [exp, setExp] = useState<Expediente | null>(cacheEstado.get(ref) ?? null);
  const [error, setError] = useState("");

  const recargar = useCallback(async () => {
    try { const e = await api.estado(ref); cacheEstado.set(ref, e); setExp(e); setError(""); } catch (e) { setError((e as Error).message); }
  }, [ref]);
  useEffect(() => { recargar(); }, [recargar]);

  const irA = useCallback((paso: PasoId | "trazas", vista?: Vista) => {
    setParams(vista ? { paso, vista } : { paso });
    window.scrollTo({ top: 0 });
  }, [setParams]);

  const antigua = params.get("pestana");
  if (antigua && PESTANA_A_PASO[antigua]) {
    const [paso, vista] = PESTANA_A_PASO[antigua];
    return <Navigate replace to={`/informes/${encodeURIComponent(ref)}?paso=${paso}${vista ? `&vista=${vista}` : ""}`} />;
  }
  const pedido = params.get("paso");
  const paso: PasoId | "trazas" = pedido === "trazas" || ORDEN.includes(pedido as PasoId) ? (pedido as PasoId | "trazas") : exp?.paso_sugerido ?? "documentos";
  const vista = (params.get("vista") as Vista) || "documento";
  const i = ORDEN.indexOf(paso as PasoId);
  const props = exp ? { refExp: ref, exp, recargar, irA } : null;
  // Qué toca hacer, en la cabecera del paso sugerido; si el paso ya tiene su propio aviso (lo nuevo, lo pendiente), manda el aviso.
  const sugerencia = (id: PasoId) => (exp && exp.paso_sugerido === id && !exp.pasos.find((p) => p.id === id)?.aviso ? exp.sugerencia : undefined);

  return (
    <>
      <Cabecera titulo={exp?.nombre ?? "Informe"} atras="/informes" activo="/informes" extra={exp && <span className="badge-status">{exp.referencia}</span>} />
      {error && <section className="progress-panel"><div className="section-label" style={{ marginBottom: 8 }}>No se ha podido abrir el informe</div><div className="result-box error">{error}</div><div className="row" style={{ marginTop: 16 }}><button className="btn btn-primary" onClick={recargar}>Reintentar</button><Link className="btn btn-ghost" to="/informes">Informes</Link></div></section>}
      {!exp && !error && <><div className="pasos" aria-busy="true">{ORDEN.map((k) => <div key={k} style={{ flex: 1, padding: "16px 16px 14px 0" }}><Esqueleto ancho={60} /><Esqueleto ancho={80} /></div>)}</div>
        <main className="main-container main-container--una-columna"><section className="extraction-panel"><div className="tab-content-container"><EsqueletoDocumento bloques={2} /></div></section></main></>}
      {exp && props && (
        <>
          <Pasos pasos={exp.pasos} activo={paso} onIr={(id) => irA(id as PasoId)}
            extra={<button type="button" className={`btn btn-ghost btn-ghost--inline small ${paso === "trazas" ? "active" : ""}`} onClick={() => irA("trazas")} title="Cada llamada al modelo: prompt, respuesta y tokens">Trazas</button>} />
          {paso === "informe"
            ? <InformePaso key={ref} {...props} vista={vista} cabecera={<PasoCabecera numero={4} total={ORDEN.length} titulo="Informe" ayuda={AYUDA.informe} sugerencia={sugerencia("informe")} />}
                pie={<PasoPie anterior={{ titulo: "Observaciones", ir: () => irA("observaciones") }} siguiente={{ titulo: "Entrega", ir: () => irA("entrega") }} />} />
            : (
              <main className="main-container main-container--una-columna aparece" key={paso}>
                <section className="extraction-panel">
                  <div className="tab-content-container">
                    {paso === "trazas"
                      ? <PasoCabecera titulo="Trazas del modelo" ayuda="Cada llamada al modelo con su prompt, su respuesta y los tokens: la evidencia de cómo se ha generado cada texto." />
                      : <PasoCabecera numero={i + 1} total={ORDEN.length} titulo={exp.pasos[i].titulo} ayuda={AYUDA[paso]} sugerencia={sugerencia(paso as PasoId)} />}
                    {paso === "documentos" && <Entrada {...props} />}
                    {paso === "contexto" && <Contexto {...props} />}
                    {paso === "observaciones" && <Conclusiones {...props} />}
                    {paso === "entrega" && <Entregables {...props} />}
                    {paso === "trazas" && <Trazas {...props} />}
                    {paso !== "trazas" && (
                      <PasoPie anterior={i > 0 ? { titulo: exp.pasos[i - 1].titulo, ir: () => irA(ORDEN[i - 1]) } : undefined}
                        siguiente={i < ORDEN.length - 1 ? { titulo: exp.pasos[i + 1].titulo, ir: () => irA(ORDEN[i + 1]) } : undefined} />)}
                  </div>
                </section>
              </main>)}
        </>
      )}
    </>
  );
};

/** `/informes/:ref/informe` (enlaces antiguos) → el paso Informe del espacio de trabajo. */
export const RedirigirInforme = () => {
  const { ref = "" } = useParams();
  const { search } = useLocation();
  return <Navigate replace to={`/informes/${encodeURIComponent(ref)}?paso=informe${search ? `&${search.slice(1)}` : ""}`} />;
};
