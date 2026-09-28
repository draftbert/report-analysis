# Guía del front homogéneo (React + TypeScript + IDS)

Cómo está construido el front del generador de actas y cómo reproducir **el mismo paradigma** en
cualquier otra aplicación interna. Está escrita para pasársela a otro Claude Code (o a una persona)
junto con el **kit** de ficheros que se copian tal cual. Al final hay un prompt listo para pegar.

La idea central: **el front no inventa nada**. Estructura, tokens, componentes, patrones de pantalla,
contrato con la API y sesión están fijados aquí; una pantalla nueva se compone con esas piezas y se
diseña sobre un mockup HTML del IOP Design System (como los de `docs/mockups/`). Si algo no está en
la guía, se añade a la guía y al kit, no se improvisa en un proyecto.

---

## 1. Stack fijo

| Pieza | Decisión |
|---|---|
| Build | Vite 6 + React 18 + TypeScript 5 (`strict`), `tsc --noEmit` antes de `vite build`. |
| Router | `react-router-dom` 7, `BrowserRouter`, una ruta por pantalla, `Layout` con `Outlet`. |
| Estilo | CSS plano con BEM ligero; **sin** Tailwind, MUI, styled-components. Tokens en `tokens.css` (`--ids-*`) y `custom.css` (`--c-*` de los mockups). |
| Iconos | `lucide-react`, trazo 1.5, monocromos. Logotipo del CDN de AMIGA con marca tipográfica de respaldo. |
| Animación | `framer-motion` solo para notificaciones y modales. |
| Markdown | `react-markdown` + `remark-gfm` en un único componente `Markdown`. |
| Servidor | nginx sirve `dist/` y hace proxy de `/api`; es la puerta de sesión (`auth_request`). |
| Idioma | Toda la interfaz en español; etiquetas de KPI/cabeceras de tabla pueden ir en inglés si el mockup lo trae. |

Prohibido: lógica de negocio en el front (todo cálculo o validación relevante vive en la API),
`window.confirm/alert`, estado global (context solo para notificaciones y confirmaciones), CSS-in-JS.

## 2. Estructura de carpetas (obligatoria)

```
frontend/
  Dockerfile              build multi-stage (node:22-alpine → nginx:1.27-alpine)
  nginx.conf              SPA + proxy /api + auth_request (ver § 7)
  index.html              <div id="app"> + fuentes del CDN
  package.json, tsconfig.json, vite.config.ts   (alias "@", proxy /api en dev, puerto 3030)
  public/acceso.html      login autocontenido (sin bundle), se sirve antes de la sesión
  src/
    main.tsx              createRoot + import de tokens.css y custom.css
    app.tsx               providers (Notificaciones, Confirm) + rutas
    api/types.ts          contrato con la API: tipos de datos + interface Api
    api/client.ts         implementación fetch: 401 → login, errores {error}, subida con progreso (XHR)
    api/index.ts          `api`, `esperarJob` y re-export de tipos
    assets/styles/tokens.css   --ids-* (en corporativo se sustituye por @inditex/sewingiopdsweb-styles)
    assets/styles/custom.css   sistema visual completo (~180 clases, ver § 3)
    components/ui.tsx     componentes compartidos (§ 4)
    hooks/useJob.ts       seguimiento de trabajos largos
    layout/layout.tsx     Cabecera IDS + Layout (Outlet); layout.css
    lib/formato.ts        fechas, duraciones, tamaños, clases por valor (riesgo, prioridad, estado)
    pages/<pantalla>/<pantalla>.tsx (+ .css solo si hace falta; secciones.tsx para trozos compartidos)
```

Una pantalla = una carpeta en `pages/`. Nada de componentes sueltos fuera de `components/ui.tsx`
salvo que sean privados de una página.

## 3. Sistema visual

