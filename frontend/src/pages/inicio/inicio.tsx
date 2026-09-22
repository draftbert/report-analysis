/* Portada (patrón 1 de la guía): hero y KPIs reales. El listado vive en /informes y el alta en /nuevo. */
import { Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { Cabecera } from "@/layout/layout";

import { Kpis, useExpedientes } from "./secciones";

export const Inicio = () => {
  const { lista, salud } = useExpedientes();
  return (
    <>
      <Cabecera brand activo="/" />
      <main className="content-container">
        <section className="hero-section">
          <div className="hero-eyebrow">Auditoría interna · fases 7 a 9 del proceso de auditoría</div>
          <h1 className="hero-title">Revisor de informes de auditoría interna</h1>
          <p className="hero-subtitle">Del papel de trabajo al informe emitido: el modelo propone la introducción, el resumen ejecutivo y las conclusiones; el auditor las revisa, aprueba y recomienda. Cada apartado del informe es una diapositiva del PowerPoint corporativo y toda salida del modelo queda trazada.</p>
          <div className="row" style={{ gap: 16 }}>
            <Link to="/nuevo" className="btn btn-primary"><Plus size={16} strokeWidth={1.5} />Nuevo informe</Link>
            <Link to="/informes" className="btn btn-secondary">Ver informes</Link>
          </div>
        </section>
        <Kpis lista={lista} salud={salud} />
      </main>
    </>
  );
};
