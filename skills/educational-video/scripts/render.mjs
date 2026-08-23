#!/usr/bin/env node
// Render a motion-engine lesson: drives window.seek(t) in headless Chromium and pipes frames to ffmpeg.
//   node render.mjs [--project <dir>] <mode> [options]        (--project defaults to the current directory)
//
//   --sheet [--every 1] [--phase 0.25] [--marks] [--fmt 9x16]   contact sheet, one labelled frame per second (or per mark)
//                                                              → review/sheets/sheet_<fmt>.jpg (+ _phone.jpg at 360 px wide tiles)
//   --at 1.2,3.4 [--fmt 1x1]                                    stills → review/stills/<fmt>/t<sec>.png
//   --draft [--all]                                             30 fps, no blur, CRF 22 → renders/draft_<fmt>.mp4 (review rounds)
//   [--fmt 16x9 | --all]                                        final: 60 fps, adaptive 180° motion blur, H.264 yuv420p CRF 16 → renders/<fmt>.mp4
//   --range 3,5 | --scene 02 [--blur 0]                         a clip: seconds 3-5, or one scene by storyboard id
//   --mux [--all]                                               re-mux audio/mix.wav into existing renders without re-rendering
//   --verify [--all]                                            determinism check: 12 probes, cold vs after seeking elsewhere
//   options: --tag name (output prefix)  --fps N  --blur 0|1 (default 1 for finals)  --crf N  --audio path (default audio/mix.wav if present)  --out file
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';

const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf(`--${k}`); return i < 0 ? d : (argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : true); };
const has = (k) => argv.includes(`--${k}`);
const die = (m) => { console.error(`render: ${m}`); process.exit(1); };

const ROOT = path.resolve(String(opt('project', process.cwd())));
if (!fs.existsSync(path.join(ROOT, 'timeline.json')) || !fs.existsSync(path.join(ROOT, 'film/index.html'))) {
  die(`${ROOT} is not a motion project (no timeline.json / film/index.html). Create one with scripts/scaffold_motion.sh`);
}
if (!fs.existsSync(path.join(ROOT, 'film/data.js'))) die('film/data.js is missing: run scripts/sync.mjs first');

let chromium;
for (const base of [path.join(ROOT, 'package.json'), path.join(process.cwd(), 'package.json'), import.meta.url]) {
  try { ({ chromium } = createRequire(base)('playwright')); break; } catch { /* try the next place */ }
}
if (!chromium) die(`playwright not found from ${ROOT}. Run: (cd ${ROOT} && npm i -D playwright && npx playwright install chromium)`);

const TL = JSON.parse(fs.readFileSync(path.join(ROOT, 'timeline.json'), 'utf8'));
const SIZES = { '16x9': [1920, 1080], '1x1': [1080, 1080], '4x5': [1080, 1350], '9x16': [1080, 1920] };
const ALL = TL.formats || ['16x9'];
const FORMATS = has('all') ? ALL : [opt('fmt', ALL[0])];
for (const f of FORMATS) if (!SIZES[f]) die(`unknown format "${f}" (use ${Object.keys(SIZES).join(', ')})`);
const DRAFT = has('draft');
const TAG = String(opt('tag', DRAFT ? 'draft' : '')).replace(/[^\w-]/g, '') ;   // output name prefix: renders/<tag>_<fmt>.mp4
const AUDIO = path.resolve(ROOT, String(opt('audio', 'audio/mix.wav')));
const hasAudio = fs.existsSync(AUDIO);
const mkdir = (d) => fs.mkdirSync(d, { recursive: true });
const rel = (p) => path.relative(ROOT, p);
const run = (cmd, a) => { const r = spawnSync(cmd, a, { stdio: ['ignore', 'inherit', 'pipe'] }); if (r.status) throw new Error(`${cmd} failed: ${r.stderr}`); return r; };

