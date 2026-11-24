# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright", "pillow"]
# ///
"""The README's pictures of the app, taken on a project made up here.

A real library's thumbnails are frames of other people's films, so the README never shows one. This builds a small
project in a temporary folder from what is ours: the reference film is "Plan it together", the made-up Acme film the
example film studies (its frames drawn in code by starter/films/splice-explainer/src/demo_frames.py, here animated
and cut into a video), and the film in production is the example film itself, with the app's own intro.mp4 as its
render. Then it opens the app on that project in a browser and photographs each view.

  uv run scripts/readme_shots.py               # writes docs/readme/*.jpg
  uv run scripts/readme_shots.py --keep <dir>  # also leaves the made-up project in <dir>, to open with `spliced open`

Needs ffmpeg and uv (the library build). Uses the installed Chrome, or Playwright's own Chromium.
"""
import json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.parse, urllib.request

from PIL import Image
from playwright.sync_api import sync_playwright

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STARTER = os.path.join(REPO, "starter", "films", "splice-explainer")
OUT = os.path.join(REPO, "docs", "readme")
sys.path.insert(0, os.path.join(STARTER, "src"))
import demo_frames  # noqa: E402  (PAGE: the made-up film's scenes as HTML, drawn at any point p from 0 to 1)

SLUG = "acme-plan-it-together"
FPS = 12
VIEW_W, VIEW_H = 1440, 900   # the browser window; photographed at 2x and saved at SAVE_W wide
SAVE_W = 1800
BOARD = "Explainer: borrowed moves"
FILM = "splice-explainer"

ACME, TEAL, DEEP, CREAM, INK, CORAL, MINT = "#FFB703", "#12A594", "#0E3B43", "#FBF7EF", "#10201F", "#FB6F5C", "#DFF3EE"


def sc(sid, dur, title, role, world, subject, motion, *, camera=("locked",), trans="hard-cut", tt=("centered-headline",), pace="fast",
       energy="steady", sync=("motion-on-beat",), palette=(), on, moves, recreate, steal=2):
    return {"id": sid, "dur": dur, "title": title, "role": role, "world": world, "subject": list(subject), "camera": list(camera),
            "motion": list(motion), "transition_in": trans, "type_treatment": list(tt), "pace": pace, "energy": energy,
            "sound_sync": list(sync), "production": ["code-only"], "palette": list(palette), "on_screen": on, "how_it_moves": moves,
            "recreate": recreate, "steal": steal}


