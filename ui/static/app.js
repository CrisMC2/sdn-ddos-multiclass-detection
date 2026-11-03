'use strict';

// Mismas 5 areas que scripts/mininet/roles.py (AREAS). Es solo para
// dibujar: la lista real de escenarios/areas la manda el backend.
const AREAS = [
  { key: 'salud', titulo: 'Salud' },
  { key: 'ing', titulo: 'Ingenierías' },
  { key: 'emp', titulo: 'Admin.' },
  { key: 'soc', titulo: 'Sociales' },
  { key: 'agr', titulo: 'Agrarias' },
];

const FASES_ACTIVAS = ['arrancando', 'navegando', 'atacando', 'verificando', 'cerrando'];

let elegido = null;       // escenario elegido en la pestaña Lanzar
let pollStatus = null;
let pollMetrics = null;
let faseAnterior = null;

// -------------------------------------------------------------------------
// Pestañas
// -------------------------------------------------------------------------
document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => irATab(btn.dataset.tab));
});

function irATab(nombre) {
  document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('activo', b.dataset.tab === nombre));
  document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('activo', p.id === 'tab-' + nombre));
}

// -------------------------------------------------------------------------
// Tab 1: entorno
// -------------------------------------------------------------------------
async function cargarEntorno() {
  let data;
  try {
    data = await (await fetch('/api/env')).json();
  } catch (e) {
    marcarCard('card-docker', false, 'No se pudo hablar con la interfaz');
    return;
  }
  marcarCard('card-docker', data.docker, data.docker ? 'Corriendo' : 'Cerrado — abre Docker Desktop');
  marcarCard('card-imagen', data.imagen, data.imagen ? 'Lista' : (data.docker ? 'No existe (construye la imagen)' : 'No se puede revisar sin Docker'));
  marcarCard('card-puerto', data.puerto_libre, data.puerto_libre ? ('Libre (' + data.puerto + ')') : ('Ocupado (' + data.puerto + ') — cierra lo que lo use'));
  const disco = data.disco_libre_gb;
  const discoOk = disco === null || disco === undefined ? null : disco > 2;
  marcarCard('card-disco', discoOk, disco === null ? 'No se pudo medir' : (disco + ' GB libres'));

  document.getElementById('btn-limpiar').classList.toggle('oculto', !data.contenedor_activo);
  document.getElementById('btn-verify').disabled = !data.docker || !data.imagen;

  renderScenarios(data.scenarios || []);
}

function marcarCard(id, ok, texto) {
  const card = document.getElementById(id);
  card.classList.remove('ok', 'mal');
  if (ok === true) card.classList.add('ok');
  else if (ok === false) card.classList.add('mal');
  card.querySelector('.estado').textContent = texto;
}

document.getElementById('btn-refrescar-env').addEventListener('click', cargarEntorno);

document.getElementById('btn-limpiar').addEventListener('click', async () => {
  await fetch('/api/limpiar_contenedor', { method: 'POST' });
  cargarEntorno();
});

document.getElementById('btn-verify').addEventListener('click', async () => {
  const res = await lanzar('verify', 30, {});
  if (res.ok) {
    irATab('vivo');
  } else {
    document.getElementById('verify-resultado').classList.remove('oculto');
    document.getElementById('verify-resultado').textContent = 'No se pudo lanzar: ' + res.error;
  }
});

// -------------------------------------------------------------------------
// Tab 2: lanzar
// -------------------------------------------------------------------------
function renderScenarios(lista) {
  const cont = document.getElementById('scenario-grid');
  if (cont.dataset.listo === '1') return; // ya dibujado, no perder la seleccion
  cont.innerHTML = '';
  lista.forEach((s) => {
    const div = document.createElement('div');
    div.className = 'scenario-card';
    div.dataset.id = s.id;
    div.innerHTML =
      '<div class="icono">' + s.icono + '</div>' +
      '<div class="nombre">' + s.nombre + '</div>' +
      '<div class="tipo">' + s.tipo + '</div>' +
      '<div class="descripcion">' + s.descripcion + '</div>' +
      '<div class="herramienta">' + s.herramienta + '</div>';
    div.addEventListener('click', () => elegirScenario(s));
    cont.appendChild(div);
  });
  cont.dataset.listo = '1';
}

function elegirScenario(s) {
  elegido = s;
  document.querySelectorAll('.scenario-card').forEach((c) => c.classList.toggle('elegido', c.dataset.id === s.id));
  const btn = document.getElementById('btn-lanzar');
  btn.disabled = false;
  btn.textContent = '▶️ Lanzar ' + s.nombre;
}

