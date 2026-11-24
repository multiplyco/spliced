# /// script
# requires-python = ">=3.10"
# dependencies = ["librosa", "numpy", "scipy", "soundfile"]
# ///
"""The Spliced explainer's UI sound design: light, soft, low-passed hits that follow the picture.

  uv run remotion/src/films/splice-explainer/sfx.py     (after score.py: adds the sfx lane to sound.json)

Sources are ElevenLabs Sound Effects v3 takes in audio/sfx-raw/ (keys, clicks, ticks, thuds, slides, whooshes; see
assets.json). Single hits are cut from them, low-passed so nothing bright sits on top of the deep score, and levelled
quietly. Every moment comes from cues.json on the scenes' design clock and is mapped to film time through the sync
anchors (sync.py), so a click lands where the cursor presses and on the beat the picture was moved to. Typing runs are
pre-mixed into one file each, so keystrokes stay sample-accurate instead of snapping to frames.
"""
import json, os
import numpy as np, librosa, soundfile as sf
from scipy.signal import butter, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
AUD = os.path.join(ROOT, "remotion", "public", "films", "splice-explainer", "audio")
RAW, FX = os.path.join(AUD, "sfx-raw"), os.path.join(AUD, "fx")
SR, FPS = 48000, 30
rel = lambda p: os.path.relpath(p, ROOT)
db = lambda x: 10 ** (x / 20)

# how loud each kind sits (peak dBFS of one hit) and how dark it is (low-pass Hz): heard on each hit, well under the score (v7 at 9 dB lower was inaudible)
LEVEL = {"key": (-22, 4500), "space": (-24, 3500), "click": (-16, 5000), "tick": (-22, 4500), "pop": (-19, 2600),
         "thud": (-15, 2500), "slide": (-22, 3800), "whoosh": (-21, 3000)}


def load(name):
    y, _ = librosa.load(os.path.join(RAW, name + ".mp3"), sr=SR, mono=True)
    return y