# the film's scenes, in order: the ids are the ones demo_frames.py draws (the explainer's own made-up film skips some)
SCENES = [
    sc("s01", 1.85, "Diamond glyph pops, wordmark fades in beside it", "cold-open", "dark-stage", ["logo"], ["scale-pop", "arrive-soft"],
       trans="none", tt=(), palette=("#0C1114", ACME, "#FFFFFF"), on="An amber diamond and the word acme on near-black.",
       moves="The diamond pops from half size; the wordmark fades in a beat behind it.", recreate="Two spans: scale 0.5 to 1 on a spring, then opacity."),
    sc("s02", 1.73, "Title on black, liquid gradient blooms underneath", "headline", "gradient-field", ["typography", "abstract-shapes"],
       ["blur-in", "arrive-soft"], trans="cut-on-beat", palette=("#05080A", TEAL, ACME, CORAL), steal=3,
       on="\"Plan it together\" in white, a teal and amber glow rising from the bottom edge.",
       moves="The glow blooms up from below while the title holds still.", recreate="Three blurred circles rising behind a fixed headline."),
    sc("s03", 1.37, "Punch-in onto \"together\"", "headline", "gradient-field", ["typography"], ["kinetic-type"], camera=("push-in",),
       tt=("centered-headline", "oversized-crop"), palette=(DEEP, TEAL, "#58B8E8", ACME), steal=3,
       on="One word, very big, over a drifting gradient field.", moves="The word grows a fifth while the field drifts the other way.",
       recreate="Scale the word 132 to 168 px; move the blobs against it."),
    sc("s04", 1.69, "\"A calmer way to run a launch\" with two live cursors", "hook", "gradient-field", ["typography", "cursor"],
       ["blur-in", "loop-float"], palette=(DEEP, TEAL, ACME), on="A two-line claim; two named cursors, Ana and Sam, drift around it.",
       moves="The cursors float a few pixels each way; the field keeps drifting.", recreate="Two absolutely placed cursor chips on a slow sine."),
    sc("s05", 2.0, "Six pills cascade beside \"Everything in one place\"", "feature-demo", "gradient-field", ["ui-fragment", "typography"],
       ["stagger-cascade", "arrive-soft"], tt=("left-aligned-headline",), palette=(DEEP, TEAL, "#FFFFFF"),
       on="A left-aligned line; six frosted pills stack in on the right.", moves="The pills arrive one after another, four frames apart.",
       recreate="Map six labels to pills with a 4-frame stagger."),
    sc("s06", 1.44, "Projects table fills row by row", "product-reveal", "light-tint-stage", ["ui-rebuild"], ["stagger-cascade"],
       tt=("type-in-ui",), palette=(CREAM, INK, TEAL, ACME), on="A white card on cream: five projects with status and progress.",
       moves="Rows land one by one; each progress bar is already filled.", recreate="One card, five rows, a 3-frame stagger."),
    sc("s07", 2.12, "Glass tiles fly in around the statement", "feature-demo", "gradient-field", ["icons", "typography"],
       ["scale-pop", "spring-overshoot"], palette=(DEEP, TEAL, "#FFFFFF"), on="Six frosted glass tiles with glyphs around a centred line.",
       moves="The tiles pop in from zero, each a little after the last, and overshoot.", recreate="Six tiles, scale 0 to 1 on a bouncy spring, staggered."),
    sc("s09", 1.3, "Title card: \"Stay five steps ahead\"", "bridge", "light-tint-stage", ["typography"], ["arrive-soft"],
       palette=(CREAM, INK, TEAL), steal=1, on="One line on cream, two words in teal.", moves="It fades up and holds.", recreate="A single line, opacity 0.4 to 1."),
    sc("s11", 3.5, "A row expands into a launch plan", "feature-demo", "light-tint-stage", ["ui-rebuild", "cursor"], ["morph", "ui-interaction"],
       trans="morph-transition", tt=("type-in-ui",), pace="medium", palette=("#F6F3EC", INK, CORAL), steal=3,
       on="A document card titled Launch plan, a cursor resting at its foot.",
       moves="The card grows taller and rises as if a table row opened into it.", recreate="Animate one card's top and height; keep its contents fixed."),
    sc("s13", 3.75, "Helper pills drift in rows", "montage", "white-stage", ["ui-fragment"], ["ui-interaction", "loop-float"],
       camera=("pan-track",), tt=("type-in-ui",), pace="medium", palette=("#FBFAF6", TEAL, ACME, CORAL),
       on="\"Loading your helpers\" over three rows of coloured pills.", moves="The rows slide sideways, the middle one against the others.",
       recreate="Three flex rows on a slow translateX, alternate directions."),
    sc("s14", 1.35, "\"Make it yours\" builds word by word on mint", "headline", "light-tint-stage", ["typography"], ["word-by-word"],
       palette=(MINT, INK), on="Three bold words on mint.", moves="The last word darkens into place as it lands.",
       recreate="Three spans; colour the last one on the beat."),
    sc("s20", 2.4, "Stepped punch-ins onto \"Ask Acme\", a soft glow builds", "product-reveal", "white-stage", ["ui-fragment"],
       ["ui-interaction", "morph"], camera=("push-in",), tt=("type-in-ui",), pace="medium", palette=("#FBFAF6", "#9FF0E2", INK),
       on="A large rounded input reading Ask Acme, a mint glow behind it.", moves="The input grows in steps while the glow widens.",
       recreate="Interpolate the pill's size, radius and type together."),
    sc("s21", 6.4, "Frosted chat panel: typing dots, then a reply", "use-case", "gradient-field", ["ui-rebuild", "ai-working-state"],
       ["blur-in", "arrive-soft"], tt=("type-in-ui",), pace="slow", energy="calm", palette=(DEEP, TEAL, "#FFFFFF"),
       on="A glass chat panel: a question, then three dots, then a four-line answer.", moves="The dots hold, then the reply opens out of them.",
       recreate="Swap the dots for the answer at the halfway mark; widen the bubble."),
    sc("s23", 4.4, "Launch plan co-edited with live text cursors", "use-case", "light-tint-stage", ["ui-rebuild", "cursor"],
       ["typewriter", "ui-interaction"], tt=("type-in-ui",), pace="medium", palette=("#F6F3EC", INK, CORAL, TEAL),
       on="A document with two coloured text cursors, Sam and Ana.", moves="A phrase types in at Ana's cursor while Sam's waits.",
       recreate="Reveal characters at a fixed rate; tag each caret with a name chip."),
    sc("s25", 4.83, "Next steps checklist ticked by two cursors", "use-case", "white-stage", ["ui-rebuild", "cursor"],
       ["stagger-cascade", "ui-interaction"], tt=("type-in-ui",), pace="medium", palette=("#FBFAF6", INK, TEAL, ACME), steal=3,
       on="A five-item checklist; two cursors work down it.", moves="Items tick and strike through one by one as the cursors pass.",
       recreate="Drive a tick count from time; move the cursors on two eased paths."),
    sc("s26", 5.3, "Activity feed scrolls, the plan is approved", "proof", "white-stage", ["ui-rebuild"], ["arrive-soft"],
       camera=("pan-track",), tt=("type-in-ui",), pace="slow", energy="calm", palette=("#FBFAF6", INK, "#12724F"), steal=1,
       on="An activity card: five lines of who did what, one marked Approved.", moves="The card scrolls up slowly.",
       recreate="One card on a slow translateY."),
    sc("s27", 2.64, "Tagline blurs in through a coral sweep", "payoff", "white-stage", ["typography", "abstract-shapes"],
       ["blur-in", "word-by-word"], palette=("#FBFAF6", CORAL, DEEP), on="\"Plans that keep up with you\" with a coral glow passing behind.",
       moves="A blurred coral shape sweeps left to right; the line sharpens as it passes.", recreate="filter: blur(5px) to 0, under a moving blurred ellipse."),
    sc("s28", 6.26, "\"acme\" end card on near-black", "end-card", "dark-stage", ["logo", "typography"], ["arrive-soft"], pace="slow",
       energy="calm", palette=("#0C1114", ACME, "#E8EEEC"), steal=0, on="The acme lockup with the title beneath.",
       moves="The title brightens and holds.", recreate="A lockup and one fade."),
]

