"""Is there a newer Spliced than this one, and how this copy is brought up to date.

  spliced update            which Spliced this is, whether a newer one is out, and the command that gets it
  spliced update --json     the same, for the app
  spliced update --known    only what was learned last time: never goes online

Asked at most once a day, of the npm registry: one request for the newest version number, which carries nothing
about you or your project. The answer is kept in the project's .cache. Turn it off with spliced.json
`"updates": false` or SPLICED_NO_UPDATE_CHECK=1. A git checkout is never asked about (git knows), and the Mac app
has its own check (mac/Sources/Spliced/Updates.swift).

After an update, `spliced setup` brings the project's copies of Spliced's files (the skills, the film kit) up to date.

Standard library only: the server imports this to answer /api/update.
"""
import json, os, re, sys, time, urllib.request

import paths

PACKAGE = "spliced-app"                      # the name Spliced is published under (package.json, pyproject.toml)
URL = paths.env("UPDATE_URL") or f"https://registry.npmjs.org/{PACKAGE}/latest"   # SPLICED_UPDATE_URL: a stand-in, for checks of this code
FILE = os.path.join(paths.CACHE, "update.json")
DAY, HOUR = 24 * 3600, 3600


def kind():
    """How this copy was installed, which decides how it is updated: npx | npm | app | checkout | uv | other."""
    tools = paths.TOOLS.replace(os.sep, "/")
    if paths.VIA.startswith("npx"):
        return "npx"
    if paths.COMMAND:
        return "app"
    if os.path.exists(os.path.join(os.path.dirname(paths.TOOLS), ".git")):
        return "checkout"
    if "/node_modules/" in tools:
        return "npm"
    if "/uv/tools/" in tools:
        return "uv"
    return "other"


HOW = {   # kind -> (the command, or "" when there is none to run; what to say)
    "npx": ("", "npx fetches the newest Spliced each time it starts: stop Spliced and start it again"),
    "npm": (f"npm install -g {PACKAGE}@latest", "Then start Spliced again"),
    "uv": (f"uv tool upgrade {PACKAGE}", "Then start Spliced again"),
    "other": (f"npm install -g {PACKAGE}@latest", "Then start Spliced again"),
    "checkout": ("git pull", "This copy is a git checkout: pull to update it"),
    "app": ("", "The Mac app updates itself: Spliced, Check for Updates"),
}


def off():
    if paths.env("NO_UPDATE_CHECK") or paths.CONFIG.get("updates") is False:
        return True
    if paths.env("UPDATE_URL"):   # a stand-in was named on purpose (a check of this code): ask it, whatever kind of copy this is
        return False
    return bool(paths.env("OFFLINE") or kind() in ("checkout", "app"))


def _number(v):
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", str(v or ""))
    return tuple(int(x) for x in m.groups()) if m else None


def newer(latest, current):
    a, b = _number(latest), _number(current)
    return bool(a and b and a > b)


def _read():
    try:
        with open(FILE) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _ask():
    """The newest version's number, or None when the registry can't be reached or says nothing useful."""
    try:
        req = urllib.request.Request(URL, headers={"Accept": "application/json", "User-Agent": f"spliced/{paths.VERSION}"})
        with urllib.request.urlopen(req, timeout=4) as r:
            v = json.load(r).get("version")
        return v if _number(v) else None
    except Exception:   # offline, not published yet, a proxy's own page: all the same answer, "don't know"
        return None


def check(fresh=False, online=True):
    """{current, latest, newer, kind, command, how, checked, off}. online=False: only what is already known."""
    k = kind()
    out = {"current": paths.VERSION, "latest": None, "newer": False, "kind": k, "command": HOW[k][0], "how": HOW[k][1], "checked": None, "off": off()}
    if out["off"]:
        return out
    d = _read()
    age = time.time() - float(d.get("checked") or 0)
    stale = age > (DAY if d.get("latest") else HOUR)   # an answer keeps for a day; "couldn't tell" is asked again in an hour
    if online and (fresh or stale):
        d = {"latest": _ask(), "checked": int(time.time())}
        try:
            os.makedirs(paths.CACHE, exist_ok=True)
            with open(FILE, "w") as f:
                json.dump(d, f)
        except OSError:
            pass
    out["latest"], out["checked"] = d.get("latest"), d.get("checked")
    out["newer"] = newer(out["latest"], paths.VERSION)
    return out


def report(u):
    if u["off"]:
        why = ("this copy is a git checkout: `git pull` updates it" if u["kind"] == "checkout" else "the Mac app checks for itself" if u["kind"] == "app"
               else "checking is turned off for this project")
        return f"Spliced {paths.VERSION}. Not checked: {why}."
    if u["newer"]:
        return (f"Spliced {u['latest']} is out (this is {paths.VERSION}).\n  " + (f"{u['command']}\n  {u['how']}." if u["command"] else u["how"] + ".")
                + f"\nAfter updating, `{paths.CLI} setup` brings this project's skills and film kit up to date.")
    if u["latest"]:
        return f"Spliced {paths.VERSION} is the newest."
    return f"Spliced {paths.VERSION}. Couldn't tell whether a newer one is out (offline, or not published yet)."


def main():
    a = sys.argv[1:]
    u = check(fresh="--known" not in a, online="--known" not in a)
    print(json.dumps(u, indent=1) if "--json" in a else report(u))


if __name__ == "__main__":
    main()
