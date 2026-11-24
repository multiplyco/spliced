"""Write the fixture project the tests run against: a tiny Spliced project, everything in it made here.

  python3 tests/make_fixture.py          # (re)writes tests/fixture/ ; needs ffmpeg for the two films and the render

Two reference films with breakdowns, one uploaded image, one board with a review and a moment, and one film in
production with a render and a six-frame stack. No third-party footage: the videos are ffmpeg test patterns. The derived files (scene
strips, breakdown.md, INDEX.md) are written by the library build, which this runs last (needs uv). The app's
library index is not part of the fixture: it lives in .cache/, and the server builds it on its first start.
"""
import json, os, shutil, struct, subprocess, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fixture")

TAXONOMY = """# Taxonomy (fixture)

The tags a breakdown may use. Each field is a heading; its tags are the backticked words under it.

## 1. Film level

### `category`

| Tag | Meaning |
| --- | --- |
| `product-launch` | A new product or feature, announced |
| `explainer` | How something works |

### `format`

`16x9`, `9x16`

### `voice`

`on-screen-type-only` (no voice), `voiceover` (a narrator)

### `music_feel`

`minimal-pulse`, `driving-electronic`

## 2. Scene level

### `role`

| Tag | Meaning |
| --- | --- |
| `hook` | Opens the film |
| `demo` | Shows the product at work |
| `end-card` | Logo and sign-off |

### `world`

`white-stage`, `dark-stage`

### `subject`

`typography`, `ui`, `logo`

### `camera`

`locked`, `push-in`

### `motion`

`blur-in`, `word-by-word`, `scale-up`

### `transition_in`

`none`, `hard-cut`, `whip`

### `type_treatment`

`centered-headline`, `no-type`

### `pace`

`slow`, `rapid-fire`

### `energy`

`calm`, `punchy`

### `sound_sync`

`cuts-on-beat`, `free`

### `production`

`code`, `generated-video`
"""

STYLES = """# Styles (fixture)

What the two fixture films do, grouped the way a real library groups its looks.

## 1. Looks

Two looks, one per film.

### White stage

A near-white stage with one headline at a time.

- **Seen in:** [Demo one](references/demo-one/breakdown.md#s01) (the hook)
- **Recreate:** a white div and a blur-in headline

### Dark stage

- **Seen in:** [Demo two](references/demo-two/breakdown.md)

## 2. Pace

How fast each film cuts.

| Tier | Films | Notes |
| --- | --- | --- |
| Slow | demo-one (two scenes) | One idea per scene |
| Fast | demo-two | [The whip](references/demo-two/breakdown.md#s02) sets it |

## 3. Notes

Plain prose with one reference: [the end card](references/demo-two/breakdown.md#s03).
"""

README = """# Library (fixture)

Scenes are referenced as `demo-one/s01`.
"""


def scene(sid, start, end, title, role, **kw):
    s = {"id": sid, "start": start, "end": end, "title": title, "role": role, "world": "white-stage", "subject": ["typography"],
         "camera": ["locked"], "motion": ["blur-in"], "transition_in": "hard-cut", "type_treatment": ["centered-headline"],
         "pace": "slow", "energy": "calm", "sound_sync": ["free"], "production": ["code"], "palette": ["#FFFFFF", "#111111"],
         "on_screen": f"{title}, centred on the stage.", "how_it_moves": "The headline sharpens in over half a second.",
         "recreate": "A div and one blur-in.", "steal": 2}
    s.update(kw)
    return s


