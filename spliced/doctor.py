"""What this machine and this project can do with Spliced right now, and the one step that unlocks each next thing.

  spliced doctor            a readable list
  spliced doctor --json     the same, for the app's Setup view and for an agent

Nothing here is required to browse a library. Each level adds something:
  Browse       the app, on whatever is already in the project
  Collect      add films from a link or a file: download, cuts, tempo, palette, contact sheets
  Analyse      an AI agent of yours reads each film and writes its breakdown
  Make films   a render engine in the project, to build and render your own
  Generate     voice, footage and images, from services you connect

Standard library only: the server imports this to answer /api/doctor.
"""
import json, os, shutil, subprocess, sys, time

import connect, paths, runners, skillset, updates
import kit as film_kit

LEVELS = [("browse", "Browse", "Open the app on what is already in the project"),
          ("collect", "Collect", "Add films from a link or a file"),
          ("analyse", "Analyse", "Your AI reads each film and writes its breakdown"),
          ("make", "Make films", "Build and render your own films"),
          ("generate", "Generate", "Voice, footage and images from services you connect")]
BREW = sys.platform == "darwin" and bool(shutil.which("brew"))
AGENTS = (("claude", "Claude"), ("codex", "Codex"), ("gemini", "Gemini CLI"), ("cursor-agent", "Cursor"))   # the command, and what to call it


_SEEN = {}   # a program's answer, kept for a minute: the app asks often (the welcome, Setup), a version rarely changes


def _version(cmd):
    hit = _SEEN.get(tuple(cmd))
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    v = _ask(cmd)
    _SEEN[tuple(cmd)] = (time.time(), v)
    return v


