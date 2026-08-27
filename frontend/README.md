# Front del revisor de informes

Vite + React 18 + TypeScript, con el mismo look & feel y la misma estructura
que la plantilla corporativa (AMIGA + Sewing DS): tokens de diseño `--ids-*`,
CSS BEM por página, cabecera + menú lateral, notificación negra fija, tablas y
dropzones de la plantilla.

Fuera del entorno corporativo no se pueden instalar `@inditex/*` ni
`@amiga-fwk-web/*` (registro privado), así que:

- `src/assets/styles/tokens.css` define los tokens `--ids-*` con valores
  equivalentes. En el entorno corporativo se elimina ese fichero y se importa
  `@inditex/sewingiopdsweb-styles` en `main.tsx`: los nombres coinciden.
- El shell (`src/layout/layout.tsx`) reproduce `ApplicationLayout` + `Header`
  (botón atrás, logo, título, botón de menú) + `Menu` desplegable (logo, grupos,
  pie con avatar y versión) de Sewing, con `framer-motion` para el deslizamiento
  del menú, las transiciones de página, modales y notificaciones; y la barra de
  *workflow* de puntos de la plantilla como navegación por fases. Para migrar,
  basta con envolver las páginas con los componentes reales de Sewing y pasarles
  `SECCIONES` como `items` del menú.
- Iconos: `lucide-react` (línea, 1,5 px, monocromos, como los de Sewing); en el
  entorno corporativo se sustituyen por los de `@inditex/sewingiopdsweb-resources`.
- `Logo` es una marca tipográfica provisional: en corporativo, `Logo` de Sewing.
- No hay AMIGA `Auth`/`ConfigProvider`: la app habla con `/api` en el mismo
  origen (el servidor Python sirve `dist/`).

## Uso

```bash
npm install
npm run dev          # http://localhost:3030, proxy /api → http://localhost:8000 (arranca antes `./revisor web`)
npm run dev:mock     # sin back-end: datos de ejemplo del expediente TEC-2026 y jobs simulados (VITE_MOCK=1)
npm run build        # dist/ (lo sirve `./revisor web` en http://127.0.0.1:8000)
npm run types:check
```

## Estructura

```
src/api/          types.ts (contrato), client.ts (fetch a /api), mock.ts (modo mock), index.ts (esperarJob)
src/components/   ui.tsx: JobButton, JobResult, RiskBadge, StateChip, MarkdownEditor, DiffView, Dropzone, Modal, SlideCard
src/layout/       shell: cabecera, menú lateral con estado por sección, barra de título con fase y siguiente paso
src/pages/        expedientes · entrada · contexto · conclusiones · informe · reunion · entregables · trazas
```

Contrato de API: `docs/SUPERPROMPT_FRONT.md` § 5 (implementado en `audit_agent/api.py`).
