"""Spliced's skills in a project: put in, kept current, and never written over a person's own changes.

The copies in a project's .claude/skills/ are Spliced's, and a new version replaces them, the way `kit update`
replaces the film kit. But a person may have changed one. So Spliced remembers what each file held when it put it
there (.claude/skills/.spliced.json), and tells three cases apart:

  unchanged since Spliced put it there   replaced with the new version, silently
  changed by hand                        left alone and said so (--force replaces it, keeping the old one)
  there before Spliced kept a record     replaced when asked to (`agents install`, `setup`), the old one kept;
                                         left alone when nobody asked (a refresh after an update)

Whatever is replaced without being provably Spliced's own goes to .cache/skills-kept/<time>/ first, so nothing a
person wrote is ever lost. Files a person added to a skill's folder are theirs and are never touched.

A project's own rules belong outside the skills anyway: in its AGENTS.md (outside Spliced's section) and in its
profiles (profiles/<slug>/PROFILE.md), which the skills read first.

Needs no project module (the command line calls it before one is loaded), and nothing but the standard library.
"""
import hashlib, json, os, shutil, time

SKILLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")


def _sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def shipped():
    """{"make-film/SKILL.md": <path in Spliced>}: every file of every skill Spliced ships."""
    out = {}
    for name in sorted(os.listdir(SKILLS)) if os.path.isdir(SKILLS) else []:
        root = os.path.join(SKILLS, name)
        if not os.path.isfile(os.path.join(root, "SKILL.md")):
            continue
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for f in files:
                if not f.startswith("."):
                    p = os.path.join(d, f)
                    out[os.path.relpath(p, SKILLS).replace(os.sep, "/")] = p
    return out


def _dir(project):
    return os.path.join(project, ".claude", "skills")


def _record(project):
    try:
        with open(os.path.join(_dir(project), ".spliced.json")) as f:
            d = json.load(f)
        return d.get("files") if isinstance(d.get("files"), dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def files(project):
    """{rel: state} for every shipped file. current | older (ours, a new version is out) | edited (changed by hand) |
    unknown (differs, and there is no record of what Spliced put there) | missing."""
    rec, out = _record(project), {}
    for rel, src in shipped().items():
        dst = os.path.join(_dir(project), rel)
        if not os.path.isfile(dst):
            out[rel] = "missing"
            continue
        have = _sha(dst)
        out[rel] = "current" if have == _sha(src) else "unknown" if rel not in rec else "older" if have == rec[rel] else "edited"
    return out


def status(project):
    """{skill: state}, the worst of its files: missing > unknown > older > edited > current. A skill none of whose
    files are there is "missing"; one a person changed and that is otherwise current is "edited"."""
    order = ["current", "edited", "older", "unknown", "missing"]
    out = {}
    for rel, st in files(project).items():
        name = rel.split("/", 1)[0]
        out[name] = st if name not in out or order.index(st) > order.index(out[name]) else out[name]
    return out


def install(project, force=False, asked=True):
    """Bring the project's skills up to date. Returns [(rel, what)]: what is new | updated | kept (changed by hand) |
    replaced (the old one saved) | left (no record, nobody asked) | current.
    asked=False is the quiet refresh after an update of Spliced: only files that are provably Spliced's own, in skills
    the project already has, are touched."""
    rec, done, saved = dict(_record(project)), [], None
    src_files, states = shipped(), files(project)
    have = {rel.split("/", 1)[0] for rel, st in states.items() if st != "missing"}
    if not asked and not have:   # the project has none of Spliced's skills: nobody asked for them, so none are put there
        return [], None

    def keep(rel):   # a copy of what is about to be replaced, out of the way of every agent
        nonlocal saved
        saved = saved or os.path.join(project, ".cache", "skills-kept", time.strftime("%Y%m%d-%H%M%S"))
        os.makedirs(os.path.dirname(os.path.join(saved, rel)), exist_ok=True)
        shutil.copy2(os.path.join(_dir(project), rel), os.path.join(saved, rel))

    for rel, src in src_files.items():
        st, dst = states[rel], os.path.join(_dir(project), rel)
        if st == "current":
            rec[rel] = _sha(src)   # (a copy from before there was a record: now it has one)
            done.append((rel, "current"))
            continue
        if not asked and rel.split("/", 1)[0] not in have:
            continue
        if not asked and st in ("unknown", "edited"):
            done.append((rel, "left" if st == "unknown" else "kept"))
            continue
        if st == "edited" and not force:
            done.append((rel, "kept"))
            continue
        if st in ("edited", "unknown"):
            keep(rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        rec[rel] = _sha(src)
        done.append((rel, {"missing": "new", "older": "updated"}.get(st, "replaced")))
    for rel in [r for r in rec if r not in src_files]:   # a file Spliced no longer ships: gone if it is still as we left it
        dst = os.path.join(_dir(project), rel)
        if os.path.isfile(dst) and _sha(dst) == rec[rel]:
            os.remove(dst)
        del rec[rel]
    try:
        os.makedirs(_dir(project), exist_ok=True)
        with open(os.path.join(_dir(project), ".spliced.json"), "w") as f:
            json.dump({"_note": "What each of Spliced's skill files held when Spliced put it here, so a file you change is noticed and left alone.",
                       "files": {k: rec[k] for k in sorted(rec)}}, f, indent=1)
            f.write("\n")
    except OSError:
        pass
    return done, (os.path.relpath(saved, project) if saved else None)
