/* El campus: plano de la red, estado del portal y paquetes en movimiento. */
import { $, h, ico, svgEl } from '../core/dom.js';
import { clamp, mean } from '../core/format.js';
import { AREAS, PORTAL_CUPO, S, catalogo } from '../core/state.js';
import { MotorPaquetes } from './packets.js';

const NW = 148; const NH = 56;     // tamano de los nodos
const TOP = 64; const LAB = 214;   // filas de la red (y)
const LAB_X = [110, 305, 500, 695, 890];
const POR_FILA = 8;                // hosts por fila en cada laboratorio

let modelo = null;
let motor = null;
let clave = '';

/* ----------------------------- construccion ----------------------------- */

function disposicion(ns, nb) {
  const n = ns + nb;
  const filas = Math.ceil(n / POR_FILA);
  const yFila = (r) => 306 + r * 30;
  return { n, filas, yFila, yTexto: yFila(filas - 1) + 38 };
}

function construir(svg, ns, nb) {
  svg.replaceChildren();
  const d = disposicion(ns, nb);
  const alto = d.yTexto + 44;
  svg.setAttribute('viewBox', '0 0 1000 ' + alto);

  const zona = svgEl('g', {}, svg);
  const enlaces = svgEl('g', {}, svg);
  const capaNormal = svgEl('g', { class: 'pk-normal' }, svg);
  const capaAtaque = svgEl('g', { class: 'atk-layer' }, svg);
  const nodos = svgEl('g', {}, svg);
  const hostsG = svgEl('g', {}, svg);

  svgEl('rect', { class: 'zone-rect', x: 200, y: 22, width: 794, height: alto - 34, rx: 14 }, zona);
  svgEl('text', { class: 'zone-label', x: 214, y: d.yTexto + 26 }, zona).textContent = 'Campus UNCP, red 10.0.0.0/8';
  svgEl('text', { class: 'zone-label', x: 80, y: 24, 'text-anchor': 'middle' }, zona).textContent = 'Internet';

  const enlace = (dPath, carries, soft) => svgEl('path', { d: dPath, class: 'lk' + (carries ? ' carries' : '') + (soft ? ' soft' : '') }, enlaces);
  enlace('M154 ' + TOP + 'H216');
  enlace('M364 ' + TOP + 'H426');
  enlace('M574 ' + TOP + 'H636', true);
  enlace('M784 ' + TOP + 'H846', true);

  const nodo = (cx, cy, icono, titulo, sub, cls) => {
    const g = svgEl('g', { class: 'node ' + (cls || '') }, nodos);
    svgEl('rect', { x: cx - NW / 2, y: cy - NH / 2, width: NW, height: NH, rx: 8 }, g);
    const i = svgEl('svg', { class: 'ic', x: cx - NW / 2 + 12, y: cy - 10, width: 20, height: 20, 'aria-hidden': 'true' }, g);
    svgEl('use', { href: '/static/icons.svg#i-' + icono }, i);
    svgEl('text', { x: cx - NW / 2 + 42, y: cy - 3 }, g).textContent = titulo;
    svgEl('text', { class: 'sub', x: cx - NW / 2 + 42, y: cy + 15 }, g).textContent = sub;
    return g;
  };

  nodo(80, TOP, 'terminal', 'C2', 'fuera del campus', 'c2');
  nodo(290, TOP, 'globe', 'Módem', '10.0.0.1');
  nodo(500, TOP, 'switch', 'Switch core', 's1');
  nodo(710, TOP, 'switch', 'DMZ', 's2');

  // Portal: halo de presion detras, nodo, medidor de cupo debajo.
  const halo = svgEl('rect', { class: 'halo', x: 920 - NW / 2 - 4, y: TOP - NH / 2 - 4, width: NW + 8, height: NH + 8, rx: 11 }, nodos);
  const portal = nodo(920, TOP, 'server', 'Portal', '10.0.0.10', 'portal');
  const st = svgEl('svg', { class: 'ic st', x: 920 + NW / 2 - 24, y: TOP - NH / 2 + 6, width: 16, height: 16, style: 'display:none', 'aria-hidden': 'true' }, portal);
  svgEl('use', { href: '/static/icons.svg#i-check' }, st);
  svgEl('rect', { class: 'meter-bg', x: 852, y: 104, width: 136, height: 5, rx: 2.5 }, nodos);
  const medidor = svgEl('rect', { class: 'meter-fill', x: 852, y: 104, width: 0, height: 5, rx: 2.5 }, nodos);
  const medidorT = svgEl('text', { class: 'meter-t', x: 852, y: 126 }, nodos);

  // Laboratorios, sus enlaces y sus hosts.
  const hosts = [];
  const labs = [];
  AREAS.forEach((area, i) => {
    const x = LAB_X[i];
    enlace('M500 ' + (TOP + NH / 2) + 'V140H' + x + 'V' + (LAB - NH / 2), true);
    const gLab = nodo(x, LAB, 'switch', area.titulo, area.sw, 'lab');
    labs.push(gLab);

    const ultimoBus = d.yFila(d.filas - 1) - 17;
    enlace('M' + x + ' ' + (LAB + NH / 2) + 'V' + ultimoBus, true, true);

    for (let r = 0; r < d.filas; r++) {
      const desde = r * POR_FILA; const hasta = Math.min(d.n, desde + POR_FILA);
      const cuantos = hasta - desde;
      const sep = Math.min(22, 156 / Math.max(cuantos, 1));
      const x0 = x - (sep * (cuantos - 1)) / 2;
      const yBus = d.yFila(r) - 17; const yH = d.yFila(r);
      if (cuantos > 1) enlace('M' + x0 + ' ' + yBus + 'H' + (x0 + sep * (cuantos - 1)), true, true);
      for (let k = 0; k < cuantos; k++) {
        const idx = desde + k; const hx = x0 + k * sep;
        const esAlumno = idx < ns;
        enlace('M' + hx + ' ' + yBus + 'V' + (yH - 7), true, true);
        if (esAlumno) svgEl('circle', { class: 'host', cx: hx, cy: yH, r: 7 }, hostsG);
        else svgEl('rect', { class: 'bot', x: hx - 6, y: yH - 6, width: 12, height: 12, transform: 'rotate(45 ' + hx + ' ' + yH + ')' }, hostsG);
        hosts.push({
          tipo: esAlumno ? 'alumno' : 'bot', lab: i, indice: esAlumno ? idx : idx - ns, forma: 'volumen',
          ruta: [[hx, yH], [hx, yBus], [x, yBus], [x, 140], [500, 140], [500, TOP], [860, TOP]],
        });
      }
    }
    svgEl('text', { class: 'cnt', x, y: d.yTexto, 'text-anchor': 'middle' }, hostsG).textContent =
      ns + (ns === 1 ? ' alumno, ' : ' alumnos, ') + nb + (nb === 1 ? ' infectada' : ' infectadas');
  });

  modelo = { portal, halo, medidor, medidorT, hosts, ns, nb, estado: st };
  if (motor) motor.detener();
  motor = new MotorPaquetes(capaNormal, capaAtaque, hosts, halo);
  if (S.view === 'simulacion') motor.arrancar();
}