// ------------------------------------------------------------------ --mux: new mix into existing renders, video untouched
if (has('mux')) {
  if (!hasAudio) die(`no audio at ${AUDIO}`);
  for (const fmt of FORMATS) {
    const src = path.join(ROOT, `renders/${fmt}.mp4`), tmp = src + '.tmp.mp4';
    if (!fs.existsSync(src)) die(`no render to mux into: ${rel(src)} (render it first)`);
    run('ffmpeg', ['-y', '-loglevel', 'error', '-i', src, '-i', AUDIO, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k', '-shortest', '-movflags', '+faststart', tmp]);
    fs.renameSync(tmp, src); console.log('muxed', rel(src));
  }
  process.exit(0);
}

// ------------------------------------------------------------------ static server (the film fetches nothing; data.js is generated)
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.otf': 'font/otf', '.wav': 'audio/wav', '.mp4': 'video/mp4' };
const server = http.createServer((req, res) => {
  const f = path.resolve(ROOT, '.' + decodeURIComponent(req.url.split('?')[0]));
  if (!f.startsWith(ROOT + path.sep) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const browser = await chromium.launch({ args: ['--force-color-profile=srgb', '--disable-lcd-text', '--font-render-hinting=none', '--disable-gpu-vsync'] });
const quit = async (code) => { await browser.close().catch(() => {}); server.closeAllConnections(); server.close(); process.exit(code); };

// minimal PNG decoder (8-bit RGB/RGBA, non-interlaced) → packed RGB
function decodePNG(buf) {
  let p = 8, w = 0, h = 0, ct = 0; const idat = [];
  while (p < buf.length) {
    const len = buf.readUInt32BE(p), type = buf.toString('ascii', p + 4, p + 8), data = buf.subarray(p + 8, p + 8 + len);
    if (type === 'IHDR') { w = data.readUInt32BE(0); h = data.readUInt32BE(4); ct = data[9]; if (data[8] !== 8 || data[12] !== 0) throw new Error('unsupported PNG'); }
    else if (type === 'IDAT') idat.push(data); else if (type === 'IEND') break;
    p += 12 + len;
  }
  const bpp = ct === 6 ? 4 : ct === 2 ? 3 : (() => { throw new Error('PNG colour type ' + ct); })();
  const raw = zlib.inflateSync(Buffer.concat(idat)), stride = w * bpp, cur = Buffer.alloc(stride), prev = Buffer.alloc(stride);
  const out = new Uint8Array(w * h * 3);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], row = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let x = 0; x < stride; x++) {
      const A = x >= bpp ? cur[x - bpp] : 0, B = prev[x], Cc = x >= bpp ? prev[x - bpp] : 0; let v = row[x];
      if (f === 1) v += A; else if (f === 2) v += B; else if (f === 3) v += (A + B) >> 1;
      else if (f === 4) { const pp = A + B - Cc, pa = Math.abs(pp - A), pb = Math.abs(pp - B), pc = Math.abs(pp - Cc); v += pa <= pb && pa <= pc ? A : pb <= pc ? B : Cc; }
      cur[x] = v & 255;
    }
    for (let x = 0, o = y * w * 3; x < w; x++, o += 3) { const q = x * bpp; out[o] = cur[q]; out[o + 1] = cur[q + 1]; out[o + 2] = cur[q + 2]; }
    cur.copy(prev);
  }
  return out;
}

async function openFilm(fmt) {
  const [W, H] = SIZES[fmt];
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.text()); });
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/film/index.html?fmt=${fmt}`);
  // a script error (unknown cue, typo in film.js) means window.READY never exists: fail with the message, not a timeout
  const ready = await Promise.race([
    page.waitForFunction(() => window.READY, null, { timeout: 120000 }).then(() => page.evaluate(() => window.READY)),
    new Promise((r) => { const i = setInterval(() => { if (errors.length) { clearInterval(i); r(false); } }, 50); }),
  ]);
  if (!ready || errors.length) { console.error(`render: the film failed to load (${fmt}):\n  ${errors.join('\n  ') || 'READY never resolved'}`); await quit(1); }
  const cdp = await page.context().newCDPSession(page);
  const info = await page.evaluate(() => ({ DUR: window.DURATION, FPS: window.FPS, CUTS: window.CUTS || [], MARKS: window.MARKS || {}, SCENES: window.SCENE_TIMES || [] }));
  // Headless Chromium now and then refuses a capture ("Unable to capture screenshot") or never answers it: every capture
  // has a deadline, and a retry goes through Playwright's own screenshot, which re-activates the page first.
  const timed = (promise, ms, what) => new Promise((resolve, reject) => {
    const to = setTimeout(() => reject(new Error(`${what} timed out after ${ms / 1000}s`)), ms);
    promise.then((v) => { clearTimeout(to); resolve(v); }, (e) => { clearTimeout(to); reject(e); });
  });
  const shot = async () => {
    for (let attempt = 1; ; attempt++) {
      try {
        if (attempt === 1) return Buffer.from((await timed(cdp.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true }), 15000, 'screenshot')).data, 'base64');
        await page.bringToFront();
        return await page.screenshot({ type: 'png', timeout: 30000 });
      } catch (e) {
        if (attempt >= 4) throw e;
        console.warn(`[render] capture retry ${attempt}: ${e.message}`);
        await new Promise((r) => setTimeout(r, 200 * attempt));
      }
    }
  };
  const png = async (t) => {
    await page.evaluate((t) => window.seek(t), t);
    return shot();
  };
  // a stamped copy of frame t for contact sheets: the stamp is added after painting and removed again, never rendered into video
  const pngLabeled = async (t, text) => {
    await page.evaluate(([t, text, fs]) => {
      window.seek(t);
      const d = document.createElement('div'); d.id = '__stamp'; d.textContent = text;
      d.style.cssText = `position:absolute;left:0;top:0;z-index:99999;padding:${fs * 0.15}px ${fs * 0.4}px;font:700 ${fs}px monospace;color:#fff;background:rgba(0,0,0,.72)`;
      document.getElementById('stage').appendChild(d);
    }, [t, text, Math.round(W / 26)]);
    const buf = await shot();
    await page.evaluate(() => document.getElementById('__stamp').remove());
    return buf;
  };
  return { page, png, pngLabeled, W, H, ...info };
}

