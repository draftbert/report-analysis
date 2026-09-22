/* Datos y secciones compartidos por la portada y el listado de informes. */
import { useCallback, useEffect, useState } from "react";

import { api } from "@/api";
import type { Expediente, Salud } from "@/api";
import { useNotificar } from "@/components/ui";
import { esEmitido, fmt } from "@/lib/formato";

export const useExpedientes = () => {
  const notificar = useNotificar();
  const [lista, setLista] = useState<Expediente[] | null>(null);
  const [salud, setSalud] = useState<Salud | null>(null);
  const cargar = useCallback(async () => {
    try {
      const [l, s] = await Promise.all([api.listarExpedientes(), api.salud()]);
      setLista(l); setSalud(s);
    } catch (err) { setLista([]); notificar({ texto: (err as Error).message, error: true }); }
  }, [notificar]);
  useEffect(() => { cargar(); }, [cargar]);
  return { lista, salud, cargar };
};

/** KPIs de la portada, calculados sobre la lista real de expedientes de la API. */
export const Kpis = ({ lista, salud }: { lista: Expediente[] | null; salud: Salud | null }) => {
  const enCurso = lista?.filter((e) => !esEmitido(e.fase)).length;
  const emitidos = lista?.filter((e) => esEmitido(e.fase)).length;
  const aprobadas = lista?.reduce((s, e) => s + (e.conclusiones?.aprobada ?? 0), 0);
  const modelo = lista?.find((e) => e.llm)?.llm;
  return (
    <section className="kpi-row" aria-label="Indicadores de la cartera de informes">
      <div className="kpi-item"><span className="kpi-label">Informes</span><span className="kpi-value">{lista ? fmt.n(lista.length) : "—"}</span><span className="kpi-caption">{salud ? `Revisor v${salud.version}` : "Expedientes en la carpeta de trabajo"}</span></div>
      <div className="kpi-item"><span className="kpi-label">En curso</span><span className="kpi-value">{lista ? fmt.n(enCurso) : "—"}</span><span className="kpi-caption">Entre entrada y redacción</span></div>
      <div className="kpi-item"><span className="kpi-label">Emitidos</span><span className="kpi-value">{lista ? fmt.n(emitidos) : "—"}</span><span className="kpi-caption">Con entregable generado</span></div>
      <div className="kpi-item"><span className="kpi-label">Conclusiones aprobadas</span><span className="kpi-value">{lista ? fmt.n(aprobadas) : "—"}</span><span className="kpi-caption">{modelo ? `Modelo: ${modelo}` : "Validadas por el auditor"}</span></div>
    </section>
  );
};