/* ----------------------------- actualizacion ----------------------------- */

function formaDe(info, ip, botAttacks, cat) {
  const id = botAttacks && botAttacks[ip] ? botAttacks[ip] : (info && info.id);
  return (cat[id] && cat[id].forma) || 'volumen';
}

function cargaDesdeMetricas(st, atacando) {
  const rows = S.rows; const ultima = rows[rows.length - 1];
  const as = st.meta.attack_start_elapsed;
  const antes = rows.filter((r) => as == null || r.t < as);
  const base = mean(antes.map((r) => r.pps).filter((x) => x != null)) || 120;
  const bots = modelo.hosts.filter((x) => x.tipo === 'bot');
  const n = (f) => bots.filter((b) => b.forma === f).length;

  const extra = atacando && ultima && ultima.pps != null ? Math.max(0, ultima.pps - base) : 0;
  const volumen = n('volumen') ? clamp(extra / 9, 10, 70) / n('volumen') : 0;
  const lento = n('lento') ? clamp(((ultima && ultima.conns) || 10) / (n('lento') * 7), 0.7, 3) : 0;
  return {
    normal: clamp(base / 10, 3, 18),
    atacando,
    tasa: { volumen, app: 2.8, lento },
    portalOk: !ultima || ultima.code === '200',
  };
}

