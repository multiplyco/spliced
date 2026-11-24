# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["numpy", "scipy", "soundfile", "librosa"]
# ///
"""A film's sound, taken apart: voice, music and sound effects on separate lanes, on the music's beat grid.

For our own films the stems are known, so nothing is guessed:
  HyperFrames  every <audio> in videos/<slug>/index.html (the bed, each SFX hit, any voice-over) with its start,
               length and volume; the bed's edit plan (assets/*/plan-*.json, from build_bed.py) gives the
               source sections it was cut from and where they join.
  Remotion     remotion/src/films/<slug>/sound.json if the film declares its tracks (same shape as below),
               otherwise the newest full render's audio. Alternatives for a track (music sketches, voice takes) live in
               takes.json next to it (spliced film takes): the Sound panel auditions them under the picture, and Use
               writes the chosen file into sound.json, which changes this map's fingerprint so it is read again.
A finished mix only (a render, or any video with --video) is split with Demucs when asked (--separate): vocals
become the voice lane, drums + bass + other the music lane, and loud hits off the beat grid are listed as likely
sound effects (a guess: Demucs can't take effects out of the music).

On the music lane it finds the tempo, beats and bars, and sections (A, B, ...; intro, drop, break, outro by
energy). Everything goes to .cache/sound/<key>/sound.json with waveform peaks per lane, which Spliced's
Build view draws and plays (spliced open, Build, a film, Sound).

usage:
  spliced sound analyze <slug> [--separate] [--force]   # prints the cache path
  spliced sound show <slug>                              # the sound map as text, with open sound notes
  spliced sound analyze --video <file> [--separate]      # any video or audio file (e.g. a reference)
"""
import hashlib, json, os, re, subprocess, sys, warnings

import numpy as np

warnings.filterwarnings("ignore")
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import paths  # noqa: E402
import film  # noqa: E402  (stdlib only at import time)

ROOT = paths.ROOT
CACHE = paths.SOUND_CACHE
SR = 22050
PEAK_RATE = 50  # peaks per second
VERSION = 5


def rel(p):
    return os.path.relpath(p, ROOT)


# ---------- audio io ----------
def decode(path, sr=SR):
    """Mono float32 at sr, through ffmpeg (mp3, wav, mp4 all fine). None if the file has no audio."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True)
    if r.returncode or not r.stdout:
        return None
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def has_audio(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def render_lane(clips, dur, cache):
    """Mix a lane's clips (each at its start, from its offset, at its gain) into one mono buffer."""
    out = np.zeros(int(dur * SR) + SR, dtype=np.float32)
    for c in clips:
        y = cache.get(c["path"])
        if y is None:
            y = cache[c["path"]] = decode(c["path"])
        if y is None:
            continue
        a = int(c.get("offset", 0) * SR)
        n = int(c["dur"] * SR) if c.get("dur") else len(y) - a
        seg = y[a:a + n] * float(c.get("gain", 1.0))
        i = int(c["start"] * SR)
        if i >= len(out):
            continue
        seg = seg[: len(out) - i]
        out[i:i + len(seg)] += seg
    return out[: int(dur * SR)]


def peaks(y, rate=PEAK_RATE):
    """Peak per 1/rate s, 0..100 on a dB-ish scale (so quiet SFX still show)."""
    hop = SR // rate
    n = len(y) // hop
    if not n:
        return []
    m = np.abs(y[: n * hop]).reshape(n, hop).max(1)
    db = 20 * np.log10(m + 1e-6)
    return [int(v) for v in np.clip((db + 60) / 60 * 100, 0, 100)]


def db(x):
    return float(20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-9)) if len(x) else -120.0