Tokens (`custom.css`, `:root`): `--c-primary #000`, `--c-secondary #757575`, `--c-neutral #fff`,
superficies `#F7F7F7`/`#EDEDED`, borde `#E3E3E3` (0.5 px), foco `#0170E9`, deshabilitado `#B3B3B3`,
estados error `#DA2727/#FFF4F4`, aviso `#B66009/#FFF4E5`, éxito `#0A882A/#F1FDF1`, info `#0968F6/#F0F6FE`.
Tipografía `Helvetica Now Text` (325 para títulos y etiquetas, 300 cuerpo), mono `Noto Sans Mono`.
Sin radios (solo píldoras `999px` en estados), sin sombras salvo menús flotantes, mayúsculas con
`letter-spacing 0.4px` en etiquetas, botones y navegación.

Catálogo de clases (todas en `custom.css`; se usan por nombre, no se redefinen):

| Grupo | Clases |
|---|---|
| Cabecera | `ids-header` (`--brand` 88 px), `header-zone` (`--center`, `--right`), `header-title`, `header-nav-item(.active)`, `header-search`, `icon-btn`, `brand-logo`, `brand-text` |
| Barra | `toolbar` (sticky bajo la cabecera), `toolbar-title`, `toolbar-actions` |
| Botones | `btn` + `btn-primary` / `btn-secondary` / `btn-ghost` (`--inline`) / `btn-danger` / `btn-block`; `spinner` dentro para estados de trabajo |
| Contenedores | `content-container` (1440), `page-container` (1200), `workspace-grid` (alta: 1fr / 400 px, una columna en pantallas estrechas), `section-grid` (bloques a dos columnas de ≥ 480 px cuando caben, una columna si no; `__ancha` ocupa toda la fila), `section-block`, `section-header`, `section-title`, `section-label` (`--muted`), `editable-badge` |
| Portada | `hero-section`, `hero-eyebrow`, `hero-title`, `hero-subtitle`, `kpi-row` (`--compact`), `kpi-item/label/value/caption`, `template-grid/card/badge/title/desc/footer/meta` |
| Tablas | `table-wrapper`, `ids-table` (`--muted`), `col-right`, `td-title`, `td-acciones`, `empty` |
| Etiquetas | `status-tag` + `status-completed/processing/pending/error`; `tag` + `tag-success/info/warning/error/neutral`; `status-pill` + `pending/progress/done`; `prio-alta/media/baja`; `source-type`; `badge-status` |
| Formularios | `form-group`, `input-label`, `text-input` (`--small`), `select-input`, `select-wrapper`, `tag-container`, `chip`, `chip-remove`, `field-underlined`, `field-label`, `field-select`, `inline-edit`, `textarea-notas` (mono), `textarea-doc` (texto corrido), `switch`/`slider`, `toggle-row`, `switch-container` |
| Pestañas | `input-mode-tabs` / `tab-row`, `tab-item(.active)`, `.count` |
| Subida | `file-uploader(.over)`, `uploader-title/desc`, `uploaded-file-preview`, `file-info/name/size`, `recorder-panel`, `recording-timer`, `waveform-visualizer`, `recorder-controls` |
| Estudio | `main-container` (grid 1fr/420 px; `--una-columna` sin configurador), `extraction-panel`, `panel-toolbar`, `meta-info-strip`, `meta-item/label/value`, `tab-content-container`, `section-header-sm`, `executive-summary-text`, `summary-bullets`, `agreements-list`, `agreement-card/tag/title/meta` (`agreement-card--hecho`: borde verde, p. ej. cambio de un acta ya aplicado), `cita`, `transcript-stream`, `transcript-item`, `speaker-name/time`, `transcript-text` |
| Configurador | `configurator-panel` (sticky), `config-content`, `config-title`, `config-group(-title)`, `options-grid`, `option-card(.selected, .radio)`, `check-box`, `tone-selector`, `tone-btn(.selected)`, `config-footer` |
| Documento | `main-layout`, `document-container(.editing, --ancho sin límite de 920 px)`, `doc-header`, `doc-headline`, `metadata-grid`, `meta-key/val`, `doc-section`, `executive-summary-box`, `topics-list`, `topic-card/title/desc`, `md`, `slide-card` (`--critico/alto/medio/bajo/neutro`, `__band`, `__body`, `__header`, `__kicker`, `__title`: un apartado = una diapositiva, banda vertical con el nombre de la sección coloreada por riesgo) |
| Asistente | `ai-drawer(.abierto)` (`--plegable`: oculto hasta que se abre con `drawer-toggle--fijo`, y entonces flota fijo a la derecha por encima del documento, sin ocupar columna), `drawer-header/title/body`, `prompt-section-label`, `prompt-chips`, `prompt-chip`, `chat-history`, `chat-bubble(-user/-ai)`, `drawer-input-area`, `input-wrapper`, `ai-input`, `send-btn`, `drawer-toggle` |
| Carga y transición | `transicion-ruta` (contenedor del `Outlet` con `key={pathname}`: fundido de entrada en cada ruta, la cabecera no se anima), `aparece` (fundido del contenido real al llegar), `esqueleto` (`--titulo`, `--bloque`: silueta con brillo mientras carga). Solo opacity + translateY sin fill-mode; todo respeta `prefers-reduced-motion` |
| Flujo por pasos | `pasos` (`__lista`, `__li`, `__item` `--activo`/`--hecho`/`--aviso`, `__num`, `__titulo`, `__siguiente`, `__resumen`, `__extra`: barra de pasos siempre navegables con el aspecto de `tab-item` —número en mono, título en mayúsculas, subrayado en el activo, estado en una línea (color de aviso si hay algo pendiente), `tag tag-info` «Siguiente»; sin iconos ni círculos), `paso-cabecera` (`__kicker`, `__titulo`, `__ayuda`), `aviso-paso` (`--info`, `--aviso`, `__texto`, `__accion`), `paso-pie` |
| Estado | `progress-panel`, `progress-bar`, `progress-parts` (`.hecha/.en_curso/.error`), `result-box(.error)`, `toast(--error)`, `modal-overlay`, `modal` (`--ancho`), `modal-actions`, `menu-flotante(.open)`, `menu-flotante__lista` |
| Texto técnico | `diff-view` (`__add`, `__del`, `__meta`: diff unificado plegable), `diff-doc` (`__fila` `--add`/`--del`, `__signo`, `__texto`, `__marca`, `__plegado`, `__lector`: cambios sobre el documento estilo GitHub, una fila por párrafo o viñeta, palabras cambiadas marcadas; tokens `--c-diff-*`), `diff-cuenta` (`__mas`, `__menos`: «+12 −4»), `diff-resumen` (`__texto`: franja de resumen y selector de versión), `mono-block` (prompt/respuesta de una traza), `kpi-row--sin-borde` (KPIs compactos dentro de un panel) |

