"""The film kit: a Remotion setup for making films with Spliced, copied into the project's remotion/ folder.

Two kinds of file. The kit's own (the motion library in src/lib, the specimens, docs/CRAFT.md, MOTION-SYSTEMS.md,
SOUND.md, the UI sound kit) are Spliced's: `update` replaces them with this version's, the way `agents install`
replaces the skills. The project's own (package.json, Root.tsx, src/profiles.ts, its films) are written once if
they are missing and never touched again. src/profiles.generated.ts is Spliced's too: the project's profiles as code,
written on every install and update and whenever a profile changes (profiles.write_code). remotion/.spliced-kit.json remembers which version is in and what each
kit file held, so a kit file changed by hand is noticed instead of overwritten.

usage:
  spliced kit                      what is installed, and whether it is current
  spliced kit install [--no-npm]   the kit into remotion/, and its packages (Remotion, React) with npm
  spliced kit packages [--background]   install remotion/'s packages if they are missing (`spliced open` does it too)
  spliced kit update [--force]     replace the kit's files with this version's (--force: also ones changed by hand)
  spliced kit starter [<film>]     add the example films (or one) to the project, to read, render and borrow from
"""
import datetime, hashlib, json, os, re, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

KIT = os.path.join(paths.TOOLS, "kit")
MANAGED = os.path.join(KIT, "managed")
PROJECT = os.path.join(KIT, "project")
# The example films: beside the package (a checkout, npm, the Mac app), or inside it (a copy built as a Python wheel)
STARTER = next((p for p in (os.path.join(os.path.dirname(paths.TOOLS), "starter"), os.path.join(paths.TOOLS, "starter")) if os.path.isdir(p)),
               os.path.join(os.path.dirname(paths.TOOLS), "starter"))
MANIFEST = os.path.join(paths.REMOTION, ".spliced-kit.json")


def _sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _files(root):
    out = []
    for d, dirs, names in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in ("__pycache__", "node_modules"))
        out += [os.path.relpath(os.path.join(d, n), root) for n in sorted(names) if n != ".DS_Store"]
    return out


def manifest():
    try:
        with open(MANIFEST) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def status():
    """{installed, version, current, edited: [...], stale: [...], missing: [...]} for the doctor and `spliced kit`."""
    m = manifest()
    if not m:
        return {"installed": False, "version": None, "current": False, "edited": [], "stale": [], "missing": []}
    edited, stale, missing = [], [], []
    for rel in _files(MANAGED):
        here, theirs = os.path.join(paths.REMOTION, rel), _sha(os.path.join(MANAGED, rel))
        if not os.path.exists(here):
            missing.append(rel)
            continue
        mine = _sha(here)
        if mine != m["files"].get(rel) and mine != theirs:
            edited.append(rel)
        elif mine != theirs:
            stale.append(rel)
    if not os.path.isfile(os.path.join(paths.REMOTION, "src", "profiles.generated.ts")):
        missing.append("src/profiles.generated.ts")   # written by update, never shipped: the profiles as code
    return {"installed": True, "version": m.get("version"), "current": not (stale or missing), "edited": edited,
            "stale": stale, "missing": missing}


def _write_manifest(files):
    with open(MANIFEST, "w") as f:
        json.dump({"_note": "Written by `spliced kit`: the kit version in this folder and what each of its files held, so "
                            "a file changed by hand is noticed. Kit files are Spliced's; put your own code beside them.",
                   "version": paths.VERSION, "files": files}, f, indent=1)
        f.write("\n")


# ---------- the packages: remotion/node_modules ----------
# A project's remotion/ carries package.json and its lock, never node_modules (a fresh clone, a new worktree, a
# teammate's machine). Spliced installs them itself: after `kit install`, and when the app opens a project without them.
NPM_JOB = os.path.join(paths.CACHE, "npm-install.json")
NPM_LOG = os.path.join(paths.CACHE, "npm-install.log")
LICENCE = "Remotion is free for individuals and small teams and needs a company licence above that: remotion.dev/license"
_WRAP = ("import json, subprocess, sys, datetime\n"
         "log, job, cwd, cmd = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]\n"
         "with open(log, 'w') as f:\n    code = subprocess.call(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT)\n"
         "j = json.load(open(job)); j.update(exit=code, ended=datetime.datetime.now().isoformat(timespec='seconds'))\n"
         "json.dump(j, open(job, 'w'), indent=1)\n")


