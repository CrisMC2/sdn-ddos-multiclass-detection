'use strict';

/* Campus-DDoS-SDN: interfaz del banco de pruebas.
   Todo lo que viene del backend o de los logs entra al DOM con textContent,
   nunca con innerHTML: los logs del contenedor no son confiables. */

const NS = 'http://www.w3.org/2000/svg';
const $ = (sel, el = document) => el.querySelector(sel);

// Cupo de conexiones del portal (MAX_CONNECTIONS en scripts/mininet/roles.py).
const PORTAL_CUPO = 30;

const AREAS = [
  { key: 'salud', titulo: 'Salud', sw: 's3' },
  { key: 'ing', titulo: 'Ingenierías', sw: 's4' },
  { key: 'emp', titulo: 'Admin.', sw: 's5' },
  { key: 'soc', titulo: 'Sociales', sw: 's6' },
  { key: 'agr', titulo: 'Agrarias', sw: 's7' },
];

const FASES = {
  inactivo:    { txt: 'Sin corrida',          tone: '',     icon: 'info' },
  arrancando:  { txt: 'Arrancando la red',    tone: 'warn', icon: 'clock' },
  navegando:   { txt: 'Tráfico normal',       tone: 'good', icon: 'check' },
  atacando:    { txt: 'Atacando',             tone: 'crit', icon: 'alert' },
  verificando: { txt: 'Verificando',          tone: 'warn', icon: 'clock' },
  cerrando:    { txt: 'Cerrando',             tone: '',     icon: 'clock' },
  listo:       { txt: 'Terminó bien',         tone: 'good', icon: 'check' },
  error:       { txt: 'Terminó con error',    tone: 'crit', icon: 'x' },
  detenido:    { txt: 'Detenida',             tone: '',     icon: 'stop' },
};

const VERIFY_STEPS = [
  ['alumno -> portal', 'Un alumno alcanza el portal'],
  ['infectado -> portal', 'Una PC infectada alcanza el portal'],
  ['C2 -> infectado', 'El C2 alcanza una PC infectada'],
  ['alumno abre el portal', 'Un alumno abre el portal por HTTP'],
  ['navegador externo abre el portal', 'Tu navegador abre el portal por el puerto 8080'],
];

const S = {
  view: 'entorno',
  env: null,
  envAt: 0,
  scenarios: [],
  sel: null,
  status: null,
  rows: [],
  counts: { s: 4, b: 2 },
  peak: -1,
  runSeen: null,
  verifyAsked: false,
  table: false,
  timer: null,
  lost: false,
};

/* ----------------------------- utilidades ----------------------------- */

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k === 'class') el.className = v; else el.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) {
    if (k == null || k === false) continue;
    el.appendChild(typeof k === 'string' ? document.createTextNode(k) : k);
  }
  return el;
}

function svgEl(tag, attrs, parent) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  if (parent) parent.appendChild(el);
  return el;
}

function ico(name, cls) {
  const s = svgEl('svg', { class: 'ic' + (cls ? ' ' + cls : ''), 'aria-hidden': 'true' });
  svgEl('use', { href: '#i-' + name }, s);
  return s;
}

const num = (v) => { const n = parseFloat(v); return Number.isFinite(n) ? n : null; };
const fmtInt = (v) => Math.round(v).toLocaleString('es');
const mean = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : null);
function fmtBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1024 * 1024) return (b / 1024).toFixed(0) + ' KB';
  return (b / (1024 * 1024)).toFixed(1) + ' MB';
}

async function api(path, opts) {
  try {
    const r = await fetch(path, opts);
    setLost(false);
    return await r.json();
  } catch (e) {
    setLost(true);
    return null;
  }
}

function setLost(v) {
  if (S.lost === v) return;
  S.lost = v;
  $('#conn-lost').hidden = !v;
}

/* ------------------------------- tema -------------------------------- */

function effectiveTheme() {
  return document.documentElement.dataset.theme
    || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
}
function paintThemeBtn() {
  const dark = effectiveTheme() === 'dark';
  $('#theme-ic').setAttribute('href', dark ? '#i-sun' : '#i-moon');
  $('#theme-txt').textContent = dark ? 'Tema claro' : 'Tema oscuro';
}
function initTheme() {
  try {
    const saved = localStorage.getItem('ddos-theme');
    if (saved === 'light' || saved === 'dark') document.documentElement.dataset.theme = saved;
  } catch (e) { /* sin almacenamiento: se sigue el del sistema */ }
  paintThemeBtn();
  $('#theme-btn').addEventListener('click', () => {
    const next = effectiveTheme() === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('ddos-theme', next); } catch (e) { /* idem */ }
    paintThemeBtn();
  });
}

/* ------------------------------ navegacion ----------------------------- */

