/* Graficos de linea (SVG, sin libreria), tira de disponibilidad y tabla.
   Dos graficos separados (paquetes/s y latencia): nunca dos escalas en uno. */
import { $, h, svgEl } from '../core/dom.js';
import { fmtInt } from '../core/format.js';
import { S } from '../core/state.js';

let modoTabla = false;

function niceAxis(max) {
  if (!(max > 0)) max = 1;
  const raw = max / 4;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const f = raw / p;
  const step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
  const top = Math.ceil(max / step) * step;
  const ticks = [];
  for (let t = 0; t <= top + step / 2; t += step) ticks.push(Math.round(t * 1e6) / 1e6);
  return { ticks, top: ticks[ticks.length - 1] };
}
const fmtTick = (v) => (v >= 10000 ? (v / 1000).toLocaleString('es') + ' K' : v.toLocaleString('es'));

function lineChart(host, o) {
  if (host.dataset.hover === '1') return;      // no repintar mientras se lee un tooltip
  host.replaceChildren();
  const W = Math.max(300, Math.floor(host.clientWidth || 640)); const H = 200;
  const m = { l: 48, r: 72, t: 16, b: 28 };
  const pw = W - m.l - m.r; const ph = H - m.t - m.b;
  const svg = svgEl('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': o.aria, tabindex: '0' });
  host.appendChild(svg);

  const pts = o.pts.filter((p) => p.y != null);
  if (!pts.length) {
    svgEl('line', { class: 'ch-axis', x1: m.l, x2: m.l + pw, y1: m.t + ph, y2: m.t + ph }, svg);
    svgEl('text', { class: 'ch-empty', x: m.l + pw / 2, y: m.t + ph / 2, 'text-anchor': 'middle' }, svg).textContent = 'Esperando datos…';
    return;
  }
  const xmax = Math.max(o.xmax || 0, ...o.pts.map((p) => p.x), 2);
  const { ticks, top } = niceAxis(Math.max(...pts.map((p) => p.y)));
  const X = (x) => m.l + (x / xmax) * pw;
  const Y = (y) => m.t + ph - (y / top) * ph;

  ticks.forEach((t) => {
    svgEl('line', { class: t === 0 ? 'ch-axis' : 'ch-grid', x1: m.l, x2: m.l + pw, y1: Y(t), y2: Y(t) }, svg);
    svgEl('text', { class: 'ch-tick', x: m.l - 8, y: Y(t) + 4, 'text-anchor': 'end' }, svg).textContent = fmtTick(t);
  });
  const xs = (() => { const raw = xmax / 6; const p = Math.pow(10, Math.floor(Math.log10(raw))); const f = raw / p; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p; })();
  for (let v = 0; v <= xmax + 1e-9; v += xs) {
    svgEl('text', { class: 'ch-tick', x: X(v), y: H - 8, 'text-anchor': v === 0 ? 'start' : 'middle' }, svg).textContent = v + ' s';
  }

  const line = pts.map((p, i) => (i ? 'L' : 'M') + X(p.x).toFixed(1) + ' ' + Y(p.y).toFixed(1)).join(' ');
  svgEl('path', { class: 'ch-area ' + o.cls, d: line + ' L' + X(pts[pts.length - 1].x).toFixed(1) + ' ' + Y(0) + ' L' + X(pts[0].x).toFixed(1) + ' ' + Y(0) + ' Z' }, svg);
  svgEl('path', { class: 'ch-line ' + o.cls, d: line }, svg);

  if (o.onset != null && o.onset <= xmax) {
    const xo = X(o.onset);
    svgEl('line', { class: 'ch-onset', x1: xo, x2: xo, y1: m.t, y2: m.t + ph }, svg);
    const left = xo + 8 + 98 > W - m.r;
    svgEl('text', { class: 'ch-onset-t', x: left ? xo - 6 : xo + 6, y: m.t + 11, 'text-anchor': left ? 'end' : 'start' }, svg).textContent = 'Inicio del ataque';
  }

  const lp = pts[pts.length - 1];
  svgEl('circle', { class: 'ch-dot ' + o.cls, cx: X(lp.x), cy: Y(lp.y), r: 4.5 }, svg);
  svgEl('text', { class: 'ch-end', x: X(lp.x) + 10, y: Y(lp.y) + 4 }, svg).textContent = o.endFmt(lp.y);

  // Cruz y tooltip: sigue al puntero y tambien responde al teclado.
  const cross = svgEl('g', { style: 'display:none' }, svg);
  const cl = svgEl('line', { class: 'ch-cross', y1: m.t, y2: m.t + ph }, cross);
  const cd = svgEl('circle', { class: 'ch-dot ' + o.cls, r: 5 }, cross);
  const tt = h('div', { class: 'tt' }); tt.hidden = true; host.appendChild(tt);
  let idx = pts.length - 1;
  const show = (i) => {
    idx = Math.max(0, Math.min(pts.length - 1, i));
    const p = pts[idx]; const cx = X(p.x); const cy = Y(p.y);
    cross.style.display = '';
    cl.setAttribute('x1', cx); cl.setAttribute('x2', cx);
    cd.setAttribute('cx', cx); cd.setAttribute('cy', cy);
    tt.replaceChildren(
      h('div', { class: 'tt-h' }, 'Segundo ' + Math.round(p.x)),
      h('div', { class: 'tt-r' }, h('span', { class: 'tt-key', style: 'background:var(' + o.keyVar + ')' }),
        h('span', { class: 'tt-v' }, o.tipFmt(p.y)), h('span', { class: 'tt-n' }, o.name)));
    tt.hidden = false;
    const tw = tt.offsetWidth; const th = tt.offsetHeight;
    let left = cx + 14; if (left + tw > W) left = cx - 14 - tw;
    tt.style.left = Math.max(0, left) + 'px';
    tt.style.top = Math.max(0, cy - th - 10) + 'px';
  };
  const hide = () => { cross.style.display = 'none'; tt.hidden = true; };
  const hit = svgEl('rect', { x: m.l, y: m.t, width: pw, height: ph, fill: 'transparent' }, svg);
  hit.addEventListener('pointermove', (e) => {
    const r = svg.getBoundingClientRect();
    const dx = ((((e.clientX - r.left) / r.width) * W - m.l) / pw) * xmax;
    let best = 0; let bd = Infinity;
    pts.forEach((p, i) => { const dd = Math.abs(p.x - dx); if (dd < bd) { bd = dd; best = i; } });
    show(best);
  });
  // En el svg (se recrea en cada repintado) y no en el host: no se acumulan listeners.
  svg.addEventListener('pointerenter', () => { host.dataset.hover = '1'; });
  svg.addEventListener('pointerleave', () => { host.dataset.hover = ''; hide(); renderCharts(); });
  svg.addEventListener('focus', () => show(pts.length - 1));
  svg.addEventListener('blur', hide);
  svg.addEventListener('keydown', (e) => {
    const k = { ArrowLeft: idx - 1, ArrowRight: idx + 1, Home: 0, End: pts.length - 1 }[e.key];
    if (k == null) return;
    e.preventDefault(); show(k);
  });
}

