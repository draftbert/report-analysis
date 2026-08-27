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
- El shell (`src/layout/layout.tsx`) sustituye a `ApplicationLayout` +
  `Header` + `Menu` de Sewing con los mismos bloques BEM; para migrar, basta
  con envolver las páginas con esos componentes y pasarles `getMenu`.
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