Textos largos: los nombres de fichero y demás textos sin espacios se parten (`overflow-wrap: anywhere` en `file-name`,
`td-title`, `modal`, `toast`, `result-box`, avisos…) y las columnas de las rejillas tienen `min-width: 0`: un nombre
largo nunca ensancha la página ni se sale de un modal. Las subidas validan el formato ANTES de enviar (al arrastrar,
el navegador no aplica `accept`).

Responsive: 1180 px (estudio a una columna, cajón del asistente como panel fijo), 1024 px
(padding 32, rejillas a 2), 768 px (padding 16, navegación central oculta, tablas con scroll).

## 4. Componentes compartidos (`components/ui.tsx`)

| Componente | Uso |
|---|---|
| `Logo`, `Loader`, `Spinner` | marca y estados de carga. |
| `NotificacionesProvider` + `useNotificar()` | `notificar({ texto, error? })`: toast negro abajo (rojo si error). Todo error de API se notifica con el `error` que devuelve el backend. |
| `ConfirmProvider` + `useConfirmar()` | `await confirmar({ titulo, cuerpo, accion, peligro })` → modal propio. Obligatorio antes de borrar o sobreescribir. |
| `Modal` | diálogo genérico (Escape cierra); `ancho` para contenido extenso (trazas, editor Markdown). |
| `EstadoTag`, `RiesgoTag`, `SeveridadTag`, `PlanTag` (revisor) · `OrigenTag`, `PrioridadTag`, `EstadoTareaPill` (actas) | etiquetas por valor (mapas en `lib/formato.ts`). Añade aquí las de tu dominio. |
| `Markdown` | único renderizador de Markdown. |
| `Esqueleto`, `EsqueletoFilas`, `EsqueletoDocumento` | siluetas con la forma del contenido real (mismos anchos y nº de bloques) en la primera carga; el mensaje «vacío» solo se muestra con `!cargando`. |
| `SlideCard` | tarjeta-diapositiva: `banda` (texto vertical), `nivel` (color por riesgo), `kicker`, `titulo`, `tools`. |
| `DiffView` | diff unificado coloreado y plegable (`abiertoInicial`); toda salida con `diff` del backend se muestra con él. |
| `Pasos`, `PasoCabecera`, `PasoPie`, `Aviso` | flujo de trabajo por pasos en una sola pantalla: barra con el estado de cada paso en texto (aviso en su color, «Siguiente» en el sugerido; todos navegables), cabecera del paso (para qué sirve + qué toca ahora), pie «← anterior / Continuar: siguiente →» y franjas de aviso con acción. El estado lo calcula la API. |
| `DiffDocumento`, `DiffCuenta`, `CambioTag` | cambios estructurados del backend sobre el documento (líneas `igual/add/del` con `segmentos` de palabra; pliega lo que no cambia), recuento +/− y estado del apartado (añadido / modificado / eliminado). |
| `ResultBox` | mensaje multilínea de un trabajo (error en rojo). |
| `Dropzone` | un fichero (`onFichero`) o varios (`onFicheros`), arrastrar o clic, `accept`. |
| `Switch`, `MenuFlotante`, `Progreso` | interruptor IDS, menú desplegable de acciones, panel de progreso de un job con «Detener». |

