// Display type: words rise through a mask, leave upward through it. Typewriter with caret.
// All pure functions of t. Build DOM in scene build(); animate in run().
(() => {
  const C = window.C;

  /** A masked line of words. opts: { x, y, size, cls='display', color, accent: [word indices], gap } → { el, words } */
  function line(parent, text, o = {}) {
    const el = C.el('div', { class: `line ${o.cls || 'display'}`, style:
      `left:${o.x || 0}px;top:${o.y || 0}px;font-size:${o.size || 160}px;${o.color ? `color:${o.color};` : ''}` }, parent);
    const words = text.split(' ').map((w, i) => {
      const s = C.el('span', { class: 'word' }, el, w);
      if (o.accent && o.accent.includes(i)) s.style.color = 'var(--accent)';
      if (i < text.split(' ').length - 1) el.appendChild(document.createTextNode(' '));
      return C.reg(s, { y: 0 });
    });
    C.reg(el);
    return { el, words, size: o.size || 160 };
  }

  /**
   * Words rise in and lift out.
   *   inAt:   when for word 0, or an array of whens (one per word, e.g. the narration cues of those words). Hits use
   *           C.spHit: they read ON the cue.
   *   outAt:  when the line starts leaving, or null. RULE: set it to the NEXT thing's in-time minus the exit time,
   *           so the outgoing line is gone before the incoming one lands (no double exposure at swaps).
   *   opts:   { stagger: 0.07 s, preset: 'heavy', exit: 0.16 s }
   * Words start 145% of the size below the mask, so no glyph tops peek through the padding on the first frame.
   */
  function rise(t, L, inAt, outAt = null, o = {}) {
    const stagger = o.stagger ?? 0.07, preset = o.preset || 'heavy', exit = o.exit ?? 0.16;
    const below = L.size * 1.45, above = -L.size * 1.45;
    L.words.forEach((w, i) => {
      const tin = Array.isArray(inAt) ? inAt[i] : C.at(inAt) + i * stagger;
      let y = below * (1 - C.spHit(t, tin, preset));
      if (outAt != null) y += above * C.sp(t, C.at(outAt) + i * stagger * 0.5 - exit * 0.5, 'snappy');
      C.put(w, { y, hide: y >= below * 0.999 || y <= above * 0.999 });
    });
  }

  /** Typewriter between whens a..b into el (a text holder). Caret hides once the line starts leaving (hideAt). */
  function type(t, el, text, a, b, caret = null, hideAt = Infinity) {
    const n = Math.floor(C.seg(t, a, b) * text.length + 1e-6);
    C.put(el, { text: text.slice(0, n) });
    if (caret) {
      const blink = n < text.length || Math.floor(t * 2.4) % 2 === 0;   // blinks only once typing is done
      C.put(caret, { o: t >= C.at(a) - 0.25 && t < C.at(hideAt) && blink ? 1 : 0 });
    }
    return n;
  }

  window.TYPE = { line, rise, type };
})();
