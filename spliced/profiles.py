"""A project's profiles: the looks its films are made in, each one built up over time.

A profile is a folder in the project, profiles/<slug>/:
  profile.json   its name, kind (house: a real company's own; exploration: a look to try), the motion profile its
                 films move by, palette, type, the scenes that define it, and the rules learned while making films
  PROFILE.md     the profile in prose: voice, stage, type, what to do and never do. The person's to write, and the
                 first thing an agent reads before building in it.

One profile may be the default: a board or a scene brief that names none is built in it. Every build can also choose
another profile, or none at all ("as the reference": recreate what the reference shows, in its own look).
A project from before profiles had one brand (spliced.json) and remotion/docs/HOUSE.md: `spliced setup` makes them
its first profile, once, and leaves both files where they were.

  spliced profile                                   the profiles, the default marked
  spliced profile show <profile>                    everything an agent needs to build in it (PROFILE.md, rules, scenes)
  spliced profile new "<name>" [--kind house|exploration] [--motion soft] [--about ".."] [--from-film <slug>] [--default]
                                                    --from-film starts it from a reference film's palette, type and moves
  spliced profile set <profile> [--name ..] [--kind ..] [--motion ..] [--about ..] [--type ..] [--palette "#hex name, #hex name"]
  spliced profile default <profile | none>          what a build uses when it names no profile
  spliced profile learn <profile> "never bounce the logo" [--from "launch-film note 3"]
  spliced profile forget <profile> <n>              take rule n out
  spliced profile pin <profile> <film/sNN>          a scene that shows the look; unpin takes it out
  spliced profile remove <profile>                  kept in .cache/profiles-removed/ first
"""
import argparse, datetime as dt, json, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

DIR = paths.PROFILE_DIR
KINDS = ("house", "exploration")
NONE = "none"   # a build in no profile: as the reference
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
MD_INTRO = ("<!-- This profile in your own words: the voice, the stage, the type, what its films always do and never do. "
            "Your AI reads it before building a film in this profile. -->\n")


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:48].strip("-")


def _dir(slug):
    if not SLUG.match(str(slug or "")):
        raise ValueError(f"{slug!r} isn't a profile (a short kebab-case name)")
    return os.path.join(DIR, slug)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def _save(slug, p):
    keep = {k: p[k] for k in ("name", "kind", "default", "motion", "about", "palette", "type", "scenes", "rules", "from_film", "created", "updated") if k in p}
    keep["default"] = bool(p.get("default"))
    _write(os.path.join(_dir(slug), "profile.json"), json.dumps(keep, indent=1, ensure_ascii=False) + "\n")


def _read(slug):
    try:
        with open(os.path.join(_dir(slug), "profile.json")) as f:
            p = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(p, dict):
        return None
    try:
        with open(os.path.join(_dir(slug), "PROFILE.md")) as f:
            md = f.read()
    except OSError:
        md = ""
    return {"slug": slug, "name": str(p.get("name") or slug), "kind": p.get("kind") if p.get("kind") in KINDS else "exploration",
            "default": bool(p.get("default")), "motion": p.get("motion") if p.get("motion") in paths.PROFILES else paths.DEFAULT_PROFILE,
            "about": str(p.get("about") or ""), "palette": [c for c in (p.get("palette") or []) if isinstance(c, dict) and c.get("hex")],
            "type": str(p.get("type") or ""), "scenes": [str(x) for x in (p.get("scenes") or [])],
            "rules": [r for r in (p.get("rules") or []) if isinstance(r, dict) and r.get("text")], "from_film": p.get("from_film") or "",
            "created": p.get("created") or "", "updated": p.get("updated") or "", "md": md.replace(MD_INTRO, "", 1)}


def every():
    """Every profile, the default first, then by name."""
    if not os.path.isdir(DIR):
        return []
    out = [p for p in (_read(d) for d in sorted(os.listdir(DIR)) if SLUG.match(d)) if p]
    return sorted(out, key=lambda p: (not p["default"], p["name"].lower()))


