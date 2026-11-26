# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""Films in production: each storyboard beat paired with its slice of the render and its reference scenes.

The storyboard is the red thread. Every beat has a window in film time, the library scenes it borrows from, a status
and the person's review notes, so any render can be cut up beat by beat and laid next to its plan and its references:
in Spliced's Build view (spliced open) and, for agents, in a pairing sheet.

  Remotion films   remotion/src/films/<slug>/storyboard.json (the plan) + cues.json (the times: beat id = key in
                   cues.scenes). Renders: remotion/out/<slug>-vN[-<beat>].mp4, each with a .json sidecar that
                   snapshots the beat times it was rendered with.
  HyperFrames      videos/<slug>/STORYBOARD.md (## Frame N) + index.html (data-start of each frame's composition).
                   Renders: videos/<slug>/renders/*.mp4. Review notes go to videos/<slug>/review.json.
  Folders          a project can sort its films into folders (spliced.json "folders", see `spliced folders`). A
                   Remotion film names its folder in storyboard.json ("folder") and renders to <folder>/renders/;
                   a HyperFrames film lives in its folder: <folder>/<slug>/ instead of videos/<slug>/.

usage:
  spliced film list
  spliced film status <slug>                       # beat by beat: window, status, references, open notes
  spliced film context <slug>                      # a new session's brief: plan, notes, cues, file map (~3k tokens)
  spliced film new <slug> --board "<board name>" [--folder <folder>]   # start a Remotion film from a Spliced board
  spliced film move <slug> <folder>                # put a film in one of the project's folders (- for none), renders too
  spliced film mark <slug> <beat> <status> [--done "what changed"]
  spliced film render <slug> [--beat <id>] [--scale 0.5] [--note "..."]
  spliced film render <slug> ... --background        # start it and return; then: spliced film render-status <slug>
  spliced film sheet <slug> [--beat <id>] [--render <file>] [--out <jpg>]
  spliced film sound-done <slug> <note-id> --done "what changed"   # sound notes (see sound.py)
  spliced film note <slug> <0:18.66 | beat> "note" [--by chat]    # pin a note to a moment (the Build view's N)
  spliced film notes <slug> [--all]                                 # the pinned notes, open first
  spliced film note-done <slug> <id> --done "what changed"          # close one (records the render with the fix)
  spliced film done <slug> <id>... --done "what changed"            # close any notes: pinned, beat or sound ids
  spliced film note-reply <slug> <id> "copy changed, voice pending" # progress on a note that stays open
  spliced film render <slug> --fixes <id>,<id> --note "..."         # render and close the notes it fixes
  spliced film render <slug> --beat 1..2 --pad 0 --scale 1          # a run of beats: the timeline so far, scene by scene
  spliced film assets <slug>                                        # every still and clip, where it's used
  spliced film takes <slug>                        # each sound track's takes (alternatives), chosen one marked
  spliced film take <slug> <track> <file> [--name ..] [--note ..]   # add a take; take-use <slug> <track> <id> picks one

Statuses: todo -> wip (being built) -> review (rendered, waiting for the person) -> changes (notes left) / approved.
`mark ... --done` files the open note in the beat's log with what was changed, and clears it.
"""
import datetime as dt, hashlib, json, os, re, stat, subprocess, sys, time

import paths
import profiles

ROOT = paths.ROOT
FILMS_DIR = paths.FILMS
OUT_DIR = paths.OUT
VIDEOS_DIR = paths.VIDEOS
REFS_DIR = paths.REFS
CACHE = paths.FRAMES_CACHE
STATUSES = ["todo", "wip", "review", "changes", "approved"]
VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v")


def rel(p):
    return paths.rel(p)


def today():
    return dt.date.today().isoformat()


def load_json(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(p, obj):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, p)


def slugify(s, n=28):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:n].strip("-")


# ---------- library ----------
_LIB = None


def library():
    """Every library scene by key (film/sNN), with its film's video file."""
    global _LIB
    if _LIB is None:
        _LIB = {}
        if os.path.isdir(REFS_DIR):
            for film in sorted(os.listdir(REFS_DIR)):
                d = load_json(os.path.join(REFS_DIR, film, "breakdown.json"))
                if not d:
                    continue
                for s in d.get("scenes", []):
                    _LIB[f"{film}/{s['id']}"] = {"film": film, "id": s["id"], "start": s["start"], "end": s["end"],
                                                 "title": s.get("title", ""), "file": d.get("file", ""), "brand": d.get("brand", "")}
    lib = dict(_LIB)
    up = load_json(paths.UPLOADS_INDEX, {}) or {}
    for x in up.get("items", []):  # uploaded references: images, GIFs, clips (uploads.py)
        lib[f"uploads/{x['id']}"] = {"film": "uploads", "id": x["id"], "start": 0, "end": x.get("duration") or 0,
                                     "title": x.get("title", ""), "file": x["file"], "brand": "Uploaded", "upload": True}
    return lib


# ---------- renders ----------
def probe_duration(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True, timeout=20).stdout.strip()
        return float(out)
    except Exception:
        return None


def render_entry(path, offset=0.0, side=None):
    st = os.stat(path)
    m = re.search(r"-v(\d+)", os.path.basename(path))
    e = {"file": rel(path), "name": os.path.basename(path), "mtime": st.st_mtime, "size": st.st_size,
         "version": int(m.group(1)) if m else None, "offset": offset, "span": None, "beats": None, "note": "", "beat": None}
    if side:
        e.update({k: side[k] for k in ("span", "beats", "note", "beat", "scale", "cues_hash", "created", "git", "own_sound") if k in side})
        if side.get("span"):
            e["offset"] = side["span"][0]
    return e


# ---------- Remotion films ----------
def cue_window(cues, beat):
    keys = beat.get("cue") or beat["id"]
    keys = keys if isinstance(keys, list) else [keys]
    w = [cues.get("scenes", {}).get(k) for k in keys]
    # A window is [start, end], or a scene object with "start" and "end" (and its own inner timings).
    w = [[x["start"], x["end"]] if isinstance(x, dict) else x for x in w if x]
    return [min(x[0] for x in w), max(x[1] for x in w)] if w else None


def cues_hash(cues):
    return hashlib.sha1(json.dumps({"d": cues.get("duration"), "s": cues.get("scenes")}, sort_keys=True).encode()).hexdigest()[:12]


def newest_code(d, skip=("storyboard.json", "review.json")):
    t = 0
    for dp, dn, fn in os.walk(d):
        dn[:] = [x for x in dn if x not in ("node_modules", "renders", "snapshots", "exports", "out", ".cache")]
        for f in fn:
            if f in skip or f.startswith("."):
                continue
            t = max(t, os.path.getmtime(os.path.join(dp, f)))
    return t


def _render_name(slug):
    return re.compile(rf"^{re.escape(slug)}(-(v\d+|draft)[^/]*)?\.(mp4|mov|webm)$")


def render_dirs(folder):
    """Where a Remotion film's renders are: its folder's renders/ first, then remotion/out (where they went before
    the film had a folder, and where a film in no folder renders). In a worktree whose renders go to the main
    checkout, there first and then the worktree's own (renders made before)."""
    out = []
    for home in dict.fromkeys([paths.render_home(), ROOT]):
        out += ([paths.renders_dir(folder, home)] if folder else []) + [paths.renders_dir("", home)]
    return list(dict.fromkeys(out))


def remotion_renders(slug, folder=""):
    pat, out = _render_name(slug), []
    for d in render_dirs(folder):
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if pat.match(f):
                p = os.path.join(d, f)
                out.append(render_entry(p, side=load_json(os.path.splitext(p)[0] + ".json")))
    return out


def film_folder(sb):
    """The folder a Remotion film's storyboard names, "" for none."""
    return paths.clean_folder((sb or {}).get("folder", ""))


def remotion_film(slug, films_dir=None):
    d = os.path.join(films_dir or FILMS_DIR, slug)
    sb = load_json(os.path.join(d, "storyboard.json"))
    if sb is None:
        return None
    cues_p = os.path.normpath(os.path.join(d, sb.get("cues", "cues.json")))
    cues = load_json(cues_p, {}) or {}
    lib = library()
    beats = []
    for i, b in enumerate(sb.get("beats", [])):
        w = cue_window(cues, b)
        beats.append({
            "id": b["id"], "n": i + 1, "title": b.get("title") or b["id"],
            "start": w[0] if w else None, "end": w[1] if w else None,
            "status": b.get("status", "todo"), "review": b.get("review", ""), "log": b.get("log", []),
            "refs": [r for r in b.get("refs", [])], "missing_refs": [r for r in b.get("refs", []) if r not in lib],
            "on_screen": b.get("on_screen", ""), "copy": b.get("copy", ""), "roles": b.get("roles", []),
            "sound": b.get("sound", ""), "notes": b.get("notes", ""), "cue": b.get("cue") or b["id"], "src": b.get("src", ""),
            "vo": b.get("vo", ""), "act": b.get("act", ""),
        })
    h = cues_hash(cues)
    code_t = max(newest_code(d), newest_code(os.path.dirname(cues_p)) if os.path.dirname(cues_p) != d else 0)
    folder = film_folder(sb)
    renders = remotion_renders(slug, folder)
    for r in renders:
        r["stale"] = bool(r.get("cues_hash") and r["cues_hash"] != h) or (not r.get("cues_hash") and os.path.exists(cues_p) and os.path.getmtime(cues_p) > r["mtime"])
        r["code_newer"] = code_t > r["mtime"] + 1
    renders.sort(key=lambda r: r["mtime"], reverse=True)
    acts(beats)
    spoken(beats, load_json(os.path.join(d, "sound.json"), {}) or {}, cues)
    board_lines(beats, sb.get("board", ""))
    film_text(beats, cues)
    return {
        "slug": slug, "engine": "remotion", "title": sb.get("title") or slug, "dir": rel(d),
        "folder": folder if folder in paths.FOLDER_NAMES else "",
        "renders_dir": rel(paths.renders_dir(folder if folder in paths.FOLDER_NAMES else "")),
        "storyboard": rel(os.path.join(d, "storyboard.json")), "message": sb.get("message", ""),
        "format": sb.get("format", "1920x1080"), "fps": sb.get("fps", 60), "profile": sb.get("profile", paths.DEFAULT_PROFILE), "style": sb.get("style", ""),
        "board": sb.get("board", ""), "composition": sb.get("composition", ""), "cues": rel(cues_p),
        "duration": cues.get("duration") or max([b["end"] or 0 for b in beats] or [0]),
        "beats": beats, "renders": renders, "editable": True,
        "warnings": (lambda miss: [] if not miss else [f"beat {miss[0]} has no window in cues.json scenes"] if len(miss) == 1
                     else [f"{len(miss)} beats have no window in cues.json scenes yet (not built): {', '.join(miss[:3])}, ..."])([b["id"] for b in beats if b["start"] is None])
                    + [f"beat {b['id']}: unknown reference {r}" for b in beats for r in b["missing_refs"]],
    }


# ---------- HyperFrames films ----------
ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def hf_compositions(html):
    comps = []
    for tag in re.findall(r"<[a-z]+\s[^>]*data-composition-src=\"[^\"]+\"[^>]*>", html):
        a = dict(ATTR.findall(tag))
        try:
            comps.append({"id": a.get("data-composition-id") or a.get("id", ""), "src": a["data-composition-src"],
                          "start": float(a.get("data-start", 0)), "dur": float(a.get("data-duration", 0))})
        except ValueError:
            continue
    return sorted(comps, key=lambda c: c["start"])


def hf_frames(md):
    """## Frame N headings with their `- key: value` bullets and the prose under them."""
    frames = []
    parts = re.split(r"(?m)^## ", md)
    for p in parts[1:]:
        head, _, body = p.partition("\n")
        m = re.match(r"Frame\s+(\d+)\s*[—–:-]?\s*(.*)$", head.strip())
        if not m:
            continue
        title = m.group(2).strip()
        src = None
        pm = re.search(r"\(([^()]*\.html)[^()]*\)\s*$", title)
        if pm:
            src = re.findall(r"[\w./-]+\.html", pm.group(1))[-1]
            title = title[: pm.start()].strip()
        fields, prose = {}, []
        for line in body.splitlines():
            bm = re.match(r"^- (\w+):\s*(.*)$", line)
            if bm and not prose:
                fields[bm.group(1)] = bm.group(2).strip()
            elif line.strip() or prose:
                prose.append(line)
        frames.append({"n": int(m.group(1)), "title": title, "src": fields.get("src") or src, "fields": fields,
                       "prose": "\n".join(prose).strip()})
    return frames


def hf_frontmatter(md):
    m = re.match(r"^---\n(.*?)\n---", md, re.S)
    out = {}
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            if v:
                out[k.strip()] = v.strip().strip('"')
    return out


def hf_dirs():
    """slug -> the folder of each HyperFrames film: videos/<slug>/, or <folder>/<slug>/ in one of the project's folders."""
    out = {}
    for base in [VIDEOS_DIR] + [paths.folder_path(f["folder"]) for f in paths.FOLDERS]:
        for s in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            if s not in out and not s.startswith(".") and os.path.isfile(os.path.join(base, s, "index.html")):
                out[s] = os.path.join(base, s)
    return out


def hf_dir(slug):
    return hf_dirs().get(slug) or os.path.join(VIDEOS_DIR, slug)


def hf_film(slug):
    d = hf_dir(slug)
    idx = os.path.join(d, "index.html")
    if not os.path.isfile(idx):
        return None
    html = open(idx, encoding="utf-8").read()
    comps = hf_compositions(html)
    if not comps:
        return None
    sbp = os.path.join(d, "STORYBOARD.md")
    md = open(sbp, encoding="utf-8").read() if os.path.isfile(sbp) else ""
    fm, frames = hf_frontmatter(md), hf_frames(md)
    root = re.search(r'data-composition-id="main"[^>]*data-duration="([\d.]+)"', html)
    duration = float(root.group(1)) if root else max(c["start"] + c["dur"] for c in comps)
    review = load_json(os.path.join(d, "review.json"), {}) or {}
    has_render = any(os.path.isdir(os.path.join(d, x)) and any(f.lower().endswith(VIDEO_EXT) for f in os.listdir(os.path.join(d, x))) for x in ("renders", "exports"))
    used, beats = set(), []
    for i, c in enumerate(comps):
        fr = next((f for f in frames if f["src"] and os.path.basename(f["src"]) == os.path.basename(c["src"])), None)
        if fr is None and len(frames) == len(comps):
            fr = frames[i]
        if fr:
            used.add(id(fr))
        nxt = comps[i + 1]["start"] if i + 1 < len(comps) and comps[i + 1]["start"] > c["start"] else c["start"] + c["dur"]
        f = (fr or {}).get("fields", {})
        rv = review.get("beats", {}).get(c["id"], {})
        built = has_render or f.get("status", "") in ("animated", "built", "done", "rendered")
        beats.append({
            "id": c["id"], "n": i + 1, "title": (fr or {}).get("title") or c["id"].replace("-", " "),
            "start": c["start"], "end": nxt, "tail": c["start"] + c["dur"],
            "status": rv.get("status") or ("review" if built else "todo"), "stage": f.get("status", ""),
            "review": rv.get("review", ""), "log": rv.get("log", []), "refs": rv.get("refs", []),
            "on_screen": f.get("scene", ""), "copy": f.get("voiceover", "").strip('"'), "roles": [x for x in [f.get("type"), f.get("beat")] if x],
            "sound": f.get("sfx", ""), "notes": (fr or {}).get("prose", ""), "src": c["src"], "cue": c["id"],
            "transition_in": f.get("transition_in", ""), "blueprint": f.get("blueprint", ""), "missing_refs": [],
        })
    code_t = newest_code(d, skip=("review.json",))
    renders = []
    for sub in ("renders", "exports"):
        sd = os.path.join(d, sub)
        if os.path.isdir(sd):
            for f in os.listdir(sd):
                if f.lower().endswith(VIDEO_EXT):
                    r = render_entry(os.path.join(sd, f))
                    r["stale"] = False
                    r["code_newer"] = code_t > r["mtime"] + 1
                    renders.append(r)
    renders.sort(key=lambda r: r["mtime"], reverse=True)
    acts(beats)
    return {
        "slug": slug, "engine": "hyperframes", "title": fm.get("title") or slug.replace("-", " ").capitalize(),
        "dir": rel(d), "folder": paths.folder_of(d), "renders_dir": rel(os.path.join(d, "renders")), "storyboard": rel(sbp) if md else rel(idx), "message": fm.get("message", ""),
        "format": (re.match(r"\d+x\d+", fm.get("format", "")) or [""])[0], "fps": 30, "profile": "", "board": "", "composition": "main", "duration": duration,
        "beats": beats, "renders": renders, "editable": True, "review_file": rel(os.path.join(d, "review.json")),
        "warnings": ([] if md else ["no STORYBOARD.md: beats come from index.html only"])
                    + ([] if not frames or len(used) == len(frames) else [f"{len(frames) - len(used)} storyboard frame(s) didn't match a composition in index.html"]),
    }


# ---------- the script: sections, what's said, what the board planned ----------
ACT_NAMES = {"open": "Opening", "opening": "Opening", "hook": "Hook", "bridge": "Bridge", "headline": "Headline",
             "payoff": "Payoff", "end": "End"}


def acts(beats):
    """Group beats into sections. A beat's own `act` wins; otherwise a title prefix ("open: ...", "bridge: ...") or a
    "chapter N" title starts a section, and beats without one stay in the section before them."""
    cur = ""
    for b in beats:
        a = (b.get("act") or "").strip()
        if not a:
            t = (b.get("title") or "").strip()
            m = re.match(r"^(chapter\s+\d+|act\s+\d+|part\s+\d+)\b", t, re.I) or re.match(r"^(\w+):\s", t)
            k = m.group(1).strip().lower() if m else ""
            if k and (k in ACT_NAMES or re.match(r"^(chapter|act|part)\s", k)):
                a = ACT_NAMES.get(k, k[:1].upper() + k[1:])
        cur = a or cur or "Film"
        b["act"] = cur


def spoken(beats, sound, cues=None):
    """The voice-over as recorded: sound.json voice tracks, each on the beat its first word falls in. A track's text is
    its name, or the line cues.json gives the same file (film.voLines text, or the beat's `sub`)."""
    film_c = (cues or {}).get("film") or {}
    text_of = {os.path.basename(v.get("src", "")): v.get("text") for v in film_c.get("voLines", []) or [] if v.get("text")}
    if (film_c.get("vo") or {}).get("src"):
        sub = next((e.get("sub") for e in film_c.get("beats", []) or [] if isinstance(e, dict) and e.get("sub")), None)
        if sub:
            text_of.setdefault(os.path.basename(film_c["vo"]["src"]), sub)
    lines = sorted([t for t in sound.get("tracks", []) if t.get("lane") == "voice" and t.get("start") is not None],
                   key=lambda t: t["start"])
    for b in beats:
        b["spoken"] = []
    for t in lines:
        for b in beats:
            if b["start"] is not None and b["start"] - 0.05 <= t["start"] < b["end"] - 0.05:
                b["spoken"].append({"id": t.get("id", ""), "text": text_of.get(os.path.basename(t.get("file", ""))) or t.get("name", ""), "start": t["start"],
                                    "dur": t.get("dur"), "file": t.get("file", "")})
                break


def film_text(beats, cues):
    """Best effort: the words a film's cues.json puts on screen, per beat (cues `film.beats[*]` copyText / line / copy keyed
    by storyboard id; word-timed `phrases` and a `todo` list inside a scene), so the script can show what's in the film."""
    found = {}

    def at(t):
        for b in beats:
            if b["start"] is not None and b["start"] - 0.01 <= t < b["end"]:
                return b["id"]
    for e in (cues.get("film") or {}).get("beats", []) or []:
        if not isinstance(e, dict) or not e.get("storyboard"):
            continue
        v = next((e[k] for k in ("copyText", "line", "copy") if isinstance(e.get(k), (str, list)) and e.get(k)), None)
        if v:
            found.setdefault(e["storyboard"], []).append(" / ".join(v) if isinstance(v, list) else v)
    for sc in (cues.get("scenes") or {}).values():
        if not isinstance(sc, dict):
            continue
        for ph in sc.get("phrases") or []:
            ws = [w for w in ph.get("words", []) if isinstance(w, list) and len(w) > 1]
            if ws and at(ws[0][1]):
                found.setdefault(at(ws[0][1]), []).append(" ".join(str(w[0]) for w in ws))
        td = sc.get("todo")
        if isinstance(td, dict) and td.get("items"):
            t = td.get("start", sc.get("start", 0))
            labels = [i.get("label") for i in td["items"] if i.get("label")]
            if labels and at(t):
                found.setdefault(at(t), []).append(". ".join(labels) + ".")
    for b in beats:
        if found.get(b["id"]):
            b["in_film"] = " / ".join(found[b["id"]])


def board_lines(beats, board_name):
    """What the board (the script before the film existed) planned for each beat, matched by beat name: shown in the
    script until the film's own copy and voice-over are written."""
    if not board_name:
        return
    items = ((load_json(paths.state_file(), {}) or {}).get("boards", {}).get(board_name) or {}).get("items", [])
    by_title = {}
    for it in items:
        by_title.setdefault((it.get("beat") or "").strip().lower(), it)
    for b in beats:
        it = by_title.get((b.get("title") or "").strip().lower())
        if it:
            b["board"] = {k: it.get(k, "") for k in ("copy", "vo", "note") if it.get(k)}


# ---------- notes at a moment: the person's notes pinned to a frame of a render ----------
# Kept with the plan: storyboard.json "pins" (Remotion) or review.json "pins" (HyperFrames), a list of
#   {"id", "t": film seconds, "beat": beat id at t, "render": "companion-v33.mp4", "note", "by": "person"|"chat"|"claude",
#    "at", "status": "open"|"done", "done": "what changed", "done_at", "done_in": "companion-v34.mp4"}
# "at" and "done_at" are local date and time to the second (the app shows both); a "done_at" from before is a date alone.
def _pin_store(slug, p=None):
    p = p or (remotion_film(slug) or hf_film(slug))
    if not p:
        raise KeyError(f"no film called {slug}")
    path = _sb_path(slug) if p["engine"] == "remotion" else os.path.join(ROOT, p["review_file"])
    return p, path, load_json(path, {}) or {}


def pins(slug, p=None):
    return _pin_store(slug, p)[2].get("pins", [])


def _beat_at(p, t, render=None):
    r = next((x for x in p["renders"] if render in (x["name"], x["file"])), None) if render else None
    wins = [(b["id"], *((r or {}).get("beats") or {}).get(b["id"], [b["start"], b["end"]])) for b in p["beats"]]
    hit = None
    for bid, a, _e in wins:
        if a is not None and t >= a - 0.001:
            hit = bid
    return hit


def parse_time(x):
    """0:18.66, 18.66 or 1:02:03.5 -> seconds."""
    parts = str(x).strip().split(":")
    if not all(re.fullmatch(r"\d+(\.\d+)?", q) for q in parts):
        raise ValueError(f"not a time: {x}")
    s = 0.0
    for q in parts:
        s = s * 60 + float(q)
    return s


def add_pin(slug, t, note, by="person", render=None, beat=None):
    p, path, doc = _pin_store(slug)
    if not str(note).strip():
        raise ValueError("a note needs some words")
    t = round(max(0.0, min(float(t), p["duration"] or float(t))), 3)
    render = render or (p["renders"][0]["name"] if p["renders"] else "")
    beat = beat or _beat_at(p, t, render)
    pin = {"id": secrets_hex(), "t": t, "beat": beat, "render": render, "note": str(note).strip(), "by": by,
           "at": dt.datetime.now().isoformat(timespec="seconds"), "status": "open"}
    doc.setdefault("pins", []).append(pin)
    doc["pins"].sort(key=lambda x: x["t"])
    # a note on a rendered beat asks for a change, like the beat's own note box
    if beat and p["engine"] == "remotion":
        b = next((x for x in doc.get("beats", []) if x["id"] == beat), None)
        if b and b.get("status") in ("review", "approved"):
            b["status"] = "changes"
    elif beat:
        rb = doc.setdefault("beats", {}).setdefault(beat, {})
        if rb.get("status", "review") in ("review", "approved"):
            rb["status"] = "changes"
    write_json(path, doc)
    return pin


def update_pin(slug, pid, patch=None, done=None, done_in=None, delete=False, reply=None, by="claude"):
    p, path, doc = _pin_store(slug)
    lst = doc.get("pins", [])
    pin = next((x for x in lst if x["id"] == pid), None)
    if not pin:
        raise KeyError(f"no note {pid} on {slug}: {', '.join(x['id'] for x in lst) or 'none yet'}")
    if delete:
        lst.remove(pin)
    elif reply is not None:  # progress on a note that isn't fixed yet ("copy changed, voice pending"): it stays open
        pin.setdefault("replies", []).append({"at": dt.datetime.now().isoformat(timespec="seconds"), "by": by, "text": str(reply).strip()})
    elif done is not None:
        pin.update({"status": "done", "done": done or "done", "done_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "done_in": done_in or (p["renders"][0]["name"] if p["renders"] else "")})
    else:
        for k, v in (patch or {}).items():
            if k == "note":
                pin["note"] = str(v).strip()
            elif k == "t":
                pin["t"] = round(float(v), 3)
                pin["beat"] = _beat_at(p, pin["t"], pin.get("render"))
            elif k == "status" and v in ("open", "done"):
                pin["status"] = v
                if v == "open":
                    for x in ("done", "done_at", "done_in"):
                        pin.pop(x, None)
            else:
                raise ValueError(f"notes have note, t and status, not {k!r}")
        lst.sort(key=lambda x: x["t"])
    write_json(path, doc)
    return lst


def close_notes(slug, ids, done, done_in=None):
    """Close the person's notes once a render has the fix: note ids (pinned to a frame), beat ids (the beat's note box)
    or sound note ids. Returns what was closed and what wasn't found."""
    p, path, doc = _pin_store(slug)
    pins = {x["id"]: x for x in doc.get("pins", [])}
    done_in = done_in or (p["renders"][0]["name"] if p["renders"] else "")
    closed, missing = [], []
    for i in ids:
        if i in pins:
            if pins[i].get("status") != "done":
                update_pin(slug, i, done=done, done_in=done_in)
            closed.append(i)
        elif any(b["id"] == i for b in p["beats"]):
            b = next(b for b in p["beats"] if b["id"] == i)
            if b.get("review"):
                update_beat(slug, i, {}, done=done)
            closed.append(i)
        elif i in (sound_notes(slug, p) or {}):
            update_sound_note(slug, i, {}, done=done)
            closed.append(i)
        else:
            missing.append(i)
    return closed, missing


def open_notes(p, span=None):
    """Every open note on the film (pinned, beat and sound), optionally only those inside a span of film time."""
    a, e = span or (0, 1e9)
    inside = lambda t0, t1=None: t0 is not None and t0 < e and (t1 if t1 is not None else t0) >= a
    out = [("note", x["id"], x["t"], x["note"]) for x in p.get("pins", []) if x.get("status") != "done" and inside(x["t"])]
    out += [("beat", b["id"], b["start"], b["review"]) for b in p["beats"] if b.get("review") and inside(b["start"], b["end"])]
    out += [("sound", k, v.get("start"), v["note"]) for k, v in (p.get("sound_notes") or {}).items() if v.get("note") and inside(v.get("start"), v.get("end"))]
    return sorted(out, key=lambda x: x[2] or 0)


# ---------- who picks up the notes: auto (any chat working on the film fixes open notes, and `watch` wakes one up)
# or manual (notes wait until the person copies them into a prompt). Kept as "notes_mode" next to the pins.
NOTE_MODES = ("auto", "manual")
WATCH_DIR = paths.WATCH


def notes_mode(slug, p=None):
    return (_pin_store(slug, p)[2].get("notes_mode") or "auto")


def set_notes_mode(slug, mode):
    if mode not in NOTE_MODES:
        raise ValueError(f"notes mode is auto or manual, not {mode!r}")
    p, path, doc = _pin_store(slug)
    doc["notes_mode"] = mode
    write_json(path, doc)
    return mode


def _watch_file(slug):
    return os.path.join(WATCH_DIR, f"{slug}.json")


def watcher(slug):
    """What a chat watching this film's notes is doing: {state: "waiting"|"working", at, notes} or None.
    "waiting" only counts while its heartbeat is fresh (the watch writes it every couple of seconds)."""
    w = load_json(_watch_file(slug), None)
    if not w or not w.get("at"):
        return None
    age = time.time() - w["at"]
    if w.get("state") == "waiting" and age > 20:
        return None
    if w.get("state") == "working" and age > 3 * 3600:
        return None
    return {"state": w.get("state"), "at": w["at"], "notes": w.get("notes", [])}


def _note_keys(p):
    """Every open note with a key that changes when its words do (a beat or sound note rewritten counts as new)."""
    h = lambda t: hashlib.sha1(str(t).encode()).hexdigest()[:8]
    out = []
    for kind, nid, t, text in open_notes(p):
        out.append((f"{kind}:{nid}" if kind == "note" else f"{kind}:{nid}:{h(text)}", kind, nid, t, text))
    return out


def secrets_hex():
    import secrets
    return secrets.token_hex(3)


# ---------- assets: every still and clip a film uses ----------
# Optional metadata: remotion/src/films/<slug>/assets.json {"<path under remotion/public>": {"source": "higgsfield",
#   "model": "...", "prompt": "...", "credits": 12, "note": "..."}}. Without it, the folder says what an asset is.
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")
KIND_BY_DIR = {"shots": "generated", "placeholders": "placeholder", "refs": "reference", "plates": "generated", "ui": "ui"}


def _where(node, needle, path=()):
    """Every place in a JSON tree whose string value mentions needle: (path, label of the nearest object)."""
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str) and needle in v:
                out.append((path + (k,), node.get("label") or node.get("name") or ""))
            else:
                out += _where(v, needle, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, str) and needle in v:
                out.append((path + (i,), ""))
            else:
                out += _where(v, needle, path + (i,))
    return out


def assets(slug):
    p = production(slug)
    if not p:
        raise KeyError(f"no film called {slug}")
    if p["engine"] != "remotion":
        return {"slug": slug, "assets": [], "note": "Assets are listed for Remotion films (remotion/public/films/<slug>/)."}
    pub = paths.PUBLIC
    base = os.path.join(pub, "films", slug)
    src_dir = os.path.join(FILMS_DIR, slug)
    meta = load_json(os.path.join(src_dir, "assets.json"), {}) or {}
    code = {}
    for f in sorted(os.listdir(src_dir)) if os.path.isdir(src_dir) else []:
        if f.endswith((".tsx", ".ts")) or f in ("cues.json",):
            code[f] = open(os.path.join(src_dir, f), encoding="utf-8").read()
    cues = load_json(os.path.join(src_dir, "cues.json"), {}) or {}
    beat_of_cue = {}
    for b in p["beats"]:
        for k in (b["cue"] if isinstance(b["cue"], list) else [b["cue"]]):
            beat_of_cue.setdefault(k, []).append(b["n"])
    out = []
    for dp, dn, fn in os.walk(base):
        dn[:] = sorted(x for x in dn if x not in ("audio",))
        for f in sorted(fn):
            if not f.lower().endswith(IMG_EXT + VIDEO_EXT):
                continue
            full = os.path.join(dp, f)
            under = os.path.relpath(full, pub)          # what staticFile() takes: films/<slug>/shots/x.png
            top = os.path.relpath(full, base).split(os.sep)[0]
            m = meta.get(under) or meta.get(os.path.relpath(full, base)) or {}
            uses, seq = [], _seq_prefix(under)
            for name, text in code.items():
                if name == "cues.json":
                    for path, label in _where(cues, under):
                        where, beats = ".".join(str(x) for x in path[:2]), []
                        if len(path) > 1 and path[0] == "scenes":
                            sc = cues["scenes"].get(path[1])
                            beats = beat_of_cue.get(path[1]) or ([b["n"] for b in p["beats"] if isinstance(sc, dict) and b["start"] is not None
                                                                 and sc.get("start", 0) - 0.01 <= b["start"] < sc.get("end", 0)])
                        elif len(path) > 2 and path[:2] == ("film", "beats"):
                            e = cues["film"]["beats"][path[2]]
                            sid = e.get("storyboard") if isinstance(e, dict) else None
                            beats = [b["n"] for b in p["beats"] if b["id"] == sid]
                            where = f"film.beats {sid or e.get('id', path[2]) if isinstance(e, dict) else path[2]}"
                        uses.append({"file": "cues.json", "where": where, "label": label, "beats": beats})
                elif under in text or (f in text and len(f) > 6) or (seq and (seq in text or os.path.dirname(under) + "/" in text)):
                    uses.append({"file": name, "where": "", "label": "", "beats": []})   # (a render's frames are named by their prefix or folder)
            out.append({"file": rel(full), "path": under, "name": f, "dir": os.path.relpath(dp, base),
                        "type": "video" if f.lower().endswith(VIDEO_EXT) else "image",
                        "kind": m.get("source") and ("generated" if m["source"] in ("higgsfield", "generated") else m["source"]) or KIND_BY_DIR.get(top, "other"),
                        "size": os.path.getsize(full), "mtime": os.path.getmtime(full), "uses": uses,
                        **{k: m[k] for k in ("source", "model", "prompt", "credits", "note", "job") if k in m}})
    out.sort(key=lambda a: (a["dir"], a["name"]))
    return {"slug": slug, "dir": rel(base), "meta": rel(os.path.join(src_dir, "assets.json")), "assets": out, "stacks": stack_assets(out)}


# ---------- the asset library: every generated still, clip and sound across films ----------
# Where media lives: remotion/public/films/<slug>/ (Remotion films), videos/<slug>/assets/ (HyperFrames films) and
# music/ (beds). What made it comes from the film's assets.json when it says so, else from the folder:
#   shots/ plates/ -> Higgsfield · el/ sfx-el/ and a Remotion film's audio/ -> ElevenLabs · audio/fx/ -> made in code
#   placeholders/ -> placeholder · refs/ -> reference still · ui/ and HyperFrames stills -> design (UI, Figma exports).
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".ogg")
STOCK_SOURCES = ("pexels", "pixabay", "unsplash", "nasa", "openverse")  # free libraries, via stock.py
MEDIA_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif") + VIDEO_EXT + AUDIO_EXT
SKIP_DIRS = {"brand", "icons", "fonts", "node_modules", "renders", "snapshots", "exports", ".cache"}


def _audio_role(rel_path):
    p = rel_path.lower()
    if re.search(r"(^|/)(vo|voice)[/-]|vo-|voice|narrat|kai|lauren|nick", p):
        return "voice"
    if re.search(r"(^|/)(fx|sfx|sfx-el|sfx-raw)/|flick|note-|typing|impact|whoosh|click|swoosh|pop|riser", p):
        return "effect"
    return "music"


def _source(rel_path, typ, film_engine):
    p = "/" + rel_path.lower()
    if typ == "audio":
        if "/fx/" in p and film_engine == "remotion":
            return "code"
        if "/el/" in p or "/sfx-el/" in p or "/sfx-raw/" in p or film_engine == "remotion" or "/style-tests/" in p:
            return "elevenlabs"
        return "other"
    if "/stock/" in p:
        return "stock"
    if p.startswith("/uploads/"):
        return "upload"       # the person's own files, added from Spliced's Assets (stock.py add_file)
    if "/placeholders/" in p:
        return "placeholder"
    if "/refs/" in p:
        return "reference"
    if "/3d/" in p:
        return "blender"
    if re.search(r"_\d{3,5}\.(png|jpe?g|webp)$", p):
        return "code"          # a numbered frame sequence is rendered (Remotion, a script), never a generation
    if "/shots/" in p or "/plates/" in p:
        return "higgsfield"
    if "/ui/" in p or film_engine == "hyperframes":
        return "design"
    return "other"


def _meta_for_dir(meta, pub_rel):
    """assets.json can describe a whole folder (a key ending in "/", e.g. a rendered frame sequence): the deepest match."""
    keys = [k for k in (meta or {}) if k.endswith("/") and pub_rel.startswith(k)]
    return meta[max(keys, key=len)] if keys else None


# ---------- stacks: the frames of one render, or one numbered set, shown as one thing ----------
# A Blender or code render lands as f_0001.png … f_0120.png: 120 files that are one asset to a person. Images in the
# same folder whose names differ only by a number are a stack. Every frame stays in the list, marked with its stack
# and its number, so an agent or an edit still reaches each one; the app shows the stack as one card.
_NUMBERED = re.compile(r"^(.*?)(\d{1,6})(\.(?:png|jpe?g|webp|avif|gif|svg))$", re.I)
_PLAIN_PREFIX = {"", "f", "s", "frame", "frames", "img", "image", "images", "render", "seq", "out", "still"}
STACK_MIN = 3


def stack_assets(items):
    """Mark the images in `items` that belong to a stack (a["stack"] = its id, a["frame"] = its number) and return the
    stacks, each {id, name, film, dir, count, first, last, pattern, cover, size, mtime, source, used, label}.
    The id is the frames' path with the number as "#": "…/glass-icon/f_#.png"."""
    groups = {}
    for a in items:
        m = _NUMBERED.match(a["file"]) if a.get("type") == "image" else None
        if m:
            groups.setdefault((m.group(1), m.group(3).lower()), []).append((int(m.group(2)), len(m.group(2)), a))
    out = []
    for (prefix, ext), mem in groups.items():
        if len(mem) < STACK_MIN:
            continue
        mem.sort(key=lambda x: x[0])
        sid = f"{prefix}#{ext}"
        for n, _, a in mem:
            a["stack"], a["frame"] = sid, n
        frames = [a for _, _, a in mem]
        stem = os.path.basename(prefix).strip("_-. ")
        folder = os.path.basename(os.path.dirname(prefix))
        used = [a.get("used") for a in frames if "used" in a] or [bool(a.get("uses")) for a in frames]
        labels = {a.get("label") for a in frames if a.get("label")}
        out.append({
            "id": sid, "name": folder if stem.lower() in _PLAIN_PREFIX or len(stem) < 3 else stem, "film": frames[0].get("film"), "dir": frames[0].get("dir"),
            "count": len(frames), "first": mem[0][0], "last": mem[-1][0], "pattern": f"{prefix}{'#' * mem[0][1]}{ext}", "cover": frames[len(frames) // 2]["file"],
            "size": sum(a.get("size", 0) for a in frames), "mtime": max(a.get("mtime", 0) for a in frames), "source": frames[0].get("source") or frames[0].get("kind"),
            "used": None if all(u is None for u in used) else any(used), "label": labels.pop() if len(labels) == 1 else "",
        })
    return out


def _seq_prefix(pub_rel):
    """The prefix a frame sequence is referenced by ("films/x/shots/sunrise/s_" for …/s_0012.png), or None."""
    m = re.match(r"(.*?)\d{3,5}\.(png|jpe?g|webp)$", pub_rel, re.I)
    return m.group(1) if m else None


def _asset_roots():
    """Where assets live: (film, engine, the folder of files, the folder of the film's code, the project folder it is in)
    for each film, the music beds, a top-level assets/ (shared by every folder) and each of the project's folders'
    own files (whatever the person put there that isn't a film or a render)."""
    roots = []
    if os.path.isdir(FILMS_DIR):
        pub = paths.PUBLIC_FILMS
        for slug in sorted(os.listdir(pub)) if os.path.isdir(pub) else []:
            sb = load_json(os.path.join(FILMS_DIR, slug, "storyboard.json"), {}) or {}
            f = film_folder(sb)
            roots.append((slug, "remotion", os.path.join(pub, slug), os.path.join(FILMS_DIR, slug), f if f in paths.FOLDER_NAMES else ""))
    for slug, d in hf_dirs().items():
        if os.path.isdir(os.path.join(d, "assets")):
            roots.append((slug, "hyperframes", os.path.join(d, "assets"), d, paths.folder_of(d)))
    if os.path.isdir(paths.MUSIC):
        roots.append(("music", "beds", paths.MUSIC, None, ""))
    shared = os.path.join(ROOT, "assets")
    if os.path.isdir(shared) and not paths.folder_of(shared):
        roots.append(("", "shared", shared, None, ""))
    for f in paths.FOLDERS:
        d = paths.folder_path(f["folder"])
        if os.path.isdir(d):
            roots.append(("", "folder", d, None, f["folder"]))
    return roots


def _folder_skip(base, dp, dn):
    """In a folder's own files: not its renders, its HyperFrames films (listed as films), another folder, or a dot name."""
    keep = []
    for x in dn:
        full = os.path.join(dp, x)
        if x.startswith(".") or x in SKIP_DIRS or os.path.isfile(os.path.join(full, "index.html")):
            continue
        if dp == base and x == "renders":
            continue
        if any(os.path.realpath(full) == os.path.realpath(paths.folder_path(f)) for f in paths.FOLDER_NAMES):
            continue
        keep.append(x)
    return sorted(keep)


def _assets_stamp(roots):
    """Everything library_assets reads, as names, times and sizes. While this is the same, so is its answer.
    (Naming the files is a tenth of the work: the rest is reading each film's code to see which files it uses.)"""
    seen = [tuple(r) for r in roots]
    for _, engine, base, src, _ in roots:
        tops = [t for t in (src, base) if t and os.path.isdir(t)]
        if len(tops) == 2 and (base + os.sep).startswith(src + os.sep):
            tops = [src]   # the files sit inside the film's own folder: one walk sees both
        for top in tops:
            for dp, dn, fn in os.walk(top):
                dn[:] = _folder_skip(top, dp, dn) if engine == "folder" else sorted(x for x in dn if x not in SKIP_DIRS)
                for f in sorted(fn):
                    try:
                        st = os.stat(os.path.join(dp, f))
                    except OSError:
                        continue
                    seen.append((dp, f, st.st_mtime_ns, st.st_size))
    return hash(tuple(seen))


_ASSETS = (None, None)   # (stamp, answer): the last answer, kept while nothing it was made from has changed


def library_assets():
    """Every image, clip and sound file across the films, with what made it, which film and whether it's used.
    The answer is kept until a file it was made from changes, so treat it as read-only."""
    global _ASSETS
    roots = _asset_roots()
    stamp = _assets_stamp(roots)
    if _ASSETS[0] == stamp:
        return _ASSETS[1]
    out, films = [], []
    for slug, engine, base, src, folder in roots:
        meta = load_json(os.path.join(src, "assets.json"), {}) if src else {}
        labels = {}  # a readable name for a file: the line a voice track speaks, a take's name, a shot's label
        if src:
            for t in (load_json(os.path.join(src, "sound.json"), {}) or {}).get("tracks", []):
                if t.get("file") and t.get("name") and t.get("lane") != "sfx":
                    labels.setdefault(t["file"], t["name"])
            for tr in ((load_json(os.path.join(src, "takes.json"), {}) or {}).get("tracks") or {}).values():
                for tk in tr.get("takes", []):
                    if tk.get("file") and tk.get("name"):
                        labels.setdefault(tk["file"], tk["name"])
            cj = load_json(os.path.join(src, "cues.json"), {}) or {}
            for grp in ("shots", "plates"):
                for v in (cj.get(grp) or {}).values():
                    if isinstance(v, dict) and v.get("src") and v.get("label"):
                        labels.setdefault("remotion/public/" + v["src"], v["label"])
        text = ""
        if src and os.path.isdir(src):  # the film's code, cues and sound plan: is the file named anywhere?
            for dp, dn, fn in os.walk(src):
                dn[:] = [x for x in dn if x not in SKIP_DIRS | {"assets"}]
                for f in fn:
                    if f.endswith((".tsx", ".ts", ".json", ".html", ".js", ".md")) and f not in ("assets.json", "takes.json"):
                        try:
                            text += open(os.path.join(dp, f), encoding="utf-8").read()
                        except (OSError, UnicodeDecodeError):
                            pass
        n = 0
        for dp, dn, fn in os.walk(base):
            dn[:] = _folder_skip(base, dp, dn) if engine == "folder" else sorted(x for x in dn if x not in SKIP_DIRS)
            for f in sorted(fn):
                if not f.lower().endswith(MEDIA_EXT):
                    continue
                full = os.path.join(dp, f)
                inner = os.path.relpath(full, base)
                typ = "audio" if f.lower().endswith(AUDIO_EXT) else "video" if f.lower().endswith(VIDEO_EXT) else "image"
                pub_rel = os.path.relpath(full, paths.PUBLIC)
                m = (meta or {}).get(pub_rel) or (meta or {}).get(inner) or _meta_for_dir(meta, pub_rel) or {}
                source = m.get("source") or ("upload" if engine in ("folder", "shared") else _source(inner, typ, engine))   # a folder's own files are the person's
                st = os.stat(full)
                out.append({
                    "file": rel(full), "name": f, "label": m.get("label") or labels.get(rel(full), ""), "film": slug, "engine": engine, "dir": os.path.dirname(inner) or ".",
                    "folder": folder,
                    "type": typ, "role": _audio_role(inner) if typ == "audio" else ("clip" if typ == "video" else "still"),
                    "source": source, "generated": source in ("higgsfield", "elevenlabs"),
                    "stock": source in STOCK_SOURCES or source == "stock",
                    # a frame sequence is named by its folder or its prefix ("…/sunrise/s_"), not by each frame
                    "used": None if not text else (f in text or inner in text or (_seq_prefix(pub_rel) is not None and (
                        _seq_prefix(pub_rel) in text or os.path.dirname(pub_rel) + "/" in text))),
                    "raw": bool(re.search(r"-raw\b|/sfx-raw/|/raw/", inner)),
                    "size": st.st_size, "mtime": st.st_mtime,
                    **{k: m[k] for k in ("model", "prompt", "credits", "note", "job", "voice", "author", "author_url", "page", "license", "license_url", "credit") if k in m},
                })
                n += 1
        if n and slug:
            films.append({"slug": slug, "engine": engine, "count": n, "folder": folder})
    out.sort(key=lambda a: -a["mtime"])
    answer = {"assets": out, "films": films, "stacks": stack_assets(out)}
    _ASSETS = (stamp, answer)
    return answer


# ---------- productions ----------
def production(slug):
    p = remotion_film(slug) or hf_film(slug)
    if p:
        p["sound_notes"] = sound_notes(slug, p)
        p["pins"] = pins(slug, p)
        p["notes_mode"] = notes_mode(slug, p)
        p["watcher"] = watcher(slug)
        p["sound_stamp"] = sound_stamp(p)
    return p


def sound_stamp(p):
    """What the film's sound was last written from: the mtimes and sizes of its sound.json and takes.json (Remotion) or
    index.html (HyperFrames). The Build view polls it and reloads the Sound panel when it changes, so a new mix is heard
    without a reload."""
    d = os.path.join(ROOT, p["dir"])
    files = ["sound.json", "takes.json"] if p.get("engine") == "remotion" else ["index.html"]
    out = []
    for f in files:
        try:
            st = os.stat(os.path.join(d, f))
            out.append(f"{f}:{st.st_mtime_ns}:{st.st_size}")
        except OSError:
            pass
    return "|".join(out)


# ---------- sound notes: notes on music ranges, voice ranges and single sound effects ----------
# Kept next to the beat notes: storyboard.json "sound" (Remotion) or review.json "sound" (HyperFrames), keyed by id:
#   {"kind": "music"|"voice"|"sfx"|"mix", "label": "bars 9-12", "start": 16.0, "end": 21.3, "ref": "el-sfx-3",
#    "note": "the bridge drags, cut a bar", "at": "2026-11-17", "log": [{"at", "note", "done"}]}
def _sound_store(slug, p=None):
    p = p or (remotion_film(slug) or hf_film(slug))
    if not p:
        raise KeyError(f"no film called {slug}")
    path = _sb_path(slug) if p["engine"] == "remotion" else os.path.join(ROOT, p["review_file"])
    return path, load_json(path, {}) or {}


def sound_notes(slug, p=None):
    return _sound_store(slug, p)[1].get("sound", {})


def update_sound_note(slug, nid, patch, done=None):
    """Upsert a sound note. An empty note without `done` deletes it; `done` files the note in its log and clears it."""
    path, doc = _sound_store(slug)
    notes = doc.setdefault("sound", {})
    n = notes.get(nid, {})
    if done is not None:
        if not n:
            raise KeyError(f"no sound note {nid}: {', '.join(notes) or 'none yet'}")
        n.setdefault("log", []).append({"at": today(), "note": n.get("note", ""), "done": done})
        n["note"] = ""
    else:
        for k in ("kind", "label", "start", "end", "ref", "note"):
            if k in patch:
                n[k] = patch[k]
        n["at"] = today()
        if not n.get("note") and not n.get("log"):
            notes.pop(nid, None)
            write_json(path, doc)
            return notes
    notes[nid] = n
    write_json(path, doc)
    return notes


# ---------- takes: alternatives for a sound track, auditioned under the picture and chosen ----------
# remotion/src/films/<slug>/takes.json (HyperFrames: videos/<slug>/takes.json), keyed by sound.json track id:
#   {"tracks": {"music": {"label": "Score", "chosen": "f2-extended",
#                         "takes": [{"id": "f2-extended", "name": "F2 extended", "file": "remotion/public/...wav",
#                                    "dur": 69.66, "offset": 0, "note": "..."}]}}}
# `chosen` is the take the film plays. Choosing one (Spliced Sound panel, Use) writes it into sound.json at once
# (the track's file and dur; the music track's name too), so the next render uses it, and the film's sound script
# (remotion/scripts/score_sketch.py sound) keeps it when it rewrites sound.json.
TAKES_NOTE = ("Alternatives for the film's sound tracks, keyed by sound.json track id. `chosen` is the take the film plays: "
              "choosing one in Spliced (Build, Sound, Takes, Use) or with `spliced film take-use` writes its file "
              "into sound.json, and score_sketch.py sound keeps it. Take: id, name, file (repo path, under remotion/public), "
              "dur (seconds), offset (seconds into the file to start, default 0), note.")


def _takes_path(slug, p=None):
    """takes.json's path and a light description of the film (engine, dir, duration): no render scan."""
    if p is None:
        rd, hd = os.path.join(FILMS_DIR, slug), hf_dir(slug)
        if os.path.isfile(os.path.join(rd, "storyboard.json")):
            sb = load_json(os.path.join(rd, "storyboard.json"), {}) or {}
            cues = load_json(os.path.normpath(os.path.join(rd, sb.get("cues", "cues.json"))), {}) or {}
            p = {"engine": "remotion", "dir": rel(rd), "duration": cues.get("duration")}
        elif os.path.isfile(os.path.join(hd, "index.html")):
            p = {"engine": "hyperframes", "dir": rel(hd), "duration": None}
        else:
            raise KeyError(f"no film called {slug}")
    return os.path.join(ROOT, p["dir"], "takes.json"), p


def takes(slug, p=None):
    """The film's takes, with each track's current file from sound.json (Remotion) and whether each take's file exists."""
    path, p = _takes_path(slug, p)
    doc = load_json(path, {}) or {}
    tracks = doc.get("tracks", {})
    sj = load_json(os.path.join(ROOT, p["dir"], "sound.json"), {}) or {}
    cur = {t.get("id"): t for t in sj.get("tracks", [])}
    out = {}
    for tid, tr in tracks.items():
        s = cur.get(tid, {})
        out[tid] = {**tr, "current": s.get("file", ""), "track_name": s.get("name", ""), "lane": s.get("lane", ""),
                    "start": s.get("start"), "in_mix": tid in cur,
                    "takes": [{**t, "exists": os.path.exists(os.path.join(ROOT, t.get("file", "")))} for t in tr.get("takes", [])]}
    return {"file": rel(path), "engine": p["engine"], "writes_mix": p["engine"] == "remotion", "tracks": out}


def _take_id(name, existing):
    base = slugify(name, 40) or "take"
    tid, k = base, 2
    while tid in existing:
        tid, k = f"{base}-{k}", k + 1
    return tid


def add_take(slug, track, file, name="", note="", offset=0.0, label=""):
    path, p = _takes_path(slug)
    fp = os.path.abspath(os.path.join(ROOT, file)) if not os.path.isabs(file) else file
    if not os.path.isfile(fp):
        raise ValueError(f"no such file: {file}")
    if p["engine"] == "remotion" and not rel(fp).startswith("remotion/public/"):
        raise ValueError("a take for a Remotion film has to live under remotion/public/ so the render can play it")
    doc = load_json(path, {}) or {}
    doc["_note"] = TAKES_NOTE
    tr = doc.setdefault("tracks", {}).setdefault(track, {"label": label or track, "chosen": "", "takes": []})
    if label:
        tr["label"] = label
    if any(t.get("file") == rel(fp) for t in tr["takes"]):
        raise ValueError(f"{rel(fp)} is already a take on {track}")
    t = {"id": _take_id(name or os.path.splitext(os.path.basename(fp))[0], {x["id"] for x in tr["takes"]}),
         "name": name or os.path.splitext(os.path.basename(fp))[0], "file": rel(fp), "dur": round(probe_duration(fp) or 0, 3)}
    if offset:
        t["offset"] = round(float(offset), 3)
    if note:
        t["note"] = note
    tr["takes"].append(t)
    write_json(path, doc)
    return t


def use_take(slug, track, take_id):
    """Make take_id the track's chosen take. Remotion: writes its file (and dur; name on the music lane) into sound.json."""
    path, p = _takes_path(slug)
    doc = load_json(path, {}) or {}
    tr = doc.get("tracks", {}).get(track)
    if not tr:
        raise KeyError(f"no takes for track {track}: {', '.join(doc.get('tracks', {})) or 'none yet'}")
    t = next((x for x in tr.get("takes", []) if x["id"] == take_id), None)
    if not t:
        raise KeyError(f"track {track} has no take {take_id}: {', '.join(x['id'] for x in tr.get('takes', []))}")
    if not os.path.exists(os.path.join(ROOT, t["file"])):
        raise ValueError(f"{t['file']} is missing")
    applied = False
    if p["engine"] == "remotion":
        sp = os.path.join(ROOT, p["dir"], "sound.json")
        sj = load_json(sp)
        st = next((x for x in (sj or {}).get("tracks", []) if x.get("id") == track), None)
        if not st:
            raise KeyError(f"sound.json has no track {track}")
        dur = float(t.get("dur") or probe_duration(os.path.join(ROOT, t["file"])) or 0) - float(t.get("offset") or 0)
        if st.get("lane") == "music":
            dur = min(dur, max(0.0, float(p["duration"] or dur) - float(st.get("start") or 0)))
            st["name"] = t["name"]
        st.update({"file": t["file"], "offset": float(t.get("offset") or 0), "take": t["id"]})
        if dur > 0:
            st["dur"] = round(dur, 3)
        write_json(sp, sj)
        applied = True
    tr["chosen"] = take_id
    doc["_note"] = TAKES_NOTE
    write_json(path, doc)
    return {**takes(slug, p), "applied": applied}


def slugs():
    out = []
    if os.path.isdir(FILMS_DIR):
        out += [s for s in sorted(os.listdir(FILMS_DIR)) if os.path.isfile(os.path.join(FILMS_DIR, s, "storyboard.json"))]
    out += [s for s in hf_dirs() if s not in out]
    return out


def worktrees():
    """The project's other git worktrees (Conductor workspaces, `git worktree add`), for a main checkout:
    [(the project's folder in it, its branch, the worktree's name)]. A worktree itself has none."""
    if paths.main_checkout():
        return []
    try:
        prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=ROOT, capture_output=True, text=True, timeout=5).stdout.strip()
        out = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=ROOT, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode:
        return []
    found, here = [], os.path.realpath(ROOT)
    for block in out.stdout.strip().split("\n\n"):
        kv = dict((line.split(" ", 1) + [""])[:2] for line in block.splitlines() if line)
        if "worktree" not in kv or "bare" in kv:
            continue
        proj = os.path.realpath(os.path.join(kv["worktree"], prefix))
        if proj != here and os.path.isfile(os.path.join(proj, paths.MARKER)):
            found.append((proj, kv.get("branch", "").replace("refs/heads/", "") or "(detached)", os.path.basename(kv["worktree"].rstrip("/"))))
    return found


def workspace_films():
    """Remotion films that so far exist only in another worktree of this project: what is being made in a Conductor
    workspace before its branch is merged. Their renders came here (worktree_renders "main"), so they play here too."""
    here, out = set(slugs()), []
    for proj, branch, name in worktrees():
        fd = os.path.join(proj, os.path.relpath(FILMS_DIR, ROOT))
        for slug in sorted(os.listdir(fd)) if os.path.isdir(fd) else []:
            if slug in here or not os.path.isfile(os.path.join(fd, slug, "storyboard.json")):
                continue
            try:
                p = remotion_film(slug, fd)
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if p:
                here.add(slug)
                p["workspace"] = {"branch": branch, "path": proj, "name": name}
                out.append(p)
    return out


def summaries():
    out = []
    films = [production(s) for s in slugs()] + workspace_films()
    for p in films:
        if not p:
            continue
        r0 = p["renders"][0] if p["renders"] else None
        out.append({k: p[k] for k in ("slug", "engine", "title", "dir", "folder", "message", "format", "duration", "board", "profile")} | {
            "beats": [{"id": b["id"], "n": b["n"], "title": b["title"], "start": b["start"], "end": b["end"], "status": b["status"], "review": bool(b["review"]),
                       "ref": (b.get("refs") or [None])[0]} for b in p["beats"]],
            "renders": len(p["renders"]), "latest": r0 and {"name": r0["name"], "file": r0["file"], "mtime": r0["mtime"], "stale": r0["stale"], "code_newer": r0["code_newer"]},
            # the newest render of the whole film (not one beat), for the Build list's poster and hover preview
            "full": (lambda f: f and {"name": f["name"], "file": f["file"], "mtime": f["mtime"], "offset": f.get("offset", 0), "beats": f.get("beats")})(
                next((r for r in p["renders"] if not r.get("beat")), None)),
            "pins": len([x for x in p.get("pins", []) if x.get("status") != "done"]),
            "updated": max([r0["mtime"] if r0 else 0, os.path.getmtime(os.path.join(ROOT, p["storyboard"]))]),
            **({"workspace": p["workspace"]} if p.get("workspace") else {}),
        })
    return out


_LENGTHS = {}


def _render_length(path):
    """A render's length in seconds, asked of ffprobe once per file and change."""
    key = (path, os.path.getmtime(path))
    if key not in _LENGTHS:
        _LENGTHS[key] = probe_duration(path) or 0
    return _LENGTHS[key]


def own_films():
    """The project's own films as the Library shows them: every film with a render of the whole film, its beats as the
    scenes, each timed within that render (where the render says so, else from the plan), with what the plan says is on
    screen and in the copy, so they can be browsed and searched beside the references."""
    out = []
    films = [remotion_film(s) or hf_film(s) for s in slugs()] + workspace_films()
    for p in films:
        if not p:
            continue
        # the newest render that really holds the film: a short preview export (a few seconds of a 40 s film) is not one
        planned = max([b["end"] or 0 for b in p["beats"]] or [0])
        full = length = None
        for r in (x for x in p["renders"] if not x.get("beat")):
            try:
                real = paths.resolve(r["file"], main_ok=True)
            except ValueError:
                continue
            n = _render_length(real) if os.path.isfile(real) else 0
            if n and (not planned or n >= planned * 0.8 or r.get("beats")):
                full, length = r, n
                break
        if not full:
            continue
        off, timed = full.get("offset", 0) or 0, full.get("beats") or {}
        scenes = []
        for b in p["beats"]:
            w = timed.get(b["id"]) or ([b["start"] - off, b["end"] - off] if b["start"] is not None and b["end"] is not None else None)
            if not w or w[1] <= w[0] or w[0] >= length - 0.05:   # a beat the render doesn't reach has no picture to show
                continue
            w = [w[0], min(w[1], length)]
            scenes.append({"id": b["id"], "n": b["n"], "title": b["title"], "start": round(max(0, w[0]), 3), "end": round(w[1], 3),
                           "on_screen": b.get("on_screen", ""), "copy": b.get("copy", ""), "vo": b.get("vo", ""), "status": b.get("status", ""),
                           "refs": b.get("refs", [])})
        if not scenes:
            continue
        out.append({"slug": p["slug"], "title": p["title"], "engine": p["engine"], "file": full["file"], "render": full["name"], "mtime": full["mtime"],
                    "duration": round(max(x["end"] for x in scenes), 3), "fps": p.get("fps", 30), "format": p.get("format", ""), "message": p.get("message", ""),
                    "style": p.get("style", ""), "folder": p.get("folder", ""), "scenes": scenes,
                    **({"workspace": p["workspace"]["name"]} if p.get("workspace") else {})})
    out.sort(key=lambda f: -f["mtime"])
    return out


def _sb_path(slug):
    return os.path.join(FILMS_DIR, slug, "storyboard.json")


def update_beat(slug, beat_id, patch, done=None):
    """Set status / review (and the script's copy / vo) on a beat. With `done`, file the open review note in the beat's log first."""
    if "status" in patch and patch["status"] not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    p = production(slug)
    if not p:
        raise KeyError(f"no film called {slug}")
    if not any(b["id"] == beat_id for b in p["beats"]):
        raise KeyError(f"{slug} has no beat {beat_id}: {', '.join(b['id'] for b in p['beats'])}")
    latest = p["renders"][0]["name"] if p["renders"] else ""
    if p["engine"] == "remotion":
        path = _sb_path(slug)
        sb = load_json(path)
        b = next(x for x in sb["beats"] if x["id"] == beat_id)
    else:
        path = os.path.join(ROOT, p["review_file"])
        sb = load_json(path, {}) or {}
        b = sb.setdefault("beats", {}).setdefault(beat_id, {})
    if done is not None:
        b.setdefault("log", []).append({"at": today(), "render": latest, "note": b.get("review", ""), "done": done})
        b["review"] = ""
    for k in ("status", "review", "copy", "vo"):
        if k in patch:
            b[k] = patch[k]
    if p["engine"] != "remotion":
        for k in [k for k, v in b.items() if v in ("", [], None)]:
            del b[k]
    write_json(path, sb)
    return production(slug)


def new_from_board(slug, board_name, items=None, profile=None, folder=None, style=None):
    """Start a Remotion film from a board. Its folder: the one given, else the board's, else the one work here belongs in."""
    slug = slugify(slug, 48)
    if not slug:
        raise ValueError("give the film a slug, e.g. search-launch")
    if folder not in (None, "") and paths.clean_folder(folder) not in paths.FOLDER_NAMES:
        raise ValueError(f"no folder called {folder!r} ({', '.join(sorted(paths.FOLDER_NAMES)) or f'the project has none: {paths.CLI} folders add <folder>'})")
    d = os.path.join(FILMS_DIR, slug)
    if os.path.exists(os.path.join(d, "storyboard.json")):
        raise FileExistsError(f"{rel(d)}/storyboard.json already exists")
    bd = (load_json(paths.state_file(), {}) or {}).get("boards", {}).get(board_name)
    if items is None:
        if bd is None:
            raise KeyError(f"no board called {board_name!r} in library/state.json")
        items, profile = bd.get("items", []), profile or bd.get("profile")
    # the profile it is made in, fixed now: a later change of the project's default doesn't move a film already started
    style = style or (bd or {}).get("style") or profiles.default() or profiles.NONE
    if folder is None:
        folder = (bd or {}).get("folder") if (bd or {}).get("folder") in paths.FOLDER_NAMES else paths.here_folder()
    folder = paths.clean_folder(folder)
    lib = library()
    beats, seen, t, scenes = [], set(), 0.0, {}
    for i, it in enumerate(items):
        s = lib.get(it.get("id"))
        bid = slugify(it.get("beat") or "") or f"b{i + 1:02d}"
        while bid in seen:
            bid = f"{bid}-{i + 1}"
        seen.add(bid)
        length = round(max(1.0, (s["end"] - s["start"]) if s else 3.0), 1)
        scenes[bid] = [round(t, 3), round(t + length, 3)]
        t += length
        beats.append({"id": bid, "title": it.get("beat") or (s["title"] if s else bid), "refs": [it["id"]] if it.get("id") else [],
                      "on_screen": it.get("note", ""), "copy": "", "roles": [], "sound": "", "status": "todo", "review": "", "log": []})
    os.makedirs(d, exist_ok=True)
    sb = {
        "_note": "The plan, beat by beat: Spliced's Build view pairs it with every render (spliced open, Build). "
                 "Beat id = its key in cues.json scenes. Statuses: todo, wip, review, changes, approved. "
                 "`review` is the person's open note; resolve it with `spliced film mark <slug> <beat> review --done \"...\"`.",
        "title": board_name or slug, "board": board_name, "style": style, "profile": profile or paths.DEFAULT_PROFILE, "composition": "", "fps": 60,
        "format": "1920x1080", "message": "", "beats": beats, **({"folder": folder} if folder else {}),
    }
    write_json(os.path.join(d, "storyboard.json"), sb)
    cp = os.path.join(d, "cues.json")
    if not os.path.exists(cp):
        write_json(cp, {"_note": "Every time in the film, in film seconds. Seeded from the reference scenes' lengths: put the cuts on the beat grid. Beat ids in storyboard.json = keys in scenes.",
                        "duration": round(t, 3), "scenes": scenes})
    return production(slug)


def move_film(slug, folder):
    """Put a film in one of the project's folders ("" for none). A Remotion film's storyboard names it and its renders
    move to the folder's renders/; a HyperFrames film's whole folder moves (videos/<slug>/ <-> <folder>/<slug>/)."""
    folder = "" if folder in (None, "", "-") else paths.clean_folder(folder)
    if folder not in paths.FOLDER_NAMES and folder != "":
        raise ValueError(f"no folder called {folder!r} ({', '.join(sorted(paths.FOLDER_NAMES)) or f'the project has none: {paths.CLI} folders add <folder>'})")
    p = production(slug)
    if not p:
        raise KeyError(f"no film called {slug}")
    if p["engine"] == "remotion":
        path = _sb_path(slug)
        sb = load_json(path)
        was = film_folder(sb)
        sb.pop("folder", None)
        if folder:
            sb["folder"] = folder
        to = paths.renders_dir(folder)
        pat = _render_name(slug)
        for d in render_dirs(was) + [paths.renders_dir(f) for f in sorted(paths.FOLDER_NAMES)]:
            if os.path.realpath(d) == os.path.realpath(to) or not os.path.isdir(d):
                continue
            for f in sorted(os.listdir(d)):
                if not pat.match(f):
                    continue
                for src in (os.path.join(d, f), os.path.join(d, os.path.splitext(f)[0] + ".json")):
                    dst = os.path.join(to, os.path.basename(src))
                    if os.path.isfile(src) and not os.path.exists(dst):
                        os.makedirs(to, exist_ok=True)
                        os.replace(src, dst)
        write_json(path, sb)
    else:
        src = os.path.join(ROOT, p["dir"])
        dst = os.path.join(paths.folder_path(folder) if folder else VIDEOS_DIR, slug)
        if os.path.realpath(src) != os.path.realpath(dst):
            if os.path.exists(dst):
                raise FileExistsError(f"{rel(dst)} already exists")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.replace(src, dst)
    return production(slug)


# ---------- frames ----------
def frame_jpg(path, t, w=320):
    """A cached JPEG of one frame of a video (ffmpeg)."""
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1(f"{path}|{os.path.getmtime(path)}|{t:.3f}|{w}".encode()).hexdigest()[:20]
    out = os.path.join(CACHE, key + ".jpg")
    if not os.path.exists(out):
        tmp = out + ".tmp.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, t):.3f}", "-i", path, "-frames:v", "1",
                        "-vf", f"scale={w}:-2", "-q:v", "4", tmp], capture_output=True, timeout=30)
        if not os.path.exists(tmp):
            return None
        os.replace(tmp, out)
    return out


# ---------- CLI ----------
def fmt_t(t):
    return "  ?  " if t is None else f"{int(t // 60)}:{t % 60:05.2f}"


def ago(ts):
    s = dt.datetime.now().timestamp() - ts
    return f"{int(s // 60)}m ago" if s < 3600 else f"{int(s // 3600)}h ago" if s < 86400 else f"{int(s // 86400)}d ago"


def cmd_list(_):
    for s in summaries():
        st = {}
        for b in s["beats"]:
            st[b["status"]] = st.get(b["status"], 0) + 1
        lat = s["latest"]
        print(f"{s['slug']:<30} {s['engine']:<11} " + (f"{(s['folder'] or '-'):<20} " if paths.FOLDERS else "") + f"{len(s['beats']):>2} beats  " + " ".join(f"{k}:{v}" for k, v in st.items())
              + (f"   latest {lat['name']} ({ago(lat['mtime'])})" if lat else "   no render yet"))


def cmd_status(a):
    p = production(a.slug) or sys.exit(f"no film called {a.slug} ({paths.CLI} film list)")
    lib = library()
    print(f"# {p['title']}  ({p['engine']}, {p['dir']})")
    if p["message"]:
        print(f"News: {p['message']}")
    print(f"Plan: {p['storyboard']}   {fmt_t(p['duration'])}   made in {('the profile ' + p['style']) if p.get('style') and p['style'] != 'none' else 'no profile (as the reference)' if p.get('style') else 'the project default'}   motion {p['profile'] or '-'}   board {p['board'] or '-'}")
    if p.get("style") and p["style"] != "none":
        print(f"  Read the profile before building: {paths.CLI} profile show {p['style']}")
    for w in p["warnings"]:
        print(f"! {w}")
    print()
    for b in p["beats"]:
        print(f"{b['n']:>2}. [{b['status']:<8}] {b['id']:<22} {fmt_t(b['start'])}-{fmt_t(b['end'])}  {b['title']}")
        for r in b["refs"]:
            s = lib.get(r)
            print(f"       ref {r}: {s['title'] if s else 'NOT IN LIBRARY'}")
        if b["review"]:
            print(f"       NOTE: {b['review']}")
        if b["log"]:
            last = b["log"][-1]
            print(f"       last fix ({last.get('at')}, {last.get('render')}): {last.get('done')}")
    print()
    if p["renders"]:
        print("Renders (newest first):")
        for r in p["renders"][:6]:
            span = f" covers {fmt_t(r['span'][0])}-{fmt_t(r['span'][1])}" if r.get("span") and r.get("beat") else ""
            flags = (" [times changed since]" if r["stale"] else "") + (" [code changed since]" if r["code_newer"] else "")
            print(f"  {r['file']}  {ago(r['mtime'])}{span}{flags}{('  ' + r['note']) if r.get('note') else ''}")
    else:
        print("No render yet.")
    sn = [(k, v) for k, v in p.get("sound_notes", {}).items() if v.get("note")]
    if sn:
        print(f"\nOpen sound notes ({paths.CLI} sound show " + p["slug"] + " for the beat grid and every effect):")
        for k, v in sn:
            print(f"  [{k}] {v.get('kind', '')} {v.get('label', '')} ({fmt_t(v.get('start'))}-{fmt_t(v.get('end'))}): {v['note']}")
    op = [x for x in p.get("pins", []) if x.get("status") != "done"]
    if p.get("notes_mode") == "manual":
        print(f"\nNotes: MANUAL. The person hands notes over in a prompt: work only on the notes a prompt names, and leave the other open notes alone.")
    else:
        print(f"\nNotes: AUTO. Open notes are yours to fix as they come in. When you're done with them, keep listening: "
              f"run `{paths.CLI} film watch {p['slug']}` in the background; it returns with the next notes.")
    if op:
        nb = {b["id"]: b for b in p["beats"]}
        print(f"\nOpen notes at a moment ({len(op)}; close each with `{paths.CLI} film note-done {p['slug']} <id> --done \"...\"`):")
        for x in op:
            b = nb.get(x.get("beat"))
            print(f"  [{x['id']}] {fmt_t(x['t'])} beat {b['n'] if b else '?'} {x.get('beat') or ''} (seen in {x.get('render') or '?'}, from {x.get('by', 'person')}): {x['note']}")
    todo = [b for b in p["beats"] if b["status"] in ("changes",)] or [b for b in p["beats"] if b["status"] in ("todo", "wip")]
    if todo:
        print(f"\nNext: beat {todo[0]['n']} `{todo[0]['id']}` ({todo[0]['status']})")


# ---------- context: a new session's brief of a film, so an agent starts from it instead of reading the code ----------
CONTEXT_LIMIT = 12000          # characters (about 3k tokens); past it the brief is cut, with a pointer to the rest
_KNOWN = {"storyboard.json": "the plan beat by beat (this brief reads it)", "cues.json": "every time in the film (the beats' cues below)",
          "assets.json": "what made each still and clip (prompt, model, source)", "sound.json": "the mix: music, voice and effect tracks",
          "takes.json": "alternatives for each sound track, the chosen one marked", "review.json": "the person's review notes"}
_EXPORT = re.compile(r"^export\s+(?:default\s+)?(?:async\s+)?(?:const|let|var|function\*?|class|type|interface|enum)\s+([A-Za-z_$][\w$]*)", re.M)
_EXPORT_LIST = re.compile(r"^export\s*(?:type\s*)?\{([^}]*)\}", re.M)
_DEFINES = re.compile(r"^(?:const|function)\s+([A-Z][\w$]*)", re.M)


def _clip(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 3].rstrip() + "..."


def _header(name, text):
    """The first line of a file's header comment (or a Markdown file's first heading, a Python file's docstring)."""
    lines = [x.strip() for x in text.splitlines()[:40]]
    for x in lines:
        if not x or x.startswith(("#!", "# ///", "# requires", "# dependencies", "import ", "'use ", '"use ')):
            continue
        if name.endswith(".md"):
            return x.lstrip("#").strip()
        for mark in ("//", "/**", "/*", "*", "#", '"""', "'''"):
            if x.startswith(mark):
                return x[len(mark):].strip(" */\"'") or None
        return None
    return None


