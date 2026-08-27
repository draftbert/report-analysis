/* Modo mock (VITE_MOCK=1): la app funciona sin back-end con los datos de ejemplo
   del expediente TEC-2026. Los trabajos del modelo se simulan con 2 s de espera. */
import type { Acta, Api, Conclusion, Documentos, Estado, ExpedienteEstado, Hallazgo, Informe, Job, ResultadoCambios, Traza, Version } from "./types";

const C01: Conclusion = {
  id: "C-01", titulo: "Mantenimiento manual y desactualización del maestro de tarifas", tipo: "recomendacion", estado: "aprobada",
  prueba: "2.11 b) Gestión del maestro de tarifas", nivel_riesgo: "Alto", riesgo_propuesto: false, area: "Transporte e-Commerce",
  responsable: "Pablo Nieto (1.1); Operativa (1.2)", plazo: "31/03/2027 (1.1); 31/12/2026 (1.2)", referencia_recomendacion: "TMSCIIF-10",
  fuente: "papel_trabajo.txt — 2.11 CONCLUSIONES",
  incidencia: "El mantenimiento del maestro de tarifas en la Herramienta de Costes es un proceso manual sin una plantilla común. Durante nuestra revisión hemos identificado que los acuerdos alcanzados entre Operativa y los proveedores no siempre se transmiten al equipo de validación.",
  causa_raiz: "Proceso dependiente de tareas manuales y formatos heterogéneos por courier.",
  como_se_ha_llegado: "- Los equipos de validación (BDO, Serviguide e Inditex - China) actualizan el maestro manualmente, incluso a nivel de Código Postal.\n- Cada pedido validado se registra en Snowflake (TRANSPORT_BUSINESS.FOUNDATION.COSTES_ECOM_DETALLE).\n- Existen alertas diarias y una revisión semanal de Transport Business Analytics.",
  consecuencias: "La manualidad incrementa el riesgo de tarifas desactualizadas en la Herramienta de Costes, que se traslada a CPF y a la asignación de transportistas en SCA. Respecto a la materialización, no ha sido posible cuantificar el impacto económico.",
  recomendacion: "Implantar un sistema para la carga y gestión de los tarifarios de todas las operativas de transporte.\n\nEstablecer un procedimiento que deje evidencia de los acuerdos alcanzados con los proveedores y garantice su trazabilidad con las tarifas cargadas.",
  notas: "",
};
const C02: Conclusion = {
  ...C01, id: "C-02", titulo: "CPF hereda deficiencias en la valoración de casuísticas minoritarias (COD, zonas remotas)", estado: "propuesta",
  prueba: "2.11 a) Contrastar el tarifario negociado", nivel_riesgo: "Medio", riesgo_propuesto: true, area: "", responsable: "", plazo: "", referencia_recomendacion: "",
  incidencia: "CPF entrena sobre facturas en bruto y no discrimina conceptos como Cash On Delivery, linehaul o zonas remotas, lo que induce estimaciones de coste sesgadas para esas casuísticas.",
  causa_raiz: "Limitaciones del modelo de inferencia y ausencia de desglose de conceptos en la factura.",
  como_se_ha_llegado: "- El COD no es un concepto desglosado en la factura pero genera extracargos.\n- La definición de «zona remota» depende de cada courier.",
  consecuencias: "Asignaciones de transportista subóptimas en SCA para pedidos con estas casuísticas.", recomendacion: "",
};
const C03: Conclusion = {
  ...C01, id: "C-03", titulo: "Documentación del control de alertas diarias y revisión semanal", tipo: "sugerencia", estado: "aprobada",
  nivel_riesgo: "Bajo", riesgo_propuesto: false, area: "Transport Business Analytics", responsable: "", plazo: "", referencia_recomendacion: "",
  incidencia: "Existen alertas diarias y una revisión semanal de Transport Business Analytics para detectar inputs no entrenados por CPF, pero no están documentadas en ningún procedimiento.",
  causa_raiz: "", como_se_ha_llegado: "", consecuencias: "Dependencia de la práctica del equipo sin control formalizado.",
  recomendacion: "Documentar y formalizar el control de alertas diarias y la revisión semanal de Transport Business Analytics.",
};

