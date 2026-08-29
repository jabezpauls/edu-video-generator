// Lesson components for the motion engine: shared helpers and the EDU namespace. Loads after core.js and type.js;
// each component file (equation.js, code.js, plot.js, diagram.js, captions.js) adds itself to window.EDU.
// Components follow the engine's contract: build DOM once (in a scene's build()), then every frame call the component's
// run(t, ...) from the scene's run(); it put()s everything it animates. Nothing is kept between frames.
(() => {
  const C = window.C;
  const { step } = window.Motion;

  // KaTeX faces the engine must have before frame 0 (equations measure text). Push, never reassign, C.fonts.
  C.fonts.push('16px KaTeX_Main', 'italic 16px KaTeX_Math', 'bold 16px KaTeX_Main', '16px KaTeX_Size1', '16px KaTeX_Size2',
    '16px KaTeX_AMS');

  /** Look tokens as css colours: ink, ink2, accent, hi, card; anything else passes through (#hex, var(--x), rgb()). */
  const TONES = { ink: 'var(--ink)', ink2: 'var(--ink-2)', accent: 'var(--accent)', hi: 'var(--hi)', card: 'var(--card)', bg: 'var(--bg)' };
  const tone = (n) => TONES[n] || n;
  /** pct percent of colour a over colour b, as one css colour (a transparent b gives a tint). */
  const mix = (a, b, pct) => `color-mix(in srgb, ${tone(a)} ${Math.max(0, Math.min(100, pct)).toFixed(2)}%, ${tone(b)})`;

  /**
   * A critically damped spring preset that settles in about `dur` seconds, for things drawn over a stated time
   * (a curve, an arrow, a line of typing that must land on a word). Same closed form as the named presets.
   */
  const over = (dur) => ({ response: Math.max(0.05, dur / 1.06), damping: 1 });

  /** 0 -> 1 progress of a draw-on that starts at `from` and lasts about `dur` seconds. */
  const draw = (t, from, dur = 1) => step(t - C.at(from), over(dur));

  /** Font size that fits `cols` monospace columns in `width` px (0.6 em per column), never above `max`. */
  const fitMono = (cols, width, max) => Math.min(max, Math.floor(width / (Math.max(1, cols) * 0.602)));

  /** The look tokens resolved to real colours (canvas cannot read var()): { ink, ink2, accent, hi, card, bg, mono }. Read once. */
  let PAL = null;
  const palette = () => {
    if (PAL) return PAL;
    const cs = getComputedStyle(document.getElementById('stage')), v = (n) => cs.getPropertyValue(n).trim();
    PAL = { ink: v('--ink'), ink2: v('--ink-2'), accent: v('--accent'), hi: v('--hi'), card: v('--card'), bg: v('--bg'), mono: v('--font-mono') || 'monospace' };
    return PAL;
  };
  /** A look token or css colour as a colour a canvas understands. */
  const canvasColor = (n) => palette()[n] && n !== 'mono' ? palette()[n] : n;

  window.EDU = { palette, canvasColor, tone, mix, over, draw, fitMono, TONES };
})();
