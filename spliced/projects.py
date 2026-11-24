"""The projects this person has opened, newest first: what lets one project's app offer the others.

  spliced projects          the projects opened on this machine, and which are running now

A project is noted when its app starts. The list is the person's, so it lives with their own settings
(~/.config/spliced/projects.json, or under XDG_CONFIG_HOME), never in Spliced's folders and never in a project.
A folder that is gone, or no longer a project, drops out by itself. (The Mac app keeps its own list of recent
projects for its menus; this one is what `spliced open` in a browser uses.)

Needs no project to be asked, and nothing but the standard library.
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locate

KEEP = 30


def _file():
    home = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(home, "spliced", "projects.json")


def _read():
    try:
        with open(_file()) as f:
            d = json.load(f)
        return [x for x in d if isinstance(x, dict) and isinstance(x.get("root"), str)] if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def name_of(root):
    try:
        with open(os.path.join(root, locate.MARKER)) as f:
            return str(json.load(f).get("name") or "") or os.path.basename(root)
    except (OSError, ValueError, AttributeError):
        return os.path.basename(root)


def note(root):
    """This project was opened now. Never an error: a list that can't be written is only a shorter menu."""
    root = os.path.realpath(root)
    rows = [{"root": root, "opened": int(time.time())}] + [x for x in _read() if os.path.realpath(x["root"]) != root]
    try:
        os.makedirs(os.path.dirname(_file()), exist_ok=True)
        tmp = _file() + ".tmp"
        with open(tmp, "w") as f:
            json.dump(rows[:KEEP], f, indent=1)
        os.replace(tmp, _file())
    except OSError:
        pass


def running(root):
    """Where this project's app is served right now ({port, url, pid}), or None. Its server wrote .cache/server.json."""
    try:
        with open(os.path.join(root, ".cache", "server.json")) as f:
            info = json.load(f)
        os.kill(int(info["pid"]), 0)
        return info if os.path.realpath(str(info.get("root") or "")) == os.path.realpath(root) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def recent():
    """[{root, name, opened, url}]: every noted folder that is still a project, newest first; url when it is running."""
    out = []
    for x in _read():
        root = x["root"]
        if os.path.isfile(os.path.join(root, locate.MARKER)):
            live = running(root)
            out.append({"root": root, "name": name_of(root), "opened": x.get("opened"), "url": live["url"] if live else None})
    return out


def main():
    rows = recent()
    if "--json" in sys.argv[1:]:
        return print(json.dumps(rows, indent=1))
    if not rows:
        return print("No project has been opened on this machine yet. Start one with: spliced setup <folder>")
    w = max(len(r["name"]) for r in rows)
    for r in rows:
        print(f"{r['name']:<{w}}  {r['root']}" + (f"   running at {r['url']}" if r["url"] else ""))


if __name__ == "__main__":
    main()
