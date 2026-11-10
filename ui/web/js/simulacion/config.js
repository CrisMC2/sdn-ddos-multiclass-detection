/* Panel de configuracion de la simulacion: un ataque o varios a la vez,
   parametros, linea de tiempo prevista y boton de lanzar. Se pliega a una
   linea de resumen cuando hay una simulacion en marcha. */
import { $, h, ico, setIcon } from '../core/dom.js';
import { post } from '../core/api.js';
import { emit, on } from '../core/bus.js';
import { S, catalogo } from '../core/state.js';

const C = {
  modo: 'single',          // 'single' | 'multi'
  sel: null,               // escenario elegido (modo single)
  multi: new Set(),        // ataques marcados (modo multi)
  valores: {},             // intensidades escritas: VARIABLE -> texto
  perfil: 'normal',        // forma del ataque (PERFILES en ui/server/catalog.py)
  abierto: true,
  vistoCorrida: false,
};

const hayCorrida = () => !!(S.status && S.status.run_name && S.status.scenario !== 'verify');
const activa = () => !!(S.status && S.status.activo);

/* ------------------------------ selector ------------------------------ */

function pintarLista() {
  if (!S.env) return;
  const host = $('#sc-list');
  const clave = C.modo + '|' + S.env.scenarios.map((s) => s.id).join(',');
  if (host.dataset.clave === clave) return;
  host.dataset.clave = clave;
  host.replaceChildren(h('legend', { class: 'sr-only' }, 'Escenario'));

  const multi = C.modo === 'multi';
  const lista = S.env.scenarios.filter((s) => s.id !== 'multivector' && (!multi || s.id !== 'baseline'));
  const grupos = [...S.env.grupos, ...new Set(lista.map((s) => s.grupo).filter((g) => !S.env.grupos.includes(g)))];
  for (const g of grupos) {
    const items = lista.filter((s) => s.grupo === g);
    if (!items.length) continue;
    const caja = h('div', { class: 'sc-group' }, h('h4', null, g));
    for (const s of items) {
      const input = h('input', multi ? { type: 'checkbox', name: 'ataque', value: s.id } : { type: 'radio', name: 'escenario', value: s.id });
      if (multi ? C.multi.has(s.id) : (C.sel && C.sel.id === s.id)) input.checked = true;
      input.addEventListener('change', () => {
        if (multi) { if (input.checked) C.multi.add(s.id); else C.multi.delete(s.id); } else C.sel = s;
        pintarLado();
      });
      caja.appendChild(h('label', { class: 'sc-item' }, input, ico(s.icono),
        h('span', { class: 'sc-body' }, h('span', { class: 'sc-name' }, s.nombre), h('span', { class: 'sc-tool' }, s.herramienta)),
        multi ? h('span', { class: 'sc-box' }) : null));
    }
    host.appendChild(caja);
  }
}

function cambiarModo(modo) {
  C.modo = modo;
  $('#mode-single').classList.toggle('on', modo === 'single');
  $('#mode-multi').classList.toggle('on', modo === 'multi');
  $('#mode-single').setAttribute('aria-pressed', String(modo === 'single'));
  $('#mode-multi').setAttribute('aria-pressed', String(modo === 'multi'));
  $('#sc-list').dataset.clave = '';
  pintarLista();
  pintarLado();
}

/* --------------------------- detalle y formulario --------------------------- */

function atacantes() {
  if (C.modo === 'multi') return [...C.multi].map((id) => catalogo()[id]).filter(Boolean);
  return C.sel && C.sel.id !== 'baseline' ? [C.sel] : [];
}

