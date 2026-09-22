/* Shell de la aplicación: cabecera IDS (botón atrás o menú, logotipo, título, navegación central,
   buscador/lupa y cierre de sesión), según el kit del front homogéneo (docs/GUIA_FRONT_HOMOGENEO.md). */
import React from "react";
import { ArrowLeft, LogOut, Menu as MenuIcon, Search } from "lucide-react";
import { Link, Outlet, useNavigate } from "react-router-dom";

import { api } from "@/api";
import { Logo } from "@/components/ui";

import "./layout.css";

const NAV: [string, string][] = [["/", "Inicio"], ["/informes", "Informes"], ["/nuevo", "Nuevo informe"]];

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

export const Layout = () => (
  <div className="app-shell">
    <Outlet />
  </div>
);
