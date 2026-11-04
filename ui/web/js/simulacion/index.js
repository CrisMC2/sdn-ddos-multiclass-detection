/* Modulo Simulacion: configurar, lanzar y ver la simulacion en un solo lugar.
   Coordina las piezas: config, campus (con paquetes), avance, tarjetas,
   graficos y resumen. */
import { $, h, ico } from '../core/dom.js';
import { post } from '../core/api.js';
import { emit, on } from '../core/bus.js';
import { FASES, S } from '../core/state.js';
import { initConfig } from './config.js';
import { pausarCampus, renderCampus } from './campus.js';
import { initCharts, renderCharts } from './charts.js';
import { initResumen, renderLogs, renderSummary } from './resumen.js';
import { reiniciarStepper, renderStepper } from './stepper.js';
import { renderTiles } from './tiles.js';

function pintarCabecera() {
  const st = S.status;
  const hay = st && st.run_name && st.scenario !== 'verify';
  $('#h-stage').textContent = hay ? ((st.scenario_info && st.scenario_info.nombre) || st.scenario) : 'Campus en reposo';
  const pill = $('#lh-pill');
  pill.hidden = !hay;
  if (hay) {
    const f = FASES[st.fase] || FASES.inactivo;
    pill.className = 'pill ' + f.tone;
    pill.replaceChildren(ico(f.icon), f.txt);
  }
  $('#lh-sub').textContent = hay
    ? st.run_name + (st.elapsed != null ? ' · t+' + Math.round(st.elapsed) + ' s' : '')
    : 'Configura una simulación arriba y el campus cobrará vida.';
  const stop = $('#btn-stop');
  stop.hidden = !(hay && st.activo);
  stop.disabled = !st.activo;
  const err = $('#live-error');
  err.hidden = !(hay && st.fase === 'error');
  err.textContent = hay && st.fase === 'error'
    ? (st.error || 'La simulación terminó con error (código ' + (st.exit_code || '?') + '). Abre el registro del contenedor para ver por qué.') : '';
}

function render() {
  const st = S.status; if (!st) return;
  const hay = st.run_name && st.scenario !== 'verify';
  $('#sim-data').hidden = !hay;
  pintarCabecera();
  renderCampus();
  renderStepper();
  if (hay) {
    renderTiles();
    renderCharts();
    renderSummary();
    renderLogs();
  }
}

export function initSimulacion() {
  initConfig();
  initCharts();
  initResumen();

  $('#btn-stop').addEventListener('click', async () => {
    $('#btn-stop').disabled = true;
    await post('/api/parar');
    emit('pedir-estado');
  });

  on('lanzada', () => { reiniciarStepper(); });
  on('status', () => { if (S.view === 'simulacion') render(); });
  on('vista', (v) => {
    pausarCampus(v === 'simulacion');
    if (v === 'simulacion') render();
  });
  // Los graficos se miden al ancho del contenedor: repintar al cambiar de tamano.
  new ResizeObserver(() => { if (S.view === 'simulacion' && S.status) requestAnimationFrame(renderCharts); }).observe(document.body);
}