TAXONOMY = os.path.join(REPO, "spliced", "templates", "project", "library", "TAXONOMY.md")


def breakdown():
    t, scenes = 0.0, []
    for s in SCENES:
        s = dict(s)
        dur = s.pop("dur")
        s["start"], s["end"] = round(t, 3), round(t + dur, 3)
        t += dur
        scenes.append(s)
    return {
        "title": "Plan it together", "brand": "Acme", "source": "made up: drawn by starter/films/splice-explainer/src/demo_frames.py",
        "file": f"reference/{SLUG}.mp4", "duration": round(t, 3), "format": "16x9", "category": "product-launch",
        "voice": "on-screen-type-only", "music_feel": ["minimal-pulse"],
        "summary": "A made-up launch film for a made-up planning app. Warm gradients, frosted glass and rebuilt UI, with two named cursors "
                   "carrying the idea of planning together from the first claim to the checklist.",
        "tempo": {"bpm": 120, "avg_shot_s": round(t / len(scenes), 2), "cuts_per_min": round(len(scenes) / t * 60, 1),
                  "notes": "Fast type up front, slower UI scenes in the middle, a long hold on the end card."},
        "structure": "Logo, title, claim, three features, the assistant, working together, tagline, end card.",
        "style_signature": {"palette": [{"hex": DEEP, "name": "deep teal"}, {"hex": TEAL, "name": "teal"}, {"hex": ACME, "name": "amber"},
                                        {"hex": CORAL, "name": "coral"}, {"hex": CREAM, "name": "cream"}],
                            "type": "One rounded grotesk, semibold, tight tracking.", "motion": "Arrive soft, float while held, stagger every group."},
        "signature_moves": [
            {"name": "Live cursors", "scenes": ["s04", "s23", "s25"], "description": "Named cursors drift and work in the frame, so the film says together without saying it.",
             "recreate": "A cursor chip per person on its own eased path."},
            {"name": "Gradient field", "scenes": ["s02", "s03", "s05", "s07"], "description": "Four blurred colour blobs drift slowly behind every type scene.",
             "recreate": "Blurred circles moved by a shared progress value."},
            {"name": "Frosted pills", "scenes": ["s05", "s13"], "description": "Rounded labels on glass arrive one after another.",
             "recreate": "A 4-frame stagger over a list of pills."},
            {"name": "Sharpen through a sweep", "scenes": ["s27"], "description": "A coloured glow passes behind the line as it comes into focus.",
             "recreate": "Blur 5px to 0 timed to a moving blurred ellipse."},
        ],
        "takeaways": ["Say the idea with the motion: two cursors are worth a line of copy.", "Hold the end card long enough to read twice."],
        "scenes": scenes,
    }


