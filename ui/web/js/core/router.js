/* Dos modulos: Entorno y Simulacion. La vista actual vive en el hash (#entorno). */
import { $, $$ } from './dom.js';
import { emit } from './bus.js';
import { S } from './state.js';

export const VISTAS = ['entorno', 'simulacion'];

export function go(vista) {
  if (!VISTAS.includes(vista)) vista = 'entorno';
  S.view = vista;
  for (const v of VISTAS) $('#view-' + v).hidden = v !== vista;
  $$('.nav-item[data-view]').forEach((b) => {
    if (b.dataset.view === vista) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  if (location.hash !== '#' + vista) history.replaceState(null, '', '#' + vista);
  window.scrollTo(0, 0);
  emit('vista', vista);
}

export function initRouter() {
  $$('.nav-item[data-view]').forEach((b) => b.addEventListener('click', () => go(b.dataset.view)));
}

export function vistaInicial(hayCorridaActiva) {
  const hash = location.hash.replace('#', '');
  if (VISTAS.includes(hash)) return hash;
  return hayCorridaActiva ? 'simulacion' : 'entorno';
}
