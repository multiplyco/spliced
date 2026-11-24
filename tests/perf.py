# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///
"""How fast is the app on a big library? Makes a synthetic project and measures the things a person waits for.

  uv run tests/perf.py                    # 600 scenes (a library today) and 5,000 (one after a folder import)
  uv run tests/perf.py 2000               # one size
  uv run tests/perf.py --json             # the numbers only

The project is made here and thrown away: N films of 50 scenes each, with breakdowns as long as real ones and a
strip picture per scene. Nothing in it is anyone's film. Measured in the installed Chrome, on this machine, so
compare runs with each other, not with someone else's laptop.

What is measured:
  index       the library as the app downloads it: raw, and as sent (gzip). The synthetic breakdowns repeat one
              paragraph, so they compress far better than real ones: trust the raw size, not the sent one
  first card  from opening the app to the first scene on screen
  all cards   until the Library has drawn everything it is going to draw (the cards near the window, and a place
              for every other scene)
  far scroll  jumping two thirds down: until the cards there are on screen, and whether the page shifted under you
  nodes       how many elements the page holds once it has
  memory      the page's JavaScript heap
  filter      choosing a filter: until the Library has drawn the narrower list
  a change    someone else changes a review: until this tab has caught up and drawn again
  search      typing a word in the global search: until results show
"""
import gzip, json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_fixture as fx   # its taxonomy and the shape of a scene

PROSE = ("The headline sits centred on a near-white stage in a geometric grotesk at about nine percent of frame height, ink on paper, "
         "with a hairline grid behind it that fades toward the edges. Each word arrives out of a twelve pixel blur over a third of a second, "
         "staggered by eighty milliseconds, and settles without bounce while the camera pushes in by two percent across the whole scene. ")
ROLES, WORLDS, MOTIONS = ["hook", "demo", "end-card"], ["white-stage", "dark-stage"], ["blur-in", "word-by-word", "scale-up"]


