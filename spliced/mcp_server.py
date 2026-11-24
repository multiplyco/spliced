"""Spliced's tools for an AI agent, over the Model Context Protocol (stdio).

  spliced mcp            started by the agent, not by you: `spliced agents install` registers it in the project

An agent with a shell can already do everything with the `spliced` command. This is for agents without one (a
desktop chat app), and for the common moves to be one typed call instead of a command line to get right:
searching the library, reading and editing boards, a film's plan and notes, the import queue.

Every tool is the command it names, run as its own process on this project, so a tool can never do more or
differently than the command line does, and whatever a command prints stays out of the protocol's channel.
Standard library only. Jobs that take minutes (a render, a download) are started and then asked about: they
outlive a tool call.
"""
import base64, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths  # noqa: E402
import toolbox_state  # noqa: E402  (for the board operations' own description)

VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
SLUG = r"[\w][\w.-]*"
SCENE = r"[a-z0-9][a-z0-9-]*/[\w-]+"
BY = paths.env("BY", "agent")
# The folder the agent was opened in, if it is one of the project's: films and boards it starts go there. (The
# commands run from the project's root, so they are told rather than left to find it from where they stand.)
HERE_FOLDER = paths.here_folder()
OPS = toolbox_state.__doc__[toolbox_state.__doc__.index("Operations ("):].strip()

INSTRUCTIONS = (
    f"Spliced, working on the project \"{paths.NAME}\"" + (f" (films for {paths.BRAND})" if paths.BRAND else "") + ". "
    "A library of reference films broken down scene by scene (scenes are `<film>/sNN`), boards that are scripts built from "
    "those scenes, and films in production with the person's notes. Start with project_info. Search before you assume a "
    "scene exists. Read a board back before discussing it: the person may have edited it in the app. "
    "When the person gives feedback on a render, file it with film_note; close every note you fix, in the same step.")


def run(*args, stdin=None, timeout=180):
    """One Spliced command on this project: (ok, what it printed)."""
    env = {**os.environ, "SPLICED_PROJECT": paths.ROOT, "SPLICED_BY": BY, **({"SPLICED_FOLDER": HERE_FOLDER} if HERE_FOLDER else {})}
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "cli.py"), *[str(a) for a in args]], input=stdin, capture_output=True, text=True, timeout=timeout, env=env, cwd=paths.ROOT)
    except subprocess.TimeoutExpired:
        return False, f"`spliced {' '.join(map(str, args[:2]))}` took longer than {timeout}s and was stopped"
    out = (r.stdout + ("\n" + r.stderr if r.stderr.strip() else "")).strip()
    return r.returncode == 0, out or ("done" if r.returncode == 0 else f"failed (exit {r.returncode})")


def text(ok, out):
    return {"content": [{"type": "text", "text": out}], "isError": not ok}


def image(path, limit=3_000_000):
    """A picture as MCP content, or None if it isn't there or is too big to send."""
    try:
        if os.path.getsize(path) > limit:
            return None
        with open(path, "rb") as f:
            return {"type": "image", "data": base64.b64encode(f.read()).decode(), "mimeType": "image/png" if path.lower().endswith(".png") else "image/jpeg"}
    except OSError:
        return None


class Bad(ValueError):
    """What the agent sent can't be a call to this tool: said back to it plainly."""


def need(a, key, pattern=None, what=None):
    v = a.get(key)
    if v in (None, ""):
        raise Bad(f"`{key}` is needed" + (f": {what}" if what else ""))
    if pattern and not re.fullmatch(pattern, str(v)):
        raise Bad(f"`{key}` should be {what or 'like ' + pattern}, got {v!r}")
    return str(v)


# ---------- the tools ----------
def project_info(a):
    parts = [run("doctor")[1], "Boards:\n" + run("board", "boards")[1], "Films in production:\n" + run("film", "list")[1]]
    ok, waiting = run("imports", "next")
    if "Nothing is waiting" not in waiting:
        parts.append("An import is waiting for you:\n" + waiting)
    return text(True, "\n\n".join(parts))


def library_search(a):
    args = ["board", "find", str(a.get("query") or "")]
    for field, tag in (a.get("tags") or {}).items():
        args += ["--tag", f"{field}={tag}"]
    if a.get("min_steal"):
        args += ["--steal", int(a["min_steal"])]
    if a.get("film"):
        args += ["--film", str(a["film"])]
    return text(*run(*args, "--limit", int(a.get("limit") or 15)))