STATE = {
    "rev": 4, "log": [{"rev": 4, "by": "readme", "at": "2026-11-20T10:00:00", "summary": "made the showcase project"}],
    "reviews": {f"{SLUG}/s02": {"fav": True, "verdict": "use", "note": "the opening we want"},
                f"{SLUG}/s25": {"fav": True, "verdict": "use", "note": "two cursors say together"},
                f"{SLUG}/s11": {"fav": True, "verdict": "use"},
                f"{SLUG}/s05": {"verdict": "use"}, f"{SLUG}/s09": {"verdict": "skip"}},
    "moments": [{"uid": "m0m001", "key": f"{SLUG}/s21", "t": 3.6, "note": "the reply opens out of the dots", "at": "2026-11-20T10:00:00", "by": "readme"},
                {"uid": "m0m002", "key": f"{SLUG}/s03", "t": 0.8, "note": "punch-in lands", "at": "2026-11-20T10:00:00", "by": "readme"}],
    "boards": {BOARD: {
        "profile": "splice", "created": "2026-11-18", "updated": "2026-11-20T10:00:00",
        "brief": {"news": "Spliced turns the films we love into named, reusable moves, and builds new films from them.",
                  "audience": "motion designers and the people who brief them", "aspect": "16:9", "length": 36},
        "items": [
            {"uid": "b00001", "id": f"{SLUG}/s02", "beat": "hook", "copy": "Films you love. Frame by frame.", "vo": "", "seconds": 3.0, "note": "type on black, a glow underneath"},
            {"uid": "b00002", "id": f"{SLUG}/s05", "beat": "feature-demo", "copy": "Cut into scenes.", "vo": "", "seconds": 4.0, "note": "the cascade, for the scene cards"},
            {"uid": "b00003", "id": f"{SLUG}/s03", "beat": "headline", "copy": "Every move, named.", "vo": "", "seconds": 3.0, "note": "punch in on the tag"},
            {"uid": "b00004", "id": f"{SLUG}/s20", "t": 1.2, "beat": "feature-demo", "copy": "Find it in seconds.", "vo": "", "seconds": 4.0, "note": "the search field grows"},
            {"uid": "b00005", "id": f"{SLUG}/s25", "beat": "use-case", "copy": "Borrow the move. Write the script.", "vo": "", "seconds": 5.0, "note": "two cursors, us and the AI"},
            {"uid": "b00006", "id": f"{SLUG}/s23", "beat": "use-case", "copy": "Your AI works with you.", "vo": "", "seconds": 4.0, "note": ""},
            {"uid": "b00007", "id": f"{SLUG}/s11", "beat": "feature-demo", "copy": "Every beat, beside its reference.", "vo": "", "seconds": 5.0, "note": "a row opens into the Build view"},
            {"uid": "b00008", "id": f"{SLUG}/s28", "beat": "end-card", "copy": "Study it. Name it. Make it.", "vo": "", "seconds": 4.4, "note": "hold it"},
        ]}},
}

