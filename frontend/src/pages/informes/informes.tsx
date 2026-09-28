/* Listado de informes (patrón 2 de la guía): buscador en la cabecera, filtros, tabla con acciones y
   eliminación con confirmación (la API exige escribir la referencia exacta). */
import { useMemo, useState } from "react";
import { Plus, Search, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import { api } from "@/api";
import type { Expediente } from "@/api";
import { EsqueletoFilas, Modal, useNotificar } from "@/components/ui";
import { Cabecera } from "@/layout/layout";
import { esEmitido, fmt, textoSiguiente } from "@/lib/formato";
import { useExpedientes } from "@/pages/inicio/secciones";

type Filtro = "" | "en_curso" | "emitido";

export const Informes = () => {
  const notificar = useNotificar();
  const { lista, cargando, cargar } = useExpedientes();
  const [q, setQ] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("");
  const [borrar, setBorrar] = useState<Expediente | null>(null);
  const [confirmacion, setConfirmacion] = useState("");
  const [borrando, setBorrando] = useState(false);

  const filas = useMemo(() => {
    const ql = q.trim().toLowerCase();
    return (lista ?? []).filter((e) =>
      (!ql || `${e.referencia} ${e.nombre} ${e.fase}`.toLowerCase().includes(ql)) &&
      (!filtro || (filtro === "emitido") === esEmitido(e.fase)));
  }, [lista, q, filtro]);

  const eliminar = async () => {
    if (!borrar || confirmacion !== borrar.referencia) return;
    setBorrando(true);
    try {
      const r = await api.eliminarExpediente(borrar.referencia, confirmacion);
      notificar({ texto: r.mensaje }); setBorrar(null); setConfirmacion(""); await cargar();
    } catch (err) { notificar({ texto: (err as Error).message, error: true }); }
    finally { setBorrando(false); }
  };

  return (
    <>
      <Cabecera titulo="Informes" atras="/" activo="/informes" buscador={
        <label className="header-search"><Search size={18} strokeWidth={1.5} /><input type="search" placeholder="Buscar informe…" aria-label="Buscar informe" value={q} onChange={(e) => setQ(e.target.value)} /></label>} />
      <main className="content-container">
        <section className="section-block">
          <div className="section-header">
            <h2 className="section-title">Cartera de informes ({lista?.length ?? 0})</h2>
            <div className="row" style={{ gap: 16 }}>
              <label className="small muted row">Estado
                <select className="select-input text-input--small" style={{ width: 160 }} value={filtro} onChange={(e) => setFiltro(e.target.value as Filtro)}>
                  <option value="">Todos</option><option value="en_curso">En curso</option><option value="emitido">Emitidos</option>
                </select></label>
              <Link to="/nuevo" className="btn btn-primary"><Plus size={16} strokeWidth={1.5} />Nuevo informe</Link>
            </div>
          </div>
          <div className="table-wrapper">
            <table className="ids-table">
              <thead><tr><th>Referencia</th><th>Auditoría</th><th>Fecha</th><th>Fase</th><th>Siguiente paso</th><th>Actividad</th><th className="col-right">Acciones</th></tr></thead>
              {cargando && <EsqueletoFilas anchos={[10, 30, 9, 13, 22, 8, 12]} />}
              <tbody className="aparece">
                {filas.map((e) => (
                  <tr key={e.referencia}>
                    <td className="td-title"><Link to={`/informes/${encodeURIComponent(e.referencia)}`}>{e.referencia}</Link></td>
                    <td>{e.nombre}{e.distribucion.length > 0 && <div className="small muted">{e.distribucion.join(" · ")}</div>}</td>
                    <td>{e.fecha || "—"}</td>
                    <td><span className={`status-tag ${esEmitido(e.fase) ? "status-completed" : "status-processing"}`}>{e.fase}</span></td>
                    <td className="small muted">{textoSiguiente(e.siguiente)}</td>
                    <td>{fmt.relativa(e.modificado)}</td>
                    <td className="col-right td-acciones">
                      <Link className="btn btn-ghost" to={`/informes/${encodeURIComponent(e.referencia)}`}>Abrir</Link>
                      {e.informe && e.informe.n_conclusiones + e.informe.n_sugerencias > 0 && <Link className="btn btn-ghost" to={`/informes/${encodeURIComponent(e.referencia)}?paso=informe`}>Ver informe</Link>}
                      <button className="icon-btn" onClick={() => { setConfirmacion(""); setBorrar(e); }} title="Eliminar informe" aria-label={`Eliminar ${e.referencia}`}><Trash2 size={18} strokeWidth={1.5} /></button>
                    </td>
                  </tr>))}
              </tbody>
            </table>
            {!cargando && lista !== null && lista.length === 0 && <div className="empty">Todavía no hay informes. Crea el primero con «Nuevo informe».</div>}
            {!cargando && lista !== null && lista.length > 0 && filas.length === 0 && <div className="empty">Ningún informe coincide con el filtro.</div>}
          </div>
        </section>
      </main>

      {borrar && (
        <Modal titulo={`Eliminar informe ${borrar.referencia}`} onClose={() => setBorrar(null)} acciones={
          <>
            <button className="btn btn-secondary" onClick={() => setBorrar(null)}>Cancelar</button>
            <button className="btn btn-danger" onClick={eliminar} disabled={confirmacion !== borrar.referencia || borrando}>{borrando ? <><span className="spinner" />Eliminando…</> : "Eliminar definitivamente"}</button>
          </>}>
          <p>Se borrará <strong>{borrar.nombre}</strong> con todo su contenido: documentos de entrada, conclusiones, informe, instrucciones, historial, trazas, actas y entregables. Esta acción no se puede deshacer.</p>
          <p className="small muted">Si ya generaste un archivo de evidencia (zip), descárgalo antes: también se borra.</p>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="input-label" htmlFor="confirmar-ref">Escribe la referencia del informe para confirmar</label>
            <input id="confirmar-ref" className="text-input" value={confirmacion} onChange={(e) => setConfirmacion(e.target.value)} placeholder={borrar.referencia} autoFocus onKeyDown={(e) => { if (e.key === "Enter") eliminar(); }} />
            {confirmacion && confirmacion !== borrar.referencia && <p className="small" style={{ color: "var(--c-error-fg)" }}>No coincide con «{borrar.referencia}».</p>}
          </div>
        </Modal>
      )}
    </>
  );
};
