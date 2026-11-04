/* Arranque de la interfaz: tema, rutas, modulos y el sondeo del estado. */
import { $ } from './core/dom.js';
import { api } from './core/api.js';
import { emit, on } from './core/bus.js';
import { cleanRows } from './core/format.js';
import { S } from './core/state.js';
import { initTheme } from './core/theme.js';
import { go, initRouter, vistaInicial } from './core/router.js';
import { cargarEntorno, initEntorno } from './entorno/entorno.js';

let timer = null;

async function tick() {
  const st = await api('/api/status');
  if (st) {
    const estabaActiva = S.status && S.status.activo;
    S.status = st;
    const hayCorrida = st.run_name && st.scenario !== 'verify';
    if (hayCorrida) {
      const m = await api('/api/metrics?n=600');
      if (m) S.rows = cleanRows(m.rows || []);
      const rec = await api('/api/recursos');
      S.recursos = rec ? rec.rows || [] : [];
    } else { S.rows = []; S.recursos = []; }
    // Al terminar una corrida cambian el puerto y el contenedor: se vuelve a medir.
    if ((estabaActiva && !st.activo) || Date.now() - S.envAt > 10000) cargarEntorno();
    pintarFranja(st);
    emit('status', st);
  }
  clearTimeout(timer);
  timer = setTimeout(tick, S.status && S.status.activo ? 1000 : 4000);
}

function pintarFranja(st) {
  $('#nav-live').hidden = !st.activo;
  document.body.classList.toggle('is-attack', st.activo && st.fase === 'atacando');
  const franja = $('#runstrip');
  franja.hidden = !st.activo;
  if (!st.activo) return;
  $('#rs-name').textContent = st.scenario === 'verify' ? 'Verificación de la red' : st.run_name;
  $('#rs-time').textContent = st.elapsed != null ? 't+' + Math.round(st.elapsed) + ' s' : '';
  $('#rs-go').textContent = st.scenario === 'verify' ? 'Ver detalle' : 'Ver simulación';
  franja.dataset.go = st.scenario === 'verify' ? 'entorno' : 'simulacion';
}

(async function init() {
  initTheme();
  initRouter();
  initEntorno();
  on('conexion', (ok) => { $('#conn-lost').hidden = ok; });
  on('pedir-estado', tick);
  $('#runstrip').addEventListener('click', (e) => go(e.currentTarget.dataset.go || 'simulacion'));

  // El modulo Simulacion se carga aparte: si falla, Entorno sigue funcionando.
  try {
    const sim = await import('./simulacion/index.js');
    sim.initSimulacion();
  } catch (e) {
    console.warn('Modulo Simulacion no disponible:', e.message);
  }

  await Promise.all([cargarEntorno(), tick()]);
  go(vistaInicial(S.status && S.status.activo && S.status.scenario !== 'verify'));
})();
