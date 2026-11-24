# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["librosa", "numpy", "scipy", "soundfile"]
# ///
"""A Remotion film's sound, from takes to mix: the score arranged from stems to the cuts, and the UI sounds on the cues.

The process (the film kit's docs/SOUND.md has the whole recipe):

  spliced soundkit takes <slug>    # every music take in audio/takes/: length, tempo, brightness, vocals; splits stems
  spliced soundkit score <slug>    # arranges every take to the picture (cues.json music), writes takes.json + music lane
  spliced soundkit sfx <slug>      # places the film's UI sounds (sound_events.py) from the shared kit, writes the sfx lane
  spliced soundkit loudness <file> # integrated loudness of a render (aim for about -16 LUFS)

Files, per film (remotion/src/films/<slug>/ and remotion/public/films/<slug>/audio/):
  audio/takes/<id>.mp3        ElevenLabs Music takes (record prompt, model and credits in assets.json)
  audio/stems/<id>/*.wav      their Demucs stems (drums, bass, other, vocals), made by `takes`
  cues.json `music`           anchor (film s where the take's first hit lands), fade, rms (level), take (the chosen id),
                              arrangement (when each stem comes in and out), takes (id, name, note, arranged)
  sound_events.py             events(C, h): the film's UI sounds, from its own cues (one function per film)
  sound.json, takes.json      written here; Remotion plays sound.json (lib/sound.tsx), the Build view reads both

The shared kit (remotion/public/audio/kit/, kit.json): crisp phone-keyboard keys, a tactile tap, soft pops, crisp ticks,
thuds, slides, air and a soft pass-by, each kind with its level and brightness. Every film starts from the same sounds.
"""
import importlib.util, json, os, subprocess, sys, zlib

import numpy as np, librosa, soundfile as sf
from scipy.signal import butter, sosfilt

import paths

ROOT = paths.ROOT
PUB = paths.PUBLIC
FILMS = paths.FILMS
KIT = os.path.join(PUB, "audio", "kit")
SR, FPS = 48000, 30
rel = lambda p: os.path.relpath(p, ROOT)
db = lambda x: 10 ** (x / 20)
film_dir = lambda slug: os.path.join(FILMS, slug)
audio_dir = lambda slug: os.path.join(PUB, "films", slug, "audio")


def load_json(p, default=None):
    return json.load(open(p)) if os.path.exists(p) else default


# ---------------------------------------------------------------- takes: measure and split
def separate(src, out):
    """Demucs stems for one take (sound.py's htdemucs), cached in `out`."""
    sys.path.insert(0, paths.TOOLS)
    import sound
    os.makedirs(out, exist_ok=True)
    wav = os.path.join(out, "_44k.wav")
    if not all(os.path.exists(os.path.join(out, s + ".wav")) for s in ("drums", "bass", "other", "vocals")):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ar", "44100", "-ac", "2", wav], check=True)
        sound.separate(wav, out)
        os.remove(wav)
    return {s: os.path.join(out, s + ".wav") for s in ("drums", "bass", "other", "vocals")}


def rms_db(y):
    return 20 * np.log10(np.sqrt(np.mean(np.square(y))) + 1e-9)