function go(view) {
  S.view = view;
  for (const v of ['entorno', 'lanzar', 'vivo']) $('#view-' + v).hidden = v !== view;
  document.querySelectorAll('.nav-item[data-view]').forEach((b) => {
    if (b.dataset.view === view) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  if (location.hash !== '#' + view) history.replaceState(null, '', '#' + view);
  if (view === 'entorno') loadEnv();
  if (view === 'vivo') renderLive();
  window.scrollTo(0, 0);
}

/* ------------------------------- entorno ------------------------------- */

async function loadEnv() {
  const env = await api('/api/env');
  if (!env) return;
  S.env = env;
  S.envAt = Date.now();
  S.scenarios = env.scenarios || [];
  renderEnv();
  renderRailHealth();
  renderScenarioList();
  updateLaunchState();
}

function envItems() {
  const e = S.env;
  const busy = S.status && S.status.activo;
  const items = [];
  items.push({
    icon: 'server', titulo: 'Docker',
    ok: e.docker, detalle: e.docker ? 'En ejecución' : 'No responde',
    fix: e.docker ? '' : 'Abre Docker Desktop y espera a que diga «Engine running».',
  });
  items.push({
    icon: 'box', titulo: 'Imagen ' + e.imagen_nombre,
    ok: e.imagen, detalle: e.imagen === null ? 'Se revisa cuando Docker responda' : (e.imagen ? 'Disponible' : 'No existe'),
    fix: e.imagen === false ? 'Constrúyela una vez: docker build -t ' + e.imagen_nombre + ' -f scripts/docker/Dockerfile .' : '',
  });
  let puertoOk = e.puerto_libre; let puertoDet = puertoOk ? 'Libre' : 'Ocupado'; let puertoFix = '';
  if (!puertoOk && busy) { puertoOk = true; puertoDet = 'En uso por la corrida activa'; }
  else if (!puertoOk) puertoFix = e.contenedor_activo
    ? 'Lo ocupa un contenedor de otra corrida que sigue en marcha: puede ser una anterior sin limpiar o la de otra copia de esta interfaz abierta en otra terminal.'
    : 'Otro programa usa este puerto. Ciérralo para que tu navegador pueda entrar al portal durante la corrida.';
  items.push({ icon: 'plug', titulo: 'Puerto ' + e.puerto, ok: puertoOk, detalle: puertoDet, fix: puertoFix });
  const gb = e.disco_libre_gb;
  items.push({
    icon: 'disk', titulo: 'Espacio en disco',
    ok: gb == null ? null : gb > 2, detalle: gb == null ? 'No se pudo medir' : gb.toLocaleString('es') + ' GB libres',
    fix: gb != null && gb <= 2 ? 'Libera espacio: una corrida de 120 s ocupa del orden de 10 MB entre captura y métricas.' : '',
  });
  return items;
}

function renderEnv() {
  if (!S.env) return;
  const items = envItems();
  const bad = items.filter((i) => i.ok === false).length;
  const ban = $('#env-banner');
  ban.className = 'banner ' + (bad ? 'bad' : 'good');
  ban.replaceChildren(
    ico(bad ? 'alert' : 'check'),
    h('div', null,
      h('b', null, bad ? (bad === 1 ? 'Falta resolver 1 cosa' : 'Faltan resolver ' + bad + ' cosas') : 'Listo para lanzar'),
      h('span', null, bad ? 'Revisa lo marcado abajo antes de lanzar una corrida.' : 'Docker, la imagen y el puerto están en orden.'),
    ),
  );
  const ul = $('#env-checks');
  ul.replaceChildren(...items.map((i) => {
    const cls = i.ok === true ? 'ok' : (i.ok === false ? 'bad' : 'unk');
    return h('li', { class: cls },
      ico(i.ok === true ? 'check' : (i.ok === false ? 'x' : 'info'), 'st'),
      h('div', { class: 'chk-t' }, h('b', null, i.titulo), h('span', { class: 'chk-d' }, i.detalle)),
      i.fix ? h('div', { class: 'chk-fix' }, i.fix) : null,
    );
  }));
  $('#btn-clean').hidden = !(S.env.contenedor_activo && !(S.status && S.status.activo));
  renderVerify();
}

function renderRailHealth() {
  if (!S.env) return;
  const e = S.env;
  const row = (ok, txt) => h('li', { class: ok === true ? 'ok' : (ok === false ? 'bad' : 'unk') },
    ico(ok === true ? 'check' : (ok === false ? 'x' : 'info')), txt);
  $('#rail-health').replaceChildren(
    row(e.docker, 'Docker'),
    row(e.imagen, 'Imagen'),
    row(e.puerto_libre || (S.status && S.status.activo), 'Puerto ' + e.puerto),
  );
}

function renderVerify() {
  const st = S.status;
  const isVerify = st && st.scenario === 'verify';
  const list = $('#verify-list'); const note = $('#verify-note');
  const btn = $('#btn-verify');
  const busy = st && st.activo;
  btn.disabled = !!busy || !S.env || !S.env.docker || !S.env.imagen;
  if (!isVerify) { list.hidden = true; note.hidden = true; return; }

  const lines = st.logs || [];
  const running = !!st.activo;
  const results = VERIFY_STEPS.map(([key, label]) => {
    const hit = lines.find((l) => l.startsWith('OK ' + key) || l.startsWith('FALLO ' + key));
    let estado = running ? 'run' : 'unk';
    if (hit) estado = hit.startsWith('OK ') ? 'ok' : 'bad';
    return { label, estado };
  });
  list.hidden = false;
  list.replaceChildren(...results.map((r) => h('li', { class: r.estado },
    ico(r.estado === 'ok' ? 'check' : (r.estado === 'bad' ? 'x' : (r.estado === 'run' ? 'refresh' : 'info')), 'st'),
    h('div', { class: 'chk-t' }, h('b', null, r.label)),
  )));
  note.hidden = false;
  const okAll = results.every((r) => r.estado === 'ok');
  const anyBad = results.some((r) => r.estado === 'bad');
  if (running) note.textContent = 'Levantando la red de prueba. Los resultados aparecen a medida que llegan.';
  else if (okAll) note.textContent = 'Los cinco caminos responden. La red está lista para una corrida.';
  else if (anyBad) note.textContent = 'Algún camino falló. Abre el registro de la última corrida en la vista En vivo o vuelve a verificar.';
  else note.textContent = st.error || 'La verificación terminó sin resultados. Vuelve a intentarlo.';
}

$('#btn-env-refresh').addEventListener('click', loadEnv);
$('#btn-clean').addEventListener('click', async () => {
  // Matar el contenedor interrumpe cualquier corrida que lo este usando,
  // incluida la de otra copia de la interfaz: se pide confirmacion.
  const aviso = 'Esto elimina el contenedor ataque-sdn-run. Si hay una corrida usándolo, se interrumpe y sus datos quedan incompletos.';
  if (!confirm(aviso + '\n\n¿Continuar?')) return;
  await api('/api/limpiar_contenedor', { method: 'POST' });
  loadEnv();
});
$('#btn-verify').addEventListener('click', async () => {
  S.verifyAsked = true;
  const res = await api('/api/lanzar', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario: 'verify', duration: 30 }),
  });
  if (res && !res.ok) {
    const note = $('#verify-note'); note.hidden = false; note.textContent = res.error;
  }
  tick(true);
});