function pintarLado() {
  const cat = catalogo();
  const multi = C.modo === 'multi';
  const vacio = multi ? C.multi.size === 0 : !C.sel;
  $('#sc-empty').hidden = !vacio;
  $('#sc-panel').hidden = vacio;
  $('#sc-empty-txt').textContent = multi
    ? 'Marca dos o más ataques de la lista: cada PC infectada lanzará uno de ellos, todos al mismo tiempo.'
    : 'Elige un escenario de la lista para ver qué hace y configurarlo.';
  if (vacio) { pintarLanzar(); return; }

  const info = multi ? cat.multivector || { icono: 'multi', nombre: 'Varios a la vez', grupo: 'Combinado', descripcion: '' } : C.sel;
  setIcon($('#sd-icon'), info.icono);
  $('#sd-name').textContent = multi ? 'Varios a la vez (' + C.multi.size + ')' : info.nombre;
  $('#sd-group').textContent = info.grupo;
  $('#sd-desc').textContent = info.descripcion;
  $('#sd-facts').hidden = multi;
  if (!multi) {
    $('#sd-agota').textContent = info.agota;
    $('#sd-firma').textContent = info.firma;
    $('#sd-tool').textContent = info.herramienta;
  }
  const mezcla = $('#sd-mix');
  mezcla.hidden = !multi;
  if (multi) {
    mezcla.replaceChildren(...[...C.multi].map((id) => h('li', null, ico((cat[id] && cat[id].icono) || 'generic'), h('b', null, (cat[id] && cat[id].nombre) || id))));
  }
  $('#fld-onset').hidden = !multi && info.id === 'baseline';
  $('#fld-perfil').hidden = !multi && info.id === 'baseline';
  pintarPerfiles();
  pintarIntensidades();
  pintarFormulario();
}

function pintarPerfiles() {
  const sel = $('#f-perfil');
  const perfiles = (S.env && S.env.perfiles) || [];
  if (sel.options.length !== perfiles.length) {
    sel.replaceChildren(...perfiles.map((p) => h('option', { value: p.id }, p.nombre)));
  }
  sel.value = C.perfil;
  const p = perfiles.find((x) => x.id === C.perfil);
  $('#f-perfil-h').textContent = p ? p.descripcion : '';
}

function pintarIntensidades() {
  const caja = $('#int-list');
  const lista = atacantes().filter((a) => a.intensidad);
  caja.replaceChildren(...lista.map((a) => {
    const i = a.intensidad;
    // Con una forma de ataque distinta de 'normal' la intensidad la sortea el
    // perfil; escribir un valor aqui lo fija igual (gana sobre el perfil).
    const ph = C.perfil === 'normal' ? String(i.defecto) : 'según la forma';
    const input = h('input', { type: 'number', min: i.min, max: i.max, placeholder: ph, inputmode: 'numeric', 'data-env': i.env });
    input.value = C.valores[i.env] || '';
    input.addEventListener('input', () => { C.valores[i.env] = input.value; pintarFormulario(); });
    return h('label', { class: 'field' },
      h('span', { class: 'field-l' }, (C.modo === 'multi' ? a.nombre + ': ' : '') + i.etiqueta),
      h('span', { class: 'input-unit' }, input, h('span', null, 'de ' + i.min + ' a ' + i.max)));
  }));
}

function estado() {
  const atk = atacantes();
  const multi = C.modo === 'multi';
  const hayAtaque = multi || (C.sel && C.sel.id !== 'baseline');
  const duracion = parseInt($('#f-duration').value, 10);
  const raw = $('#f-onset').value;
  const inicio = raw === '' ? null : parseInt(raw, 10);
  let err = ''; let errInicio = false;
  if (!Number.isFinite(duracion) || duracion < 5 || duracion > 1800) err = 'La duración va de 5 a 1800 segundos.';
  else if (hayAtaque && inicio == null) { err = 'Indica en qué segundo arranca el ataque (0 para que arranque de inmediato).'; errInicio = true; }
  else if (hayAtaque && (!Number.isFinite(inicio) || inicio < 0)) { err = 'El inicio del ataque no puede ser negativo.'; errInicio = true; }
  else if (hayAtaque && inicio > 0 && duracion < inicio + 10) { err = 'Tienen que quedar al menos 10 s de ataque: sube la duración o adelanta el inicio.'; errInicio = true; }
  else if (multi && C.multi.size < 2) err = 'Para combinar hay que marcar al menos dos ataques.';

  const intensidades = {};
  if (!err) {
    for (const a of atk) {
      const i = a.intensidad; const txt = C.valores[i && i.env];
      if (!i || txt === undefined || txt === '') continue;
      const v = parseInt(txt, 10);
      if (!Number.isFinite(v) || v < i.min || v > i.max) { err = a.nombre + ': el valor va de ' + i.min + ' a ' + i.max + '.'; break; }
      intensidades[i.env] = v;
    }
  }
  return { atk, multi, hayAtaque, duracion, inicio, err, errInicio, intensidades };
}

