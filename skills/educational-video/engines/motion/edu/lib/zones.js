// Storyboard positions (center, top, left, bottom-right, ...) as boxes in a frame, per aspect ratio. Pure; loads as a
// classic <script> (window.Zones) or through require().
//
// The content area leaves the left/right margin the house style uses, the 9:16 platform zones (top 14 %, right 12 %,
// bottom 20 %), and, unless opts.captions is false, the strip burned-in captions occupy. In a tall frame the side-by-side
// positions re-block into stacked ones: left -> top half, right -> bottom half, the corners -> the quarters of those halves
// (top-left stays top-left of the upper half, bottom-left is the lower half's, and so on), so two elements that sit
// side by side in 16:9 stack in 9:16 instead of shrinking.
(function (root, factory) {
  const Z = factory();
  if (typeof module === 'object' && module.exports) module.exports = Z;
  else root.Zones = Z;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const POSITIONS = ['center', 'top', 'bottom', 'left', 'right', 'top-left', 'top-right', 'bottom-left', 'bottom-right'];

  /** The area content may use: { x, y, w, h }. */
  function content(W, H, opts = {}) {
    const tall = H > W, caps = opts.captions !== false;
    const left = Math.round(W * (tall ? 0.065 : 0.073));
    const right = tall ? Math.round(W * 0.12) : left;
    const top = Math.round(H * (tall ? 0.14 : 0.07));
    const bottom = Math.round(H * (tall ? (caps ? 0.62 : 0.8) : (caps ? 0.8 : 0.93)));
    return { x: left, y: top, w: W - left - right, h: bottom - top };
  }

  /** A position word -> { x, y, w, h } inside the content area (a box, not a point: centre it yourself). */
  function zone(position, W, H, opts = {}) {
    if (!POSITIONS.includes(position)) throw new Error(`zones: unknown position "${position}" (use ${POSITIONS.join(', ')})`);
    const c = content(W, H, opts), gap = Math.round(Math.min(W, H) * 0.03), tall = H > W;
    const half = (len) => Math.floor((len - gap) / 2), third = (len) => Math.floor((len - 2 * gap) / 3);
    const box = (x, y, w, h) => ({ x: c.x + x, y: c.y + y, w, h });
    const cw = c.w, ch = c.h, hw = half(cw), hh = half(ch);
    if (position === 'center') return box(0, Math.round(ch * 0.2), cw, Math.round(ch * 0.6));
    if (position === 'top') return box(0, 0, cw, third(ch));
    if (position === 'bottom') return box(0, ch - third(ch), cw, third(ch));
    if (tall) {
      // side-by-side becomes stacked
      if (position === 'left' || position === 'top-left' || position === 'top-right') return box(0, 0, cw, hh);
      return box(0, hh + gap, cw, hh);
    }
    const xs = position.endsWith('left') || position === 'left' ? 0 : hw + gap;
    if (position === 'left' || position === 'right') return box(xs, 0, hw, ch);
    return box(xs, position.startsWith('top') ? 0 : hh + gap, hw, hh);
  }

  return { POSITIONS, content, zone };
});