# ---------- music: beats, bars, sections ----------
def beat_grid(y, bar_hints=()):
    import librosa
    if len(y) < SR * 2 or np.abs(y).max() < 1e-4:
        return None
    oenv = librosa.onset.onset_strength(y=y, sr=SR)
    tempo, beats = librosa.beat.beat_track(onset_envelope=oenv, sr=SR, units="time", trim=False)
    tempo = float(np.atleast_1d(tempo)[0])
    beats = np.asarray(beats, dtype=float)
    if tempo <= 0 or len(beats) < 4:
        return None
    period = float(np.median(np.diff(beats)))
    dur = len(y) / SR
    # fill gaps (quiet intros, breaks) and extend to both ends at the local period
    filled = [beats[0]]
    for b in beats[1:]:
        gap = b - filled[-1]
        k = int(round(gap / period))
        for j in range(1, k):
            filled.append(filled[-1] + gap / k)
        filled.append(b)
    beats = np.array(filled)
    head = np.arange(beats[0] - period, -period * 0.25, -period)[::-1]
    tail = np.arange(beats[-1] + period, dur + period * 0.25, period)
    beats = np.concatenate([head[head >= -0.02], beats, tail[tail <= dur]])
    beats = np.clip(beats, 0, dur)
    # downbeat: the phase (of 4) whose beats carry the most low-end onset energy
    import scipy.signal as ss
    lo = ss.sosfilt(ss.butter(4, 160, "low", fs=SR, output="sos"), y)
    lenv = librosa.onset.onset_strength(y=lo, sr=SR)
    frames = np.clip(librosa.time_to_frames(beats, sr=SR), 0, len(lenv) - 1)
    strength = lenv[frames]
    if len(bar_hints):  # known bar lines (a bed plan's cut points) decide the downbeat
        hints = np.array(bar_hints)
        phase = int(np.argmin([np.abs(hints[:, None] - beats[p::4][None, :]).min(1).sum() for p in range(4)]))
    else:
        phase = int(np.argmax([strength[p::4].sum() for p in range(4)]))
    bars = beats[phase::4]
    return {"bpm": round(60 / period, 2), "period": round(period, 4), "beats": [round(float(b), 4) for b in beats],
            "phase": phase, "bars": [round(float(b), 4) for b in bars]}


def music_sections(y, grid):
    """Sections on bar lines, lettered by similarity (A, B, A2 ...) and tagged by energy (intro, drop, break, outro)."""
    import librosa
    dur = len(y) / SR
    if not grid:
        return []
    hop = 512
    beats = np.array(grid["beats"])
    bf = librosa.time_to_frames(beats, sr=SR, hop_length=hop)
    C = librosa.feature.chroma_stft(y=y, sr=SR, hop_length=hop)
    M = librosa.feature.mfcc(y=y, sr=SR, n_mfcc=13, hop_length=hop)
    R = librosa.feature.rms(y=y, hop_length=hop)
    Cs, Ms, Rs = (librosa.util.sync(X, bf) for X in (C, M, R))
    Ms = (Ms - Ms.mean(1, keepdims=True)) / (Ms.std(1, keepdims=True) + 1e-9)
    F = np.vstack([librosa.util.normalize(Cs, axis=0), Ms * 0.5, np.log(Rs + 1e-6) * 2])
    starts = np.concatenate([[0.0], beats])[: F.shape[1]]
    k = int(np.clip(round(dur / 7), 3, 9))
    k = min(k, F.shape[1] - 1)
    if k < 2:
        return []
    idx = librosa.segment.agglomerative(F, k)
    bounds = sorted(set([0.0] + [float(starts[i]) for i in idx if i < len(starts)] + [dur]))
    bars = np.array(grid["bars"]) if grid["bars"] else beats
    snapped = [0.0]
    for b in bounds[1:-1]:
        s = float(bars[np.argmin(np.abs(bars - b))])
        if s - snapped[-1] >= grid["period"] * 3.5 and dur - s >= grid["period"] * 3.5:
            snapped.append(s)
    snapped.append(dur)
    secs = []
    for a, e in zip(snapped[:-1], snapped[1:]):
        m = (starts >= a - 1e-3) & (starts < e - 1e-3)
        feat = F[:, m].mean(1) if m.any() else F.mean(1)
        secs.append({"start": round(a, 3), "end": round(e, 3), "energy_db": round(db(y[int(a * SR):int(e * SR)]), 1), "_f": feat})
    # letters: greedy clustering on the section means
    letters, protos = [], []
    for s in secs:
        f = s["_f"] / (np.linalg.norm(s["_f"]) + 1e-9)
        sims = [float(f @ p) for p in protos]
        if sims and max(sims) > 0.93:
            letters.append(int(np.argmax(sims)))
        else:
            protos.append(f)
            letters.append(len(protos) - 1)
    seen = {}
    med = float(np.median([s["energy_db"] for s in secs]))
    for i, (s, L) in enumerate(zip(secs, letters)):
        seen[L] = seen.get(L, 0) + 1
        s["label"] = chr(65 + L) + (str(seen[L]) if seen[L] > 1 else "")
        prev = secs[i - 1]["energy_db"] if i else None
        tag = ""
        if i == 0 and s["energy_db"] < med - 3:
            tag = "intro"
        elif i == len(secs) - 1 and s["energy_db"] < med - 3:
            tag = "outro"
        elif prev is not None and s["energy_db"] - prev >= 3:
            tag = "drop"
        elif prev is not None and prev - s["energy_db"] >= 3:
            tag = "break"
        s["tag"] = tag
        s["id"] = f"m{i + 1}"
        del s["_f"]
    return secs


