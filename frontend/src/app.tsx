import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { NotificacionesProvider } from "@/components/ui";
import { Layout } from "@/layout/layout";
import { Conclusiones } from "@/pages/conclusiones/conclusiones";
import { Contexto } from "@/pages/contexto/contexto";
import { Entrada } from "@/pages/entrada/entrada";
import { Entregables } from "@/pages/entregables/entregables";
import { Expedientes } from "@/pages/expedientes/expedientes";
import { Informe } from "@/pages/informe/informe";
import { Reunion } from "@/pages/reunion/reunion";
import { Trazas } from "@/pages/trazas/trazas";

const Application = () => (
  <NotificacionesProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Expedientes />} />
        <Route path="/expedientes/:ref" element={<Layout />}>
          <Route index element={<Navigate to="entrada" replace />} />
          <Route path="entrada" element={<Entrada />} />
          <Route path="contexto" element={<Contexto />} />
          <Route path="conclusiones" element={<Conclusiones />} />
          <Route path="informe" element={<Informe />} />
          <Route path="reunion" element={<Reunion />} />
          <Route path="entregables" element={<Entregables />} />
          <Route path="trazas" element={<Trazas />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </NotificacionesProvider>
);

export default Application;