def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _npm_cmd():
    npm = shutil.which("npm")
    if not npm:
        return None
    # the lock pins every version: `npm ci` installs exactly those and never rewrites it
    lock = os.path.isfile(os.path.join(paths.REMOTION, "package-lock.json"))
    return [npm, "ci" if lock else "install", "--no-audit", "--no-fund"]


def packages():
    """{state: none|ok|installing|failed|missing|no-npm, detail}. none: no remotion/package.json, nothing to install."""
    if not os.path.isfile(os.path.join(paths.REMOTION, "package.json")):
        return {"state": "none"}
    try:
        with open(NPM_JOB) as f:
            j = json.load(f)
    except (OSError, ValueError):
        j = {}
    if j and "exit" not in j and _alive(j.get("pid")):
        return {"state": "installing", "started": j.get("started"), "log": paths.rel(NPM_LOG)}
    if os.path.isdir(os.path.join(paths.REMOTION, "node_modules", "remotion")):
        return {"state": "ok"}
    if j.get("exit"):
        try:
            with open(NPM_LOG) as f:
                tail = [l for l in f.read().splitlines() if l.strip()][-6:]
        except OSError:
            tail = []
        return {"state": "failed", "ended": j.get("ended"), "log": paths.rel(NPM_LOG), "tail": tail}
    return {"state": "missing" if _npm_cmd() else "no-npm"}


def install_packages(background=False, quiet=False):
    """Install remotion/'s packages when they are missing. One install at a time per project.
    Foreground: npm's own output, and True if they are in. Background: started (True) or not needed / not possible."""
    st = packages()
    if st["state"] in ("none", "ok"):
        return True
    if st["state"] == "installing":
        if not quiet:
            print(f"Spliced: {paths.rel(paths.REMOTION)}/'s packages are being installed already (since {st['started']}; {st['log']})")
        return True
    if st["state"] == "no-npm":
        if not quiet:
            print(f"Spliced: npm isn't on this machine, so {paths.rel(paths.REMOTION)}/'s packages aren't installed. Install Node.js, then {paths.CLI} kit packages")
        return False
    cmd = _npm_cmd()
    where = paths.rel(paths.REMOTION)
    os.makedirs(paths.CACHE, exist_ok=True)
    with open(NPM_JOB, "w") as f:
        json.dump({"started": datetime.datetime.now().isoformat(timespec="seconds"), "cmd": cmd[1:], "pid": None}, f, indent=1)
    if background:
        p = subprocess.Popen([sys.executable, "-c", _WRAP, NPM_LOG, NPM_JOB, paths.REMOTION, *cmd], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, cwd=paths.ROOT)
        with open(NPM_JOB) as f:
            j = json.load(f)
        if "exit" not in j:
            j["pid"] = p.pid
            with open(NPM_JOB, "w") as f:
                json.dump(j, f, indent=1)
        if not quiet:
            print(f"Spliced: installing {where}/'s packages (Remotion, React) in the background: npm {cmd[1]}. {LICENCE}", flush=True)
        return True
    if not quiet:
        print(f"\nInstalling {where}/'s packages (Remotion, React): npm {cmd[1]}. {LICENCE}", flush=True)
    with open(NPM_JOB) as f:
        j = json.load(f)
    j["pid"] = os.getpid()
    with open(NPM_JOB, "w") as f:
        json.dump(j, f, indent=1)
    r = subprocess.run(cmd, cwd=paths.REMOTION, stdout=subprocess.DEVNULL if quiet else None, stderr=subprocess.STDOUT if quiet else None)
    j.update(exit=r.returncode, ended=datetime.datetime.now().isoformat(timespec="seconds"))
    with open(NPM_JOB, "w") as f:
        json.dump(j, f, indent=1)
    if r.returncode and not quiet:
        print(f"Spliced: npm {cmd[1]} failed in {where}/ (exit {r.returncode}). Run it there yourself to see why: cd {where} && npm {cmd[1]}")
    return r.returncode == 0