/* ------------------------------- lanzar -------------------------------- */

function renderScenarioList() {
  const host = $('#sc-list');
  if (host.dataset.built === (S.scenarios.map((s) => s.id).join(','))) return;
  const keep = S.sel ? S.sel.id : null;
  host.replaceChildren(h('legend', { class: 'sr-only' }, 'Escenario'));
  const grupos = (S.env && S.env.grupos) || [];
  const orden = [...grupos, ...new Set(S.scenarios.map((s) => s.grupo).filter((g) => !grupos.includes(g)))];
  for (const g of orden) {
    const items = S.scenarios.filter((s) => s.grupo === g);
    if (!items.length) continue;
    const box = h('div', { class: 'sc-group' }, h('h3', null, g));
    for (const s of items) {
      const input = h('input', { type: 'radio', name: 'scenario', value: s.id });
      if (s.id === keep) input.checked = true;
      input.addEventListener('change', () => selectScenario(s));
      box.appendChild(h('label', { class: 'sc-item' }, input, ico(s.icono),
        h('span', null, h('span', { class: 'sc-name' }, s.nombre), h('span', { class: 'sc-tool' }, s.herramienta))));
    }
    host.appendChild(box);
  }
  host.dataset.built = S.scenarios.map((s) => s.id).join(',');
}

function selectScenario(s) {
  S.sel = s;
  $('#sc-empty').hidden = true;
  $('#sc-panel').hidden = false;
  $('#sd-icon').setAttribute('href', '#i-' + s.icono);
  $('#sd-name').textContent = s.nombre;
  $('#sd-group').textContent = s.grupo;
  $('#sd-desc').textContent = s.descripcion;
  $('#sd-agota').textContent = s.agota;
  $('#sd-firma').textContent = s.firma;
  $('#sd-tool').textContent = s.herramienta;

  const attack = s.id !== 'baseline';
  $('#fld-onset').hidden = !attack;
  const inten = s.intensidad;
  $('#fld-intensity').hidden = !inten;
  if (inten) {
    $('#int-label').textContent = inten.etiqueta;
    const inp = $('#f-intensity');
    inp.min = inten.min; inp.max = inten.max; inp.placeholder = String(inten.defecto); inp.value = '';
    $('#int-range').textContent = 'de ' + inten.min + ' a ' + inten.max;
  }
  refreshForm();
}

function formState() {
  const s = S.sel;
  const attack = s && s.id !== 'baseline';
  const duration = parseInt($('#f-duration').value, 10);
  const onsetRaw = $('#f-onset').value;
  const onset = onsetRaw === '' ? null : parseInt(onsetRaw, 10);
  let err = '';
  if (!Number.isFinite(duration) || duration < 5 || duration > 1800) err = 'La duración va de 5 a 1800 segundos.';
  else if (attack && onset == null) err = 'Indica en qué segundo arranca el ataque (0 para que arranque de inmediato).';
  else if (attack && (onset < 0 || !Number.isFinite(onset))) err = 'El inicio del ataque no puede ser negativo.';
  else if (attack && onset > 0 && duration < onset + 10) err = 'Tienen que quedar al menos 10 s de ataque: sube la duración o adelanta el inicio.';
  let intensidad = null;
  if (!err && s && s.intensidad && $('#f-intensity').value !== '') {
    intensidad = parseInt($('#f-intensity').value, 10);
    if (!Number.isFinite(intensidad) || intensidad < s.intensidad.min || intensidad > s.intensidad.max) {
      err = s.intensidad.etiqueta + ': el valor va de ' + s.intensidad.min + ' a ' + s.intensidad.max + '.';
    }
  }
  return { attack, duration, onset, err, intensidad };
}