function strip(st, rows) {
  const host = $('#ch-ok');
  if (host.dataset.hover === '1') return;
  const dur = st.duration || 0;
  const byT = new Map(rows.map((r) => [r.t, r]));
  const total = Math.max(dur - 1, rows.length, 1);
  host.replaceChildren();
  const tira = h('div', { class: 'strip', role: 'img' });
  const tt = h('div', { class: 'tt' }); tt.hidden = true;
  let okN = 0; let noN = 0;
  for (let i = 0; i < total; i++) {
    const t = i + 2; const r = byT.get(t);
    const cls = !r ? 'na' : (r.code === '200' ? 'ok' : 'no');
    if (cls === 'ok') okN++; if (cls === 'no') noN++;
    const c = h('div', { class: 'strip-c ' + cls });
    c.addEventListener('pointerenter', () => {
      host.dataset.hover = '1';
      tt.replaceChildren(h('div', { class: 'tt-h' }, 'Segundo ' + t),
        h('div', { class: 'tt-r' }, h('span', { class: 'tt-v' }, !r ? 'Sin dato todavía' : (r.code === '200' ? 'Respondió (200)' : 'No respondió (' + (r.code || 'sin código') + ')'))));
      tt.hidden = false;
      const hr = host.getBoundingClientRect(); const cr = c.getBoundingClientRect();
      const left = cr.left - hr.left + cr.width / 2 - tt.offsetWidth / 2;
      tt.style.left = Math.max(0, Math.min(host.clientWidth - tt.offsetWidth, left)) + 'px';
      tt.style.top = '-' + (tt.offsetHeight + 6) + 'px';
    });
    c.addEventListener('pointerleave', () => { host.dataset.hover = ''; tt.hidden = true; });
    tira.appendChild(c);
  }
  tira.setAttribute('aria-label', 'Respuesta del portal por segundo: ' + okN + ' correctas y ' + noN + ' con fallo.');
  host.style.position = 'relative';
  host.append(tira, tt, h('div', { class: 'strip-axis' }, h('span', null, '2 s'), h('span', null, (total + 1) + ' s')));
}