def library_scene(a):
    scene = need(a, "scene", SCENE, "a scene id like acme-launch/s05")
    ok, out = run("board", "scene", scene)
    content = [{"type": "text", "text": out}]
    film, sid = scene.split("/", 1)
    strip = image(os.path.join(paths.REFS, film, "scenes", f"{sid}.jpg")) if ok and film != "uploads" else None
    if strip:
        content.append(strip)  # the scene's frames, left to right
    return {"content": content, "isError": not ok}


def board_read(a):
    return text(*(run("board", "show", a["board"], "--md") if a.get("board") else run("board", "boards")))


def board_edit(a):
    ops = a.get("ops")
    if not isinstance(ops, list) or not ops:
        raise Bad("`ops` is a list of operations, each an object with an `op`")
    return text(*run("board", "apply", "-", stdin=json.dumps({"ops": ops})))


def show_in_app(a):
    args = ["board", "show-in-app", need(a, "target", what="a board's name or a scene id")]
    return text(*run(*args, *(["--note", str(a["note"])] if a.get("note") else [])))


def film_status(a):
    return text(*(run("film", "status", need(a, "film", SLUG)) if a.get("film") else run("film", "list")))


def film_notes(a):
    return text(*run("film", "notes", need(a, "film", SLUG), *(["--all"] if a.get("include_closed") else [])))


def film_note(a):
    film, action = need(a, "film", SLUG), a.get("action") or "add"
    if action == "add":
        return text(*run("film", "note", film, need(a, "at", what="a film time (0:18.66) or a beat id"), need(a, "text"), "--by", "chat"))
    if action == "reply":
        return text(*run("film", "note-reply", film, need(a, "id"), need(a, "text"), "--by", BY))
    if action == "done":
        ids = a.get("ids") or ([a["id"]] if a.get("id") else [])
        if not ids:
            raise Bad("`ids` is needed: the notes this closes")
        return text(*run("film", "done", film, *map(str, ids), "--done", need(a, "text", what="what you changed")))
    raise Bad("`action` is add, reply or done")


def film_mark(a):
    args = ["film", "mark", need(a, "film", SLUG), need(a, "beat"), need(a, "status", "todo|wip|review|changes|approved", "todo, wip, review, changes or approved")]
    return text(*run(*args, *(["--done", str(a["done"])] if a.get("done") else [])))


def film_new(a):
    return text(*run("film", "new", need(a, "film", r"[a-z0-9][a-z0-9-]*", "a short kebab-case name"), "--board", need(a, "board"),
                     *(["--folder", str(a["folder"])] if a.get("folder") else [])))


def profile_tool(a):
    action = a.get("action") or "list"
    if action == "list":
        return text(*run("profile"))
    prof = need(a, "profile", r"[a-z0-9][a-z0-9-]*", "a profile's name, as list shows it") if action != "new" else ""
    if action == "show":
        return text(*run("profile", "show", prof))
    if action == "learn":
        return text(*run("profile", "learn", prof, need(a, "text", what="the rule, in a sentence"), *(["--from", str(a["from"])] if a.get("from") else [])))
    if action in ("pin", "unpin"):
        return text(*run("profile", action, prof, need(a, "scene", what="a scene id (film/sNN)")))
    if action == "new":
        args = ["profile", "new", need(a, "name", what="the profile's name"), "--kind", a.get("kind") or "exploration"]
        for k in ("motion", "about"):
            if a.get(k):
                args += [f"--{k}", str(a[k])]
        if a.get("from_film"):
            args += ["--from-film", str(a["from_film"])]
        return text(*run(*args))
    raise Bad("`action` is list, show, learn, pin, unpin or new")


def folders_tool(a):
    action = a.get("action") or "list"
    if action == "list":
        return text(*run("folders"))
    if action == "add":
        return text(*run("folders", "add", need(a, "folder", r"[\w][\w./ -]*", "a folder inside the project, e.g. branding-videos"),
                         *(["--name", str(a["name"])] if a.get("name") else [])))
    if action == "move":
        return text(*run("film", "move", need(a, "film", SLUG), str(a.get("folder") or "-")))
    raise Bad("action is list, add or move")


