# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pillow", "librosa"]
# ///
"""Machine pass over a reference video: cuts, per-scene frames, motion energy, palette, music tempo.

The output is what a human or an agent looks at to write the scene-by-scene breakdown
(library/references/<slug>/breakdown.json). Agents can't watch video or hear audio, so this
turns both into things they can read: contact sheets, numbers, and a beat grid.

usage:
  spliced analyze analyze <video> <slug> [--threshold 0.22] [--min-scene 0.25]
  spliced analyze strip <video> <t0> <t1> <n> <out.jpg>   # dense look at a moment

writes library/references/<slug>/:
  analysis.json         hard cuts, shots between them (start/end/energy/palette/brightness), change_events
                        (soft transitions and big moments), audio (bpm, beats, cut-on-beat share)
  sheets/overview.jpg   the whole film, one tile per 0.5-1.5s, timestamps burned in
  sheets/shot-NN.jpg    per detected shot: 3 frames (10/50/90%), or 5 for shots longer than 4s
Shots are machine-detected cut-to-cut spans. Scenes are decided by a person/agent in breakdown.json.
"""
import json, os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import paths

ROOT = paths.ROOT
LIB = paths.REFS


def probe(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", video],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out); s = j["streams"][0]; n, d = s["r_frame_rate"].split("/")
    return {"width": s["width"], "height": s["height"], "fps": round(float(n) / float(d), 3),
            "duration": round(float(j["format"]["duration"]), 3)}


def detect_cuts(video, threshold):
    """ffmpeg scene score on a downscaled decode. Catches hard cuts; misses slow morphs/dissolves (by design:
    those are transitions inside a scene and the breakdown describes them)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-an", "-vf",
                        f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def gray_frames(video, fps=12, w=160):
    info = probe(video); h = int(round(info["height"] * w / info["width"] / 2) * 2)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-an", "-vf", f"fps={fps},scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    return a, fps


def grab(video, t, width=640):
    from io import BytesIO
    out = ["-frames:v", "1", "-vf", f"scale={width}:-2", "-f", "image2pipe", "-vcodec", "png", "-"]
    tries = [["-ss", f"{max(t, 0):.3f}", "-i", video],            # fast seek
             ["-i", video, "-ss", f"{max(t, 0):.3f}"],            # accurate seek (some files fail fast seek)
             ["-ss", f"{max(t - 0.1, 0):.3f}", "-i", video],      # a hair earlier
             ["-sseof", "-0.2", "-i", video]]                     # past the end
    for a in tries:
        r = subprocess.run(["ffmpeg", "-v", "error", *a, *out], capture_output=True)
        if r.stdout:
            return Image.open(BytesIO(r.stdout)).convert("RGB")
    raise RuntimeError(f"could not grab a frame at {t}s from {video}")


def font(size):
    for p in ["/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def label(im, text):
    d = ImageDraw.Draw(im); f = font(max(14, im.width // 32))
    box = d.textbbox((0, 0), text, font=f); pad = 6
    d.rectangle([0, 0, box[2] + 2 * pad, box[3] + 2 * pad], fill=(0, 0, 0))
    d.text((pad, pad), text, fill=(255, 255, 255), font=f)
    return im


def sheet(images, cols, gap=6, bg=(30, 30, 30)):
    w, h = images[0].size; rows = (len(images) + cols - 1) // cols
    out = Image.new("RGB", (cols * w + (cols - 1) * gap, rows * h + (rows - 1) * gap), bg)
    for i, im in enumerate(images):
        out.paste(im, ((i % cols) * (w + gap), (i // cols) * (h + gap)))
    return out


def palette(im, k=5):
    q = im.resize((160, 90)).quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: 3 * k]; counts = sorted(q.getcolors(), reverse=True)
    return [{"hex": "#%02x%02x%02x" % tuple(pal[3 * i: 3 * i + 3]), "share": round(c / (160 * 90), 3)} for c, i in counts]


def audio(video, cuts):
    import librosa, tempfile
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "a.wav")
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "22050", wav], capture_output=True)
        if r.returncode or not os.path.exists(wav):
            return {"silent": True, "note": "no audio stream"}
        y, sr = librosa.load(wav, sr=22050, mono=True)
    if len(y) < sr or np.abs(y).max() < 1e-4:
        return {"silent": True}
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    bpm = float(np.atleast_1d(tempo)[0])
    rms = librosa.feature.rms(y=y)[0]; t = librosa.times_like(rms, sr=sr)
    loud = [round(float(20 * np.log10(rms[(t >= i) & (t < i + 1)].mean() + 1e-9)), 1) for i in range(int(len(y) / sr))]
    on_beat = None
    if len(beats) and cuts:
        dist = [min(abs(c - b) for b in beats) for c in cuts]
        on_beat = round(sum(d <= 0.08 for d in dist) / len(dist), 2)
    return {"bpm": round(bpm, 1), "beat_s": round(60 / bpm, 4) if bpm else None,
            "beats": [round(float(b), 3) for b in beats], "loudness_db_per_s": loud,
            "cuts_within_80ms_of_beat": on_beat}


def analyze(video, slug, threshold=0.22, min_scene=0.25):
    info = probe(video); dur = info["duration"]
    out = os.path.join(LIB, slug); sh = os.path.join(out, "sheets"); os.makedirs(sh, exist_ok=True)

    cuts = [c for c in detect_cuts(video, threshold) if 0.1 < c < dur - 0.1]
    merged = []
    for c in cuts:  # drop flicker: cuts closer than min_scene to the previous one
        if not merged or c - merged[-1] >= min_scene:
            merged.append(c)
    bounds = [0.0] + merged + [dur]

    g, gfps = gray_frames(video)
    diff = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))  # mean abs change per frame step, 0..255
    gt = np.arange(len(diff)) / gfps

    scenes = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        m = (gt > a + 0.1) & (gt < b - 0.1)  # skip the cut itself
        energy = float(diff[m].mean()) if m.any() else 0.0
        fracs = [0.1, 0.5, 0.9] if b - a <= 4 else [0.05, 0.27, 0.5, 0.73, 0.95]
        frames = [grab(video, a + f * (b - a), 480) for f in fracs]
        for im, f in zip(frames, fracs):
            label(im, f"shot {i + 1:02d}  {a + f * (b - a):.2f}s")
        sheet(frames, len(frames)).save(os.path.join(sh, f"shot-{i + 1:02d}.jpg"), quality=82)
        mid = frames[len(frames) // 2]
        scenes.append({"id": f"c{i + 1:02d}", "start": round(a, 3), "end": round(b, 3), "dur": round(b - a, 3),
                       "motion_energy": round(energy, 2), "brightness": round(float(np.asarray(mid.convert("L")).mean()), 1),
                       "palette": palette(mid)})

    step = max(0.5, round(dur / 72 * 2) / 2)  # <= ~72 tiles, 0.5s steps for short films
    ts = np.arange(0, dur - 0.05, step)
    tiles = [label(grab(video, float(t), 320), f"{t:.1f}s") for t in ts]
    sheet(tiles, 8).save(os.path.join(sh, "overview.jpg"), quality=80)

    # Soft changes that aren't hard cuts: fades on white, blur-outs, big reshuffles. Peaks of the change over
    # ~0.33s, local max within +-0.5s. Some are scene boundaries, some are events inside a scene (a sort, a
    # reveal); the breakdown decides which.
    k = max(1, round(gfps / 3)); d = np.abs(g[k:] - g[:-k]).mean(axis=(1, 2)); dt = (np.arange(len(d)) + k / 2) / gfps
    w = round(gfps / 2)
    events = [{"t": round(float(dt[i]), 2), "change": round(float(d[i]), 1),
               "hard_cut": any(abs(dt[i] - c) < 0.25 for c in merged)}
              for i in range(w, len(d) - w) if d[i] == d[i - w:i + w + 1].max() and d[i] > 3]

    shot = [s["dur"] for s in scenes]
    res = {"slug": slug, "file": os.path.relpath(video, ROOT), **info,
           "cut_threshold": threshold, "shot_count": len(scenes),
           "avg_shot_s": round(float(np.mean(shot)), 2), "median_shot_s": round(float(np.median(shot)), 2),
           "cuts_per_min": round(len(merged) / dur * 60, 1),
           "motion_energy_mean": round(float(diff.mean()), 2),
           "overview_step_s": step, "shots": scenes, "change_events": events, "audio": audio(video, merged)}
    with open(os.path.join(out, "analysis.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(f"{slug}: {dur:.1f}s, {len(scenes)} shots, avg shot {res['avg_shot_s']}s, "
          f"bpm {res['audio'].get('bpm')}, cuts on beat {res['audio'].get('cuts_within_80ms_of_beat')}")


def strip(video, t0, t1, n, out):
    ts = np.linspace(float(t0), float(t1), int(n))
    ims = [label(grab(video, float(t), 480), f"{t:.2f}s") for t in ts]
    sheet(ims, min(len(ims), 5)).save(out, quality=82)
    print(out)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("analyze", "strip"):
        sys.exit(__doc__)
    if a[0] == "strip":
        strip(*a[1:6])
    else:
        kw = {}
        if "--threshold" in a: kw["threshold"] = float(a[a.index("--threshold") + 1])
        if "--min-scene" in a: kw["min_scene"] = float(a[a.index("--min-scene") + 1])
        analyze(a[1], a[2], **kw)