function pintarFormulario() {
  const f = estado();
  const e = $('#err-onset');
  e.hidden = !f.errInicio; e.textContent = f.errInicio ? f.err : '';
  $('#f-onset').classList.toggle('invalid', f.errInicio);
  $('#f-duration').classList.toggle('invalid', f.err.startsWith('La duración'));

  const tl = $('#tl'); const leyenda = $('#tl-legend');
  tl.replaceChildren(); leyenda.replaceChildren();
  if (Number.isFinite(f.duracion) && f.duracion > 0 && !f.errInicio) {
    const nav = f.hayAtaque ? Math.max(0, f.inicio || 0) : f.duracion;
    const atk = f.hayAtaque ? f.duracion - nav : 0;
    if (nav > 0) tl.appendChild(h('i', { class: 't-nav', style: 'flex:' + nav }));
    if (atk > 0) tl.appendChild(h('i', { class: 't-atk', style: 'flex:' + atk }));
    if (nav > 0) leyenda.appendChild(h('li', null, h('i', { class: 't-nav' }), 'Tráfico normal: ' + nav + ' s'));
    if (atk > 0) leyenda.appendChild(h('li', null, h('i', { class: 't-atk' }), 'Ataque: ' + atk + ' s'));
  }
  pintarLanzar();
}

function pintarLanzar() {
  const btn = $('#btn-launch'); const nota = $('#launch-note');
  const f = estado();
  const falta = C.modo === 'multi' ? C.multi.size === 0 : !C.sel;
  $('#btn-launch-txt').textContent = f.multi ? 'Iniciar ' + C.multi.size + ' ataques a la vez' : (C.sel ? 'Iniciar ' + C.sel.nombre : 'Iniciar simulación');
  let msg = ''; let mal = false; let ok = true;
  if (falta) { ok = false; msg = ''; }
  else if (activa()) { ok = false; msg = 'Hay una simulación en curso. Detenla o espera a que termine.'; }
  else if (S.env && !S.env.docker) { ok = false; mal = true; msg = 'Docker no responde. Abre Docker Desktop y revisa el Entorno.'; }
  else if (S.env && S.env.imagen === false) { ok = false; mal = true; msg = 'Falta la imagen de Docker. Revisa el Entorno.'; }
  else if (f.err) { ok = false; mal = true; msg = f.err; }
  else msg = 'Dura unos ' + (f.duracion + 20) + ' a ' + (f.duracion + 40) + ' s en total, contando el arranque de la red.';
  btn.disabled = !ok;
  nota.textContent = msg; nota.classList.toggle('bad', mal);
}

/* ------------------------------- lanzar ------------------------------- */