function refreshForm() {
  const f = formState();
  const errEl = $('#err-onset');
  const onsetErr = f.err && f.err.startsWith('Tienen') || (f.err && f.err.startsWith('Indica')) || (f.err && f.err.startsWith('El inicio'));
  errEl.hidden = !onsetErr; errEl.textContent = onsetErr ? f.err : '';
  $('#f-onset').classList.toggle('invalid', !!onsetErr);
  $('#f-duration').classList.toggle('invalid', !!f.err && f.err.startsWith('La duración'));

  // Linea de tiempo prevista.
  const tl = $('#tl'); const legend = $('#tl-legend');
  tl.replaceChildren(); legend.replaceChildren();
  if (Number.isFinite(f.duration) && f.duration > 0 && !onsetErr) {
    const nav = f.attack ? Math.max(0, f.onset || 0) : f.duration;
    const atk = f.attack ? f.duration - nav : 0;
    if (nav > 0) tl.appendChild(h('i', { class: 't-nav', style: 'flex:' + nav }));
    if (atk > 0) tl.appendChild(h('i', { class: 't-atk', style: 'flex:' + atk }));
    if (nav > 0) legend.appendChild(h('li', null, h('i', { class: 't-nav' }), 'Tráfico normal: ' + nav + ' s'));
    if (atk > 0) legend.appendChild(h('li', null, h('i', { class: 't-atk' }), 'Ataque: ' + atk + ' s'));
    tl.setAttribute('aria-label', 'Línea de tiempo: ' + (nav ? nav + ' s de tráfico normal' : '') + (atk ? (nav ? ', luego ' : '') + atk + ' s de ataque' : ''));
  }
  updateLaunchState();
}

function updateLaunchState() {
  const btn = $('#btn-launch'); const note = $('#launch-note');
  if (!S.sel) return;
  const f = formState();
  const busy = S.status && S.status.activo;
  let msg = ''; let bad = false; let ok = true;
  if (busy) { ok = false; msg = 'Hay una corrida en curso. Detenla o espera a que termine.'; }
  else if (S.env && !S.env.docker) { ok = false; bad = true; msg = 'Docker no responde. Abre Docker Desktop y revisa el Entorno.'; }
  else if (S.env && S.env.imagen === false) { ok = false; bad = true; msg = 'Falta la imagen de Docker. Revisa el Entorno.'; }
  else if (f.err) { ok = false; bad = true; msg = f.err; }
  else msg = 'Dura unos ' + (f.duration + 20) + ' a ' + (f.duration + 40) + ' s en total, contando el arranque de la red.';
  btn.disabled = !ok;
  note.textContent = msg; note.classList.toggle('bad', bad);
  $('#btn-launch-txt').textContent = 'Lanzar ' + S.sel.nombre;
}

['f-duration', 'f-onset', 'f-intensity'].forEach((id) => $('#' + id).addEventListener('input', refreshForm));

$('#btn-launch').addEventListener('click', async () => {
  const f = formState();
  if (!S.sel || f.err) return;
  const body = { scenario: S.sel.id, duration: f.duration };
  if (f.attack) body.onset_s = f.onset;
  const tag = $('#f-tag').value.trim(); if (tag) body.run_tag = tag;
  const st = $('#f-students').value; if (st) body.students_per_area = st;
  const bo = $('#f-bots').value; if (bo) body.bots_per_area = bo;
  const sd = $('#f-seed').value; if (sd) body.seed = sd;
  if (S.sel.intensidad && f.intensidad != null) body[S.sel.intensidad.env] = f.intensidad;

  $('#btn-launch').disabled = true;
  const res = await api('/api/lanzar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!res || !res.ok) {
    const note = $('#launch-note'); note.textContent = (res && res.error) || 'No se pudo lanzar la corrida.'; note.classList.add('bad');
    updateLaunchState();
    return;
  }
  S.counts = { s: parseInt(st, 10) || 4, b: parseInt(bo, 10) || 2 };
  S.rows = []; S.peak = -1; S.runSeen = res.run_name;
  $('#topo').dataset.key = '';
  await tick(true);
  go('vivo');
});

/* ------------------------------- en vivo ------------------------------- */

async function tick(force) {
  const st = await api('/api/status');
  if (!st) return;
  const wasActive = S.status && S.status.activo;
  S.status = st;
  // Al terminar una corrida el puerto y el contenedor cambian de estado:
  // se vuelve a medir el entorno para que el panel lateral no mienta.
  if ((wasActive && !st.activo) || Date.now() - S.envAt > 10000) loadEnv();
  const hasRun = st.run_name && st.scenario !== 'verify';
  if (hasRun) {
    const m = await api('/api/metrics?n=600');
    if (m) S.rows = cleanRows(m.rows || []);
  } else S.rows = [];
  renderChrome();
  if (S.view === 'vivo') renderLive();
  if (S.view === 'entorno') { renderVerify(); renderEnv(); }
  updateLaunchState();
  schedule();
}

