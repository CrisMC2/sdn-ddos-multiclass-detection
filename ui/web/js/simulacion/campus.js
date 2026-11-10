/* El campus: plano de la red, estado del portal y paquetes en movimiento. */
import { $, h, ico, svgEl } from '../core/dom.js';
import { clamp, mean } from '../core/format.js';
import { AREAS, PORTAL_CUPO, S, catalogo } from '../core/state.js';
import { MotorPaquetes } from './packets.js';

// Solo presentacion: cinco sectores conservan los hosts y los indices del motor.
// El resto del equipamiento es una infraestructura de referencia, sin hosts nuevos.
const SECTORES = [
  { titulo: 'Administración', x: 925, ont: 490, inicio: 535, enlace: 580 },
  { titulo: 'Pabellón A', x: 130, ont: 800, inicio: 845, enlace: 675 },
  { titulo: 'Pabellón B', x: 410, ont: 800, inicio: 845, enlace: 675 },
  { titulo: 'Pabellón C', x: 690, ont: 800, inicio: 845, enlace: 675 },
  { titulo: 'Pabellón D', x: 970, ont: 800, inicio: 845, enlace: 675 },
];
const COMPLEMENTOS = ['Pabellón E', 'Pabellón F', 'Pabellón G', 'Pabellón H', 'Biblioteca', 'Comedor', 'Transporte'];
const POR_FILA = 8;

let modelo = null;
let motor = null;
let clave = '';

/* ----------------------------- construccion ----------------------------- */