let conclusiones: Conclusion[] = [C01, C02, C03];
let introduccion = `La auditoría ha sido realizada en cumplimiento del Plan de Auditoría del año 2026, aprobado por la Comisión de Auditoría y Cumplimiento.

**Contexto:** El coste de transporte se ha incorporado como criterio directo de asignación de transportistas en pedidos de e-Commerce mediante la herramienta SCA, cuyo desarrollo sigue en curso.

**Objetivo de la auditoría:** Asegurar la integridad de los tarifarios que alimentan la asignación de transportistas en SCA. Entre otros, los principales aspectos que se han revisado están relacionados con:
- Contraste del tarifario negociado frente al valor cargado en HC/CPF.
- Gestión del maestro de tarifas: responsables, formatos y controles de actualización.

**Riesgos a cubrir:**
- Tarifarios cargados en HC que no reflejan las condiciones acordadas con los couriers.
- Estimaciones de coste de CPF sesgadas para casuísticas concretas.

**Alcance de la auditoría:** Herramienta de Costes, Snowflake, CPF y SCA en los mercados donde está implantado; ejercicio en curso.

**Principales magnitudes:**
- 38 — Couriers con tarifario cargado en HC
- 12 — Mercados con SCA/CPF operativo
- 41,6 M — Pedidos e-Commerce valorados por HC en el último año
- 1,4 M€ — Reclamaciones de transporte relacionadas con tarifas (primer semestre)

El trabajo ha sido llevado a cabo de acuerdo con las Normas Internacionales para la Práctica Profesional de Auditoría Interna, según certificado emitido por el Instituto de Auditores Internos.`;
let resumen = `Transporte e-Commerce gestiona el maestro de tarifas utilizado para imputar costes de envío y alimentar al algoritmo CPF, que estima el coste por pedido para la asignación de transportistas en SCA.

A pesar de los controles operativos existentes, se han detectado deficiencias de control relevantes que se detallan a continuación:

/ El mantenimiento del tarifario es manual y sin plantilla común, lo que dificulta la estandarización y aumenta el riesgo de tarifas desactualizadas.
/ Hemos constatado la falta de trazabilidad entre los acuerdos negociados por Operativa y las tarifas cargadas en la Herramienta de Costes.
/ CPF presenta limitaciones frente a casuísticas minoritarias (COD, zonas remotas, linehaul), lo que puede sesgar la estimación de coste.

Cabe destacar que la recomendación TMSCIIF-10 de la Auditoría de Controles SCIIF 2022 sigue abierta.`;
let evaluacionGlobal = "Mejorable";
let instrucciones = "";
let docs: Documentos = {
  contexto: [{ nombre: "contexto_auditoria_tarifarios.md", bytes: 2830, lector: "texto" }],
  papeles_trabajo: [{ nombre: "papel_trabajo.txt", bytes: 16794, lector: "texto" }],
};
const historial: Version[] = [
  { fichero: "informe", nombre: "2026-08-27T10-12-00_02_informe_aplicar-cambios.md", fecha: "2026-08-27 10:12:00", motivo: "aplicar-cambios" },
  { fichero: "informe", nombre: "2026-08-27T09-40-11_02_informe_redactar-conclusiones.md", fecha: "2026-08-27 09:40:11", motivo: "redactar-conclusiones" },
  { fichero: "conclusiones", nombre: "2026-08-27T09-35-02_01_conclusiones_recomendar.md", fecha: "2026-08-27 09:35:02", motivo: "recomendar" },
];
const trazas: Traza[] = [
  { nombre: "2026-08-27T09-20-01_redactar-contexto.json", fecha: "2026-08-27T09:20:01", accion: "redactar-contexto", modelo: "gpt-5-mini", tokens: { prompt: 6120, completion: 2210 } },
  { nombre: "2026-08-27T09-25-40_extraer.json", fecha: "2026-08-27T09:25:40", accion: "extraer", modelo: "gpt-5-mini", tokens: { prompt: 7810, completion: 3320 } },
  { nombre: "2026-08-27T09-34-10_recomendar-C-02.json", fecha: "2026-08-27T09:34:10", accion: "recomendar-C-02", modelo: "gpt-5-mini", tokens: { prompt: 1410, completion: 380 } },
  { nombre: "2026-08-27T10-11-30_aplicar-cambios.json", fecha: "2026-08-27T10:11:30", accion: "aplicar-cambios", modelo: "gpt-5-mini", tokens: { prompt: 5230, completion: 1120 } },
  { nombre: "2026-08-27T10-30-05_reunion.json", fecha: "2026-08-27T10:30:05", accion: "reunion", modelo: "gpt-5-mini", tokens: { prompt: 6900, completion: 1900 } },
  { nombre: "2026-08-27T10-41-12_corregir.json", fecha: "2026-08-27T10:41:12", accion: "corregir", modelo: "gpt-5-mini", tokens: { prompt: 1200, completion: 300 } },
];
const jobs: Record<string, Job> = {};
let n = 0;

