/* Tarjetas de metricas con el cambio frente a "antes del ataque". */
import { $, h, ico } from '../core/dom.js';
import { fmtInt, mean, pctText } from '../core/format.js';
import { PORTAL_CUPO, S } from '../core/state.js';

const IDS = ['pps', 'lat', 'ok', 'conns', 'time'];

function asegurar() {
  const host = $('#tiles');
  if (host.children.length) return;
  for (const id of IDS) {
    host.appendChild(h('div', { class: 'tile', id: 't-' + id },
      h('div', { class: 'tile-l' }), h('div', { class: 'tile-v' }), h('div', { class: 'tile-d' })));
  }
}

function poner(id, label, valor, unidad, delta) {
  const t = $('#t-' + id);
  $('.tile-l', t).textContent = label;
  const v = $('.tile-v', t); v.replaceChildren(valor);
  if (unidad) v.appendChild(h('small', null, unidad));
  const d = $('.tile-d', t);
  d.className = 'tile-d' + (delta && delta.tone ? ' ' + delta.tone : '');
  d.replaceChildren();
  if (delta && delta.icon) d.appendChild(ico(delta.icon));
  d.appendChild(document.createTextNode(delta ? delta.text : ''));
}

export function renderTiles() {
  const st = S.status; if (!st) return;
  asegurar();
  const rows = S.rows; const last = rows[rows.length - 1];
  const as = st.meta && st.meta.attack_start_elapsed != null ? st.meta.attack_start_elapsed : null;
  const antes = as != null ? rows.filter((r) => r.t < as) : rows;
  const durante = as != null ? rows.filter((r) => r.t >= as) : [];
  const bPps = mean(antes.map((r) => r.pps).filter((x) => x != null));
  const bLat = mean(antes.map((r) => r.lat).filter((x) => x != null));
  const sinAtaque = { text: as != null ? '' : 'Todavía sin ataque' };

  let d = sinAtaque;
  const pp = last && as != null ? pctText(last.pps, bPps) : null;
  if (pp) d = { text: pp + ' frente a antes del ataque', icon: last.pps >= bPps ? 'up' : 'down' };
  poner('pps', 'Paquetes por segundo', last && last.pps != null ? fmtInt(last.pps) : '—', '', d);

  d = sinAtaque;
  const pl = last && as != null ? pctText(last.lat, bLat) : null;
  if (pl) d = { text: pl + ' frente a antes del ataque', icon: last.lat >= bLat ? 'up' : 'down', tone: last.lat > bLat * 1.25 ? 'bad' : '' };
  poner('lat', 'Latencia de la sonda', last && last.lat != null ? fmtInt(last.lat) : '—', last && last.lat != null ? 'ms' : '', d);

  const ambito = as != null ? durante : rows;
  const okN = ambito.filter((r) => r.code === '200').length;
  const pct = ambito.length ? Math.round((okN / ambito.length) * 100) : null;
  const mal = pct != null && pct < 90;
  poner('ok', as != null ? 'Respuestas correctas durante el ataque' : 'Respuestas correctas',
    pct == null ? '—' : String(pct), pct == null ? '' : '%',
    { text: ambito.length ? okN + ' de ' + ambito.length + ' sondas' : '', tone: mal ? 'bad' : '', icon: mal ? 'alert' : null });

  const cn = last ? last.conns : null;
  poner('conns', 'Conexiones abiertas en el portal', cn == null ? '—' : fmtInt(cn), '',
    cn != null && cn > PORTAL_CUPO
      ? { text: 'Cupo de ' + PORTAL_CUPO + ' lleno: el resto se rechaza', tone: 'bad', icon: 'alert' }
      : { text: 'Cupo del portal: ' + PORTAL_CUPO });

  const dur = st.duration || 0;
  let sub = 'El ataque aún no empieza';
  if (st.scenario === 'baseline') sub = 'Sin ataque en esta simulación';
  else if (as != null) sub = 'Etiquetado como ataque desde el segundo ' + as;
  poner('time', 'Tiempo medido', String(Math.round(last ? last.t : 0)), dur ? 'de ' + dur + ' s' : 's', { text: sub });
}