def install(force=False, quiet=False, npm=True):
    """Copy the kit in. The project's own files only when missing; the kit's files unless changed by hand (or --force).
    Then its packages, unless npm is False (--no-npm)."""
    os.makedirs(paths.REMOTION, exist_ok=True)
    wrote = []
    name = re.sub(r"[^a-z0-9]+", "-", paths.NAME.lower()).strip("-") or "project"
    for rel in _files(PROJECT):
        dst = os.path.join(paths.REMOTION, ".gitignore" if rel == "gitignore" else rel)
        if os.path.exists(dst):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(os.path.join(PROJECT, rel), encoding="utf-8") as f:
            text = f.read().replace("__NAME__", name)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(text)
        wrote.append(os.path.relpath(dst, paths.REMOTION) + " (yours from now on)")
    st = status()
    if not st["installed"]:   # the first time: files already at the kit's paths that differ are someone's own work
        st["edited"] = [r for r in _files(MANAGED) if os.path.exists(os.path.join(paths.REMOTION, r))
                        and _sha(os.path.join(paths.REMOTION, r)) != _sha(os.path.join(MANAGED, r))]
    if st["edited"] and not force:
        sys.exit("Spliced: these kit files were changed by hand, so they are left as they are:\n  "
                 + "\n  ".join(st["edited"]) + "\nMove your changes into your own files, then run this again, or add "
                 "--force to replace them with the kit's.")
    files = {}
    for rel in _files(MANAGED):
        src, dst = os.path.join(MANAGED, rel), os.path.join(paths.REMOTION, rel)
        files[rel] = _sha(src)
        if os.path.exists(dst) and _sha(dst) == files[rel]:
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        wrote.append(rel)
    # a kit file this version no longer has goes too, unless it was changed by hand
    old = (manifest() or {}).get("files", {})
    for rel, sha in old.items():
        p = os.path.join(paths.REMOTION, rel)
        if rel not in files and os.path.exists(p) and _sha(p) == sha:
            os.remove(p)
            wrote.append(rel + " (removed: no longer in the kit)")
    _write_manifest(files)
    import profiles   # the project's profiles as code (src/profiles.generated.ts): the kit's profile.tsx reads it
    if profiles.write_code(always=True):
        wrote.append(os.path.relpath(profiles.CODE, paths.REMOTION) + " (the profiles as code)")
    if not quiet:
        where = paths.rel(paths.REMOTION)
        print(f"The film kit {paths.VERSION} is in {where}/." if wrote else f"The film kit in {where}/ is already current.")
        for w in wrote[:40]:
            print("  " + w)
        if len(wrote) > 40:
            print(f"  ... and {len(wrote) - 40} more")
    if npm:
        install_packages(quiet=quiet)
    elif not quiet and packages()["state"] != "ok":
        print(f"\nNext: {paths.CLI} kit packages   (Remotion and React, with npm. {LICENCE})")
    if not quiet:
        where = paths.rel(paths.REMOTION)
        if not os.path.isfile(os.path.join(paths.REMOTION, "docs", "media", "system-moves.mp4")):
            print(f"To see every move in Spliced's Systems view: cd {where} && npm run specimens, then {paths.CLI} moves")
    return wrote


def starters():
    """The example films this copy of Spliced carries: {slug: folder}."""
    root = os.path.join(STARTER, "films")
    if not os.path.isdir(root):
        return {}
    return {n: os.path.join(root, n) for n in sorted(os.listdir(root)) if os.path.isfile(os.path.join(root, n, "starter.json"))}


