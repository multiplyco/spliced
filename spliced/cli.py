# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Spliced: one command for everything the tools do.

  spliced <command> [arguments]                 with no command: this list
  spliced --project <folder> <command> ...      work on another project than the one you are in
  spliced setup [<folder>]                      everything in one go: a project, your AI's skills, the film kit, a first film
  spliced init [<folder>]                       start a new project
  spliced --version                             which Spliced this is

A project is a folder with a spliced.json in it: your library of reference films, your boards, your films in
production. Run commands from inside it. Each command has its own help: spliced <command> --help

Not installed? From a checkout, `uv run spliced/cli.py <command>` is the same thing.
"""
import json, os, shlex, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import locate  # noqa: E402

# command -> (the tool's file, what it is for). The order is the order of the help.
COMMANDS = {
    "open": ("toolbox.py", "Start the app in the browser (the server stays up until Ctrl+C); --background to get the terminal back, --stop, --port, --no-open"),
    "doctor": ("doctor.py", "What this machine and project can do now, and the step that unlocks the next thing; --json"),
    "update": ("updates.py", "Is a newer Spliced out, and the command that gets it; --json"),
    "board": ("board.py", "Boards: find scenes, read and edit a board's script, point the open app at one"),
    "film": ("film.py", "Films in production: status, notes, render, the storyboard beside the render"),
    "folders": ("folders.py", "The project's folders (one per kind of video, or per client): list, add, remove"),
    "reference": ("add_reference.py", "Add a reference film from a link or a file, and run the machine pass"),
    "imports": ("importer.py", "The import queue: add, list, cancel; `next` and `done` for an agent picking a job up"),
    "import": ("folder.py", "Bring in a folder of pictures, clips and films you already have; --go to do it"),
    "library": ("build_library.py", "Rebuild the library from the breakdowns; --check, --links, --index-only, --moves"),
    "analyze": ("analyze_reference.py", "The machine pass on one film; `strip` for a dense look at a moment"),
    "uploads": ("uploads.py", "Uploaded images, GIFs and clips: list, add, edit, pending, set an analysis"),
    "keys": ("apikeys.py", "Service keys in .env (ElevenLabs, footage libraries): which are set; set one by pasting it"),
    "stock": ("stock.py", "Free footage and photos: search, and get one into a film with its licence"),
    "sound": ("sound.py", "A film's sound taken apart: music, voice and effects on the beat grid"),
    "soundkit": ("soundkit.py", "Make a film's sound: stems, score, UI sounds, loudness"),
    "voice": ("voice.py", "Voice-over line by line"),
    "kit": ("kit.py", "The film kit in remotion/: install, update, starter (example films to read, render and borrow from)"),
    "motion": ("check_motion.py", "Check that a film's motion comes from its profile"),
    "moves": ("build_system_moves.py", "Rebuild the library's film of the kit's own moves"),
    "connect": ("connect.py", "Add this project's tools to an AI app: claude-desktop, cursor, codex; --remove, --dry-run"),
    "mcp": ("mcp_server.py", "Spliced's tools for an AI agent, over MCP (your agent starts this, not you)"),
}
BUILT_IN = {
    "setup": "Set everything up in one go, or bring a project up to date after an update: project, skills, film kit, a first film, the app",
    "init": "Start a new project in a folder (default: here): spliced.json and an empty library",
    "projects": "The projects opened on this machine, and which are running now; --json",
    "agents": "`agents install`: Spliced's skills, a section in AGENTS.md and its MCP server (Claude Code, Codex, Cursor, Gemini CLI)",
}
ALIASES = {"serve": "open", "toolbox": "open", "boards": "board", "films": "film", "importer": "imports", "folder": "folders",
           "build": "library", "build_library": "library", "add_reference": "reference", "analyze_reference": "analyze", "check_motion": "motion"}


def usage(project):
    w = max(map(len, list(COMMANDS) + list(BUILT_IN)))
    where = "none here (go to your project's folder, pass --project, or run: spliced init <folder>)"
    if project:
        try:
            with open(os.path.join(project, locate.MARKER)) as f:
                name = json.load(f).get("name") or ""
        except (OSError, ValueError, AttributeError):
            name = ""
        where = project + (f"  ({name})" if name else "")
    return (__doc__.strip() + f"\n\nProject: {where}\n\nCommands:\n"
            + "\n".join(f"  {n:<{w}}  {what}" for n, (_, what) in COMMANDS.items())
            + "\n" + "\n".join(f"  {n:<{w}}  {what}" for n, what in BUILT_IN.items()))


def version():
    """ "0.3.0", and the build when this is a git checkout: asked without needing a project. """
    import re, subprocess
    try:
        with open(os.path.join(HERE, "__init__.py")) as f:
            number = (re.search(r'__version__\s*=\s*"([^"]+)"', f.read()) or [None, "?"])[1]
    except OSError:
        number = "?"
    build = ""
    if os.path.exists(os.path.join(os.path.dirname(HERE), ".git")):
        try:
            build = subprocess.run(["git", "-C", HERE, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return number + (f" (build {build})" if build else "")


def init(args, quiet=False):
    """A new project: the marker file, the taxonomy every breakdown is checked against, and empty places for the rest."""
    root = os.path.abspath(os.path.expanduser(args[0] if args else "."))
    marker = os.path.join(root, locate.MARKER)
    if os.path.exists(marker):
        sys.exit(f"Spliced: {root} is already a project")
    name = next((args[i + 1] for i, a in enumerate(args) if a == "--name" and i + 1 < len(args)), None) or os.path.basename(root)
    template = os.path.join(HERE, "templates", "project")
    for d, _, files in os.walk(template):
        for f in files:
            src = os.path.join(d, f)
            dst = os.path.join(root, os.path.relpath(src, template))
            dst = os.path.join(os.path.dirname(dst), ".gitignore") if f == "gitignore" else dst
            if not os.path.exists(dst):  # never over anything that is already there
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy(src, dst)
    for d in ("library/references", "library/uploads", "reference"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    with open(marker, "w") as f:
        json.dump({"format": 1, "name": name, "brand": {"name": ""}}, f, indent=1)
        f.write("\n")
    if quiet:
        return
    print(f"A new project at {root}\n\n  cd {root}\n  spliced open                      the app, in your browser\n"
          "  spliced reference add <link>      your first reference film\n\n"
          "spliced.json is where the project says whose films these are (brand), which motion profiles it adds,\n"
          "and who reads imported films (agent). `spliced agents install` gives your AI Spliced's skills.")


def setup(args):
    """One command from nothing to a rendered film, safe to run again: each step does only what is still missing.
    After an update of Spliced it is also what brings a project's skills and film kit up to date.

      spliced setup [<folder>] [--name <name>] [--no-kit] [--no-render] [--no-open]
    """
    import subprocess
    flags = {x for x in args if x.startswith("--")}
    name = next((args[i + 1] for i, x in enumerate(args) if x == "--name" and i + 1 < len(args)), None)
    rest = [x for i, x in enumerate(args) if not x.startswith("--") and not (i and args[i - 1] == "--name")]
    folder = rest[0] if rest else None
    step = lambda n, what: print(f"\n[{n}/5] {what}", flush=True)

    # 1. the project: the folder named, the one we are in, or a new one here when here is empty
    project = None if folder else locate.find()
    step(1, "The project")
    if project:
        print(f"{project} (already a project)")
    else:
        root = os.path.abspath(os.path.expanduser(folder or "."))
        if os.path.exists(os.path.join(root, locate.MARKER)):
            project = root
            print(f"{project} (already a project)")
        else:
            if not folder and any(not n.startswith(".") for n in os.listdir(root)):
                sys.exit(f"Spliced: {root} has files in it and isn't a project. Name a folder for the new project:\n"
                         f"  spliced setup my-films\n(or make this folder one with: spliced init .)")
            init([root] + (["--name", name] if name else []), quiet=True)
            project = root
            print(f"A new project at {project}")
    project = os.path.realpath(project)
    os.environ["SPLICED_PROJECT"] = project
    run = lambda *x: subprocess.run([sys.executable, os.path.abspath(__file__), "--project", project, *x]).returncode

    # 2. the person's AI: the skills, the section in AGENTS.md, the MCP server
    step(2, "Your AI: Spliced's skills, a section in AGENTS.md, its tools over MCP")
    agents(["install"], project, quiet=True)

    # 3. the film kit (also what brings it up to date), and the example film in a project that has no film yet
    films = os.path.join(project, _layout(project, "remotion"), "src", "films")
    had_film = os.path.isdir(films) and any(os.path.isfile(os.path.join(films, d, "storyboard.json")) for d in os.listdir(films))
    rendered = False
    step(3, "The film kit: the motion library and the packages that render a film")
    if "--no-kit" in flags:
        print("Skipped (--no-kit). Later: spliced kit install")
    elif not shutil.which("npm"):
        print("Skipped: Node.js isn't on this machine, and films are rendered with it. Install Node.js (https://nodejs.org/en/download),\n"
              "then run this again. Everything else works without it.")
    elif run("kit", "install"):
        print("The film kit didn't install: the lines above say why. Run this again once that is sorted.")
    else:
        if not had_film and not run("kit", "starter"):
            # 4. a first film, start to finish: it shows the whole chain works, and gives Build something to show
            step(4, "A first film: the example, rendered")
            if "--no-render" in flags:
                print("Skipped (--no-render).")
            elif not shutil.which("uv"):
                print("Skipped: rendering runs through uv, which isn't on this machine (https://docs.astral.sh/uv/getting-started/installation/).")
            else:
                starters = sorted(d for d in os.listdir(films) if os.path.isfile(os.path.join(films, d, "storyboard.json"))) if os.path.isdir(films) else []
                rendered = bool(starters) and not run("film", "render", starters[0])
        else:
            step(4, "A first film")
            print("This project has films already: nothing to add.")

    # 5. what is set up on this machine, then the app
    step(5, "What is set up on this machine")
    run("doctor")
    if "--no-open" not in flags and shutil.which("uv"):
        print()
        run("open", "--background")
    cli = _cli_name()
    print("\nNext, say this to your AI in this folder (or do it yourself in the app):\n"
          "  1. \"Add this film as a reference: <a link to a film whose motion you like>\"\n"
          "  2. \"Break it down\" (your AI reads it scene by scene; the import waits for it)\n"
          "  3. \"Make a film about <your product> that borrows from it\"" + (", then compare it with the example in Build" if rendered else "")
          + f"\n{cli} with no arguments lists every command.")


def _layout(project, key):
    """A folder's name in this project (spliced.json "layout" may rename it), without needing paths.py."""
    try:
        with open(os.path.join(project, locate.MARKER)) as f:
            v = (json.load(f).get("layout") or {}).get(key)
    except (OSError, ValueError, AttributeError):
        v = None
    return v if isinstance(v, str) and v else key