CONTEXT_READ = 256 * 1024   # a film's code file is far smaller: anything bigger is named with its size, not read


def _plain_file(path):
    try:
        return stat.S_ISREG(os.lstat(path).st_mode)   # lstat: a link is not followed, so it is not a plain file
    except OSError:
        return False


def _file_line(path, name):
    try:
        if os.path.getsize(path) > CONTEXT_READ:
            raise ValueError("too big to read for a brief")
        with open(path, encoding="utf-8") as f:
            text = f.read(CONTEXT_READ)
    except (OSError, UnicodeDecodeError, ValueError):
        return f"{name}  {os.path.getsize(path) // 1024} KB"
    out = f"{name}  {text.count(chr(10)) + (0 if text.endswith(chr(10)) or not text else 1)} lines"
    what = _KNOWN.get(name) or _header(name, text)
    if what:
        out += f"  {_clip(what, 110)}"
    if name.endswith((".tsx", ".ts", ".jsx", ".js")):
        ex = list(dict.fromkeys(_EXPORT.findall(text) + [w.split(" as ")[-1].strip() for g in _EXPORT_LIST.findall(text) for w in g.split(",") if w.strip()]))
        defs = [d for d in dict.fromkeys(_DEFINES.findall(text)) if d not in ex]
        if ex:
            out += f"\n      exports: {', '.join(ex[:12])}" + (f" +{len(ex) - 12} more" if len(ex) > 12 else "")
        if defs:
            out += f"\n      also defines: {', '.join(defs[:12])}" + (f" +{len(defs) - 12} more" if len(defs) > 12 else "")
    return out