function schedule() {
  clearTimeout(S.timer);
  const active = S.status && S.status.activo;
  S.timer = setTimeout(tick, active ? 1000 : 4000);
}

function cleanRows(raw) {
  return raw.map((r) => ({
    t: num(r.elapsed_s), pps: num(r.server_rx_pps), lat: num(r.probe_latency_ms),
    code: (r.probe_http_code || '').trim(), conns: num(r.server_conns),
  })).filter((r) => r.t != null && r.t > 1);   // el segundo 1 sale vacio: se omite como en build_windows.py
}

function pillInto(el, fase, label) {
  const f = FASES[fase] || FASES.inactivo;
  el.className = 'pill ' + f.tone;
  el.replaceChildren(ico(f.icon), label || f.txt);
}

function renderChrome() {
  const st = S.status; if (!st) return;
  const active = st.activo;
  $('#nav-live').hidden = !active;
  const strip = $('#runstrip');
  strip.hidden = !active;
  if (active) {
    pillInto($('#rs-pill'), st.fase);
    $('#rs-name').textContent = st.scenario === 'verify' ? 'Verificación de la red' : st.run_name;
    $('#rs-time').textContent = st.elapsed != null ? 't+' + Math.round(st.elapsed) + ' s' : '';
    strip.dataset.go = st.scenario === 'verify' ? 'entorno' : 'vivo';
  }
  renderRailHealth();
}

$('#runstrip').addEventListener('click', (e) => go(e.currentTarget.dataset.go || 'vivo'));
$('#btn-go-launch').addEventListener('click', () => go('lanzar'));
$('#btn-stop').addEventListener('click', async () => {
  $('#btn-stop').disabled = true;
  await api('/api/parar', { method: 'POST' });
  tick(true);
});

function attackStart() {
  const m = S.status && S.status.meta;
  return m && m.attack_start_elapsed != null ? m.attack_start_elapsed : null;
}

function renderLive() {
  const st = S.status;
  const has = st && st.run_name && st.scenario !== 'verify';
  $('#live-empty').hidden = !!has;
  $('#live').hidden = !has;
  if (!has) return;

  const info = st.scenario_info || { nombre: st.scenario };
  $('#h-vivo').textContent = info.nombre;
  pillInto($('#lh-pill'), st.fase);
  const wall = st.elapsed != null ? ' · t+' + Math.round(st.elapsed) + ' s' : '';
  $('#lh-sub').textContent = st.run_name + wall;
  $('#btn-stop').hidden = !st.activo;
  $('#btn-stop').disabled = !st.activo;
  const err = $('#live-error');
  err.hidden = st.fase !== 'error';
  err.textContent = st.fase === 'error' ? (st.error || 'La corrida terminó con error (código ' + (st.exit_code || '?') + '). Abre el registro del contenedor para ver por qué.') : '';

  renderStepper(st);
  renderTopo(st);
  renderTiles(st);
  renderCharts(st);
  renderSummary(st);
  renderLogs(st);
}

function renderStepper(st) {
  const attack = st.scenario !== 'baseline';
  const steps = [['arrancando', 'Arranque de red'], ['navegando', 'Tráfico normal']];
  if (attack) steps.push(['atacando', 'Ataque']);
  steps.push(['cerrando', 'Cierre'], ['listo', 'Terminó']);
  const idxOf = (f) => steps.findIndex((s) => s[0] === f);
  let cur = idxOf(st.fase);
  if (cur >= 0) S.peak = Math.max(S.peak, cur);
  const stopped = st.fase === 'error' || st.fase === 'detenido';
  if (cur < 0) cur = S.peak;
  const finished = st.fase === 'listo';
  $('#stepper').replaceChildren(...steps.map(([f, label], i) => {
    let cls = ''; let icon = 'baseline';
    if (finished || i < cur) { cls = 'done'; icon = 'check'; }
    else if (i === cur) {
      cls = stopped ? 'stop' : 'now' + (f === 'atacando' ? ' atk' : '');
      icon = stopped ? 'x' : (f === 'atacando' ? 'alert' : 'clock');
    }
    const li = h('li', { class: cls }, ico(icon), label);
    if (cls.startsWith('now')) li.setAttribute('aria-current', 'step');
    return li;
  }));
}

/* ---- campus ---- */

function renderTopo(st) {
  const m = st.meta || {};
  let ns = S.counts.s; let nb = S.counts.b;
  if (m.students && m.students.length) ns = Math.round(m.students.length / AREAS.length);
  if (m.bots && m.bots.length) nb = Math.round(m.bots.length / AREAS.length);
  const svg = $('#topo');
  const key = ns + 'x' + nb;
  if (svg.dataset.key !== key) { buildTopo(svg, ns, nb); svg.dataset.key = key; }
  svg.classList.toggle('is-attack', st.fase === 'atacando');

  const last = S.rows[S.rows.length - 1];
  const portal = $('#topo .portal');
  if (portal) {
    const sub = $('.sub', portal); const stI = $('.st use', portal);
    portal.classList.remove('ok', 'fail');
    if (last && last.code) {
      const ok = last.code === '200';
      portal.classList.add(ok ? 'ok' : 'fail');
      sub.textContent = ok ? 'Responde' : 'Error ' + last.code;
      stI.setAttribute('href', ok ? '#i-check' : '#i-alert');
      stI.parentNode.style.display = '';
    } else { sub.textContent = '10.0.0.10'; stI.parentNode.style.display = 'none'; }
  }
}

