/* Resumen antes/durante el ataque, archivos generados y registro del contenedor. */
import { $, h, ico } from '../core/dom.js';
import { fmtBytes, fmtInt, mean } from '../core/format.js';
import { post } from '../core/api.js';
import { emit } from '../core/bus.js';
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
  // Rendimiento: lo que costo simular (docker stats), antes y durante el ataque.
  const rec = S.recursos || [];
  if (rec.length) {
    const tramo = (i) => (as == null ? rec : (i === 0 ? rec.filter((r) => r.t < as) : rec.filter((r) => r.t >= as)));
    const col = (k, f) => cols.map((_c, i) => { const rs = tramo(i); return rs.length ? f(rs.map((r) => r[k])) : '—'; });
    const media = (v) => fmtInt(v.reduce((a, b) => a + b, 0) / v.length);
    const pico = (v) => fmtInt(Math.max(...v));
    filas.push(['CPU del contenedor (media, %)', (_rs, i) => col('cpu', media)[i]],
      ['CPU del contenedor (pico, %)', (_rs, i) => col('cpu', pico)[i]],
      ['Memoria del contenedor (media, MiB)', (_rs, i) => col('mem', media)[i]],
      ['Memoria del contenedor (pico, MiB)', (_rs, i) => col('mem', pico)[i]]);
  }
  $('#sum-table').replaceChildren(
    h('thead', null, h('tr', null, h('th', { scope: 'col' }, ''), cols.map(([t]) => h('th', { scope: 'col' }, t)))),
    h('tbody', null, filas.map(([etq, fn]) => h('tr', null, h('td', null, etq), cols.map(([, rs], i) => h('td', null, fn(rs, i)))))));

  const archivos = st.archivos || [];
  $('#files-block').hidden = !archivos.length;
  $('#file-list').replaceChildren(...archivos.map((f) => h('li', null, ico('file'),
    h('span', { class: 'fn' }, f.nombre), h('span', { class: 'fd' }, f.carpeta + '/'), h('span', { class: 'fs' }, fmtBytes(f.bytes)))));
  renderDatasets();
}

/* ----------------------- dataset de entrenamiento ----------------------- */

function tarjeta(titulo, desc, datos, ruta) {
  const cuerpo = [h('b', null, datos ? fmtInt(datos.total) : '—'), h('span', { class: 'muted' }, titulo + ' · ' + desc)];
  if (datos) {
    cuerpo.push(h('ul', { class: 'chips' }, Object.entries(datos.por_clase).map(([clase, n]) => h('li', null, h('b', null, clase), ' ' + fmtInt(n)))));
    cuerpo.push(h('code', null, ruta));
  } else cuerpo.push(h('span', { class: 'muted' }, 'No se generó.'));
  return h('div', { class: 'ds-card' }, cuerpo);
}

function renderDatasets() {
  const st = S.status; const d = st && st.datasets;
  if (!d) return;
  const run = st.run_name;
  const tienePcap = (st.archivos || []).some((f) => f.nombre.endsWith('.pcap'));
  const convirtiendo = d.activo;
  const btn = $('#btn-convert');
  btn.disabled = convirtiendo || st.activo || !tienePcap;
  $('#btn-convert').lastChild.textContent = d.resultado && !convirtiendo ? 'Volver a convertir' : 'Convertir a CSV';
  $('#ds-note').textContent = !tienePcap ? 'Esta simulación no dejó captura (.pcap): no se puede convertir.'
    : (st.activo ? 'Espera a que termine la simulación.' : (convirtiendo ? '' : 'Tarda unos 30 s a 1 min por corrida.'));

  const pasos = $('#ds-pasos');
  pasos.hidden = !convirtiendo;
  if (convirtiendo) {
    const fase = d.fase;
    const fila = (txt, estado) => h('li', { class: estado }, ico(estado === 'ok' ? 'check' : (estado === 'run' ? 'refresh' : 'info'), 'st'), h('div', { class: 'chk-t' }, h('b', null, txt)));
    pasos.replaceChildren(
      fila('Dataset por flujo: CICFlowMeter y agrupador ICMP, dentro de Docker', fase === 'flujos' ? 'run' : 'ok'),
      fila('Dataset por ventana: métricas por segundo y telemetría SDN', fase === 'ventanas' ? 'run' : 'unk'));
  }
  const err = $('#ds-error');
  err.hidden = d.fase !== 'error' || d.run_name !== run;
  err.textContent = d.error || '';

  const res = d.resultado && d.resultado.run_name === run ? d.resultado : null;
  const caja = $('#ds-result');
  caja.hidden = !res || convirtiendo;
  if (res && !convirtiendo) {
    caja.replaceChildren(h('div', { class: 'ds-grid' },
      tarjeta('Por flujo', 'filas, una por conexión', res.flujos, 'data/processed/' + run + '.csv'),
      tarjeta('Por ventana', 'filas, una por segundo', res.ventanas, 'data/processed/ventanas/' + run + '.csv')),
      h('div', { class: 'ds-actions' },
        h('a', { class: 'btn', href: '/api/descargar/' + encodeURIComponent(run), download: run + '.zip' }, ico('file'), 'Descargar ZIP'),
        h('span', { class: 'muted' }, 'Incluye los dos CSV y el meta.json que explica el etiquetado.')));
  }
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
  $('#btn-convert').addEventListener('click', async () => {
    const st = S.status; if (!st || !st.run_name) return;
    $('#btn-convert').disabled = true;
    const res = await post('/api/convertir', { run_name: st.run_name });
    if (res && !res.ok) { const e = $('#ds-error'); e.hidden = false; e.textContent = res.error; }
    emit('pedir-estado');
  });
  $('#logs').closest('details').addEventListener('toggle', renderLogs);
}
