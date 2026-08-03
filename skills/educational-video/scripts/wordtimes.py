"""Word-level timing helpers shared by grid.py and align_subtitles.py.

A "word" is {"word": str, "start": float, "end": float} in seconds from the start of one
scene's audio. Timings come from the TTS provider, from forced alignment (faster-whisper), or,
as a last resort, from an estimate based on text length. Whatever the source, the words are
re-aligned to the narration text written in the storyboard so that anchors such as
"derivative#2" always refer to the words the author wrote.
"""
import difflib
import json
import os
import re
import subprocess
import sys

SENTENCE_END = re.compile(r"[.!?;:…]+[\"'”’)\]]*$")
_STRIP = re.compile(r"[^\w'-]+", re.UNICODE)

WORDS_PER_SECOND = 2.6      # estimate used when nothing better exists
SENTENCE_PAUSE_S = 0.28     # extra silence assumed after a sentence end


def norm(word):
    """Lowercase, punctuation stripped; keeps inner apostrophes and hyphens."""
    w = word.lower().replace("’", "'")
    w = _STRIP.sub("", w).replace("_", "")
    return w.strip("'-")


def tokenize(text):
    """Split narration into spoken tokens (whitespace separated, must contain a letter or digit)."""
    return [t for t in (text or "").split() if norm(t)]


def ends_sentence(token):
    return bool(SENTENCE_END.search(token))


def audio_duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, check=True).stdout.strip()
        return float(out)
    except Exception:  # noqa: BLE001
        return 0.0


def estimate_words(tokens, duration=None):
    """Spread tokens over time by character weight. Without duration, use a speaking rate."""
    if not tokens:
        return []
    weights = [max(2, len(norm(t))) + (6 if ends_sentence(t) else 0) for t in tokens]
    if duration is None:
        n = len(tokens)
        pauses = sum(1 for t in tokens if ends_sentence(t))
        duration = n / WORDS_PER_SECOND + pauses * SENTENCE_PAUSE_S
    total = float(sum(weights))
    out, t = [], 0.0
    for tok, w in zip(tokens, weights):
        span = duration * w / total
        speech = span * (0.78 if ends_sentence(tok) else 0.92)
        out.append({"word": tok, "start": round(t, 4), "end": round(t + speech, 4)})
        t += span
    return out


def align_to_text(tokens, heard):
    """Give every narration token a time, using the heard words as anchors.

    `heard` is a list of {"word","start","end"} (provider or ASR). Tokens that match a heard
    word (same normalised form, in order) take its timing; tokens in between are interpolated
    by character weight. Heard words that match nothing are dropped. Returns one entry per
    token, with the narration's own spelling.
    """
    if not tokens:
        return []
    heard = [h for h in heard if norm(h["word"])]
    if not heard:
        return estimate_words(tokens)
    a = [norm(t) for t in tokens]
    b = [norm(h["word"]) for h in heard]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    timed = [None] * len(tokens)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            h = heard[blk.b + k]
            timed[blk.a + k] = (float(h["start"]), float(h["end"]))
    if not any(timed):
        # nothing matched (heavy mis-hearing): squeeze the narration into the heard span
        span = (float(heard[0]["start"]), float(heard[-1]["end"]))
        est = estimate_words(tokens, span[1] - span[0])
        return [{"word": t, "start": round(span[0] + e["start"], 4),
                 "end": round(span[0] + e["end"], 4)} for t, e in zip(tokens, est)]
    i = 0
    while i < len(timed):
        if timed[i]:
            i += 1
            continue
        j = i
        while j < len(timed) and not timed[j]:
            j += 1
        # gap tokens i..j-1; lo/hi are the neighbouring timed words (or clamped ends)
        lo = timed[i - 1][1] if i > 0 else None
        hi = timed[j][0] if j < len(timed) else None
        if lo is None:   # leading gap: pack it just before the first timed word
            w = [max(2, len(a[k])) for k in range(i, j)]
            dur = min(hi, sum(w) * 0.07)
            lo = hi - dur
        if hi is None:   # trailing gap: pack it just after the last timed word
            w = [max(2, len(a[k])) for k in range(i, j)]
            hi = lo + sum(w) * 0.07
        hi = max(hi, lo)
        w = [max(2, len(a[k])) for k in range(i, j)]
        tot = float(sum(w))
        t = lo
        for k, wk in zip(range(i, j), w):
            span = (hi - lo) * wk / tot
            timed[k] = (t, t + span * 0.92)
            t += span
        i = j
    return [{"word": tok, "start": round(s, 4), "end": round(max(e, s + 0.02), 4)}
            for tok, (s, e) in zip(tokens, timed)]


def whisper_words(wav):
    """Force-align via faster-whisper (installed lazily). Returns [] if unavailable."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "faster-whisper"],
                           check=True, capture_output=True)
            from faster_whisper import WhisperModel
        except Exception as e:  # noqa: BLE001
            print(f"warning: faster-whisper unavailable ({e}); estimating word timings",
                  file=sys.stderr)
            return []
    try:
        import numpy as np
        # decode with ffmpeg ourselves: faster-whisper's bundled decoder breaks on some PyAV builds
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", wav, "-f", "f32le", "-ac", "1",
                              "-ar", "16000", "-"], capture_output=True, check=True).stdout
        audio = np.frombuffer(raw, dtype=np.float32)
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(audio, word_timestamps=True)
        return [{"word": w.word.strip(), "start": w.start, "end": w.end}
                for seg in segments for w in (seg.words or [])]
    except Exception as e:  # noqa: BLE001
        print(f"warning: forced alignment failed ({e}); estimating word timings", file=sys.stderr)
        return []


def scene_words(project, sid, text, use_asr=True):
    """Words for one scene, aligned to its narration text. Returns (words, source, duration).

    source: "provider" (audio/scene_<id>.words.json existed), "asr", "estimated".
    The result is cached in audio/scene_<id>.words.json when it came from ASR.
    """
    adir = os.path.join(project, "audio")
    wav = os.path.join(adir, f"scene_{sid}.wav")
    wjson = os.path.join(adir, f"scene_{sid}.words.json")
    tokens = tokenize(text)
    dur = audio_duration(wav) if os.path.isfile(wav) else 0.0
    fresh = os.path.isfile(wjson) and (not os.path.isfile(wav)
                                       or os.path.getmtime(wjson) >= os.path.getmtime(wav))
    if fresh:
        with open(wjson) as f:
            heard = json.load(f)
        return align_to_text(tokens, heard), "provider", dur
    if os.path.isfile(wav) and use_asr:
        heard = whisper_words(wav)
        if heard:
            with open(wjson, "w") as f:
                json.dump(heard, f)
            return align_to_text(tokens, heard), "asr", dur
    if os.path.isfile(wav):
        return estimate_words(tokens, dur), "estimated", dur
    return estimate_words(tokens), "estimated", 0.0