def film_sheet(a):
    film = need(a, "film", SLUG)
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "sheet.jpg")
        ok, said = run("film", "sheet", film, *(["--beat", str(a["beat"])] if a.get("beat") else []), "--out", out, timeout=240)
        pic = image(out) if ok else None
        if ok and not pic:
            said += "\n(The sheet is too large to send here. Ask for one beat with `beat`.)"
        return {"content": [{"type": "text", "text": said}] + ([pic] if pic else []), "isError": not ok}


def film_render(a):
    film, action = need(a, "film", SLUG), a.get("action") or "start"
    if action == "status":
        return text(*run("film", "render-status", film))
    if action != "start":
        raise Bad("`action` is start or status")
    args = ["film", "render", film, "--background"]
    if a.get("beat"):
        args += ["--beat", str(a["beat"])]
    if a.get("scale"):
        args += ["--scale", float(a["scale"])]
    if a.get("note"):
        args += ["--note", str(a["note"])]
    if a.get("fixes"):
        args += ["--fixes", ",".join(map(str, a["fixes"]))]
    return text(*run(*args))


def reference_add(a):
    links = [str(x) for x in (a.get("links") or []) if str(x).strip()]
    if not links:
        raise Bad("`links` is needed: one or more links or file paths")
    args = ["imports", "add", *links]
    if a.get("name") and len(links) == 1:
        args += ["--slug", need(a, "name", r"[a-z0-9][a-z0-9-]*", "kebab-case, brand-what")]
    return text(*run(*args, *(["--no-breakdown"] if a.get("breakdown") is False else [])))


def film_kit(a):
    action = a.get("action") or "status"
    if action not in ("status", "install", "update", "starter"):
        raise Bad("action is status, install, update or starter")
    if action in ("install", "update"):   # npm can take minutes: the packages go in the background, `status` says when they're in
        ok, out = run("kit", action, "--no-npm")
        if ok:
            out += "\n" + run("kit", "packages", "--background")[1]
        return text(ok, out)
    args = ["kit", action] + ([str(a["film"])] if action == "starter" and a.get("film") else [])
    return text(*run(*args, timeout=600 if action == "starter" else 180))


def import_folder(a):
    folder = str(a.get("folder") or "").strip()
    if not folder:
        raise Bad("`folder` is needed: the path of a folder on this machine")
    args = ["import", folder]
    if a.get("clip_under") is not None:
        args += ["--clip-under", float(a["clip_under"])]
    if a.get("go"):
        args += ["--go"] + (["--no-reading"] if a.get("reading") is False else [])
    return text(*run(*args))


def imports(a):
    action = a.get("action") or "list"
    if action in ("list", "next"):
        return text(*run("imports", action))
    if action == "cancel":
        return text(*run("imports", "cancel", need(a, "id", r"\w+")))
    if action == "done":
        return text(*run("imports", "done", need(a, "id", r"\w+"), *(["--slug", need(a, "renamed_to", r"[a-z0-9][a-z0-9-]*")] if a.get("renamed_to") else [])))
    raise Bad("`action` is list, next, done or cancel")


def uploads(a):
    action = a.get("action") or "pending"
    if action in ("pending", "list"):
        return text(*run("uploads", action))
    if action == "set":
        analysis = a.get("analysis")
        if not isinstance(analysis, dict):
            raise Bad("`analysis` is an object: title, role, world, subject, camera, motion, type_treatment, pace, energy, production, on_screen, how_it_moves, recreate, steal")
        return text(*run("uploads", "set", need(a, "id", r"\w+"), json.dumps(analysis, ensure_ascii=False)))
    raise Bad("`action` is pending, list or set")


def library_build(a):
    return text(*run("library", *(["--check"] if a.get("check_only") else []), timeout=600))


def film_voice(a):
    film, action = need(a, "film", SLUG), a.get("action") or "status"
    if action == "status":
        return text(*run("voice", "status", film))
    if action == "lines":   # the hand-off: what your own voice connector reads, no key needed
        args = ["voice", "record", film, *map(str, a.get("lines") or []), "--agent", "--json"]
        if a.get("takes"):
            args += ["--takes", int(a["takes"])]
        if a.get("direction"):
            args += ["--direction", str(a["direction"])]
        return text(*run(*args))
    if action == "file":
        files = a.get("files") or []
        if not files:
            raise Bad("`files` is needed: the reads you downloaded, as absolute paths")
        args = ["voice", "file", film, need(a, "line"), *[os.path.expanduser(str(f)) for f in files]]
        if a.get("direction"):
            args += ["--direction", str(a["direction"])]
        if a.get("source"):
            args += ["--source", str(a["source"])]
        return text(*run(*args, *(["--plain"] if a.get("plain") else []), timeout=300))
    if action == "fit":
        return text(*run("voice", "fit", film, timeout=300))
    raise Bad("`action` is status, lines, file or fit")


