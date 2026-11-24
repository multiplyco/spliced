"""Connect an AI app to this project: add Spliced's tools (its MCP server) to the app's own settings.

`spliced agents install` covers agents that open the project folder (Claude Code, Codex, Cursor read the
project's .mcp.json and AGENTS.md; Gemini CLI its .gemini/settings.json and GEMINI.md). Chat apps don't open a folder: the Claude desktop app, Cursor's global
tools and Codex keep their own list of tool servers. This adds one entry per project, named spliced-<project>,
that runs `spliced --project <this folder> mcp`.

usage:
  spliced connect                        which apps are connected to this project
  spliced connect claude-desktop         the Claude desktop app (quit and reopen it afterwards)
  spliced connect cursor                 Cursor, for every window (~/.cursor/mcp.json)
  spliced connect codex                  Codex (through `codex mcp add`)
  spliced connect <app> --remove         take this project out again
  spliced connect <app> --dry-run        show what would change, change nothing
  spliced connect <app> --here           connect a git worktree anyway (by default, connect from the main checkout)
  spliced connect --json                 the list, for the app
"""
import json, os, re, shlex, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

HOME = os.path.expanduser("~")
APPS = {
    "claude-desktop": {"name": "Claude desktop app", "file": os.path.join(HOME, "Library", "Application Support", "Claude", "claude_desktop_config.json")
                       if sys.platform == "darwin" else os.path.join(os.environ.get("APPDATA", HOME), "Claude", "claude_desktop_config.json"),
                       "after": "Quit the Claude app and open it again: Spliced's tools are under the tools button in a chat."},
    "cursor": {"name": "Cursor", "file": os.path.join(HOME, ".cursor", "mcp.json"), "after": "Cursor picks it up in a new chat (Settings, Tools & MCP lists it)."},
    "codex": {"name": "Codex", "file": os.path.join(HOME, ".codex", "config.toml"), "after": "Start a new Codex session to use it."},
}


def key():
    """This project's entry name in an app: spliced-<project>, in the characters every app accepts."""
    return "spliced-" + (re.sub(r"[^a-z0-9]+", "-", paths.NAME.lower()).strip("-") or "project")


def entry():
    """How an app starts Spliced's MCP server for this project, with full paths. A chat app starts its tools with a
    bare PATH (/usr/bin:/bin), where uv, ffmpeg and node aren't, so the entry carries this shell's PATH too."""
    seen, dirs = set(), []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if d and d not in seen and os.path.isdir(d):
            seen.add(d); dirs.append(d)
    env = {"PATH": os.pathsep.join(dirs)}
    installed = shutil.which("spliced") if not paths.VIA else None   # under npx the one on the PATH is temporary
    if installed:
        return {"command": os.path.abspath(installed), "args": ["--project", paths.ROOT, "mcp"], "env": env}
    if paths.COMMAND:   # the command inside the Mac app
        return {"command": paths.COMMAND, "args": ["--project", paths.ROOT, "mcp"], "env": env}
    if paths.VIA:       # npx: "npx -y <package>", with npx's full path
        first, *rest = shlex.split(paths.VIA)
        return {"command": shutil.which(first) or first, "args": [*rest, "--project", paths.ROOT, "mcp"], "env": env}
    uv = shutil.which("uv") or "uv"
    return {"command": os.path.abspath(uv) if uv != "uv" else uv, "args": ["run", paths.tool("cli"), "--project", paths.ROOT, "mcp"], "env": env}


def _read_json(path):
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except ValueError:
        sys.exit(f"Spliced: {path} isn't valid JSON; fix it first, Spliced won't write over it")
    if not isinstance(data, dict):
        sys.exit(f"Spliced: {path} isn't a JSON object; Spliced won't write over it")
    return data


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and not os.path.exists(path + ".before-spliced"):   # the first time we touch it, keep the original
        shutil.copy2(path, path + ".before-spliced")
    tmp = path + ".spliced-tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def present(app):
    """Is the app on this machine at all (its settings folder, or for Codex its command)?"""
    if app == "codex":
        return bool(shutil.which("codex")) or os.path.isdir(os.path.dirname(APPS[app]["file"]))
    return os.path.isdir(os.path.dirname(APPS[app]["file"]))


