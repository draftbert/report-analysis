/* Espacio de trabajo de un informe, en una sola pantalla y con dos momentos (la API dice cuál: `modo`):
   - Primera pasada: Documentos → Contexto → Observaciones → Informe.
   - Iteración (el informe ya tiene observaciones): se trabaja sobre el informe —Informe (a mano o con el chat) ·
     Reuniones con el área · Exportación— y «Añadir más contexto» abre los tres pasos previos para incorporar
     documentación nueva, con «Volver al informe».
   Todos los pasos se pueden abrir siempre. El paso va en la URL (`?paso=`; en el informe, `&vista=documento|cambios`). */
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Plus } from "lucide-react";
import { Link, Navigate, useLocation, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api";
import type { Expediente, Paso, PasoId } from "@/api";
import { Aviso, Esqueleto, EsqueletoDocumento, PasoCabecera, PasoPie, Pasos } from "@/components/ui";
import { Cabecera } from "@/layout/layout";

import { Conclusiones } from "./conclusiones";
import { Contexto } from "./contexto";
import { Entrada } from "./entrada";
import { Entregables } from "./entregables";
import { InformePaso, type Vista } from "./informe";
import { Reunion } from "./reunion";
import { Trazas } from "./trazas";

/** Lo que recibe cada paso: el expediente, cómo recargarlo y cómo ir a otro paso. */
export interface PropsPestana { refExp: string; exp: Expediente; recargar: () => Promise<void>; irA?: (paso: PasoId | "trazas", vista?: Vista) => void }

const PRIMERA_PASADA: PasoId[] = ["documentos", "contexto", "observaciones", "informe"];
const PREPARACION: PasoId[] = ["documentos", "contexto", "observaciones"];
const ITERACION: PasoId[] = ["informe", "reuniones", "entrega"];
const AYUDA: Record<PasoId, string> = {
  documentos: "El papel de trabajo final es la fuente de las observaciones; el contexto de la auditoría (design thinking, planificación) es opcional y alimenta la introducción. Lo que subas queda «Sin procesar» hasta que pase por el modelo.",
  contexto: "El modelo redacta la introducción y el resumen ejecutivo a partir del contexto y del papel de trabajo; tú los dejas a tu gusto y calificas la evaluación global.",
  observaciones: "Una observación por incidencia del papel de trabajo. Revisa lo que propone el modelo, completa la recomendación, aprueba y pásalas al informe. Aquí manda el auditor.",
  informe: "El informe tal como se leerá en el PowerPoint, un apartado por diapositiva. Cámbialo a mano o con el asistente; «Últimos cambios» enseña qué ha cambiado.",
  reuniones: "Sube la grabación o la transcripción de una reunión con el área: se genera el acta y aplicas al informe los cambios que marques.",
  entrega: "Genera el PowerPoint sobre la plantilla corporativa y archiva la evidencia para cerrar el expediente en Pentana.",
};
/** Enlaces antiguos (`?pestana=`, `&vista=reuniones`) → paso actual. */
const PESTANA_A_PASO: Record<string, PasoId | "trazas"> = {
  entrada: "documentos", contexto: "contexto", conclusiones: "observaciones", reunion: "reuniones", entregables: "entrega", trazas: "trazas",
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

  const antigua = params.get("pestana") ?? (params.get("vista") === "reuniones" ? "reunion" : null);
  if (antigua && PESTANA_A_PASO[antigua]) return <Navigate replace to={`/informes/${encodeURIComponent(ref)}?paso=${PESTANA_A_PASO[antigua]}`} />;

  const iterando = exp?.modo === "iteracion";
  const pedido = params.get("paso");
  const todos: string[] = [...PRIMERA_PASADA, ...ITERACION, "trazas"];
  const porDefecto: PasoId = !exp ? "documentos" : iterando ? (ITERACION.includes(exp.paso_sugerido) ? exp.paso_sugerido : "informe") : exp.paso_sugerido;
  const paso = (pedido && todos.includes(pedido) ? pedido : porDefecto) as PasoId | "trazas";
  const vista = (params.get("vista") as Vista) || "documento";
  // Qué barra se ve: en iteración, la de iterar salvo cuando se está añadiendo contexto (los tres pasos previos).
  const anadiendo = iterando && PREPARACION.includes(paso as PasoId);
  const barra: PasoId[] = !iterando ? PRIMERA_PASADA : anadiendo ? PREPARACION : ITERACION;
  const i = barra.indexOf(paso as PasoId);
  const pasoDe = (id: PasoId) => exp?.pasos.find((p) => p.id === id) as Paso;
  const kicker = paso === "trazas" ? "Consulta"
    : anadiendo ? `Añadir más contexto · paso ${i + 1} de ${barra.length}`
    : iterando ? "Iterar el informe"
    : i >= 0 ? `Paso ${i + 1} de ${barra.length}` : "Informe";
  // La sugerencia va en la cabecera del paso sugerido, salvo que el paso ya tenga su propio aviso (manda el aviso).
  const sugerencia = (id: PasoId) => (exp && exp.paso_sugerido === id && !pasoDe(id)?.aviso ? exp.sugerencia : undefined);
  const props = exp ? { refExp: ref, exp, recargar, irA } : null;

  const volverAlInforme = <button type="button" className="btn btn-primary" onClick={() => irA("informe")}><ArrowLeft strokeWidth={1.5} /> Volver al informe</button>;
  const botonTrazas = <button type="button" className="btn btn-ghost btn-ghost--inline small" onClick={() => irA("trazas")} title="Cada llamada al modelo: prompt, respuesta y tokens">Trazas</button>;
  const botonContexto = exp && (
    <button type="button" className="btn btn-secondary" onClick={() => irA(PREPARACION.includes(exp.paso_sugerido) ? exp.paso_sugerido : "documentos")}
      title="Subir más papeles de trabajo o contexto, redactar de nuevo la introducción o el resumen, extraer y pasar más observaciones">
      <Plus strokeWidth={1.5} /> Añadir más contexto{exp.preparacion_pendiente && <span className="tag tag-warning" style={{ marginLeft: 4 }}>Pendiente</span>}</button>);
  // En iteración, lo pendiente de los pasos previos se avisa sobre el informe, con acceso directo.
  const avisoPendiente = iterando && !anadiendo && exp?.preparacion_pendiente
    ? <Aviso tipo="aviso" accion={botonContexto}>{exp.sugerencia}</Aviso> : undefined;
  const pie = (() => {
    if (!exp || paso === "trazas" || i < 0 || (iterando && !anadiendo)) return undefined;
    const anterior = i > 0 ? { titulo: pasoDe(barra[i - 1]).titulo, ir: () => irA(barra[i - 1]) } : undefined;
    const siguiente = i < barra.length - 1 ? { titulo: pasoDe(barra[i + 1]).titulo, ir: () => irA(barra[i + 1]) }
      : anadiendo ? { titulo: "volver al informe", ir: () => irA("informe") } : undefined;
    return <PasoPie anterior={anterior} siguiente={siguiente} />;
  })();

  return (
    <>
      <Cabecera titulo={exp?.nombre ?? "Informe"} atras="/informes" activo="/informes" extra={exp && <span className="badge-status">{exp.referencia}</span>} />
      {error && <section className="progress-panel"><div className="section-label" style={{ marginBottom: 8 }}>No se ha podido abrir el informe</div><div className="result-box error">{error}</div><div className="row" style={{ marginTop: 16 }}><button className="btn btn-primary" onClick={recargar}>Reintentar</button><Link className="btn btn-ghost" to="/informes">Informes</Link></div></section>}
      {!exp && !error && <><div className="pasos" aria-busy="true">{PRIMERA_PASADA.map((k) => <div key={k} style={{ flex: 1, padding: "16px 16px 14px 0" }}><Esqueleto ancho={60} /><Esqueleto ancho={80} /></div>)}</div>
        <main className="main-container main-container--una-columna"><section className="extraction-panel"><div className="tab-content-container"><EsqueletoDocumento bloques={2} /></div></section></main></>}
      {exp && props && (
        <>
          <Pasos pasos={barra.map(pasoDe)} activo={paso} onIr={(id) => irA(id as PasoId)}
            extra={<span className="row">{anadiendo ? volverAlInforme : iterando ? botonContexto : null}{botonTrazas}</span>} />
          {paso === "informe"
            ? <InformePaso key={ref} {...props} vista={vista === "cambios" ? "cambios" : "documento"}
                cabecera={<PasoCabecera kicker={kicker} titulo="Informe" ayuda={AYUDA.informe} sugerencia={sugerencia("informe")} aviso={avisoPendiente} />} pie={pie} />
            : (
              <main className="main-container main-container--una-columna aparece" key={paso}>
                <section className="extraction-panel">
                  <div className="tab-content-container">
                    {paso === "trazas"
                      ? <PasoCabecera kicker={kicker} titulo="Trazas del modelo" ayuda="Cada llamada al modelo con su prompt, su respuesta y los tokens: la evidencia de cómo se ha generado cada texto." />
                      : <PasoCabecera kicker={kicker} titulo={pasoDe(paso).titulo} ayuda={AYUDA[paso]} sugerencia={sugerencia(paso)} aviso={avisoPendiente} />}
                    {paso === "documentos" && <Entrada {...props} />}
                    {paso === "contexto" && <Contexto {...props} />}
                    {paso === "observaciones" && <Conclusiones {...props} />}
                    {paso === "reuniones" && <Reunion {...props} alAplicar={() => irA("informe", "cambios")} />}
                    {paso === "entrega" && <Entregables {...props} />}
                    {paso === "trazas" && <Trazas {...props} />}
                    {pie}
                  </div>
                </section>
              </main>)}
        </>
      )}
    </>
  );
};

/** `/informes/:ref/informe` (enlaces antiguos) → el informe del espacio de trabajo. */
export const RedirigirInforme = () => {
  const { ref = "" } = useParams();
  const { search } = useLocation();
  return <Navigate replace to={`/informes/${encodeURIComponent(ref)}?paso=informe${search ? `&${search.slice(1)}` : ""}`} />;
};