def bar_of(t, grid):
    """'bar 5 beat 3' for a time, and the offset (s) to the nearest beat."""
    if not grid:
        return None
    beats = np.array(grid["beats"])
    i = int(np.argmin(np.abs(beats - t)))
    bars = np.array(grid["bars"])
    bi = int(np.searchsorted(bars, beats[i] + 1e-3)) - 1  # bar index containing that beat (-1 = pickup)
    beat_in_bar = (i - grid["phase"]) % 4 + 1
    off = float(t - beats[i])
    # where it sits: on the beat, on the 8th or 16th between beats, or off the grid (within ~35ms)
    frac = off / grid["period"]
    where = "off grid"
    for q, name in ((0, "on the beat"), (0.5, "on the 8th"), (-0.5, "on the 8th"), (0.25, "on a 16th"), (-0.25, "on a 16th")):
        if abs(frac - q) * grid["period"] <= 0.035:
            where = name
            break
    return {"beat": i, "bar": bi + 1, "beat_in_bar": beat_in_bar, "offset": round(off, 4), "where": where}


# ---------- sources ----------
ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def lane_of(el_id, src):
    s = f"{el_id} {src}".lower()
    if re.search(r"\b(vo|voice|voiceover|narr|narration|tts|speech)\b|[-_/](vo|voice|narration|tts)[-_./]", s):
        return "voice"
    if re.search(r"bgm|music|bed|track", s) and "sfx" not in s:
        return "music"
    return "sfx"


def hf_tracks(d):
    html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    clips = []
    for tag in re.findall(r"<audio\s[^>]*>", html):
        a = dict(ATTR.findall(tag))
        src = a.get("src")
        if not src or "data-start" not in a:
            continue
        p = os.path.normpath(os.path.join(d, src))
        if not os.path.isfile(p):
            continue
        el = a.get("id") or os.path.basename(src)
        clips.append({"id": el, "lane": lane_of(el, src), "path": p, "file": rel(p), "name": os.path.splitext(os.path.basename(src))[0],
                      "start": float(a.get("data-start", 0)), "dur": float(a["data-duration"]) if a.get("data-duration") else None,
                      "offset": float(a.get("data-media-start", 0) or 0), "gain": float(a.get("data-volume", 1) or 1)})
    return clips


def bed_plan(d, bed_file):
    """The build_bed / edit_bed plan whose output is this bed, if any."""
    for dp, dn, fn in os.walk(os.path.join(d, "assets")):
        for f in fn:
            if f.startswith("plan") and f.endswith(".json"):
                p = os.path.join(dp, f)
                j = film.load_json(p)
                if isinstance(j, dict) and j.get("out") and os.path.basename(j["out"]) == os.path.basename(bed_file):
                    j["_path"] = rel(p)
                    return j
    return None


def plan_info(plan):
    if not plan:
        return None
    out = {"file": plan["_path"], "source": plan.get("src", ""), "pieces": [], "joins": [], "lift": plan.get("lift", []),
           "dips": [[a, b] for a, b, *_ in plan.get("dips", [])], "fade_out": plan.get("fade_out")}
    if plan.get("pieces"):
        for i, (sa, sb, da, dbb) in enumerate(plan["pieces"]):
            out["pieces"].append({"n": i + 1, "src": [sa, sb], "dst": [da, dbb], "stretch": round((sb - sa) / max(1e-6, dbb - da), 4)})
            if i:
                prev = plan["pieces"][i - 1]
                jump = round(sa - prev[1], 3)
                out["joins"].append({"t": da, "from": prev[1], "to": sa, "jump": jump, "seamless": abs(jump) < 0.01})
    elif plan.get("edits"):
        for i, (sa, sb, da, xf) in enumerate(plan["edits"]):
            out["pieces"].append({"n": i + 1, "src": [sa, sb], "dst": [da, da + (sb - sa)], "stretch": 1.0, "xfade": xf})
            if i:
                out["joins"].append({"t": da, "from": plan["edits"][i - 1][1], "to": sa, "xfade": xf})
    return out


def full_render(p):
    for r in p["renders"]:
        if not r.get("beat") and not (r.get("span") and r["span"][0] > 0.05):
            return paths.abspath(r["file"])
    return None