def _cli_name():
    """How to write a Spliced command for this person: the installed command, the one inside the Mac app, npx, or this checkout."""
    via = os.environ.get("SPLICED_VIA", "").strip()   # npx (bin/spliced.js): its `spliced` on the PATH is temporary
    if shutil.which("spliced") and not via:
        return "spliced"
    app = os.environ.get("SPLICED_COMMAND", "")
    return shlex.quote(app) if os.path.isfile(app) else via if via else "uv run " + os.path.join(HERE, "cli.py")


BLOCK = ("<!-- spliced:begin -->", "<!-- spliced:end -->")
AGENTS_MD = """{begin}
## Spliced

This folder is a Spliced project: a library of reference films broken down scene by scene, boards that are scripts
built from those scenes, and films in production. `spliced.json` holds its settings. (This section is written by
`spliced agents install`; edit outside it.)

- `{cli}` with no arguments lists every command. `{cli} doctor` says what is set up on this machine.
- To show the person the app, run `{cli} open --background`: it starts the app, opens it in their browser and returns
  with its address (`{cli} open` alone stays in the foreground until stopped). `{cli} open --stop` stops it.
- Scenes are referenced as `<film>/sNN`. Find them with `{cli} board find "<words>"`, read one with `{cli} board scene <film>/sNN`.
- Boards are scripts. Read one back with `{cli} board show "<board>"` before discussing it, since the person may have
  edited it in the app; change it with `{cli} board add`, `edit`, `mv`, `rm`.
- Adding a reference film: follow `.claude/skills/add-reference/SKILL.md`. An import may be waiting for you: `{cli} imports next`.
- A folder the person already has (pictures, clips, films): `{cli} import <folder>` says what is in it and what reading it
  will ask of you; tell them, and bring it in with `--go` once they agree.
- Making a film: follow `.claude/skills/make-film/SKILL.md`. Films are built on Spliced's film kit in `remotion/`
  (`{cli} kit` says whether it is in; its files are Spliced's, so don't edit them). The project's own rules, if it has
  them, are in `remotion/docs/HOUSE.md`.
- Films in production: `{cli} film status <slug>`. File the person's feedback on its frame with `{cli} film note`, and
  close every note you fix with `{cli} film done`.
- The project may sort its films, boards and assets into folders (`{cli} folders`), say one per kind of video or per
  client. A film or board started while you work inside one of them goes there; move a film with `{cli} film move`.
  A Remotion film in a folder renders to `<folder>/renders/`; a HyperFrames film in a folder lives in `<folder>/<slug>/`.
  The library is never in a folder: every folder borrows from all of it.
- In a git worktree (a Conductor workspace), `{cli} film render` puts the render in the main checkout's folders, so the
  person sees it in Spliced there; the project can keep renders with the branch instead (spliced.json `worktree_renders`).
- Tags come only from `library/TAXONOMY.md`. `INDEX.md` and every `breakdown.md` are generated: edit `breakdown.json`,
  then run `{cli} library`.
- Without a shell, the same is offered as MCP tools: the server is `spliced`, registered in `.mcp.json`.
- Service keys (ElevenLabs, footage libraries) are the person's: they add them in Spliced's Settings, Service keys, or with
  `{cli} keys set <service>` in their own terminal. Never open, print, copy or ask for `.env` or a key; `{cli} keys`
  says which are set.
{code}{end}
"""