FILMS = {
    "demo-one": {
        "title": "Demo one", "brand": "Fixture", "source": "made by tests/make_fixture.py", "file": "reference/demo-one.mp4",
        "duration": 4.0, "format": "16x9", "category": "product-launch", "voice": "on-screen-type-only", "music_feel": ["minimal-pulse"],
        "summary": "Four seconds of a test pattern, read as a two-scene launch film.",
        "tempo": {"bpm": 120, "avg_shot_s": 2.0, "cuts_per_min": 30, "notes": "One cut, on the beat."},
        "structure": "Hook, then demo.",
        "style_signature": {"palette": [{"hex": "#FFFFFF", "name": "white stage"}], "type": "One grotesk.", "motion": "Arrive fast, land soft."},
        "signature_moves": [{"name": "Sharpen in", "scenes": ["s01"], "description": "Words arrive out of a blur.", "recreate": "filter: blur() to 0."}],
        "takeaways": ["Lead with the news.", "One idea per scene."],
        "scenes": [scene("s01", 0.0, 2.0, "A headline sharpens in", "hook", transition_in="none", steal=3),
                   scene("s02", 2.0, 4.0, "The product at work", "demo", subject=["ui"], camera=["push-in"], motion=["scale-up"])],
    },
    "demo-two": {
        "title": "Demo two", "brand": "Fixture", "source": "made by tests/make_fixture.py", "file": "reference/Demo two [abc123].mp4",
        "duration": 3.0, "format": "16x9", "category": "explainer", "voice": "voiceover", "music_feel": ["driving-electronic"],
        "summary": "Three one-second scenes, cut fast. Its file name has a space and brackets on purpose.",
        "tempo": {"bpm": 140, "avg_shot_s": 1.0, "cuts_per_min": 60, "notes": "A cut every second."},
        "structure": "Hook, demo, end card.",
        "style_signature": {"palette": [{"hex": "#111111", "name": "dark stage"}], "motion": "Whips between scenes."},
        "signature_moves": [{"name": "The whip", "scenes": ["s02"], "description": "A fast sideways move into the demo.", "recreate": "translateX with motion blur."}],
        "takeaways": ["Cut on the beat."],
        "scenes": [scene("s01", 0.0, 1.0, "Three words, one at a time", "hook", world="dark-stage", motion=["word-by-word"], transition_in="none",
                         pace="rapid-fire", energy="punchy", sound_sync=["cuts-on-beat"]),
                   scene("s02", 1.0, 2.0, "A whip into the interface", "demo", world="dark-stage", subject=["ui"], transition_in="whip",
                         pace="rapid-fire", energy="punchy", production=["generated-video"], steal=3),
                   scene("s03", 2.0, 3.0, "The logo lands", "end-card", world="dark-stage", subject=["logo"], type_treatment=["no-type"], steal=1)],
    },
}

UPLOAD_ID = "f1x7u0"
STATE = {
    "rev": 3, "log": [{"rev": 3, "by": "fixture", "at": "2026-01-01T00:00:00", "summary": "made the fixture"}],
    "reviews": {"demo-one/s01": {"fav": True, "verdict": "use", "note": "the opening we want"}},
    "moments": [{"uid": "m0m3n7", "key": "demo-two/s02", "t": 1.5, "note": "mid-whip", "at": "2026-01-01T00:00:00", "by": "fixture"}],
    "boards": {"Fixture board": {
        "profile": "soft", "created": "2026-01-01", "updated": "2026-01-01T00:00:00",
        "brief": {"news": "The fixture exists.", "audience": "tests", "aspect": "16:9", "length": 6},
        "items": [{"uid": "aaa111", "id": "demo-one/s01", "beat": "hook", "copy": "It exists.", "vo": "", "seconds": 2.0, "note": "sharpen in"},
                  {"uid": "bbb222", "id": "demo-two/s02", "t": 1.5, "beat": "demo", "copy": "", "vo": "Here it is.", "seconds": 2.0, "note": ""},
                  {"uid": "ccc333", "id": f"uploads/{UPLOAD_ID}", "beat": "end-card", "copy": "Fixture", "vo": "", "seconds": 2.0, "note": "the look"}]}},
}

STORYBOARD = {
    "_note": "The fixture's film in production: three beats, ids matching cues.json scenes.",
    "title": "Demo film", "board": "Fixture board", "profile": "soft", "composition": "Demo", "fps": 24, "format": "320x180",
    "message": "The fixture exists.",
    "beats": [
        {"id": "hook", "title": "Hook", "refs": ["demo-one/s01"], "on_screen": "A headline.", "copy": "It exists.", "vo": "", "roles": ["textReveal"],
         "sound": "", "status": "approved", "review": "", "log": []},
        {"id": "demo", "title": "Demo", "refs": ["demo-two/s02"], "on_screen": "The interface.", "copy": "", "vo": "Here it is.", "roles": ["camera"],
         "sound": "", "status": "review", "review": "", "log": []},
        {"id": "end-card", "title": "End card", "refs": [f"uploads/{UPLOAD_ID}"], "on_screen": "The logo.", "copy": "Fixture", "vo": "", "roles": ["enter"],
         "sound": "", "status": "todo", "review": "", "log": []},
    ],
}
CUES = {"fps": 24, "board": "Fixture board", "duration": 6.0, "scenes": {"hook": [0.0, 2.0], "demo": [2.0, 4.0], "end-card": [4.0, 6.0]}}


