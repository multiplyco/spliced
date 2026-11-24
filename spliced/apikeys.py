"""The service keys a project holds, in its .env (which git ignores). Spliced writes them and says which are set;
it never shows, prints or returns a key's value, and no agent tool can set or read one.

usage:
  spliced keys                     which keys this project has (names only, never values)
  spliced keys set <service>       paste a key; it isn't shown or echoed, and goes straight into .env
  spliced keys remove <service>    take one out of .env

services: elevenlabs, pexels, pixabay, unsplash. Settings in the app (Keys) does the same.
`set` asks the person at the keyboard: run by an agent, or with the key on the command line, it refuses, so a key
never passes through an agent's transcript or a shell's history.
"""
import getpass, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

# What Spliced reads, by the name it reads it under. `what` is what the key unlocks, in the person's terms.
KEYS = [
    {"id": "elevenlabs", "name": "ElevenLabs", "env": "ELEVENLABS_API_KEY", "url": "https://elevenlabs.io/app/settings/api-keys",
     "what": "Voice-over recorded by Spliced itself. Optional: without a key, your AI can use a voice service it is connected to, or you can record the lines"},
    {"id": "pexels", "name": "Pexels", "env": "PEXELS_API_KEY", "url": "https://www.pexels.com/api/",
     "what": "Free photos and video in the Assets search"},
    {"id": "pixabay", "name": "Pixabay", "env": "PIXABAY_API_KEY", "url": "https://pixabay.com/api/docs/",
     "what": "Free photos and video in the Assets search"},
    {"id": "unsplash", "name": "Unsplash", "env": "UNSPLASH_ACCESS_KEY", "url": "https://unsplash.com/developers",
     "what": "Free photos in the Assets search (the Access Key)"},
]
BY_ID = {k["id"]: k for k in KEYS}
SHAPE = re.compile(r"[A-Za-z0-9_\-.]{10,300}")


def _lines():
    try:
        with open(paths.ENV) as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []


def _names():
    return {l.split("=", 1)[0].strip().removeprefix("export ").strip() for l in _lines() if "=" in l and not l.lstrip().startswith("#")}


def status():
    """Every key Spliced knows, and whether this project has it: names and state only."""
    have = _names()
    return [{**x, "set": x["env"] in have or bool(os.environ.get(x["env"]))} for x in KEYS]


def _key(service):
    if service not in BY_ID:
        raise ValueError(f"Spliced has no key called {service!r}; one of: {', '.join(BY_ID)}")
    return BY_ID[service]


def _write(lines):
    os.makedirs(os.path.dirname(paths.ENV), exist_ok=True)
    tmp = paths.ENV + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)   # owner only, from the first byte
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    os.replace(tmp, paths.ENV)
    os.chmod(paths.ENV, 0o600)


def _drop(lines, env):
    return [l for l in lines if l.split("=", 1)[0].strip().removeprefix("export ").strip() != env]


def set_key(service, value):
    """Put one key in .env, replacing the one there. Returns {id, env}; never the value."""
    k = _key(service)
    value = (value or "").strip().strip('"\'')
    if not SHAPE.fullmatch(value):
        raise ValueError("that doesn't look like an API key (letters, digits, - _ and . only, no spaces)")
    _write(_drop(_lines(), k["env"]) + [f"{k['env']}={value}"])
    return {"id": k["id"], "env": k["env"]}


def remove_key(service):
    k = _key(service)
    lines = _lines()
    left = _drop(lines, k["env"])
    if left != lines:
        _write(left)
    return {"id": k["id"], "env": k["env"], "removed": left != lines}


def main(a):
    cmd = a[0] if a else ""
    if cmd in ("-h", "--help", "help"):
        return print(__doc__)
    if not cmd or cmd == "list":
        for k in status():
            print(f"  {'✓ set' if k['set'] else '· not set':12} {k['id']:12} {k['env']:22} {k['what']}")
        return print(f"\nAdd one in Spliced (Settings, Service keys) or here: {paths.CLI} keys set <service>. Keys live in .env and are never shown.")
    if cmd in ("set", "remove") and len(a) < 2:
        sys.exit(f"usage: {paths.CLI} keys {cmd} <service>   ({', '.join(BY_ID)})")
    try:
        if cmd == "remove":
            r = remove_key(a[1])
            return print(f"{r['env']} {'taken out of' if r['removed'] else 'was not in'} {paths.rel(paths.ENV)}")
        if cmd == "set":
            if len(a) > 2:
                sys.exit("Spliced: don't put a key on the command line (it stays in your shell's history). Run it without, and paste when asked.")
            if not sys.stdin.isatty():
                sys.exit("Spliced: a key is pasted by a person, not passed in. Run this in your own terminal, or use Settings, Service keys in the app.")
            k = _key(a[1])
            v = getpass.getpass(f"Paste your {k['name']} key (it won't show): ")
            r = set_key(a[1], v)
            return print(f"Saved {r['env']} in {paths.rel(paths.ENV)} (only you can read it; git ignores it).")
    except ValueError as e:
        sys.exit(f"Spliced: {e}")
    sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
