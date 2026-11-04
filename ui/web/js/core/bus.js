/* Bus de eventos minimo: los modulos no se importan entre si, se avisan. */

const listeners = new Map();

export function on(evt, fn) {
  if (!listeners.has(evt)) listeners.set(evt, []);
  listeners.get(evt).push(fn);
}

export function emit(evt, data) {
  for (const fn of listeners.get(evt) || []) fn(data);
}
