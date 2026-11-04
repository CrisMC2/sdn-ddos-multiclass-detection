/* Tema claro / oscuro: sigue al sistema, con boton para forzarlo. */
import { $, setIcon } from './dom.js';

function efectivo() {
  return document.documentElement.dataset.theme
    || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
}

function pintarBoton() {
  const oscuro = efectivo() === 'dark';
  setIcon($('#theme-ic'), oscuro ? 'sun' : 'moon');
  $('#theme-txt').textContent = oscuro ? 'Tema claro' : 'Tema oscuro';
}

export function initTheme() {
  try {
    const guardado = localStorage.getItem('ddos-theme');
    if (guardado === 'light' || guardado === 'dark') document.documentElement.dataset.theme = guardado;
  } catch (e) { /* sin almacenamiento: se sigue el del sistema */ }
  pintarBoton();
  $('#theme-btn').addEventListener('click', () => {
    const siguiente = efectivo() === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = siguiente;
    try { localStorage.setItem('ddos-theme', siguiente); } catch (e) { /* idem */ }
    pintarBoton();
  });
}
