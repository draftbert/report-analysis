/* Cartera de expedientes, con el diseño de la «cartera» de la plantilla:
   cabecera con título y botón primario, buscador + pills, bloque CONTINUAR
   con workflow de puntos, filas con estado y menú ⋯. */
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { MoreHorizontal, Plus, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api";
import type { ExpedienteResumen } from "@/api";
import { Loader, Logo, Modal, useNotificar } from "@/components/ui";
import { SECCIONES } from "@/layout/layout";

import "./expedientes.css";

const relativa = (iso: string) => {
  if (!iso) return "—";
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (d <= 0) return "hoy";
  if (d === 1) return "ayer";
  if (d < 30) return `hace ${d} días`;
  return `hace ${Math.floor(d / 30)} mes${d >= 60 ? "es" : ""}`;
};
const faseNum = (fase: string) => parseInt(fase, 10) || 0;
type Filtro = "TODOS" | "EN_CURSO" | "EMITIDOS";

export const Expedientes = () => {
  const navigate = useNavigate();
  const notificar = useNotificar();
  const [lista, setLista] = useState<ExpedienteResumen[] | null>(null);
  const [busqueda, setBusqueda] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("TODOS");
  const [menuFila, setMenuFila] = useState<string | null>(null);
  const [nuevo, setNuevo] = useState(false);
  const [form, setForm] = useState({ referencia: "", nombre: "", fecha: "", distribucion: "" });
  const [borrar, setBorrar] = useState<ExpedienteResumen | null>(null);
  const [confirmacion, setConfirmacion] = useState("");
  const [borrando, setBorrando] = useState(false);

  const cargar = () => api.listarExpedientes().then(setLista).catch((e) => { setLista([]); notificar({ texto: String(e.message), error: true }); });
  useEffect(() => { cargar(); }, []);
  useEffect(() => { const h = () => setMenuFila(null); window.addEventListener("click", h); return () => window.removeEventListener("click", h); }, []);

  const crear = async () => {
    try {
      const e = await api.crearExpediente({ ...form, distribucion: form.distribucion.split(",").map((x) => x.trim()).filter(Boolean) });
      setNuevo(false);
      navigate(`/expedientes/${e.referencia}/entrada`);
    } catch (err) { notificar({ texto: String((err as Error).message), error: true }); }
  };
  const eliminar = async () => {
    if (!borrar || confirmacion !== borrar.referencia) return;
    setBorrando(true);
    try { const r = await api.eliminarExpediente(borrar.referencia, confirmacion); notificar({ texto: r.mensaje }); setBorrar(null); setConfirmacion(""); await cargar(); }
    catch (err) { notificar({ texto: String((err as Error).message), error: true }); }
    finally { setBorrando(false); }
  };

  const todos = lista ?? [];
  const reciente = todos.find((e) => faseNum(e.fase) < 4);
  const filtrados = todos
    .filter((e) => filtro === "TODOS" || (filtro === "EN_CURSO" ? faseNum(e.fase) < 4 : faseNum(e.fase) >= 4))
    .filter((e) => (e.nombre + e.referencia).toLowerCase().includes(busqueda.toLowerCase()))
    .filter((e) => e.referencia !== reciente?.referencia || filtro !== "TODOS" || busqueda);

  return (
    <div className="cartera-wrap">
      <header className="cartera__top"><Logo /><span className="layout__header-title">Auditoría Interna</span><span className="detail" style={{ marginLeft: "auto" }}>Revisor de informes</span></header>
      <div className="cartera">
        <div className="cartera__header">
          <div><h1 className="cartera__title">Expedientes</h1><p className="cartera__subtitle">Selecciona una auditoría en curso o crea un expediente nuevo.</p></div>
          <button className="btn btn--primary" onClick={() => setNuevo(true)}><Plus size={14} strokeWidth={1.75} />Nuevo expediente</button>
        </div>
        <div className="cartera__filters">
          <input className="input cartera__search" placeholder="Buscar…" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
          <div className="row">
            {([["TODOS", "Todos"], ["EN_CURSO", "En curso"], ["EMITIDOS", "Emitidos"]] as [Filtro, string][]).map(([f, l]) => (
              <button key={f} className={`pill ${filtro === f ? "pill--active" : ""}`} onClick={() => setFiltro(f)}>{l}</button>
            ))}
          </div>
        </div>

        {lista === null && <div className="layout__loading"><Loader /></div>}

        {reciente && filtro === "TODOS" && !busqueda && (
          <motion.div className="cartera__continue" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
            <span className="cartera__continue-label">CONTINUAR</span>
            <div className="cartera__continue-title">{reciente.nombre}</div>
            <div className="detail">{reciente.referencia} · {reciente.fecha} · última actividad {relativa(reciente.modificado)}</div>
            <div className="cartera__workflow">
              {SECCIONES.map((s, i) => (
                <span key={s.id} className="cartera__workflow-item">
                  <span className={`workflow__dot ${i < faseNum(reciente.fase) + 1 ? "workflow__dot--done" : ""} ${i === Math.min(faseNum(reciente.fase) + 1, SECCIONES.length - 1) && faseNum(reciente.fase) < 4 ? "workflow__dot--current" : ""}`} />
                  {i < SECCIONES.length - 1 && <span className="cartera__workflow-line" />}
                </span>
              ))}
            </div>
            <div className="body">Estado: {reciente.fase}</div>
            <div className="detail">Pendiente: {reciente.siguiente.replace(/`/g, "")}</div>
            <div className="cartera__continue-footer">
              <span />
              <button className="btn" onClick={() => navigate(`/expedientes/${reciente.referencia}/entrada`)}>Continuar →</button>
            </div>
          </motion.div>
        )}

        {lista !== null && filtrados.length === 0 && !reciente && <div className="empty">No hay expedientes. Crea uno para empezar.</div>}
        <div className="cartera__list">
          {filtrados.map((e, i) => (
            <motion.div key={e.referencia} className="cartera__row" onClick={() => navigate(`/expedientes/${e.referencia}/entrada`)}
              initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2, delay: i * 0.03 }}>
              <div className="cartera__row-main">
                <div className="cartera__row-header">
                  <span className="cartera__row-title">{e.nombre}</span>
                  <span className={`cartera__row-status ${faseNum(e.fase) >= 4 ? "cartera__row-status--emitido" : ""}`}>{faseNum(e.fase) >= 4 ? "○ Emitido" : "● En curso"}</span>
                </div>
                <div className="detail">{e.referencia} · {e.fecha} · última actividad {relativa(e.modificado)}</div>
                <div className="detail">{e.fase} · {e.siguiente.replace(/`/g, "")}</div>
              </div>
              <button className="layout__icon-btn" aria-label={`Opciones de ${e.referencia}`} onClick={(ev) => { ev.stopPropagation(); setMenuFila(menuFila === e.referencia ? null : e.referencia); }}><MoreHorizontal size={18} strokeWidth={1.5} /></button>
              {menuFila === e.referencia && (
                <div className="cartera__dropdown" onClick={(ev) => ev.stopPropagation()}>
                  <button onClick={() => navigate(`/expedientes/${e.referencia}/entregables`)}>Entregables</button>
                  <button onClick={() => navigate(`/expedientes/${e.referencia}/trazas`)}>Trazas</button>
                  <button className="cartera__dropdown-danger" onClick={() => { setMenuFila(null); setConfirmacion(""); setBorrar(e); }}><Trash2 size={14} strokeWidth={1.5} /> Eliminar expediente…</button>
                </div>
              )}
            </motion.div>
          ))}
        </div>
      </div>

      {borrar && (
        <Modal titulo={`Eliminar expediente ${borrar.referencia}`} onClose={() => setBorrar(null)}
          acciones={<><button className="btn" onClick={() => setBorrar(null)}>Cancelar</button><button className="btn btn--danger" onClick={eliminar} disabled={confirmacion !== borrar.referencia || borrando}>{borrando ? <><span className="spinner" />Eliminando…</> : "Eliminar definitivamente"}</button></>}>
          <p className="body">Se borrará <strong>{borrar.nombre}</strong> con todo su contenido: documentos de entrada, conclusiones, informe, instrucciones, historial, trazas, actas y entregables. Esta acción no se puede deshacer.</p>
          <p className="detail">Si ya generaste un archivo de evidencia (zip), descárgalo antes: también se borra.</p>
          <div className="field"><span className="field__label">Escribe la referencia del expediente para confirmar</span>
            <input className="input" value={confirmacion} onChange={(e) => setConfirmacion(e.target.value)} placeholder={borrar.referencia} autoFocus onKeyDown={(e) => { if (e.key === "Enter") eliminar(); }} />
            {confirmacion && confirmacion !== borrar.referencia && <span className="conc__hallazgo">No coincide con «{borrar.referencia}».</span>}
          </div>
        </Modal>
      )}
      {nuevo && (
        <Modal titulo="Nuevo expediente" onClose={() => setNuevo(false)} acciones={<><button className="btn" onClick={() => setNuevo(false)}>Cancelar</button><button className="btn btn--primary" onClick={crear} disabled={!form.referencia || !form.nombre}>Crear</button></>}>
          <div className="field"><span className="field__label">Referencia</span><input className="input" value={form.referencia} onChange={(e) => setForm({ ...form, referencia: e.target.value })} placeholder="TEC-2026" autoFocus /></div>
          <div className="field"><span className="field__label">Nombre de la auditoría</span><input className="input" value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} placeholder="Auditoría de Transporte e-Commerce: tarifarios y SCA" /></div>
          <div className="field"><span className="field__label">Fecha del informe</span><input className="input" value={form.fecha} onChange={(e) => setForm({ ...form, fecha: e.target.value })} placeholder="Junio 2026" /></div>
          <div className="field"><span className="field__label">Lista de distribución (separada por comas)</span><input className="input" value={form.distribucion} onChange={(e) => setForm({ ...form, distribucion: e.target.value })} placeholder="Dirección de Transporte e-Commerce, Comité de Auditoría" /></div>
        </Modal>
      )}
    </div>
  );
};
