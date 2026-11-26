# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""The library toolbox (Spliced): browse, preview, review and collect reference scenes in the browser,
and work on boards live with Claude.

usage:
  spliced open              # serves the app and the project on http://localhost:8765 (or the next free port) and opens it
  spliced --project ~/films/acme open     # another project than the one you are in
  spliced open --port 9000 --no-open
  spliced open --background # start it and return: for an agent, or a terminal you want back. It says where it runs
  spliced open --stop       # stop this project's app, however it was started

Run it in your own terminal so it stays up as long as you like (Ctrl+C stops it). Each project keeps the port it
got (.cache/port), so its tabs and the page's own memory (theme, what you have seen) stay with it.

Live: every change (from a browser tab, or from Claude via board.py) is a small operation applied to the
latest state and pushed to every open tab at once, so nobody's edits overwrite anyone else's. Claude can also ask
the app to show a board or a scene (`board.py show`). State: library/state.json (shared through git).

No restarts: when toolbox.py, toolbox_state.py or film.py change (an edit, a git pull), the server compiles them
and restarts itself on the same port (if the new code doesn't compile it keeps running the old code and the tabs say
so). When the app's own files (library/toolbox/*.js, .css, .html) or the library index change, open tabs reload themselves as
soon as nobody is typing or playing a video.

API:
  GET  /api/state            the whole state (rev, reviews, boards, log)
  POST /api/ops              {by, client, ops: [...]}  see toolbox_state.py for the operations
  POST /api/focus            {by, target}  target = "#/boards/<name>" | "#/scene/<film>/<sNN>" | any app route
  GET  /api/events           server-sent events: {type: "state", rev, by, client, summary} | {type: "focus", target, by}
  GET  /api/info             root folder, rev, live tabs
  GET  /api/projects         the projects opened on this machine   POST /api/projects/open {root}   start one, answer its address
  POST /api/projects/new {folder}   a new project in a new or empty folder, started   POST /api/pick-folder {for}   the system's folder picker
  GET  /api/connect          the agents and chat apps this project is connected to   POST /api/connect {agents, apps: {id: bool}}
  GET  /api/update           is a newer Spliced out (updates.py)
  GET  /api/profiles         the project's profiles (profiles.py)   POST /api/profiles {op: new|set|default|learn|forget|pin|unpin|remove|house|
                             motion-save|motion-remove|draft|site, ...}   POST /api/profiles/<slug>/sources (raw file, X-Filename)  what one is drafted from
                             (site: {profile, url}, a website Spliced reads into its sources, website.py)
  GET  /api/own-films        the project's own films with a whole render, their beats as scenes, for the Library
  GET  /api/fonts            the font families on this machine, and whether Google Fonts may be offered (spliced.json "google_fonts")
Data: .cache/library.json, built by `spliced library` (run it after changing breakdowns) and served as
/api/library.js; the server builds it itself when it is missing or older than the breakdowns.

The Build view pairs films in production with their renders (storyboard beat <-> render slice <-> reference scenes).
Its data comes live from film.py: Remotion films in remotion/src/films/<slug>/storyboard.json and the
HyperFrames films in videos/. Frame thumbnails are cut with ffmpeg and cached in .cache/frames.
  GET  /api/productions, /api/productions/<slug>, /api/frame?file=&t=&w=   POST /api/productions   PATCH .../beats/<id>
  PATCH /api/productions/<slug> {notes_mode: auto|manual}   (who picks up the notes: spliced film mode / watch)
  POST /api/productions/<slug>/pins {t, note, render?}   PATCH/DELETE .../pins/<id> {note?, t?, status?, done?}  (notes at a moment)
  POST /api/reveal {path, how: reveal|open|folder}   show a repo file in Finder, or open it
  POST /api/assets/upload (raw file; X-Filename, X-Film)   the person's own files into a film (from the computer)
  GET  /api/stock/search?q=&kind=photo|video&source=   POST /api/stock/get {id, film, name?}   free footage (stock.py)
  GET  /api/uploads   POST /api/uploads (raw file, X-Filename)   POST /api/uploads/url {url}   PATCH/DELETE /api/uploads/<id>
                                         uploaded references: images, GIFs, clips (uploads.py), shown in Scenes as uploads/<id>
  GET  /api/assets                      the asset library: every still, clip and sound across films (film.py)
  GET  /api/imports   POST /api/imports {urls, slug?, breakdown?}   POST .../<id>/cancel|retry   DELETE .../<id>
                                         Add reference: paste a link, it's downloaded, analysed, broken down (importer.py)
  GET  /api/productions/<slug>/assets   every still and clip the film uses (spliced film assets)
  GET  /api/productions/<slug>/takes   PATCH /api/productions/<slug>/takes/<track> {take}   (sound takes: spliced film takes)