def starter(only=None):
    films = starters()
    if not films:
        sys.exit("Spliced: this copy of Spliced carries no example films (a checkout, the npm package and the Mac app do)")
    if only and only not in films:
        sys.exit(f"Spliced: no example film called {only!r}; there are: {', '.join(films)}")
    if not manifest():
        install(quiet=True, npm=False)
        print(f"The film kit is in {paths.rel(paths.REMOTION)}/ first, since the examples are built on it.")
        install_packages()
    root_tsx = os.path.join(paths.REMOTION, "src", "Root.tsx")
    for slug, src in films.items():
        if only and slug != only:
            continue
        with open(os.path.join(src, "starter.json")) as f:
            meta = json.load(f)
        code, media = os.path.join(paths.FILMS, slug), os.path.join(paths.PUBLIC_FILMS, slug)
        if os.path.exists(code):
            print(f"  {slug}: already in the project, left as it is")
            continue
        shutil.copytree(os.path.join(src, "src"), code)
        if os.path.isdir(os.path.join(src, "public")):
            shutil.copytree(os.path.join(src, "public"), media, dirs_exist_ok=True)
        added = _register(root_tsx, meta)
        print(f"  {slug}: {meta['title']} (composition {meta['composition']})"
              + ("" if added else f"\n    add it to {paths.rel(root_tsx)} yourself:\n      {meta['import']}\n      {meta['composition_tsx']}"))
    print(f"\nSee it in Build (`{paths.CLI} film status <film>`), or render it: {paths.CLI} film render <film>")


def _register(root_tsx, meta):
    """Add a film's import and composition between Root.tsx's spliced markers. False when there are no markers."""
    try:
        with open(root_tsx, encoding="utf-8") as f:
            s = f.read()
    except OSError:
        return False
    if "// spliced:imports" not in s or "{/* spliced:films */}" not in s:
        return False
    if meta["composition_tsx"] not in s:
        s = s.replace("// spliced:imports", meta["import"] + "\n// spliced:imports", 1)
        s = s.replace("{/* spliced:films */}", "{/* spliced:films */}\n    " + meta["composition_tsx"], 1)
        with open(root_tsx, "w", encoding="utf-8") as f:
            f.write(s)
    return True


def show():
    st = status()
    where = paths.rel(paths.REMOTION)
    if not st["installed"]:
        print(f"No film kit in {where}/ yet. `{paths.CLI} kit install` puts it there: the motion library, its specimens, "
              "the craft and sound docs, and the UI sound kit.")
    else:
        print(f"Film kit {st['version']} in {where}/" + (" (current)" if st["current"] and not st["edited"] else ""))
        if st["stale"] or st["missing"]:
            print(f"  {len(st['stale']) + len(st['missing'])} file(s) differ from this Spliced ({paths.VERSION}): `{paths.CLI} kit update`")
        if st["edited"]:
            print("  changed by hand (update leaves these unless --force):\n    " + "\n    ".join(st["edited"]))
    pk = packages()
    say = {"ok": "installed", "installing": f"being installed (since {pk.get('started')}; {pk.get('log')})",
           "failed": f"the last install failed ({pk.get('log')}): `{paths.CLI} kit packages` tries again",
           "missing": f"not installed: `{paths.CLI} kit packages`", "no-npm": "not installed, and npm isn't on this machine (install Node.js)"}
    if pk["state"] in say:
        print(f"Packages (Remotion, React): {say[pk['state']]}")
    films = starters()
    if films:
        print("Example films: " + ", ".join(films) + f"  (`{paths.CLI} kit starter`)")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else ""
    if cmd in ("-h", "--help", "help"):
        print(__doc__)
    elif not cmd or cmd == "status":
        show()
    elif cmd in ("install", "update"):
        install(force="--force" in a, npm="--no-npm" not in a)
    elif cmd == "packages":
        sys.exit(0 if install_packages(background="--background" in a) else 1)
    elif cmd == "starter":
        starter(next((x for x in a[1:] if not x.startswith("-")), None))
    else:
        sys.exit(f"spliced kit: no subcommand {cmd!r}\n\n{__doc__}")