def tempo_of(drums):
    """BPM from the drum stem's onset autocorrelation, read between 95 and 160 (the beat tracker halves fast takes)."""
    y, sr = librosa.load(drums, sr=22050, mono=True)
    ac = librosa.autocorrelate(librosa.onset.onset_strength(y=y, sr=sr), max_size=4 * sr // 512)
    bpm = 60 * sr / 512 / np.maximum(np.arange(len(ac)), 1)
    m = (bpm > 95) & (bpm < 160)
    return float(bpm[m][np.argmax(ac[m])])


def cmd_takes(slug):
    A = audio_dir(slug)
    td = os.path.join(A, "takes")
    for f in sorted(os.listdir(td)):
        if not f.endswith((".mp3", ".wav")):
            continue
        tid = os.path.splitext(f)[0]
        y, sr = librosa.load(os.path.join(td, f), sr=22050, mono=True)
        S = np.abs(librosa.stft(y)); fr = librosa.fft_frequencies(sr=sr)
        hi = S[fr > 5000].sum() / S.sum()
        st = separate(os.path.join(td, f), os.path.join(A, "stems", tid))
        lv = {s: rms_db(sf.read(p)[0]) for s, p in st.items()}
        d, dsr = sf.read(st["drums"]); d = d.mean(1) if d.ndim == 2 else d
        opening = rms_db(d[: 12 * dsr])
        flags = []
        if lv["vocals"] > -45: flags.append("VOCALS")
        if opening < lv["drums"] - 6: flags.append(f"drums {lv['drums'] - opening:.0f} dB quieter in the first 12 s (play it as generated, not drums-first)")
        bpm = tempo_of(st["drums"])
        print(f"{tid}: {len(y) / sr:.1f}s, ~{bpm:.0f} BPM, high end {hi * 100:.0f}%, "
              + ", ".join(f"{s} {v:.0f} dB" for s, v in lv.items()) + (f"  [{'; '.join(flags)}]" if flags else ""))


# ---------------------------------------------------------------- score: arrange to the picture
def load_st(path):
    y, _ = librosa.load(path, sr=SR, mono=False)
    return np.vstack([y, y]) if y.ndim == 1 else y


def first_hit(y):
    """A take's first strong onset (s): where its music really starts."""
    env = librosa.onset.onset_strength(y=y.mean(0), sr=SR)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=SR, units="time", backtrack=True)
    strong = [t for t in on if env[librosa.time_to_frames(t, sr=SR)] > 0.35 * env.max()]
    return float(strong[0] if strong else on[0] if len(on) else 0.0)


def gate(n, ins, outs=(), ramp=0.25):
    """0..1 over n samples: up from each film time in `ins` (a short ramp), down over each [a, b) in `outs`."""
    t = np.arange(n) / SR
    g = np.zeros(n)
    for a in ins:
        g = np.maximum(g, np.clip((t - a) / ramp + 1, 0, 1) * (t >= a - ramp))
    for a, b in outs:
        g *= 1 - np.clip(np.minimum((t - a + 0.08) / 0.08, (b - t) / 0.12), 0, 1)
    return g


def place(y, start, n):
    out = np.zeros((2, n)); a = int(round(start * SR))
    src = y[:, max(0, -a):]; d0 = max(0, a)
    k = min(src.shape[1], n - d0)
    out[:, d0: d0 + k] = src[:, :k]
    return out


def cmd_score(slug):
    D, A = film_dir(slug), audio_dir(slug)
    C = load_json(os.path.join(D, "cues.json"))
    M = C["music"]; arr = M.get("arrangement", {})
    film = C["duration"]; n = int(film * SR)
    takes, chosen = [], None
    for T in M["takes"]:
        tid = T["id"]
        src = os.path.join(A, "takes", tid + ".mp3")
        if not os.path.exists(src):
            print(f"{tid}: no take file, skipped"); continue
        y = load_st(src)
        hit = first_hit(y)
        start = M["anchor"] - hit
        if T.get("arranged") and arr:
            st = separate(src, os.path.join(A, "stems", tid))
            layer = {s: place(load_st(st[s]), start, n) for s in ("drums", "bass", "other")}
            outs = [tuple(b) for b in arr.get("breaths", [])]
            out = sum(layer[s] * gate(n, [arr.get(s, 0)], outs if s != "drums" else []) for s in ("drums", "bass", "other"))
            how = "stems arranged: " + ", ".join(f"{s} from {arr.get(s, 0)}s" for s in ("drums", "bass", "other")) + (f", drums alone over {outs}" if outs else "")
        else:
            out = place(y, start, n); how = "the take as generated"
        f = int(M["fade"] * SR)
        out[:, -f:] *= np.linspace(1, 0, f) ** 1.5
        out[:, : int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))
        lvl = np.sqrt(np.mean(out[:, int(min(8, film / 3) * SR): int((film - 3) * SR)] ** 2))
        out = np.clip(out * db(M["rms"]) / (lvl + 1e-9), -0.98, 0.98)
        path = os.path.join(A, f"score-{tid}.wav")
        sf.write(path, out.T.astype(np.float32), SR)
        takes.append({"id": tid, "name": T["name"], "file": rel(path), "dur": film,
                      "note": f"{T.get('note', '')}. First hit on {M['anchor']}s; {how}; fades over the last {M['fade']}s".lstrip(". ")})
        if tid == M["take"]:
            chosen = (rel(path), T["name"])
        print(f"{tid}: first hit {hit:.2f}s, starts at film {start:.2f}s, {how}")
    json.dump({"_note": "Alternatives for the film's sound tracks, keyed by sound.json track id (Build, Sound, Takes, Use). Written by soundkit.py score.",
               "tracks": {"music": {"label": "Score", "chosen": M["take"], "takes": takes}}}, open(os.path.join(D, "takes.json"), "w"), indent=2)
    p = os.path.join(D, "sound.json")
    S = load_json(p, {"_note": "The film's mix (soundkit.py writes it). Remotion plays it (lib/sound.tsx); sound.py reads it for the Sound panel.", "tracks": []})
    S["tracks"] = [{"id": "music", "lane": "music", "name": f"Score: {chosen[1]}, arranged to the picture", "file": chosen[0],
                    "start": 0.0, "offset": 0.0, "dur": film, "gain": M.get("gain", 0.9)}] + [t for t in S["tracks"] if t["lane"] != "music"]
    json.dump(S, open(p, "w"), indent=2)


