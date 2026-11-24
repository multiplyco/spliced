# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///
"""The app in a real browser, against the fixture project: every view loads clean, media plays, a change made in
the page reaches the project's state, and another site's page can change nothing.

  uv run tests/smoke.py                # headless; uses the installed Chrome, or Playwright's own Chromium
  uv run tests/smoke.py --show         # watch it

It starts its own server on a free port with a throwaway copy of tests/fixture, so the project you are working
on (and the toolbox you have open) are never touched. Exit code 0 when everything passed.
"""
import http.server, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time, urllib.request

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402  (named(): the names the app must never show)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SENTINEL = "SENTINEL_DO_NOT_SERVE"
VIEWS = ["#/scenes", "#/scene/demo-one/s01", "#/scenes?role=hook", "#/films", "#/film/demo-two", "#/styles", "#/moves", "#/moments",
         "#/boards", "#/boards/Fixture%20board", "#/build", "#/build/demo", "#/assets", "#/assets?view=sound", "#/profiles", "#/settings", "#/setup"]

fails, checks = [], [0]


def check(name, ok, detail=""):
    checks[0] += 1
    print(f"{'ok  ' if ok else 'FAIL'}  {name}" + (f"   {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.load(r)


def main():
    show = "--show" in sys.argv
    tmp = os.path.realpath(tempfile.mkdtemp(prefix="spliced-smoke-"))
    root = os.path.join(tmp, "project")
    shutil.copytree(os.path.join(HERE, "fixture"), root)
    with open(os.path.join(root, ".env"), "w") as f:
        f.write(f"UNSPLASH_ACCESS_KEY={SENTINEL}\n")
    # an import that has been downloaded and analysed and now waits for the person's own AI (the fixture has no runner)
    os.makedirs(os.path.join(root, ".cache", "imports"))
    with open(os.path.join(root, ".cache", "imports", "w41t1n.json"), "w") as f:
        json.dump({"id": "w41t1n", "src": "https://example.com/a-film", "slug": None, "breakdown": True, "status": "waiting", "created": "2026-01-01T00:00:00",
                   "steps": {"download": {"status": "done"}, "analyse": {"status": "done"}, "breakdown": {"status": "waiting"}, "library": {"status": "todo"}},
                   "step": "breakdown", "activity": "Waiting for your AI", "log": [], "film": "demo-one", "title": "A film that waits", "error": "", "pid": None,
                   "prompt": "Add one reference film..."}, f)
    with open(os.path.join(root, ".cache", "imports", "d0n3d0.json"), "w") as f:   # and one that finished a while ago: history
        json.dump({"id": "d0n3d0", "src": "https://example.com/an-older-film", "slug": None, "breakdown": True, "status": "done", "created": "2025-12-01T00:00:00", "ended": "2025-12-01T00:10:00",
                   "steps": {k: {"status": "done"} for k in ("download", "analyse", "breakdown", "library")}, "activity": "In the library: demo-two, 3 scenes", "log": [], "film": "demo-two",
                   "title": "A film from before", "error": "", "pid": None, "scenes": 3}, f)
    port, evil_port = free_port(), free_port()
    base = f"http://localhost:{port}"
    log = open(os.path.join(tmp, "server.log"), "w")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
    env["XDG_CONFIG_HOME"] = os.path.join(tmp, "config")   # the list of opened projects (projects.py): the test's own, not the person's
    env["SPLICED_PICKER"] = "false"   # the system's folder picker never opens on the screen of whoever runs this: it answers "cancelled"
    server = subprocess.Popen([sys.executable, os.path.join(REPO, "spliced", "toolbox.py"), "--port", str(port), "--no-open"],
                              env={**env, "SPLICED_PROJECT": root}, stdout=log, stderr=subprocess.STDOUT)

    # another site: a page on a different origin that tries to change our boards, the way a hostile page would
    class Evil(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            body = (f"<!doctype html><title>evil</title><form id=f method=post action='{base}/api/ops' enctype='text/plain' target=sink>"
                    "<input name='{\"ops\":[{\"op\":\"board.create\",\"name\":\"Made by a form\"}],\"x\":\"' value='\"}'></form><iframe name=sink></iframe>").encode()
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    evil = http.server.HTTPServer(("127.0.0.1", evil_port), Evil)
    threading.Thread(target=evil.serve_forever, daemon=True).start()

    try:
        for _ in range(900):  # the first start builds the library index
            try:
                info = get(base + "/api/info"); break
            except OSError:
                time.sleep(0.1)
        else:
            sys.exit("the server didn't start:\n" + open(log.name).read())
        check("the server serves the fixture, not this repo", os.path.realpath(info["root"]) == root, info["root"])

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=not show, channel="chrome")
            except Exception:  # noqa: BLE001  (no Chrome installed: Playwright's own, after `playwright install chromium`)
                browser = p.chromium.launch(headless=not show)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.add_init_script("localStorage.setItem('cr.welcomed', '1')")   # this pass is someone who has been here before
            problems, bodies = [], []
            page.on("console", lambda m: problems.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
            page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
            page.on("response", lambda r: problems.append(f"{r.status} {r.url}") if r.status >= 400 else None)
            page.on("requestfailed", lambda r: problems.append(f"failed {r.url} ({r.failure})") if "/api/events" not in r.url else None)

            r = page.goto(base + "/")
            check("/ lands on /app/", page.url.startswith(base + "/app/"), page.url)
            try:
                page.wait_for_selector("#main [class]", timeout=30000)
            except Exception:
                print("THE APP DID NOT START. problems:", problems[:6], "| body:", page.evaluate("() => document.body.innerText.slice(0, 300)"),
                      "| scripts ok:", page.evaluate("() => ({ SP: !!window.SP, LIBRARY: !!window.LIBRARY, SPLICED: !!window.SPLICED, main: document.querySelector('#main')?.innerHTML.slice(0, 200) })"))
                raise
            for view in VIEWS:
                problems.clear()
                page.evaluate("h => { location.hash = h }", view)
                page.wait_for_timeout(700)
                page.wait_for_load_state("networkidle")
                if view == "#/setup":   # its answer comes from the server asking each program for its version
                    page.wait_for_selector(".su section", timeout=30000)
                broken = page.evaluate("() => [...document.images].filter(i => i.complete && i.getAttribute('src') && !i.naturalWidth).map(i => i.getAttribute('src'))")
                text = page.evaluate("() => document.querySelector('#main').innerText.length + document.querySelector('#detail').innerText.length")
                html = page.content()
                if view == "#/setup":   # Setup names Claude Code and Codex as programs one can install: that is not the app's voice
                    html = html.replace("Claude", "")
                if "${SP" in html or "Claude" in html:
                    problems.append("the page shows an unfilled ${SP...}" if "${SP" in html else "the page says Claude in a project that names no AI: " + html[max(0, html.index("Claude") - 70):html.index("Claude") + 30].replace("\n", " "))
                # every control says what it is: text, a label or a tooltip (an icon alone is a riddle to someone new)
                mute = page.evaluate("""() => [...document.querySelectorAll('button, a.icon-btn, [role=button]')].filter(b => b.offsetParent && !b.textContent.trim()
                    && !b.getAttribute('aria-label') && !b.getAttribute('title') && !b.dataset.tip).map(b => (b.id ? '#' + b.id : '') + '.' + b.className + (b.dataset.a ? '[' + b.dataset.a + ']' : '')).slice(0, 6)""")
                if mute:
                    problems.append("controls with no label or tooltip: " + ", ".join(mute))
                check(f"{view} loads clean", not problems and not broken and text > 0, "; ".join(problems[:4] + [f"broken image {b}" for b in broken[:3]] + ([] if text else ["nothing rendered"])))

            follow = page.evaluate("() => { const b = document.querySelector('#status [data-a=\"follow\"]'); return b?.getAttribute('title') || b?.dataset.tip || '' }")
            check("the app calls it your AI when the project names none", "your AI" in follow, follow)

            # tooltips are the app's own: a title is taken over on hover and shown at once after the first
            page.evaluate("h => { location.hash = h }", "#/scenes")
            page.wait_for_timeout(300)
            page.hover('#views a[data-view="boards"]')
            page.wait_for_selector(".tip.on", timeout=3000)
            tipped = page.evaluate("() => ({ text: document.querySelector('.tip.on').innerText, native: document.querySelector('#views a[data-view=\"boards\"]').getAttribute('title'), inside: (r => r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight)(document.querySelector('.tip.on').getBoundingClientRect()) })")
            check("a tooltip is ours, not the browser's", "scripts" in tipped["text"] and tipped["native"] is None and tipped["inside"], str(tipped))
            page.hover('#views a[data-view="build"]')
            page.wait_for_timeout(120)
            check("moving to the next control shows its tooltip at once", "production" in page.evaluate("() => document.querySelector('.tip.on')?.innerText || ''"), "")
            page.mouse.move(700, 500)
            page.wait_for_timeout(150)
            check("and it goes when the pointer leaves", page.evaluate("() => !document.querySelector('.tip.on')"), "")

            # a view explains itself the first time, and only then
            def explainer(view):
                page.evaluate("h => { location.hash = h }", view)
                page.wait_for_timeout(700)
                return page.evaluate("() => { const e = document.querySelector('#main .explain'); return e ? { key: e.dataset.key, title: e.querySelector('.ex-text b').innerText, after: e.previousElementSibling?.classList.contains('view-head'), n: document.querySelectorAll('#main .explain').length } : null }")
            seen = {v: explainer(v) for v in ("#/scenes", "#/boards", "#/boards/Fixture%20board", "#/build", "#/build/demo", "#/assets", "#/films", "#/settings")}
            want = {"#/scenes": "scenes", "#/boards": "boards", "#/boards/Fixture%20board": "board", "#/build": "build", "#/build/demo": "build-film", "#/assets": "assets", "#/films": None, "#/settings": None}
            check("each main view explains itself under its heading, once on the page", all((seen[v] or {}).get("key") == k for v, k in want.items()) and all(e["after"] and e["n"] == 1 for e in seen.values() if e), str(seen))
            explainer("#/scenes")
            page.click('#main .explain [data-a="ok"]')
            check("Got it puts that one away for good", explainer("#/boards") is not None and explainer("#/scenes") is None, "")
            explainer("#/build/demo")
            page.click('#main > .explain [data-a="ok"]')
            page.reload()
            page.wait_for_selector(".snd", state="attached", timeout=15000)   # (the panel is there but closed until Sound is turned on)
            page.wait_for_function("() => !!document.querySelector('.snd .explain')", timeout=60000)   # its first analysis of a film takes a moment
            snd = page.evaluate("() => [...document.querySelectorAll('#main .explain')].map(e => [e.dataset.key, !!e.closest('.snd')])")
            check("the Sound panel waits its turn, then explains itself in its own place", snd == [["sound", True]], str(snd))
            explainer("#/scenes")
            page.evaluate("() => window.CR.commands.get('app.explain').run()")
            page.wait_for_timeout(300)
            check("About this view shows it again when asked", page.evaluate("() => document.querySelector('#main .explain')?.dataset.key") == "scenes", "")
            page.evaluate("h => { location.hash = h }", "#/scene/demo-one/s01")
            page.wait_for_timeout(500)
            page.evaluate("h => { location.hash = h }", "#/boards")
            page.wait_for_timeout(500)
            page.click('#main .explain [data-a="all"]')
            check("Hide all of these puts every one away", all(explainer(v) is None for v in ("#/boards", "#/build", "#/assets", "#/build/demo")), "")
            page.evaluate("h => { location.hash = h }", "#/settings")
            page.wait_for_selector('.set [data-a="explainers"]', timeout=5000)
            page.click('.set [data-a="explainers"]')
            check("Settings brings them back", (explainer("#/scenes") or {}).get("key") == "scenes" and (explainer("#/build") or {}).get("key") == "build", "")
            page.click('#main .explain [data-a="all"]')   # the rest of this pass is someone who has put them away

            # a render's frames are one stack in Assets, and each frame is still its own asset
            page.evaluate("h => { location.hash = h }", "#/assets")
            page.wait_for_selector(".as-grid .as-tile", timeout=10000)
            page.wait_for_timeout(500)
            grid = page.evaluate("() => ({ tiles: document.querySelectorAll('.as-grid .as-tile').length, stacks: [...document.querySelectorAll('.as-tile.stack')].map(t => [t.querySelector('.nm').innerText, t.querySelector('.stk').innerText.trim()]) })")
            check("six frames of a render show as one stack", grid["stacks"] == [["spin", "6 frames"]] and grid["tiles"] == 2, str(grid))
            box = page.locator(".as-tile.stack .th").bounding_box()
            first = page.evaluate("() => document.querySelector('.as-tile.stack img').getAttribute('src')")
            page.mouse.move(box["x"] + 4, box["y"] + box["height"] / 2)
            page.wait_for_timeout(150)
            left = page.evaluate("() => document.querySelector('.as-tile.stack img').getAttribute('src')")
            page.mouse.move(box["x"] + box["width"] - 4, box["y"] + box["height"] / 2)
            page.wait_for_timeout(150)
            right = page.evaluate("() => document.querySelector('.as-tile.stack img').getAttribute('src')")
            check("moving across a stack runs through its frames", left.endswith("f_0001.png") and right.endswith("f_0006.png") and first.endswith("f_0004.png"), f"{first} {left} {right}")
            page.click(".as-tile.stack")
            page.wait_for_selector(".as-grid.frames .as-tile", timeout=5000)
            opened = page.evaluate("() => ({ hash: decodeURIComponent(location.hash), frames: [...document.querySelectorAll('.as-grid.frames .nm')].map(n => n.innerText), meta: document.querySelector('.view-head .meta').innerText })")
            check("opening a stack shows every frame", opened["frames"] == [f"Frame {n:04d}" for n in range(1, 7)] and "stack=remotion/public/films/demo/shots/spin/f_#.png" in opened["hash"] and "6 frames, 0001 to 0006" in opened["meta"], str(opened))
            page.click(".as-grid.frames .as-tile:nth-child(2)")
            page.wait_for_selector(".as-lb .as-step", timeout=5000)
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(300)
            lb = page.evaluate("() => ({ step: document.querySelector('.as-lb .as-step span').innerText, file: document.querySelector('.as-lb .mono').innerText, n: document.querySelectorAll('.as-lb').length })")
            check("a frame opens on its own, and the arrows step to the next", lb == {"step": "Frame 3 of 6 in spin", "file": "remotion/public/films/demo/shots/spin/f_0003.png", "n": 1}, str(lb))
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            page.click('.view-head [data-a="back"]')
            page.wait_for_selector(".as-tile.stack", timeout=5000)
            check("and back shows the stack again", page.evaluate("() => location.hash") == "#/assets", page.evaluate("() => location.hash"))
            page.evaluate("h => { location.hash = h }", "#/build/demo/assets")
            page.wait_for_selector(".bx-asset", state="attached", timeout=10000)   # (a folder of unused files starts folded)
            tab = page.evaluate("() => [...document.querySelectorAll('.bx-asset')].map(a => [a.classList.contains('stack'), a.querySelector('.nm').textContent, a.querySelector('.nm').dataset.copy])")
            check("Build's Assets tab shows the stack as one card with the frames' path", [True, "spin · 6 frames", "films/demo/shots/spin/f_####.png"] in tab and len(tab) == 2, str(tab))

            # every view that lists things has a search bar, and each filters what is on screen
            def bar(view, typed, cards):
                page.evaluate("h => { location.hash = h }", view)
                page.wait_for_selector(".view-head .vsearch input", timeout=8000)
                page.fill(".view-head .vsearch input", typed)
                page.wait_for_timeout(350)
                return page.evaluate("""c => ({ shown: [...document.querySelectorAll(c)].filter(e => !e.classList.contains('vs-hide') && e.offsetParent).length, all: document.querySelectorAll(c).length,
                    meta: document.querySelector('.view-head .meta')?.innerText || '', none: !!document.querySelector('.vs-none'), hash: location.hash, focused: document.activeElement?.closest('.vsearch') != null })""", cards)
            for view, typed, cards, want_shown, want_all, says in (("#/films", "explainer", ".films .film", 1, 2, "1 of 2 films"), ("#/films", "sharpen", ".films .film", 1, 2, "1 of 2"),
                                                              ("#/moves", "whip", ".moves .move", 1, 2, "1 of 2 named"), ("#/boards", "here it is", ".bgrid .bcard", 1, None, "1 of"),
                                                              ("#/film/demo-two", "logo", ".grid > .card", 1, 3, "1 of 3 scenes"), ("#/styles", "dark", ".st-look, .st-move, .st-struct, .st-tier", 1, None, "1 of"),
                                                              ("#/build", "end card", ".bx-films .bx-film", 1, 1, "1 of 1 films")):
                r = bar(view, typed, cards)
                check(f"{view}: searching “{typed}” leaves what matches", r["shown"] == want_shown and (want_all is None or r["all"] == want_all) and says in r["meta"] and not r["none"] and r["focused"] and r["hash"].startswith(view.split("?")[0]), str(r))
            r = bar("#/films", "bfkn zzz", ".films .film")   # letters that are single-key shortcuts elsewhere: here they are just typing
            check("a search with no match says so, and typing in it is only typing", r["shown"] == 0 and r["none"] and r["hash"] == "#/films", str(r))
            page.evaluate("h => { location.hash = h }", "#/moves")
            page.wait_for_selector(".moves .move", timeout=5000)
            page.evaluate("h => { location.hash = h }", "#/films")
            page.wait_for_selector(".films .film", timeout=5000)
            page.wait_for_timeout(200)
            check("going somewhere else and back finds the list whole again", page.evaluate("() => ({ q: document.querySelector('.vsearch input').value, shown: document.querySelectorAll('.films .film:not(.vs-hide)').length })") == {"q": "", "shown": 2}, "")
            page.fill(".view-head .vsearch input", "bfkn zzz")
            page.wait_for_timeout(300)
            page.click(".vs-none .vs-clear")
            page.wait_for_timeout(250)
            check("clearing the search brings everything back", page.evaluate("() => document.querySelectorAll('.films .film:not(.vs-hide)').length") == 2 and page.evaluate("() => document.querySelector('.vsearch input').value") == "", "")
            page.evaluate("h => { location.hash = h }", "#/styles")
            page.wait_for_selector(".vsearch input", timeout=8000)
            page.fill(".vsearch input", "dark")
            page.wait_for_timeout(350)
            check("Styles hides the sections with nothing left in them", page.evaluate("() => [...document.querySelectorAll('.st-sec')].filter(s => !s.classList.contains('vs-hide')).length") == 1, "")
            page.fill(".vsearch input", "")

            # the global search reaches all of it, and lands where the thing lives
            def find(typed):
                page.evaluate("() => window.CR.openPalette()")
                page.wait_for_selector(".cmdk input", timeout=5000)
                page.fill(".cmdk input", typed)
                page.wait_for_timeout(1500)   # films in production arrive from the server a moment after it opens
                return page.evaluate("() => [...document.querySelectorAll('.pal-list .pal-g')].map(g => g.childNodes[0].textContent.trim())")
            groups = find("whip")
            check("the global search finds a scene and a named move for the same word", "Scenes" in groups and "Moves" in groups, str(groups))
            page.evaluate("() => [...document.querySelectorAll('.pal-it')].find(b => b.innerText.includes('The whip')).click()")
            page.wait_for_selector(".moves .move:not(.vs-hide)", timeout=5000)
            page.wait_for_timeout(300)
            landed = page.evaluate("() => ({ hash: location.hash, q: document.querySelector('.vsearch input')?.value, shown: document.querySelectorAll('.moves .move:not(.vs-hide)').length })")
            check("and opens Moves already narrowed to it", landed == {"hash": "#/moves?q=The%20whip", "q": "The whip", "shown": 1}, str(landed))
            groups = find("here it is")
            check("a line of a board's script is found", "Board beats" in groups, str(groups))
            page.keyboard.press("Escape")
            groups = find("end card")
            check("a beat of a film in production is found", "Beats in production" in groups, str(groups))
            page.evaluate("() => [...document.querySelectorAll('.pal-it')].find(b => b.innerText.includes('End card')).click()")
            page.wait_for_selector(".bx-row", timeout=10000)
            page.wait_for_timeout(600)
            at = page.evaluate("() => ({ hash: location.hash, sel: document.querySelector('.bx-row.sel')?.dataset.i })")
            check("and Build opens on that beat", at == {"hash": "#/build/demo?beat=end-card", "sel": "2"}, str(at))
            groups = find("stem")
            check("a film word is found too", "Words" in groups, str(groups))
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)

            # the volume knob remembered at zero: turning the sound on brings it back up, so sound on is never silence
            page.evaluate("() => localStorage.setItem('cr.vol', '0')")
            page.evaluate("h => { location.hash = h }", "#/build/demo")
            page.reload()
            page.wait_for_selector('.bx-tr [data-a="mute"]', timeout=10000)
            page.wait_for_timeout(400)
            before = page.evaluate("() => document.querySelector('#bx-vol').getAttribute('aria-valuenow')")
            page.click('.bx-tr [data-a="mute"]')
            page.wait_for_timeout(200)
            vol = page.evaluate("""() => ({ on: document.querySelector('.bx-tr [data-a="mute"]').getAttribute('aria-pressed'),
                knob: document.querySelector('#bx-vol').getAttribute('aria-valuenow'), kept: localStorage.getItem('cr.vol') })""")
            check("sound on with the volume knob at zero turns the level back up", before == "0" and vol == {"on": "true", "knob": "1", "kept": "1.000"}, f"{before} {vol}")
            page.click('.bx-tr [data-a="mute"]')
            page.wait_for_timeout(200)

            # the timeline zooms: = shows a shorter stretch with finer times on the ruler, the same in the sound lanes; 0 shows the whole film again
            tl = lambda: page.evaluate("""() => ({ z: document.querySelector('#bx-zoom [data-a="zfit"]').textContent, end: document.querySelector('#bx-tl-b').textContent,
                step: document.querySelector('#bx-ruler').dataset.step, labels: document.querySelectorAll('#bx-ruler i.M span').length, where: !document.querySelector('#bx-tlov').hidden,
                wide: Math.round(document.querySelector('#bx-tl-in').getBoundingClientRect().width / document.querySelector('#bx-tl').getBoundingClientRect().width) })""")
            page.evaluate("() => document.activeElement?.blur()")
            fit = tl()
            page.keyboard.press("=")
            page.keyboard.press("=")
            page.wait_for_timeout(300)
            near = tl()
            page.keyboard.press("0")
            page.wait_for_timeout(200)
            back = tl()
            check("the timeline zooms in to finer times and back out to the whole film",
                  fit["z"] == "1×" and fit["end"] == "0:06.00" and not fit["where"] and near["z"] == "4×" and near["end"] == "0:01.50" and near["wide"] == 4 and near["where"]
                  and near["step"] != fit["step"] and near["labels"] >= 3 and back == fit, f"{fit} {near} {back}")

            # a paused film leaves the page alone: nothing is rewritten frame after frame (it kept WebKit repainting)
            idle = page.evaluate("""() => new Promise((done) => { const v = document.querySelector('.bx-stage video'); if (v) v.pause();
                setTimeout(() => { const seen = []; const mo = new MutationObserver((ms) => ms.forEach((m) => seen.push((m.target.id || m.target.parentElement?.id || m.target.nodeName) + ' ' + m.type)));
                mo.observe(document.querySelector('.bx-tr') || document.body, {subtree: true, attributes: true, childList: true, characterData: true});
                setTimeout(() => { mo.disconnect(); done(seen.slice(0, 6)); }, 1000); }, 300); })""")
            check("a paused film rewrites nothing in the transport while it sits", idle == [], str(idle))

            # a note says when it was written, and done notes can be taken off the beat bar (they stay in the Notes tab)
            ids = page.evaluate("""async () => { const send = (u, method, b) => fetch(u, { method, body: JSON.stringify(b) }).then((r) => r.json());
                await send('/api/productions/demo/pins', 'POST', { t: 4.5, note: 'An open note', by: 'person' });
                const all = await send('/api/productions/demo/pins', 'POST', { t: 5.2, note: 'A fixed note', by: 'person' });
                await send('/api/productions/demo/pins/' + all.find((x) => x.note === 'A fixed note').id, 'PATCH', { done: 'Fixed it' });
                return all.map((x) => x.id); }""")
            page.evaluate("h => { location.hash = h }", "#/build/demo/notes")
            page.reload()
            page.wait_for_selector(".bx-note", timeout=10000)
            pins = lambda: page.evaluate("""() => ({ bar: [...document.querySelectorAll('.bx-pin')].map((p) => p.classList.contains('done')), btn: document.querySelector('#bx-donepins').innerText.trim(),
                list: document.querySelectorAll('.bx-note').length, at: [...document.querySelectorAll('.bx-note .at')].map((a) => a.textContent), done: document.querySelector('.bx-note.done .dn').textContent })""")
            shown = pins()
            check("each note says the date and time it was added, a done one when it was done",
                  len(shown["at"]) == 2 and all(re.fullmatch(r"added .*\d.*\d{1,2}[:.]\d{2}.*", a) for a in shown["at"]) and re.match(r"Done .*\d{1,2}[:.]\d{2}.*: Fixed it", shown["done"]), str(shown))
            page.click("#bx-donepins")
            hidden = pins()
            check("done notes come off the beat bar and stay in the list", (shown["bar"], shown["btn"]) == ([False, True], "Hide 1 done note")
                  and (hidden["bar"], hidden["btn"], hidden["list"]) == ([False], "Show 1 done note", 2), f"{shown} {hidden}")
            page.reload()
            page.wait_for_selector(".bx-note", timeout=10000)
            kept = pins()
            page.click("#bx-donepins")
            check("the choice is remembered, and one click brings them back", kept["bar"] == [False] and pins()["bar"] == [False, True], str(kept))
            page.evaluate("ids => Promise.all(ids.map((i) => fetch('/api/productions/demo/pins/' + i, { method: 'DELETE' })))", ids)

            # a note on the sound sits in the Notes tab with the frame notes, in time order, marked with its kind
            page.evaluate("ids => fetch('/api/productions/demo/pins', { method: 'POST', body: JSON.stringify({ t: 4.5, note: 'A frame note', by: 'person' }) })", ids)
            page.evaluate("() => fetch('/api/productions/demo/sound/sfx-swoosh', { method: 'PATCH', body: JSON.stringify({ kind: 'sfx', label: 'the swoosh', start: 2.0, end: 2.4, ref: 'swoosh', note: 'Remove this swoosh' }) })")
            page.reload()
            page.wait_for_selector(".bx-note.snd", timeout=10000)
            sn = page.evaluate("""() => ({ order: [...document.querySelectorAll('.bx-nlist .bx-note')].map((n) => n.classList.contains('snd') ? 'sound' : 'frame'),
                kind: document.querySelector('.bx-note.snd .kind')?.textContent, body: document.querySelector('.bx-note.snd .body')?.textContent,
                pointer: document.querySelector('.bx-nother')?.innerText || '' })""")
            check("a sound note shows in the Notes tab with the frame notes, by time, marked SFX",
                  sn["order"] == ["sound", "frame"] and sn["kind"] == "SFX" and sn["body"] == "Remove this swoosh" and "sound note" not in sn["pointer"], str(sn))
            page.evaluate("() => fetch('/api/productions/demo/sound/sfx-swoosh', { method: 'PATCH', body: JSON.stringify({ note: '' }) })")
            page.evaluate("() => fetch('/api/productions/demo').then((r) => r.json()).then((p) => Promise.all((p.pins || []).map((x) => fetch('/api/productions/demo/pins/' + x.id, { method: 'DELETE' }))))")

            # Settings says which Spliced this is, and What's new lists what changed in a sheet that scrolls
            page.evaluate("h => { location.hash = h }", "#/settings")
            page.wait_for_selector('.set [data-a="whatsnew"]', timeout=5000)
            page.wait_for_function("() => !document.querySelector('.set-new').hidden", timeout=5000)
            about = page.evaluate("() => ({ row: document.querySelector('.set [data-a=\"whatsnew\"]').closest('.set-row').innerText, dot: document.querySelector('#status [data-a=\"settings\"]').classList.contains('has-news') })")
            check("Settings names the version that is running, and says there is news", re.search(r"Version \d+\.\d+\.\d+", about["row"]) and "new" in about["row"] and about["dot"], str(about))
            page.click('.set [data-a="whatsnew"]')
            page.wait_for_selector(".cl-sheet .cl-entry", timeout=5000)
            page.wait_for_timeout(600)
            cl = page.evaluate("""() => { const l = document.querySelector('.cl-list'); return { n: l.querySelectorAll('.cl-entry').length, dates: [...l.querySelectorAll('time')].map(t => t.dateTime),
                scrolls: l.scrollHeight > l.clientHeight + 40, fits: document.querySelector('.cl-sheet').getBoundingClientRect().bottom <= innerHeight, head: document.querySelector('.cl-head').innerText,
                leads: l.querySelectorAll('.cl-lead').length, raw: l.innerText.includes('![') || l.innerText.includes('##'), imgs: [...l.querySelectorAll('img')].length } }""")
            check("What's new lists the changes, newest first, and scrolls inside the window", cl["n"] >= 5 and cl["leads"] == cl["n"] and all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) for d in cl["dates"])
                  and cl["scrolls"] and cl["fits"] and not cl["raw"] and cl["imgs"] >= 1 and re.search(r"Spliced \d+\.\d+", cl["head"]), str(cl))
            for part in range(1, 9):   # past every picture in turn: they load as they come near
                page.evaluate("(p) => { const l = document.querySelector('.cl-list'); l.scrollTop = l.scrollHeight * p / 8 }", part)
                page.wait_for_timeout(250)
            page.wait_for_timeout(500)
            check("its pictures load", page.evaluate("() => [...document.querySelectorAll('.cl-list img')].every(i => i.complete && i.naturalWidth > 0)"), "")
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
            after = page.evaluate("() => ({ marker: document.querySelector('.set-new').hidden, dot: document.querySelector('#status [data-a=\"settings\"]').classList.contains('has-news'), open: !!document.querySelector('.cl-sheet') })")
            check("once opened, it is no longer news", after == {"marker": True, "dot": False, "open": False}, str(after))

            # commands the app shows are written through the one entry point
            page.evaluate("h => { location.hash = h }", "#/styles")
            page.wait_for_timeout(600)
            styles = page.evaluate("() => document.querySelector('#main').innerText")
            check("commands shown in the app go through the entry point", re.search(r"(spliced|cli\.py) library", styles) and "build_library.py" not in styles and "${SP" not in page.content(),
                  styles[-300:].replace("\n", " | "))

            # an import waiting for the person's AI says so, and says what to tell it
            page.evaluate("h => { location.hash = h }", "#/scenes")
            page.click("#add-ref")
            page.wait_for_selector(".imp-list .imp-job", timeout=5000)
            sheet = page.evaluate("() => document.querySelector('.imp-sheet, .imp')?.innerText || document.body.innerText")
            check("an import that waits for your AI says so", "needs your AI" in sheet and re.search(r"(spliced|cli\.py) imports next", sheet) and "waits for your AI" in sheet and "A film that waits" in sheet,
                  sheet[-400:].replace("\n", " | "))
            # the sheet's history can be put away: what is under way stays, what has finished goes, and it is remembered
            shown = lambda: page.evaluate("() => ({ jobs: [...document.querySelectorAll('.imp-list .imp-job b')].map(b => b.innerText), head: document.querySelector('.imp-rec h3')?.innerText.toLowerCase(), toggle: document.querySelector('.imp-toggle')?.innerText })")
            before = shown()
            page.click(".imp-toggle")
            page.wait_for_timeout(200)
            tucked = shown()
            check("the Add reference sheet can put its history away", before["jobs"] == ["A film that waits", "A film from before"] and before["toggle"] == "Hide history"
                  and tucked == {"jobs": ["A film that waits"], "head": "under way", "toggle": "Show history (1)"}, f"{before} -> {tucked}")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            page.click("#add-ref")
            page.wait_for_selector(".imp-list .imp-job", timeout=5000)
            check("and it stays away until asked back", shown()["jobs"] == ["A film that waits"], str(shown()))
            page.click(".imp-toggle")
            page.wait_for_timeout(200)
            check("Show history brings it back", shown()["jobs"] == ["A film that waits", "A film from before"], str(shown()))
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)

            # media really comes through /project/
            page.evaluate("h => { location.hash = h }", "#/scene/demo-two/s02")
            page.wait_for_selector("#detail video", timeout=5000)
            ready = page.wait_for_function("() => { const v = document.querySelector('#detail video'); return v && v.readyState >= 1 && v.videoWidth }", timeout=8000).json_value()
            src = page.evaluate("() => document.querySelector('#detail video').currentSrc")
            detail = page.evaluate("() => document.querySelector('#detail').innerText")
            check("the scene's copy names no company (Recreate is plain: the profile is chosen where the brief is copied)", "Recreate" in detail and "Recreate for" not in detail and not support.named(detail), detail[:200].replace("\n", " | "))
            check("a reference film with a space and brackets in its name plays", ready == 320 and "/project/reference/Demo%20two%20%5Babc123%5D.mp4" in src, f"{ready} {src}")
            # a note on a scene: N puts the caret in the note, and what is typed is on the scene, its button and the Library's count
            page.evaluate("() => document.activeElement?.blur()")
            page.keyboard.press("n")
            in_note = page.evaluate("() => document.activeElement?.id === 'note'")
            page.keyboard.type("Steal the cut")
            page.wait_for_timeout(700)
            noted = page.evaluate("() => !!document.querySelector('#review [data-a=\"note\"].note-on')")
            with open(os.path.join(root, "library", "state.json")) as f:
                saved = json.load(f)["reviews"].get("demo-two/s02", {}).get("note")
            page.keyboard.press("Escape")
            check("N writes a note on the open scene, and it is saved", in_note and noted and saved == "Steal the cut", f"{in_note} {noted} {saved}")
            strips = page.evaluate("() => { location.hash = '#/scenes'; return new Promise(r => setTimeout(() => r([...document.querySelectorAll('.thumb img')].map(i => [i.getAttribute('src'), i.naturalWidth])), 900)) }")
            lib = [(s, w) for s, w in strips if s.startswith("/project/library/references/")]
            check("scene strips come from /project/library/references/", len({s for s, _ in lib}) == 5 and sum(1 for _, w in lib if w > 0) >= 3 and not [s for s, _ in strips if s.startswith("..")],
                  str(strips))  # five scenes in the fixture (the board's tray repeats some); any below the fold load lazily

            # a change made in the page reaches the project (the browser's own Origin and Sec-Fetch-Site pass the guard)
            out = page.evaluate("""async () => { const r = await fetch('/api/ops', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ by: 'browser', ops: [{ op: 'board.create', name: 'Made in the page' }] }) }); return [r.status, (await r.json()).rev] }""")
            with open(os.path.join(root, "library", "state.json")) as f:
                on_disk = json.load(f)
            check("a change made in the page is saved to the project", out[0] == 200 and "Made in the page" in on_disk["boards"], str(out))
            page.evaluate("h => { location.hash = h }", "#/boards")
            page.wait_for_function("() => document.querySelector('#main').innerText.includes('Made in the page')", timeout=5000)
            check("and the open tab shows it", True)

            # another site's page: a fetch and a plain form post, both aimed at /api/ops
            other = browser.new_page()
            other.goto(f"http://127.0.0.1:{evil_port}/")
            other.evaluate(f"""async () => {{ try {{ await fetch('{base}/api/ops', {{ method: 'POST', mode: 'no-cors',
                body: JSON.stringify({{ ops: [{{ op: 'board.create', name: 'Made by a fetch' }}] }}) }}) }} catch (e) {{}} }}""")
            other.evaluate("() => document.getElementById('f').submit()")
            other.wait_for_timeout(800)
            leaked = other.evaluate(f"async () => {{ try {{ return (await (await fetch('{base}/api/state')).text()).length }} catch (e) {{ return 0 }} }}")
            boards = list(get(base + "/api/state")["boards"])
            check("another site's page can change nothing", not [b for b in boards if b.startswith("Made by")], str(boards))
            check("and can read nothing", leaked == 0, f"read {leaked} bytes of state")

            # the app's other page: the hardware specimen drives its own controls
            page.goto(base + "/app/hardware.html?selftest")
            page.wait_for_function("() => document.querySelector('#selftest').textContent.startsWith('SELFTEST')", timeout=20000)
            st = page.evaluate("() => document.querySelector('#selftest').textContent")
            check("hardware self-test", "ALL PASSED" in st, st.splitlines()[0] + " " + "; ".join(l for l in st.splitlines() if l.startswith("FAIL"))[:300])
            # a stranger's first run: a project made by `spliced init`, with nothing in it yet
            fresh = os.path.join(tmp, "my films")
            subprocess.run([sys.executable, os.path.join(REPO, "spliced", "cli.py"), "init", fresh], check=True, capture_output=True, env=env)
            port2 = free_port()
            log2 = open(os.path.join(tmp, "server2.log"), "w")
            server2 = subprocess.Popen([sys.executable, os.path.join(REPO, "spliced", "toolbox.py"), "--port", str(port2), "--no-open"],
                                       env={**env, "SPLICED_PROJECT": fresh}, stdout=log2, stderr=subprocess.STDOUT)
            try:
                base2 = f"http://localhost:{port2}"
                for _ in range(900):
                    try:
                        get(base2 + "/api/info"); break
                    except OSError:
                        time.sleep(0.1)
                empty = browser.new_page(viewport={"width": 1440, "height": 900})
                problems2 = []
                empty.on("console", lambda m: problems2.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
                empty.on("pageerror", lambda e: problems2.append(f"page error: {e}"))
                empty.on("response", lambda r: problems2.append(f"{r.status} {r.url}") if r.status >= 400 else None)
                empty.goto(base2 + "/")
                empty.wait_for_selector("#main [class]", timeout=30000)
                # someone new is welcomed, once: three steps, none done yet, each leading to a real place
                empty.wait_for_selector(".wl-sheet .wl-step", timeout=10000)
                wl = empty.evaluate("() => ({ text: document.querySelector('.wl-sheet').innerText, done: document.querySelectorAll('.wl-step.done').length, primary: [...document.querySelectorAll('.wl-sheet .primary')].map(b => b.innerText.trim()), film: !!document.querySelector('.wl-film') })")
                has_film = os.path.isfile(os.path.join(REPO, "spliced", "web", "intro.mp4"))
                check("the app ships its introduction film", has_film and os.path.getsize(os.path.join(REPO, "spliced", "web", "intro.mp4")) < 4_000_000, "spliced/web/intro.mp4 is missing or heavier than 4 MB")
                check("someone new is welcomed with the three steps", all(x in wl["text"] for x in ("Welcome to Spliced", "Collect films you love", "Connect your AI", "Make your own")) and wl["done"] == 0 and wl["primary"] == ["Add a reference"] and wl["film"] == has_film, str(wl)[:300])
                if has_film:
                    empty.wait_for_function("() => { const v = document.querySelector('.wl-film'); return v && v.readyState >= 2 && v.currentTime > 0.3 }", timeout=15000)
                    film = empty.evaluate("() => { const v = document.querySelector('.wl-film'); return { muted: v.muted, paused: v.paused, controls: v.controls, wide: v.videoWidth, inside: document.querySelector('.wl-sheet').getBoundingClientRect().bottom <= innerHeight + 1 } }")
                    check("for someone new the introduction film plays by itself, without sound, inside the window", film["muted"] and not film["paused"] and film["controls"] and film["wide"] > 0 and film["inside"], str(film))
                    whole = empty.evaluate("() => { const s = document.querySelector('.wl-sheet'), d = document.querySelector('.wl-sheet [data-a=\"done\"]').getBoundingClientRect(); return { scrolls: s.scrollHeight > s.clientHeight + 2, done: d.bottom <= innerHeight && d.top >= 0, steps: [...document.querySelectorAll('.wl-step')].every(e => e.getBoundingClientRect().bottom <= innerHeight) } }")
                    check("and the film, the three steps and the way out are all in view at once", whole == {"scrolls": False, "done": True, "steps": True}, str(whole))
                lib = empty.evaluate("() => document.querySelector('#main').innerText")
                check("an empty library says how to start, not that nothing matches", "Your library is empty" in lib and "No scene matches" not in lib, lib[:160].replace("\n", " | "))
                empty.click(".wl-step .primary")
                empty.wait_for_selector(".imp-sheet textarea", timeout=5000)
                check("the first step opens Add reference and the welcome steps aside", empty.evaluate("() => !document.querySelector('.wl-sheet')") or empty.evaluate("() => !document.querySelector('.wl.in')"), "")
                # a whole folder: look first, bring nothing in until asked
                empty.click('.imp-sheet [data-a="folder"]')
                empty.fill(".imp-folder input", os.path.join(HERE, "no-such-folder"))
                empty.keyboard.press("Enter")
                empty.wait_for_selector(".imp-found .imp-err", timeout=5000)
                check("a folder that isn't there is said plainly", "there is no folder" in empty.inner_text(".imp-found"), empty.inner_text(".imp-found"))
                empty.fill(".imp-folder input", os.path.join(HERE, "fixture", "remotion", "public", "films", "demo"))
                empty.click('.imp-folder [data-a="look"]')
                empty.wait_for_selector('.imp-found [data-a="bring"]', timeout=5000)
                found = empty.inner_text(".imp-found")
                check("Add a folder looks first: how many of what, and what it will ask of the AI", "demo: 7 pictures" in found and "Bring in 7 files" in found and "already in the library is skipped" in found, found.replace("\n", " | "))
                check("and nothing is queued by looking", empty.evaluate("() => document.querySelectorAll('.imp-job').length") == 0, "")
                empty.keyboard.press("Escape")
                empty.wait_for_timeout(300)
                check("Esc still closes the sheet from the folder field", empty.evaluate("() => !document.querySelector('.imp-sheet')"), "")
                empty.reload()
                empty.wait_for_selector("#main [class]", timeout=30000)
                empty.wait_for_timeout(600)
                check("the welcome is shown once", empty.evaluate("() => !document.querySelector('.wl-sheet')"), "")
                for view in ["#/scenes", "#/films", "#/film/system-moves", "#/moves", "#/styles", "#/moments", "#/boards", "#/build", "#/assets", "#/settings", "#/setup"]:
                    problems2.clear()
                    empty.evaluate("h => { location.hash = h }", view)
                    empty.wait_for_timeout(600)
                    empty.wait_for_load_state("networkidle")
                    text = empty.evaluate("() => document.querySelector('#main').innerText.length")
                    check(f"a new, empty project: {view} loads clean", not problems2 and text > 0, "; ".join(problems2[:4]) or "nothing rendered")
                empty.evaluate("h => { location.hash = h }", "#/scenes")
                empty.wait_for_timeout(400)
                check("a new, empty project names no brand of ours", not support.named(empty.content()), "")
                # Setup says the same as `spliced doctor`, and hands over the step or the request for an AI
                doc = get(base2 + "/api/doctor")
                nxt = next((i for i in doc["items"] if i["id"] == doc["next"]), None)
                empty.evaluate("h => { location.hash = h }", "#/setup")
                empty.wait_for_selector(".su section", timeout=30000)
                setup = empty.evaluate("() => document.querySelector('#main').innerText")
                check("Setup names GitHub as where your app's real code is", "GitHub" in setup and "Your app's real code" in setup, setup[-300:].replace("\n", " | "))
                check("Setup names the next step the doctor does", bool(nxt) and f"Next: {nxt['label']}" in setup and all(l["label"].upper() in setup.upper() for l in doc["levels"]),
                      (nxt or {}).get("label", "no next step") + " | " + setup[:160].replace("\n", " | "))
                empty.context.grant_permissions(["clipboard-read", "clipboard-write"])
                empty.click('[data-a="prompt"]')
                empty.wait_for_timeout(300)
                clip = empty.evaluate("() => navigator.clipboard.readText()")
                check("Copy for your AI hands over a request that names the doctor", "doctor" in clip and "one at a time" in clip, clip[:120])
                empty.click('[data-a="again"]')
                empty.wait_for_selector(".su section", timeout=30000)
                empty.evaluate("h => { location.hash = h }", "#/settings")
                empty.wait_for_timeout(400)
                check("Settings leads to Setup", empty.evaluate("() => !!document.querySelector('.set a[href=\"#/setup\"]')"), "")
                # the browser names the project and offers the others this person has opened (the fixture's, opened first)
                empty.click("#sb-proj")
                empty.wait_for_selector(".pj-pop [data-i]", timeout=5000)
                menu = empty.evaluate("() => ({name: document.querySelector('#sb-proj .sb-proj-n').textContent, rows: [...document.querySelectorAll('.pj-pop [data-i] .rv-t')].map(x => x.textContent), "
                                      "make: document.querySelector('.pj-pop [data-a=\"new\"]').title})")
                check("the sidebar names the project and its menu offers the other one", menu["name"] == "my films" and "Fixture" in menu["rows"] and "setup <folder>" in menu["make"], str(menu))
                empty.keyboard.press("Escape")
                empty.click('.set [data-a="welcome"]')
                empty.wait_for_selector(".wl-sheet .wl-step", timeout=5000)
                empty.wait_for_function("() => /Ready on this machine|Next:/.test(document.querySelector('.wl-sheet').innerText)", timeout=30000)
                check("Settings shows the welcome again, with what is set up on this machine", True, "")
                if has_film:
                    check("shown again, the film waits to be played", empty.evaluate("() => { const v = document.querySelector('.wl-film'); return v.paused && !v.autoplay }"), "")
                # film words explain themselves, in the copy and in one list
                empty.locator('.wl-sheet .term[data-term="beat"]').scroll_into_view_if_needed()
                empty.wait_for_timeout(250)
                empty.hover('.wl-sheet .term[data-term="beat"]')
                empty.wait_for_selector(".tip.tip-term.on", timeout=3000)
                means = empty.evaluate("() => document.querySelector('.tip.on').innerText")
                check("a film word in the copy says what it means", means.startswith("Beat") and "line on a board" in means, means[:120])
                empty.click('.wl-sheet [data-a="words"]')
                empty.wait_for_selector(".gl-sheet .gl-list dt", timeout=5000)
                words = empty.evaluate("() => [...document.querySelectorAll('.gl-list dt')].map(d => d.innerText)")
                empty.wait_for_timeout(300)
                check("the glossary lists the words", len(words) >= 14 and {"Beat", "Board", "Take", "Bed", "Stem"} <= set(words) and not empty.evaluate("() => !!document.querySelector('.wl-sheet')"), str(words))
                empty.keyboard.press("Escape")
                empty.wait_for_timeout(300)
                empty.evaluate("h => { location.hash = h }", "#/film/system-moves")
                empty.wait_for_timeout(500)
                check("Systems explains itself in a project with no film kit", "No film kit in this project yet" in empty.evaluate("() => document.querySelector('#main').innerText"), "")
            finally:
                server2.terminate()
                log2.close()
            # a long library: only the cards near the window exist, every scene has its place, and nothing jumps
            import perf
            long_root = os.path.join(tmp, "long")
            perf.make(long_root, 400)
            port3 = free_port()
            log3 = open(os.path.join(tmp, "server3.log"), "w")
            server3 = subprocess.Popen([sys.executable, os.path.join(REPO, "spliced", "toolbox.py"), "--port", str(port3), "--no-open"],
                                       env={**env, "SPLICED_PROJECT": long_root}, stdout=log3, stderr=subprocess.STDOUT)
            try:
                base3 = f"http://localhost:{port3}"
                for _ in range(900):
                    try:
                        get(base3 + "/api/info"); break
                    except OSError:
                        time.sleep(0.1)
                lp = browser.new_page(viewport={"width": 1440, "height": 900})
                lp.add_init_script("localStorage.setItem('cr.welcomed', '1'); localStorage.setItem('cr.explainOff', '1')")
                errs3 = []
                lp.on("pageerror", lambda e: errs3.append(str(e)))
                lp.goto(base3 + "/app/#/scenes")
                lp.wait_for_selector("#main .card", timeout=60000)
                lp.wait_for_timeout(500)
                count = "() => ({ cards: document.querySelectorAll('#main .card').length, places: document.querySelectorAll('#main .card, #main .card-ph').length, h: document.getElementById('main').scrollHeight })"
                top = lp.evaluate(count)
                check("a long library draws only the cards near the window, with a place for every scene", top["places"] == 400 and 8 <= top["cards"] < 120, str(top))
                lp.evaluate("() => { const m = document.getElementById('main'); m.scrollTop = m.scrollHeight }")
                lp.wait_for_function("() => { const vh = innerHeight; return [...document.querySelectorAll('#main .card')].some(c => { const r = c.getBoundingClientRect(); return r.bottom > 0 && r.top < vh }) && ![...document.querySelectorAll('#main .card-ph')].some(c => { const r = c.getBoundingClientRect(); return r.bottom > 0 && r.top < vh }) }", timeout=8000)
                end = lp.evaluate(count)
                check("scrolling far makes the cards there and lets go of the ones left behind, and the page keeps its length", end["places"] == 400 and end["cards"] < 120 and abs(end["h"] - top["h"]) < 2, f"{top} -> {end}")
                lp.evaluate("() => { document.getElementById('main').scrollTop = 0 }")
                lp.wait_for_timeout(500)
                lp.evaluate("h => { location.hash = h }", "#/scene/film-006/s40")
                lp.wait_for_function("() => document.querySelector('#main .card.sel')?.dataset.key === 'film-006/s40'", timeout=8000)
                check("opening a scene far down finds its place and makes its card", lp.evaluate("() => { const r = document.querySelector('#main .card.sel').getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight }"), "")
                lp.keyboard.press("Escape")
                lp.wait_for_timeout(300)
                for mode, setup in (("the list", "() => document.querySelector('#lib-view [data-v=\"list\"]').click()"), ("captions always shown", "() => { document.querySelector('#lib-view [data-v=\"grid\"]').click(); document.documentElement.classList.add('cards-always'); window.dispatchEvent(new Event('resize')) }")):
                    lp.evaluate(setup)
                    lp.wait_for_timeout(500)
                    if mode != "the list":   # (a change of caption mode comes with a redraw in the app; here: draw again)
                        lp.evaluate("() => { location.hash = '#/films' }"); lp.wait_for_timeout(300); lp.evaluate("() => { location.hash = '#/scenes' }"); lp.wait_for_selector("#main .card"); lp.wait_for_timeout(400)
                    fit = lp.evaluate("() => { const c = document.querySelector('#main .card'), p = document.querySelector('#main .card-ph'); const cc = c._c, pc = p._c; return { card: c.getBoundingClientRect().height, place: p.getBoundingClientRect().height, same: Math.abs(cc.ar - pc.ar) < 0.001 } }")
                    check(f"in {mode}, a place is exactly as tall as its card", fit["same"] and abs(fit["card"] - fit["place"]) < 0.6, str(fit))
                check("no errors in the long library", not errs3, "; ".join(errs3[:3]))
            finally:
                server3.terminate()
                log3.close()
            browser.close()

        # nothing private is reachable, by any address
        for path in ("/.env", "/project/.env", "/app/../.env", "/project/library/../.env", "/project/spliced.json", "/project/library/state.json", "/app/state.json",
                     "/project/library/TAXONOMY.md", "/reference/demo-one.mp4", "/spliced/toolbox.py"):
            req = urllib.request.Request(base + path)
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    code, body = r.status, r.read()
            except urllib.error.HTTPError as e:
                code, body = e.code, e.read()
            check(f"{path} is not served", code == 404 and SENTINEL.encode() not in body, str(code))
    finally:
        server.terminate()
        evil.shutdown()
        log.close()
        if fails:
            print("\nserver log:\n" + open(log.name).read()[-2000:])
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{checks[0] - len(fails)} of {checks[0]} passed" + (f"; failed: {', '.join(fails)}" if fails else ""))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
