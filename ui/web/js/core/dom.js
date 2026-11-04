/* Ayudas para construir DOM. Todo lo que viene del backend o de los logs entra
   con textContent / createTextNode, nunca con innerHTML: los logs del
   contenedor no son confiables. */

export const NS = 'http://www.w3.org/2000/svg';
export const SPRITE = '/static/icons.svg';

export const $ = (sel, el = document) => el.querySelector(sel);
export const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));

/** Elemento HTML: h('div', {class:'x'}, 'texto', otroNodo). */
export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === false || v == null) continue;
      if (k === 'class') el.className = v; else el.setAttribute(k, v === true ? '' : v);
    }
  }
  for (const k of kids.flat()) {
    if (k == null || k === false) continue;
    el.appendChild(typeof k === 'string' ? document.createTextNode(k) : k);
  }
  return el;
}

/** Elemento SVG; si se da parent, lo agrega ahi. */
export function svgEl(tag, attrs, parent) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  if (parent) parent.appendChild(el);
  return el;
}

/** Icono del sprite (ui/web/icons.svg). */
export function ico(name, cls) {
  const s = svgEl('svg', { class: 'ic' + (cls ? ' ' + cls : ''), 'aria-hidden': 'true' });
  svgEl('use', { href: SPRITE + '#i-' + name }, s);
  return s;
}

export function setIcon(useEl, name) {
  useEl.setAttribute('href', SPRITE + '#i-' + name);
}
