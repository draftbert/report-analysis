import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ConfirmProvider, NotificacionesProvider } from "@/components/ui";
import { Layout } from "@/layout/layout";
import { Estudio } from "@/pages/estudio/estudio";
import { Informe } from "@/pages/informe/informe";
import { Informes } from "@/pages/informes/informes";
import { Inicio } from "@/pages/inicio/inicio";
import { Nuevo } from "@/pages/nuevo/nuevo";
import { Reglas } from "@/pages/reglas/reglas";

const Application = () => (
  <NotificacionesProvider>
    <ConfirmProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Inicio />} />
            <Route path="/informes" element={<Informes />} />
            <Route path="/nuevo" element={<Nuevo />} />
            <Route path="/reglas" element={<Reglas />} />
            <Route path="/informes/:ref" element={<Estudio />} />
            <Route path="/informes/:ref/informe" element={<Informe />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfirmProvider>
  </NotificacionesProvider>
);

export default Application;