## 5. Patrones de pantalla

Cada pantalla arranca de un mockup HTML del IDS (pídelo o hazlo primero) y se monta con estas plantillas:

1. **Portada**: `Cabecera brand` + `hero-section` (eyebrow, título, subtítulo, CTA primario) + `kpi-row` con datos reales de la API. Nada más: listados, catálogos y analítica van en sus propias rutas (`/actas`, `/plantillas`, `/analitica`) enlazadas desde la navegación central.
2. **Listado**: `Cabecera` con buscador en la zona derecha, `section-header` con filtros (`text-input--small`, `select-input`), `ids-table` con `td-acciones` (botones `btn-ghost` según estado + papelera con confirmación). Se refresca sola mientras haya filas «procesando».
3. **Alta / formulario**: `page-container` con `workspace-grid` (1fr / 400 px): izquierda la fuente (pestañas `input-mode-tabs`, `Dropzone`, previsualización), derecha los metadatos (`form-group` + `input-label` + `text-input`) y el `btn-primary btn-block` de envío con barra de progreso de subida.
4. **Estudio / edición** (si el trabajo tiene fases, como un informe: **espacio de trabajo por pasos**, una sola ruta con `?paso=`, `Pasos` bajo la cabecera, `PasoCabecera` + contenido + `PasoPie` en cada paso; nunca «ir a otra pantalla y volver con la flecha». Si tras la primera pasada se itera sobre el resultado, la barra pasa a mostrar las superficies de iteración y los pasos previos quedan tras un botón «Añadir más …» con «Volver»): `main-container` con `extraction-panel` (`panel-toolbar` con `meta-info-strip` + `tab-row`, contenido por pestaña) y `configurator-panel` sticky (grupos de `option-card`, `tone-selector`, `switch-container`, `config-footer` con la acción principal). Mientras se procesa, `Progreso` a pantalla completa; si falla, `progress-panel` con `ResultBox` de error y «Reintentar».
5. **Documento / informe**: `toolbar` sticky (estado a la izquierda, acciones a la derecha: editar/guardar, `MenuFlotante` de descargas, exportar) + `main-layout` con `document-container` (cabecera editable con `contentEditable` solo en modo edición, tablas `ids-table`, `topic-card`) y `ai-drawer` a la derecha (chips de prompts, historial, entrada).

Reglas: los KPIs y contadores son reales (de la API), los estados de proceso se muestran con
`status-tag`, toda acción larga usa `useJob` y muestra progreso, toda acción destructiva confirma.

### Carga sin pantallas vacías