def _ask(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return (out.stdout or out.stderr).strip().splitlines()[0][:60] if (out.stdout or out.stderr).strip() else ""
    except (OSError, subprocess.SubprocessError, IndexError):
        return ""


def _signed_in_to_github():
    """Whether the GitHub CLI holds a login (asked locally; the token itself is never read here)."""
    hit = _SEEN.get(("gh",))
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    try:
        ok = subprocess.run(["gh", "auth", "token"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8).returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    _SEEN[("gh",)] = (time.time(), ok)
    return ok


def _install(name, other=""):
    return (f"brew install {name}" if BREW else other or f"Install {name} and make sure it is on your PATH")


def _env_keys():
    """Names (never values) of the keys set in the environment or the project's .env."""
    names = {k for k in os.environ if k.endswith(("_API_KEY", "_ACCESS_KEY"))}
    try:
        with open(paths.ENV) as f:
            names |= {l.split("=", 1)[0].strip() for l in f if "=" in l and not l.lstrip().startswith("#") and l.split("=", 1)[1].strip()}
    except OSError:
        pass
    return names


def _mcp_registered():
    try:
        with open(os.path.join(paths.ROOT, ".mcp.json")) as f:
            return "spliced" in (json.load(f).get("mcpServers") or {})
    except (OSError, ValueError, AttributeError):
        return False


def check(fresh=False):
    """Every check, in the order a person would fix them. state: ok | missing | off (a choice, not a fault).
    fresh: ask every program again instead of trusting the last minute's answers ("Check again")."""
    if fresh:
        _SEEN.clear()
    items = []

    def add(key, level, label, state, detail, unlocks, fix="", optional=False):
        # optional: nice to have, the level works without it. Anything else has to be "ok" for its level to be ready.
        items.append({"id": key, "level": level, "label": label, "state": state, "detail": detail, "unlocks": unlocks, "fix": fix, "optional": optional})

    # ---- browse: the project itself
    films = [d for d in sorted(os.listdir(paths.REFS)) if os.path.exists(os.path.join(paths.REFS, d, "breakdown.json"))] if os.path.isdir(paths.REFS) else []
    add("project", "browse", "Project", "ok", f"{paths.NAME} at {paths.ROOT}" + (f", films for {paths.BRAND}" if paths.BRAND else ""), "Everything: this folder is what Spliced works on")
    u = updates.check(online=False)   # what the last check learned (the app and `spliced update` do the asking): doctor never goes online
    add("spliced", "browse", "Spliced itself", "off" if u["newer"] else "ok",
        f"Version {paths.VERSION}; {u['latest']} is out" if u["newer"] else f"Version {paths.VERSION}" + (", the newest" if u["latest"] else ""),
        "What's new in the app, and fixes", u["command"] or u["how"], optional=True)
    add("uv", "browse", "uv", "ok" if shutil.which("uv") else "missing", _version(["uv", "--version"]) or "Not found",
        "Runs Spliced's tools, each with the packages it needs", "https://docs.astral.sh/uv/getting-started/installation/")
    add("library", "browse", "Library", "ok" if films else "off", f"{len(films)} film{'' if len(films) == 1 else 's'} broken down" if films else "Empty so far",
        "Scenes to browse, review and put on boards", f"{paths.CLI} reference add <link>", optional=True)

    # ---- collect
    ff = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))   # ffprobe ships with ffmpeg: one thing to a person
    # with no Homebrew there is still a way that needs no password: a ready-built ffmpeg that uv installs (paths.py links it in)
    add("ffmpeg", "collect", "ffmpeg", "ok" if ff else "missing",
        (_version(["ffmpeg", "-version"]).replace(" Copyright", "").split(" the ")[0] if ff else "Not found" + ("" if BREW else ". A ready-built ffmpeg installs with uv, with no password asked")),
        "Frames, thumbnails and the machine pass (cuts, tempo, palette)", _install("ffmpeg", paths.STATIC_FFMPEG))
    add("yt-dlp", "collect", "yt-dlp", "ok" if shutil.which("yt-dlp") else "missing", _version(["yt-dlp", "--version"]) or "Not found",
        "Adding a film from a link (YouTube, Vimeo, X, LinkedIn)", _install("yt-dlp", "uv tool install yt-dlp"))

    # ---- analyse: an agent, and how it reaches Spliced
    # any of the agents `agents install` and `connect` set up: the command line ones by their command, the apps by being installed
    apps = [a for a in connect.status() if a["present"]]
    agents = [label for cmd, label in AGENTS if shutil.which(cmd)]
    agents += [a["name"] for a in apps if a["name"].split()[0] not in " ".join(agents)]
    add("agent", "analyse", "An AI agent", "ok" if agents else "missing", ", ".join(agents) + " on this machine" if agents else "None of Claude Code, Codex, Cursor or Gemini CLI found",
        "Breakdowns, boards built with you, films built from them", "Install Claude Code (https://claude.com/claude-code) or another coding agent, then open this folder in it")
    # current | edited (changed by hand: kept, and fine) | older, unknown, missing (a newer one of ours is out, or none is in)
    skills = skillset.status(paths.ROOT)
    stale = [n for n, st in skills.items() if st in ("older", "unknown", "missing")]
    edited = [n for n, st in skills.items() if st == "edited"]
    add("skills", "analyse", "Spliced's skills in this project", "ok" if skills and not stale else "missing",
        ("Installed" + (f"; your changes to {', '.join(edited)} are kept" if edited else "")) if skills and not stale
        else ", ".join(f"{n}: {'older' if skills[n] == 'unknown' else skills[n]}" for n in stale) or "None shipped",
        "Your agent knows how to add a reference and break it down the way the library expects", f"{paths.CLI} agents install")
    add("mcp", "analyse", "Spliced's tools offered to your agent (MCP)", "ok" if _mcp_registered() else "off",
        "Registered in .mcp.json" if _mcp_registered() else "Not registered. Your agent can still use the `spliced` command in a shell",
        "An agent that opens this folder can search the library, edit boards and read a film's notes without a shell", f"{paths.CLI} agents install", optional=True)
    linked = [a["name"] for a in apps if a["connected"]]
    add("apps", "analyse", "AI apps connected to this project", "ok" if linked else "off",
        ("Connected: " + ", ".join(linked)) if linked else ("Not yet: " + ", ".join(a["name"] for a in apps) + " on this machine") if apps else "None of the Claude desktop app, Cursor or Codex found",
        "Ask about your library, boards and films from a chat app, without opening the folder", f"{paths.CLI} connect", optional=True)
    if shutil.which("claude"):   # a suggestion, never a fault: what a Claude Code session here carries besides Spliced (sessions.py)
        import sessions
        lean, what = sessions.summary()
        add("lean", "analyse", "Lean Claude Code sessions for film work", "ok" if lean else "off", what,
            "Film sessions that cost less: fewer tools read on every call",
            f"{paths.CLI} agents context shows what a session here loads; {paths.CLI} agents install --lean trims it to Spliced's own tools (undo: --lean off)", optional=True)
    r = runners.name()
    add("runner", "analyse", "Who reads imported films", "ok" if r == "none" or runners.available() else "missing",
        "Your own agent, when you ask it (imports wait for it)" if r == "none" else f"A background {r} session per film" + (", unfenced (bypass)" if runners.bypass() else ", fenced in") + ("" if runners.available() else f": but {r} isn't installed"),
        "Whether a breakdown starts on its own after a download", 'spliced.json: "agent": {"runner": "claude", "permissions": "ask"} for background runs', optional=True)

    # ---- make films
    add("node", "make", "Node.js", "ok" if shutil.which("node") else "missing", _version(["node", "--version"]) or "Not found", "Remotion and HyperFrames both run on it", _install("node", "https://nodejs.org/en/download"))
    pk = film_kit.packages()
    n_films = len([d for d in os.listdir(paths.FILMS) if os.path.isfile(os.path.join(paths.FILMS, d, "storyboard.json"))]) if os.path.isdir(paths.FILMS) else 0
    where = paths.rel(paths.REMOTION)
    engine = {   # state, detail, fix
        "ok": ("ok", f"Remotion in {where}/, {n_films} film{'' if n_films == 1 else 's'}", ""),
        "installing": ("missing", f"Remotion in {where}/: its packages are being installed now (since {str(pk.get('started', ''))[11:16]}). Check again in a minute", ""),
        "failed": ("missing", f"Remotion in {where}/: installing its packages failed" + (f" ({pk['tail'][-1].strip()[:120]})" if pk.get("tail") else "") + f". The whole log: {pk.get('log')}", f"{paths.CLI} kit packages"),
        "missing": ("missing", f"{where}/ is there but its packages are not installed. Opening the project in Spliced installs them", f"{paths.CLI} kit packages"),
        "no-npm": ("missing", f"{where}/ is there but its packages are not installed, and npm comes with Node.js", f"Install Node.js, then {paths.CLI} kit packages"),
        "none": ("off", f"None yet. `kit install` brings Spliced's film kit and its packages; {film_kit.LICENCE}", f"{paths.CLI} kit install"),
    }[pk["state"]]
    add("engine", "make", "A render engine in the project", engine[0], engine[1], "The Build view: your film beside its references, rendered beat by beat", engine[2])
    ks = film_kit.status()
    add("kit", "make", "Spliced's film kit", "ok" if ks["installed"] and ks["current"] else "missing" if ks["installed"] else "off",
        (f"Version {ks['version']}, current" if ks["current"] else f"Version {ks['version']}: {len(ks['stale']) + len(ks['missing'])} file(s) older than this Spliced")
        + (f"; changed by hand: {', '.join(ks['edited'][:3])}" if ks["edited"] else "") if ks["installed"] else "Not installed",
        "Motion profiles, the moves in Systems, the craft and sound recipes, UI sounds, and example films to start from",
        f"{paths.CLI} kit update" if ks["installed"] else f"{paths.CLI} kit install", optional=True)

    # the product's real code: what a film's UI is rebuilt from
    remote = lambda c: bool(__import__("re").match(r"(https?://|git@|github\.com/)", c))
    gone = [c for c in paths.APP_CODE if not remote(c) and not os.path.isdir(os.path.expanduser(c if os.path.isabs(os.path.expanduser(c)) else os.path.join(paths.ROOT, c)))]
    gh = "The GitHub CLI is signed in here, so your AI can read your repositories" if _signed_in_to_github() else "Sign the GitHub CLI in (`gh auth login`) and your AI can read your repositories"
    here = [c for c in paths.APP_CODE if c not in gone]   # a list means any of them: a teammate without the folder still has the address
    gone = gone if not here else []
    away = [c for c in paths.APP_CODE if c not in here]
    add("app-code", "make", "Your app's real code", "missing" if gone else "ok" if paths.APP_CODE else "off",
        (f"{', '.join(gone)} isn't on this machine" if gone else ", ".join(here) + (f" ({', '.join(away)} isn't on this machine)" if away else "") if here else f"Not set. {gh}"),
        "The film's UI is rebuilt from the components, styles and copy that really ship, not from memory or a screenshot",
        ("Clone it, or correct \"app\": {\"code\"} in spliced.json" if gone else
         'spliced.json: "app": {"code": "~/code/your-app"} (a folder on this machine, or a GitHub address your AI can read)'), optional=not gone)

    # ---- generate: services, by the keys the project holds (names only) or the connectors the agent has
    keys = _env_keys()
    stock = [n for n, k in (("Pexels", "PEXELS_API_KEY"), ("Pixabay", "PIXABAY_API_KEY"), ("Unsplash", "UNSPLASH_ACCESS_KEY")) if k in keys]
    add("stock", "generate", "Free footage and photos", "ok", "NASA and Openverse need no key" + (f"; {', '.join(stock)} connected" if stock else ""),
        "Real footage for a film, with its author and licence recorded", "Settings, Service keys in the app: paste a free key for Pexels, Pixabay or Unsplash", optional=True)
    # A film needs no voice or music. When it has them: Spliced calls ElevenLabs with the project's key, or the person's AI
    # makes the audio with whatever voice or music service it is connected to (`voice record --agent`, then `voice file`),
    # or the person brings a file. Spliced can't see a connector, so it says what there is to choose from.
    voice = paths.CONFIG.get("voice") if isinstance(paths.CONFIG.get("voice"), dict) else {}
    other = str(voice.get("provider") or "elevenlabs").strip().lower() != "elevenlabs"
    voice_set = bool(voice.get("voice_id") or (other and voice.get("provider")))
    key = "ELEVENLABS_API_KEY" in keys
    add("voice", "generate", "Voice-over", "ok" if key or (other and voice_set) else "off",
        (f"Read by {voice.get('provider')}, through your AI" if other and voice_set else
         "ElevenLabs key set" + ("" if voice_set else ', but no "voice" in spliced.json yet') if key else
         "Not set up, and not needed: a film can carry its words on screen. Your AI can read the lines with a voice service it is connected to, or you can record them"),
        "`spliced voice` records a film's lines take by take, or files reads made elsewhere",
        f"Any one of: an ElevenLabs key (Settings, Service keys, or {paths.CLI} keys set elevenlabs); a voice service connected in your AI app, then {paths.CLI} voice record <film> --agent; "
        f"or your own recording, {paths.CLI} voice file <film> <line> <audio> --plain --source recording"
        + ("" if voice_set else '. Name the voice in spliced.json "voice"'), optional=True)
    items[-1]["key"] = "elevenlabs"   # Setup offers to add it in place
    add("music", "generate", "Music", "ok", "The UI sound kit ships with Spliced. A music bed is a file from anywhere: a generator in your AI, a track you have the rights to, or none",
        "`spliced soundkit` measures any take, splits it into stems and arranges it to the film's cuts", "remotion/docs/SOUND.md, section 2, says how each kind of take is filed", optional=True)
    add("connectors", "generate", "Generators in your AI (music, voice, images, clips)", "off",
        "Spliced can't see what your agent is connected to: ask it. Nothing here is needed to make a film",
        "Generated clips, stills, voices and music, made by your agent and recorded in a film's assets", "Connect them in your AI app's connector or MCP settings", optional=True)

    # each level stands on its own: making films doesn't wait for an agent, an agent doesn't wait for a render engine
    levels = [{"id": k, "label": l, "what": w, "ready": all(i["state"] == "ok" for i in items if i["level"] == k and not i["optional"])} for k, l, w in LEVELS]
    need = [i for i in items if not i["optional"] and i["state"] != "ok"]
    nxt = next((i for i in need if i["state"] == "missing"), None) or next(iter(need), None)   # something broken before something not chosen yet
    return {"project": paths.NAME, "root": paths.ROOT, "cli": paths.CLI, "levels": levels, "next": nxt and nxt["id"], "items": items}


MARK = {"ok": "✓", "missing": "✗", "off": "·"}


def report(d):
    out = [f"Spliced {paths.VERSION}{' (build ' + paths.BUILD + ')' if paths.BUILD else ''} on this machine, for {d['project']} ({d['root']})", ""]
    for lv in d["levels"]:
        out.append(f"{lv['label']}: {lv['what']}" + ("" if lv["ready"] else "   (not set up yet)"))
        for i in [x for x in d["items"] if x["level"] == lv["id"]]:
            out.append(f"  {MARK[i['state']]} {i['label']}: {i['detail']}")
            if i["state"] != "ok" and i["fix"]:
                out.append(f"      {'to add it' if i['state'] == 'off' else 'fix'}: {i['fix']}")
        out.append("")
    nxt = next((i for i in d["items"] if i["id"] == d["next"]), None)
    out.append(f"Next: {nxt['label']}. {nxt['unlocks']}.\n      {nxt['fix']}" if nxt else "Everything is set up. The lines marked · are extras you can add.")
    return "\n".join(out)


def main():
    d = check()
    print(json.dumps(d, indent=1, ensure_ascii=False) if "--json" in sys.argv[1:] else report(d))


if __name__ == "__main__":
    main()