def S(props=None, required=()):
    return {"type": "object", "properties": props or {}, "required": list(required), "additionalProperties": False}


STR, INT, BOOL = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}
FILM = {"type": "string", "description": "The film's slug, as film_status lists them"}
TOOLS = [
    ("project_info", project_info, "Start here. What this project is, what is set up on this machine, its boards, its films in production, and any import waiting for you.", S()),
    ("library_search", library_search, "Search the library's scenes by words and tags. Returns scene ids (`<film>/sNN`) with their title, world, motion and length; the best are marked ★★★.",
     S({"query": {"type": "string", "description": "Words to look for in titles, descriptions and tags. May be empty when filtering by tags."},
        "tags": {"type": "object", "description": "Field to tag, from the project's library/TAXONOMY.md, e.g. {\"motion\": \"slot-reel\", \"world\": \"white-stage\"}", "additionalProperties": STR},
        "min_steal": {"type": "integer", "minimum": 1, "maximum": 3, "description": "Only scenes rated at least this worth borrowing"},
        "film": {"type": "string", "description": "Only this film (its slug, or part of it)"}, "limit": {"type": "integer", "minimum": 1, "maximum": 60}})),
    ("library_scene", library_scene, "One scene's breakdown: what is on screen, how it moves (with numbers), how to recreate it, and its frames as a picture. Read it before writing a beat that borrows it.",
     S({"scene": {"type": "string", "description": "A scene id like acme-launch/s05, or uploads/<id>"}}, ["scene"])),
    ("board_read", board_read, "A board as a script: its brief, motion profile and beats with copy, voice-over, seconds and notes. With no board, the list of boards. Read a board back before discussing it.",
     S({"board": {"type": "string", "description": "The board's exact name"}})),
    ("board_edit", board_edit, "Change boards, reviews and saved moments with named operations, applied in order, all or nothing. With the app open the person sees each change at once.\n\n" + OPS,
     S({"ops": {"type": "array", "items": {"type": "object"}, "description": "e.g. [{\"op\": \"item.add\", \"board\": \"Launch\", \"id\": \"acme-launch/s05\", \"beat\": \"hook\", \"copy\": \"On-screen words\", \"seconds\": 3}]"}}, ["ops"])),
    ("show_in_app", show_in_app, "Point the person's open Spliced tab at a board or a scene (they see it change). Needs the app running.",
     S({"target": {"type": "string", "description": "A board's name, or a scene id"}, "note": {"type": "string", "description": "One line shown with it"}}, ["target"])),
    ("film_status", film_status, "A film in production, beat by beat: each beat's window, status, references and open notes, and its renders. With no film, the list of films.", S({"film": FILM})),
    ("film_notes", film_notes, "The notes the person pinned to moments of a film, open ones first.", S({"film": FILM, "include_closed": BOOL}, ["film"])),
    ("film_note", film_note, "File, answer or close a note on a film. add: the person's feedback from the chat, pinned to its frame. reply: say what is done on a note that stays open. done: close the notes you fixed, with what you changed. Close every note you fix in the same step.",
     S({"film": FILM, "action": {"type": "string", "enum": ["add", "reply", "done"]}, "at": {"type": "string", "description": "add: a film time like 0:18.66, or a beat id"},
        "id": {"type": "string", "description": "reply: the note's id"}, "ids": {"type": "array", "items": STR, "description": "done: the notes' ids"},
        "text": {"type": "string", "description": "The note, the reply, or what you changed"}}, ["film", "action", "text"])),
    ("film_mark", film_mark, "Set a beat's status as you work: todo, wip (being built), review (rendered, waiting for the person). The person sets changes and approved. `done` files their open note with what you changed.",
     S({"film": FILM, "beat": {"type": "string", "description": "The beat's id"}, "status": {"type": "string", "enum": ["todo", "wip", "review", "changes", "approved"]}, "done": STR}, ["film", "beat", "status"])),
    ("film_new", film_new, "Start a film from a board: writes its storyboard (one beat per board item) so the app can pair every render with it.",
     S({"film": {"type": "string", "description": "A new kebab-case slug"}, "board": {"type": "string", "description": "The board's exact name"},
        "folder": {"type": "string", "description": "One of the project's folders (folders lists them). Default: the board's folder"}}, ["film", "board"])),
    ("folders", folders_tool, "The project's folders: how its films, boards and assets are sorted (say one per kind of video, or per client). "
     "list: each folder with its films and boards. add: make one. move: put a film in a folder (no folder: out of its folder); its renders move with it. "
     "A board's folder is set with board_edit (board.create / board.set with folder). The library is shared by every folder.",
     S({"action": {"type": "string", "enum": ["list", "add", "move"]}, "folder": {"type": "string", "description": "The folder's path in the project, e.g. branding-videos"},
        "name": {"type": "string", "description": "add: the name the app shows (default: from the folder's name)"}, "film": FILM})),
    ("profile", profile_tool, "The project's profiles: the looks its films are made in (a house look, looks to explore), each with its motion profile, palette, type, "
     "its own text and the rules learned while making films. list: every profile, the default marked. show: everything to read before building in one (do this first when a "
     "prompt names a profile). learn: keep a lasting preference the person stated (\"never bounce the logo\") in the profile, with where it came from. pin / unpin: a scene "
     "that shows the look. new: a profile (from_film starts it from a reference film's look). A build in no profile recreates its references as they are.",
     S({"action": {"type": "string", "enum": ["list", "show", "learn", "pin", "unpin", "new"]}, "profile": {"type": "string", "description": "The profile's name, as list shows it"},
        "text": {"type": "string", "description": "learn: the rule, in a sentence"}, "from": {"type": "string", "description": "learn: where it came from, e.g. launch-film note 3"},
        "scene": {"type": "string", "description": "pin / unpin: a scene id like acme-launch/s05"}, "name": {"type": "string", "description": "new: its name"},
        "kind": {"type": "string", "enum": ["house", "exploration"]}, "motion": {"type": "string", "description": "new: its motion profile"},
        "about": {"type": "string", "description": "new: one line about it"}, "from_film": {"type": "string", "description": "new: a reference film's slug to start from"}})),
    ("film_sheet", film_sheet, "See a film's newest render against its plan: storyboard, reference frames and render frames, beat by beat, as one picture. Ask for one beat to see it larger.",
     S({"film": FILM, "beat": {"type": "string", "description": "One beat's id"}}, ["film"])),
    ("film_render", film_render, "Render a film, or one beat of it, in the background (a render takes minutes). start returns at once; ask again with action status until it has finished, then look at it with film_sheet. `fixes` closes the notes this render fixes.",
     S({"film": FILM, "action": {"type": "string", "enum": ["start", "status"]}, "beat": {"type": "string", "description": "One beat's id, or a run: first..last"},
        "scale": {"type": "number", "description": "0.5 (the default) for a draft, 1 for full size"}, "note": {"type": "string", "description": "What changed in this render"},
        "fixes": {"type": "array", "items": STR, "description": "Ids of the notes this render fixes"}}, ["film"])),
    ("film_voice", film_voice, "A film's voice-over, read with a voice service you are connected to (ElevenLabs or another; no key in the project needed). status: every line, script against what was recorded. "
     "lines: the changed lines (or the ones named) with the provider, the exact prompt and the voice to generate each with; read the prompt as written (for ElevenLabs it starts with the "
     "line before as a lead-in, and comes with voice_id and model_id). file: give it the reads you downloaded for one line, with the arguments the line's `then` names; each is levelled "
     "(the lead-in cut away when there is one) and becomes a take (the crisper plays). fit: once every line is in, time the film to the reads.",
     S({"film": FILM, "action": {"type": "string", "enum": ["status", "lines", "file", "fit"]},
        "lines": {"type": "array", "items": STR, "description": "lines: only these line ids (default: the ones whose script changed)"},
        "takes": {"type": "integer", "minimum": 1, "maximum": 4, "description": "lines: reads to make of each (default 2)"},
        "direction": {"type": "string", "description": "lines and file: a delivery direction, the same for both, e.g. \"crisp, clear\""},
        "line": {"type": "string", "description": "file: the line's id"},
        "files": {"type": "array", "items": STR, "description": "file: the downloaded reads, absolute paths"},
        "plain": {"type": "boolean", "description": "file: the reads are the line alone, with no lead-in to cut"},
        "source": {"type": "string", "description": "file: where the reads came from when it isn't the project's voice provider: a service's name, or \"recording\""}}, ["film"])),
    ("reference_add", reference_add, "Queue reference films to add to the library from links (YouTube, Vimeo, X, LinkedIn) or file paths. Spliced downloads and analyses them; follow with imports to see progress.",
     S({"links": {"type": "array", "items": STR}, "name": {"type": "string", "description": "For one link: its slug, kebab-case brand-what"},
        "breakdown": {"type": "boolean", "description": "false: download and analyse only"}}, ["links"])),
    ("film_kit", film_kit, "The film kit in the project's remotion/ folder (the motion library, specimens, craft and sound docs, UI sounds). status: installed and current? "
     "install / update: put this Spliced's kit in (files changed by hand are left alone and listed) and start installing its packages "
     "(Remotion, React) in the background; status says when they are in. starter: add the example films, to read, render and borrow from.",
     S({"action": {"type": "string", "enum": ["status", "install", "update", "starter"]}, "film": {"type": "string", "description": "starter: just this example film"}})),
    ("import_folder", import_folder, "Bring a folder of pictures, GIFs and videos the person already has into the library. Without `go` it only looks: how many of each, "
     "and what reading them will ask of you. Tell the person that count and bring it in (`go`: true) once they agree. Pictures and short videos become uploads to read "
     "(uploads pending), longer videos become films to break down (imports next). What is already in the library is skipped, so running it again takes only what is new.",
     S({"folder": {"type": "string", "description": "A folder on this machine: an absolute path, or one starting with ~"}, "go": {"type": "boolean", "description": "true: bring it in. Leave out to look first"},
        "clip_under": {"type": "number", "description": "Videos up to this many seconds are clips, longer ones films (default 15)"},
        "reading": {"type": "boolean", "description": "false: bring the files in but queue no reading"}}, ["folder"])),
    ("imports", imports, "The import queue. list: every job and its step. next: the job waiting for you to break down, with exactly what to do. done: you finished that reading, hand it back. cancel: stop one.",
     S({"action": {"type": "string", "enum": ["list", "next", "done", "cancel"]}, "id": STR, "renamed_to": {"type": "string", "description": "done: the film's new slug, if you renamed it"}}, ["action"])),
    ("uploads", uploads, "Uploaded images, GIFs and clips. pending: the ones not read yet, with the file to look at for each. set: store your reading of one (tags are checked against the taxonomy).",
     S({"action": {"type": "string", "enum": ["pending", "list", "set"]}, "id": STR, "analysis": {"type": "object"}}, ["action"])),
    ("library_build", library_build, "Rebuild the library after a breakdown changed (scene strips, pages, the app's index), or with check_only just validate: every tag in the taxonomy, no gaps between scenes, no broken references.",
     S({"check_only": BOOL})),
]
BY_NAME = {name: fn for name, fn, _, _ in TOOLS}