- **Transición de ruta:** `Layout` envuelve el `Outlet` en `.transicion-ruta` con `key={pathname}`.
- **Caché de datos:** los hooks de datos compartidos guardan la última respuesta en una variable de módulo y la usan como estado inicial; pintan al instante lo conocido y refrescan por detrás (`cargando` solo en la primera visita). Lo que casi no cambia se memoiza en `client.ts` con una promesa por sesión que se anula si falla.
- **Esqueletos + `.aparece`:** nunca se devuelve una página vacía o un loader suelto; se pinta la silueta y el contenido entra con fundido.

## 6. Contrato con la API

- Base `/api`, JSON, cookie de sesión. Errores `4xx/5xx` con `{ "error": "mensaje para el usuario" }`; el front lo muestra tal cual.
- **Trabajos largos** (modelo, transcripción, exportaciones pesadas): la API devuelve `{ job_id }`; `GET /api/jobs/{id}` → `{ estado: en_curso|ok|error, mensaje, resultado, progreso, progreso_pct, progreso_partes }`; `POST /api/jobs/{id}/detener`. El front usa `esperarJob` (polling 2 s) o el hook `useJob` (`lanzar`, `seguir`, `detener`, `job`, `activo`). El `job_id` de un alta se guarda en `sessionStorage` (`job:<id>`) para que la pantalla de destino siga el progreso tras la navegación.
- `api/types.ts` es la **única** fuente de tipos: se escribe a partir del JSON real del backend, con los mismos nombres de campo (snake_case). `interface Api` declara cada endpoint como método; `client.ts` los implementa; nada llama a `fetch` fuera de `client.ts`.
- Subidas: multipart por `XMLHttpRequest` para tener progreso real (`postConProgreso`). Descargas: URLs directas (`urlExportar…`) abiertas por el navegador con la cookie.
- Sin mocks salvo que se pidan: el front se prueba contra la API real o un proveedor «simulado» del backend.

## 7. Sesión

- `public/acceso.html` es autocontenido (sin bundle) y hace `POST /api/acceso/login` con `{ password }`; con 204 recarga la URL (nginx la sirvió en el sitio al que iba el usuario).
- `nginx.conf`: `auth_request /_auth` → `GET /api/acceso/verificar` en cada petición; sin sesión, `/` y `/assets` responden con `acceso.html` (redirect interno) y `/api` con 401. Públicos: `/acceso.html` y `/api/acceso/login`. `client_max_body_size` y `proxy_read_timeout` altos para subidas y trabajos largos.
- `client.ts`: cualquier 401 → `location.reload()` (nginx) o `/acceso.html` (vite en desarrollo, `import.meta.env.DEV`).
- El backend expone `login`, `verificar`, `logout` y además rechaza con 401 cualquier `/api` sin cookie (doble puerta).

## 8. Docker y ejecución

- `frontend/Dockerfile`: `npm ci` + `npm run build` en node, `dist/` a nginx con `nginx.conf`.
- `docker-compose.yml`: servicio `frontend` publica `${PUERTO}:80` y depende del `backend` sano; `dev.docker-compose.yml` monta el código y arranca `vite` (proxy `/api` → backend).
- `npm run types:check && npm run build` deben pasar en verde antes de entregar.

## 9. Checklist de entrega de una pantalla

- [ ] Parte de un mockup IDS y usa solo clases del catálogo (§ 3); si falta una, se añade a `custom.css` con nombre BEM y se documenta aquí.
- [ ] Tipos nuevos en `api/types.ts`, método en `interface Api` y en `client.ts`.
- [ ] Acciones largas con `useJob` + progreso; destructivas con `useConfirmar`; errores con `useNotificar`.
- [ ] Sin lógica de negocio: el front solo compone, filtra y muestra.
- [ ] Textos en español, sin Lorem ni datos inventados (los KPIs salen de la API).
- [ ] Responsive a 1180/1024/768 comprobado.
- [ ] `tsc` sin errores; build sin warnings nuevos.

## 10. Kit: ficheros que se copian tal cual a otro proyecto

