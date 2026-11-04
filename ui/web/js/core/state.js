/* Estado compartido de la pagina. Los modulos lo leen; main.js lo actualiza. */

export const S = {
  view: 'entorno',
  env: null,          // /api/env
  envAt: 0,           // cuando se midio por ultima vez
  status: null,       // /api/status
  rows: [],           // metricas por segundo de la corrida (ya limpias)
  conectado: true,
};

/** Cupo de conexiones del portal (MAX_CONNECTIONS en scripts/mininet/roles.py). */
export const PORTAL_CUPO = 30;

/** Las 5 areas academicas (mismas que AREAS en roles.py). Solo para dibujar. */
export const AREAS = [
  { key: 'salud', titulo: 'Salud', sw: 's3' },
  { key: 'ing', titulo: 'Ingenierías', sw: 's4' },
  { key: 'emp', titulo: 'Admin.', sw: 's5' },
  { key: 'soc', titulo: 'Sociales', sw: 's6' },
  { key: 'agr', titulo: 'Agrarias', sw: 's7' },
];

export const FASES = {
  inactivo:    { txt: 'Sin simulación',     tone: '',     icon: 'info' },
  arrancando:  { txt: 'Arrancando la red',  tone: 'warn', icon: 'clock' },
  navegando:   { txt: 'Tráfico normal',     tone: 'good', icon: 'check' },
  atacando:    { txt: 'Atacando',           tone: 'crit', icon: 'alert' },
  verificando: { txt: 'Verificando',        tone: 'warn', icon: 'clock' },
  cerrando:    { txt: 'Cerrando',           tone: '',     icon: 'clock' },
  listo:       { txt: 'Terminó bien',       tone: 'good', icon: 'check' },
  error:       { txt: 'Terminó con error',  tone: 'crit', icon: 'x' },
  detenido:    { txt: 'Detenida',           tone: '',     icon: 'stop' },
};

/** Catalogo por id, desde /api/env. */
export function catalogo() {
  const m = {};
  for (const s of (S.env && S.env.scenarios) || []) m[s.id] = s;
  return m;
}