def connected(app):
    """This project's entry in the app, if there is one."""
    if app == "codex":
        try:
            with open(APPS[app]["file"]) as f:
                text = f.read()
        except OSError:
            return None
        return {"name": key()} if re.search(r"^\[mcp_servers\.\"?" + re.escape(key()) + r"\"?\]", text, re.M) else None
    return (_read_json(APPS[app]["file"]).get("mcpServers") or {}).get(key())


def status():
    return [{"id": a, "name": v["name"], "present": present(a), "connected": bool(connected(a)), "file": v["file"]} for a, v in APPS.items()]


def change(app, remove=False, dry=False):
    """Add (or take out) this project's entry. Returns what happened, in a sentence."""
    meta, name, e = APPS[app], key(), entry()
    if app == "codex":
        codex = shutil.which("codex")
        env = [f"--env={k}={v}" for k, v in e.get("env", {}).items()]
        cmd = [codex or "codex", "mcp", "remove", name] if remove else [codex or "codex", "mcp", "add", name, *env, "--", e["command"], *e["args"]]
        if dry:
            return "would run: " + " ".join(cmd)
        if not codex:
            sys.exit("Spliced: the codex command isn't on this machine; install Codex first (https://developers.openai.com/codex)")
        if remove and not connected(app):
            return f"{meta['name']} has no {name}: nothing to take out"
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"Spliced: {' '.join(cmd)} failed:\n{(r.stdout + r.stderr).strip()}")
        return f"{'Took' if remove else 'Added'} {name} {'out of' if remove else 'to'} {meta['name']}. " + ("" if remove else meta["after"])
    data = _read_json(meta["file"])
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        sys.exit(f"Spliced: mcpServers in {meta['file']} isn't an object; Spliced won't write over it")
    if remove:
        if name not in servers:
            return f"{meta['name']} has no {name}: nothing to take out"
        if dry:
            return f"would take {name} out of {meta['file']}"
        del servers[name]
        _write_json(meta["file"], data)
        return f"Took {name} out of {meta['name']}."
    if servers.get(name) == e:
        return f"{meta['name']} already has {name}."
    if dry:
        return f"would write into {meta['file']}:\n" + json.dumps({"mcpServers": {name: e}}, indent=2)
    servers[name] = e
    _write_json(meta["file"], data)
    return f"Added {name} to {meta['name']} ({meta['file']}). {meta['after']}"


def main(argv):
    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        s = status()
        if "--json" in flags:
            return print(json.dumps({"key": key(), "entry": entry(), "apps": s}))
        print(f"AI apps and this project ({paths.NAME}, as {key()}):")
        for a in s:
            mark = "✓ connected" if a["connected"] else "· not connected" if a["present"] else "  not on this machine"
            print(f"  {mark:22} {a['name']:20} {paths.CLI} connect {a['id']}")
        if not any(a["connected"] for a in s):
            print("\nThis only lists them. Connect one with the command beside it, then quit and reopen that app.")
        main = paths.main_checkout()
        if main:
            print(f"\n! This folder is a git worktree. Connect from the main checkout, which stays put:\n  cd {main} && {paths.CLI} connect <app>")
        print(f"\nAgents that open this folder (Claude Code, Codex, Cursor, Gemini CLI) use {paths.CLI} agents install instead.")
        return
    app = args[0]
    if app not in APPS:
        sys.exit(f"Spliced: no app called {app!r}; one of: {', '.join(APPS)}\n\n{__doc__}")
    main = paths.main_checkout()
    if main and "--remove" not in flags and "--dry-run" not in flags and "--here" not in flags:
        # A worktree goes away when its branch is done; the app would keep starting Spliced on a folder that is gone.
        sys.exit(f"Spliced: {paths.ROOT} is a git worktree of {main}. The app would keep pointing here after it is removed.\n"
                 f"Connect the main checkout instead:  cd {main} && {paths.CLI} connect {app}\n"
                 f"(or {paths.CLI} connect {app} --here to connect this worktree anyway)")
    print(change(app, remove="--remove" in flags, dry="--dry-run" in flags))


if __name__ == "__main__":
    if sys.argv[1:2] in (["-h"], ["--help"]):
        print(__doc__)
    else:
        main(sys.argv[1:])