def agents(args, project, quiet=False):
    """Give the project's AI what it needs to work with Spliced: the skills, a section in AGENTS.md, and the MCP server."""
    if args[:1] != ["install"]:
        sys.exit("usage: spliced agents install [--force]")
    if not project:
        sys.exit(locate.NO_PROJECT)
    via = os.environ.get("SPLICED_VIA", "").strip()   # npx (bin/spliced.js): its `spliced` on the PATH is temporary
    installed = bool(shutil.which("spliced")) and not via
    app = os.environ.get("SPLICED_COMMAND", "")   # the command inside the Mac app, when that is how Spliced is installed
    app = app if not installed and os.path.isfile(app) else ""
    cli = "spliced" if installed else shlex.quote(app) if app else via if via else "uv run " + os.path.join(HERE, "cli.py")
    # 1. the skills, where an agent that opens the folder looks for them. The copies are Spliced's and a new version
    #    replaces them, but never a file the person changed (skillset.py remembers what it put there)
    import skillset
    done, saved = skillset.install(project, force="--force" in args)
    by = {}
    for rel, what in done:
        by.setdefault(rel.split("/", 1)[0], []).append((rel, what))
    for name, rows in by.items():
        kept = [os.path.basename(r) for r, w in rows if w == "kept"]
        changed = any(w in ("new", "updated", "replaced") for _, w in rows)
        print(f"skill      .claude/skills/{name}" + ("" if changed else " (already current)" if not kept else "")
              + (f"  (your changes to {', '.join(kept)} are kept; `agents install --force` replaces them)" if kept else ""))
    if saved:
        print(f"           what was replaced is kept in {saved}/")
    # 2. a section in AGENTS.md that any agent reads; everything outside the markers is the project's own
    p = os.path.join(project, "AGENTS.md")
    try:   # where the product's real code is, if the project says (spliced.json "app": {"code": ...})
        with open(os.path.join(project, locate.MARKER)) as f:
            code = (json.load(f).get("app") or {}).get("code")
    except (OSError, ValueError, AttributeError):
        code = None
    code = [str(c) for c in (code if isinstance(code, list) else [code] if code else [])]
    line = (f"- The product's real code is at {', '.join('`' + c + '`' for c in code)}. Rebuild a film's UI from the components, styles and copy\n"
            "  that ship there, never from memory or a screenshot.\n") if code else ""
    block = AGENTS_MD.format(begin=BLOCK[0], end=BLOCK[1], cli=cli, code=line)
    old = open(p).read() if os.path.exists(p) else ""
    if BLOCK[0] in old and BLOCK[1] in old:
        new = old[:old.index(BLOCK[0])] + block.rstrip("\n") + old[old.index(BLOCK[1]) + len(BLOCK[1]):]
    else:
        new = (old.rstrip("\n") + "\n\n" if old.strip() else "") + block
    if new != old:
        with open(p, "w") as f:
            f.write(new)
    print("section    AGENTS.md" + ("" if new != old else " (already current)"))
    cm = os.path.join(project, "CLAUDE.md")
    if not os.path.exists(cm):  # Claude Code reads CLAUDE.md: point it at the same instructions
        with open(cm, "w") as f:
            f.write("@AGENTS.md\n")
        print("pointer    CLAUDE.md -> AGENTS.md")
    # 3. Claude Code may not read the project's keys: a deny rule for .env in .claude/settings.json (merged, never replaced)
    sp = os.path.join(project, ".claude", "settings.json")
    try:
        with open(sp) as f:
            st = json.load(f)
        if not isinstance(st, dict):
            raise ValueError
    except FileNotFoundError:
        st = {}
    except ValueError:
        st = None
        print("keys       .claude/settings.json isn't valid JSON, so .env isn't fenced off from Claude Code")
    if st is not None:
        deny = st.setdefault("permissions", {}).setdefault("deny", [])
        add = [r for r in ("Read(./.env)", "Read(./.env.*)") if r not in deny]
        deny.extend(add)
        if add:
            os.makedirs(os.path.dirname(sp), exist_ok=True)
            with open(sp, "w") as f:
                json.dump(st, f, indent=2)
                f.write("\n")
        print("keys       .claude/settings.json: Claude Code may not read .env" + ("" if add else " (already current)"))
    # 4. the MCP server, for agents that read a project's .mcp.json (Claude Code asks before using it the first time)
    mp = os.path.join(project, ".mcp.json")
    try:
        with open(mp) as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            raise ValueError
    except FileNotFoundError:
        cfg = {}
    except ValueError:
        sys.exit("Spliced: .mcp.json isn't valid JSON; fix or remove it, then run this again")
    entry = ({"command": "spliced", "args": ["mcp"]} if installed else {"command": app, "args": ["mcp"]} if app
             else {"command": shlex.split(via)[0], "args": shlex.split(via)[1:] + ["mcp"]} if via
             else {"command": "uv", "args": ["run", os.path.join(HERE, "cli.py"), "mcp"]})
    servers = cfg.setdefault("mcpServers", {})
    changed = servers.get("spliced") != entry
    servers["spliced"] = entry
    if changed:
        with open(mp, "w") as f:
            json.dump(cfg, f, indent=1)
            f.write("\n")
    print("mcp server .mcp.json" + ("" if changed else " (already current)"))
    # 5. Gemini CLI: it reads GEMINI.md (which imports AGENTS.md) and its own .gemini/settings.json, not .mcp.json
    gm = os.path.join(project, "GEMINI.md")
    if not os.path.exists(gm):
        with open(gm, "w") as f:
            f.write("@./AGENTS.md\n")
        print("pointer    GEMINI.md -> AGENTS.md")
    gp = os.path.join(project, ".gemini", "settings.json")
    try:
        with open(gp) as f:
            gcfg = json.load(f)
        if not isinstance(gcfg, dict):
            raise ValueError
    except FileNotFoundError:
        gcfg = {}
    except ValueError:
        gcfg = None
        print("mcp server .gemini/settings.json isn't valid JSON, so Gemini CLI wasn't given the tools")
    if gcfg is not None:
        gservers = gcfg.setdefault("mcpServers", {})
        gchanged = gservers.get("spliced") != entry
        gservers["spliced"] = dict(entry)
        if gchanged:
            os.makedirs(os.path.dirname(gp), exist_ok=True)
            with open(gp, "w") as f:
                json.dump(gcfg, f, indent=2)
                f.write("\n")
        print("mcp server .gemini/settings.json (Gemini CLI)" + ("" if gchanged else " (already current)"))
    # its file tools skip what .geminiignore names: the project's keys among them
    ig = os.path.join(project, ".geminiignore")
    have = open(ig).read().splitlines() if os.path.exists(ig) else []
    add = [x for x in (".env", ".env.*") if x not in have]
    if add:
        with open(ig, "a") as f:
            f.write(("\n" if have and have[-1] else "") + "\n".join(add) + "\n")
    print("keys       .geminiignore: Gemini CLI's file tools skip .env" + ("" if add else " (already current)"))
    if not quiet:
        print(f"\nOther agents: Codex registers it with `codex mcp add spliced -- {' '.join([entry['command']] + entry['args'])}`.\n"
              f"Check what is set up with: {cli} doctor")


