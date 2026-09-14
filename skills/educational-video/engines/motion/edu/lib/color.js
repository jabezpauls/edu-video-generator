// Colour parsing and blending for canvas drawing (a canvas cannot resolve var() or blend css colours itself).
// Loads as a classic <script> (window.Color) or through require().
(function (root, factory) {
  const K = factory();
  if (typeof module === 'object' && module.exports) module.exports = K;
  else root.Color = K;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  /** '#rgb', '#rrggbb', 'rgb(r, g, b)', 'rgba(r, g, b, a)' -> [r, g, b, a]; anything else throws. */
  function parse(s) {
    const x = String(s).trim();
    let m = /^#([\da-f]{3})$/i.exec(x);
    if (m) return [...m[1]].map((h) => parseInt(h + h, 16)).concat(1);
    m = /^#([\da-f]{6})$/i.exec(x);
    if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)).concat(1);
    m = /^rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$/i.exec(x);
    if (m) { const a = m[4] == null ? 1 : m[4].endsWith('%') ? parseFloat(m[4]) / 100 : parseFloat(m[4]); return [+m[1], +m[2], +m[3], a]; }
    throw new Error(`color: cannot parse "${s}"`);
  }
  /** a toward b by k (0..1), componentwise. */
  const lerp = (a, b, k) => a.map((v, i) => v + (b[i] - v) * k);
  const css = (c) => `rgba(${Math.round(c[0])}, ${Math.round(c[1])}, ${Math.round(c[2])}, ${+c[3].toFixed(3)})`;
  /** css colour with alpha multiplied by k. */
  const fade = (c, k) => css([c[0], c[1], c[2], c[3] * k]);

  return { parse, lerp, css, fade };
});