"""
import atexit, gzip, http.server, json, os, re, signal, socketserver, subprocess, sys, threading, time, urllib.request, webbrowser
from urllib.parse import parse_qs, unquote, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _mtimes(paths):
    out = {}
    for p in paths:
        try:
            st = os.stat(p)
            out[p] = (st.st_mtime, st.st_size)
        except FileNotFoundError:
            out[p] = None
    return out


# The server's own Python, stamped before it is imported: an edit that lands while the server is (re)starting
# is then seen as a change by the code watcher, instead of being missed until the next edit.
PY_FILES = [os.path.join(HERE, f) for f in ("toolbox.py", "toolbox_state.py", "film.py", "importer.py", "stock.py", "uploads.py", "paths.py", "runners.py", "locate.py", "cli.py", "doctor.py", "folder.py", "kit.py", "apikeys.py")]
PY_AT_START = _mtimes(PY_FILES)

import paths
import toolbox_state as ts
import film
import importer
import uploads
import stock
import runners
import folder
import folders
import profiles
import doctor
import apikeys
import updates
import projects
import skillset
import connect
import shlex
import shutil
import socket

ROOT = paths.ROOT
CONFIG_FILE = os.path.join(ROOT, paths.MARKER)   # the project's settings: a change restarts the server like a code change does
CONFIG_AT_START = _mtimes([CONFIG_FILE])
# how the app writes a Spliced command in the prompts and hints it shows: short while the tool lives in the project
CLI = paths.CLI
SOUND_LOCKS = {}


def sound_map(slug, separate=False, force=False):
    """Run sound.py (its own environment: numpy, librosa) and return the cached sound map."""
    lock = SOUND_LOCKS.setdefault(slug, threading.Lock())
    with lock:
        cmd = ["uv", "run", "--quiet", paths.tool("sound"), "analyze", slug] + (["--separate"] if separate else []) + (["--force"] if force else [])
        r = __import__("subprocess").run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800)
        if r.returncode:
            raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else "sound analysis failed")
        return json.load(open(r.stdout.strip().splitlines()[-1]))

LOCK = threading.Lock()
LIB_LOCK, LIB_BODY = threading.Lock(), {}  # the library index as last served, by ETag
COND = threading.Condition(LOCK)
EVENTS = []          # (seq, payload) ring
SEQ = [0]
LIVE = [0]           # open event streams
STATE = [ts.load()]
KNOWN = [ts.known_scenes()]


def publish(payload):
    """Call with LOCK held."""
    SEQ[0] += 1
    EVENTS.append((SEQ[0], payload))
    del EVENTS[:-200]
    COND.notify_all()


LOCAL_NAMES = ("localhost", "127.0.0.1", "[::1]")
WEB_REAL = os.path.realpath(paths.WEB)
NOTHING = os.path.join(WEB_REAL, ".nothing")  # a path that never exists: what a URL we don't serve translates to
OLD_APP = "/library/toolbox"                  # where the app used to be served; bookmarks and open tabs are sent on


def served(upath):
    """The file a URL stands for, or None. Three kinds of URL, and nothing else on disk is reachable:
      /app/<file>        Spliced's own web files (paths.WEB)
      /project/<path>    a picture, clip or sound of the project, by its project-relative path (paths.media's rule:
                         inside the project, a media file, no dot name on the way)
      /api/...           handled before this is asked"""
    p = unquote(upath).replace("\\", "/")
    if p.startswith("/project/"):
        return paths.media(p[len("/project/"):])
    if not p.startswith("/app/"):
        return None
    name = p[len("/app/"):] or "index.html"
    segs = name.split("/")
    if any(not x or x.startswith(".") for x in segs):
        return None
    f = os.path.realpath(os.path.join(WEB_REAL, *segs))
    return f if f.startswith(WEB_REAL + os.sep) and os.path.isfile(f) else None


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".webmanifest": "application/manifest+json",
                      ".md": "text/markdown; charset=utf-8", ".avif": "image/avif", ".webp": "image/webp", ".m4a": "audio/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime"}

    def _guard(self):
        """Only this machine's own Spliced pages and command line may talk to the server; called first in every do_*.
        Host must be localhost on our port (so a web page can't reach us through a domain it points at 127.0.0.1).
        Anything that changes something, and every /api/ read, must also come from our own page or from no page at
        all (board.py, curl): another site's page sends its Origin and a cross-site Sec-Fetch-Site, and is refused."""
        own = {f"{n}:{self.server.server_port}" for n in LOCAL_NAMES}
        why = ""
        if (self.headers.get("Host") or "").strip().lower() not in own:
            why = "Spliced only answers on localhost"
        elif self.command not in ("GET", "HEAD") or self.path.startswith("/api/"):
            origin, site = self.headers.get("Origin"), (self.headers.get("Sec-Fetch-Site") or "").lower()
            if (origin is not None and origin.lower() not in {f"http://{o}" for o in own}) or site not in ("", "same-origin", "none"):
                why = "Spliced only takes requests from its own page"
        if not why:
            return True
        if self.command == "HEAD":
            self.send_error(403)
        else:
            self._json(403, {"error": why})
        return False

    def list_directory(self, path):  # no folder listings: the app never asks for one
        self.send_error(404)
        return None

    def translate_path(self, path):  # the one place a URL becomes a file: see served()
        return served(urlsplit(path).path) or NOTHING

    def _moved(self):
        """/ and the app's old address go to /app/ (the #route survives the redirect in the browser)."""
        u = urlsplit(self.path)
        to = "/app/" if u.path in ("/", "/app") else "/app" + (u.path[len(OLD_APP):] or "/") if (u.path + "/").startswith(OLD_APP + "/") else ""
        if not to:
            return False
        self.send_response(302); self.send_header("Location", to + ("?" + u.query if u.query else "")); self.send_header("Content-Length", "0"); self.end_headers()
        return True

    def do_HEAD(self):
        if not self._guard() or self._moved():
            return
        return super().do_HEAD()

    def log_message(self, fmt, *args):  # quiet, except errors
        if args and str(args[1])[:1] in "45":
            super().log_message(fmt, *args)

    def end_headers(self):
        if not self.path.startswith(("/api/frame", "/api/library")):  # these set their own (a frame's URL carries the render's mtime; the library has an ETag)
            self.send_header("Cache-Control", "no-store" if self.path.startswith(("/api/", "/app")) else "max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
        if self.path.startswith("/project/") and (served(urlsplit(self.path).path) or "").lower().endswith(".svg"):
            # an uploaded SVG is a picture, never a page that runs: judged by the file served, not by how its URL is
            # written (logo.sv%67 and logo.svg/ reach the same file as logo.svg)
            self.send_header("Content-Security-Policy", "sandbox; default-src 'none'; style-src 'unsafe-inline'")
        super().end_headers()

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def _body(self):
        try:
            return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return None

    def do_GET(self):
        if not self._guard() or self._moved():
            return
        if self.path == "/api/state":
            with LOCK:
                return self._json(200, STATE[0])
        if self.path == "/api/info":
            with LOCK:
                return self._json(200, {"root": ROOT, "rev": STATE[0]["rev"], "live_tabs": LIVE[0], "boards": list(STATE[0]["boards"])})
        if self.path.startswith("/api/events"):
            return self._events()
        url = urlsplit(self.path)
        if url.path == "/api/boot.js":  # what the app needs to know about the project before anything else runs
            boot = {"project": paths.NAME, "brand": paths.BRAND, "profiles": paths.PROFILES, "default_profile": paths.DEFAULT_PROFILE, "google_fonts": paths.CONFIG.get("google_fonts", True) is not False, "cli": CLI, "ai": runners.called(), "version": paths.VERSION, "build": paths.BUILD,
                    "folders": paths.reload_folders()}   # how the project sorts its films, boards and assets (spliced folders)
            if os.path.isfile(os.path.join(WEB_REAL, "intro.mp4")):  # the introduction film, when the app ships one: the welcome plays it
                boot["intro"] = "/app/intro.mp4"
                if os.path.isfile(os.path.join(WEB_REAL, "intro.jpg")):   # the frame it shows before it plays
                    boot["intro_poster"] = "/app/intro.jpg"
            loops = os.path.join(WEB_REAL, "explainers")   # a short loop per view, when the app ships them (web/explain.js)
            if os.path.isdir(loops):
                boot["explainers"] = {f[:-4]: f"/app/explainers/{f}" for f in sorted(os.listdir(loops)) if f.endswith(".mp4") and not f.startswith(".")}
            body = ("window.SPLICED = " + json.dumps(boot, ensure_ascii=False) + ";\n").encode()
            self.send_response(200); self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if url.path == "/api/keys":  # which service keys the project has: names and state, never a value
            return self._json(200, {"keys": apikeys.status()})
        if url.path == "/api/doctor":  # what this machine and project can do now (the Setup view; spliced doctor)
            return self._json(200, doctor.check(fresh="fresh=1" in url.query))
        if url.path == "/api/projects":  # the projects this person has opened, for the sidebar's menu (projects.py)
            return self._json(200, {"current": ROOT, "projects": [{**p, "here": os.path.realpath(p["root"]) == os.path.realpath(ROOT)} for p in projects.recent()]})
        if url.path == "/api/connect":  # the Connect your AI sheet: what is connected now (connect.py, skillset.py)
            return self._json(200, connect_status())
        if url.path == "/api/update":  # is a newer Spliced out, and how this copy gets it (updates.py; asked once a day at most)
            return self._json(200, updates.check(fresh="fresh=1" in url.query))
        if url.path in ("/api/library.js", "/api/library"):
            return self._library(url.path.endswith(".js"))
        if url.path == "/api/folders":
            return self._json(200, {"folders": paths.reload_folders()})
        if url.path == "/api/profiles":  # the looks the project's films are made in (profiles.py; spliced profile)
            return self._json(200, {"profiles": profiles.every(), "default": profiles.default(), "motion": paths.PROFILES,
                                    "knobs": {k: {"allowed": list(profiles.LISTS[k]) if k in profiles.LISTS else list(v[0]), "about": v[1]} for k, v in profiles.MOTION.items()}, "kit": profiles.KIT_MOTION,
                                    "motions": profiles.motions()})
        if url.path == "/api/fonts":  # what the typeface picker offers: this machine's families, and Google Fonts unless the project says no
            return self._json(200, {"installed": profiles.installed_fonts(), "google": paths.CONFIG.get("google_fonts", True) is not False})
        if url.path == "/api/productions":
            paths.reload_folders()   # (a command may have added one since)
            return self._json(200, film.summaries())
        if url.path == "/api/own-films":  # the project's own films, beat by beat, for the Library (film.own_films)
            return self._json(200, {"films": film.own_films()})
        m = re.fullmatch(r"/api/productions/([\w.-]+)", url.path)
        if m:
            p = film.production(m.group(1))
            return self._json(200, p) if p else self._json(404, {"error": f"no film called {m.group(1)}"})
        if url.path == "/api/frame":
            return self._frame(parse_qs(url.query))
        if url.path in ("/api/stock/search", "/api/stock/sources"):
            q = parse_qs(url.query)
            try:
                if url.path.endswith("sources"):
                    return self._json(200, {"sources": stock.sources()})
                return self._json(200, stock.search(q.get("q", [""])[0], q.get("kind", ["video"])[0],
                                                    [x for x in q.get("source", [""])[0].split(",") if x] or None, int(q.get("n", ["18"])[0])))
            except Exception as e:  # noqa: BLE001
                return self._json(500, {"error": str(e)})
        if url.path == "/api/uploads":
            return self._json(200, {"items": uploads.items()})
        if url.path == "/api/assets":
            paths.reload_folders()
            return self._json(200, film.library_assets())
        if url.path == "/api/imports":
            return self._json(200, {"jobs": importer.jobs(), "worker": bool(importer.worker_pid()), "runner": runners.name(), "claude": runners.available()})
        m = re.fullmatch(r"/api/productions/([\w.-]+)/assets", url.path)
        if m:
            try:
                return self._json(200, film.assets(m.group(1)))
            except KeyError as e:
                return self._json(404, {"error": str(e).strip("'\"")})
        m = re.fullmatch(r"/api/productions/([\w.-]+)/takes", url.path)
        if m:  # a film's takes (alternatives per sound track), see spliced film takes
            try:
                return self._json(200, film.takes(m.group(1)))
            except KeyError as e:
                return self._json(404, {"error": str(e).strip("'\"")})
        m = re.fullmatch(r"/api/sound/([\w.-]+)", url.path)
        if m:
            q = parse_qs(url.query)
            try:
                return self._json(200, sound_map(m.group(1), q.get("separate") == ["1"], q.get("force") == ["1"]))
            except Exception as e:
                return self._json(500, {"error": str(e)})
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if rng and os.path.isfile(path):
            return self._range(path, rng)
        return super().do_GET()

    def _library(self, as_js):
        """The library as the app reads it (.cache/library.json): as a script that sets window.LIBRARY, or as JSON.
        Compressed, and with an ETag, so a reload costs a 304 instead of the megabyte."""
        try:
            st = os.stat(paths.LIBRARY_JSON)
        except FileNotFoundError:
            return self._json(503, {"error": "the library index isn't built yet: run `spliced library`"})
        gz = "gzip" in (self.headers.get("Accept-Encoding") or "")
        etag = f'"{int(st.st_mtime * 1000):x}-{st.st_size:x}{"-js" if as_js else ""}{"-gz" if gz else ""}"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304); self.send_header("ETag", etag); self.send_header("Cache-Control", "no-cache"); self.end_headers(); return
        with LIB_LOCK:
            body = LIB_BODY.get(etag)
            if body is None:
                with open(paths.LIBRARY_JSON, "rb") as f:
                    body = f.read()
                if as_js:
                    body = b"window.LIBRARY = " + body + b";\n"
                if gz:
                    body = gzip.compress(body, 6, mtime=0)
                LIB_BODY.clear() if len(LIB_BODY) > 6 else None
                LIB_BODY[etag] = body
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript; charset=utf-8" if as_js else "application/json; charset=utf-8")
        if gz:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Vary", "Accept-Encoding"); self.send_header("ETag", etag); self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def _events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        with LOCK:
            last = SEQ[0]
            LIVE[0] += 1
            hello = {"type": "hello", "rev": STATE[0]["rev"], "web": CODE["web"], "data": CODE["data"], "error": CODE["error"]}
        try:
            self.wfile.write(f"data: {json.dumps(hello)}\n\n".encode()); self.wfile.flush()
            while True:
                with COND:
                    COND.wait_for(lambda: SEQ[0] > last, timeout=15)
                    new = [(s, p) for s, p in EVENTS if s > last]
                    last = SEQ[0]
                if new:
                    for _, p in new:
                        self.wfile.write(f"data: {json.dumps(p, ensure_ascii=False)}\n\n".encode())
                else:
                    self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with LOCK:
                LIVE[0] -= 1

    def _range(self, path, rng):
        """Byte ranges, so <video> can seek (SimpleHTTPRequestHandler doesn't support them)."""
        size = os.path.getsize(path)
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        if not m:
            return super().do_GET()
        a, b = m.group(1), m.group(2)
        start = int(a) if a else max(0, size - int(b))
        end = min(int(b), size - 1) if a and b else size - 1
        if start >= size:
            self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.end_headers(); return
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start); left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk: break
                    self.wfile.write(chunk); left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _frame(self, q):
        """One frame of a render as a JPEG: /api/frame?file=<repo path>&t=<seconds>&w=<px>."""
        path = paths.media(unquote(q.get("file", [""])[0]))
        if not path or not path.lower().endswith(film.VIDEO_EXT):
            return self._json(404, {"error": "no such video"})
        try:
            jpg = film.frame_jpg(path, float(q.get("t", ["0"])[0]), min(960, max(80, int(q.get("w", ["320"])[0]))))
        except Exception as e:
            return self._json(500, {"error": str(e)})
        if not jpg:
            return self._json(404, {"error": "no frame there"})
        body = open(jpg, "rb").read()
        self.send_response(200); self.send_header("Content-Type", "image/jpeg"); self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=86400"); self.end_headers(); self.wfile.write(body)

    def do_PATCH(self):
        """Review a beat: {status?, review?}. Writes the film's storyboard.json (Remotion) or review.json (HyperFrames).
        Sound notes: /api/productions/<slug>/sound/<id> with {kind, label, start, end, ref, note} or {done}."""
        if not self._guard():
            return
        um = re.fullmatch(r"/api/uploads/(\w+)", urlsplit(self.path).path)
        if um:
            try:
                return self._uploaded(uploads.update(um.group(1), self._body() or {}))
            except (KeyError, ValueError) as e:
                return self._json(400, {"error": str(e).strip("'\"")})
        tm = re.fullmatch(r"/api/productions/([\w.-]+)/takes/([\w.:@-]+)", urlsplit(self.path).path)
        if tm:  # use a take: {take: <id>} writes it into sound.json (Remotion) and records it as chosen
            try:
                with LOCK:
                    return self._json(200, film.use_take(tm.group(1), tm.group(2), str((self._body() or {}).get("take", ""))))
            except (KeyError, ValueError) as e:
                return self._json(400, {"error": str(e).strip("'\"")})
        sm = re.fullmatch(r"/api/productions/([\w.-]+)/sound/([\w.:@-]+)", urlsplit(self.path).path)
        if sm:
            try:
                b = self._body()
                with LOCK:
                    return self._json(200, film.update_sound_note(sm.group(1), sm.group(2), b, done=b.get("done")))
            except (KeyError, ValueError) as e:
                return self._json(400, {"error": str(e).strip("'\"")})
        pm = re.fullmatch(r"/api/productions/([\w.-]+)/pins/([\w-]+)", urlsplit(self.path).path)
        if pm:
            try:
                b = self._body() or {}
                with LOCK:
                    return self._json(200, film.update_pin(pm.group(1), pm.group(2), {k: v for k, v in b.items() if k in ("note", "t", "status")},
                                                           done=b.get("done"), done_in=b.get("done_in")))
            except (KeyError, ValueError) as e:
                return self._json(400, {"error": str(e).strip("'\"")})
        fm = re.fullmatch(r"/api/productions/([\w.-]+)", urlsplit(self.path).path)
        if fm:  # the film's notes mode: {notes_mode: "auto"|"manual"} (spliced film mode)
            try:
                with LOCK:
                    film.set_notes_mode(fm.group(1), str((self._body() or {}).get("notes_mode", "")))
                return self._json(200, {"notes_mode": film.notes_mode(fm.group(1)), "watcher": film.watcher(fm.group(1))})
            except (KeyError, ValueError) as e:
                return self._json(400, {"error": str(e).strip("'\"")})
        m = re.fullmatch(r"/api/productions/([\w.-]+)/beats/([\w.-]+)", urlsplit(self.path).path)
        if not m:
            return self._json(404, {"error": "not found"})
        try:
            patch = {k: v for k, v in (self._body() or {}).items() if k in ("status", "review", "copy", "vo")}
            with LOCK:
                return self._json(200, film.update_beat(m.group(1), m.group(2), patch))
        except (KeyError, ValueError) as e:
            return self._json(400, {"error": str(e).strip("'\"")})

    def _uploaded(self, it):
        with LOCK:
            KNOWN[0] = ts.known_scenes()
            publish({"type": "uploads", "id": it["id"]})
        return self._json(200, it)

    def do_POST(self):
        if not self._guard():
            return
        if urlsplit(self.path).path == "/api/assets/upload":
            # A file of the person's own into a film (Assets' Upload): the raw file as the body, X-Filename and X-Film (url-encoded)
            n = int(self.headers.get("Content-Length", 0))
            if n > stock.MAX_FILE:
                return self._json(413, {"error": f"{n / 1e6:.0f} MB is too big for the repo (under 95 MB, please)"})
            data = self.rfile.read(n)
            if len(data) < n:   # the browser stopped sending (the upload was cancelled): keep nothing
                return self._json(400, {"error": "the upload was cancelled"})
            try:
                return self._json(200, stock.add_file(unquote(self.headers.get("X-Film", "")), data, unquote(self.headers.get("X-Filename", "file"))))
            except ValueError as e:
                return self._json(400, {"error": str(e)})
        sm = re.fullmatch(r"/api/profiles/([a-z0-9][a-z0-9-]{0,47})/sources", urlsplit(self.path).path)
        if sm:
            # A file a profile is drafted from (a brand book, logo, screenshot, film): the raw file as the body, its name in X-Filename
            n = int(self.headers.get("Content-Length", 0))
            if n > profiles.SOURCE_MAX:
                return self._json(413, {"error": "that file is too big (under 400 MB, please)"})
            data = self.rfile.read(n)
            if len(data) < n:
                return self._json(400, {"error": "the upload was cancelled"})
            try:
                with LOCK:
                    f = profiles.add_source(sm.group(1), unquote(self.headers.get("X-Filename", "source")), data)
                profiles.digest_later(sm.group(1))   # digested for an agent in the background (digest.py)
                return self._json(200, {"file": f, "sources": profiles.sources(sm.group(1))})
            except (KeyError, ValueError, OSError) as e:
                return self._json(400, {"error": str(e.args[0]) if e.args else str(e)})
        if urlsplit(self.path).path == "/api/uploads":
            # Upload a reference: the raw file as the body, its name in X-Filename (url-encoded), optional X-Title / X-Note
            n = int(self.headers.get("Content-Length", 0))
            if n > uploads.MAX:
                return self._json(413, {"error": f"{n / 1e6:.0f} MB is too big for the repo (under 95 MB, please)"})
            data = self.rfile.read(n)
            if len(data) < n:   # the browser stopped sending (the upload was cancelled): keep nothing
                return self._json(400, {"error": "the upload was cancelled"})
            try:
                it = uploads.add_bytes(data, unquote(self.headers.get("X-Filename", "upload")), title=unquote(self.headers.get("X-Title", "")),
                                       note=unquote(self.headers.get("X-Note", "")))
            except ValueError as e:
                return self._json(400, {"error": str(e)})
            importer.add_uploads_job()  # read it like a film scene, in the background
            return self._uploaded(it)
        body = self._body()
        if body is None:
            return self._json(400, {"error": "expected JSON"})
        if urlsplit(self.path).path == "/api/imports":
            # Add reference: {urls: [...], slug?, breakdown?} -> queued jobs (importer.py runs them)
            urls = [u for u in (body.get("urls") or []) if str(u).strip()]
            if not urls:
                return self._json(400, {"error": "paste a link (YouTube, Vimeo, X, LinkedIn...) or a file path"})
            try:
                return self._json(200, {"jobs": importer.add(urls, body.get("slug") or None, body.get("breakdown", True) is not False)})
            except (OSError, ValueError) as e:
                return self._json(400, {"error": str(e)})
        if urlsplit(self.path).path in ("/api/folder/look", "/api/folder/import"):
            # A folder of things already collected (folder.py): look says what is in it; import queues bringing it in
            try:
                found = folder.look(str(body.get("folder", "")))
                if self.path.endswith("/look") or not found["pictures"] + found["videos"]:
                    return self._json(200, {**found, "clip_under": folder.CLIP_UNDER})
                return self._json(200, {"jobs": [importer.add_folder(found["folder"], reading=body.get("reading", True) is not False)]})
            except (OSError, ValueError) as e:
                return self._json(400, {"error": str(e)})
        im = re.fullmatch(r"/api/imports/(\w+)/(cancel|retry)", urlsplit(self.path).path)
        if im:
            try:
                if im.group(2) == "cancel":
                    return self._json(200, importer.cancel(im.group(1)))
                j = importer.load(im.group(1)) or {}
                importer.remove(im.group(1))
                if j.get("type") == "uploads":
                    return self._json(200, {"jobs": [importer.add_uploads_job()]})
                if j.get("type") == "folder":
                    return self._json(200, {"jobs": [importer.add_folder(j["src"], j.get("clip_under"), j.get("breakdown", True))]})
                return self._json(200, {"jobs": importer.add([j["src"]], j.get("slug"), j.get("breakdown", True))})
            except (KeyError, ValueError) as e:
                return self._json(400, {"error": str(e).strip("'\"")})
        pm = re.fullmatch(r"/api/productions/([\w.-]+)/pins", urlsplit(self.path).path)
        if pm:
            try:
                with LOCK:
                    film.add_pin(pm.group(1), float(body.get("t", 0)), body.get("note", ""), by=str(body.get("by") or "person"),
                                 render=body.get("render"))
                    return self._json(200, film.pins(pm.group(1)))
            except (KeyError, ValueError, TypeError) as e:
                return self._json(400, {"error": str(e).strip("'\"")})
        if urlsplit(self.path).path == "/api/folders":
            # Make one of the project's folders: {name, folder?} (the folder's path defaults to the name, kebab-cased)
            try:
                with LOCK:
                    f = folders.add(body.get("folder") or film.slugify(str(body.get("name", "")), 48), str(body.get("name", "")))
                return self._json(200, {"folder": f, "folders": paths.FOLDERS})
            except (OSError, ValueError) as e:
                return self._json(400, {"error": str(e).strip("'\"")})
        fm = re.fullmatch(r"/api/productions/([\w.-]+)/folder", urlsplit(self.path).path)
        if fm:
            # Put a film in one of the project's folders: {folder} ("" for none). Its renders move with it.
            try:
                with LOCK:
                    paths.reload_folders()
                    return self._json(200, film.move_film(fm.group(1), str(body.get("folder") or "")))
            except (KeyError, ValueError, FileExistsError, OSError) as e:
                return self._json(400, {"error": str(e).strip("'\"")})
        if urlsplit(self.path).path == "/api/productions":
            # Start a Remotion film from a board: {slug, board, items, profile, folder?}.
            try:
                with LOCK:
                    p = film.new_from_board(body.get("slug", ""), body.get("board", ""), body.get("items"), body.get("profile"), body.get("folder"), body.get("style"))
                return self._json(200, p)
            except (KeyError, ValueError, FileExistsError) as e:
                return self._json(400, {"error": str(e).strip("'\"")})
        if self.path == "/api/ops":
            ops = body.get("ops") or []
            by, client = str(body.get("by") or "browser"), body.get("client")
            with LOCK:
                try:
                    new, results, summary = ts.apply(STATE[0], ops, by=by, known=KNOWN[0])
                except (ts.OpError, KeyError, TypeError, ValueError) as e:
                    return self._json(400, {"error": str(e)})
                STATE[0] = new
                ts.save(new)
                publish({"type": "state", "rev": new["rev"], "by": by, "client": client, "summary": summary})
                return self._json(200, {"rev": new["rev"], "results": results, "summary": summary})
        if self.path == "/api/profiles":
            # A change to the project's profiles, the same operations as `spliced profile`: {op, profile?, ...}
            op, slug = str(body.get("op", "")), str(body.get("profile", ""))
            if op == "site":   # a website read into its sources (website.py): seconds of fetching, so not under the lock
                try:
                    site = profiles.add_site(slug, str(body.get("url", "")))
                except (KeyError, ValueError, OSError) as e:
                    return self._json(400, {"error": str(e.args[0]) if e.args else str(e)})
                profiles.digest_later(slug)
                return self._json(200, {"profile": slug, "site": site, "sources": profiles.sources(slug), "profiles": profiles.every(), "default": profiles.default()})
            try:
                with LOCK:
                    if op == "new":
                        p = profiles.create(body.get("name", ""), body.get("motion"), body.get("about", ""), body.get("from_film"), is_default=bool(body.get("default")))
                        slug = p["slug"]
                    elif op == "house":
                        p = profiles.take_in_house()
                        slug = p["slug"] if p else slug
                    elif op == "set":
                        profiles.update(slug, {k: body.get(k) for k in ("name", "about", "font", "font_source", "text_font", "text_font_source", "type", "palette", "md", "motion")})
                    elif op == "motion-save":
                        profiles.save_motion(slug, body.get("name", ""))
                    elif op == "motion-remove":
                        profiles.remove_motion(str(body.get("motion", "")))
                    elif op == "draft":
                        profiles.draft(slug, body.get("request", ""))
                    elif op == "default":
                        profiles.set_default("" if slug == profiles.NONE else slug)
                    elif op == "learn":
                        profiles.learn(slug, body.get("text", ""), body.get("from", ""))
                    elif op == "forget":
                        profiles.forget(slug, body.get("n", 0))
                    elif op in ("pin", "unpin"):
                        profiles.pin(slug, body.get("scene", ""), op == "pin")
                    elif op == "remove":
                        profiles.remove(slug)
                    else:
                        return self._json(400, {"error": "op is new, set, default, learn, forget, pin, unpin, remove, house, motion-save, motion-remove, draft or site"})
            except (KeyError, ValueError, OSError) as e:
                return self._json(400, {"error": str(e.args[0]) if e.args else str(e)})
            return self._json(200, {"profile": slug, "profiles": profiles.every(), "default": profiles.default(), "motions": profiles.motions()})
        if self.path == "/api/keys":
            # Save or remove a service key: {id: "elevenlabs", value} or {id, remove: true} -> .env (owner-only, git ignores it).
            # The answer says what changed and never carries the value back.
            try:
                k = str(body.get("id", ""))
                r = apikeys.remove_key(k) if body.get("remove") else apikeys.set_key(k, str(body.get("value", "")))
            except ValueError as e:
                return self._json(400, {"error": str(e)})
            return self._json(200, {**r, "keys": apikeys.status()})
        if self.path == "/api/stock/key":
            # Save a library's API key: {source: "unsplash", value} -> .env (git ignores it)
            try:
                return self._json(200, stock.set_key(str(body.get("source", "")), str(body.get("value", ""))))
            except ValueError as e:
                return self._json(400, {"error": str(e)})
        if self.path == "/api/stock/get":
            # Pull a stock photo or clip into a film: {id: "pexels:video:123", film, name?} (stock.py)
            try:
                return self._json(200, stock.get(str(body.get("id", "")), str(body.get("film", "")), body.get("name") or None))
            except Exception as e:  # noqa: BLE001
                return self._json(400, {"error": str(e)})
        if self.path == "/api/uploads/analyse":
            # (Re)analyse uploads: {ids?: [...]} clears those analyses first; then every unanalysed upload is queued
            for uid in body.get("ids") or []:
                try:
                    uploads.clear_analysis(uid)
                except KeyError:
                    pass
            return self._json(200, {"job": importer.add_uploads_job(), "pending": len(uploads.pending())})
        if self.path == "/api/uploads/url":
            # An image, GIF or clip by its link: {url, title?, note?}
            try:
                it = uploads.add_url(str(body.get("url", "")), title=str(body.get("title", "")), note=str(body.get("note", "")))
            except Exception as e:  # noqa: BLE001
                return self._json(400, {"error": str(e)})
            importer.add_uploads_job()
            return self._uploaded(it)
        if self.path == "/api/projects/open":
            # Switch to another project: one this person has opened before, never a path the page made up. Its own
            # server is started if it isn't running (as `spliced open --background` does), and the page goes there.
            want = os.path.realpath(str(body.get("root") or ""))
            known = next((p for p in projects.recent() if os.path.realpath(p["root"]) == want), None)
            if not known:
                return self._json(404, {"error": "that isn't a project that has been opened on this machine"})
            url_, why = start_project(known["root"])
            if not url_:
                return self._json(500, {"error": why})
            known = {**known, "url": url_}
            return self._json(200, {"url": known["url"], "name": known["name"]})
        if self.path == "/api/projects/new":
            # A new project in a folder the person chose: a new or empty folder (never one that holds their files), or a
            # folder that is a project already. `spliced setup` makes it and gives its AI the skills; then its app starts.
            where = str(body.get("folder") or "").strip()   # (not `folder`: that is a module here)
            root = os.path.realpath(os.path.expanduser(where)) if where else ""
            if not root or not os.path.isabs(os.path.expanduser(where)):
                return self._json(400, {"error": "name the folder with its whole path, like ~/films/mine"})
            if not os.path.isfile(os.path.join(root, paths.MARKER)):
                if os.path.isfile(root) or (os.path.isdir(root) and any(not n.startswith(".") for n in os.listdir(root))):
                    return self._json(400, {"error": f"{where} has files in it. Choose a new or empty folder for the project"})
                ok, out = cli("setup", root, "--no-kit", "--no-render", "--no-open")
                if not ok or not os.path.isfile(os.path.join(root, paths.MARKER)):
                    return self._json(500, {"error": out[-400:] or "the project wasn't made"})
            projects.note(root)
            url_, why = start_project(root)
            if not url_:
                return self._json(500, {"error": why})
            return self._json(200, {"url": url_, "name": projects.name_of(root), "root": root})
        if self.path == "/api/pick-folder":
            path = pick_folder(str(body.get("for") or "import"))
            if path is None:
                return self._json(501, {"error": "this machine has no folder picker Spliced knows: type the folder's path"})
            return self._json(200, {"path": path or None})
        if self.path == "/api/connect":
            # Connect your AI, as the Mac app's sheet does it: {agents: true} runs `agents install`; {apps: {id: true|false}}
            # adds this project to a chat app's tools or takes it out. Each is the command a person could run.
            steps = ([["agents", "install"]] if body.get("agents") else [])
            known = {a["id"]: a["connected"] for a in connect_status()["apps"]}
            for app, want in (body.get("apps") or {}).items() if isinstance(body.get("apps"), dict) else []:
                if app in known and bool(want) != known[app]:
                    steps.append(["connect", app] if want else ["connect", app, "--remove"])
            done = []
            for st in steps:
                ok, out = cli(*st, root=ROOT)
                done.append({"step": " ".join(st), "ok": ok, "said": out.splitlines()[-1] if out else ""})
            return self._json(200, {"ok": all(d["ok"] for d in done), "done": done, **connect_status()})
        if self.path == "/api/reveal":
            # Show a file of the repo in Finder ({path, how: "reveal" (select it) | "open" (default app) | "folder"})
            try:
                p = paths.resolve(str(body.get("path") or ""), main_ok=True)   # (a render this worktree sent to the main checkout)
            except ValueError:
                p = ""
            if not p or not os.path.exists(p):
                return self._json(404, {"error": "no such file in the repo"})
            how = body.get("how") or "reveal"
            target = os.path.dirname(p) if how == "folder" and os.path.isfile(p) else p
            cmd = (["open", "-R", target] if how == "reveal" else ["open", target]) if sys.platform == "darwin" else ["xdg-open", os.path.dirname(p) if how == "reveal" else target]
            try:
                __import__("subprocess").Popen(cmd)
            except OSError as e:
                return self._json(500, {"error": str(e)})
            return self._json(200, {"ok": True, "path": paths.rel(target)})
        if self.path == "/api/focus":
            target = str(body.get("target") or "")
            if not target.startswith("#/"):
                return self._json(400, {"error": "target is an app route like #/boards/<name> or #/scene/<film>/<sNN>"})
            with LOCK:
                publish({"type": "focus", "target": target, "by": str(body.get("by") or "claude"), "note": body.get("note", "")})
            return self._json(200, {"ok": True})
        if self.path == "/api/reload-library":
            with LOCK:
                KNOWN[0] = ts.known_scenes()
                publish({"type": "library"})
            return self._json(200, {"scenes": len(KNOWN[0])})
        return self._json(404, {"error": "not found"})

    def do_DELETE(self):
        if not self._guard():
            return
        um = re.fullmatch(r"/api/uploads/(\w+)", urlsplit(self.path).path)
        if um:
            try:
                return self._uploaded(uploads.remove(um.group(1)))
            except KeyError as e:
                return self._json(404, {"error": str(e).strip("'\"")})
        im = re.fullmatch(r"/api/imports/(\w+)", urlsplit(self.path).path)
        if im:
            try:
                importer.remove(im.group(1))
                return self._json(200, {"jobs": importer.jobs()})
            except ValueError as e:
                return self._json(400, {"error": str(e)})
        pm = re.fullmatch(r"/api/productions/([\w.-]+)/pins/([\w-]+)", urlsplit(self.path).path)
        if not pm:
            return self._json(404, {"error": "not found"})
        try:
            with LOCK:
                return self._json(200, film.update_pin(pm.group(1), pm.group(2), delete=True))
        except KeyError as e:
            return self._json(404, {"error": str(e).strip("'\"")})

    def do_PUT(self):
        if not self._guard():
            return
        return self._json(410, {"error": "whole-state saves are gone: send operations to POST /api/ops"})


PICK_PROMPTS = {"import": "Choose a folder of pictures, clips and films to bring in", "project": "Choose a new or empty folder for the project"}


def pick_folder(what):
    """Ask the person for a folder with the system's own picker: what a browser can't do, since a page is never told
    where a folder is. The path, "" when they cancel, None when this machine has no picker we know (the page then
    asks for the path in words). The prompt is one of ours, never the page's."""
    prompt = PICK_PROMPTS.get(what, PICK_PROMPTS["import"])
    stand = paths.env("PICKER")   # SPLICED_PICKER: a command that prints a path, for checks of this code
    if stand:
        cmd = shlex.split(stand)
    elif sys.platform == "darwin":
        cmd = ["osascript", "-e", "tell me to activate", "-e", f'POSIX path of (choose folder with prompt "{prompt}")']
    elif shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", "--directory", f"--title={prompt}"]
    elif shutil.which("kdialog"):
        cmd = ["kdialog", "--getexistingdirectory", os.path.expanduser("~"), "--title", prompt]
    else:
        return None
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError):
        return None
    path = r.stdout.strip()
    return (path.rstrip("/") or "/") if r.returncode == 0 and path else ""


