/* Formato de numeros y utilidades estadisticas pequenas. */

export const num = (v) => { const n = parseFloat(v); return Number.isFinite(n) ? n : null; };
export const fmtInt = (v) => Math.round(v).toLocaleString('es');
export const mean = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : null);
export const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export function fmtBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1024 * 1024) return (b / 1024).toFixed(0) + ' KB';
  return (b / (1024 * 1024)).toFixed(1) + ' MB';
}

/** "+86 %" / "-41 %" respecto a una base; null si no se puede calcular. */
export function pctText(now, base) {
  if (now == null || base == null || base === 0) return null;
  const p = Math.round(((now - base) / base) * 100);
  return (p > 0 ? '+' : '') + p.toLocaleString('es') + ' %';
}

/** Metricas por segundo del CSV -> numeros. Se omite el segundo 1: el contador
    del portal arranca ahi y sale vacio (misma regla que build_windows.py). */
export function cleanRows(raw) {
  return raw.map((r) => ({
    t: num(r.elapsed_s), pps: num(r.server_rx_pps), lat: num(r.probe_latency_ms),
    code: (r.probe_http_code || '').trim(), conns: num(r.server_conns),
  })).filter((r) => r.t != null && r.t > 1);
}
