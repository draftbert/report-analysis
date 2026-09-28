/* Shell de la aplicación: cabecera IDS (botón atrás o menú, logotipo, título, navegación central,
   buscador/lupa y cierre de sesión), según el kit del front homogéneo (docs/GUIA_FRONT_HOMOGENEO.md). */
import React from "react";
import { ArrowLeft, LogOut, Menu as MenuIcon, Search } from "lucide-react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";

import { api } from "@/api";
import { Logo } from "@/components/ui";

import "./layout.css";

const NAV: [string, string][] = [["/", "Inicio"], ["/informes", "Informes"], ["/nuevo", "Nuevo informe"], ["/reglas", "Reglas"]];

export const Cabecera = ({ titulo, atras, activo = "", brand = false, buscador, extra }: {
  titulo?: string; atras?: string; activo?: string; brand?: boolean; buscador?: React.ReactNode; extra?: React.ReactNode;
}) => {
  const navigate = useNavigate();
  const salir = async () => { await api.logout(); window.location.href = "/acceso.html"; };
  return (
    <header className={`ids-header ${brand ? "ids-header--brand" : ""}`}>
      <div className="header-zone">
        {atras
          ? <Link className="icon-btn" to={atras} aria-label="Volver"><ArrowLeft size={20} strokeWidth={1.5} /></Link>
          : <button className="icon-btn" onClick={() => navigate("/")} aria-label="Menú"><MenuIcon size={20} strokeWidth={1.5} /></button>}
        <Logo grande={brand} onClick={() => navigate("/")} />
        {titulo && <h1 className="header-title">{titulo}</h1>}
      </div>
      <nav className="header-zone header-zone--center" aria-label="Navegación principal">
        {NAV.map(([h, n]) => <Link key={h} to={h} className={`header-nav-item ${activo === h ? "active" : ""}`}>{n}</Link>)}
      </nav>
      <div className="header-zone header-zone--right">
        {extra}
        {buscador ?? <Link className="icon-btn" to="/informes" aria-label="Buscar"><Search size={20} strokeWidth={1.5} /></Link>}
        <button className="icon-btn" onClick={salir} aria-label="Cerrar sesión" title="Cerrar sesión"><LogOut size={20} strokeWidth={1.5} /></button>
      </div>
    </header>
  );
};

/** `key={pathname}` remonta el contenido en cada cambio de ruta y relanza la animación de entrada
 *  (la cabecera queda fuera de la animación para que no parpadee). */
export const Layout = () => {
  const { pathname } = useLocation();
  return (
    <div className="app-shell">
      <div className="transicion-ruta" key={pathname}>
        <Outlet />
      </div>
    </div>
  );
};