function construir(svg, ns, nb) {
  if (motor) motor.detener();
  svg.replaceChildren();
  const n = ns + nb;
  const filas = Math.ceil(n / POR_FILA);
  const filaExtra = 845 + (filas - 1) * 26 + 86;
  const alto = filaExtra + 150;
  svg.setAttribute('viewBox', '0 0 1100 ' + alto);
  svg.setAttribute('aria-describedby', 'campus-desc');
  svgEl('desc', { id: 'campus-desc' }, svg).textContent =
    'Infraestructura de referencia de un campus universitario: borde de Internet, centro de datos y edificios. ' +
    'Cinco sectores representan los hosts emulados; los equipos auxiliares y los edificios conectados con líneas discontinuas son ilustrativos.';

  const zona = svgEl('g', {}, svg);
  const enlaces = svgEl('g', {}, svg);
  const capaNormal = svgEl('g', { class: 'pk-normal' }, svg);
  const capaAtaque = svgEl('g', { class: 'atk-layer' }, svg);
  const nodos = svgEl('g', {}, svg);
  const hostsG = svgEl('g', {}, svg);

  const texto = (parent, x, y, contenido, cls = 'zone-label', ancla = 'middle') => {
    const t = svgEl('text', { class: cls, x, y, 'text-anchor': ancla }, parent);
    t.textContent = contenido;
    return t;
  };
  const region = (y, h, titulo) => {
    svgEl('rect', { class: 'zone-rect', x: 16, y, width: 1068, height: h }, zona);
    texto(zona, 30, y + 19, titulo, 'zone-title', 'start');
  };
  region(16, 252, '01  BORDE DE INTERNET');
  region(282, 342, '02  CENTRO DE DATOS');
  region(638, alto - 654, '03  CAMPUS UNIVERSITARIO');

  const enlace = (puntos, cls = '') => {
    const d = puntos.map(([x, y], i) => (i ? 'L' : 'M') + x + ' ' + y).join(' ');
    return svgEl('path', { d, class: 'lk ' + cls }, enlaces);
  };
  const icono = (parent, x, y, nombre, tam = 32) => {
    const i = svgEl('svg', {
      class: 'ic topology-icon', x, y, width: tam, height: tam,
      style: 'width:' + tam + 'px;height:' + tam + 'px', 'aria-hidden': 'true',
    }, parent);
    svgEl('use', { href: '/static/icons.svg#i-' + nombre }, i);
    return i;
  };
  const nodo = (cx, cy, nombre, titulo, sub, cls = '', ancho = 180) => {
    const g = svgEl('g', { class: 'node ' + cls }, nodos);
    svgEl('rect', { x: cx - ancho / 2, y: cy - 26, width: ancho, height: 52 }, g);
    icono(g, cx - ancho / 2 + 7, cy - 16, nombre);
    texto(g, cx - ancho / 2 + 46, cy - 3, titulo, 'node-label', 'start');
    texto(g, cx - ancho / 2 + 46, cy + 15, sub, 'sub', 'start');
    return g;
  };

  // Borde duplicado, como en un plano de campus. El respaldo es ilustrativo.
  nodo(165, 88, 'terminal', 'C2 externo', 'Origen de la orden', 'c2');
  icono(nodos, 528, 42, 'isp', 44);
  texto(nodos, 588, 61, 'Proveedor / ISP', 'equipment-label', 'start');
  texto(nodos, 588, 78, 'Acceso principal y reserva', 'cnt', 'start');
  enlace([[255, 88], [330, 88], [330, 64], [528, 64]], 'reference');
  enlace([[550, 86], [550, 100], [435, 100], [435, 146]], 'reference');
  enlace([[550, 100], [665, 100], [665, 146]], 'standby');
  nodo(435, 146, 'router', 'Router A', 'Acceso principal', 'auxiliary');
  nodo(665, 146, 'router', 'Router B', 'Reserva · esquema', 'auxiliary');
  enlace([[435, 172], [435, 218]], 'reference');
  enlace([[665, 172], [665, 218]], 'standby');
  nodo(435, 218, 'firewall', 'Seguridad A', 'Perímetro · esquema', 'auxiliary');
  nodo(665, 218, 'firewall', 'Seguridad B', 'Reserva · esquema', 'auxiliary');
  enlace([[435, 244], [435, 265], [550, 265], [550, 340]], 'reference');
  enlace([[665, 244], [665, 265], [550, 265]], 'standby');

  // Nucleo y destino: conservan s1, s2 y el portal de la simulacion actual.
  nodo(550, 340, 'switch', 'Switch core', 's1 · Núcleo SDN');
  enlace([[550, 340], [210, 340], [210, 410]], 'carries');
  nodo(210, 340, 'switch', 'DMZ', 's2 · Red de servidores');
  const portal = nodo(210, 410, 'server', 'Portal', '10.0.0.10', 'portal');
  const st = svgEl('svg', { class: 'ic st', x: 277, y: 390, width: 16, height: 16, style: 'display:none', 'aria-hidden': 'true' }, portal);
  svgEl('use', { href: '/static/icons.svg#i-check' }, st);
  svgEl('rect', { class: 'meter-bg', x: 142, y: 449, width: 136, height: 5 }, nodos);
  const medidor = svgEl('rect', { class: 'meter-fill', x: 142, y: 449, width: 0, height: 5 }, nodos);
  const medidorT = texto(nodos, 210, 472, '', 'meter-t');
  const halo = svgEl('rect', { class: 'halo', x: 118, y: 382, width: 184, height: 56 }, nodos);

  // Racks, controlador y acceso optico no agregan procesos a Docker.
  icono(nodos, 125, 487, 'rack', 64);
  icono(nodos, 213, 487, 'rack', 64);
  texto(nodos, 200, 573, 'Racks de servicios', 'equipment-label');
  texto(nodos, 200, 590, 'Equipamiento de referencia', 'cnt');
  enlace([[210, 436], [210, 483]], 'reference');
  enlace([[210, 483], [157, 483], [157, 487]], 'reference');
  enlace([[210, 483], [245, 483], [245, 487]], 'reference');
  enlace([[550, 340], [550, 675]], 'carries');
  nodo(550, 456, 'olt', 'OLT', 'Cabecera óptica', 'auxiliary');
  nodo(365, 540, 'switch', 'Control de acceso', 'Wi-Fi · esquema', 'auxiliary', 192);
  enlace([[550, 456], [365, 456], [365, 514]], 'reference');
  nodo(550, 580, 'switch', 'Distribución', 'Acceso del campus', 'auxiliary');
  texto(nodos, 574, 514, 'Troncal óptica', 'cnt', 'start');
  enlace([[550, 580], [760, 580], [760, 490], [925, 490]], 'carries');
  enlace([[130, 675], [970, 675]], 'carries');

  // Cada PC mantiene su sector, tipo e indice original. Solo cambia su posicion.
  const hosts = [];
  SECTORES.forEach((sector, i) => {
    const { x, ont, inicio, enlace: bus } = sector;
    const lab = svgEl('g', { class: 'sector lab', 'data-sector': i }, nodos);
    svgEl('title', {}, lab).textContent = sector.titulo + ': grupo emulado ' + AREAS[i].sw;
    if (i === 0) {
      icono(lab, x - 32, 342, 'building', 64);
      texto(lab, x, 426, 'Edificio administrativo', 'equipment-label');
      texto(lab, x, 443, 'Sector 1 · ' + AREAS[i].sw, 'cnt');
    } else {
      enlace([[x, 675], [x, ont]], 'carries');
      icono(lab, x - 25, 692, 'building', 50);
      texto(lab, x, 759, sector.titulo + ' · ' + AREAS[i].sw, 'equipment-label');
    }
    nodo(x, ont, 'ont', 'ONT', 'Acceso de sector ' + (i + 1), 'lab', 174);
    const ultimaFila = inicio + (filas - 1) * 26;
    enlace([[x, ont + 26], [x, ultimaFila - 17]], 'carries soft');
    for (let r = 0; r < filas; r++) {
      const desde = r * POR_FILA;
      const hasta = Math.min(n, desde + POR_FILA);
      const cuantos = hasta - desde;
      const sep = 20;
      const x0 = x - sep * (cuantos - 1) / 2;
      const yH = inicio + r * 26;
      const yBus = yH - 17;
      if (cuantos > 1) enlace([[x0, yBus], [x0 + sep * (cuantos - 1), yBus]], 'carries soft');
      for (let k = 0; k < cuantos; k++) {
        const idx = desde + k;
        const hx = x0 + k * sep;
        const esAlumno = idx < ns;
        enlace([[hx, yBus], [hx, yH - 7]], 'carries soft');
        const pc = svgEl('svg', { x: hx - 8, y: yH - 7, width: 16, height: 16, viewBox: '0 0 16 16', 'aria-hidden': 'true' }, hostsG);
        svgEl('rect', { class: 'pc-case', x: 1, y: 1, width: 14, height: 10 }, pc);
        svgEl('rect', { class: esAlumno ? 'host' : 'bot', x: 3, y: 3, width: 10, height: 6 }, pc);
        svgEl('path', { class: 'pc-stand', d: 'M6 11v3H3v1h10v-1h-3v-3' }, pc);
        const salida = i === 0
          ? [[x, ont], [760, ont], [760, bus], [550, bus]]
          : [[x, bus], [550, bus]];
        const ruta = [[hx, yH], [hx, yBus], [x, yBus], ...salida, [550, 340], [210, 340], [210, 384]];
        hosts.push({ tipo: esAlumno ? 'alumno' : 'bot', lab: i, indice: esAlumno ? idx : idx - ns, forma: 'volumen', ruta });
      }
    }
    texto(hostsG, x, ultimaFila + 32, ns + ' alumnos · ' + nb + ' infectadas', 'cnt');
  });

  // Edificios adicionales: conexion discontinua, sin PCs ni trafico ficticios.
  texto(nodos, 40, filaExtra - 14, 'EXTENSIÓN DEL CAMPUS · EQUIPAMIENTO ILUSTRATIVO', 'zone-title', 'start');
  const busExtra = filaExtra + 4;
  const centros = COMPLEMENTOS.map((_nombre, i) => 96 + i * 151);
  enlace([[550, 675], [550, filaExtra - 38], [centros[0], filaExtra - 38], [centros[0], busExtra]], 'reference');
  enlace([[centros[0], busExtra], [centros.at(-1), busExtra]], 'reference');
  COMPLEMENTOS.forEach((nombre, i) => {
    const x = centros[i];
    enlace([[x, busExtra], [x, filaExtra + 20]], 'reference');
    icono(nodos, x - 23, filaExtra + 20, 'building', 46);
    enlace([[x, filaExtra + 66], [x, filaExtra + 77]], 'reference');
    icono(nodos, x - 12, filaExtra + 77, 'ont', 24);
    texto(nodos, x, filaExtra + 119, nombre, 'equipment-label');
  });
  texto(nodos, 1060, alto - 14, 'Red del campus universitario · Esquema funcional reducido', 'cnt', 'end');

  modelo = { portal, halo, medidor, medidorT, hosts, ns, nb, estado: st };
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
  const as = st.meta && st.meta.attack_start_elapsed;
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
  const mapa = (st.meta && st.meta.bot_attacks) || {};
  const vectores = {};
  for (const ip of Object.keys(mapa)) vectores[mapa[ip]] = (vectores[mapa[ip]] || 0) + 1;
  const ids = Object.keys(vectores);
  const nBots = ((st.meta && st.meta.bots) || []).length || modelo.hosts.filter((x) => x.tipo === 'bot').length;
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
  // El conteo puede superar el cupo (incluye intentos que el portal rechaza):
  // el medidor se llena y el texto lo dice, en vez de un "49 de 30".
  modelo.medidorT.textContent = !(hay && ultima) ? ''
    : (conns > PORTAL_CUPO ? 'Cupo lleno: ' + Math.round(conns) + ' intentos' : 'Cupos ' + Math.round(conns) + ' de ' + PORTAL_CUPO);

  pintarAviso(st, atacando, ultima);

  if (hay && ['navegando', 'atacando'].includes(st.fase)) motor.setCarga(cargaDesdeMetricas(st, atacando));
  else { motor.setCarga({ normal: 0, atacando: false, tasa: { volumen: 0, app: 0, lento: 0 }, portalOk: true }); }
  if (!hay || !['navegando', 'atacando'].includes(st.fase)) motor.limpiar();
}

export function pausarCampus(visible) {
  if (!motor) return;
  if (visible) motor.arrancar(); else motor.detener();
}