def _flat_cues(v, pre=""):
    """A cue's inner timings, flattened: {"logo": 0.25, "card": {"in": 1}} -> ["logo .25", "card.in 1"]."""
    out = []
    for k, x in (v.items() if isinstance(v, dict) else []):
        if k.startswith("_"):
            continue
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            out.append(f"{pre}{k} {round(x, 3):g}")
        elif isinstance(x, list) and len(x) == 2 and all(isinstance(y, (int, float)) for y in x):
            out.append(f"{pre}{k} {round(x[0], 3):g}-{round(x[1], 3):g}")
        elif isinstance(x, dict):
            out += _flat_cues(x, f"{pre}{k}.")
    return out


def _beat_cues(cues, b):
    """One line per place cues.json times a beat: its scene windows when it has several, the scene's own inner times,
    and any other top-level table keyed by the beat's cue (e.g. cues.beat.<id>)."""
    keys = b["cue"] if isinstance(b["cue"], list) else [b["cue"]]
    out = []
    for k in keys:
        sc = (cues.get("scenes") or {}).get(k)
        if len(keys) > 1 and sc is not None:
            w = [sc["start"], sc["end"]] if isinstance(sc, dict) and "start" in sc else sc if isinstance(sc, list) else None
            if w:
                out.append(f"scenes.{k} {fmt_t(w[0])}-{fmt_t(w[1])}")
        inner = _flat_cues({x: y for x, y in sc.items() if x not in ("start", "end")}) if isinstance(sc, dict) else []
        if inner:
            out.append(f"scenes.{k}: " + ", ".join(inner))
        for top, tab in cues.items():
            if top in ("scenes", "fps", "duration", "board") or top.startswith("_") or not isinstance(tab, dict) or not isinstance(tab.get(k), dict):
                continue
            inner = _flat_cues(tab[k])
            if inner:
                out.append(f"{top}.{k}: " + ", ".join(inner))
    return [_clip(x, 220) for x in out]