const espera = (ms: number) => new Promise((r) => setTimeout(r, ms));

function job(accion: string, fn: () => { mensaje: string; resultado?: unknown }, ms = 2200): Promise<{ job_id: string }> {
  const id = `mock-${++n}`;
  jobs[id] = { estado: "en_curso", accion, mensaje: "", resultado: null };
  setTimeout(() => {
    try {
      const r = fn();
      jobs[id] = { estado: "ok", accion, mensaje: r.mensaje, resultado: r.resultado ?? null };
    } catch (err) {
      jobs[id] = { estado: "error", accion, mensaje: String(err), resultado: null };
    }
  }, ms);
  return Promise.resolve({ job_id: id });
}

function apartadoMd(c: Conclusion, i: number, sug: boolean) {
  const recs = c.recomendacion.split(/\n\s*\n/).filter(Boolean);
  const meta = [`- Prueba: ${c.prueba}`, `- Nivel de riesgo: ${c.nivel_riesgo}`, `- Área: ${c.area}`, `- Responsable: ${c.responsable}`, `- Plazo: ${c.plazo}`, `- Ref. recomendación: ${c.referencia_recomendacion}`];
  const det = c.como_se_ha_llegado ? `*A continuación, se muestran los detalles descriptivos de la situación anterior:*\n${c.como_se_ha_llegado}\n\n` : "";
  return `### ${i}. ${c.titulo}\n\n${meta.join("\n")}\n\n${c.incidencia}\n\n${c.causa_raiz ? c.causa_raiz + "\n\n" : ""}${det}${c.consecuencias}\n\n` +
    recs.map((r, k) => `**${sug ? "Propuesta de mejora" : "Recomendación"} ${i}.${k + 1}.** ${r}`).join("\n\n");
}

function estado(): ExpedienteEstado {
  const aprobadas = conclusiones.filter((c) => c.estado === "aprobada");
  return {
    referencia: "TEC-2026", nombre: "Auditoría de Transporte e-Commerce: tarifarios y SCA", fecha: "Junio 2026",
    distribucion: ["Dirección de Transporte e-Commerce", "Dirección Financiera", "Comité de Auditoría"],
    fase: "3 · Informe en redacción", siguiente: "`recomendar`: C-02 sin recomendación (escríbela o que la proponga el modelo)",
    modificado: "2026-08-27T10:41:12", contexto: docs.contexto.map((d) => d.nombre), papeles: docs.papeles_trabajo.map((d) => d.nombre),
    conclusiones: {
      total: conclusiones.length, propuesta: conclusiones.filter((c) => c.estado === "propuesta").length, aprobada: aprobadas.length,
      descartada: conclusiones.filter((c) => c.estado === "descartada").length, sugerencias: conclusiones.filter((c) => c.tipo === "sugerencia").length,
      sin_recomendacion: aprobadas.filter((c) => c.tipo === "recomendacion" && !c.recomendacion).map((c) => c.id),
      riesgo_pendiente: aprobadas.filter((c) => c.riesgo_propuesto).map((c) => c.id), con_notas: conclusiones.filter((c) => c.notas).map((c) => c.id),
    },
    informe: { contexto: true, n_conclusiones: aprobadas.filter((c) => c.tipo === "recomendacion").length, n_sugerencias: aprobadas.filter((c) => c.tipo === "sugerencia").length, errores: 1, avisos: 2, modificado: "2026-08-27T10:41:12", versiones: historial.length },
    instrucciones_pendientes: instrucciones.trim().length > 0, ppt: { nombre: "ResumenEjecutivo_TEC-2026.pptx", desactualizado: true },
    archivos: ["TEC-2026_archivo_20260826-1300.zip"], llm: "kaia · gpt-5-mini (mock)",
  };
}