def slice_hit(y, at, length, attack=0.002):
    a = max(0, int(at * SR) - int(0.004 * SR))
    h = y[a: a + int(length * SR)].copy()
    n = len(h); env = np.ones(n)
    k = int(attack * SR); env[:k] = np.linspace(0, 1, k)
    env *= np.exp(-np.linspace(0, 1, n) * 3) ** 0.5
    env[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
    return h * env


def finish(h, kind):
    peak, lp = LEVEL[kind]
    h = sosfilt(butter(4, lp, "low", fs=SR, output="sos"), h)
    h = sosfilt(butter(2, 70, "high", fs=SR, output="sos"), h)       # leave the sub to the score
    return h * db(peak) / (np.abs(h).max() + 1e-9)


def hits():
    """The kit: lists of single hits per kind, cut from the ElevenLabs takes."""
    kit = {}
    keys = []
    for name in ("keys-1", "keys-2"):
        y = load(name)
        for t in librosa.onset.onset_detect(y=y, sr=SR, units="time", backtrack=True):
            h = slice_hit(y, t, 0.07)
            if np.abs(h).max() > db(-40):
                keys.append(finish(h, "key"))
    kit["key"] = keys[:24]
    kit["space"] = [finish(sosfilt(butter(2, 1800, "low", fs=SR, output="sos"), k), "space") for k in keys[:6]]
    kit["click"] = [finish(slice_hit(load("click-2"), 0.06, 0.12), "click"), finish(slice_hit(load("click-1"), 0.10, 0.12), "click")]
    kit["tick"] = [finish(slice_hit(load("tick-1"), 0.04, 0.06), "tick"), finish(slice_hit(load("tick-2"), 0.07, 0.06), "tick")]
    pop = librosa.resample(slice_hit(load("tick-2"), 0.07, 0.09), orig_sr=SR, target_sr=SR * 2)  # an octave down
    kit["pop"] = [finish(pop, "pop")]
    kit["thud"] = [finish(slice_hit(load("thud-1"), 0.25, 0.35), "thud"), finish(slice_hit(load("thud-2"), 0.05, 0.3), "thud")]
    kit["slide"] = [finish(slice_hit(load("slide-2"), 0.07, 0.32), "slide"), finish(slice_hit(load("slide-1"), 0.10, 0.32), "slide")]
    w = load("whoosh-1"); w = w * np.hanning(len(w)) ** 0.6
    kit["whoosh"] = [finish(w, "whoosh")]
    return kit


def bezier(x1, y1, x2, y2):
    """CSS cubic-bezier as a function of progress (for the reel's ease-sink)."""
    ts = np.linspace(0, 1, 2001)
    bx = 3 * (1 - ts) ** 2 * ts * x1 + 3 * (1 - ts) * ts ** 2 * x2 + ts ** 3
    by = 3 * (1 - ts) ** 2 * ts * y1 + 3 * (1 - ts) * ts ** 2 * y2 + ts ** 3
    return lambda p: np.interp(np.clip(p, 0, 1), bx, by)


def main():
    C = json.load(open(os.path.join(HERE, "cues.json")))
    SYNC = np.array(C["sync"])
    film = lambda d: float(np.interp(d, SYNC[:, 0], SYNC[:, 1]))     # design clock -> film time
    lead = C["music"].get("encoderLead", 0)
    kit = hits()
    rng = np.random.default_rng(3)
    ev = []                                                          # (id, name, kind or None, [(design t, kind)])

    def one(i, name, kind, d):
        ev.append((i, name, [(d, kind)]))

    def typing(i, name, text, at, cps):
        ev.append((i, f"typing: {name}", [(at + n / cps, "space" if ch == " " else "key") for n, ch in enumerate(text)]))

    o, p, c, nm, f, b, cl, bu, e = (C[k] for k in ("open", "paste", "cut", "name", "find", "boardIt", "claude", "build", "end"))
    typing("type-open-1", o["lines"][0], o["lines"][0], o["typeAt"][0], o["cps"])
    typing("type-open-2", o["lines"][1], o["lines"][1], o["typeAt"][1], o["cps"])
    one("whip", "add sheet whips in", "whoosh", p["whip"] - 0.08)
    one("focus", "text box focus", "tick", p["focus"])
    ev.append(("paste", "paste (cmd V)", [(p["paste"] - 0.07, "key"), (p["paste"], "key")]))
    one("add-click", "click Add", "click", p["click"])
    one("job", "job row opens", "slide", p["job"])
    ev.append(("steps", "steps done", [(p["steps"][0], "tick"), (p["steps"][1], "tick")]))
    one("strip-in", "film strip slides in", "slide", c["enter"])
    # the playhead passes each scene cut: a tick as each gap opens
    a, z = c["scan"]
    strip = json.load(open(os.path.join(HERE, "frames.json")))["strip"]
    cuts = [i for i in range(1, len(strip)) if strip[i]["scene"] != strip[i - 1]["scene"]]
    ev.append(("scan-cuts", "playhead cuts the scenes", [(a + (z - a) * i / len(strip), "tick") for i in cuts]))
    ev.append(("cards", "scenes become cards", [(c["cards"], "slide")] + [(c["cards"] + g * 0.05 + 0.3, "tick") for g in range(0, 6, 2)]))
    one("carry", "card carries to centre", "whoosh", nm["carry"] - 0.05)
    ease = bezier(0.7, 0, 0.2, 1); n = len(nm["reelTags"]) - 1
    ts = np.arange(nm["reel"], nm["reel"] + 0.9, 0.001); pos = np.floor(ease((ts - nm["reel"]) / 0.9) * n)
    ev.append(("reel", "tag reel spins", [(float(t), "tick") for t, d in zip(ts[1:], np.diff(pos)) if d > 0][:-1]))
    one("reel-land", "reel locks on blur-in", "click", nm["land"])
    ev.append(("tags", "tags appear", [(nm["tags"] + i * 0.07, "pop") for i in range(0, 4, 2)]))
    one("window", "app window rises", "whoosh", f["window"] - 0.05)
    one("search-click", "click search", "click", f["click"])
    typing("type-find", f["query"], f["query"], f["type"], f["cps"])
    one("sort", "grid re-sorts", "slide", f["sort"])
    ev.append(("pick", "pick a scene", [(f["pickClick"], "click"), (f["pickClick"] + 0.06, "pop")]))
    one("to-boards", "to Boards", "whoosh", C["design"]["board-it"][0] - 0.05)
    ev.append(("pile", "cards drop on the pile", [(b["pile"] + i * b["pileGap"] + 0.12, "thud") for i in range(4)]))
    one("snap", "cards snap into the beats", "slide", b["snap"])
    one("row-focus", "focus beat 3", "tick", b["focus"])
    typing("type-board", "Cut into scenes.", "Cut into scenes.", b["type"], b["cps"])
    ev.append(("claude-add", "Claude adds two beats", [(t, "pop") for t in cl["add"]]))
    one("toast-1", "toast", "tick", cl["toast1"] + 0.05)
    one("claude-edit", "Claude edits beat 4", "pop", cl["edit"])
    one("to-build", "to Build", "whoosh", C["design"]["build-view"][0] - 0.05)
    one("render-click", "click the render", "click", bu["click"])
    one("pin", "note pin drops", "pop", bu["pin"])
    typing("type-note", bu["note"], bu["note"], bu["type"], bu["cps"])
    ev.append(("blocks", "logo blocks rise", [(e["rise"] + j * e["riseGap"], "thud") for j in range(1, 4)]))
    one("word", "wordmark wipes in", "whoosh", e["word"] - 0.05)

    os.makedirs(FX, exist_ok=True)
    for old in os.listdir(FX):
        os.remove(os.path.join(FX, old))
    tracks, count = [], {}
    for i, name, hs in ev:
        times = [(film(d) - lead, kind) for d, kind in hs]
        t0 = min(t for t, _ in times)
        f0 = max(0, int(np.floor(t0 * FPS))) / FPS                   # start on a frame, pad to the exact sample
        ends = []
        for t, kind in times:
            k = count.get(kind, 0); count[kind] = k + 1
            h = kit[kind][k % len(kit[kind])] * db(rng.uniform(-1.5, 1.5))
            ends.append((int(round((t - f0) * SR)), h))
        out = np.zeros(max(s + len(h) for s, h in ends))
        for s, h in ends:
            out[max(0, s): s + len(h)] += h[max(0, -s):]
        path = os.path.join(FX, f"{i}.wav")
        sf.write(path, out.astype(np.float32), SR)
        tracks.append({"id": f"sfx-{i}", "lane": "sfx", "name": name, "file": rel(path), "start": round(f0, 4), "offset": 0, "gain": 1})
    p = os.path.join(HERE, "sound.json")
    S = json.load(open(p))
    S["tracks"] = [t for t in S["tracks"] if t["lane"] != "sfx"] + tracks
    json.dump(S, open(p, "w"), indent=2)
    print(f"{len(tracks)} effect tracks, {sum(count.values())} hits: " + ", ".join(f"{k} {v}" for k, v in sorted(count.items())))


if __name__ == "__main__":
    main()
