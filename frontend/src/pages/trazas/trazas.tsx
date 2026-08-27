import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "@/api";
import type { Traza } from "@/api";

export const Trazas = () => {
  const { ref = "" } = useParams();
  const [lista, setLista] = useState<Traza[]>([]);
  const [abierta, setAbierta] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { api.trazas(ref).then(setLista).catch(() => setLista([])); }, [ref]);
  const fecha = (iso: string) => iso.replace("T", " ").slice(0, 16);
  return (
    <div className="page">
      <div className="page__header"><div><h2 className="page__title">Trazas</h2><p className="page__subtitle">Toda salida del modelo queda ligada a su entrada: prompt, respuesta estructurada y tokens de cada llamada.</p></div></div>
      {lista.length === 0 ? <div className="empty">Sin llamadas al modelo todavía.</div> : (
        <table className="table"><thead><tr><th>Fecha</th><th>Acción</th><th>Modelo</th><th>Tokens (entrada / salida)</th><th></th></tr></thead><tbody>
          {lista.map((t) => (
            <tr key={t.nombre} data-clickable onClick={() => api.traza(ref, t.nombre).then(setAbierta)}>
              <td className="detail">{fecha(t.fecha)}</td><td>{t.accion}{t.error ? <span className="conc__hallazgo"> · error</span> : null}</td><td className="detail">{t.modelo}</td>
              <td className="detail">{t.tokens.prompt ?? "—"} / {t.tokens.completion ?? "—"}</td><td className="detail">Ver →</td>
            </tr>
          ))}
        </tbody></table>
      )}
      {abierta && (
        <div className="drawer">
          <div className="row row--between"><span className="section-title">{String(abierta.accion ?? "")}</span><button className="btn btn--ghost" onClick={() => setAbierta(null)}>Cerrar</button></div>
          <span className="detail">{String(abierta.fecha ?? "")} · {String(abierta.modelo ?? "")} · {JSON.stringify(abierta.usage ?? {})}</span>
          {"error" in abierta && abierta.error ? <div className="job-result job-result--error">{String(abierta.error)}</div> : null}
          <span className="label">Prompt de sistema</span><div className="mono">{String(abierta.system ?? "")}</div>
          <span className="label">Prompt de usuario</span><div className="mono">{String(abierta.user ?? "")}</div>
          <span className="label">Respuesta</span><div className="mono">{JSON.stringify(abierta.respuesta ?? abierta.respuesta_bruta ?? abierta.documentos ?? {}, null, 2)}</div>
        </div>
      )}
    </div>
  );
};