# ---------- separation (Demucs, in its own environment) ----------
def separate(wav, outdir):
    """vocals / drums / bass / other stems with htdemucs. Returns {stem: path} or raises with the reason."""
    os.makedirs(outdir, exist_ok=True)
    stems = {s: os.path.join(outdir, f"{s}.wav") for s in ("vocals", "drums", "bass", "other")}
    if all(os.path.exists(p) for p in stems.values()):
        return stems
    code = (
        "import sys, numpy as np, soundfile as sf, torch\n"
        "from demucs.pretrained import get_model\nfrom demucs.apply import apply_model\n"
        "m = get_model('htdemucs'); m.eval()\n"
        "x, sr = sf.read(sys.argv[1], dtype='float32', always_2d=True)\n"
        "assert sr == m.samplerate, sr\n"
        "w = torch.from_numpy(x.T.copy())\nref = w.mean(0)\nw = (w - ref.mean()) / (ref.std() + 1e-8)\n"
        "dev = 'mps' if torch.backends.mps.is_available() else 'cpu'\n"
        "with torch.no_grad(): out = apply_model(m, w[None], device=dev, split=True, overlap=0.25, progress=False)[0]\n"
        "out = out * (ref.std() + 1e-8) + ref.mean()\n"
        "for name, s in zip(m.sources, out): sf.write(f'{sys.argv[2]}/{name}.wav', s.cpu().numpy().T, sr)\n"
    )
    r = subprocess.run(["uv", "run", "--quiet", "--python", "3.12", "--with", "demucs", "--with", "soundfile", "python", "-c", code, wav, outdir],
                       capture_output=True, text=True)
    if r.returncode or not all(os.path.exists(p) for p in stems.values()):
        raise RuntimeError("Demucs failed: " + (r.stderr.strip().splitlines() or ["no output"])[-1])
    return stems


# ---------- analysis ----------
def key_for(slug=None, video=None):
    if slug:
        return slug
    return "file-" + hashlib.sha1(os.path.abspath(video).encode()).hexdigest()[:10]


def fingerprint(paths, extra=""):
    h = hashlib.sha1(f"v{VERSION}|{extra}".encode())
    for p in sorted(set(paths)):
        if os.path.exists(p):
            st = os.stat(p)
            h.update(f"{p}|{st.st_mtime}|{st.st_size}".encode())
    return h.hexdigest()[:16]


def analyze_mix(path, out, dur, want_sep, notes):
    """A finished mix: one 'mix' lane, or voice / music / hits when separated."""
    lanes, cache = [], {}
    if not has_audio(path):
        notes.append(f"{os.path.basename(path)} has no audio track: render with sound to work on it here.")
        return lanes, None, [], {"no_audio": True}
    mix = decode(path)
    dur = dur or len(mix) / SR
    sep = {}
    if want_sep:
        wav = os.path.join(out, "mix-44k.wav")
        if not os.path.exists(wav):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vn", "-ac", "2", "-ar", "44100", wav], check=True)
        try:
            sep = separate(wav, os.path.join(out, "stems"))
        except Exception as e:  # report, fall back to the mix
            notes.append(str(e))
    if sep:
        music_path = os.path.join(out, "stems", "music.wav")
        if not os.path.exists(music_path):
            import soundfile as sf
            parts = [sf.read(sep[s], dtype="float32", always_2d=True) for s in ("drums", "bass", "other")]
            sf.write(music_path, sum(p[0] for p in parts), parts[0][1])
        voice = decode(sep["vocals"])
        music = decode(music_path)
        if db(voice) > -45:
            lanes.append({"id": "voice", "label": "Voice", "kind": "voice", "clips": [{"id": "voice", "file": rel(sep["vocals"]), "name": "vocals (separated)", "start": 0, "dur": dur, "offset": 0, "gain": 1}], "peaks": peaks(voice)})
        lanes.append({"id": "music", "label": "Music", "kind": "music", "clips": [{"id": "music", "file": rel(music_path), "name": "drums + bass + other (separated)", "start": 0, "dur": dur, "offset": 0, "gain": 1}], "peaks": peaks(music)})
        return lanes, music, [], {"separated": True}
    lanes.append({"id": "mix", "label": "Mix", "kind": "music", "clips": [{"id": "mix", "file": rel(path), "name": os.path.basename(path), "start": 0, "dur": dur, "offset": 0, "gain": 1}], "peaks": peaks(mix)})
    return lanes, mix, [], {"separated": False}