function ffmpeg(a) {
  const p = spawn('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...a], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((ok, bad) => p.on('close', (c) => (c ? bad(new Error(`ffmpeg exit ${c}`)) : ok())));
  return { p, done };
}
const write = async (s, buf) => { if (!s.write(buf)) await new Promise((r) => s.once('drain', r)); };

for (const fmt of FORMATS) {
  const F = await openFilm(fmt);
  const t0 = Date.now();

  if (has('sheet')) {
    // one labelled frame per `every` seconds (or per mark with --marks), a little after the moment so the reaction is visible
    let times;
    if (has('marks')) {
      const lag = +opt('lag', 0.3);
      times = [...new Set(Object.values(F.MARKS).map((t) => +Math.min(F.DUR - 1 / F.FPS, t + lag).toFixed(3)))].sort((a, b) => a - b);
    } else {
      const every = +opt('every', 1), phase = +opt('phase', 0.25);
      times = [];
      for (let t = phase * every; t < F.DUR - 0.5 / F.FPS; t += every) times.push(+t.toFixed(3));
    }
    const dir = path.join(ROOT, 'review/sheets', fmt); mkdir(dir);
    for (const f of fs.readdirSync(dir)) fs.unlinkSync(path.join(dir, f));
    for (let i = 0; i < times.length; i++) fs.writeFileSync(path.join(dir, `f${String(i).padStart(3, '0')}.png`), await F.pngLabeled(times[i], `${times[i].toFixed(2)}s`));
    fs.writeFileSync(path.join(dir, 'times.json'), JSON.stringify(times));
    const wide = F.W >= F.H;
    for (const [tag, tw] of [['', wide ? 480 : 270], ['_phone', 360]]) {
      const th = Math.round(tw * F.H / F.W / 2) * 2, c = wide ? 4 : (tag ? 5 : 6), r = Math.ceil(times.length / c);
      const out = path.join(ROOT, `review/sheets/sheet_${fmt}${tag}.jpg`);
      run('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', '1', '-i', path.join(dir, 'f%03d.png'), '-vf', `scale=${tw}:${th}:flags=lanczos,tile=${c}x${r}:padding=6:color=0x202020`, '-frames:v', '1', '-q:v', '3', out]);
      console.log('wrote', rel(out), `(${times.length} frames, ${r} rows)`);
    }
  } else if (has('verify')) {
    // determinism: every probe time must paint identical pixels cold and after seeking elsewhere (in any order)
    const probes = Array.from({ length: 12 }, (_, i) => +((i + 0.37) * F.DUR / 12).toFixed(3));
    const cold = [];
    for (const t of probes) cold.push(decodePNG(await F.png(t)));
    let bad = 0;
    for (let k = probes.length - 1; k >= 0; k--) {
      await F.png(probes[(k * 7 + 3) % probes.length]);                // disturb: seek somewhere else first
      const again = decodePNG(await F.png(probes[k]));
      let d = 0; for (let q = 0; q < again.length; q += 13) d = Math.max(d, Math.abs(again[q] - cold[k][q]));
      if (d > 2) { bad++; console.log(`NOT DETERMINISTIC at t=${probes[k]}s (max pixel diff ${d})`); }
    }
    console.log(bad ? `${bad}/${probes.length} probes differ: state is leaking between frames` : `deterministic: ${probes.length}/${probes.length} probes identical (${fmt})`);
    if (bad) process.exitCode = 1;
  } else if (has('at')) {
    const dir = path.join(ROOT, 'review/stills', fmt); mkdir(dir);
    for (const t of String(opt('at', '0')).split(',').map(Number)) {
      const f = path.join(dir, `t${t.toFixed(3)}.png`); fs.writeFileSync(f, await F.png(t)); console.log('wrote', rel(f));
    }
  } else {
    const fps = +opt('fps', DRAFT ? 30 : F.FPS);
    const blur = !DRAFT && String(opt('blur', '1')) !== '0';
    let a = 0, b = F.DUR, tag = '';
    if (has('range')) { [a, b] = String(opt('range')).split(',').map(Number); tag = `clip_${fmt}_${a}-${b}`; }
    if (has('scene')) {
      const id = String(opt('scene'));
      const S = F.SCENES.find((s) => [id, `s${id}`, `scene_${id}`].includes(s.name));
      if (!S) { console.error(`render: no scene "${id}" in the film (scenes: ${F.SCENES.map((s) => s.name).join(', ')})`); await quit(1); }
      a = S.from; b = Math.min(S.to, F.DUR); tag = `scene_${id}_${fmt}`;
    }
    if (!(b > a) || a < 0 || b > F.DUR + 1e-6) { console.error(`render: bad range ${a}-${b} (film is 0-${F.DUR}s)`); await quit(1); }
    const clip = has('range') || has('scene');
    const out = path.resolve(ROOT, String(opt('out', path.join('renders', clip ? `${tag}.mp4` : `${TAG ? TAG + '_' : ''}${fmt}.mp4`))));
    mkdir(path.dirname(out));
    const withAudio = hasAudio;
    const { p, done } = ffmpeg([
      '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', `${F.W}x${F.H}`, '-framerate', String(fps), '-probesize', '100M', '-i', '-',
      ...(withAudio ? ['-ss', String(a), '-t', String(b - a), '-i', AUDIO] : []),
      '-c:v', 'libx264', '-preset', DRAFT ? 'veryfast' : 'slow', '-crf', String(opt('crf', DRAFT ? 22 : 16)), '-pix_fmt', 'yuv420p', '-profile:v', 'high',
      '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
      ...(withAudio ? ['-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '320k', '-shortest'] : []),
      '-movflags', '+faststart', out,
    ]);
    // Adaptive 180° motion blur: each frame is probed at two shutter points; the mean pixel difference sets how many
    // sub-frames to average (2 when static → 24 on the fastest moves). Sub-frames sit symmetrically around the frame
    // time and never straddle a hard cut (window.CUTS), so a cut is never double-exposed.
    const SHUTTER = 0.5, MIN_SUB = 2, MAX_SUB = 24;
    const clampCut = (tc, ts) => {
      for (const c of F.CUTS) {
        if (tc < c && ts >= c) return c - 1e-4;
        if (ts < c && tc >= c) return c;
      }
      return ts;
    };
    const at = (tc, u) => clampCut(tc, Math.max(0, Math.min(F.DUR - 1e-6, tc + (u - 0.5) * SHUTTER / fps)));
    const N = Math.round((b - a) * fps), acc = new Float32Array(F.W * F.H * 3), buf = Buffer.alloc(F.W * F.H * 3), hist = {};
    for (let i = 0; i < N; i++) {
      const tc = a + i / fps;
      if (!blur) { await write(p.stdin, Buffer.from(decodePNG(await F.png(tc)))); }
      else {
        const x = decodePNG(await F.png(at(tc, 0.25))), y = decodePNG(await F.png(at(tc, 0.75)));
        let d = 0; for (let q = 0; q < x.length; q += 97) d += Math.abs(x[q] - y[q]); d /= x.length / 97;
        const SUB = d < 0.35 ? MIN_SUB : Math.min(MAX_SUB, Math.max(4, Math.round(4 + d * 1.6)));
        hist[SUB] = (hist[SUB] || 0) + 1;
        acc.fill(0);
        const add = (im) => { for (let q = 0; q < acc.length; q++) acc[q] += im[q]; };
        if (SUB === 2) { add(x); add(y); } else for (let k = 0; k < SUB; k++) add(decodePNG(await F.png(at(tc, (k + 0.5) / SUB))));
        for (let q = 0; q < acc.length; q++) buf[q] = Math.min(255, Math.round(acc[q] / SUB));
        await write(p.stdin, buf);
      }
      if (i % 60 === 0) process.stdout.write(`${process.stdout.isTTY ? '\r' : ''}${fmt} frame ${i}/${N}  ${((Date.now() - t0) / 1000).toFixed(0)}s${process.stdout.isTTY ? '   ' : '\n'}`);
    }
    p.stdin.end(); await done;
    console.log(`${process.stdout.isTTY ? '\n' : ''}wrote ${rel(out)}  ${N} frames @ ${fps} fps${blur ? '  sub-frames ' + JSON.stringify(hist) : ''}${withAudio ? '  + ' + rel(AUDIO) : '  (silent)'}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  await F.page.close();
}
await quit(process.exitCode || 0);
