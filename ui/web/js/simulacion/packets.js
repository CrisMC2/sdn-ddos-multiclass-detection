/* Paquetes que recorren la red. Cada uno viaja por la ruta real de su host:
   host -> bus del laboratorio -> switch -> core -> DMZ -> portal.

   Tipos (la forma tambien distingue, no solo el color):
     req   circulo azul     peticion normal de un alumno
     resp  anillo           respuesta del portal (verde si responde, rojo si no)
     atk   rombo rojo       ataque de volumen: muchos, chicos y rapidos
     app   cuadrado rojo    ataque de aplicacion: peticiones completas
     slow  rombo hueco      ataque lento: pocos, tardan en llegar y se acumulan
   La cantidad sale de las metricas reales (ver campus.js, cargaDesdeMetricas). */
import { svgEl } from '../core/dom.js';

const VELOCIDAD = { req: 480, resp: 480, atk: 820, app: 520, slow: 170 };
const TAMANO_MAX = 240;
const reducirMovimiento = matchMedia('(prefers-reduced-motion: reduce)');

function preparar(ruta) {
  const acum = [0];
  for (let i = 1; i < ruta.length; i++) {
    acum.push(acum[i - 1] + Math.hypot(ruta[i][0] - ruta[i - 1][0], ruta[i][1] - ruta[i - 1][1]));
  }
  return { pts: ruta, acum, largo: acum[acum.length - 1] };
}

function puntoEn(r, d) {
  const { pts, acum } = r;
  let i = 1;
  while (i < acum.length - 1 && acum[i] < d) i++;
  const f = (d - acum[i - 1]) / ((acum[i] - acum[i - 1]) || 1);
  return [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f];
}

export class MotorPaquetes {
  /** capaNormal / capaAtaque son <g> del SVG; hosts: [{tipo, forma, ruta, acc}] */
  constructor(capaNormal, capaAtaque, hosts, portalEl) {
    this.capas = { normal: capaNormal, ataque: capaAtaque };
    this.hosts = hosts.map((h) => ({ ...h, r: preparar(h.ruta), rev: preparar([...h.ruta].reverse()), acc: Math.random() }));
    this.portalEl = portalEl;
    this.activos = [];
    this.pool = { req: [], resp: [], atk: [], app: [], slow: [] };
    this.carga = { normal: 0, atacando: false, tasa: { volumen: 0, app: 0, lento: 0 }, portalOk: true };
    this.actual = { normal: 0, volumen: 0, app: 0, lento: 0 };
    this.impactos = 0;
    this.nivelPortal = 0;
    this.ultimo = 0;
    this.raf = null;
  }

  setCarga(c) { this.carga = c; }

  arrancar() {
    if (this.raf || reducirMovimiento.matches) return;
    this.ultimo = 0;
    const paso = (ahora) => {
      this.raf = requestAnimationFrame(paso);
      if (document.hidden) { this.ultimo = 0; return; }
      // Tiempo real transcurrido (con tope): asi el ritmo no depende de los
      // cuadros por segundo del navegador.
      const dt = this.ultimo ? Math.min(0.25, (ahora - this.ultimo) / 1000) : 0;
      this.ultimo = ahora;
      if (dt > 0) this.cuadro(dt);
    };
    this.raf = requestAnimationFrame(paso);
  }

  detener() {
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = null;
    this.limpiar();
  }

  limpiar() {
    for (const p of this.activos) this.soltar(p);
    this.activos = [];
    this.actual = { normal: 0, volumen: 0, app: 0, lento: 0 };
    this.nivelPortal = 0;
    if (this.portalEl) this.portalEl.style.setProperty('--load', '0');
  }

  elemento(tipo) {
    const libre = this.pool[tipo].pop();
    if (libre) { libre.style.display = ''; return libre; }
    let el;
    if (tipo === 'req') el = svgEl('circle', { class: 'pk-req', r: 3.3 });
    else if (tipo === 'resp') el = svgEl('circle', { class: 'pk-resp', r: 3.1 });
    else if (tipo === 'app') el = svgEl('rect', { class: 'pk-app', x: -3.4, y: -3.4, width: 6.8, height: 6.8 });
    else if (tipo === 'slow') el = svgEl('rect', { class: 'pk-slow', x: -4, y: -4, width: 8, height: 8 });
    else el = svgEl('rect', { class: 'pk-atk', x: -3.3, y: -3.3, width: 6.6, height: 6.6 });
    (tipo === 'req' || tipo === 'resp' ? this.capas.normal : this.capas.ataque).appendChild(el);
    return el;
  }

  soltar(p) {
    p.el.style.display = 'none';
    this.pool[p.tipo].push(p.el);
  }

  lanzar(tipo, ruta, extra) {
    if (this.activos.length >= TAMANO_MAX) return;
    const el = this.elemento(tipo);
    if (tipo === 'resp') el.setAttribute('class', 'pk-resp ' + (extra && extra.ok ? 'ok' : 'err'));
    this.activos.push({ tipo, el, ruta, d: 0, v: VELOCIDAD[tipo] * (0.9 + Math.random() * 0.2) });
  }

  cuadro(dt) {
    const c = this.carga;
    const suave = Math.min(1, dt * 2.5);
    this.actual.normal += (c.normal - this.actual.normal) * suave;
    for (const k of ['volumen', 'app', 'lento']) {
      this.actual[k] += ((c.atacando ? c.tasa[k] : 0) - this.actual[k]) * suave;
    }

    const alumnos = this.hosts.filter((h) => h.tipo === 'alumno');
    const porAlumno = alumnos.length ? this.actual.normal / alumnos.length : 0;
    for (const h of this.hosts) {
      let tasa = 0; let tipo = 'req';
      if (h.tipo === 'alumno') tasa = porAlumno;
      else if (c.atacando) {
        tipo = h.forma === 'lento' ? 'slow' : (h.forma === 'app' ? 'app' : 'atk');
        tasa = this.actual[h.forma === 'lento' ? 'lento' : (h.forma === 'app' ? 'app' : 'volumen')];
      }
      h.acc += tasa * dt;
      while (h.acc >= 1) { h.acc -= 1; this.lanzar(tipo, h.r); }
    }

    let impactos = 0;
    const vivos = [];
    for (const p of this.activos) {
      p.d += p.v * dt;
      const ruta = p.ruta;
      if (p.d >= ruta.largo) {
        if (p.tipo === 'req' && Math.random() < 0.7) {
          const host = this.hosts.find((h) => h.r === ruta);
          if (host) this.lanzar('resp', host.rev, { ok: c.portalOk });
        } else if (p.tipo === 'atk' || p.tipo === 'app' || p.tipo === 'slow') impactos++;
        this.soltar(p);
        continue;
      }
      const [x, y] = puntoEn(ruta, p.d);
      p.el.setAttribute('transform', 'translate(' + x.toFixed(1) + ' ' + y.toFixed(1) + ')' +
        (p.tipo === 'atk' || p.tipo === 'slow' ? ' rotate(45)' : ''));
      vivos.push(p);
    }
    this.activos = vivos;

    // Presion sobre el portal: suaviza los impactos por segundo.
    this.nivelPortal += ((Math.min(1, impactos / dt / 45)) - this.nivelPortal) * 0.08;
    if (this.portalEl) this.portalEl.style.setProperty('--load', this.nivelPortal.toFixed(2));
  }
}
