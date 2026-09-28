# Front del revisor de informes

Vite + React 18 + TypeScript (`strict`), construido con el **kit del front homogéneo**
Inditex/IDS: `docs/GUIA_FRONT_HOMOGENEO.md` fija la estructura, el catálogo de clases
(`src/assets/styles/custom.css`), los componentes compartidos (`src/components/ui.tsx`),
el seguimiento de trabajos largos (`src/hooks/useJob.ts`), las utilidades de formato
(`src/lib/formato.ts`), el contrato con la API y la sesión (nginx `auth_request` +
`public/acceso.html`). Una pantalla nueva se compone con esas piezas; si falta una clase
o un componente, se añade al kit con nombre BEM y se documenta en la guía.

Fuera del entorno corporativo no se pueden instalar `@inditex/*` (registro privado), así que
`src/assets/styles/tokens.css` define los tokens `--ids-*`; en corporativo se sustituye por
`@inditex/sewingiopdsweb-styles`. El logotipo se carga del CDN de AMIGA con marca
tipográfica de respaldo.

## Uso

```bash
npm install
npm run dev          # http://localhost:3030, proxy /api → http://localhost:8000 (arranca antes `./revisor web`)
npm run build        # tsc --noEmit + vite build → dist/ (lo sirve `./revisor web` o el nginx del Dockerfile)
npm run types:check
```

No hay mocks: el front se prueba contra la API real (`./revisor web`). En Docker,
`frontend/Dockerfile` construye `dist/` y lo sirve con nginx (`nginx.conf`: SPA + proxy
`/api` + puerta de sesión; ver la guía § 7 y § 8).

## Pantallas (ruta → patrón de la guía § 5 → API)

| Ruta | Patrón | Qué hace | Endpoints |
|---|---|---|---|
| `/` | Portada | Hero y KPIs reales de la cartera (informes, en curso, emitidos, conclusiones aprobadas). | `GET /expedientes`, `GET /salud` |
| `/informes` | Listado | Tabla con buscador y filtro de estado; abrir, ver informe, eliminar (con la referencia escrita). | `GET /expedientes`, `DELETE /expedientes/{ref}` |
| `/nuevo` | Alta | Documentos de entrada (papeles de trabajo / contexto) + datos del informe; crea y sube con progreso. | `POST /expedientes`, `POST …/documentos/{carpeta}` |
| `/informes/:ref?paso=` | Espacio de trabajo por pasos | Una pantalla por informe con dos momentos (`modo` de la API). Primera pasada: Documentos → Contexto → Observaciones → Informe. Iteración (el informe ya tiene observaciones): Informe (a mano o con el chat) · Reuniones · Exportación, y «Añadir más contexto» abre los tres pasos previos con «Volver al informe» (lo pendiente allí se avisa en el botón). Todos los pasos siempre navegables. La API dice el estado de cada paso, el sugerido y qué toca (`pasos`, `paso_sugerido`, `sugerencia`); cada paso tiene cabecera con para qué sirve y pie «Continuar». Lo nuevo sin procesar se avisa y se incorpora sin rehacer lo revisado («Extraer sus observaciones»; «Pasar al informe…» con vista previa y modo añadir/rehacer). `?paso=trazas` para las trazas; `?pestana=` y `/informes/:ref/informe` antiguos redirigen. | estado, documentos, informe, conclusiones, acciones (jobs), `extraer {solo_nuevos}`, `redactar-conclusiones {modo, simular}`, reuniones, transcripción, trazas, ppt, archivar |
| `/reglas` | Documento | Criterio de estilo (config/estilo.yaml) editable por secciones o como YAML, historial con restauración y cajón «Modificar usando el chat» (el modelo propone; el auditor carga la propuesta en el editor y guarda). | `GET/PUT /reglas`, `POST /reglas/restaurar`, `POST /reglas/chat` (job) |
| `…?paso=informe&vista=` | Documento | Dos vistas: Documento (apartado a apartado, cada uno una diapositiva; edición de introducción/resumen/evaluación) y Últimos cambios (el informe entero, todas las secciones en su orden y sin plegar, con lo cambiado en verde/rojo, contra el último cambio, cualquier versión del historial o el último PowerPoint: `&desde=ppt`, que abre en otra pestaña el botón «¿Qué ha cambiado?» del aviso de PowerPoint desactualizado y de Exportación); dos paneles a la derecha, cerrados por defecto y excluyentes (como en el generador de actas): «Revisar vocabulario» (hallazgos resaltados en el documento + propuestas del modelo por párrafo, aplicables una a una o todas) y «Modificar con el chat» (chat de cambios y buzón de instrucciones). | informe, revisar, `proponer-correcciones` (job), `aplicar-correccion`, cambio, instrucciones, aplicar-cambios, reunion, `GET /informe/comparacion?contra=|desde=ppt`, deshacer |

## Estructura

```
src/api/          types.ts (contrato: tipos + interface Api), client.ts (fetch a /api), index.ts (api, esperarJob)
src/components/   ui.tsx: Logo, Loader, notificaciones, confirmaciones, Modal, etiquetas, Markdown, DiffView, DiffDocumento, Pasos, PasoCabecera, PasoPie, Aviso, ResultBox, Dropzone, Switch, MenuFlotante, Progreso
src/hooks/        useJob: lanzar / seguir / detener un trabajo largo con progreso
src/layout/       Cabecera IDS (brand / normal, navegación central, buscador, cierre de sesión) + Layout (Outlet)
src/lib/          formato: fechas, tamaños, fases, clases por valor (estado, riesgo, severidad, plan)
src/pages/        inicio · informes · nuevo · reglas · estudio (espacio de trabajo: entrada, contexto, conclusiones, informe + reunion, entregables, trazas)
```