function buildTopo(svg, ns, nb) {
  svg.replaceChildren();
  // Los textos van grandes en unidades del viewBox: asi siguen legibles cuando
  // el panel se achica en pantallas angostas.
  svg.setAttribute('viewBox', '0 0 1000 382');
  const NW = 148; const NH = 56;

  const node = (cx, cy, icon, title, sub, cls) => {
    const g = svgEl('g', { class: 'node ' + (cls || '') }, svg);
    svgEl('rect', { x: cx - NW / 2, y: cy - NH / 2, width: NW, height: NH, rx: 8 }, g);
    const i = svgEl('svg', { class: 'ic', x: cx - NW / 2 + 12, y: cy - 10, width: 20, height: 20, 'aria-hidden': 'true' }, g);
    svgEl('use', { href: '#i-' + icon }, i);
    svgEl('text', { x: cx - NW / 2 + 42, y: cy - 3 }, g).textContent = title;
    svgEl('text', { class: 'sub', x: cx - NW / 2 + 42, y: cy + 15 }, g).textContent = sub;
    return g;
  };
  const link = (d, carries, soft) => svgEl('path', { d, class: 'lk' + (carries ? ' carries' : '') + (soft ? ' soft' : '') }, svg);

  // Los enlaces van primero para que los nodos queden encima.
  const TOP = 64;
  link('M154 ' + TOP + 'H216');
  link('M364 ' + TOP + 'H426');
  link('M574 ' + TOP + 'H636', true);
  link('M784 ' + TOP + 'H846', true);
  const labX = [110, 305, 500, 695, 890];
  const LAB = 214;
  AREAS.forEach((a, i) => {
    const x = labX[i];
    link('M500 ' + (TOP + NH / 2) + 'V140H' + x + 'V' + (LAB - NH / 2), true);
    link('M' + x + ' ' + (LAB + NH / 2) + 'V284', true, true);
  });

  svgEl('text', { class: 'zone', x: 185, y: 48, 'text-anchor': 'middle' }, svg).textContent = 'Internet';

  node(80, TOP, 'terminal', 'C2', 'fuera del campus', 'c2');
  node(290, TOP, 'globe', 'Módem', '10.0.0.1');
  node(500, TOP, 'switch', 'Switch core', 's1');
  node(710, TOP, 'switch', 'DMZ', 's2');
  const portal = node(920, TOP, 'server', 'Portal', '10.0.0.10', 'portal');
  const stIcon = svgEl('svg', { class: 'ic st', x: 920 + NW / 2 - 24, y: TOP - NH / 2 + 6, width: 16, height: 16, style: 'display:none', 'aria-hidden': 'true' }, portal);
  svgEl('use', { href: '#i-check' }, stIcon);

  AREAS.forEach((a, i) => {
    const x = labX[i];
    node(x, LAB, 'switch', a.titulo, a.sw, 'lab');
    const gap = Math.min(22, 150 / Math.max(ns, 1));
    const x0 = x - (gap * (ns - 1)) / 2;
    for (let k = 0; k < ns; k++) svgEl('circle', { class: 'host', cx: x0 + k * gap, cy: 300, r: 7 }, svg);
    const gb = Math.min(26, 150 / Math.max(nb, 1));
    const xb = x - (gb * (nb - 1)) / 2;
    for (let k = 0; k < nb; k++) svgEl('rect', { class: 'bot', x: xb + k * gb - 6, y: 332 - 6, width: 12, height: 12, transform: 'rotate(45 ' + (xb + k * gb) + ' 332)' }, svg);
    svgEl('text', { class: 'cnt', x: x, y: 368, 'text-anchor': 'middle' }, svg).textContent =
      ns + (ns === 1 ? ' alumno, ' : ' alumnos, ') + nb + (nb === 1 ? ' infectada' : ' infectadas');
  });
}

/* ---- tarjetas ---- */

function ensureTiles() {
  const host = $('#tiles');
  if (host.children.length) return;
  for (const id of ['pps', 'lat', 'ok', 'conns', 'time']) {
    host.appendChild(h('div', { class: 'tile', id: 't-' + id },
      h('div', { class: 'tile-l' }), h('div', { class: 'tile-v' }), h('div', { class: 'tile-d' })));
  }
}

function setTile(id, label, value, unit, delta) {
  const t = $('#t-' + id);
  $('.tile-l', t).textContent = label;
  const v = $('.tile-v', t); v.replaceChildren(value);
  if (unit) v.appendChild(h('small', null, unit));
  const d = $('.tile-d', t);
  d.className = 'tile-d' + (delta && delta.tone ? ' ' + delta.tone : '');
  d.replaceChildren();
  if (delta && delta.icon) d.appendChild(ico(delta.icon));
  d.appendChild(document.createTextNode(delta ? delta.text : ''));
}