def cli(*args, root=None, timeout=300):
    """Run a `spliced` command on a project as its own process, as the Mac app does: (ok, what it printed)."""
    env = {k: v for k, v in os.environ.items() if k not in ("SPLICED_RESTARTED", "SPLICED_PORT", "SPLICED_PARENT_PID", "SPLICED_FOLDER", "SPLICED_PROJECT")}
    try:
        r = subprocess.run([sys.executable, paths.tool("cli"), *(["--project", root] if root else []), *args], env=env, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def start_project(root):
    """Start another project's app if it isn't running, as `spliced open --background` does: (its address, or None; why not)."""
    live = projects.running(root)
    if live:
        return live["url"], ""
    ok, out = cli("open", "--background", "--no-open", root=root, timeout=150)
    live = projects.running(root)
    return (live["url"], "") if live else (None, out[-400:] or "it didn't start")


def connect_status():
    """What the Connect your AI sheet shows: the agents that open the folder (are the skills in?), and each chat app on this machine."""
    skills = skillset.status(ROOT)
    return {"project": paths.NAME, "agents": bool(skills) and all(s in ("current", "edited") for s in skills.values()),
            "apps": [{"id": a["id"], "name": a["name"], "connected": a["connected"]} for a in connect.status() if a["present"]],
            "worktree": bool(paths.main_checkout())}


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    # A page asks for some twenty files at once, each on its own connection. The default queue holds five: on a busy
    # machine the rest were refused, and the app came up without half its scripts.
    request_queue_size = 128


def watch_uploads():
    """uploads.json changed (an analysis landed, uploads.py from the chat, a git pull): tell the tabs."""
    def stamp():   # 0 while there is no index yet: its first appearance is a change too (a new project's first uploads)
        try:
            return os.path.getmtime(uploads.INDEX)
        except OSError:
            return 0

    last = stamp()
    while True:
        time.sleep(1.5)
        m = stamp()
        if m != last:
            with LOCK:
                KNOWN[0] = ts.known_scenes()
                publish({"type": "uploads"})
        last = m


def watch_file():
    """Pick up edits made to state.json while the server runs (e.g. board.py with the server down, or a git pull)."""
    last = os.path.getmtime(ts.STATE) if os.path.exists(ts.STATE) else 0
    while True:
        time.sleep(1.5)
        try:
            m = os.path.getmtime(ts.STATE)
        except FileNotFoundError:
            continue
        if m != last:
            last = m
            with LOCK:
                disk = ts.load()
                if disk.get("rev", 0) != STATE[0].get("rev", 0) or disk != STATE[0]:
                    STATE[0] = disk
                    publish({"type": "state", "rev": disk["rev"], "by": "file", "client": None, "summary": "state.json changed on disk"})


# ---------- live code: the server restarts itself when its Python changes, tabs reload when the app changes ----------
WEB_DIR = paths.WEB
HTTPD = [None]


def _web_files():
    try:
        return sorted(os.path.join(WEB_DIR, f) for f in os.listdir(WEB_DIR) if f.endswith((".js", ".css", ".html")))
    except FileNotFoundError:
        return []


def _stamp(paths):
    import hashlib
    return hashlib.sha1(json.dumps(sorted((os.path.basename(k), v) for k, v in _mtimes(paths).items())).encode()).hexdigest()[:10]


DATA_JS = paths.LIBRARY_JSON  # the library index: when it changes, open tabs reload
CODE = {"web": _stamp(_web_files()), "data": _stamp([DATA_JS]), "error": ""}


def library_is_stale():
    """True when the library index is missing, or older than a breakdown, STYLES.md or TAXONOMY.md."""
    try:
        built = os.path.getmtime(DATA_JS)
    except FileNotFoundError:
        return True
    src = [paths.STYLES, paths.TAXONOMY]
    if os.path.isdir(paths.REFS):
        src += [os.path.join(paths.REFS, d, "breakdown.json") for d in os.listdir(paths.REFS)]
    return any(os.path.exists(p) and os.path.getmtime(p) > built for p in src)


def running():
    """The server already serving this project, from .cache/server.json, if it is still up and still ours."""
    try:
        with open(paths.SERVER_FILE) as f:
            info = json.load(f)
        if int(info["pid"]) == os.getpid():
            return None
        os.kill(int(info["pid"]), 0)
        with urllib.request.urlopen(f"http://127.0.0.1:{int(info['port'])}/api/info", timeout=1.5) as r:
            return info if os.path.realpath(str(json.load(r).get("root") or "")) == os.path.realpath(ROOT) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def announce(port, url):
    """Say where this project is served, so its command line (spliced board) and the Mac app find it on any port."""
    os.makedirs(paths.CACHE, exist_ok=True)
    tmp = paths.SERVER_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"port": port, "url": url, "pid": os.getpid(), "root": ROOT}, f)
    os.replace(tmp, paths.SERVER_FILE)

    def gone():
        try:
            with open(paths.SERVER_FILE) as f:
                if json.load(f).get("pid") == os.getpid():
                    os.remove(paths.SERVER_FILE)
        except (OSError, ValueError):
            pass
    atexit.register(gone)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))   # the Mac app stops us with SIGTERM: clean up on the way out
    if hasattr(signal, "pthread_sigmask"):   # a stop that came while restart() was replacing us waited for this: it lands now
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGTERM})
    parent = paths.env("PARENT_PID")
    if parent and parent.isdigit():   # started by the Mac app: if it goes away without stopping us (a crash), go too

        def orphaned():
            while True:
                time.sleep(2)
                try:
                    os.kill(int(parent), 0)
                except ProcessLookupError:
                    os.kill(os.getpid(), signal.SIGTERM)
                    return
                except OSError:
                    pass
        threading.Thread(target=orphaned, daemon=True).start()


