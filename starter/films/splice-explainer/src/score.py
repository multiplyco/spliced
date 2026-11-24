# /// script
# requires-python = ">=3.10"
# dependencies = ["librosa", "numpy", "scipy", "soundfile"]
# ///
"""The Spliced explainer's score: an ElevenLabs Music take (deep techno, 120 BPM) fitted to the picture.

  uv run remotion/src/films/splice-explainer/score.py            # build the score and write sound.json + takes.json

Times live in cues.json `music`: the take starts at `start` (film seconds), plays its groove up to `cut` (seconds into
the take, on its beat grid), and at film time `hit` (the cut to the end card) one deep final hit sounds: the take's own
kick at `kickAt`, under a sub tone at the take's root that decays for `tail` seconds over the logo build. Nothing high
is added: the hit is low-passed. The groove itself is never reshaped, only cut on a beat.
"""
import json, os
import numpy as np, librosa, soundfile as sf
from scipy.signal import butter, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
PUB = os.path.join(ROOT, "remotion", "public")
AUD = os.path.join(PUB, "films", "splice-explainer", "audio")
SR = 48000
rel = lambda p: os.path.relpath(p, ROOT)


def lowpass(y, hz, order=4):
    return sosfilt(butter(order, hz, "low", fs=SR, output="sos"), y, axis=-1)


def root_hz(y):
    """The take's sub root: the strongest spectral peak between 35 and 90 Hz."""
    S = np.abs(np.fft.rfft(y.mean(0)[: SR * 20])); f = np.fft.rfftfreq(SR * 20, 1 / SR)
    band = (f > 35) & (f < 90)
    return float(f[band][np.argmax(S[band])])


def final_hit(y, kick_at, tail, root):
    """The take's kick at kick_at (0.4s) and a sub sine at the root, both decaying over `tail` seconds, low-passed."""
    a = int(kick_at * SR)
    k = y[:, a: a + int(0.4 * SR)].copy()
    k *= np.linspace(1, 0, k.shape[1]) ** 2
    n = int(tail * SR); t = np.arange(n) / SR
    env = np.exp(-t / (tail / 4.5)) * np.minimum(1, t / 0.004)
    sub = 0.55 * np.sin(2 * np.pi * root * t) * env
    room = lowpass(np.random.default_rng(7).standard_normal(n) * np.exp(-t / (tail / 6)), 160) * 0.04
    hit = np.zeros((2, n)); hit[:, : k.shape[1]] += k; hit += sub + room
    return lowpass(hit, 900)


def main():
    cues_p = os.path.join(HERE, "cues.json")
    C = json.load(open(cues_p)); M = C["music"]
    src = os.path.join(AUD, "takes", M["take"])
    y, _ = librosa.load(src, sr=SR, mono=False)
    y = np.atleast_2d(y)
    cut = int(M["cut"] * SR)
    groove = y[:, :cut].copy()
    groove[:, -int(0.012 * SR):] *= np.linspace(1, 0, int(0.012 * SR))  # a click-free cut on the beat
    root = root_hz(y)
    hit = final_hit(y, M["kickAt"], M["tail"], root)
    gap = int((M["hit"] - M["start"]) * SR) - groove.shape[1]          # the hit sits on the cut, on the grid
    out = np.concatenate([groove, np.zeros((2, max(0, gap))), hit], axis=1)
    out *= 10 ** (-1 / 20) / np.max(np.abs(out))                       # peak at -1 dBFS
    dst = os.path.join(AUD, "score-deep-techno.wav")
    sf.write(dst, out.T, SR)
    dur = out.shape[1] / SR
    sound = {
        "_note": "The Spliced explainer's mix (written by score.py). Remotion plays it (lib/sound.tsx); Spliced's sound.py reads it for the Sound panel.",
        "music": {"tempo": 120.0, "key": f"root ~{root:.0f} Hz", "offset": M["start"]},
        "tracks": [{"id": "music", "lane": "music", "name": f"Deep techno ({M['take']}), cut on the end card, final hit",
                    "file": rel(dst), "start": M["start"], "offset": M.get("encoderLead", 0), "dur": round(min(dur, C["duration"] - M["start"]), 3),
                    "gain": M.get("gain", 0.9) }],
    }
    sp = os.path.join(HERE, "sound.json")                              # keep the effects lane (sfx.py writes it)
    if os.path.exists(sp):
        sound["tracks"] += [t for t in json.load(open(sp)).get("tracks", []) if t["lane"] == "sfx"]
    json.dump(sound, open(sp, "w"), indent=2)
    takes = {"_note": "Alternatives for the film's sound tracks, keyed by sound.json track id (Build, Sound, Takes, Use).",
             "tracks": {"music": {"label": "Score", "chosen": "deep-techno-a-scored", "takes": [
                 {"id": "deep-techno-a-scored", "name": "Deep techno A, scored", "file": rel(dst), "dur": round(dur, 3),
                  "note": "Darkest take; groove cut on the end card at 33.6s, then one low final hit under the logo"},
                 {"id": "deep-techno-a", "name": "Deep techno A (raw)", "file": rel(os.path.join(AUD, "takes", "deep-techno-A.mp3")), "dur": 40.0,
                  "note": "As generated: stops dead at 32s"},
                 {"id": "deep-techno-b", "name": "Deep techno B (raw)", "file": rel(os.path.join(AUD, "takes", "deep-techno-B.mp3")), "dur": 40.0,
                  "note": "Brighter hats; thins at 30s, then its own decaying tail (lands on the end card when started at 1.6s)"},
                 {"id": "deep-techno-c", "name": "Deep techno C (raw)", "file": rel(os.path.join(AUD, "takes", "deep-techno-C.mp3")), "dur": 40.0,
                  "note": "Brightest of the three: most high end"},
             ]}}}
    json.dump(takes, open(os.path.join(HERE, "takes.json"), "w"), indent=2)
    print(f"{rel(dst)}: {dur:.2f}s from film {M['start']}s, groove to {M['hit']}s, hit tail {M['tail']}s, root {root:.1f} Hz")


if __name__ == "__main__":
    main()