function pctText(now, base) {
  if (now == null || base == null || base === 0) return null;
  const p = Math.round(((now - base) / base) * 100);
  return (p > 0 ? '+' : '') + p.toLocaleString('es') + ' %';
}

function renderTiles(st) {
  ensureTiles();
  const rows = S.rows; const last = rows[rows.length - 1];
  const as = attackStart();
  const before = as != null ? rows.filter((r) => r.t < as) : rows;
  const during = as != null ? rows.filter((r) => r.t >= as) : [];

  const bPps = mean(before.map((r) => r.pps).filter((x) => x != null));
  const bLat = mean(before.map((r) => r.lat).filter((x) => x != null));

  let d = { text: as != null ? '' : 'Todavía sin ataque' };
  const pp = last && as != null ? pctText(last.pps, bPps) : null;
  if (pp) d = { text: pp + ' frente a antes del ataque', icon: last.pps >= bPps ? 'up' : 'down' };
  setTile('pps', 'Paquetes por segundo', last && last.pps != null ? fmtInt(last.pps) : '—', '', d);

  d = { text: as != null ? '' : 'Todavía sin ataque' };
  const pl = last && as != null ? pctText(last.lat, bLat) : null;
  if (pl) d = { text: pl + ' frente a antes del ataque', icon: last.lat >= bLat ? 'up' : 'down', tone: last.lat > bLat * 1.25 ? 'bad' : '' };
  setTile('lat', 'Latencia de la sonda', last && last.lat != null ? fmtInt(last.lat) : '—', last && last.lat != null ? 'ms' : '', d);

  const scope = as != null ? during : rows;
  const okN = scope.filter((r) => r.code === '200').length;
  const pct = scope.length ? Math.round((okN / scope.length) * 100) : null;
  setTile('ok', as != null ? 'Respuestas correctas durante el ataque' : 'Respuestas correctas',
    pct == null ? '—' : String(pct), pct == null ? '' : '%',
    { text: scope.length ? okN + ' de ' + scope.length + ' sondas' : '', tone: pct != null && pct < 90 ? 'bad' : '', icon: pct != null && pct < 90 ? 'alert' : null });

  const cn = last ? last.conns : null;
  setTile('conns', 'Conexiones abiertas en el portal', cn == null ? '—' : fmtInt(cn), '',
    cn != null && cn > PORTAL_CUPO
      ? { text: 'Por encima del cupo de ' + PORTAL_CUPO, tone: 'bad', icon: 'alert' }
      : { text: 'Cupo del portal: ' + PORTAL_CUPO });

  const dur = st.duration || 0;
  const tNow = last ? last.t : 0;
  let sub = '';
  if (st.scenario === 'baseline') sub = 'Sin ataque en esta corrida';
  else if (as != null) sub = 'Etiquetado como ataque desde el segundo ' + as;
  else sub = 'El ataque aún no empieza';
  setTile('time', 'Tiempo medido', String(Math.round(tNow)), dur ? 'de ' + dur + ' s' : 's', { text: sub });
}

/* ---- graficos ---- */

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
    svgEl('text', { class: 'ch-empty', x: m.l + pw / 2, y: m.t + ph / 2, 'text-anchor': 'middle' }, svg).textContent = o.emptyText || 'Esperando datos…';
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
      h('div', { class: 'tt-h' }, 'Segundo ' + p.x),
      h('div', { class: 'tt-r' }, h('span', { class: 'tt-key', style: 'background:var(' + o.keyVar + ')' }),
        h('span', { class: 'tt-v' }, o.tipFmt(p.y)), h('span', { class: 'tt-n' }, o.name)),
    );
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
    const px = ((e.clientX - r.left) / r.width) * W;
    const dx = ((px - m.l) / pw) * xmax;
    let best = 0; let bd = Infinity;
    pts.forEach((p, i) => { const dd = Math.abs(p.x - dx); if (dd < bd) { bd = dd; best = i; } });
    show(best);
  });
  // En el svg (se recrea en cada repintado) y no en el host, para no acumular listeners.
  svg.addEventListener('pointerenter', () => { host.dataset.hover = '1'; });
  svg.addEventListener('pointerleave', () => { host.dataset.hover = ''; hide(); renderCharts(S.status); });
  svg.addEventListener('focus', () => show(pts.length - 1));
  svg.addEventListener('blur', hide);
  svg.addEventListener('keydown', (e) => {
    const k = { ArrowLeft: idx - 1, ArrowRight: idx + 1, Home: 0, End: pts.length - 1 }[e.key];
    if (k == null) return;
    e.preventDefault(); show(k);
  });
}

function renderCharts(st) {
  if (!st) return;
  const rows = S.rows; const as = attackStart(); const dur = st.duration || 0;
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
  renderStrip(st);
  renderTable();
}

