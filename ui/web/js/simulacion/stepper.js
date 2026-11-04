/* Avance por pasos: arranque, trafico normal, ataque, cierre, termino. */
import { $, h, ico } from '../core/dom.js';
import { S } from '../core/state.js';

let pico = -1;     // paso mas avanzado alcanzado (para marcar donde se detuvo)

export function reiniciarStepper() { pico = -1; }

export function renderStepper() {
  const st = S.status;
  const lista = $('#stepper');
  const hay = st && st.run_name && st.scenario !== 'verify';
  lista.hidden = !hay;
  if (!hay) return;

  const conAtaque = st.scenario !== 'baseline';
  const pasos = [['arrancando', 'Arranque de red'], ['navegando', 'Tráfico normal']];
  if (conAtaque) pasos.push(['atacando', 'Ataque']);
  pasos.push(['cerrando', 'Cierre'], ['listo', 'Terminó']);

  let actual = pasos.findIndex((p) => p[0] === st.fase);
  if (actual >= 0) pico = Math.max(pico, actual);
  const detenida = st.fase === 'error' || st.fase === 'detenido';
  if (actual < 0) actual = pico;
  const terminada = st.fase === 'listo';

  lista.replaceChildren(...pasos.map(([fase, etiqueta], i) => {
    let cls = ''; let icono = 'baseline';
    if (terminada || i < actual) { cls = 'done'; icono = 'check'; }
    else if (i === actual) {
      cls = detenida ? 'stop' : 'now' + (fase === 'atacando' ? ' atk' : '');
      icono = detenida ? 'x' : (fase === 'atacando' ? 'alert' : 'clock');
    }
    const li = h('li', { class: cls }, ico(icono), etiqueta);
    if (cls.startsWith('now')) li.setAttribute('aria-current', 'step');
    return li;
  }));
}