def likely_hits(y, grid, music_sections_):
    """Loud transients off the beat grid in a separated music stem: probably sound effects."""
    import librosa
    if y is None or not grid:
        return []
    env = librosa.onset.onset_strength(y=y, sr=SR)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=SR, units="frames", delta=0.25)
    if not len(on):
        return []
    strength = env[on]
    thr = np.percentile(strength, 85)
    beats = np.array(grid["beats"])
    hits = []
    for f, s in zip(on, strength):
        t = float(librosa.frames_to_time(f, sr=SR))
        off = float(np.min(np.abs(beats - t))) if len(beats) else 1
        if s >= thr and off > 0.07:
            hits.append({"id": f"hit-{len(hits) + 1}", "name": "hit", "t": round(t, 3), "dur": 0.25, "gain": 1, "guess": True})
    return hits[:80]


def analyze(slug=None, video=None, want_sep=False, force=False):
    key = key_for(slug, video)
    out = os.path.join(CACHE, key)
    os.makedirs(out, exist_ok=True)
    notes, lanes, plan, src_desc = [], [], None, ""
    p = film.production(slug) if slug else None
    if slug and not p:
        raise SystemExit(f"no film called {slug} ({paths.CLI} film list)")
    dur = p["duration"] if p else None
    inputs = []
    clips = []
    if p and p["engine"] == "hyperframes":
        d = os.path.join(ROOT, p["dir"])
        clips = hf_tracks(d)
        inputs = [os.path.join(d, "index.html")] + [c["path"] for c in clips]
        inputs += [os.path.join(dp, f) for dp, _, fn in os.walk(os.path.join(d, "assets")) for f in fn if f.startswith("plan") and f.endswith(".json")]
        src_desc = "stems from index.html"
    elif p and p["engine"] == "remotion":
        d = os.path.join(ROOT, p["dir"])
        decl = film.load_json(os.path.join(d, "sound.json"))
        if decl and decl.get("tracks"):
            for t in decl["tracks"]:
                path = os.path.normpath(os.path.join(d, t["file"])) if not t["file"].startswith(("remotion/", "videos/", "music/")) else os.path.join(ROOT, t["file"])
                clips.append({"id": t.get("id") or os.path.basename(t["file"]), "lane": t.get("lane") or lane_of(t.get("id", ""), t["file"]), "path": path, "file": rel(path),
                              "name": t.get("name") or os.path.splitext(os.path.basename(t["file"]))[0], "start": float(t.get("start", 0)),
                              "dur": t.get("dur"), "offset": float(t.get("offset", 0)), "gain": float(t.get("gain", 1))})
            inputs = [os.path.join(d, "sound.json")] + [c["path"] for c in clips]
            src_desc = "stems from sound.json"
    mix_path = None
    if not clips:
        mix_path = video or (full_render(p) if p else None)
        if not mix_path:
            raise SystemExit("nothing to analyse: no declared tracks and no full render")
        inputs = [mix_path]
        src_desc = f"mix of {os.path.basename(mix_path)}" + (" (separated)" if want_sep else "")
    fp = fingerprint(inputs, f"sep={want_sep}")
    jp = os.path.join(out, "sound.json")
    old = film.load_json(jp)
    if old and old.get("fingerprint") == fp and not force:
        return jp
    cache, music_y, hits, meta = {}, None, [], {}
    if clips:
        for c in clips:
            if not c["dur"]:
                y = cache.setdefault(c["path"], decode(c["path"]))
                c["dur"] = round(len(y) / SR - c["offset"], 3) if y is not None else 0
        dur = dur or max(c["start"] + c["dur"] for c in clips)
        for lid, label in (("voice", "Voice"), ("music", "Music"), ("sfx", "Sound effects")):
            cs = [c for c in clips if c["lane"] == lid]
            if not cs:
                continue
            y = render_lane(cs, dur, cache)
            if lid == "music":
                music_y = y
            lanes.append({"id": lid, "label": label, "kind": lid, "peaks": peaks(y),
                          "clips": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items() if k not in ("path", "lane")} for c in cs]})
        bed = next((c for c in clips if c["lane"] == "music"), None)
        if bed and p and p["engine"] == "hyperframes":
            plan = plan_info(bed_plan(os.path.join(ROOT, p["dir"]), bed["file"]))
    else:
        lanes, music_y, hits, meta = analyze_mix(mix_path, out, dur, want_sep, notes)
        if music_y is not None:
            dur = dur or len(music_y) / SR
    hints = [pc["dst"][0] for pc in plan["pieces"]] + [pc["dst"][1] for pc in plan["pieces"]] if plan else []
    grid = beat_grid(music_y, hints) if music_y is not None else None
    secs = music_sections(music_y, grid) if grid else []
    if meta.get("separated"):
        hits = likely_hits(music_y, grid, secs)
        if hits:
            lanes.append({"id": "hits", "label": "Likely sound effects", "kind": "sfx", "guess": True, "peaks": [], "clips": [],
                          "events": hits})
    for ln in lanes:
        if ln["kind"] == "sfx" and not ln.get("events"):
            ln["events"] = [{"id": c["id"], "name": c["name"], "file": c["file"], "t": c["start"], "dur": c["dur"], "gain": c["gain"]} for c in ln["clips"]]
        for ev in ln.get("events", []):
            ev["grid"] = bar_of(ev["t"], grid)
    for s in secs:
        s["bars"] = [bar_of(s["start"], grid)["bar"], bar_of(max(s["start"], s["end"] - 0.01), grid)["bar"]] if grid else None
    if not grid and music_y is not None:
        notes.append("No steady beat found in the music.")
    res = {
        "version": VERSION, "fingerprint": fp, "key": key, "slug": slug, "video": rel(video) if video else None,
        "source": src_desc, "duration": round(float(dur or 0), 3), "peak_rate": PEAK_RATE,
        "separated": bool(meta.get("separated")), "can_separate": not clips and not meta.get("no_audio"),
        "tempo": grid, "sections": secs, "plan": plan, "lanes": lanes, "notes": notes,
    }
    film.write_json(jp, res)
    return jp


