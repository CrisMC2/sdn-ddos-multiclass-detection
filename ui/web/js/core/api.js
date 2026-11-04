/* Llamadas al backend. Si una falla, se avisa que se perdio la conexion. */
import { emit } from './bus.js';
import { S } from './state.js';

export async function api(path, opts) {
  try {
    const r = await fetch(path, opts);
    setConectado(true);
    return await r.json();
  } catch (e) {
    setConectado(false);
    return null;
  }
}

export function post(path, body) {
  return api(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
}

function setConectado(v) {
  if (S.conectado === v) return;
  S.conectado = v;
  emit('conexion', v);
}