function pintarAviso(st, atacando, ultima) {
  const caja = $('#stage-alert');
  if (!atacando) { caja.hidden = true; caja.replaceChildren(); return; }
  const cat = catalogo();
  const mapa = st.meta.bot_attacks || {};
  const vectores = {};
  for (const ip of Object.keys(mapa)) vectores[mapa[ip]] = (vectores[mapa[ip]] || 0) + 1;
  const ids = Object.keys(vectores);
  const nBots = st.meta.bots.length || modelo.hosts.filter((x) => x.tipo === 'bot').length;
  const info = st.scenario_info;

  const hijos = [
    h('span', { class: 'sa-dot' }),
    h('b', null, 'Ataque en curso: ' + (ids.length ? ids.length + ' vectores a la vez' : (info ? info.nombre : ''))),
    h('span', { class: 'sa-sub' }, nBots + ' PCs infectadas apuntan al portal'),
  ];
  if (ids.length) {
    hijos.push(h('ul', { class: 'chips' }, ids.map((id) => h('li', null, ico((cat[id] && cat[id].icono) || 'generic'),
      h('b', null, (cat[id] && cat[id].nombre) || id), ' × ' + vectores[id]))));
  }
  if (ultima && ultima.code && ultima.code !== '200') {
    hijos.push(h('span', { class: 'sa-sub' }, 'El portal dejó de responder (HTTP ' + ultima.code + ').'));
  }
  caja.className = 'stage-alert';
  caja.replaceChildren(...hijos);
  caja.hidden = false;
}

export function renderCampus() {
  const st = S.status; if (!st) return;
  const svg = $('#campus');
  const meta = st.meta || {};
  const hay = st.run_name && st.scenario !== 'verify';

  const cfg = st.config || {};
  let ns = cfg.students_per_area || 4; let nb = cfg.bots_per_area || 2;
  if (meta.students && meta.students.length) ns = Math.round(meta.students.length / AREAS.length);
  if (meta.bots && meta.bots.length) nb = Math.round(meta.bots.length / AREAS.length);
  const nueva = ns + 'x' + nb;
  if (nueva !== clave || !modelo) { construir(svg, ns, nb); clave = nueva; }

  const cat = catalogo();
  const alumnosIp = meta.students || []; const botsIp = meta.bots || [];
  for (const host of modelo.hosts) {
    if (host.tipo !== 'bot') continue;
    const ip = botsIp[host.lab * nb + host.indice];
    host.forma = formaDe(st.scenario_info, ip, meta.bot_attacks, cat);
  }
  void alumnosIp;

  const atacando = !!hay && st.fase === 'atacando';
  svg.classList.toggle('is-attack', atacando);
  $('#stage').classList.toggle('is-attack', atacando);

  const ultima = S.rows[S.rows.length - 1];
  const portal = modelo.portal;
  const sub = $('.sub', portal); const icono = $('.st use', portal);
  portal.classList.remove('ok', 'fail');
  if (hay && ultima && ultima.code) {
    const ok = ultima.code === '200';
    portal.classList.add(ok ? 'ok' : 'fail');
    sub.textContent = ok ? 'Responde' : 'Error ' + ultima.code;
    icono.setAttribute('href', '/static/icons.svg#i-' + (ok ? 'check' : 'alert'));
    icono.parentNode.style.display = '';
  } else { sub.textContent = '10.0.0.10'; icono.parentNode.style.display = 'none'; }

  // Medidor de cupo del portal: conexiones abiertas frente al limite.
  const conns = hay && ultima && ultima.conns != null ? ultima.conns : 0;
  const frac = clamp(conns / PORTAL_CUPO, 0, 1);
  modelo.medidor.setAttribute('width', (136 * frac).toFixed(1));
  modelo.medidor.setAttribute('class', 'meter-fill' + (frac >= 1 ? ' crit' : (frac >= 0.6 ? ' warn' : '')));
  modelo.medidorT.textContent = hay && ultima ? 'Conexiones ' + Math.round(conns) + ' de ' + PORTAL_CUPO : '';

  pintarAviso(st, atacando, ultima);

  if (hay && ['navegando', 'atacando'].includes(st.fase)) motor.setCarga(cargaDesdeMetricas(st, atacando));
  else { motor.setCarga({ normal: 0, atacando: false, tasa: { volumen: 0, app: 0, lento: 0 }, portalOk: true }); }
  if (!hay || !['navegando', 'atacando'].includes(st.fase)) motor.limpiar();
}

export function pausarCampus(visible) {
  if (!motor) return;
  if (visible) motor.arrancar(); else motor.detener();
}