# ---------------------------------------------------------------- sfx: the shared kit on the film's cues
def slice_hit(y, at, length, attack=0.002):
    a = max(0, int(at * SR) - int(0.004 * SR))
    h = y[a: a + int(length * SR)].copy()
    m = len(h); env = np.ones(m)
    k = int(attack * SR); env[:k] = np.linspace(0, 1, k)
    env *= np.exp(-np.linspace(0, 1, m) * 3) ** 0.5
    env[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
    return h * env


def load_kit(levels=None):
    """The kit's hits, per kind, cut from the sources in kit.json and shaped to each kind's level and brightness."""
    K = load_json(os.path.join(KIT, "kit.json"))
    lv = {k: tuple(v) for k, v in K["levels"].items()}
    lv.update(levels or {})
    src = {}
    load = lambda f: src.setdefault(f, librosa.load(os.path.join(KIT, f), sr=SR, mono=True)[0])

    def finish(h, kind):
        peak, lp = lv[kind]
        h = sosfilt(butter(4, min(lp, SR / 2 - 100), "low", fs=SR, output="sos"), h)
        h = sosfilt(butter(2, 80, "high", fs=SR, output="sos"), h)          # the sub stays the score's
        return h * db(peak) / (np.abs(h).max() + 1e-9)

    kit = {}
    for kind, spec in K["kinds"].items():
        hits = []
        for s in spec:
            y = load(s["file"])
            if s.get("onsets"):                                               # a take of many taps: every clean onset
                for t in librosa.onset.onset_detect(y=y, sr=SR, units="time", backtrack=True):
                    h = slice_hit(y, t, s["len"])
                    if np.abs(h).max() > db(s.get("floor", -34)):
                        hits.append(h)
            elif s.get("whole"):                                              # a whole take, faded both ends
                w = y[int(s.get("mid", 0) * SR):] if not s.get("mid") else y[max(0, int((len(y) / SR / 2 - s["mid"]) * SR)): int((len(y) / SR / 2 + s["mid"]) * SR)]
                hits.append(w * np.hanning(len(w)) ** s.get("hann", 0.6))
            else:
                h = slice_hit(y, s["at"], s["len"])
                if s.get("pitch"):
                    h = librosa.resample(h, orig_sr=SR, target_sr=int(SR * s["pitch"]))
                hits.append(h)
        kit[kind] = [finish(h, kind) for h in hits[: spec[0].get("max", 24)]]
    kit["space"] = [finish(sosfilt(butter(2, 2500, "low", fs=SR, output="sos"), h), "space") for h in kit["key"][:6]]
    return kit


class Events:
    """What a film's sound_events.py gets: `at(beat, s)` turns a beat cue into film time (beat None: `s` is already film
    time); one/many/typing add kit events; `file` places one of the film's own sounds as it is (a played note, a sound
    made for this film), so a curated sound survives the lane being rebuilt."""
    def __init__(self, C):
        self.C, self.ev, self.files = C, [], []

    def at(self, beat, local):
        if beat is None:
            return local
        sc = self.C["scenes"][beat]
        return (sc["start"] if isinstance(sc, dict) else sc[0]) + local

    def file(self, i, name, path, beat, local, gain=1.0, offset=0.0):
        """The film's own sound file (project-relative), untouched, starting at the cue."""
        self.files.append({"id": f"sfx-{i}", "lane": "sfx", "name": name, "file": path, "start": round(self.at(beat, local), 4),
                           "offset": offset, "gain": gain})

    def one(self, i, name, kind, beat, local):
        self.ev.append((i, name, [(self.at(beat, local), kind)]))

    def many(self, i, name, beat, hits):
        self.ev.append((i, name, [(self.at(beat, l), k) for l, k in hits]))

    def typing(self, i, text, beat, start, cps, every=1):
        """One key per letter as the scene types it (letter n appears at start + n / cps); `every` thins fast runs."""
        hs = [(start + n / cps, "space" if ch == " " else "key") for n, ch in enumerate(text) if n % every == 0]
        self.ev.append((i, f"typing: {text}", [(self.at(beat, l), k) for l, k in hs]))


def cmd_sfx(slug):
    D, A = film_dir(slug), audio_dir(slug)
    C = load_json(os.path.join(D, "cues.json"))
    spec = importlib.util.spec_from_file_location("sound_events", os.path.join(D, "sound_events.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    E = Events(C)
    mod.events(C, E)
    kit = load_kit(getattr(mod, "LEVELS", None))
    fx = os.path.join(A, "fx"); os.makedirs(fx, exist_ok=True)
    for old in os.listdir(fx):
        os.remove(os.path.join(fx, old))
    tracks, count = [], {}
    for i, name, hs in E.ev:
        t0 = min(x for x, _ in hs)
        f0 = max(0, int(np.floor(t0 * FPS))) / FPS                         # start on a frame, pad to the exact sample
        parts = []
        for n, (x, kind) in enumerate(hs):
            count[kind] = count.get(kind, 0) + 1
            # which take of the kind, and its small level variation, come from this hit alone (its event id and place in
            # the event), so adding or removing another event never changes how the rest sound
            h = zlib.crc32(f"{i}:{n}:{kind}".encode())
            parts.append((int(round((x - f0) * SR)), kit[kind][h % len(kit[kind])] * db(((h >> 8) % 3001) / 1000 - 1.5)))
        out = np.zeros(max(a + len(h) for a, h in parts))
        for a, h in parts:
            out[max(0, a): a + len(h)] += h[max(0, -a):]
        path = os.path.join(fx, f"{i}.wav")
        sf.write(path, out.astype(np.float32), SR)
        tracks.append({"id": f"sfx-{i}", "lane": "sfx", "name": name, "file": rel(path), "start": round(f0, 4), "offset": 0, "gain": 1})
    p = os.path.join(D, "sound.json")
    S = load_json(p, {"_note": "The film's mix (soundkit.py writes it). Remotion plays it (lib/sound.tsx); sound.py reads it for the Sound panel.", "tracks": []})
    missing = [f["file"] for f in E.files if not os.path.exists(os.path.join(ROOT, f["file"]))]
    if missing:
        sys.exit("sound_events.py places files that don't exist: " + ", ".join(missing))
    S["tracks"] = [t for t in S["tracks"] if t["lane"] != "sfx"] + tracks + E.files
    json.dump(S, open(p, "w"), indent=2)
    print(f"{len(tracks)} effect tracks, {sum(count.values())} hits: " + ", ".join(f"{k} {v}" for k, v in sorted(count.items()))
          + (f"; {len(E.files)} of the film's own sounds" if E.files else ""))


def cmd_loudness(path):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    summary = r.stderr[r.stderr.rfind("Summary"):]
    for line in summary.splitlines():
        if line.strip().startswith(("I:", "Peak:")):
            print(line.strip())


if __name__ == "__main__":
    cmd, arg = (sys.argv[1:3] + [None, None])[:2]
    if cmd not in ("takes", "score", "sfx", "loudness") or not arg:
        print(__doc__); sys.exit(1)
    {"takes": cmd_takes, "score": cmd_score, "sfx": cmd_sfx, "loudness": cmd_loudness}[cmd](arg)
