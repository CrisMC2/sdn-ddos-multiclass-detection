/* Modulo Entorno: Docker, imagen, puerto, disco, y la prueba de caminos de red. */
import { $, h, ico } from '../core/dom.js';
import { api, post } from '../core/api.js';
import { emit, on } from '../core/bus.js';
import { S } from '../core/state.js';

const PASOS_VERIFICACION = [
  ['alumno -> portal', 'Un alumno alcanza el portal'],
  ['infectado -> portal', 'Una PC infectada alcanza el portal'],
  ['C2 -> infectado', 'El C2 alcanza una PC infectada'],
  ['alumno abre el portal', 'Un alumno abre el portal por HTTP'],
  ['navegador externo abre el portal', 'Tu navegador abre el portal por el puerto 8080'],
];

export async function cargarEntorno() {
  const env = await api('/api/env');
  if (!env) return;
  S.env = env;
  S.envAt = Date.now();
  emit('env', env);
}

function items() {
  const e = S.env;
  const ocupado = S.status && S.status.activo;
  const lista = [];
  lista.push({
    titulo: 'Docker', ok: e.docker, detalle: e.docker ? 'En ejecución' : 'No responde',
    fix: e.docker ? '' : 'Abre Docker Desktop y espera a que diga «Engine running».',
  });
  lista.push({
    titulo: 'Imagen ' + e.imagen_nombre, ok: e.imagen,
    detalle: e.imagen === null ? 'Se revisa cuando Docker responda' : (e.imagen ? 'Disponible' : 'No existe'),
    fix: e.imagen === false ? 'Constrúyela una vez: docker build -t ' + e.imagen_nombre + ' -f scripts/docker/Dockerfile .' : '',
  });
  let puertoOk = e.puerto_libre; let puertoDet = puertoOk ? 'Libre' : 'Ocupado'; let puertoFix = '';
  if (!puertoOk && ocupado) { puertoOk = true; puertoDet = 'En uso por la simulación activa'; }
  else if (!puertoOk) {
    puertoFix = e.contenedor_activo
      ? 'Lo ocupa un contenedor de otra simulación que sigue en marcha: puede ser una anterior sin limpiar o la de otra copia de esta interfaz abierta en otra terminal.'
      : 'Otro programa usa este puerto. Ciérralo para que tu navegador pueda entrar al portal durante la simulación.';
  }
  lista.push({ titulo: 'Puerto ' + e.puerto, ok: puertoOk, detalle: puertoDet, fix: puertoFix });
  const gb = e.disco_libre_gb;
  lista.push({
    titulo: 'Espacio en disco', ok: gb == null ? null : gb > 2,
    detalle: gb == null ? 'No se pudo medir' : gb.toLocaleString('es') + ' GB libres',
    fix: gb != null && gb <= 2 ? 'Libera espacio: una simulación de 120 s ocupa del orden de 10 MB entre captura y métricas.' : '',
  });
  return lista;
}

function pintarEntorno() {
  if (!S.env) return;
  const lista = items();
  const malos = lista.filter((i) => i.ok === false).length;
  const banner = $('#env-banner');
  banner.className = 'banner ' + (malos ? 'bad' : 'good');
  banner.replaceChildren(
    ico(malos ? 'alert' : 'check'),
    h('div', null,
      h('b', null, malos ? (malos === 1 ? 'Falta resolver 1 cosa' : 'Faltan resolver ' + malos + ' cosas') : 'Listo para simular'),
      h('span', null, malos ? 'Revisa lo marcado abajo antes de lanzar una simulación.' : 'Docker, la imagen y el puerto están en orden.')),
  );
  $('#env-checks').replaceChildren(...lista.map((i) => {
    const cls = i.ok === true ? 'ok' : (i.ok === false ? 'bad' : 'unk');
    return h('li', { class: cls },
      ico(i.ok === true ? 'check' : (i.ok === false ? 'x' : 'info'), 'st'),
      h('div', { class: 'chk-t' }, h('b', null, i.titulo), h('span', { class: 'chk-d' }, i.detalle)),
      i.fix ? h('div', { class: 'chk-fix' }, i.fix) : null);
  }));
  $('#btn-clean').hidden = !(S.env.contenedor_activo && !(S.status && S.status.activo));
  pintarVerificacion();
}