function informe(): Informe {
  const cs = conclusiones.filter((c) => c.estado === "aprobada" && c.tipo === "recomendacion");
  const ss = conclusiones.filter((c) => c.estado === "aprobada" && c.tipo === "sugerencia");
  const apartados = [
    { id: "introduccion", tipo: "introduccion" as const, titulo: "Introducción", markdown: introduccion, numero: 0, nivel_riesgo: "" as const },
    { id: "resumen", tipo: "resumen" as const, titulo: "Resumen ejecutivo", markdown: resumen + `\n\n**Evaluación global:** ${evaluacionGlobal}`, numero: 0, nivel_riesgo: "" as const },
    ...cs.map((c, i) => ({ id: `c${i + 1}`, tipo: "conclusion" as const, titulo: c.titulo, markdown: apartadoMd(c, i + 1, false), numero: i + 1, nivel_riesgo: c.nivel_riesgo })),
    ...ss.map((c, i) => ({ id: `s${i + 1}`, tipo: "sugerencia" as const, titulo: c.titulo, markdown: apartadoMd(c, i + 1, true), numero: i + 1, nivel_riesgo: c.nivel_riesgo || ("Bajo" as const) })),
  ];
  return { markdown: apartados.map((a) => a.markdown).join("\n\n"), apartados, evaluacion_global: evaluacionGlobal, conclusiones: cs, sugerencias: ss };
}

const HALLAZGOS: Hallazgo[] = [
  { linea: 42, tipo: "palabra_prohibida", severidad: "error", fragmento: "problema", mensaje: "Terminología estándar del informe.", sugerencia: "observación / debilidad" },
  { linea: 88, tipo: "frase_larga", severidad: "aviso", fragmento: "La manualidad del proceso y las dificultades de sincronización incrementan…", mensaje: "Frase de 61 palabras (límite 55). Dificulta la lectura.", sugerencia: "Dividir en dos o tres frases." },
];

const ACTA: Acta = {
  acta: "reuniones/2026-08-27_1030_transcript_reunion_teams.md",
  resumen: "Se revisó el borrador con la Dirección y el área auditada. Se acordó dividir la recomendación 1.1, elevar el riesgo de la conclusión 1 a Alto, acortar la segunda viñeta del resumen y añadir una sugerencia de mejora; los cambios de presentación se harán a mano.",
  cambios_texto: [
    { seccion: "Resumen ejecutivo", que_cambiar: "Acortar la segunda viñeta a una frase.", instruccion: "En el resumen ejecutivo, sustituir la segunda viñeta por una frase que sintetice la falta de actualización y comunicación de extracostes y casuísticas.", solicitado_por: "Carmen Soto (Directora)", cita: "la segunda viñeta es larguísima. Resumidla a una frase" },
    { seccion: "Conclusión 1", que_cambiar: "Elevar el nivel de riesgo a Alto.", instruccion: "En la conclusión 1, cambiar el nivel de riesgo de Medio a Alto.", solicitado_por: "Carmen Soto (Directora)", cita: "yo lo pondría en Alto" },
    { seccion: "Conclusión 1", que_cambiar: "Dividir la Recomendación 1.1 en 1.1 y 1.2 con área, responsable y plazo.", instruccion: "En la conclusión 1, sustituir la Recomendación 1.1 por dos: 1.1 implantar un sistema de carga y gestión de tarifarios; 1.2 establecer un procedimiento que deje evidencia de los acuerdos con proveedores.", solicitado_por: "Marta Rey (Gerente)", cita: "Yo la dividiría en dos, porque tienen responsables distintos" },
    { seccion: "Sugerencias de mejora", que_cambiar: "Añadir sugerencia sobre alertas diarias y revisión semanal.", instruccion: "Añadir una sugerencia de mejora (riesgo Bajo, área Transport Business Analytics): documentar y formalizar el control de alertas diarias y la revisión semanal.", solicitado_por: "Carmen Soto (Directora)", cita: "Añadidlo como sugerencia de mejora, riesgo bajo" },
  ],
  cambios_ppt: [
    { que_cambiar: "Magnitudes de la introducción en un gráfico de barras.", solicitado_por: "Carmen Soto (Directora)", cita: "quiero que las magnitudes vayan en un gráfico de barras" },
    { que_cambiar: "Usar la plantilla corporativa nueva (fondo blanco).", solicitado_por: "Carmen Soto (Directora)", cita: "que uséis la plantilla corporativa nueva" },
    { que_cambiar: "Detalles descriptivos en una diapositiva aparte como continuación.", solicitado_por: "Carmen Soto (Directora)", cita: "los detalles descriptivos en una diapositiva aparte" },
  ],
  pendientes: ["Importe anual facturado por los couriers para la introducción — lo aporta Pablo Nieto esta semana."],
  acuerdos_sin_cambio: ["Conformidad del área en diez días hábiles desde el envío de la versión final.", "Seguimiento en enero."],
};