def handle(msg):
    """One JSON-RPC message in, its reply out (None for a notification)."""
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        asked = params.get("protocolVersion")
        result = {"protocolVersion": asked if asked in VERSIONS else VERSIONS[0], "capabilities": {"tools": {}},
                  "serverInfo": {"name": "spliced", "title": "Spliced", "version": "0.0.1"}, "instructions": INSTRUCTIONS}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{"name": n, "description": d, "inputSchema": s} for n, _, d, s in TOOLS]}
    elif method == "tools/call":
        fn = BY_NAME.get(params.get("name"))
        if not fn:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"no tool called {params.get('name')!r}"}}
        try:
            result = fn(params.get("arguments") or {})
        except Bad as e:
            result = text(False, str(e))
        except Exception as e:  # noqa: BLE001  (a tool that breaks tells the agent so; the server stays up)
            result = text(False, f"{type(e).__name__}: {e}")
    elif mid is None:
        return None  # a notification (initialized, cancelled): nothing to answer
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None if mid is None else {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    out = sys.stdout
    sys.stdout = sys.stderr  # nothing but protocol messages may reach the real stdout
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            reply = handle(json.loads(line))
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "that line is not JSON"}}
        if reply is not None:
            out.write(json.dumps(reply, ensure_ascii=False) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