Desde `frontend/`: `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `Dockerfile`,
`.dockerignore`, `nginx.conf`, `public/acceso.html`, `src/main.tsx`, `src/assets/styles/tokens.css`,
`src/assets/styles/custom.css`, `src/components/ui.tsx`, `src/layout/layout.tsx`, `src/layout/layout.css`,
`src/hooks/useJob.ts`, `src/lib/formato.ts` (quita las funciones de dominio que no apliquen) y
`src/api/client.ts` (deja `req`, `json`, `postConProgreso`, `aLogin` y reescribe `clienteReal`).
Se reescriben por proyecto: `src/api/types.ts`, `src/app.tsx`, `src/pages/*`, la navegación `NAV` de
`layout.tsx` y los textos de `acceso.html`.

---

## 11. Prompt para otro Claude Code

Pega esto (adaptando corchetes) en el proyecto destino, junto con esta guía y el kit:

```
Construye el front de [NOMBRE DE LA APLICACIÓN] siguiendo al pie de la letra docs/GUIA_FRONT_HOMOGENEO.md
(la guía del front homogéneo de Inditex/IDS que acompaña a este mensaje) y el kit de ficheros de
frontend/ que ya está copiado en este repositorio.

Reglas que no se rompen:
1. Estructura exacta de la guía (§ 2): backend/ y frontend/ separados; frontend en Vite + React 18 +
   TypeScript strict; nginx con auth_request y public/acceso.html como puerta de sesión (§ 7).
2. Solo clases del catálogo visual (§ 3) y componentes de components/ui.tsx (§ 4). Si necesitas una
   clase o componente nuevo, añádelo al kit con nombre BEM y documéntalo en la guía; no lo improvises
   en una página.
3. Cada pantalla se monta con uno de los patrones de § 5 (portada / listado / alta / estudio /
   documento) a partir de su mockup HTML del IOP Design System: [RUTA DE LOS MOCKUPS]. La portada solo
   lleva hero + KPIs; listados, catálogos y analítica van en rutas propias.
4. api/types.ts se escribe a partir del JSON real de la API (mismos nombres de campo); todo endpoint
   es un método de `interface Api` implementado en client.ts; nada llama a fetch fuera de ahí.
5. Trabajos largos con useJob y progreso; destructivas con useConfirmar; errores con useNotificar y el
   `error` del backend. Sin lógica de negocio en el front. Interfaz en español.
6. Entrega: `npm run types:check && npm run build` en verde, Dockerfile + nginx.conf del kit, y el
   checklist de § 9 cumplido para cada pantalla.

Pantallas a construir: [LISTA: ruta → patrón → mockup → endpoints que consume].
```

## 12. Proyectos que siguen la guía

- **Generador de actas** (`report-generator/frontend`): origen del kit y de los mockups de `docs/mockups/`.
- **Revisor de informes de auditoría interna** (`revisor-informes/frontend`): portada `/`, listado `/informes`,
  alta `/nuevo`, espacio de trabajo `/informes/:ref?paso=` (primera pasada Documentos → Contexto → Observaciones → Informe;
  después se itera: Informe · Reuniones · Exportación, con «Añadir más contexto» para volver a los tres pasos
  previos; el informe tiene las vistas Documento · Últimos cambios —apartados cambiados en verde/rojo contra cualquier
  versión del historial— y el cajón del asistente con cambios, buzón, revisión e historial) y reglas `/reglas` (documento editable del criterio de estilo + cajón plegable «Modificar usando el chat»: el modelo propone, el auditor carga la propuesta y guarda). Aporta al kit `textarea-doc`, `diff-view`, `mono-block`, `modal--ancho`,
  `kpi-row--sin-borde`, `main-container--una-columna`, `slide-card`, `SlideCard`, `ai-drawer--plegable`, `drawer-toggle--fijo`, `section-grid`, `document-container--ancho`, `DiffView`, `diff-doc`/`DiffDocumento`/`DiffCuenta`/`CambioTag`, `pasos`/`Pasos`/`PasoCabecera`/`PasoPie`/`Aviso` y las etiquetas `EstadoTag`/`RiesgoTag`/`SeveridadTag`/`PlanTag`.
  Pantallas y endpoints en `frontend/README.md`.