async function lanzar() {
  const f = estado();
  if (f.err || (C.modo === 'single' && !C.sel) || (C.modo === 'multi' && C.multi.size < 2)) return;
  const cuerpo = { scenario: C.modo === 'multi' ? 'multivector' : C.sel.id, duration: f.duracion, intensities: f.intensidades };
  if (C.modo === 'multi') cuerpo.attacks = [...C.multi];
  if (f.hayAtaque) { cuerpo.onset_s = f.inicio; cuerpo.attack_profile = C.perfil; }
  if ($('#f-benign-var').checked) cuerpo.benign_variable = true;
  for (const [campo, id] of [['run_tag', 'f-tag'], ['students_per_area', 'f-students'], ['bots_per_area', 'f-bots'], ['seed', 'f-seed']]) {
    const v = $('#' + id).value.trim(); if (v) cuerpo[campo] = v;
  }
  $('#btn-launch').disabled = true;
  const res = await post('/api/lanzar', cuerpo);
  if (!res || !res.ok) {
    const nota = $('#launch-note'); nota.textContent = (res && res.error) || 'No se pudo lanzar la simulación.'; nota.classList.add('bad');
    pintarLanzar();
    return;
  }
  C.abierto = false;
  emit('lanzada', res.run_name);
  emit('pedir-estado');
}

/* --------------------- plegado y resumen de una linea --------------------- */

function pintarPlegado() {
  const hay = hayCorrida();
  if (hay && !C.vistoCorrida) { C.vistoCorrida = true; C.abierto = false; }   // al recargar con una corrida en marcha
  const plegado = hay && !C.abierto;
  $('#cfg').classList.toggle('collapsed', plegado);
  const toggle = $('#btn-cfg-toggle');
  toggle.hidden = !hay;
  $('#btn-cfg-toggle-txt').textContent = plegado ? 'Nueva simulación' : 'Ocultar configuración';
  const resumen = $('#cfg-sum');
  resumen.hidden = !plegado;
  if (!plegado) return;

  const st = S.status; const cfg = st.config || {}; const cat = catalogo();
  const chips = [];
  const ids = cfg.attacks && cfg.attacks.length ? cfg.attacks : [];
  if (st.scenario === 'multivector') chips.push(h('li', null, ico('multi'), h('b', null, 'Varios a la vez'), ' ' + ids.map((i) => (cat[i] && cat[i].nombre) || i).join(', ')));
  else chips.push(h('li', null, ico((cat[st.scenario] && cat[st.scenario].icono) || 'generic'), h('b', null, (cat[st.scenario] && cat[st.scenario].nombre) || st.scenario)));
  chips.push(h('li', null, ico('clock'), st.duration + ' s'));
  if (st.scenario !== 'baseline') chips.push(h('li', null, ico('bolt'), 'ataque desde el segundo ' + (st.meta.onset_planned_s != null ? st.meta.onset_planned_s : cfg.onset_s)));
  if (cfg.perfil && cfg.perfil !== 'normal') {
    const p = ((S.env && S.env.perfiles) || []).find((x) => x.id === cfg.perfil);
    chips.push(h('li', null, ico('sliders'), 'forma: ' + (p ? p.nombre : cfg.perfil)));
  }
  if (cfg.carga_variable) chips.push(h('li', null, 'carga de alumnos variable'));
  for (const [k, v] of Object.entries(cfg.intensities || {})) chips.push(h('li', null, k + ' ' + v));
  resumen.replaceChildren(...chips);
}

export function renderConfig() {
  pintarLista();
  pintarPlegado();
  pintarLanzar();
}

export function initConfig() {
  $('#mode-single').addEventListener('click', () => cambiarModo('single'));
  $('#mode-multi').addEventListener('click', () => cambiarModo('multi'));
  for (const id of ['f-duration', 'f-onset']) $('#' + id).addEventListener('input', pintarFormulario);
  $('#f-perfil').addEventListener('change', (e) => { C.perfil = e.target.value; pintarPerfiles(); pintarIntensidades(); });
  $('#btn-launch').addEventListener('click', lanzar);
  $('#btn-cfg-toggle').addEventListener('click', () => { C.abierto = !C.abierto; pintarPlegado(); });
  on('env', renderConfig);
  on('status', renderConfig);
}
