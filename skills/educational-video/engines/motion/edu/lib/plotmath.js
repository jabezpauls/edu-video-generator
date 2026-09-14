// Pure maths behind the plot component: tick placement, curve sampling (with breaks at asymptotes) and partial drawing.
// No DOM, loads as a classic <script> (window.PlotMath) or through require().
(function (root, factory) {
  const P = factory();
  if (typeof module === 'object' && module.exports) module.exports = P;
  else root.PlotMath = P;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  /** A 1-2-5 step that gives about `count` ticks over `span`. */
  function niceStep(span, count = 5) {
    const raw = span / Math.max(1, count), mag = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / mag;
    return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * mag;
  }
  /** Tick values in [min, max], multiples of the nice step. */
  function ticks(min, max, count = 5) {
    const step = niceStep(max - min, count), out = [];
    for (let k = Math.ceil(min / step - 1e-9); k * step <= max + step * 1e-9; k++) out.push(+(k * step).toPrecision(12));
    return { step, values: out };
  }
  /** Tick label: no trailing zeros, a real minus sign. */
  function fmt(v, step) {
    const d = Math.max(0, Math.min(6, -Math.floor(Math.log10(step) + 1e-9)));
    const s = String(+(Math.abs(v) < step * 1e-6 ? 0 : v).toFixed(d));
    return s.replace('-', '−');
  }

  /**
   * Sample fn on [a, b] into polylines of [x, y] in data space. The line breaks where fn is not finite or jumps by more
   * than `jump` times the visible y span between neighbours (an asymptote), so no vertical line is ever drawn across it.
   */
  function sample(fn, a, b, n, yr, jump = 2) {
    const span = Math.abs(yr[1] - yr[0]) || 1, out = [];
    let cur = [], prev = null;
    for (let i = 0; i <= n; i++) {
      const x = a + ((b - a) * i) / n, y = fn(x);
      if (!Number.isFinite(y) || (prev != null && Math.abs(y - prev) > jump * span)) { if (cur.length > 1) out.push(cur); cur = []; }
      if (Number.isFinite(y)) { cur.push([x, y]); prev = y; } else prev = null;
    }
    if (cur.length > 1) out.push(cur);
    return out;
  }

  /** Map data polylines to pixels. map = { x(v), y(v) } */
  const toPixels = (polys, map) => polys.map((pl) => pl.map(([x, y]) => [map.x(x), map.y(y)]));

  /**
   * The first fraction p (0..1) of polylines by drawn length (pixels). Returns { polys, tip: [x, y, angle] | null }.
   * Length is measured across all pieces, so the pen moves at a constant speed along the curve.
   */
  function truncate(polys, p) {
    const segLen = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);
    let total = 0;
    for (const pl of polys) for (let i = 1; i < pl.length; i++) total += segLen(pl[i - 1], pl[i]);
    if (!(p > 0) || total === 0) return { polys: [], tip: null };
    let left = Math.min(1, p) * total, tip = null;
    const out = [];
    for (const pl of polys) {
      const piece = [pl[0]];
      for (let i = 1; i < pl.length; i++) {
        const L = segLen(pl[i - 1], pl[i]);
        if (left >= L - 1e-9) {
          piece.push(pl[i]); left -= L; tip = [pl[i][0], pl[i][1], Math.atan2(pl[i][1] - pl[i - 1][1], pl[i][0] - pl[i - 1][0])];
          if (left <= 1e-9) left = -1;                 // exactly at a point: the pen stops here
          if (left < 0) break;
          continue;
        }
        const k = left / L, q = [pl[i - 1][0] + (pl[i][0] - pl[i - 1][0]) * k, pl[i - 1][1] + (pl[i][1] - pl[i - 1][1]) * k];
        piece.push(q); tip = [q[0], q[1], Math.atan2(pl[i][1] - pl[i - 1][1], pl[i][0] - pl[i - 1][0])]; left = -1; break;
      }
      if (piece.length > 1) out.push(piece);
      if (left < 0) break;
    }
    return { polys: out, tip };
  }

  return { niceStep, ticks, fmt, sample, toPixels, truncate };
});