function tabla(rows) {
  const head = h('thead', null, h('tr', null,
    ['Segundo', 'Paquetes/s', 'Latencia (ms)', 'Respuesta HTTP', 'Conexiones'].map((t) => h('th', { scope: 'col' }, t))));
  const body = h('tbody', null, rows.map((r) => h('tr', null,
    h('td', null, String(r.t)),
    h('td', null, r.pps == null ? '—' : fmtInt(r.pps)),
    h('td', null, r.lat == null ? '—' : fmtInt(r.lat)),
    h('td', { class: r.code === '200' ? '' : 'bad' }, r.code || '—'),
    h('td', null, r.conns == null ? '—' : fmtInt(r.conns)))));
  $('#data-table').replaceChildren(head, body);
}

export function renderCharts() {
  const st = S.status; if (!st) return;
  const rows = S.rows;
  const m = st.meta || {};
  const as = m.attack_start_elapsed != null ? m.attack_start_elapsed : null;
  const dur = st.duration || 0;
  if (modoTabla) { tabla(rows); return; }
  const lastPps = [...rows].reverse().find((r) => r.pps != null);
  const lastLat = [...rows].reverse().find((r) => r.lat != null);
  lineChart($('#ch-pps'), {
    pts: rows.map((r) => ({ x: r.t, y: r.pps })), xmax: dur, onset: as, cls: 'ch-s1', keyVar: '--s1',
    name: 'paquetes por segundo', endFmt: (v) => fmtInt(v), tipFmt: (v) => fmtInt(v),
    aria: 'Paquetes por segundo que recibe el portal.' + (lastPps ? ' Último valor: ' + fmtInt(lastPps.pps) + '.' : ' Sin datos todavía.'),
  });
  lineChart($('#ch-lat'), {
    pts: rows.map((r) => ({ x: r.t, y: r.lat })), xmax: dur, onset: as, cls: 'ch-s2', keyVar: '--s2',
    name: 'de latencia', endFmt: (v) => fmtInt(v) + ' ms', tipFmt: (v) => fmtInt(v) + ' ms',
    aria: 'Latencia de la sonda del alumno en milisegundos.' + (lastLat ? ' Último valor: ' + fmtInt(lastLat.lat) + ' milisegundos.' : ' Sin datos todavía.'),
  });
  const rec = S.recursos || [];
  const ultCpu = rec[rec.length - 1];
  lineChart($('#ch-cpu'), {
    pts: rec.map((r) => ({ x: r.t, y: r.cpu })), xmax: dur, onset: as, cls: 'ch-s3', keyVar: '--s3',
    name: 'de CPU', endFmt: (v) => fmtInt(v) + ' %', tipFmt: (v) => fmtInt(v) + ' %',
    aria: 'CPU del contenedor en porcentaje de un núcleo.' + (ultCpu ? ' Último valor: ' + fmtInt(ultCpu.cpu) + ' por ciento.' : ' Sin datos todavía.'),
  });
  lineChart($('#ch-mem'), {
    pts: rec.map((r) => ({ x: r.t, y: r.mem })), xmax: dur, onset: as, cls: 'ch-s4', keyVar: '--s4',
    name: 'de memoria', endFmt: (v) => fmtInt(v) + ' MiB', tipFmt: (v) => fmtInt(v) + ' MiB',
    aria: 'Memoria del contenedor en MiB.' + (ultCpu ? ' Último valor: ' + fmtInt(ultCpu.mem) + ' MiB.' : ' Sin datos todavía.'),
  });
  strip(st, rows);
}

export function initCharts() {
  const poner = (tabla_) => {
    modoTabla = tabla_;
    $('#charts-view').hidden = tabla_; $('#table-view').hidden = !tabla_;
    $('#seg-chart').classList.toggle('on', !tabla_); $('#seg-table').classList.toggle('on', tabla_);
    $('#seg-chart').setAttribute('aria-pressed', String(!tabla_));
    $('#seg-table').setAttribute('aria-pressed', String(tabla_));
    renderCharts();
  };
  $('#seg-chart').addEventListener('click', () => poner(false));
  $('#seg-table').addEventListener('click', () => poner(true));
}