# ---------- text ----------
def cmd_show(slug):
    jp = analyze(slug)
    s = film.load_json(jp)
    t = film.fmt_t
    print(f"# Sound: {slug}  ({s['source']}, {t(s['duration'])})")
    g = s["tempo"]
    print(f"Tempo: {g['bpm']} bpm, beat {g['period']}s, {len(g['bars'])} bars, bar 1 at {t(g['bars'][0])}" if g else "Tempo: no steady beat")
    for n in s["notes"]:
        print("! " + n)
    if s["sections"]:
        print("\nMusic sections:")
        for x in s["sections"]:
            print(f"  {x['label']:<4} {t(x['start'])}-{t(x['end'])}  bars {x['bars'][0]}-{x['bars'][1]}  {x['energy_db']:>6.1f} dB  {x['tag']}")
    if s["plan"]:
        print(f"\nBed plan {s['plan']['file']} (source {s['plan']['source']}):")
        for pc in s["plan"]["pieces"]:
            print(f"  piece {pc['n']}: source {t(pc['src'][0])}-{t(pc['src'][1])} -> film {t(pc['dst'][0])}-{t(pc['dst'][1])}  stretch {pc['stretch']}")
        for j in s["plan"]["joins"]:
            print(f"  join at {t(j['t'])}: " + ("seamless (same source time)" if j.get("seamless") else f"source jumps {t(j['from'])} -> {t(j['to'])}"))
    for ln in s["lanes"]:
        if ln.get("events"):
            print(f"\n{ln['label']} ({len(ln['events'])}):")
            for e in ln["events"]:
                gr = e.get("grid")
                pos = f"bar {gr['bar']} beat {gr['beat_in_bar']} {gr['offset'] * 1000:+.0f}ms, {gr['where']}" if gr else ""
                print(f"  {t(e['t'])}  {e['name']:<16} {e['id']:<12} {pos}")
        else:
            print(f"\n{ln['label']}: " + ", ".join(f"{c['name']} {t(c['start'])}-{t(c['start'] + (c['dur'] or 0))}" for c in ln["clips"]))
    p = film.production(slug)
    sn = film.sound_notes(slug) if p else {}
    open_ = [(k, v) for k, v in sn.items() if v.get("note")]
    if open_:
        print("\nOpen sound notes:")
        for k, v in open_:
            print(f"  [{k}] {v.get('label', '')}: {v['note']}")


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("analyze", "show"):
        sys.exit(__doc__)
    if a[0] == "show":
        return cmd_show(a[1])
    video = a[a.index("--video") + 1] if "--video" in a else None
    slug = None if video else next((x for x in a[1:] if not x.startswith("--")), None)
    print(analyze(slug=slug, video=video, want_sep="--separate" in a, force="--force" in a))


if __name__ == "__main__":
    main()