def _sound_line(p):
    d = os.path.join(ROOT, p["dir"])
    sj = load_json(os.path.join(d, "sound.json"), {}) or {}
    tracks = sj.get("tracks") or []
    if not tracks:
        return f"none in sound.json yet ({paths.CLI} sound show {p['slug']} takes a finished mix apart)"
    try:
        tk = takes(p["slug"], p)["tracks"]
    except (KeyError, OSError):
        tk = {}
    lanes = {}
    for t in tracks:
        lanes.setdefault(t.get("lane") or "music", []).append(t)
    parts = []
    for t in lanes.get("music", []):
        ch = (tk.get(t.get("id")) or {}).get("chosen")
        parts.append(f"music {os.path.basename(t.get('file', '')) or t.get('id')}" + (f" (take {ch})" if ch else ""))
    for lane, word in (("voice", "voice line"), ("sfx", "effect")):
        n = len(lanes.get(lane, []))
        if n:
            parts.append(f"{n} {word}{'s' if n > 1 else ''}")
    parts += [f"{len(v)} {k}" for k, v in lanes.items() if k not in ("music", "voice", "sfx")]
    return ", ".join(parts) + f"  ({paths.CLI} sound show {p['slug']} for the beat grid)"


def _assets_lines(slug):
    try:
        r = assets(slug)
    except (KeyError, OSError):
        return []
    items = r.get("assets") or []
    if not items:
        return [f"Assets: none in {r.get('dir') or 'the film’s public folder'}"]
    stacks, seen, units = {s["id"]: s for s in r.get("stacks", [])}, set(), []
    for x in items:   # a stack (a render's frames) counts as one
        sid = x.get("stack")
        if sid in stacks:
            if sid in seen:
                continue
            seen.add(sid)
            frames = [y for y in items if y.get("stack") == sid]
            units.append({**x, "name": os.path.basename(stacks[sid]["pattern"]), "uses": [u for y in frames for u in y["uses"]], "frames": len(frames)})
        else:
            units.append(x)
    by = {}
    for x in units:
        by[f"{x['kind']} {x['type']}"] = by.get(f"{x['kind']} {x['type']}", 0) + 1
    unused = [os.path.join(x["dir"], x["name"]) if x["dir"] != "." else x["name"] for x in units if not x["uses"]]
    out = [f"Assets in {r['dir']}: {len(units)}" + (" (a stack of frames counts once)" if seen else "") + ", "
           + ", ".join(f"{n} {k}{'s' if n > 1 else ''}" for k, n in sorted(by.items(), key=lambda kv: -kv[1]))]
    if unused:
        out.append(f"  unused ({len(unused)}): " + ", ".join(unused[:8]) + (f" +{len(unused) - 8} more" if len(unused) > 8 else ""))
    out.append(f"  where each is used and what made it: {paths.CLI} film assets {slug}")
    return out


