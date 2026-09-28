/* Pestaña Trazas: llamadas al modelo (fecha, acción, modelo, tokens) y detalle con prompt y respuesta. */
import { useEffect, useState } from "react";

import { api } from "@/api";
import type { Traza } from "@/api";
import { Modal, useNotificar } from "@/components/ui";
import { fmt } from "@/lib/formato";

import type { PropsPestana } from "./estudio";

export const Trazas = ({ refExp }: PropsPestana) => {
  const notificar = useNotificar();
  const [lista, setLista] = useState<Traza[] | null>(null);
  const [abierta, setAbierta] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { api.trazas(refExp).then(setLista).catch((e) => { setLista([]); notificar({ texto: (e as Error).message, error: true }); }); }, [refExp, notificar]);
  const ver = async (t: Traza) => { try { setAbierta(await api.traza(refExp, t.nombre)); } catch (e) { notificar({ texto: (e as Error).message, error: true }); } };
  const texto = (v: unknown) => (typeof v === "string" ? v : JSON.stringify(v ?? {}, null, 2));

  return (
    <div>
      <div className="table-wrapper">
        <table className="ids-table">
          <thead><tr><th>Fecha</th><th>Acción</th><th>Modelo</th><th className="col-right">Tokens entrada / salida</th><th className="col-right" /></tr></thead>
          <tbody>
            {(lista ?? []).map((t) => (
              <tr key={t.nombre}>
                <td>{fmt.fechaHora(t.fecha)}</td>
                <td className="td-title">{t.accion} {t.error && <span className="tag tag-error">error</span>}</td>
                <td className="muted">{t.modelo}</td>
                <td className="col-right num">{t.tokens.prompt ?? "—"} / {t.tokens.completion ?? "—"}</td>
                <td className="col-right td-acciones"><button className="btn btn-ghost" onClick={() => ver(t)}>Ver</button></td>
              </tr>))}
          </tbody>
        </table>
        {lista && lista.length === 0 && <div className="empty">Sin llamadas al modelo todavía.</div>}
      </div>
      {abierta && (
        <Modal ancho titulo={`Traza · ${String(abierta.accion ?? "")}`} onClose={() => setAbierta(null)}>
          <p className="small muted">{String(abierta.fecha ?? "")} · {String(abierta.modelo ?? "")} · {texto(abierta.usage)}</p>
          {"error" in abierta && abierta.error ? <div className="result-box error">{String(abierta.error)}</div> : null}
          <div className="section-label section-label--muted">Prompt de sistema</div><pre className="mono-block">{texto(abierta.system)}</pre>
          <div className="section-label section-label--muted">Prompt de usuario</div><pre className="mono-block">{texto(abierta.user)}</pre>
          <div className="section-label section-label--muted">Respuesta</div><pre className="mono-block">{texto(abierta.respuesta ?? abierta.respuesta_bruta ?? abierta.documentos)}</pre>
        </Modal>)}
    </div>
  );
};