# the beats of the example film borrow from the made-up film: Build shows each one beside its reference
REFS = {"open-a-caret": f"{SLUG}/s02", "cut-into-scenes": f"{SLUG}/s05", "name-every-move": f"{SLUG}/s03", "find-it": f"{SLUG}/s20",
        "board-it": f"{SLUG}/s25", "with-claude": f"{SLUG}/s23", "build-view": f"{SLUG}/s11", "end-card": f"{SLUG}/s28"}


def write(root, rel, data):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(data if isinstance(data, str) else json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def film_video(root, browser, b):
    """Every scene drawn at FPS frames a second by demo_frames' page, cut together into reference/<slug>.mp4."""
    frames = tempfile.mkdtemp(prefix="spliced-frames-")
    page = browser.new_page(viewport={"width": demo_frames.W, "height": demo_frames.H})
    page.set_content(demo_frames.PAGE)
    n = 0
    for s in b["scenes"]:
        count = max(2, round((s["end"] - s["start"]) * FPS))
        for i in range(count):
            page.evaluate(f"draw('{s['id']}', {i / (count - 1):.4f})")
            page.screenshot(path=os.path.join(frames, f"f{n:05d}.png"))
            n += 1
    page.close()
    out = os.path.join(root, b["file"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(frames, "f%05d.png"),
                    "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono", "-shortest", "-c:v", "libx264", "-crf", "24", "-pix_fmt", "yuv420p",
                    "-r", "24", "-c:a", "aac", "-b:a", "32k", "-movflags", "+faststart", out], check=True)
    shutil.rmtree(frames)
    return n


def make_project(root, browser):
    write(root, "spliced.json", {"format": 1, "name": "Showcase", "brand": {"name": "Acme"}, "default_profile": "splice", "updates": False})
    os.makedirs(os.path.join(root, "library"), exist_ok=True)
    shutil.copy(TAXONOMY, os.path.join(root, "library", "TAXONOMY.md"))
    for name in ("README.md", "STYLES.md"):
        shutil.copy(os.path.join(REPO, "spliced", "templates", "project", "library", name), os.path.join(root, "library", name))
    b = breakdown()
    write(root, "library/references.tsv", f"slug\tfile\tsource\n{SLUG}\t{b['file']}\t{b['source']}\n")
    write(root, f"library/references/{SLUG}/breakdown.json", b)
    write(root, f"library/references/{SLUG}/analysis.json", {"slug": SLUG, "file": b["file"], "width": demo_frames.W, "height": demo_frames.H, "fps": 24.0,
                                                             "duration": b["duration"], "shot_count": len(b["scenes"]), "shots": [], "change_events": [],
                                                             "audio": {"bpm": 120}})
    frames = film_video(root, browser, b)
    write(root, "library/state.json", STATE)

    src = os.path.join(STARTER, "src")
    story = json.load(open(os.path.join(src, "storyboard.json")))
    for beat in story["beats"]:
        if beat["id"] in REFS:
            beat["refs"] = [REFS[beat["id"]]]
    cues = json.load(open(os.path.join(src, "cues.json")))
    write(root, f"remotion/src/films/{FILM}/storyboard.json", story)
    write(root, f"remotion/src/films/{FILM}/cues.json", cues)
    render = f"remotion/out/{FILM}-v1.mp4"
    os.makedirs(os.path.join(root, "remotion", "out"), exist_ok=True)
    shutil.copy(os.path.join(REPO, "spliced", "web", "intro.mp4"), os.path.join(root, render))
    write(root, f"remotion/out/{FILM}-v1.json", {"slug": FILM, "version": 1, "file": render, "created": "2026-11-20T10:00:00", "scale": 1280 / 1920,
                                                 "beat": None, "span": [0.0, cues["duration"]], "fps": cues["fps"], "note": "first cut",
                                                 "beats": cues["scenes"]})
    subprocess.run(["uv", "run", "-q", os.path.join(REPO, "spliced", "build_library.py")], env={**os.environ, "SPLICED_PROJECT": root},
                   check=True, stdout=subprocess.DEVNULL)
    return frames


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def save(png, name):
    img = Image.open(png).convert("RGB")
    img = img.resize((SAVE_W, round(img.height * SAVE_W / img.width)), Image.LANCZOS)
    out = os.path.join(OUT, name)
    img.save(out, "JPEG", quality=84, optimize=True, progressive=True)
    print(f"  {os.path.relpath(out, REPO)}  {os.path.getsize(out) // 1024} KB")


def launch(p):
    try:
        return p.chromium.launch(channel="chrome")
    except Exception:
        return p.chromium.launch()


def main():
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    if not shutil.which("ffmpeg") or not shutil.which("uv"):
        sys.exit("ffmpeg and uv are needed")
    tmp = tempfile.mkdtemp(prefix="spliced-readme-")
    root = os.path.abspath(keep) if keep else os.path.join(tmp, "showcase")
    if keep and os.path.exists(root) and os.listdir(root):
        sys.exit(f"{root} is not empty")
    os.makedirs(root, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        print(f"drawing the made-up film into {root}")
        print(f"  {make_project(root, browser)} frames")

        port = free_port()
        env = {k: v for k, v in os.environ.items() if not k.startswith("SPLICED_")}
        env.update({"SPLICED_PROJECT": root, "SPLICED_NO_UPDATE_CHECK": "1", "SPLICED_PICKER": "false", "XDG_CONFIG_HOME": os.path.join(tmp, "config")})
        log = open(os.path.join(tmp, "server.log"), "w")
        server = subprocess.Popen([sys.executable, os.path.join(REPO, "spliced", "toolbox.py"), "--port", str(port), "--no-open"],
                                  env=env, stdout=log, stderr=subprocess.STDOUT)
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(base + "/api/info", timeout=1)
                    break
                except Exception:
                    time.sleep(0.2)
            else:
                sys.exit("the server didn't start:\n" + open(log.name).read())
            ctx = browser.new_context(viewport={"width": VIEW_W, "height": VIEW_H}, device_scale_factor=2, color_scheme="dark")
            ctx.add_init_script("localStorage.setItem('cr.welcomed', '1'); localStorage.setItem('cr.explainOff', '1'); "
                               "localStorage.setItem('cr.libCardW', '250'); localStorage.setItem('cr.cardDetails', 'always')")
            page = ctx.new_page()
            shot = os.path.join(tmp, "shot.png")

            def take(hash_, name, settle=1.5, before=None):
                page.goto(f"{base}/app/{hash_}")
                page.wait_for_load_state("networkidle")
                time.sleep(settle)
                if before:
                    before()
                page.mouse.move(VIEW_W - 2, VIEW_H - 2)
                time.sleep(0.4)
                page.screenshot(path=shot)
                save(shot, name)

            print("photographing the app")
            take("#/scenes", "library.jpg", settle=2.5)
            take(f"#/scene/{SLUG}/s25", "scene.jpg", settle=2.5)
            take(f"#/boards/{urllib.parse.quote(BOARD)}", "board.jpg", settle=2.5)
            take(f"#/build/{FILM}", "build.jpg", settle=3.0, before=lambda: (page.evaluate("() => { const v = document.querySelector('video'); if (v) { v.currentTime = 29.6; } }"), time.sleep(1.2)))

            def search():
                page.keyboard.press("/")
                time.sleep(0.4)
                page.keyboard.type("cursor", delay=40)
                time.sleep(1.0)
            take("#/scenes", "search.jpg", settle=2.0, before=search)
        finally:
            server.terminate()
            server.wait()
            browser.close()
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