def is_uv_script(path):
    with open(path) as f:
        return f.readline().startswith("# /// script")


def main():
    a = sys.argv[1:]
    named = locate.flag(a)
    if named:
        os.environ["SPLICED_PROJECT"] = named
    if a and a[0] in ("--version", "-V", "version"):
        return print("spliced " + version())
    if a and a[0] == "init":
        return init(a[1:])
    if a and a[0] == "setup":
        return setup(a[1:])
    if a and a[0] == "projects":   # asked from anywhere: it is about every project, not the one you are in
        import projects
        sys.argv = [sys.argv[0], *a[1:]]
        return projects.main()
    project = locate.find()
    if not a or a[0] in ("-h", "--help", "help"):
        print(usage(project))
        return
    if a[0] == "agents":
        return agents(a[1:], project)
    name = ALIASES.get(a[0], a[0])
    if name not in COMMANDS:
        sys.exit(f"spliced: no command called {a[0]!r}\n\n" + usage(project))
    if not project:
        sys.exit(locate.NO_PROJECT)
    os.environ["SPLICED_PROJECT"] = project
    script = os.path.join(HERE, COMMANDS[name][0])
    # a tool with its own packages (its `# /// script` header) runs in its own uv environment; the rest run as they are
    argv = ["uv", "run", "-q", script, *a[1:]] if is_uv_script(script) else [sys.executable, script, *a[1:]]
    sys.stdout.flush()
    try:
        os.execvp(argv[0], argv)
    except FileNotFoundError:
        sys.exit("Spliced needs uv to run its tools: https://docs.astral.sh/uv/getting-started/installation/")


if __name__ == "__main__":
    main()