def context(slug, limit=CONTEXT_LIMIT):
    """Everything a new session needs to pick a film up, as plain text of about 3k tokens: the plan, open notes by beat,
    the cues, a map of the film's files, its assets and sound, and the next commands. Built from what `film status`
    reads (production), so the two never disagree."""
    p = production(slug)
    if not p:
        raise KeyError(f"no film called {slug} ({paths.CLI} film list)")
    cli, L = paths.CLI, []
    L.append(f"# {p['title']} ({slug}): brief for a new session")
    L.append(f"Start from this, not from the film's code; open only the files a note touches. Everything: {cli} film status {slug}")
    L.append("")
    if p.get("message"):
        L.append(f"Message: {_clip(p['message'], 300)}")
    L.append(f"Format: {p.get('format') or '?'}, {p.get('fps') or '?'} fps, {fmt_t(p['duration']).strip()}, {len(p['beats'])} beats ({p['engine']}, {p['dir']})")
    style = p.get("style")
    if style and style != "none":
        L.append(f"Profile: {style}  (read it before changing the look: {cli} profile show {style})")
    else:
        L.append("Profile: " + ("none, the references recreated as they are" if style == "none" else "the project default"))
    if p["engine"] == "remotion":
        L.append(f"Motion profile: {p.get('profile') or '-'}  (moves come from motion('{p.get('profile')}'); {cli} motion checks it)")
    rs = p.get("renders") or []
    if rs:
        r = rs[0]
        flags = ["code changed since" if r.get("code_newer") else "code unchanged since"] + (["times changed since"] if r.get("stale") else [])
        L.append(f"Latest render: {r['file']} ({ago(r['mtime'])}, {'beat ' + r['beat'] if r.get('beat') else 'whole film'}; {', '.join(flags)})")
        whole = next((x for x in rs if not x.get("beat")), None)
        if whole and whole is not r:
            L.append(f"  last whole render: {whole['file']} ({ago(whole['mtime'])}" + ("; code changed since" if whole.get("code_newer") else "") + ")")
    else:
        L.append("Latest render: none yet")
    for w in p.get("warnings", [])[:3]:
        L.append(f"! {w}")
    L.append("Notes: " + ("MANUAL, work only on the notes a prompt names" if p.get("notes_mode") == "manual" else "AUTO, open notes are yours to fix"))
    # open notes, each under its beat
    nb, pin_beat = {b["id"]: b for b in p["beats"]}, {x["id"]: x for x in p.get("pins", [])}
    under, other = {}, []
    for kind, nid, t, note in open_notes(p):
        if kind == "beat":
            bid = nid
        elif kind == "note":
            bid = (pin_beat.get(nid) or {}).get("beat")
        else:
            bid = next((b["id"] for b in reversed(p["beats"]) if b["start"] is not None and t is not None and t >= b["start"] - 0.001), None)
        pin = pin_beat.get(nid) if kind == "note" else None
        reply = (pin or {}).get("replies", [])[-1:] if pin else []
        line = (f"[{nid}] {fmt_t(t).strip()} " if kind == "note" else f"[{nid}] beat note: " if kind == "beat" else f"[{nid}] sound {fmt_t(t).strip()}: ")
        line += _clip(note, 260) + (f"  (in {pin['render']})" if pin and pin.get("render") else "") + (f"  reply: {_clip(reply[0].get('text'), 100)}" if reply else "")
        (under.setdefault(bid, []) if bid in nb else other).append(line)
    n_open = sum(map(len, under.values())) + len(other)
    cues = load_json(os.path.join(ROOT, p["cues"]), {}) or {} if p.get("cues") else {}
    L += ["", f"Beats ({n_open} open note{'s' if n_open != 1 else ''}; ids in [brackets]):"]
    shown = 0
    for b in p["beats"]:
        words = b.get("copy") or b.get("on_screen") or ""
        L.append(f"{b['n']:>2}. {b['id']}  {fmt_t(b['start']).strip()}-{fmt_t(b['end']).strip()}  [{b['status']}]" + (f"  \"{_clip(words, 140)}\"" if words else ""))
        if b.get("vo"):
            L.append(f"      vo: \"{_clip(b['vo'], 120)}\"")
        for c in _beat_cues(cues, b) if cues else []:
            L.append(f"      cues {c}")
        for x in under.get(b["id"], []):
            shown += 1
            if shown <= 25:
                L.append(f"      NOTE {x}")
    for x in other:
        shown += 1
        if shown <= 25:
            L.append(f"   NOTE (film-wide) {x}")
    if shown > 25:
        L.append(f"   ... {shown - 25} more open notes: {cli} film notes {slug}")
    L += ["", f"Sound: {_sound_line(p)}" if p["engine"] == "remotion" else f"Sound: {cli} sound show {slug}"]
    # the film's folder, file by file
    d = os.path.join(ROOT, p["dir"])
    files = []
    for dp, dn, fn in os.walk(d):
        dn[:] = sorted(x for x in dn if not x.startswith(".") and x not in ("node_modules", "__pycache__", "renders", "out", "snapshots", "exports"))
        # the film's own files only: a link could lead anywhere (a .env), and a pipe or device would never finish reading
        files += [os.path.join(dp, f) for f in sorted(fn) if not f.startswith(".") and not f.endswith((".pyc",) + VIDEO_EXT + IMG_EXT + AUDIO_EXT)
                  and _plain_file(os.path.join(dp, f))]
    L += ["", f"Files ({p['dir']}/):"]
    for f in files[:25]:
        L.append("  " + _file_line(f, os.path.relpath(f, d)))
    if len(files) > 25:
        L.append(f"  ... {len(files) - 25} more files")
    if p["engine"] == "remotion":
        L += [""] + _assets_lines(slug)
    first = next((b for b in p["beats"] if under.get(b["id"])), None) or next((b for b in p["beats"] if b["status"] in ("changes", "todo", "wip")), None)
    bid = first["id"] if first else "<beat>"
    L += ["", "Next:",
          f"  render one beat:     {cli} film render {slug} --beat {bid} --fixes <note ids> --note \"what changed\" --background",
          f"  then:                {cli} film render-status {slug}, and look: {cli} film sheet {slug} --beat {bid}",
          f"  file the person's feedback: {cli} film note {slug} <0:12.50 | beat> \"...\" --by chat",
          f"  close fixed notes:   {cli} film done {slug} <ids> --done \"what changed\"   (partly done: {cli} film note-reply {slug} <id> \"...\")",
          f"  set a beat's status: {cli} film mark {slug} <beat> wip|review"]
    text = "\n".join(L)
    if len(text) > limit:
        cut = text[:limit].rsplit("\n", 1)[0]
        text = cut + f"\n... cut at about {limit // 4} tokens. The rest: {cli} film status {slug}, {cli} film notes {slug}, {cli} film assets {slug}"
    return text