def make(root, scenes, per_film=50):
    strip = os.path.join(HERE, "fixture", "library", "references", "demo-one", "scenes", "s01.jpg")
    os.makedirs(os.path.join(root, "library"))
    with open(os.path.join(root, "spliced.json"), "w") as f:
        json.dump({"format": 1, "name": f"{scenes} scenes", "brand": {"name": ""}}, f)
    for name, text in (("TAXONOMY.md", fx.TAXONOMY), ("STYLES.md", "# Styles\n\nNothing yet.\n"), ("README.md", "# Library\n")):
        with open(os.path.join(root, "library", name), "w") as f:
            f.write(text)
    rows = ["slug\tfile\tsource"]
    for n in range(scenes // per_film):
        slug = f"film-{n:03d}"
        d = os.path.join(root, "library", "references", slug)
        os.makedirs(os.path.join(d, "scenes"))
        sc = []
        for i in range(per_film):
            sid = f"s{i + 1:02d}"
            sc.append(fx.scene(sid, i * 2.0, i * 2.0 + 2.0, f"Scene {i + 1} of film {n}: the {MOTIONS[i % 3]} one", ROLES[i % 3], world=WORLDS[(n + i) % 2], motion=[MOTIONS[i % 3]],
                               transition_in="none" if i == 0 else "hard-cut", on_screen=PROSE, how_it_moves=PROSE, recreate=PROSE, steal=1 + (i % 3)))
            shutil.copy(strip, os.path.join(d, "scenes", f"{sid}.jpg"))
        with open(os.path.join(d, "breakdown.json"), "w") as f:
            json.dump({"title": f"Film {n}", "brand": f"Brand {n % 12}", "source": "synthetic", "file": f"reference/{slug}.mp4", "duration": per_film * 2.0, "format": "16x9",
                       "category": "product-launch", "voice": "on-screen-type-only", "music_feel": ["minimal-pulse"], "summary": PROSE, "tempo": {"bpm": 120},
                       "structure": "Hook, demo, end card.", "style_signature": {"palette": [{"hex": "#FFFFFF", "name": "white"}]},
                       "signature_moves": [{"name": f"Move {n}", "scenes": ["s01"], "description": PROSE[:120], "recreate": "A blur."}], "takeaways": ["One idea per scene."], "scenes": sc}, f)
        rows.append(f"{slug}\treference/{slug}.mp4\tsynthetic")
    with open(os.path.join(root, "library", "references.tsv"), "w") as f:
        f.write("\n".join(rows) + "\n")


def get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.read()


SETTLED = """n => new Promise(done => { let last = -1, same = 0; const tick = () => { const c = document.querySelectorAll('#main .card, #main .card-ph').length;
  same = c === last && c > 0 ? same + 1 : 0; last = c; if (same >= 3 || performance.now() > n) done(performance.now()); else requestAnimationFrame(tick) }; tick() })"""
AFTER_CHANGE = """fn => new Promise(async done => { const main = document.getElementById('main'), t0 = performance.now(); let t;
  const mo = new MutationObserver(() => { clearTimeout(t); t = setTimeout(() => requestAnimationFrame(() => { mo.disconnect(); done(performance.now() - t0 - 120) }), 120) });
  mo.observe(main, { childList: true, subtree: true }); await (0, eval)(fn)(); setTimeout(() => { mo.disconnect(); done(-1) }, 20000) })"""


def measure(scenes):
    tmp = os.path.realpath(tempfile.mkdtemp(prefix="spliced-perf-"))
    root = os.path.join(tmp, "project")
    make(root, scenes)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
    env["XDG_CONFIG_HOME"] = os.path.join(tmp, "config")   # the synthetic project stays out of the person's list of projects
    env["SPLICED_PICKER"] = "false"                        # and no folder picker ever opens on this screen
    server = subprocess.Popen([sys.executable, os.path.join(REPO, "spliced", "toolbox.py"), "--port", str(port), "--no-open"], env={**env, "SPLICED_PROJECT": root},
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://localhost:{port}"
    out = {"scenes": scenes}
    try:
        for _ in range(1800):
            try:
                get(base + "/api/info"); break
            except OSError:
                time.sleep(0.1)
        raw = get(base + "/api/library.js")
        out["index_kb"], out["index_sent_kb"] = round(len(raw) / 1024), round(len(gzip.compress(raw, 6)) / 1024)
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True, channel="chrome")
            except Exception:  # noqa: BLE001
                browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.add_init_script("localStorage.setItem('cr.welcomed', '1'); localStorage.setItem('cr.explainOff', '1'); localStorage.setItem('cr.hoverPlay', '0')")
            page.goto(base + "/app/#/scenes", wait_until="commit")
            page.wait_for_selector("#main .card", timeout=120000)
            out["first_card_ms"] = round(page.evaluate("() => performance.now()"))
            out["all_cards_ms"] = round(page.evaluate(SETTLED, 120000))
            out["cards"] = page.evaluate("() => document.querySelectorAll('#main .card').length")
            out["places"] = page.evaluate("() => document.querySelectorAll('#main .card, #main .card-ph').length")
            # scrolling: jump two thirds down a long library and see how long until cards are there, and that the page did not move under us
            scroll = page.evaluate("""() => new Promise(done => { const m = document.getElementById('main'), to = Math.round(m.scrollHeight * 0.66), t0 = performance.now(); m.scrollTop = to;
              const tick = () => { const vh = innerHeight, on = [...m.querySelectorAll('.card')].filter(c => { const r = c.getBoundingClientRect(); return r.bottom > 0 && r.top < vh }).length,
                empty = [...m.querySelectorAll('.card-ph')].filter(c => { const r = c.getBoundingClientRect(); return r.bottom > 0 && r.top < vh }).length;
                if ((on && !empty) || performance.now() - t0 > 5000) done({ ms: performance.now() - t0, on, empty, moved: Math.abs(m.scrollTop - to), cards: m.querySelectorAll('.card').length }); else requestAnimationFrame(tick) }; requestAnimationFrame(tick) })""")
            out["scroll_ms"], out["scroll_moved"], out["cards_after_scroll"] = round(scroll["ms"]), round(scroll["moved"]), scroll["cards"]
            page.evaluate("() => { document.getElementById('main').scrollTop = 0 }")
            page.wait_for_timeout(600)
            out["nodes"] = page.evaluate("() => document.querySelectorAll('*').length")
            out["heap_mb"] = round(page.evaluate("() => (performance.memory?.usedJSHeapSize || 0) / 1048576"))
            out["filter_ms"] = round(page.evaluate(AFTER_CHANGE, "() => { location.hash = '#/scenes?role=hook' }"))
            page.evaluate("() => { location.hash = '#/scenes' }")
            page.wait_for_timeout(1500); page.evaluate(SETTLED, 60000)
            out["change_ms"] = round(page.evaluate(AFTER_CHANGE, "() => fetch('/api/ops', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ by: 'someone', ops: [{ op: 'review.set', key: 'film-000/s02', patch: { fav: true } }] }) })"))
            page.evaluate("() => window.CR.openPalette()")
            page.wait_for_selector(".cmdk input")
            t0 = time.perf_counter()
            page.fill(".cmdk input", "blur stage")
            page.wait_for_selector(".pal-tile", timeout=30000)
            out["search_ms"] = round((time.perf_counter() - t0) * 1000)
            browser.close()
    finally:
        server.terminate()
        shutil.rmtree(tmp, ignore_errors=True)
    return out


ROWS = [("index_kb", "index, raw", "KB"), ("index_sent_kb", "index, as sent", "KB"), ("first_card_ms", "first card", "ms"), ("all_cards_ms", "library drawn", "ms"), ("cards", "cards drawn", ""),
        ("places", "of scenes", ""), ("scroll_ms", "a far scroll", "ms"), ("scroll_moved", "page moved by", "px"), ("cards_after_scroll", "cards then", ""),
        ("nodes", "nodes", ""), ("heap_mb", "memory", "MB"), ("filter_ms", "filter", "ms"), ("change_ms", "a change", "ms"), ("search_ms", "search", "ms")]


def main():
    sizes = [int(a) for a in sys.argv[1:] if a.isdigit()] or [600, 5000]
    results = [measure(n) for n in sizes]
    if "--json" in sys.argv:
        print(json.dumps(results, indent=1)); return
    print(f"{'':<16}" + "".join(f"{str(r['scenes']) + ' scenes':>16}" for r in results))
    for key, label, unit in ROWS:
        print(f"{label:<16}" + "".join(f"{(format(r[key], ',') + (' ' + unit if unit else '')):>16}" for r in results))


if __name__ == "__main__":
    main()