document.getElementById('btn-lanzar').addEventListener('click', async () => {
  if (!elegido) return;
  const duracion = parseInt(document.getElementById('f-duracion').value, 10) || 20;
  const extra = {
    onset_s: valorOVacio('f-onset'),
    run_tag: document.getElementById('f-tag').value.trim(),
    students_per_area: valorOVacio('f-students'),
    bots_per_area: valorOVacio('f-bots'),
    seed: valorOVacio('f-seed'),
    SYN_PPS: valorOVacio('f-syn'),
    ICMP_PPS: valorOVacio('f-icmp'),
    UDP_PPS: valorOVacio('f-udp'),
    ACK_PPS: valorOVacio('f-ack'),
    HTTP_FLOOD_WORKERS: valorOVacio('f-httpw'),
    SLOWLORIS_CONNS: valorOVacio('f-slowloris'),
    SLOWPOST_CONNS: valorOVacio('f-slowpost'),
  };
  const res = await lanzar(elegido.id, duracion, extra);
  if (res.ok) {
    irATab('vivo');
  } else {
    alert('No se pudo lanzar: ' + res.error);
  }
});

function valorOVacio(id) {
  const v = document.getElementById(id).value;
  return v === '' ? '' : v;
}

async function lanzar(scenario, duracion, extra) {
  const body = Object.assign({ scenario: scenario, duration: duracion }, extra);
  const resp = await fetch('/api/lanzar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (data.ok) iniciarPolling();
  return data;
}

// -------------------------------------------------------------------------
// Tab 3: en vivo — campus SVG
// -------------------------------------------------------------------------
function construirCampus(nStudents, nBots) {
  const svg = document.getElementById('campus-svg');
  svg.innerHTML = '';
  const ns = 'http://www.w3.org/2000/svg';
  const add = (tag, attrs, parent) => {
    const el = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    (parent || svg).appendChild(el);
    return el;
  };

  // Modem + C2, arriba.
  add('text', { x: 20, y: 24, fill: '#93a0bd', 'font-size': 12 }, svg).textContent = '🌐 Modem';
  add('text', { x: 780, y: 24, fill: '#93a0bd', 'font-size': 12 }, svg).textContent = '📡 C2 (fuera del campus)';

  // Portal, centro-arriba.
  const portal = add('g', { class: 'portal' }, svg);
  add('rect', { x: 380, y: 40, width: 140, height: 46, rx: 8 }, portal);
  add('text', { x: 450, y: 68, 'text-anchor': 'middle' }, portal).textContent = '🖥️ Portal';

  // 5 laboratorios en fila.
  const xs = [30, 210, 390, 570, 750];
  AREAS.forEach((area, i) => {
    const x = xs[i];
    const g = add('g', { class: 'nodo-lab', 'data-area': area.key, 'data-nbots': nBots }, svg);
    add('rect', { x: x, y: 150, width: 140, height: 120, rx: 10 }, g);
    add('text', { x: x + 70, y: 172, 'text-anchor': 'middle', class: 'titulo' }, g).textContent = area.titulo;
    add('text', { x: x + 70, y: 194, 'text-anchor': 'middle' }, g).textContent =
      '🧑‍🎓'.repeat(Math.min(nStudents, 6)) + (nStudents > 6 ? ' +' + (nStudents - 6) : '');

    add('text', { x: x + 70, y: 216, 'text-anchor': 'middle', class: 'bots-fila' }, g).textContent = '🤖'.repeat(nBots);

    add('text', { x: x + 70, y: 240, 'text-anchor': 'middle', 'font-size': 10, fill: '#5b6b8f' }, g).textContent = area.key;

    // Linea punteada de ese lab hacia el portal (se activa en "atacando").
    add('line', {
      x1: x + 70, y1: 150, x2: 450, y2: 86,
      class: 'linea-ataque', 'data-area': area.key,
    }, svg);
  });
}

function actualizarCampusFase(fase) {
  const atacando = fase === 'atacando';
  document.querySelectorAll('.nodo-lab').forEach((g) => {
    g.classList.toggle('atacando', atacando);
    const nBots = parseInt(g.dataset.nbots, 10) || 0;
    g.querySelector('.bots-fila').textContent = (atacando ? '💥' : '🤖').repeat(nBots);
  });
  document.querySelectorAll('.linea-ataque').forEach((l) => l.classList.toggle('activa', atacando));
}

// -------------------------------------------------------------------------
// Chart (canvas, sin libreria)
// -------------------------------------------------------------------------
function dibujarChart(rows, onsetElapsed) {
  const canvas = document.getElementById('chart');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (!rows.length) {
    ctx.fillStyle = '#5b6b8f';
    ctx.font = '13px sans-serif';
    ctx.fillText('Esperando datos…', 14, 24);
    return;
  }
  const pad = { l: 46, r: 46, t: 14, b: 26 };
  const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;

  const xs = rows.map((r) => parseFloat(r.elapsed_s) || 0);
  const pps = rows.map((r) => parseFloat(r.server_rx_pps) || 0);
  const lat = rows.map((r) => parseFloat(r.probe_latency_ms) || 0);
  const xMax = Math.max(...xs, 1), ppsMax = Math.max(...pps, 10), latMax = Math.max(...lat, 10);

  const px = (x) => pad.l + (x / xMax) * plotW;
  const pyPps = (y) => pad.t + plotH - (y / ppsMax) * plotH;
  const pyLat = (y) => pad.t + plotH - (y / latMax) * plotH;

  // Ejes.
  ctx.strokeStyle = '#2a3650';
  ctx.beginPath();
  ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, pad.t + plotH); ctx.lineTo(pad.l + plotW, pad.t + plotH);
  ctx.stroke();

  // Linea del onset (si lo hay).
  if (onsetElapsed) {
    const x = px(onsetElapsed);
    ctx.strokeStyle = '#ff5c6c';
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + plotH); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#ff5c6c';
    ctx.font = '10px sans-serif';
    ctx.fillText('ataque', x + 4, pad.t + 10);
  }

  const linea = (serie, py, color) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    xs.forEach((x, i) => {
      const X = px(x), Y = py(serie[i]);
      if (i === 0) ctx.moveTo(X, Y); else ctx.lineTo(X, Y);
    });
    ctx.stroke();
  };
  linea(pps, pyPps, '#4f8cff');
  linea(lat, pyLat, '#ffc145');

  ctx.font = '11px sans-serif';
  ctx.fillStyle = '#4f8cff'; ctx.fillText('— pps al portal', pad.l, 12);
  ctx.fillStyle = '#ffc145'; ctx.fillText('— latencia (ms)', pad.l + 130, 12);
  ctx.fillStyle = '#5b6b8f';
  ctx.fillText('0', pad.l - 10, pad.t + plotH + 4);
  ctx.fillText(Math.round(xMax) + 's', pad.l + plotW - 10, pad.t + plotH + 16);
}

