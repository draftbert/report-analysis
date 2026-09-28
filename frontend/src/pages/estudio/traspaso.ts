/* Grabación soltada en un sitio que no es el suyo (Documentos): se guarda aquí para que la vista
   Reuniones con el área la reciba ya cargada, sin volver a elegirla. Vive solo en memoria de la pestaña.
   Leer y olvidar van por separado: en desarrollo React ejecuta dos veces el inicializador del estado. */
let pendiente: File | null = null;

export const dejarGrabacion = (f: File) => { pendiente = f; };
export const verGrabacion = (): File | null => pendiente;
export const olvidarGrabacion = () => { pendiente = null; };
