// Motion engine. A lesson is a pure function of time: window.seek(t) paints frame t, t in seconds.
//
// Frame lifecycle:  begin() → every live scene's run() calls put(el, props) → commit() → after() hooks → commit()
// Every animated element is registered once with reg(el, base). On every frame commit() writes base ⊕ this
// frame's overrides to EVERY registered element, so no state survives between frames and any frame can be painted
// in any order. No timers, no CSS transitions, no Math.random; seeded noise only (mulberry32).
//
// Time: every placement takes a "when" (see lib/time.js): seconds, a mark from timeline.json, or a cue from the cue
// grid ('s03.derivative', optionally '+0.3'). Narration word timings arrive as cues, so a film written against cue
// names keeps its sync when the speech changes.
//
// Loads after lib/motion.js, lib/time.js and data.js (window.TL timeline, window.GRID cue grid, window.BEATS).
(() => {
  const TL = window.TL || {}, GRID = window.GRID || {}, BEATS = window.BEATS || {};
  const qs = new URLSearchParams(location.search);
  const FORMATS = { '16x9': [1920, 1080], '1x1': [1080, 1080], '4x5': [1080, 1350], '9x16': [1080, 1920] };
  const FMT = qs.get('fmt') || (TL.formats || ['16x9'])[0];
  if (!FORMATS[FMT]) throw new Error(`unknown format "${FMT}" (use ${Object.keys(FORMATS).join(', ')})`);
  const [W, H] = FORMATS[FMT];
  const FPS = TL.fps || 60, DUR = TL.duration || 15;
  const { step, track } = window.Motion;

  // ------------------------------------------------------------------ time (seconds are the unit)
  const T = window.Time.makeTime({ marks: TL.marks, cues: GRID.cues, beats: BEATS, bpm: TL.bpm });
  const at = T.at;                                 // when → seconds; throws on an unknown name, loudly, at build or paint
  // Visual hits lead their cue slightly so they READ on it (audio stays on the grid). A masked word only becomes visible
  // part-way through its spring, so the lead is the larger of 3 frames and the time the preset needs to cover half its travel.
  const LEAD = 3 / FPS;
  const halfCache = {};
  function leadFor(preset = 'snappy') {
    const key = typeof preset === 'string' ? preset : JSON.stringify(preset);
    if (!(key in halfCache)) { let tau = 0; while (step(tau, preset) < 0.5 && tau < 2) tau += 0.001; halfCache[key] = tau; }
    return Math.max(LEAD, halfCache[key]);
  }

  // ------------------------------------------------------------------ math
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, x) => a + (b - a) * x;
  const seg = (t, a, b) => clamp((t - at(a)) / (at(b) - at(a)));   // linear 0→1 between two whens (typing, scrolls, slow pushes)
  const ease = {
    inOut: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    out: (x) => 1 - Math.pow(1 - x, 3),
    expoOut: (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)),
    expoIn: (x) => (x <= 0 ? 0 : Math.pow(2, 10 * x - 10)),
  };
  // springs released at a when (lib/motion.js). presets: snappy | default | heavy   (playful: characters only)
  const sp = (t, when, preset = 'default') => step(t - at(when), preset);
  const spHit = (t, when, preset = 'snappy', lead = leadFor(preset)) => step(t - (at(when) - lead), preset);   // reads ON the cue
  // keys: [[when, value, preset?], ...]; first key = initial value. Retargets keep velocity (superposition).
  const trk = (t, keys, preset = 'default') => track(t, keys.map(([w, v, p]) => [at(w), v, p]), preset);
  function trkObj(t, keys, preset = 'default') {
    const out = {};
    for (const k of Object.keys(keys[0][1])) out[k] = trk(t, keys.map(([w, v, p]) => [w, v[k] ?? keys[0][1][k], p]), preset);
    return out;
  }
  // 1 inside [a, b) with spring edges; b may be null (stays on)
  const win = (t, a, b, pin = 'snappy', pout = 'snappy') => sp(t, a, pin) - (b == null ? 0 : sp(t, b, pout));

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  // smooth seeded 1D noise in [-1, 1] (drift, micro camera moves)
  function noise1(seed) {
    const r = mulberry32(seed), v = Array.from({ length: 256 }, () => r() * 2 - 1);
    return (x) => { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return lerp(v[i & 255], v[(i + 1) & 255], u); };
  }
  // pick a value per format: pick(wide, square, tall)  (4x5 uses square)
  const pick = (a, b = a, c = b) => (FMT === '16x9' ? a : FMT === '9x16' ? c : b);

  // ------------------------------------------------------------------ DOM registry
  const stage = document.getElementById('stage');
  stage.style.width = W + 'px'; stage.style.height = H + 'px';
  const REG = [];
  let OVER = new Map();
  function el(tag, attrs = {}, parent = null, html = '') {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'style') e.style.cssText = v; else if (k === 'class') e.className = v; else e.setAttribute(k, v);
    }
    if (html) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  }
  const frag = (html) => { const d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstElementChild; };

  /** Register an animated element. base = its props on frames where nobody put() it. Hidden things: {o: 0}. */
  function reg(e, base = {}) {
    if (e._reg) { Object.assign(e._base, base); return e; }
    e._reg = true; e._base = { o: 1, ...base }; e._last = {}; e._orig = {};
    REG.push(e);
    return e;
  }
  /** Override props for this frame: x y (px) s sx sy r (deg) o hide clip filter css{} text html. Later calls merge. */
  function put(e, props) {
    if (!e) return;
    if (!e._reg) reg(e);
    const cur = OVER.get(e);
    OVER.set(e, cur ? Object.assign(cur, props) : { ...props });
  }
  // 2D transforms only, and no will-change: a composited layer (translate3d / will-change / 3D rotate) keeps a cached
  // raster whose pixels depend on which frame was painted before, which breaks seek(t) determinism (render --verify).
  const TF = ['x', 'y', 's', 'sx', 'sy', 'r'];
  // A settled spring is the identity to within what the transform string can express. Write no transform then: an element
  // that once carried a real transform and one that never did must paint the same pixels (Chromium keeps raster state of
  // text that has moved), or a frame would depend on the frames painted before it.
  const identity = (p) => Math.abs(p.x || 0) < 0.005 && Math.abs(p.y || 0) < 0.005 && Math.abs(p.r || 0) < 0.0005 &&
    Math.abs((p.s ?? 1) * (p.sx ?? 1) - 1) < 5e-6 && Math.abs((p.s ?? 1) * (p.sy ?? 1) - 1) < 5e-6;
  function commit() {
    for (const e of REG) {
      const p = Object.assign({}, e._base, OVER.get(e) || {});
      const st = {};
      if (TF.some((k) => p[k] != null) && !identity(p)) {
        const s = p.s ?? 1;
        st.transform = `translate(${(p.x || 0).toFixed(2)}px, ${(p.y || 0).toFixed(2)}px) rotate(${(p.r || 0).toFixed(3)}deg) scale(${(s * (p.sx ?? 1)).toFixed(5)}, ${(s * (p.sy ?? 1)).toFixed(5)})`;
      }
      if (p.o < 0.999) st.opacity = String(Math.max(0, p.o).toFixed(4));
      if (p.o <= 0.001 || p.hide) st.visibility = 'hidden';
      if (p.clip) st.clipPath = p.clip;
      if (p.filter) st.filter = p.filter;
      if (p.css) Object.assign(st, p.css);
      // any style ever written but not set this frame returns to its original inline value
      for (const k of Object.keys(e._orig)) if (!(k in st)) st[k] = e._orig[k];
      for (const [k, v] of Object.entries(st)) {
        const custom = k.startsWith('--');
        if (!(k in e._orig)) e._orig[k] = custom ? e.style.getPropertyValue(k) : e.style[k];
        if (e._last[k] !== v) { custom ? e.style.setProperty(k, v) : (e.style[k] = v); e._last[k] = v; }
      }
      for (const key of ['text', 'html']) {
        const orig = '__' + key + '0';
        if (key in p || e[orig] != null) {
          if (e[orig] == null) e[orig] = key === 'text' ? e.textContent : e.innerHTML;
          const v = key in p ? p[key] : e[orig];
          if (e._last['__' + key] !== v) { key === 'text' ? (e.textContent = v) : (e.innerHTML = v); e._last['__' + key] = v; }
        }
      }
    }
  }
  const inset = (top, right, bottom, left, r = 0) => `inset(${top}% ${right}% ${bottom}% ${left}%${r ? ` round ${r}px` : ''})`;
  /** Live rect of an element in STAGE px. Reads layout: call only in after() hooks. */
  function rectOf(e) {
    const r = e.getBoundingClientRect(), s = stage.getBoundingClientRect(), k = s.width / W;
    return { x: (r.left - s.left) / k, y: (r.top - s.top) / k, w: r.width / k, h: r.height / k,
      cx: (r.left - s.left + r.width / 2) / k, cy: (r.top - s.top + r.height / 2) / k };
  }

  // ------------------------------------------------------------------ scenes
  // scene({ name, from, to, pre, post, cut, build(root, S), run(t, S), after(t, S) })
  //   from/to: whens (seconds, marks, cues). The root is visible on [from - pre, to + post) seconds and run() is only
  //   called then. Name a scene after its storyboard id ('s01') so `render.sh motion <project> 01` can find it.
  //   cut: true (default when pre === 0) → from is a hard cut: motion-blur samples never straddle it.
  //   S = { root, name, from, to } plus anything build() stores on it.
  const SCENES = [];
  function scene(def) {
    const S = { pre: 0, post: 0, ...def };
    S.root = el('div', { class: 'scene', 'data-scene': S.name }, stage);
    reg(S.root, { hide: true });
    SCENES.push(S);
    return S;
  }
  const canvas = (parent) => {
    const c = el('canvas', { width: W, height: H, style: `position:absolute;left:0;top:0;width:${W}px;height:${H}px` }, parent);
    return c.getContext('2d');
  };
  const hooks = { before: [], after: [] };      // global per-frame hooks (camera, cursor, overlays)

  function paint(t) {
    OVER = new Map();
    for (const h of hooks.before) h(t);
    // a scene starting at <= 0 owns frame 0
    const live = SCENES.filter((S) => (at(S.from) <= 0 || t >= at(S.from) - S.pre) && t < at(S.to) + S.post);
    for (const S of live) { put(S.root, { hide: false }); S.run && S.run(t, S); }
    commit();
    if (hooks.after.length || live.some((S) => S.after)) {
      for (const S of live) S.after && S.after(t, S);
      for (const h of hooks.after) h(t);
      commit();
    }
  }

  window.C = {
    TL, GRID, BEATS, FMT, W, H, FPS, DUR, LEAD, leadFor, stage, pick,
    at, bt: T.beat, clamp, lerp, seg, ease, sp, spHit, trk, trkObj, win, mulberry32, noise1,
    el, frag, reg, put, commit, inset, rectOf, scene, canvas, hooks, SCENES,
    fonts: [],              // film.js: e.g. C.fonts.push('600 100px Display', '400 40px UI') — awaited before frame 0
  };

  // ------------------------------------------------------------------ boot (called at the end of film.js)
  /**
   * A look preset (window.PRESET, from the project's preset.json via sync.mjs) becomes the :root tokens and the two font faces:
   * display -> 'Display' / --font-display, body -> 'UI' / --font-ui (also --font-body). Returns the promise that loads the faces.
   */
  function applyPreset() {
    const P = window.PRESET;
    if (!P) return Promise.resolve();
    const set = (k, v) => v && stage.style.setProperty(k, v);
    const c = P.colors || {};
    set('--bg', c.bg); set('--ink', c.ink); set('--ink-2', c.ink2); set('--accent', c.accent); set('--hi', c.highlight); set('--card', c.card);
    const loads = [];
    for (const [role, family, cssVar] of [['display', 'Display', '--font-display'], ['body', 'UI', '--font-ui']]) {
      const f = (P.fonts || {})[role];
      if (!f || !f.woff2) continue;
      const face = new FontFace(family, `url(../${f.woff2})`, { weight: '100 900' });
      loads.push(face.load().then((ff) => { document.fonts.add(ff); }, () => console.warn(`preset font failed: ${f.woff2}`)));
      set(cssVar, `'${family}', 'Helvetica Neue', Arial, sans-serif`);
      if (role === 'display' && f.tracking) set('--display-tracking', f.tracking);
    }
    set('--font-body', 'var(--font-ui)');
    return Promise.all(loads);
  }

  C.onStart = [];           // functions run once at the start of C.start(), before scenes build (the burned captions add their overlay here)
  C.start = () => {
    for (const f of C.onStart) f();
    const presetReady = applyPreset();
    for (const S of SCENES) S.build && S.build(S.root, S);
    // resolve every name once, now: a typo in a mark or a scene window fails before the first frame, not mid-render
    const MARKS = T.resolveMarks();
    for (const S of SCENES) { at(S.from); at(S.to); }
    window.FPS = FPS; window.DURATION = DUR; window.FILM = { W, H, FMT };
    window.MARKS = MARKS;
    window.SCENE_TIMES = SCENES.map((S) => ({ name: S.name, from: at(S.from), to: at(S.to) }));
    window.CUTS = SCENES.filter((S) => (S.cut ?? S.pre === 0) && at(S.from) > 0).map((S) => at(S.from)).sort((a, b) => a - b);
    window.seek = (t) => paint(Math.max(0, Math.min(DUR - 1e-6, t)));
    window.READY = (async () => {
      await presetReady;
      // a missing face must be loud (the render logs [page] warnings) but not fatal: the stack falls back
      await Promise.all(C.fonts.map((f) => document.fonts.load(f).then((r) => { if (!r.length) console.warn(`font not loaded: ${f} (falling back)`); },
        () => console.warn(`font failed: ${f} — check the @font-face url in film/index.html (falling back)`))));
      await document.fonts.ready;
      const imgs = [...document.images];
      await Promise.all(imgs.map((i) => (i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))));
      await Promise.all(imgs.map((i) => i.decode().catch(() => 0)));
      window.seek(0);
      return true;
    })();

    // preview player (?play): NOT used in render mode. Click to play/pause, scaled to fit the window.
    if (qs.has('play')) {
      document.body.classList.add('play');
      const fit = () => { const k = Math.min(innerWidth / W, innerHeight / H); stage.style.transform = `scale(${k})`; };
      fit(); addEventListener('resize', fit);
      const audio = new Audio('../audio/mix.wav');      // optional: silent lessons simply have no file
      let playing = false, base = 0, started = 0;
      const now = () => performance.now() / 1000;
      const clock = () => (base + (playing ? now() - started : 0)) % DUR;
      document.body.addEventListener('click', () => {
        if (playing) { base = clock(); audio.pause(); } else { started = now(); audio.currentTime = base; audio.play().catch(() => {}); }
        playing = !playing;
      });
      const loop = () => { window.seek(clock()); requestAnimationFrame(loop); };
      window.READY.then(loop);
    }
  };
})();
