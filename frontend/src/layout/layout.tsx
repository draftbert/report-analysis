/* Shell de la aplicación, siguiendo el de Sewing DS: cabecera (botón atrás,
   logo, título, botón de menú), menú desplegable lateral con logo y pie
   (avatar, versión), y barra de workflow con las fases del expediente. */
import React, { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, Check, ChevronRight, Menu as MenuIcon, X } from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";

import { api } from "@/api";
import type { ExpedienteEstado } from "@/api";
import { Loader, Logo } from "@/components/ui";

import "./layout.css";

export const EstadoCtx = React.createContext<{ estado: ExpedienteEstado | null; recargar: () => Promise<void> }>({ estado: null, recargar: async () => {} });
export const useEstado = () => React.useContext(EstadoCtx);

export const SECCIONES = [
  { id: "entrada", nombre: "Entrada", corto: "Entrada", listo: (e: ExpedienteEstado) => e.papeles.length > 0 },
  { id: "contexto", nombre: "Contexto del informe", corto: "Contexto", listo: (e: ExpedienteEstado) => !!e.informe?.contexto },
  { id: "conclusiones", nombre: "Conclusiones", corto: "Conclusiones", listo: (e: ExpedienteEstado) => !!e.conclusiones && e.conclusiones.aprobada > 0 },
  { id: "informe", nombre: "Informe", corto: "Informe", listo: (e: ExpedienteEstado) => !!e.informe && e.informe.n_conclusiones + e.informe.n_sugerencias > 0 },
  { id: "reunion", nombre: "Reunión", corto: "Reunión", listo: () => false },
  { id: "entregables", nombre: "Entregables", corto: "Entregables", listo: (e: ExpedienteEstado) => !!e.ppt && !e.ppt.desactualizado },
];
const MENU = [
  { grupo: "EXPEDIENTE", items: SECCIONES },
  { grupo: "TRAZABILIDAD", items: [{ id: "trazas", nombre: "Trazas del modelo", corto: "Trazas", listo: () => false }] },
];

export const Layout = () => {
  const { ref = "" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [estado, setEstado] = useState<ExpedienteEstado | null>(null);
  const [error, setError] = useState("");
  const [menu, setMenu] = useState(false);
  const recargar = useCallback(async () => {
    try { setEstado(await api.estado(ref)); setError(""); } catch (e) { setError(String((e as Error).message)); }
  }, [ref]);
  useEffect(() => { recargar(); }, [recargar]);
  useEffect(() => { setMenu(false); }, [location.pathname]);
  const seccionActual = location.pathname.split("/").pop() ?? "";
  const idxActual = SECCIONES.findIndex((s) => s.id === seccionActual);

  return (
    <EstadoCtx.Provider value={{ estado, recargar }}>
      <div className="layout">
        <header className="layout__header">
          <button className="layout__icon-btn" onClick={() => navigate(-1)} aria-label="Atrás"><ArrowLeft size={20} strokeWidth={1.5} /></button>
          <Logo onClick={() => navigate("/")} />
          <span className="layout__header-title">Auditoría Interna</span>
          {estado && <span className="layout__header-ref">{estado.referencia}</span>}
          <button className="layout__icon-btn layout__icon-btn--end" onClick={() => setMenu(true)} aria-label="Menú"><MenuIcon size={20} strokeWidth={1.5} /></button>
        </header>

        <AnimatePresence>
          {menu && (
            <>
              <motion.div className="menu__overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} onClick={() => setMenu(false)} />
              <motion.nav className="menu" initial={{ x: -320 }} animate={{ x: 0 }} exit={{ x: -320 }} transition={{ type: "tween", ease: [0.4, 0, 0.2, 1], duration: 0.25 }} aria-label="Menú">
                <div className="menu__head"><Logo /><button className="layout__icon-btn" onClick={() => setMenu(false)} aria-label="Cerrar menú"><X size={20} strokeWidth={1.5} /></button></div>
                {estado && <div className="menu__context"><span className="menu__context-ref">{estado.referencia}</span><span className="menu__context-name">{estado.nombre}</span></div>}
                {MENU.map((g) => (
                  <div key={g.grupo} className="menu__group">
                    <div className="menu__group-title">{g.grupo}</div>
                    {g.items.map((s) => (
                      <NavLink key={s.id} to={`/expedientes/${ref}/${s.id}`} className={({ isActive }) => `menu__item ${isActive ? "menu__item--active" : ""}`}>
                        <span>{s.nombre}</span>
                        {estado && s.listo(estado) ? <Check size={14} strokeWidth={1.75} /> : <ChevronRight size={14} strokeWidth={1.5} className="menu__chevron" />}
                      </NavLink>
                    ))}
                  </div>
                ))}
                <NavLink to="/" className="menu__item menu__item--secondary">Todos los expedientes</NavLink>
                <div className="menu__footer">
                  <span className="menu__avatar">AI</span>
                  <div className="menu__footer-text"><span>Auditoría Interna</span><span className="detail">{estado?.llm ?? ""} · v0.3</span></div>
                </div>
              </motion.nav>
            </>
          )}
        </AnimatePresence>

        <main className="layout__content">
          {error && <div className="job-result job-result--error">{error}</div>}
          {!estado && !error && <div className="layout__loading"><Loader /></div>}
          {estado && (
            <>
              <div className="layout__title-bar">
                <div>
                  <div className="layout__ref">{estado.referencia} · {estado.fecha}</div>
                  <h1 className="layout__title">{estado.nombre}</h1>
                </div>
                <div className="layout__phase">
                  <span className="layout__phase-label">Siguiente paso</span>
                  <span className="layout__next">{estado.siguiente.replace(/`/g, "")}</span>
                </div>
              </div>
              <div className="workflow" role="navigation" aria-label="Fases">
                {SECCIONES.map((s, i) => {
                  const listo = s.listo(estado);
                  const actual = s.id === seccionActual;
                  return (
                    <React.Fragment key={s.id}>
                      {i > 0 && <span className={`workflow__line ${i <= idxActual ? "workflow__line--done" : ""}`} />}
                      <NavLink to={`/expedientes/${ref}/${s.id}`} className={`workflow__step ${actual ? "workflow__step--current" : ""}`}>
                        <span className={`workflow__dot ${listo ? "workflow__dot--done" : ""} ${actual ? "workflow__dot--current" : ""}`} />
                        <span className="workflow__label">{s.corto}</span>
                      </NavLink>
                    </React.Fragment>
                  );
                })}
              </div>
            </>
          )}
          <AnimatePresence mode="wait">
            <motion.div key={location.pathname} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.18, ease: "easeOut" }}>
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </EstadoCtx.Provider>
  );
};