def cmd_context(a):
    print(context(a.slug))


def cmd_move(a):
    p = move_film(a.slug, a.folder)
    name = next((f["name"] for f in paths.FOLDERS if f["folder"] == p["folder"]), "")
    print(f"{a.slug}: " + (f"in {name} ({p['folder']}/)" if name else "in no folder") + f". Renders: {p['renders_dir']}/")


def cmd_new(a):
    p = new_from_board(a.slug, a.board, folder=a.folder)
    print(f"Started {p['dir']}: {len(p['beats'])} beats from the board {a.board!r}.")
    print(f"  {p['storyboard']}  (the plan: fill in on_screen, copy, roles; set composition once it's registered in Root.tsx)")
    print(f"  {p['dir']}/cues.json  (times seeded from the references' lengths: put them on the beat grid)")
    if p["folder"]:
        print(f"  in the folder {p['folder']}/: its renders go to {p['renders_dir']}/")
    print("Open it in Spliced: spliced open, then Build.")


def cmd_mark(a):
    p = update_beat(a.slug, a.beat, {"status": a.status}, done=a.done)
    b = next(x for x in p["beats"] if x["id"] == a.beat)
    print(f"{a.slug}/{a.beat}: {b['status']}" + (" (note filed in the log)" if a.done is not None else ""))


