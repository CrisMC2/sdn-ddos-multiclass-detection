/* Resumen antes/durante el ataque, archivos generados y registro del contenedor. */
import { $, h, ico } from '../core/dom.js';
import { fmtBytes, fmtInt, mean } from '../core/format.js';
import { S } from '../core/state.js';

export function renderSummary() {
  const st = S.status; const rows = S.rows;
  const caja = $('#summary');
  const terminada = st && (st.fase === 'listo' || st.fase === 'detenido');
  caja.hidden = !(terminada && rows.length);
  if (caja.hidden) return;

  const as = st.meta && st.meta.attack_start_elapsed != null ? st.meta.attack_start_elapsed : null;
  const cols = as != null
    ? [['Antes del ataque', rows.filter((r) => r.t < as)], ['Durante el ataque', rows.filter((r) => r.t >= as)]]
    : [['Toda la simulación', rows]];
  const prom = (rs, k) => { const v = mean(rs.map((r) => r[k]).filter((x) => x != null)); return v == null ? '—' : fmtInt(v); };
  const ok = (rs) => (rs.length ? Math.round((rs.filter((r) => r.code === '200').length / rs.length) * 100) + ' %' : '—');
  const filas = [
    ['Paquetes por segundo (media)', (rs) => prom(rs, 'pps')],
    ['Latencia de la sonda (media, ms)', (rs) => prom(rs, 'lat')],
    ['Conexiones abiertas (media)', (rs) => prom(rs, 'conns')],
    ['Respuestas correctas', ok],
    ['Muestras', (rs) => String(rs.length)],
  ];
  $('#sum-table').replaceChildren(
    h('thead', null, h('tr', null, h('th', { scope: 'col' }, ''), cols.map(([t]) => h('th', { scope: 'col' }, t)))),
    h('tbody', null, filas.map(([etq, fn]) => h('tr', null, h('td', null, etq), cols.map(([, rs]) => h('td', null, fn(rs)))))));

  const archivos = st.archivos || [];
  $('#files-block').hidden = !archivos.length;
  $('#file-list').replaceChildren(...archivos.map((f) => h('li', null, ico('file'),
    h('span', { class: 'fn' }, f.nombre), h('span', { class: 'fd' }, f.carpeta + '/'), h('span', { class: 'fs' }, fmtBytes(f.bytes)))));
}

export function renderLogs() {
  const st = S.status; if (!st) return;
  const pre = $('#logs');
  const lineas = st.logs || [];
  if (pre.closest('details').open) {
    const alFondo = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 24;
    pre.textContent = lineas.join('\n');
    if (alFondo) pre.scrollTop = pre.scrollHeight;
  }
  $('#log-last').textContent = lineas.length
    ? lineas[lineas.length - 1].replace(/^\d{4}-\d\d-\d\dT[\d:]+Z\|\d+\|/, '') : '';
}

export function initResumen() {
  $('#logs').closest('details').addEventListener('toggle', renderLogs);
}