function renderStrip(st) {
  const host = $('#ch-ok');
  if (host.dataset.hover === '1') return;
  const dur = st.duration || 0;
  const byT = new Map(S.rows.map((r) => [r.t, r]));
  const total = Math.max(dur - 1, S.rows.length, 1);
  host.replaceChildren();
  const strip = h('div', { class: 'strip', role: 'img' });
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
    strip.appendChild(c);
  }
  strip.setAttribute('aria-label', 'Respuesta del portal por segundo: ' + okN + ' correctas y ' + noN + ' con fallo.');
  host.style.position = 'relative';
  host.append(strip, tt, h('div', { class: 'strip-axis' }, h('span', null, '2 s'), h('span', null, total + 1 + ' s')));
}

function renderTable() {
  const tbl = $('#data-table');
  if (!S.table) return;
  const head = h('thead', null, h('tr', null,
    ['Segundo', 'Paquetes/s', 'Latencia (ms)', 'Respuesta HTTP', 'Conexiones'].map((t) => h('th', { scope: 'col' }, t))));
  const body = h('tbody', null, S.rows.map((r) => h('tr', null,
    h('td', null, String(r.t)),
    h('td', null, r.pps == null ? '—' : fmtInt(r.pps)),
    h('td', null, r.lat == null ? '—' : fmtInt(r.lat)),
    h('td', { class: r.code === '200' ? '' : 'bad' }, r.code || '—'),
    h('td', null, r.conns == null ? '—' : fmtInt(r.conns)))));
  tbl.replaceChildren(head, body);
}

$('#seg-chart').addEventListener('click', () => setTable(false));
$('#seg-table').addEventListener('click', () => setTable(true));
function setTable(on) {
  S.table = on;
  $('#charts-view').hidden = on; $('#table-view').hidden = !on;
  $('#seg-chart').classList.toggle('on', !on); $('#seg-table').classList.toggle('on', on);
  $('#seg-chart').setAttribute('aria-pressed', String(!on)); $('#seg-table').setAttribute('aria-pressed', String(on));
  if (on) renderTable(); else renderCharts(S.status);
}

/* ---- resumen, archivos y registro ---- */

function renderSummary(st) {
  const box = $('#summary');
  const done = st.fase === 'listo' || st.fase === 'detenido';
  box.hidden = !(done && S.rows.length);
  if (box.hidden) return;
  const as = attackStart();
  const cols = as != null
    ? [['Antes del ataque', S.rows.filter((r) => r.t < as)], ['Durante el ataque', S.rows.filter((r) => r.t >= as)]]
    : [['Toda la corrida', S.rows]];
  const avg = (rs, k) => { const v = mean(rs.map((r) => r[k]).filter((x) => x != null)); return v == null ? '—' : fmtInt(v); };
  const ok = (rs) => (rs.length ? Math.round((rs.filter((r) => r.code === '200').length / rs.length) * 100) + ' %' : '—');
  const rowsDef = [
    ['Paquetes por segundo (media)', (rs) => avg(rs, 'pps')],
    ['Latencia de la sonda (media, ms)', (rs) => avg(rs, 'lat')],
    ['Conexiones abiertas (media)', (rs) => avg(rs, 'conns')],
    ['Respuestas correctas', ok],
    ['Muestras', (rs) => String(rs.length)],
  ];
  $('#sum-table').replaceChildren(
    h('thead', null, h('tr', null, h('th', { scope: 'col' }, ''), cols.map(([t]) => h('th', { scope: 'col' }, t)))),
    h('tbody', null, rowsDef.map(([label, fn]) => h('tr', null, h('td', null, label), cols.map(([, rs]) => h('td', null, fn(rs)))))),
  );
  const files = st.archivos || [];
  $('#files-block').hidden = !files.length;
  $('#file-list').replaceChildren(...files.map((f) => h('li', null, ico('file'),
    h('span', { class: 'fn' }, f.nombre), h('span', { class: 'fd' }, f.carpeta + '/'), h('span', { class: 'fs' }, fmtBytes(f.bytes)))));
}

function renderLogs(st) {
  const pre = $('#logs');
  const lines = st.logs || [];
  const open = pre.closest('details').open;
  if (open) {
    const atBottom = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 24;
    pre.textContent = lines.join('\n');
    if (atBottom) pre.scrollTop = pre.scrollHeight;
  }
  $('#log-last').textContent = lines.length ? lines[lines.length - 1].replace(/^\d{4}-\d\d-\d\dT[\d:]+Z\|\d+\|/, '') : '';
}
$('#logs').closest('details').addEventListener('toggle', () => { if (S.status) renderLogs(S.status); });

/* -------------------------------- inicio ------------------------------- */

document.querySelectorAll('.nav-item[data-view]').forEach((b) => b.addEventListener('click', () => go(b.dataset.view)));
new ResizeObserver(() => { if (S.view === 'vivo' && S.status) requestAnimationFrame(() => renderCharts(S.status)); }).observe(document.body);

(async function init() {
  initTheme();
  await Promise.all([loadEnv(), tick(true)]);
  const fromHash = location.hash.replace('#', '');
  const start = ['entorno', 'lanzar', 'vivo'].includes(fromHash) ? fromHash : (S.status && S.status.activo && S.status.scenario !== 'verify' ? 'vivo' : 'entorno');
  go(start);
})();
