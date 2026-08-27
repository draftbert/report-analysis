/* Shell de la aplicación: cabecera, menú lateral fijo por secciones y área de contenido.
   Equivale al Layout de la plantilla corporativa (ApplicationLayout + Header + Menu de Sewing). */
import React, { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";

import { api } from "@/api";
import type { ExpedienteEstado } from "@/api";

import "./layout.css";

export const EstadoCtx = React.createContext<{ estado: ExpedienteEstado | null; recargar: () => Promise<void> }>({ estado: null, recargar: async () => {} });
export const useEstado = () => React.useContext(EstadoCtx);

const SECCIONES = [
  { id: "entrada", nombre: "Entrada", listo: (e: ExpedienteEstado) => e.papeles.length > 0 },
  { id: "contexto", nombre: "Contexto del informe", listo: (e: ExpedienteEstado) => !!e.informe?.contexto },
  { id: "conclusiones", nombre: "Conclusiones", listo: (e: ExpedienteEstado) => !!e.conclusiones && e.conclusiones.aprobada > 0 },
  { id: "informe", nombre: "Informe", listo: (e: ExpedienteEstado) => !!e.informe && e.informe.n_conclusiones + e.informe.n_sugerencias > 0 },
  { id: "reunion", nombre: "Reunión", listo: () => false },
  { id: "entregables", nombre: "Entregables", listo: (e: ExpedienteEstado) => !!e.ppt },
  { id: "trazas", nombre: "Trazas", listo: () => false },
];

export const Layout = () => {
  const { ref = "" } = useParams();
  const navigate = useNavigate();
  const [estado, setEstado] = useState<ExpedienteEstado | null>(null);
  const [error, setError] = useState("");
  const recargar = useCallback(async () => {
    try { setEstado(await api.estado(ref)); setError(""); } catch (e) { setError(String((e as Error).message)); }
  }, [ref]);
  useEffect(() => { recargar(); }, [recargar]);

  return (
    <EstadoCtx.Provider value={{ estado, recargar }}>
      <div className="layout">
        <header className="layout__header">
          <button className="layout__brand" onClick={() => navigate("/")} aria-label="Inicio">INDITEX</button>
          <span className="layout__app">Auditoría Interna · Revisor de informes</span>
          <span className="layout__llm">{estado?.llm}</span>
        </header>
        <div className="layout__body">
          <nav className="layout__menu" aria-label="Secciones">
            <div className="layout__menu-group">EXPEDIENTE</div>
            {SECCIONES.map((s) => (
              <NavLink key={s.id} to={`/expedientes/${ref}/${s.id}`} className={({ isActive }) => `layout__item ${isActive ? "layout__item--active" : ""}`}>
                <span className={`layout__dot ${estado && s.listo(estado) ? "layout__dot--listo" : ""}`} />
                {s.nombre}
              </NavLink>
            ))}
            <div className="layout__menu-footer"><NavLink to="/" className="layout__item">← Expedientes</NavLink></div>
          </nav>
          <main className="layout__content">
            {error && <div className="job-result job-result--error">{error}</div>}
            {estado && (
              <div className="layout__title-bar">
                <div>
                  <div className="layout__ref">{estado.referencia}</div>
                  <h1 className="layout__title">{estado.nombre}</h1>
                </div>
                <div className="layout__phase">
                  <span className="tag">{estado.fase}</span>
                  <span className="layout__next"><span className="label">Siguiente paso</span> {estado.siguiente.replace(/`/g, "")}</span>
                </div>
              </div>
            )}
            <Outlet />
          </main>
        </div>
      </div>
    </EstadoCtx.Provider>
  );
};