def get(slug):
    p = _read(slug)
    if not p:
        raise KeyError(f"no profile called {slug!r} (`{paths.CLI} profile` lists them)")
    return p


def default():
    """The default profile's slug, or "" when the project has none."""
    return next((p["slug"] for p in every() if p["default"]), "")


def _palette(v):
    """[{hex, name}] from a list of them, or from text like "#0E3B43 deep teal, #FFB703 amber"."""
    if isinstance(v, list):
        return [{"hex": str(c["hex"]), **({"name": str(c["name"])} if c.get("name") else {})} for c in v if isinstance(c, dict) and c.get("hex")]
    out = []
    for part in str(v or "").split(","):
        m = re.match(r"\s*(#[0-9a-fA-F]{3,8})\s*(.*)", part)
        if m:
            out.append({"hex": m.group(1).upper(), **({"name": m.group(2).strip()} if m.group(2).strip() else {})})
    return out


def _film(slug):
    try:
        with open(os.path.join(paths.REFS, slug, "breakdown.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        raise KeyError(f"no film called {slug!r} in the library")


def create(name, kind="exploration", motion=None, about="", from_film=None, md=None, is_default=False):
    name = str(name or "").strip()
    if not name:
        raise ValueError("a profile needs a name")
    slug = slugify(name)
    if not slug:
        raise ValueError(f"{name!r} can't be a profile's name")
    if os.path.exists(_dir(slug)):
        raise ValueError(f"there is already a profile called {slug!r}")
    if kind not in KINDS:
        raise ValueError(f"kind is {' or '.join(KINDS)}")
    if motion and motion not in paths.PROFILES:
        raise ValueError(f"motion is one of {', '.join(paths.PROFILES)}")
    p = {"name": name, "kind": kind, "motion": motion or paths.DEFAULT_PROFILE, "about": str(about or ""), "palette": [], "type": "",
         "scenes": [], "rules": [], "created": now(), "updated": now()}
    body = md or ""
    if from_film:
        b = _film(from_film)
        sig = b.get("style_signature") or {}
        p.update(from_film=from_film, palette=_palette(sig.get("palette") or []), type=str(sig.get("type") or ""),
                 about=p["about"] or f"Started from {b.get('title', from_film)}{(' (' + b['brand'] + ')') if b.get('brand') else ''}.",
                 scenes=list(dict.fromkeys(f"{from_film}/{sid}" for m in b.get("signature_moves") or [] for sid in m.get("scenes") or []))[:12])
        if not md:
            moves = "".join(f"- **{m.get('name')}**: {m.get('description', '')}\n" for m in b.get("signature_moves") or [])
            body = (f"Started from the reference film {b.get('title', from_film)} (`{from_film}`): its look, to explore in our own films.\n\n"
                    + (f"## Motion\n\n{sig['motion']}\n\n" if sig.get("motion") else "") + (f"## Moves\n\n{moves}\n" if moves else ""))
    _save(slug, p)
    _write(os.path.join(_dir(slug), "PROFILE.md"), MD_INTRO + body)
    if is_default or not default():
        set_default(slug)
    return get(slug)


def update(slug, patch):
    p = get(slug)
    for k in ("name", "about", "type"):
        if k in patch and patch[k] is not None:
            p[k] = str(patch[k]).strip() or (p[k] if k == "name" else "")
    if patch.get("kind") is not None:
        if patch["kind"] not in KINDS:
            raise ValueError(f"kind is {' or '.join(KINDS)}")
        p["kind"] = patch["kind"]
    if patch.get("motion") is not None:
        if patch["motion"] not in paths.PROFILES:
            raise ValueError(f"motion is one of {', '.join(paths.PROFILES)}")
        p["motion"] = patch["motion"]
    if patch.get("palette") is not None:
        p["palette"] = _palette(patch["palette"])
    if patch.get("md") is not None:
        _write(os.path.join(_dir(slug), "PROFILE.md"), MD_INTRO + str(patch["md"]))
    p["updated"] = now()
    _save(slug, p)
    return get(slug)


def set_default(slug):
    """Make one profile the default, or none ("" or "none")."""
    if slug and slug != NONE:
        get(slug)
    for p in every():
        if p["default"] != (p["slug"] == slug):
            p["default"] = p["slug"] == slug
            _save(p["slug"], p)
    return default()


def learn(slug, text, source=""):
    text = " ".join(str(text or "").split())
    if not text:
        raise ValueError("a rule needs some words")
    p = get(slug)
    if any(r["text"].lower() == text.lower() for r in p["rules"]):
        return p
    p["rules"].append({"text": text, **({"from": str(source)} if source else {}), "at": now()})
    p["updated"] = now()
    _save(slug, p)
    return get(slug)


def forget(slug, n):
    p = get(slug)
    n = int(n)
    if not 1 <= n <= len(p["rules"]):
        raise ValueError(f"{slug} has {len(p['rules'])} rules")
    p["rules"].pop(n - 1)
    p["updated"] = now()
    _save(slug, p)
    return get(slug)


def pin(slug, key, on=True):
    p = get(slug)
    key = str(key or "").strip()
    if not re.match(r"^[\w.-]+/[\w.-]+$", key):
        raise ValueError(f"{key!r} isn't a scene (film/sNN)")
    if on and key not in p["scenes"]:
        p["scenes"].append(key)
    elif not on and key in p["scenes"]:
        p["scenes"].remove(key)
    p["updated"] = now()
    _save(slug, p)
    return get(slug)


def remove(slug):
    """Take a profile out; its folder is kept in .cache/profiles-removed/<time>/ first."""
    p = get(slug)
    keep = os.path.join(paths.CACHE, "profiles-removed", dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(keep, exist_ok=True)
    shutil.move(_dir(slug), os.path.join(keep, slug))
    if p["default"]:
        rest = every()
        if rest:
            set_default(rest[0]["slug"])
    return keep


def take_in_house():
    """A project from before profiles: its brand (spliced.json) and remotion/docs/HOUSE.md become its first profile, the
    default. Only when it has no profiles yet and has one of the two; both files stay where they are. Returns the new
    profile, or None when there was nothing to do."""
    if every():
        return None
    house = ""
    if os.path.isfile(paths.HOUSE_MD):
        with open(paths.HOUSE_MD) as f:
            house = f.read()
    if not paths.BRAND and not house.strip():
        return None
    name = paths.BRAND or paths.NAME
    return create(name, kind="house", about=f"{name}'s own look: its brand, type and product.",
                  md=(house if house.strip() else "") + ("" if house.strip() else f"How {name}'s films look and sound.\n"), is_default=True)


def brief(slug):
    """A profile as an agent reads it before building in it: what `spliced profile show` prints."""
    p = get(slug)
    lines = [f"# Profile: {p['name']}", "", f"{'House' if p['kind'] == 'house' else 'Exploration'}{' · the default' if p['default'] else ''} · "
             f"motion profile `{p['motion']}` ({paths.PROFILES.get(p['motion'], '')}) · profiles/{slug}/", ""]
    if p["about"]:
        lines += [p["about"], ""]
    if p["palette"]:
        lines += ["**Palette:** " + ", ".join(f"{c['hex']}{(' (' + c['name'] + ')') if c.get('name') else ''}" for c in p["palette"]), ""]
    if p["type"]:
        lines += [f"**Type:** {p['type']}", ""]
    if p["md"].strip():
        lines += [p["md"].strip(), ""]
    if p["rules"]:
        lines += ["## Rules learned while making films", ""] + [f"{i}. {r['text']}{(' (from ' + r['from'] + ')') if r.get('from') else ''}" for i, r in enumerate(p["rules"], 1)] + [""]
    if p["scenes"]:
        lines += ["## Scenes that show the look", "", "Read each with `" + paths.CLI + " board scene <id>`: " + ", ".join(f"`{k}`" for k in p["scenes"]), ""]
    if p["kind"] == "house":
        lines += [f"A house profile: real logo and UI, rebuilt from the product's own source (spliced.json \"app\"), facts from its sources.", ""]
    return "\n".join(lines).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    x = sub.add_parser("show"); x.add_argument("profile")
    x = sub.add_parser("new"); x.add_argument("name"); x.add_argument("--kind", default="exploration", choices=KINDS); x.add_argument("--motion")
    x.add_argument("--about", default=""); x.add_argument("--from-film"); x.add_argument("--default", action="store_true")
    x = sub.add_parser("set"); x.add_argument("profile")
    for f in ("name", "kind", "motion", "about", "type", "palette"):
        x.add_argument(f"--{f}")
    x = sub.add_parser("default"); x.add_argument("profile")
    x = sub.add_parser("learn"); x.add_argument("profile"); x.add_argument("rule"); x.add_argument("--from", dest="source", default="")
    x = sub.add_parser("forget"); x.add_argument("profile"); x.add_argument("n", type=int)
    for name in ("pin", "unpin"):
        x = sub.add_parser(name); x.add_argument("profile"); x.add_argument("scene")
    x = sub.add_parser("remove"); x.add_argument("profile")
    sub.add_parser("setup", help="spliced setup's step: a project from before profiles gets its first one")
    a = ap.parse_args()
    try:
        if a.cmd in (None, "list"):
            ps = every()
            if not ps:
                print(f"No profiles yet. Make one: {paths.CLI} profile new \"<name>\" [--kind house] (or in the app: Profiles)")
                return
            for p in ps:
                print(f"{'*' if p['default'] else ' '} {p['slug']:24} {p['name']:28} {p['kind']:12} motion {p['motion']:9} {len(p['rules'])} rules")
            print(f"\n* the default: a build that names no profile is made in it. `{paths.CLI} profile show <profile>` before building in one.")
        elif a.cmd == "show":
            print(brief(a.profile), end="")
        elif a.cmd == "new":
            p = create(a.name, a.kind, a.motion, a.about, a.from_film, is_default=a.default)
            print(f"Made the profile {p['slug']} ({p['kind']}){', the default' if p['default'] else ''}: profiles/{p['slug']}/PROFILE.md is its text.")
        elif a.cmd == "set":
            p = update(a.profile, {k: getattr(a, k) for k in ("name", "kind", "motion", "about", "type", "palette")})
            print(f"{p['slug']}: saved")
        elif a.cmd == "default":
            d = set_default("" if a.profile == NONE else a.profile)
            print(f"The default profile is {d}" if d else "No default profile: a build that names none recreates the reference as it is")
        elif a.cmd == "learn":
            p = learn(a.profile, a.rule, a.source)
            print(f"{p['slug']}: {len(p['rules'])} rules")
        elif a.cmd == "forget":
            p = forget(a.profile, a.n)
            print(f"{p['slug']}: {len(p['rules'])} rules")
        elif a.cmd in ("pin", "unpin"):
            p = pin(a.profile, a.scene, a.cmd == "pin")
            print(f"{p['slug']}: {len(p['scenes'])} scenes")
        elif a.cmd == "setup":
            p = take_in_house()
            print(f"Your house rules are now the profile {p['name']} (profiles/{p['slug']}/), the default. Profiles holds it, and any other looks you make."
                  if p else f"{len(every())} profile{'' if len(every()) == 1 else 's'}" if every() else "No profiles yet: make one in the app (Profiles) when you want a house look.")
        elif a.cmd == "remove":
            print(f"Removed; kept in {os.path.relpath(remove(a.profile), paths.ROOT)}")
    except (KeyError, ValueError) as e:
        sys.exit(str(e.args[0]) if e.args else str(e))


if __name__ == "__main__":
    main()