def git_rev():
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except Exception:
        return ""


# ---------- a render in the background: for an agent whose tool call can't wait the minutes a render takes ----------
RENDER_JOBS = os.path.join(paths.CACHE, "renders")
# Runs the render, its output into the log, and writes how it ended into the job file. argv: log, job file, the command.
_RENDER_WRAP = ("import json, subprocess, sys, datetime\n"
                "log, job, cmd = sys.argv[1], sys.argv[2], sys.argv[3:]\n"
                "with open(log, 'w') as f:\n    code = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT)\n"
                "j = json.load(open(job)); j.update(exit=code, ended=datetime.datetime.now().isoformat(timespec='seconds'))\n"
                "json.dump(j, open(job, 'w'), indent=1)\n")


def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def render_job(slug):
    """The film's last background render: {id, started, args, log, pid, exit?, ended?, state: running|done|failed|lost}, or None."""
    j = load_json(os.path.join(RENDER_JOBS, f"{slug}.json"))
    if not j:
        return None
    j["state"] = ("done" if j["exit"] == 0 else "failed") if "exit" in j else "running" if _pid_alive(j.get("pid")) else "lost"
    return j


def render_in_background(a):
    """Start `film render` as its own process and return at once. One at a time per film."""
    remotion_film(a.slug) or sys.exit(f"no Remotion film called {a.slug} (remotion/src/films/{a.slug}/storyboard.json)")
    j = render_job(a.slug)
    if j and j["state"] == "running":
        sys.exit(f"a render of {a.slug} is already running (started {j['started']}): {paths.CLI} film render-status {a.slug}")
    os.makedirs(RENDER_JOBS, exist_ok=True)
    args = [a.slug, "--scale", str(a.scale), "--pad", str(a.pad)]
    for flag, v in (("--beat", a.beat), ("--note", a.note), ("--fixes", a.fixes), ("--done", a.done)):
        if v:
            args += [flag, str(v)]
    jid = hashlib.sha1(f"{a.slug}{time.time()}".encode()).hexdigest()[:6]
    job, log = os.path.join(RENDER_JOBS, f"{a.slug}.json"), os.path.join(RENDER_JOBS, f"{a.slug}-{jid}.log")
    write_json(job, {"id": jid, "slug": a.slug, "started": dt.datetime.now().isoformat(timespec="seconds"), "args": args[1:], "log": rel(log), "pid": None})
    p = subprocess.Popen([sys.executable, "-c", _RENDER_WRAP, log, job, sys.executable, os.path.abspath(__file__), "render", *args],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, cwd=ROOT)
    j = load_json(job) or {}
    if "exit" not in j:  # (a render that failed at once has already written how it ended)
        j["pid"] = p.pid
        write_json(job, j)
    print(f"{a.slug}: rendering in the background ({jid}){', beat ' + a.beat if a.beat else ''}. It takes minutes.\n"
          f"See how it is going: {paths.CLI} film render-status {a.slug}")


def cmd_render_status(a):
    j = render_job(a.slug)
    if not j:
        print(f"{a.slug}: no background render has been started ({paths.CLI} film render {a.slug} --background)")
        return
    says = {"running": "still rendering", "done": "finished", "failed": f"failed (exit {j.get('exit')})", "lost": "stopped without finishing (its process is gone)"}[j["state"]]
    print(f"{a.slug}: render {j['id']} {says}. Started {j['started']}" + (f", ended {j['ended']}" if j.get("ended") else "") + (f"  ({' '.join(j['args'])})" if j.get("args") else ""))
    try:
        with open(os.path.join(ROOT, j["log"])) as f:
            tail = [l.rstrip() for l in f.read().replace("\r", "\n").splitlines() if l.strip()][-(40 if j["state"] != "running" else 6):]
    except OSError:
        tail = []
    if tail:
        print("\n" + "\n".join(tail))
    if j["state"] in ("failed", "lost"):
        sys.exit(1)


def cmd_render(a):
    if getattr(a, "background", False):
        return render_in_background(a)
    p = remotion_film(a.slug) or sys.exit(f"no Remotion film called {a.slug} (remotion/src/films/{a.slug}/storyboard.json)")
    comp = p["composition"] or sys.exit("set \"composition\" in storyboard.json to the composition id registered in remotion/src/Root.tsx")
    fps = p["fps"]
    span = [0.0, p["duration"]]
    label = a.beat
    if a.beat:
        # One beat (its id), or a run of beats as a growing timeline: "first..last" by id or beat number ("1..2").
        def find(k):
            return next((x for x in p["beats"] if x["id"] == k or str(x["n"]) == k), None) or sys.exit(f"no beat {k}")
        ends = [find(k) for k in a.beat.split("..")] if ".." in a.beat else [find(a.beat)]
        run = p["beats"][ends[0]["n"] - 1:ends[-1]["n"]]
        if not run or any(b["start"] is None for b in run):
            sys.exit(f"beats {a.beat}: missing or without a window in cues.json")
        span = [max(0.0, min(b["start"] for b in run) - a.pad), min(p["duration"], max(b["end"] for b in run) + a.pad)]
        label = run[0]["id"] if len(run) == 1 else f"{run[0]['n']}-{run[-1]['n']}"
    import kit   # without its packages npx would fetch whatever Remotion is newest and fail far from the cause: put them in first
    if kit.packages()["state"] != "ok" and not kit.install_packages():
        sys.exit(f"Remotion's packages aren't installed in {rel(paths.REMOTION)}/, so nothing was rendered ({paths.CLI} kit packages)")
    out_dir = paths.renders_dir(p["folder"])
    os.makedirs(out_dir, exist_ok=True)
    vs = [r["version"] for r in p["renders"] if r["version"]]
    v = max(vs, default=0) + 1
    name = f"{a.slug}-v{v}" + ((f"-beats-{label}" if "-" in label and label[0].isdigit() else f"-{label}") if a.beat else "")
    out = os.path.join(out_dir, name + ".mp4")
    cmd = ["npx", "remotion", "render", "src/index.ts", comp, os.path.relpath(out, paths.REMOTION), f"--scale={a.scale}"]
    if a.beat:
        cmd.append(f"--frames={round(span[0] * fps)}-{max(round(span[0] * fps), round(span[1] * fps) - 1)}")
    print("$ (remotion) " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=paths.REMOTION)
    if r.returncode or not os.path.exists(out):
        sys.exit("render failed")
    cues = load_json(os.path.join(ROOT, p["cues"]), {}) or {}
    write_json(os.path.join(out_dir, name + ".json"), {
        "slug": a.slug, "version": v, "file": rel(out), "created": dt.datetime.now().isoformat(timespec="seconds"),
        "scale": a.scale, "beat": label, "span": span, "fps": fps, "cues_hash": cues_hash(cues), "git": git_rev(),
        "note": a.note or "", "beats": {b["id"]: [b["start"], b["end"]] for b in p["beats"] if b["start"] is not None},
    })
    print(f"\n{rel(out)}  (v{v}{', beat ' + label if a.beat else ''})")
    if a.fixes:
        closed, missing = close_notes(a.slug, [x.strip() for x in a.fixes.split(",") if x.strip()], a.done or a.note or "fixed", name + ".mp4")
        if closed:
            print(f"Closed {len(closed)} note{'s' if len(closed) > 1 else ''} as done in {name}: {', '.join(closed)}")
        if missing:
            print(f"! no note called {', '.join(missing)} ({paths.CLI} film notes {a.slug})")
    left = open_notes(production(a.slug), span)
    if left:
        print(f"\nStill open in this render's span ({len(left)}). Close each one this render fixes, or reply with what's left:")
        for kind, i, t, txt in left:
            print(f"  [{i}] {fmt_t(t)} {kind}: {txt[:110]}")
        print(f"  {paths.CLI} film done {a.slug} <id> --done \"what you changed\"     (or next time: render --fixes <id>,<id>)")
        print(f"  {paths.CLI} film note-reply {a.slug} <id> \"done so far, what's left\"")
    main = paths.main_checkout()
    if main and paths.render_home() == main:
        print(f"This project is a git worktree: the render went to the main checkout ({main}), where Spliced lists it "
              f"with this worktree's films, and where it stays when the worktree is removed.")
    elif main:
        print(f"This project is a git worktree and keeps its renders here (spliced.json worktree_renders: worktree): "
              f"commit the render to share it; Spliced opened on {main} sees it once the branch is merged.")
    print(f"Pair it with the storyboard: {paths.CLI} film sheet {a.slug}" + (f" --beat {a.beat}" if a.beat and ".." not in a.beat else "") + "   or Spliced's Build view.")


def _fit(im, W, H):
    from PIL import Image
    im = im.convert("RGB")
    im.thumbnail((W, H))
    box = Image.new("RGB", (W, H), (8, 8, 8))
    box.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    return box