def restart():
    """Replace this process with a fresh one on the same port and arguments (the open tabs reconnect on their own)."""
    print("Spliced: code changed, restarting", flush=True)
    os.environ["SPLICED_RESTARTED"] = "1"
    if HTTPD[0]:
        os.environ["SPLICED_PORT"] = str(HTTPD[0].server_address[1])   # come back on the port the tabs are on
    try:
        if HTTPD[0]:
            HTTPD[0].socket.close()
    except OSError:
        pass
    sys.stdout.flush(); sys.stderr.flush()
    # A SIGTERM while the new process starts would kill it before it can tidy up, leaving .cache/server.json behind
    # under its (unchanged) pid. Held back across the exec instead, and let in by announce() once the handler is set.
    if hasattr(signal, "pthread_sigmask"):
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])


FIRST_PORT, PORTS = 8765, 40          # where a project's app is served when nothing says otherwise, and how far to look
PORT_FILE = os.path.join(paths.CACHE, "port")


def port_free(port):
    """Nothing answers on this port and it can be bound: free for us."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return False   # something is listening (on this address or on every address)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as t:
            # as the server itself binds: a port just let go (this project stopped a moment ago) counts as free,
            # so a quick stop and start comes back on the same port and the page keeps what it remembers
            t.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            t.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


def pick_port():
    """This project's port: the one it had last time if it is free, else the first free one from 8765 up. Another
    project open at the same time, or another program on 8765, no longer stops this one from starting."""
    try:
        with open(PORT_FILE) as f:
            last = int(f.read().strip())
    except (OSError, ValueError):
        last = None
    for port in ([last] if last and 1024 < last < 65536 else []) + list(range(FIRST_PORT, FIRST_PORT + PORTS)):
        if port_free(port):
            if port != last:
                try:
                    os.makedirs(paths.CACHE, exist_ok=True)
                    with open(PORT_FILE, "w") as f:
                        f.write(str(port))
                except OSError:
                    pass
            return port
    sys.exit(f"Spliced: no free port between {FIRST_PORT} and {FIRST_PORT + PORTS - 1}. Name one: {paths.CLI} open --port <number>")


def background(args):
    """`spliced open --background`: start the server as its own process, wait until it answers, say where, return."""
    live = running()
    if live:
        print(f"Spliced: already running for this project at {live['url']}", flush=True)
        return 0
    os.makedirs(paths.CACHE, exist_ok=True)
    log = os.path.join(paths.CACHE, "server.log")
    with open(log, "ab") as out:
        p = subprocess.Popen([sys.executable, os.path.abspath(__file__), *args], stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(300):   # up to a minute: a big library's index is built before the server answers
        time.sleep(0.2)
        live = running()
        if live or p.poll() is not None:
            break
    if not live:
        try:
            with open(log, errors="replace") as f:
                tail = "".join(f.readlines()[-8:]).strip()
        except OSError:
            tail = ""
        print(f"Spliced: the app didn't start.{chr(10) + tail if tail else ''}\nThe whole log: {log}", file=sys.stderr)
        return 1
    print(f"Spliced: {live['url']}  (serving {ROOT} in the background; stop it with: {paths.CLI} open --stop)", flush=True)
    return 0


def stop():
    """`spliced open --stop`: ask this project's server to go, and wait until it has."""
    live = running()
    if not live:
        print("Spliced: the app isn't running for this project")
        return 0
    try:
        os.kill(int(live["pid"]), signal.SIGTERM)
    except OSError as e:
        print(f"Spliced: couldn't stop it ({e})", file=sys.stderr)
        return 1
    for _ in range(50):
        time.sleep(0.1)
        if not running():
            break
    print(f"Spliced: stopped the app that was at {live['url']}")
    return 0