export function pintarSaludLateral() {
  if (!S.env) return;
  const e = S.env;
  const fila = (ok, txt) => h('li', { class: ok === true ? 'ok' : (ok === false ? 'bad' : 'unk') },
    ico(ok === true ? 'check' : (ok === false ? 'x' : 'info')), txt);
  $('#rail-health').replaceChildren(
    fila(e.docker, 'Docker'), fila(e.imagen, 'Imagen'),
    fila(e.puerto_libre || (S.status && S.status.activo), 'Puerto ' + e.puerto));
}

function pintarVerificacion() {
  const st = S.status;
  const esVerif = st && st.scenario === 'verify';
  const lista = $('#verify-list'); const nota = $('#verify-note'); const btn = $('#btn-verify');
  const ocupado = st && st.activo;
  btn.disabled = !!ocupado || !S.env || !S.env.docker || !S.env.imagen;
  if (!esVerif) { lista.hidden = true; nota.hidden = true; return; }

  const lineas = st.logs || [];
  const corriendo = !!st.activo;
  const resultados = PASOS_VERIFICACION.map(([clave, etiqueta]) => {
    const linea = lineas.find((l) => l.startsWith('OK ' + clave) || l.startsWith('FALLO ' + clave));
    let estado = corriendo ? 'run' : 'unk';
    if (linea) estado = linea.startsWith('OK ') ? 'ok' : 'bad';
    return { etiqueta, estado };
  });
  lista.hidden = false;
  lista.replaceChildren(...resultados.map((r) => h('li', { class: r.estado },
    ico(r.estado === 'ok' ? 'check' : (r.estado === 'bad' ? 'x' : (r.estado === 'run' ? 'refresh' : 'info')), 'st'),
    h('div', { class: 'chk-t' }, h('b', null, r.etiqueta)))));
  nota.hidden = false;
  const todoOk = resultados.every((r) => r.estado === 'ok');
  const algunoMal = resultados.some((r) => r.estado === 'bad');
  if (corriendo) nota.textContent = 'Levantando la red de prueba. Los resultados aparecen a medida que llegan.';
  else if (todoOk) nota.textContent = 'Los cinco caminos responden. La red está lista para una simulación.';
  else if (algunoMal) nota.textContent = 'Algún camino falló. Vuelve a verificar; si sigue igual, revisa que la imagen de Docker esté actualizada.';
  else nota.textContent = st.error || 'La verificación terminó sin resultados. Vuelve a intentarlo.';
}

export function initEntorno() {
  $('#btn-env-refresh').addEventListener('click', cargarEntorno);
  $('#btn-clean').addEventListener('click', async () => {
    // Eliminar el contenedor interrumpe cualquier corrida que lo este usando,
    // incluida la de otra copia de la interfaz: se pide confirmacion.
    const aviso = 'Esto elimina el contenedor ataque-sdn-run. Si hay una simulación usándolo, se interrumpe y sus datos quedan incompletos.';
    if (!confirm(aviso + '\n\n¿Continuar?')) return;
    await api('/api/limpiar_contenedor', { method: 'POST' });
    cargarEntorno();
  });
  $('#btn-verify').addEventListener('click', async () => {
    const res = await post('/api/lanzar', { scenario: 'verify', duration: 30 });
    if (res && !res.ok) { const nota = $('#verify-note'); nota.hidden = false; nota.textContent = res.error; }
    emit('pedir-estado');
  });

  on('env', () => { pintarEntorno(); pintarSaludLateral(); });
  on('status', () => { if (S.view === 'entorno') pintarEntorno(); pintarSaludLateral(); });
  on('vista', (v) => { if (v === 'entorno') cargarEntorno(); });
}