def _strip_frames(path, dur, k=3):
    """Frames from a library scene strip (scenes/sNN.jpg: n frames, 6px apart, n by the scene's length)."""
    from PIL import Image
    im = Image.open(path)
    n = 3 if dur <= 2.5 else 4 if dur <= 5 else 5
    fw = (im.width - 6 * (n - 1)) / n
    picks = [0, n // 2, n - 1] if k == 3 else list(range(n))
    return [im.crop((round(i * (fw + 6)), 0, round(i * (fw + 6) + fw), im.height)) for i in picks]


def _wrap(text, width):
    text = (text or "").replace("—", "-").replace("–", "-").replace("→", "->")
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + ([cur] if cur else [])


def cmd_sheet(a):
    from PIL import Image, ImageDraw, ImageFont
    p = production(a.slug) or sys.exit(f"no film called {a.slug}")
    rs = p["renders"]
    if a.render:
        rs = [r for r in rs if a.render in (r["file"], r["name"])] or sys.exit(f"no render {a.render}")
    beats = [b for b in p["beats"] if not a.beat or b["id"] == a.beat]
    if not beats:
        sys.exit(f"no beat {a.beat}")
    lib = library()
    FW, FH, LW, PAD = 256, 144, 330, 10
    with_refs = any(b["refs"] for b in beats)

    def font(size):
        for f in ("/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                pass
        return ImageFont.load_default(size=size)
    f_h, f_t, f_s = font(22), font(15), font(12)

    def covering(b):
        for r in rs:
            sp = r.get("span") or [0, 1e9]
            if b["start"] is not None and sp[0] - 0.01 <= b["start"] and b["end"] <= sp[1] + 0.01:
                return r
        return None

    rows = []
    for b in beats:
        r = covering(b)
        ren = []
        if r:
            bt = (r.get("beats") or {}).get(b["id"], [b["start"], b["end"]])
            path = paths.abspath(r["file"])
            for k in (0.12, 0.5, 0.88):
                t = bt[0] + (bt[1] - bt[0]) * k - r.get("offset", 0)
                j = frame_jpg(path, t, FW * 2)
                ren.append(Image.open(j) if j else None)
        refs = []
        s = lib.get(b["refs"][0]) if b["refs"] else None
        if s:
            sp = os.path.join(REFS_DIR, s["film"], "scenes", s["id"] + ".jpg")
            if os.path.exists(sp):
                refs = _strip_frames(sp, s["end"] - s["start"])
        rows.append((b, r, s, refs, ren))

    REFW = 3 * (FW + 4) + 24 if with_refs else 0
    W = PAD + LW + PAD + REFW + 3 * (FW + 4) + PAD
    H = 70 + len(rows) * (FH + 2 * PAD) + PAD
    img = Image.new("RGB", (W, H), (20, 19, 17))
    d = ImageDraw.Draw(img)
    rname = ", ".join(sorted({r["name"] for _, r, *_ in rows if r})) or "no render covers these beats"
    d.text((PAD, 12), f"{p['title']}  ·  {p['dir']}  ·  render: {rname}", fill=(236, 229, 217), font=f_h)
    x_ref, x_ren = PAD + LW + PAD, PAD + LW + PAD + REFW
    heads = [(PAD, "STORYBOARD"), (x_ren, "RENDER (12% · 50% · 88% of the beat)")] + ([(x_ref, "REFERENCE (library scene)")] if with_refs else [])
    for x, lab in heads:
        d.text((x, 46), lab, fill=(127, 120, 109), font=f_s)
    col = {"todo": (127, 120, 109), "wip": (255, 176, 0), "review": (127, 179, 201), "changes": (255, 77, 61), "approved": (143, 214, 148)}
    y = 70
    for b, r, s, refs, ren in rows:
        d.line((PAD, y - 1, W - PAD, y - 1), fill=(45, 43, 40))
        y0 = y + PAD
        d.text((PAD, y0), f"{b['n']}. {b['title']}"[:40], fill=(236, 229, 217), font=f_t)
        d.text((PAD, y0 + 20), f"{b['id']}  {fmt_t(b['start'])}-{fmt_t(b['end'])}  ", fill=(127, 120, 109), font=f_s)
        d.text((PAD + 230, y0 + 20), b["status"], fill=col.get(b["status"], (200, 200, 200)), font=f_s)
        ty = y0 + 40
        for line in _wrap(b["on_screen"] or b["copy"], 52)[:4]:
            d.text((PAD, ty), line, fill=(185, 177, 164), font=f_s)
            ty += 15
        if b["review"]:
            for line in _wrap("NOTE: " + b["review"], 52)[:2]:
                d.text((PAD, ty), line, fill=(255, 120, 100), font=f_s)
                ty += 15
        if not with_refs:
            pass
        elif refs:
            for i, im in enumerate(refs):
                img.paste(_fit(im, FW, FH), (x_ref + i * (FW + 4), y0))
            lab = f"{b['refs'][0]}  {s['title'][:40]}" + (f"  (+{len(b['refs']) - 1})" if len(b["refs"]) > 1 else "")
            d.rectangle((x_ref, y0 + FH - 20, x_ref + 3 * (FW + 4) - 4, y0 + FH), fill=(14, 13, 12))
            d.text((x_ref + 6, y0 + FH - 17), lab, fill=(255, 176, 0), font=f_s)
        else:
            d.text((x_ref, y0 + FH // 2 - 8), "no reference scene" if not b["refs"] else f"{b['refs'][0]}: not in library", fill=(90, 85, 78), font=f_t)
        if ren:
            for i, im in enumerate(ren):
                if im:
                    img.paste(_fit(im, FW, FH), (x_ren + i * (FW + 4), y0))
        else:
            d.text((x_ren, y0 + FH // 2 - 8), "not rendered yet", fill=(90, 85, 78), font=f_t)
        y += FH + 2 * PAD
    if a.out:
        out = a.out
    else:
        base = os.path.join(ROOT, p["dir"], "snapshots") if p["engine"] == "hyperframes" else OUT_DIR
        os.makedirs(base, exist_ok=True)
        tag = os.path.splitext(rs[0]["name"])[0] if rs else a.slug
        out = os.path.join(base, f"{tag}-pairs" + (f"-{a.beat}" if a.beat else "") + ".jpg")
    img.save(out, quality=88)
    print(rel(os.path.abspath(out)))


def cmd_takes(a):
    d = takes(a.slug)
    if not d["tracks"]:
        print(f"No takes yet ({d['file']}). Add one: {paths.CLI} film take {a.slug} <track> <file> --name \"...\"")
        return
    print(f"# Takes for {a.slug}  ({d['file']})")
    for tid, tr in d["tracks"].items():
        print(f"\n{tid}  {tr.get('label', '')}" + ("" if tr["in_mix"] else "  (not in sound.json)") + f"   plays: {tr['current'] or '-'}")
        for t in tr["takes"]:
            mark = "*" if t["id"] == tr.get("chosen") else " "
            print(f"  {mark} {t['id']:<28} {t.get('dur', 0):>6.1f}s  {t['name']}" + ("" if t["exists"] else "  MISSING") + (f"  ({t['note']})" if t.get("note") else ""))
    print(f"\n* = chosen. Use another: {paths.CLI} film take-use " + a.slug + " <track> <take id>")


def cmd_note(a):
    p = production(a.slug) or sys.exit(f"no film called {a.slug}")
    try:
        t, beat = parse_time(a.at), None
    except ValueError:
        b = next((x for x in p["beats"] if x["id"] == a.at or str(x["n"]) == a.at), None) or sys.exit(f"{a.at} is neither a time (0:18.66) nor a beat of {a.slug}")
        if b["start"] is None:
            sys.exit(f"beat {b['id']} has no window in cues.json")
        t, beat = b["start"], b["id"]
    x = add_pin(a.slug, t, a.note, by=a.by, render=a.render, beat=beat)
    print(f"{a.slug}: note {x['id']} at {fmt_t(x['t'])} on beat {x['beat']} (seen in {x['render'] or 'no render'})")


def cmd_notes(a):
    p = production(a.slug) or sys.exit(f"no film called {a.slug}")
    for x in p.get("pins", []):
        if x.get("status") == "done" and not a.all:
            continue
        done = f"  -> done in {x.get('done_in') or '?'}: {x.get('done')}" if x.get("status") == "done" else ""
        print(f"[{x['id']}] {fmt_t(x['t'])} {x.get('beat') or '?':<28} {x.get('render') or '':<22} {x.get('by', '')}: {x['note']}{done}")


def cmd_note_done(a):
    update_pin(a.slug, a.id, done=a.done, done_in=a.render)
    print(f"{a.slug}: note {a.id} done")


def cmd_mode(a):
    if a.mode:
        set_notes_mode(a.slug, a.mode)
    print(f"{a.slug}: notes are {notes_mode(a.slug)}")


def cmd_watch(a):
    """Wait for the person's next notes (auto mode), then print them and return. Notes typed in a burst come together:
    it waits until no new note has come for --quiet seconds. Run it in the background and act when it returns."""
    p = production(a.slug) or sys.exit(f"no film called {a.slug}")
    os.makedirs(WATCH_DIR, exist_ok=True)
    wf = _watch_file(a.slug)
    seen = set((load_json(wf, {}) or {}).get("seen", []))
    t0, last_new, pending = time.time(), None, {}
    while True:
        p = production(a.slug)
        if p["notes_mode"] == "auto":
            for key, kind, nid, t, text in _note_keys(p):
                if key not in seen and key not in pending:
                    pending[key] = (kind, nid, t, text); last_new = time.time()
        if pending and time.time() - last_new >= a.quiet:
            break
        write_json(wf, {"state": "waiting", "at": time.time(), "pid": os.getpid(), "seen": sorted(seen)})
        if a.timeout and time.time() - t0 > a.timeout:
            print(f"{a.slug}: no new notes in {a.timeout:.0f}s")
            return
        time.sleep(2)
    seen |= set(pending)
    write_json(wf, {"state": "working", "at": time.time(), "pid": os.getpid(), "seen": sorted(seen), "notes": [v[1] for v in pending.values()]})
    print(f"{len(pending)} new note{'s' if len(pending) > 1 else ''} on {a.slug} (auto mode):")
    for kind, nid, t, text in sorted(pending.values(), key=lambda v: v[2] or 0):
        print(f"  [{nid}] {kind} at {fmt_t(t)}: {text}")
    print(f"\nFix them the /make-film way (`{paths.CLI} film status {a.slug}` for the plan), close each in the render "
          f"that fixes it (--fixes) or with `{paths.CLI} film done`, then run `{paths.CLI} film watch {a.slug}` in the background again.")


def cmd_assets(a):
    """One line per asset. A stack (the frames of one render) is one line with its range; --frames lists every frame."""
    r = assets(a.slug)
    stacks, said = {s["id"]: s for s in r.get("stacks", [])}, set()
    use_line = lambda uses: "; ".join(dict.fromkeys(f"{u['file']}{(' ' + u['where']) if u['where'] else ''}{(' beat ' + ','.join(map(str, u['beats']))) if u['beats'] else ''}" for u in uses)) or "UNUSED"
    for x in r["assets"]:
        st = stacks.get(x.get("stack")) if not a.frames else None
        if st:
            if st["id"] in said:
                continue
            said.add(st["id"])
            frames = [y for y in r["assets"] if y.get("stack") == st["id"]]
            width = st["pattern"].count("#")
            path = os.path.relpath(os.path.join(ROOT, st["pattern"]), paths.PUBLIC).replace("#" * width, f"[{st['first']:0{width}d}..{st['last']:0{width}d}]")
            print(f"{x['kind']:<11} {path:<58} {st['count']} frames  {use_line([u for y in frames for u in y['uses']])}")
            continue
        print(f"{x['kind']:<11} {x['path']:<58} {use_line(x['uses'])}{('  prompt: ' + x['prompt'][:60]) if x.get('prompt') else ''}")
    if said:
        print(f"\n{len(said)} stack{'s' if len(said) > 1 else ''} shown as one line each ([first..last] is the frame number). Every frame: {paths.CLI} film assets {a.slug} --frames")


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    s = sub.add_parser("status"); s.add_argument("slug"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("context", help="a new session's brief of a film (about 3k tokens): plan, open notes by beat, cues, file map, assets, sound, next commands")
    s.add_argument("slug"); s.set_defaults(fn=cmd_context)
    s = sub.add_parser("new"); s.add_argument("slug"); s.add_argument("--board", required=True)
    s.add_argument("--folder", help="one of the project's folders (default: the board's, or the folder you are in)"); s.set_defaults(fn=cmd_new)
    s = sub.add_parser("move", help="put a film in one of the project's folders (- for none); its renders move with it")
    s.add_argument("slug"); s.add_argument("folder"); s.set_defaults(fn=cmd_move)
    s = sub.add_parser("mark"); s.add_argument("slug"); s.add_argument("beat"); s.add_argument("status", choices=STATUSES)
    s.add_argument("--done", help="what you changed: files the open note in the beat's log and clears it"); s.set_defaults(fn=cmd_mark)
    s = sub.add_parser("render"); s.add_argument("slug"); s.add_argument("--beat", help="a beat id, or a run of beats: first..last (ids or numbers, e.g. 1..2)"); s.add_argument("--scale", type=float, default=0.5)
    s.add_argument("--pad", type=float, default=0.5, help="seconds of context either side of a beat"); s.add_argument("--note")
    s.add_argument("--fixes", help="the notes this render fixes (note, beat or sound note ids, comma-separated): closed as done in it")
    s.add_argument("--done", help="what changed, filed with the notes in --fixes (default: --note)")
    s.add_argument("--background", action="store_true", help="start it and return at once (then: render-status)"); s.set_defaults(fn=cmd_render)
    s = sub.add_parser("render-status", help="how the film's background render is going: running, finished or failed, with the end of its log")
    s.add_argument("slug"); s.set_defaults(fn=cmd_render_status)
    s = sub.add_parser("mode", help="who picks up the person's notes: auto (chats fix them as they come) or manual (only notes handed over in a prompt)")
    s.add_argument("slug"); s.add_argument("mode", nargs="?", choices=NOTE_MODES); s.set_defaults(fn=cmd_mode)
    s = sub.add_parser("watch", help="auto mode: wait for the person's next notes, print them and return (run it in the background)")
    s.add_argument("slug"); s.add_argument("--quiet", type=float, default=8, help="seconds without a new note before returning (notes typed in a burst come together)")
    s.add_argument("--timeout", type=float, default=0, help="give up after this many seconds (0: wait as long as it takes)"); s.set_defaults(fn=cmd_watch)
    s = sub.add_parser("done", help="close the person's notes (pinned, beat or sound note ids) with what changed")
    s.add_argument("slug"); s.add_argument("ids", nargs="+"); s.add_argument("--done", required=True); s.add_argument("--render", help="the render with the fix (default: newest)")
    s.set_defaults(fn=lambda a: (lambda r: (print(f"{a.slug}: closed {', '.join(r[0]) or 'nothing'}"), r[1] and sys.exit(f"no note called {', '.join(r[1])}")))(close_notes(a.slug, a.ids, a.done, a.render)))
    s = sub.add_parser("note-reply", help="say what's done on a note that isn't finished yet; it stays open")
    s.add_argument("slug"); s.add_argument("id"); s.add_argument("text"); s.add_argument("--by", default="claude")
    s.set_defaults(fn=lambda a: (update_pin(a.slug, a.id, reply=a.text, by=a.by), print(f"{a.slug}: replied on {a.id}")))
    s = sub.add_parser("sound-done", help="file an open sound note with what you changed")
    s.add_argument("slug"); s.add_argument("note_id"); s.add_argument("--done", required=True)
    s.set_defaults(fn=lambda a: (update_sound_note(a.slug, a.note_id, {}, done=a.done), print(f"{a.slug} sound note {a.note_id}: filed")))
    s = sub.add_parser("takes", help="list each sound track's takes (alternatives), the chosen one marked"); s.add_argument("slug"); s.set_defaults(fn=cmd_takes)
    s = sub.add_parser("take", help="add a take (an alternative file) to a sound track")
    s.add_argument("slug"); s.add_argument("track", help="sound.json track id, e.g. music or voice"); s.add_argument("file"); s.add_argument("--name", default="")
    s.add_argument("--note", default=""); s.add_argument("--offset", type=float, default=0.0); s.add_argument("--label", default="", help="the track's label, e.g. Score")
    s.set_defaults(fn=lambda a: print(f"{a.slug} {a.track}: added take {add_take(a.slug, a.track, a.file, a.name, a.note, a.offset, a.label)['id']}"))
    s = sub.add_parser("take-use", help="make a take the one the film plays (writes sound.json)")
    s.add_argument("slug"); s.add_argument("track"); s.add_argument("take")
    s.set_defaults(fn=lambda a: print(f"{a.slug} {a.track}: now plays {a.take}" + ("" if use_take(a.slug, a.track, a.take)["applied"] else " (recorded; wire it into the mix by hand)")))
    s = sub.add_parser("note", help="pin a note to a moment of the film (the person's feedback, from the app or the chat)")
    s.add_argument("slug"); s.add_argument("at", help="film time (0:18.66 or 18.66), or a beat id / number (its start)"); s.add_argument("note")
    s.add_argument("--by", default="chat", choices=["person", "chat", "claude"]); s.add_argument("--render", help="the render it was seen in (default: the newest)")
    s.set_defaults(fn=cmd_note)
    s = sub.add_parser("notes", help="the notes pinned to moments (open ones; --all for done too)"); s.add_argument("slug"); s.add_argument("--all", action="store_true"); s.set_defaults(fn=cmd_notes)
    s = sub.add_parser("note-done", help="close a pinned note with what changed")
    s.add_argument("slug"); s.add_argument("id"); s.add_argument("--done", required=True); s.add_argument("--render", help="the render that has the fix (default: the newest)")
    s.set_defaults(fn=cmd_note_done)
    s = sub.add_parser("assets", help="every still and clip the film uses, where, and what made it"); s.add_argument("slug")
    s.add_argument("--frames", action="store_true", help="list every frame of a stack (a render's frames) instead of one line for the stack"); s.set_defaults(fn=cmd_assets)
    s = sub.add_parser("sheet"); s.add_argument("slug"); s.add_argument("--beat"); s.add_argument("--render"); s.add_argument("--out"); s.set_defaults(fn=cmd_sheet)
    a = ap.parse_args()
    try:
        a.fn(a)
    except (KeyError, ValueError, FileExistsError) as e:
        sys.exit(str(e).strip("'\""))


if __name__ == "__main__":
    main()