// -------------------------------------------------------------------------
// Polling de estado
// -------------------------------------------------------------------------
async function tickStatus() {
  let s;
  try {
    s = await (await fetch('/api/status')).json();
  } catch (e) {
    return;
  }

  const titulo = document.getElementById('vivo-titulo');
  const badge = document.getElementById('fase-badge');
  titulo.textContent = s.run_name ? ('Corrida: ' + s.run_name) : 'Sin corrida activa';
  badge.textContent = s.fase;
  badge.className = 'fase-badge ' + s.fase;

  document.getElementById('vivo-tiempo').textContent = s.elapsed != null
    ? ('t+' + s.elapsed + 's / ' + s.duration + 's')
    : '—';
  document.getElementById('btn-parar').disabled = !s.activo;

  if (!document.getElementById('campus-svg').dataset.listo) {
    const nStudents = s.meta && s.meta.students && s.meta.students.length
      ? s.meta.students.length / AREAS.length : 4;
    const nBots = s.meta && s.meta.bots && s.meta.bots.length
      ? s.meta.bots.length / AREAS.length : 2;
    construirCampus(Math.round(nStudents), Math.round(nBots));
    document.getElementById('campus-svg').dataset.listo = '1';
  }
  actualizarCampusFase(s.fase);

  const logs = document.getElementById('logs');
  logs.textContent = (s.logs || []).join('\n');
  logs.scrollTop = logs.scrollHeight;

  if (faseAnterior !== s.fase && !s.activo && ['listo', 'error', 'detenido'].includes(s.fase)) {
    detenerPolling();
  }
  faseAnterior = s.fase;
}

async function tickMetrics() {
  let data;
  try {
    data = await (await fetch('/api/metrics')).json();
  } catch (e) {
    return;
  }
  const s = await (await fetch('/api/status')).json();
  const onset = s.meta ? s.meta.attack_start_elapsed : null;
  dibujarChart(data.rows || [], onset);
}

function iniciarPolling() {
  detenerPolling();
  tickStatus(); tickMetrics();
  pollStatus = setInterval(tickStatus, 1000);
  pollMetrics = setInterval(tickMetrics, 1500);
}

function detenerPolling() {
  if (pollStatus) clearInterval(pollStatus);
  if (pollMetrics) clearInterval(pollMetrics);
  pollStatus = null; pollMetrics = null;
}

document.getElementById('btn-parar').addEventListener('click', async () => {
  await fetch('/api/parar', { method: 'POST' });
  tickStatus();
});

// -------------------------------------------------------------------------
cargarEntorno();
tickStatus();
setInterval(() => { if (!pollStatus) tickStatus(); }, 4000); // por si hay una corrida de otra pestaña
