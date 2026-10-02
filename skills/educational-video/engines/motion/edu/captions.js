// Burned-in captions, word-synced. Words arrive as a list of seconds on the film's clock (see lib/captionplan.js):
//
//   [{ "w": "Halve", "t": 0.42, "e": 0.71 }, { "w": "the", "t": 0.71 }, ...]      (or caption cues: { cues: [{ text, start, end }] })
//
//   EDU.captions.overlay({ words: WORDS })                       // a scene on top of the film, 0 to the end
//   // or inside one scene:  const cap = EDU.captions(root, { words });  ...in run(t):  cap.run(t);
//
// A page of a few words rises in as its first word starts, the word being spoken turns accent and pops, and the page
// drops out before the next one lands. Layout is per format (C.pick) and respects the 9:16 platform zones: nothing in
// the bottom 20 % or the right 12 %. Options: { size, w (max width), cx, bottom (y of the bottom edge), maxLines,
// maxChars, maxWords, style: 'pill' | 'plain', color, active: 'accent' | 'hi' }.
// The word list is data, not code: when the narration grid exists it supplies it (C.GRID.words), a film can pass words
// from anywhere, and nothing else changes. With narration, the overlay is added automatically for the formats in
// timeline.json captions.burn (default 9x16): see the end of this file.
(() => {
  const C = window.C, E = window.EDU, CP = window.CaptionPlan;
  const { put, reg, el, sp, spHit, pick, W, H, clamp } = C;

  const QUICK = { response: 0.1, damping: 1 };      // a page leaves in about a tenth of a second

  function captions(parent, o = {}) {
    let list = o.words || (C.GRID && C.GRID.words) || (o.cues ? CP.fromCues(o.cues) : null);
    if (!list) throw new Error('captions: pass { words } (or { cues }); see lib/captionplan.js for the shape');
    const words = CP.normalize(list);
    const size = o.size || pick(60, 62, 68);
    // text zone: wide frames use most of the width; 9:16 keeps clear of the right-hand 12 % and the bottom 20 %
    const w = o.w || pick(W * 0.72, W * 0.82, W * 0.78);
    const cx = o.cx ?? pick(W / 2, W / 2, (W * 0.88) / 2 + W * 0.02);
    const bottom = o.bottom ?? pick(H * 0.94, H * 0.9, H * 0.74);
    const maxChars = o.maxChars || Math.max(12, Math.floor(w / (size * 0.56)));
    const pages = CP.pages(words, { maxChars, maxLines: o.maxLines || 2, maxWords: o.maxWords || 8, hold: o.hold });
    // a preset's caption style is the default: pill | plain | outline (plain with a stroke in the background colour)
    const PC = (window.PRESET && window.PRESET.captions) || {};
    const styleName = o.style || PC.style || 'pill';
    const pill = styleName === 'pill', activeTone = o.active || (PC.active_word === 'highlight' ? 'hi' : 'accent');
    const stroke = styleName === 'outline' ? ';-webkit-text-stroke:0.16em var(--bg);paint-order:stroke fill' : '';

    const built = pages.map((pg) => {
      const box = el('div', { class: 'cap', style: `left:${cx - w / 2}px;top:auto;bottom:${H - bottom}px;width:${w}px;font-size:${size}px;text-align:center;transform-origin:50% 100%;` +
        `color:${E.tone(o.color || 'ink')}${stroke}` }, parent);
      const inner = el('div', { style: pill ? `display:inline-block;padding:${size * 0.28}px ${size * 0.5}px ${size * 0.34}px;border-radius:${size * 0.5}px;` +
        `background:color-mix(in srgb, var(--card) 94%, transparent);box-shadow:0 2px 6px rgba(0,0,0,.06), 0 18px 50px -18px rgba(0,0,0,.28)` : 'display:inline-block' }, box);
      const lines = pg.lines.map((idx) => {
        const row = el('div', { style: 'white-space:nowrap' }, inner);
        return idx.map((i, k) => { const s = el('span', { class: 'w' }, row, words[i].w); if (k < idx.length - 1) row.appendChild(document.createTextNode(' ')); return { i, el: reg(s) }; });
      }).flat();
      reg(box, { o: 0 });
      return { ...pg, box, spans: lines, k: 1, measured: false };
    });

    function run(t) {
      built.forEach((pg, n) => {
        if (t < pg.from - 0.3 || t >= pg.to + 0.5) { put(pg.box, { o: 0 }); return; }
        if (!pg.measured) { pg.measured = true; pg.k = Math.min(1, w / (pg.box.firstElementChild.offsetWidth || w)); }
        const inP = spHit(t, pg.from, 'snappy'), outP = t >= pg.to ? sp(t, pg.to, QUICK) : 0;
        const a = clamp(inP) * (1 - clamp(outP));
        put(pg.box, { o: a > 0.001 ? a : 0, y: (1 - inP) * size * 0.7 + outP * size * 0.5, s: pg.k * (0.92 + 0.08 * inP) * (1 - 0.04 * outP) });
        for (const s of pg.spans) {
          const wd = words[s.i];
          // the word being spoken: accent colour and a small pop; spoken words stay ink, upcoming ones soften
          const on = clamp(spHit(t, wd.t, 'snappy')) - clamp(sp(t, wd.e, 'snappy'));
          const upcoming = 1 - clamp(spHit(t, wd.t, 'snappy'));
          put(s.el, { s: 1 + 0.035 * on, css: { color: E.mix(activeTone, o.color || 'ink', clamp(on) * 100), opacity: String(1 - 0.5 * upcoming) } });
        }
      });
    }
    return { run, words, pages: built };
  }

  /** A scene on top of everything that shows the captions for the whole film. Call it in film.js after the lesson's scenes. */
  captions.overlay = (o = {}) => C.scene({
    name: o.name || 'captions', from: o.from ?? 0, to: o.to ?? C.DUR,
    build(root, S) { S.cap = captions(root, o); },
    run(t, S) { S.cap.run(t); },
  });

  E.captions = captions;

  // Burned-in captions come with the film: whenever narration words exist (C.GRID.words) and this render's format is listed in
  // timeline.json captions.burn (default ["9x16"]; sync.mjs fills it in), the overlay is added by C.start(), so a lesson
  // never has to remember it. A film that adds its own EDU.captions.overlay (name 'captions') or sets captions.auto false keeps control.
  C.onStart.push(() => {
    const cfg = C.TL.captions || {};
    if (cfg.auto === false || !(cfg.burn || ['9x16']).includes(C.FMT)) return;
    if (!(C.GRID.words && C.GRID.words.length) || C.SCENES.some((S) => S.name === 'captions')) return;
    captions.overlay({});
  });
})();