const resultadoCambios = (mensaje: string): ResultadoCambios => ({
  plan: [
    { seccion: "### 1. Mantenimiento manual y desactualización del maestro de tarifas", motivo: mensaje, estado: "aplicado", detalle: "" },
  ],
  pendientes: [], diff: "--- 02_informe.md (antes)\n+++ 02_informe.md (después)\n@@ -33,5 +33,5 @@\n ### 1. Mantenimiento manual y desactualización del maestro de tarifas\n-- Nivel de riesgo: Medio\n+- Nivel de riesgo: Alto\n - Área: Transporte e-Commerce",
});

export const clienteMock: Api = {
  listarExpedientes: async () => [estado(), { referencia: "CNC-2026-03", nombre: "Auditoría de Compras No Comerciales", fecha: "Mayo 2026", fase: "2 · Conclusiones en revisión", siguiente: "Lee 01_conclusiones.md, ajusta y marca `Estado: aprobada`", modificado: "2026-08-20T17:05:00" }],
  crearExpediente: async (d) => ({ ...estado(), referencia: d.referencia, nombre: d.nombre, fecha: d.fecha, distribucion: d.distribucion, fase: "0 · Sin papeles de trabajo", siguiente: "Copia el papel de trabajo final a papeles_trabajo/", contexto: [], papeles: [], conclusiones: null, informe: null, ppt: null, archivos: [] }),
  estado: async () => estado(),
  eliminarExpediente: async (ref, confirmacion) => { if (confirmacion !== ref) throw new Error(`Para eliminar el expediente escribe exactamente su referencia: ${ref}`); return { mensaje: `Expediente ${ref} eliminado.` }; },
  job: async <T,>(id: string) => (jobs[id] ?? { estado: "error", accion: "?", mensaje: "Trabajo desconocido", resultado: null }) as Job<T>,
  documentos: async () => docs,
  subir: async (_ref, carpeta, ficheros) => { await espera(600); docs = { ...docs, [carpeta]: [...docs[carpeta], ...ficheros.map((f) => ({ nombre: f.name, bytes: f.size, lector: f.name.split(".").pop() ?? "texto" }))] }; return docs; },
  borrarDocumento: async (_ref, carpeta, nombre) => { docs = { ...docs, [carpeta as "contexto"]: docs[carpeta as "contexto"].filter((d) => d.nombre !== nombre) }; return docs; },
  redactarContexto: (_ref) => job("redactar-contexto", () => ({ mensaje: "Introducción y resumen ejecutivo redactados en 02_informe.md a partir de 1 documento(s) de contexto y 1 papel(es) de trabajo.\nRevisión determinista: 0 errores, 0 avisos ✔\nSiguiente: léelos y edítalos hasta que encajen; después `extraer` para pasar a las conclusiones." })),
  extraer: (_ref) => job("extraer", () => ({ mensaje: "Se han propuesto 3 conclusiones en 01_conclusiones.md:\n  C-01  [conc] [Alto* ] Mantenimiento manual y desactualización del maestro de tarifas  (2.11 b)) ✔ · rec. del PT (ref. TMSCIIF-10)\n  C-02  [conc] [Medio*] CPF hereda deficiencias en la valoración de casuísticas minoritarias  (2.11 a)) ✔ · sin recomendación\n  C-03  [suge] [Bajo* ] Documentación del control de alertas diarias y revisión semanal  ✔ · sin recomendación\n  (*) nivel de riesgo propuesto por el modelo sin evidencia en el PT: valídalo al aprobar." })),
  conclusiones: async () => ({ markdown: "", conclusiones }),
  guardarConclusion: async (_ref, id, campos) => { conclusiones = conclusiones.map((c) => (c.id === id ? { ...c, ...campos, riesgo_propuesto: (campos.estado ?? c.estado) === "aprobada" ? false : (campos.riesgo_propuesto ?? c.riesgo_propuesto) } : c)); return conclusiones.find((c) => c.id === id)!; },
  guardarConclusionesMd: async () => ({ conclusiones }),
  aprobar: async (_ref, ids, est: Estado) => { const todos = ids.includes("todas"); conclusiones = conclusiones.map((c) => (todos || ids.includes(c.id) ? { ...c, estado: est, riesgo_propuesto: est === "aprobada" ? false : c.riesgo_propuesto } : c)); return { mensaje: `Marcadas como «${est}»: ${todos ? conclusiones.map((c) => c.id).join(", ") : ids.join(", ")}.` }; },
  revisarConclusiones: async () => ({ hallazgos: [{ id: "C-02", tipo: "estructura", severidad: "aviso", fragmento: "recomendacion", mensaje: "Campo «recomendacion» pendiente (Recomendación (aportada por el auditor o propuesta con `recomendar`))." }] }),
  corregirConclusiones: () => job("corregir-conclusiones", () => ({ mensaje: "Corregidas: ninguna. Sin errores: C-01, C-02, C-03." })),
  regenerar: (_ref, id, notas) => job(`regenerar-${id}`, () => { conclusiones = conclusiones.map((c) => (c.id === id ? { ...c, notas: "", estado: "propuesta", incidencia: c.incidencia + " (regenerada según notas: " + notas + ")" } : c)); return { mensaje: `${id} regenerada (estado: propuesta; notas aplicadas y vaciadas). ✔ Sin errores de estilo.` }; }),
  recomendar: (_ref, o) => job("recomendar", () => {
    const lineas: string[] = [];
    conclusiones = conclusiones.map((c) => {
      if (c.estado !== "aprobada" || c.tipo !== "recomendacion" || c.recomendacion) { if (c.estado === "aprobada" && c.recomendacion && c.tipo === "recomendacion") lineas.push(`  ${c.id}: recomendación ya presente, se respeta tal cual.`); return c; }
      const r = o.respuestas[c.id];
      if (r && r.trim()) { lineas.push(`  ${c.id}: recomendación del auditor registrada tal cual.`); return { ...c, recomendacion: r.trim() }; }
      if (o.auto) { lineas.push(`  ${c.id}: recomendación propuesta por el modelo (revísala en el fichero).`); return { ...c, recomendacion: "Incorporar en CPF el desglose de los conceptos de COD, linehaul y zonas remotas, y validar periódicamente las estimaciones frente a las facturas reales." }; }
      lineas.push(`  ${c.id}: sin recomendación (no se ha contestado y no se pide proponer).`); return c;
    });
    return { mensaje: "Recomendaciones:\n" + lineas.join("\n") };
  }),
  redactarConclusiones: async () => { const bloq = conclusiones.filter((c) => c.estado === "aprobada" && c.tipo === "recomendacion" && !c.recomendacion); return { mensaje: `Detalle de conclusiones (${conclusiones.filter((c) => c.estado === "aprobada" && c.tipo === "recomendacion" && c.recomendacion).length}) y sugerencias de mejora (${conclusiones.filter((c) => c.estado === "aprobada" && c.tipo === "sugerencia").length}) volcados a 02_informe.md tal cual fueron aprobados (sin modelo).` + (bloq.length ? `\n⚠ NO incluidas: ${bloq.map((c) => c.id + " (sin recomendación)").join("; ")}` : "") }; },
  informe: async () => informe(),
  guardarInforme: async (_ref, d) => { if (d.introduccion !== undefined) introduccion = d.introduccion; if (d.resumen_ejecutivo !== undefined) resumen = d.resumen_ejecutivo; if (d.evaluacion_global !== undefined) evaluacionGlobal = d.evaluacion_global; return informe(); },
  revisar: async () => ({ hallazgos: HALLAZGOS, errores: 1, avisos: 1 }),
  corregir: () => job("corregir", () => ({ mensaje: "Párrafos reescritos: 1 de 1.\nSnapshot previo: historial/2026-08-27T10-41-12_02_informe_corregir.md (`deshacer` lo restaura).", resultado: { diff: "--- 02_informe.md (antes)\n+++ 02_informe.md (después)\n@@ -42,1 +42,1 @@\n-El problema se origina en la ausencia de un campo obligatorio.\n+La debilidad se origina en la ausencia de un campo obligatorio." } })),
  cambio: (_ref, mensaje) => job("cambio", () => ({ mensaje: "Aplicados 1 de 1 cambios. Registro en cambios_aplicados.md.", resultado: resultadoCambios(mensaje) })),
  instrucciones: async () => ({ texto: instrucciones }),
  guardarInstrucciones: async (_ref, texto) => { instrucciones = texto; return { texto }; },
  aplicarCambios: (_ref) => job("aplicar-cambios", () => { const r = resultadoCambios(instrucciones.split("\n")[0] ?? ""); instrucciones = ""; return { mensaje: "Aplicados 1 de 1 cambios. Registro en cambios_aplicados.md; 03_instrucciones.md vaciado (lo pegado queda en historial/).", resultado: r }; }),
  reunion: (_ref, _f, aplicar) => job("reunion", () => { instrucciones = ACTA.cambios_texto.map((c) => `- ${c.instruccion} [${c.solicitado_por}]`).join("\n"); return { mensaje: `El sistema ha detectado ${ACTA.cambios_texto.length} cambio(s) en el TEXTO del informe y ${ACTA.cambios_ppt.length} en el PPT (informativo).` + (aplicar ? "\n=== aplicar-cambios ===\nAplicados 4 de 4 cambios." : "\nLas instrucciones de texto se han añadido a 03_instrucciones.md."), resultado: ACTA }; }, 2600),
  historial: async () => historial,
  deshacer: async () => ({ mensaje: "02_informe.md restaurado desde historial/2026-08-27T10-12-00_02_informe_aplicar-cambios.md." }),
  diff: async () => ({ diff: resultadoCambios("").diff, contra: historial[0].nombre }),
  cambios: async () => ({ markdown: "## Cambios aplicados — 2026-08-27 10:12 (03_instrucciones.md)\n\n1. **[aplicado]** ### 1. … — Elevar el nivel de riesgo a Alto\n   - Antes: - Nivel de riesgo: Medio\n   - Después: - Nivel de riesgo: Alto" }),
  reuniones: async () => [{ nombre: "2026-08-27_1030_transcript_reunion_teams.md", fecha: "2026-08-27 10:30", markdown: `# Acta de cambios — reunión «transcript_reunion_teams»\n\n${ACTA.resumen}` }],
  ppt: async () => { await espera(800); return { nombre: "ResumenEjecutivo_TEC-2026.pptx", url: "#" }; },
  archivar: async () => { await espera(800); return { nombre: "TEC-2026_archivo_20260827-1100.zip", url: "#" }; },
  trazas: async () => trazas,
  traza: async (_ref, nombre) => ({ fecha: "2026-08-27T10:11:30", accion: nombre.split("_").slice(1).join("_").replace(".json", ""), modelo: "gpt-5-mini", system: "Eres un auditor interno senior…", user: "Un revisor ha hecho comentarios sobre el informe. Conviértelos en cambios concretos…\n\nCOMENTARIOS / INSTRUCCIONES:\nCambia el nivel de riesgo de la conclusión 1 a Alto.", respuesta: { cambios: [{ seccion: "### 1. …", motivo: "riesgo", texto_original: "- Nivel de riesgo: Medio", texto_nuevo: "- Nivel de riesgo: Alto" }], pendientes: [] }, usage: { prompt_tokens: 5230, completion_tokens: 1120 } }),
};