def refresh_skills():
    """Bring the project's copies of Spliced's skills up to date when the app starts (Spliced may have been updated
    since). Only skills the project already has, and only files that are still as Spliced left them: one a person
    changed is theirs and stays (skillset.py). The film kit is left for the person to update, since it can change how
    a film in production moves."""
    try:
        done, _ = skillset.install(ROOT, asked=False)
    except OSError:
        return
    for name in sorted({rel.split("/", 1)[0] for rel, what in done if what in ("new", "updated")}):
        print(f"Spliced: this project's {name} skill is now the one from Spliced {paths.VERSION}", flush=True)


def watch_code():
    """Keep the code watcher alive: a surprise in it must never stop the server noticing new code."""
    while True:
        try:
            _watch_code()
        except Exception as e:  # noqa: BLE001
            print(f"Spliced: code watcher hiccup ({e}), carrying on", flush=True)
            time.sleep(2)


def _watch_code():
    """Python changed: compile it, then restart (or keep the old code and say so). App files changed: tell the tabs."""
    watched = PY_FILES + [CONFIG_FILE]
    py = {**PY_AT_START, **CONFIG_AT_START}
    while True:
        time.sleep(1.0)
        now = _mtimes(watched)
        if now != py:
            time.sleep(1.0)  # debounce: let an editor or a git pull finish writing
            while _mtimes(watched) != now:
                now = _mtimes(watched)
                time.sleep(1.0)
            py = now
            errs = []
            for p in PY_FILES:
                try:
                    with open(p, encoding="utf-8") as f:
                        compile(f.read(), p, "exec")
                except (SyntaxError, ValueError, OSError) as e:
                    errs.append(f"{os.path.relpath(p, ROOT)}: {type(e).__name__}: {e}")
            if errs:
                print("Spliced: the new code has an error, still running the old version:\n  " + "\n  ".join(errs), flush=True)
                with LOCK:
                    CODE["error"] = "; ".join(errs)
                    publish({"type": "code-error", "error": CODE["error"]})
                continue
            with LOCK:
                publish({"type": "restart"})
            time.sleep(0.4)  # let the event reach the tabs
            restart()
        web, data = _stamp(_web_files()), _stamp([DATA_JS])
        if web != CODE["web"] or data != CODE["data"]:
            time.sleep(0.6)
            web, data = _stamp(_web_files()), _stamp([DATA_JS])
            with LOCK:
                if data != CODE["data"]:
                    KNOWN[0] = ts.known_scenes()
                    publish({"type": "library", "data": data})
                if web != CODE["web"]:
                    publish({"type": "code", "web": web})
                CODE["web"], CODE["data"] = web, data


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--stop" in a:
        sys.exit(stop())
    if "--background" in a:
        sys.exit(background([x for x in a if x != "--background"]))
    restarted = paths.env("RESTARTED") == "1"
    if library_is_stale():  # a fresh clone, a pull that brought breakdowns, or a breakdown edited while we were down
        print("Spliced: building the library index...", flush=True)
        r = subprocess.run(["uv", "run", "-q", paths.tool("build_library"), "--index-only"], capture_output=True, text=True)
        if not os.path.exists(DATA_JS):
            sys.exit("Spliced: couldn't build the library index (spliced library):\n" + (r.stdout + r.stderr).strip()[-1500:])
        if r.returncode:
            print(f"Spliced: some films have problems and are left out until fixed ({paths.CLI} library --check):\n  "
                  + "\n  ".join((r.stdout + r.stderr).strip().splitlines()[:12]), flush=True)
        CODE["data"] = _stamp([DATA_JS])
    if not os.path.exists(ts.STATE):
        ts.save(STATE[0])
    if not restarted and not running():   # a fresh clone or worktree: its films can't render until remotion/ has its packages
        import kit
        if kit.packages()["state"] == "missing":
            kit.install_packages(background=True)
    threading.Thread(target=watch_file, daemon=True).start()
    threading.Thread(target=watch_uploads, daemon=True).start()
    threading.Thread(target=watch_code, daemon=True).start()
    live = running()
    if live and not restarted:   # this project is already served (the Mac app, another terminal): use that one
        print(f"Spliced: already running for this project at {live['url']}", flush=True)
        if "--no-open" not in a:
            webbrowser.open(live["url"])
        sys.exit(0)
    # the port: the one asked for, the one a restart came from, or this project's own (the last it had, else a free one)
    named = int(a[a.index("--port") + 1]) if "--port" in a and a.index("--port") + 1 < len(a) and a[a.index("--port") + 1].isdigit() else None
    port = named or (int(paths.env("PORT")) if restarted and str(paths.env("PORT") or "").isdigit() else None) or pick_port()
    url = f"http://localhost:{port}/app/"
    for tries in range(40):  # after a self-restart the old socket can take a moment to let go
        try:
            httpd = Server(("127.0.0.1", port), Handler)
            break
        except OSError:
            if restarted and tries < 39:
                time.sleep(0.25)
                continue
            sys.exit(f"Spliced: port {port} is already in use, by another program or another project's Spliced.\n"
                     + (f"Leave out --port and Spliced picks a free one: {paths.CLI} open" if named else f"Name another: {paths.CLI} open --port <number>"))
    refresh_skills()
    HTTPD[0] = httpd
    announce(port, url)
    projects.note(ROOT)   # so another project's app can offer this one (the sidebar's menu of projects)
    with httpd:
        print(f"Spliced: {url}  (serving {ROOT}; {'restarted with new code' if restarted else 'Ctrl+C to stop'})", flush=True)
        if "--no-open" not in a and not restarted:
            threading.Timer(0.4, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