def write(rel, text):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text if isinstance(text, str) else json.dumps(text, indent=1, ensure_ascii=False) + "\n")


def video(rel, seconds, pattern):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"{pattern}=s=320x180:r=24:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=f=220:d={seconds}", "-c:v", "libx264", "-preset", "veryslow", "-crf", "40", "-g", "12",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "16k", "-ac", "1", "-movflags", "+faststart", "-shortest", p], check=True)


def png(rel, w=96, h=64, shift=0):
    """A small gradient PNG, written by hand so the upload needs no tool. `shift` moves the colours, for frames that differ."""
    rows = b"".join(b"\x00" + bytes(c % 256 for x in range(w) for c in (40 + x * 2 + shift, 30 + y * 3, 200 - x + shift // 2)) for y in range(h))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def stack_frames():
    """The film's own pictures: one still, and the six frames of a render, which the app shows as one stack."""
    png("remotion/public/films/demo/plate.png", shift=90)
    for n in range(1, 7):
        png(f"remotion/public/films/demo/shots/spin/f_{n:04d}.png", shift=n * 30)


def main():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is needed to make the fixture's videos")
    shutil.rmtree(OUT, ignore_errors=True)
    write("spliced.json", {"format": 1, "name": "Fixture", "brand": {"name": "Fixture"}, "default_profile": "soft"})
    write("library/TAXONOMY.md", TAXONOMY)
    write("library/STYLES.md", STYLES)
    write("library/README.md", README)
    write("library/references.tsv", "slug\tfile\tsource\n" + "".join(f"{s}\t{b['file']}\t{b['source']}\n" for s, b in FILMS.items()))
    for slug, b in FILMS.items():
        write(f"library/references/{slug}/breakdown.json", b)
        write(f"library/references/{slug}/analysis.json", {"slug": slug, "file": b["file"], "width": 320, "height": 180, "fps": 24.0, "duration": b["duration"],
                                                              "shot_count": len(b["scenes"]), "shots": [], "change_events": [], "audio": {"bpm": b["tempo"]["bpm"]}})
    video("reference/demo-one.mp4", 4, "testsrc")
    video("reference/Demo two [abc123].mp4", 3, "smptebars")
    png(f"library/uploads/fixture-look-{UPLOAD_ID}.png")
    write("library/uploads/uploads.json", {"_note": "Uploaded references (fixture).", "items": [{
        "id": UPLOAD_ID, "file": f"library/uploads/fixture-look-{UPLOAD_ID}.png", "kind": "image", "title": "A gradient", "note": "the look", "tags": [],
        "source": "", "width": 96, "height": 64, "added": "2026-01-01T00:00:00", "by": "fixture", "palette": ["#2A1EC8", "#E6D269"],
        "analysis": {"role": "end-card", "world": "dark-stage", "pace": "slow", "energy": "calm", "subject": ["logo"], "camera": ["locked"],
                     "motion": ["blur-in"], "type_treatment": ["no-type"], "production": ["code"], "title": "A gradient",
                     "on_screen": "A soft gradient.", "how_it_moves": "It doesn't.", "recreate": "A CSS gradient."},
        "analysed": "2026-01-01T00:00:00"}]})
    write("library/state.json", STATE)
    write("remotion/src/films/demo/storyboard.json", STORYBOARD)
    write("remotion/src/films/demo/cues.json", CUES)
    video("remotion/out/demo-v1.mp4", 6, "testsrc2")
    stack_frames()
    write("remotion/out/demo-v1.json", {"slug": "demo", "version": 1, "file": "remotion/out/demo-v1.mp4", "created": "2026-01-01T00:00:00", "scale": 1.0,
                                        "beat": None, "span": [0.0, 6.0], "fps": 24, "note": "the fixture's first render", "beats": CUES["scenes"]})
    # the derived files (scene strips, breakdown.md, INDEX.md, the app's library data): the library build writes them
    build = os.path.join(os.path.dirname(HERE), "spliced", "build_library.py")
    subprocess.run(["uv", "run", "-q", build], env={**os.environ, "SPLICED_PROJECT": OUT}, check=True, stdout=subprocess.DEVNULL)
    shutil.rmtree(os.path.join(OUT, ".cache"), ignore_errors=True)
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(OUT) for f in fs)
    print(f"tests/fixture written: {sum(len(fs) for _, _, fs in os.walk(OUT))} files, {size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
