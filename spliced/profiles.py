"""A project's profiles: the looks its films are made in, each one built up over time.

A profile is a folder in the project, profiles/<slug>/:
  profile.json   its name, palette, typefaces (headlines and text, each from this Mac or Google Fonts), motion, the
                 scenes that show the look, the rules learned while making films
  PROFILE.md     the profile in prose: voice, stage, type, what to do and never do. The person's to write, and the
                 first thing an agent reads before building in it.
  sources/       what a profile was drafted from, when the person dropped a brand book, logo, screenshots, a film or a
                 website on it: the person's AI reads them and fills the profile in (an import job, importer.py, type
                 "profile"). A website is read by Spliced first (website.py): <site>.site.md and its pictures

One profile may be the default: a brief starts in it. Every brief can choose another, or none ("as the reference":
recreate what the reference shows, in its own look).

Motion is a base (one of the project's motion profiles: the kit's soft, material, apple, splice, or its own) and
what this look changes about it: pace (how long every move takes, against the base), bounce, stagger, how scenes
change, how words arrive, and whether things float while held. Each is optional: unset follows the base. They are
the fields of the film kit's Profile (remotion/src/lib/motion/spec.ts), so an agent builds the film's motion profile
from them in remotion/src/profiles.ts.

One store per project: in a git worktree (a Conductor workspace, `git worktree add`) the profiles are the main
checkout's (paths.profile_dir, spliced.json "worktree_profiles"), so every worktree and the app see the same ones and
an edit made from a worktree lands there. A profile a worktree made in its own profiles/ before that is still listed,
marked local, and never written over; `spliced profile move-home <profile>` moves it to the main checkout.

A project from before profiles had one brand (spliced.json) and remotion/docs/HOUSE.md: `spliced setup` makes them
its first profile, once, and leaves both files where they were.

  spliced profile                                   the profiles, the default marked
  spliced profile show <profile>                    everything an agent needs to build in it (words, motion, rules, scenes)
  spliced profile new "<name>" [--motion soft] [--about ".."] [--from-film <slug>] [--default]
                                                    --from-film starts it from a reference film's palette, type and moves
  spliced profile set <profile> [--name ..] [--about ..] [--font ..] [--font-source local|google] [--text-font ..]
                      [--text-font-source local|google] [--type ..] [--palette "#hex name, #hex name"]
  spliced profile motion <profile> [--base soft] [--pace 1.2] [--bounce 0.15] [--stagger 0.08]
                         [--transition "blur, whip"] [--text "sharpen, typewriter"] [--idle 0.4]
                                                    scene changes and word styles: as many as fit, the first leading
                                                    "base" for any of them goes back to the base's own
  spliced profile motion <profile> --from <motion>  start again from a kit motion profile or a saved motion (spliced profile motions)
  spliced profile motions                           the motions to start from: the kit's, the project's, and the ones saved here
  spliced profile save-motion <profile> "<name>"    keep this profile's motion as a starting point for others
  spliced profile draft <profile | "New name"> <file | website>...   copy a brand book, logo, screenshots or a film into
                                                    its sources/, read a website into them (its colours, type, motion,
                                                    screenshots), and have the person's AI fill the profile in from them
  spliced profile ask <profile> "<what to change>"  the person's request, for their AI to make in the profile
  spliced profile drafted <profile>                 the agent that drafted or changed it says it is done
  spliced profile default <profile | none>          the profile a brief starts in
  spliced profile learn <profile> "never bounce the logo" [--from "launch-film note 3"]
  spliced profile forget <profile> <n>              take rule n out
  spliced profile pin <profile> <film/sNN>          a scene that shows the look; unpin takes it out
  spliced profile remove <profile>                  kept in .cache/profiles-removed/ first
  spliced profile move-home <profile>               a profile kept in this worktree's own profiles/ goes to the main checkout's
"""
import argparse, datetime as dt, json, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

LOCAL = paths.PROFILE_DIR   # this folder's own profiles/: the store, except in a worktree (store())
NONE = "none"   # a build in no profile: as the reference
FONT_SOURCES = ("local", "google")
SOURCE_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", ".mov", ".m4v", ".webm", ".txt", ".md", ".key", ".pptx"}
SOURCE_MAX = 400 * 1024 * 1024
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
MD_INTRO = ("<!-- This profile in your own words: the voice, the stage, the type, what its films always do and never do. "
            "Your AI reads it before building a film in this profile. -->\n")

# What a look may change about its base motion profile: (allowed values or a number range, what it means).
# Numbers: pace multiplies every move's length (1 = the base's); bounce is a spring's overshoot (0 = none);
# stagger is the seconds between grouped items; idle is how much held things float (0 = still).
MOTION = {
    "pace": ((0.5, 2.0), "how long every move takes, against the base (1 = the base's, 1.3 = slower, 0.8 = brisker)"),
    "bounce": ((0.0, 0.5), "overshoot on UI and emphasis (0 = none, 0.15 = a little, 0.3 = playful)"),
    "stagger": ((0.0, 0.3), "seconds between grouped items: words, cards, rows"),
    "transition": (None, "how one scene becomes the next: as many as fit the look, the first leading"),
    "text": (None, "how words arrive: as many as fit the look, the first leading"),
    "idle": ((0.0, 1.0), "how much held things float (0 = still)"),
}
# The kit's own motion profiles as the app shows them (remotion/src/lib/motion/profile.tsx): the base values a
# look changes, and the curve and length of an entrance, for the app's preview. A project's own profiles have no row
# here; they are previewed with the soft row's values.
KIT_MOTION = {
    "soft": {"pace": 1, "bounce": 0, "stagger": 0.1, "transition": ["cut"], "text": ["sharpen"], "idle": 1, "curve": [0.2, 0.8, 0.2, 1], "enter": 0.6},
    "material": {"pace": 1, "bounce": 0.1, "stagger": 0.05, "transition": ["push-in"], "text": ["sharpen"], "idle": 0, "curve": [0.05, 0.7, 0.1, 1], "enter": 0.8},
    "apple": {"pace": 1, "bounce": 0.15, "stagger": 0.06, "transition": ["slide"], "text": ["sharpen"], "idle": 0.6, "curve": [0.25, 0.9, 0.3, 1], "enter": 0.6},
    "splice": {"pace": 1, "bounce": 0, "stagger": 0.07, "transition": ["blur"], "text": ["sharpen"], "idle": 0.3, "curve": [0.16, 1, 0.3, 1], "enter": 0.75},
}
# The scene changes and word styles a look may use, each: (what it is, the kit's own helper for it or None, the library's tag).
# The kit's viewChange kinds (remotion/src/lib/motion/spec.ts) cover the first few; the rest an agent builds in the film's
# code, looking at the library's scenes with the same tag (library/TAXONOMY.md) for how others did it.
TRANSITIONS = {
    "cut": ("a straight cut", "viewChange cut", "hard-cut"),
    "cut-on-beat": ("a cut on the music's beat", "viewChange cut, placed on the beat grid", "cut-on-beat"),
    "match-cut": ("a match cut: the next shot shares a shape, place or motion with the last", None, "match-cut"),
    "blur": ("blur out of one scene and sharpen into the next", "viewChange blurThrough", "blur-dissolve"),
    "fade": ("a fade through", "viewChange fadeThrough", "crossfade"),
    "dip": ("a dip through a colour of the palette", None, "dip-to-colour"),
    "slide": ("the next scene slides in along the x axis", "viewChange sharedAxisX", "push-slide"),
    "push-in": ("push in: the old scene grows and fades, the new one settles in", "viewChange sharedAxisZ", "zoom-through"),
    "whip": ("a whip pan: a fast blurred move into the next scene", None, "whip-pan"),
    "wipe": ("a shape or line wipes the next scene on", None, "mask-wipe"),
    "colour-wipe": ("a flat colour sweeps across and carries the cut", None, "colour-wipe"),
    "iris": ("an iris: a circle closes on one scene and opens the next", None, "iris"),
    "morph": ("an element of one scene becomes the next", "the kit's container transform (MOTION-SYSTEMS.md)", "morph-transition"),
    "carry": ("an element stays while the world changes around it", None, "shared-element-carry"),
    "pull-out": ("the old scene shrinks into a frame in the new one", None, "pull-out-transition"),
    "one-move": ("one unbroken camera move, the cuts hidden in it", None, "continuous-move"),
}
TEXT_STYLES = {
    "sharpen": ("words sharpen in from a blur", "text.style sharpen", "blur-in"),
    "grey-to-ink": ("words land light grey, then darken", "text.style greyToInk", "word-by-word"),
    "word-by-word": ("a word at a time, rising", "m.textReveal", "word-by-word"),
    "typewriter": ("typed letter by letter", None, "typewriter"),
    "mask-reveal": ("lines wipe up out of a mask", None, "mask-reveal"),
    "highlight": ("a line lights up word by word, as if read aloud", None, "type-highlight-sweep"),
    "kinetic": ("type moves big: scale, tracking, slides", None, "kinetic-type"),
    "slot-reel": ("a word spins through options and lands", None, "slot-reel"),
    "scramble": ("letters scramble, then resolve", None, "scramble-type"),
    "swap": ("one word in a line swaps in place", None, "inline-swap"),
    "fly-past": ("type scales past the lens", None, "fly-past"),
}
LISTS = {"transition": TRANSITIONS, "text": TEXT_STYLES}
OLD = {"blurThrough": "blur", "fadeThrough": "fade", "sharedAxisX": "slide", "sharedAxisZ": "push-in", "greyToInk": "grey-to-ink"}   # names before lists


def _styles(k, v):
    """A list field's value as a clean list: from a list, one name, or "a, b"; old names read as their new ones."""
    items = v if isinstance(v, list) else str(v or "").split(",")
    out = []
    for x in items:
        x = OLD.get(str(x).strip(), str(x).strip())
        if x in LISTS[k] and x not in out:
            out.append(x)
    return out


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:48].strip("-")


def store():
    """Where profiles are kept: this project's profiles/, or in a git worktree the main checkout's (paths.profile_dir)."""
    return paths.profile_dir()


def motions_file():
    """Motions saved as starting points: {slug: {name, base, pace?, ...}}, beside the profiles."""
    return os.path.join(store(), "motions.json")


def _local_only(slug):
    """A profile this worktree made in its own profiles/ (before profiles went home) that the store has no namesake of."""
    return (store() != LOCAL and os.path.isfile(os.path.join(LOCAL, slug, "profile.json"))
            and not os.path.isdir(os.path.join(store(), slug)))


def _dir(slug):
    if not SLUG.match(str(slug or "")):
        raise ValueError(f"{slug!r} isn't a profile (a short kebab-case name)")
    return os.path.join(LOCAL, slug) if _local_only(slug) else os.path.join(store(), slug)


def shown(path):
    """A path as a person or agent is told it: project-relative, or in full when it is in the main checkout."""
    return path if paths.rel(path).startswith(paths.MAIN_PREFIX) else paths.rel(path)


def where(slug):
    """A profile's folder as an agent is told it (shown)."""
    return shown(_dir(slug))


def agent_path(relpath):
    """A path Spliced wrote down (paths.rel) as an agent can open it: "@main/..." becomes the full path."""
    return paths.abspath(relpath) if str(relpath).startswith(paths.MAIN_PREFIX) else relpath


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def _motion(v):
    """A stored motion as {base, and only the fields it changes}. An old profile's motion was just a base's name."""
    v = {"base": v} if isinstance(v, str) else v if isinstance(v, dict) else {}
    out = {"base": v.get("base") if v.get("base") in paths.PROFILES else paths.DEFAULT_PROFILE}
    if isinstance(v.get("from"), str) and SLUG.match(v["from"]):
        out["from"] = v["from"]   # the motion it started from (a kit one or a saved one), so the app can say "edited" and reset
    for k, (allowed, _) in MOTION.items():
        x = v.get(k)
        if x is None:
            continue
        if k in LISTS:
            if _styles(k, x):
                out[k] = _styles(k, x)
        else:
            try:
                out[k] = round(min(allowed[1], max(allowed[0], float(x))), 3)
            except (TypeError, ValueError):
                pass
    return out


def _save(slug, p):
    keep = {k: p[k] for k in ("name", "about", "palette", "font", "font_source", "text_font", "text_font_source", "type", "motion", "scenes", "rules",
                              "from_film", "drafted", "created", "updated") if k in p}
    keep["default"] = bool(p.get("default"))
    keep["motion"] = _motion(p.get("motion"))
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
    return {"slug": slug, "name": str(p.get("name") or slug), "default": bool(p.get("default")), "about": str(p.get("about") or ""),
            "palette": _palette(p.get("palette") or []), "font": str(p.get("font") or ""), "type": str(p.get("type") or ""),
            "font_source": p.get("font_source") if p.get("font_source") in FONT_SOURCES else "",
            "text_font": str(p.get("text_font") or ""), "text_font_source": p.get("text_font_source") if p.get("text_font_source") in FONT_SOURCES else "",
            "sources": sources(slug), "drafted": p.get("drafted") or "",
            "motion": _motion(p.get("motion")), "scenes": [str(x) for x in (p.get("scenes") or [])],
            "rules": [r for r in (p.get("rules") or []) if isinstance(r, dict) and r.get("text")], "from_film": p.get("from_film") or "",
            "created": p.get("created") or "", "updated": p.get("updated") or "", "md": md.replace(MD_INTRO, "", 1),
            "local": _local_only(slug),   # kept in this worktree's own profiles/, not the project's store
            "found": {"palette": colours_in(md)}}   # what its words name, for the app to offer in one click


def _slugs(d):
    return sorted(x for x in os.listdir(d) if SLUG.match(x)) if os.path.isdir(d) else []


def every():
    """Every profile, the default first, then by name: the store's, and any this worktree keeps in its own profiles/."""
    names = _slugs(store()) + [x for x in _slugs(LOCAL) if store() != LOCAL and _local_only(x)]
    out = [p for p in (_read(d) for d in names) if p]
    return sorted(out, key=lambda p: (not p["default"], p["local"], p["name"].lower()))


def shadowed():
    """Profiles this worktree keeps in its own profiles/ that the store has one of the same name: not used, never removed."""
    if store() == LOCAL:
        return []
    return [x for x in _slugs(LOCAL) if os.path.isfile(os.path.join(LOCAL, x, "profile.json")) and os.path.isdir(os.path.join(store(), x))]


def move_home(slug):
    """Move a profile this worktree keeps in its own profiles/ into the store (the main checkout's). Refuses when the
    store has one of that name; nothing is written over. Returns the new folder."""
    if store() == LOCAL:
        raise ValueError("this project keeps its profiles here: there is nowhere else to move one")
    if not SLUG.match(str(slug or "")) or not os.path.isfile(os.path.join(LOCAL, slug, "profile.json")):
        raise KeyError(f"this worktree keeps no profile called {slug!r} in its own profiles/")
    home = os.path.join(store(), slug)
    if os.path.exists(home):
        raise ValueError(f"the main checkout already has a profile called {slug!r}, so both are kept as they are: rename this "
                         f"worktree's folder (profiles/{slug}) and move that, or copy what you need across by hand")
    was_default = default()
    os.makedirs(store(), exist_ok=True)
    shutil.copytree(os.path.join(LOCAL, slug), home)
    p = _read(slug)
    if p and p["default"] and was_default and was_default != slug:   # the store's default stays the default
        p["default"] = False
        _save(slug, p)
    shutil.rmtree(os.path.join(LOCAL, slug))
    return home


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
        return [{"hex": str(c["hex"]).upper(), **({"name": str(c["name"])} if c.get("name") else {})} for c in v
                if isinstance(c, dict) and re.fullmatch(r"#[0-9a-fA-F]{3,8}", str(c.get("hex", "")))]
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


def create(name, motion=None, about="", from_film=None, md=None, is_default=False):
    name = str(name or "").strip()
    if not name:
        raise ValueError("a profile needs a name")
    slug = slugify(name)
    if not slug:
        raise ValueError(f"{name!r} can't be a profile's name")
    if os.path.exists(_dir(slug)):
        raise ValueError(f"there is already a profile called {slug!r}")
    if motion and motion not in paths.PROFILES:
        raise ValueError(f"motion is one of {', '.join(paths.PROFILES)}")
    p = {"name": name, "motion": {"base": motion or paths.DEFAULT_PROFILE}, "about": str(about or ""), "palette": [], "font": "", "type": "",
         "scenes": [], "rules": [], "created": now(), "updated": now()}
    body = md or ""
    if from_film:
        b = _film(from_film)
        sig = b.get("style_signature") or {}
        p.update(from_film=from_film, palette=_palette(sig.get("palette") or []), type=str(sig.get("type") or ""),
                 about=p["about"] or f"Started from {b.get('title', from_film)}{(' (' + b['brand'] + ')') if b.get('brand') else ''}.",
                 scenes=list(dict.fromkeys(f"{from_film}/{sid}" for m in b.get("signature_moves") or [] for sid in m.get("scenes") or []))[:12])
        if (b.get("tempo") or {}).get("avg_shot_s"):
            p["motion"]["pace"] = 1.3 if b["tempo"]["avg_shot_s"] > 3.5 else 0.8 if b["tempo"]["avg_shot_s"] < 1.5 else 1
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
    for k in ("name", "about", "font", "type", "text_font"):
        if k in patch and patch[k] is not None:
            p[k] = str(patch[k]).strip() or (p[k] if k == "name" else "")
    for k in ("font_source", "text_font_source"):
        if patch.get(k) is not None:
            if patch[k] not in ("", *FONT_SOURCES):
                raise ValueError(f"{k} is local or google")
            p[k] = patch[k]
    if patch.get("palette") is not None:
        p["palette"] = _palette(patch["palette"])
    if patch.get("md") is not None:
        _write(os.path.join(_dir(slug), "PROFILE.md"), MD_INTRO + str(patch["md"]))
    if isinstance(patch.get("motion"), dict):
        set_motion(slug, patch["motion"], p)
    p["updated"] = now()
    _save(slug, p)
    return get(slug)


def set_motion(slug, changes, p=None):
    """Change a profile's motion: {base?, pace?, bounce?, ...}; a value of None or "base" goes back to the base's own."""
    own = p is not None
    p = p or get(slug)
    m = dict(p["motion"])
    if changes.get("from"):
        start = motion_start(changes["from"])
        m = {"base": start["base"], "from": changes["from"], **{k: start[k] for k in MOTION if k in start}}
        changes = {k: v for k, v in changes.items() if k != "from"}
    for k, v in changes.items():
        if k == "base":
            if v not in paths.PROFILES:
                raise ValueError(f"the base is one of {', '.join(paths.PROFILES)}")
            m["base"] = v
            m.pop("from", None)
        elif k in MOTION:
            if v is None or v == "base" or v == "":
                m.pop(k, None)
                continue
            allowed = MOTION[k][0]
            if k in LISTS:
                names = [OLD.get(x.strip(), x.strip()) for x in (v if isinstance(v, list) else str(v).split(",")) if str(x).strip()]
                bad = [x for x in names if x not in LISTS[k]]
                if bad or not names:
                    raise ValueError(f"{k} takes one or more of {', '.join(LISTS[k])}" + (f"; not {', '.join(bad)}" if bad else ""))
                m[k] = _styles(k, names)
            else:
                try:
                    x = float(v)
                except (TypeError, ValueError):
                    raise ValueError(f"{k} is a number from {allowed[0]} to {allowed[1]}")
                if not allowed[0] <= x <= allowed[1]:
                    raise ValueError(f"{k} is a number from {allowed[0]} to {allowed[1]}")
                m[k] = x
        else:
            raise ValueError(f"motion has base, {', '.join(MOTION)}; not {k!r}")
    p["motion"] = m
    if not own:
        p["updated"] = now()
        _save(slug, p)
        return get(slug)
    return p


def saved_motions():
    try:
        with open(motions_file()) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k: {"name": str(v.get("name") or k), **_motion(v)} for k, v in (d.items() if isinstance(d, dict) else []) if SLUG.match(k) and isinstance(v, dict)}


def motions():
    """Every motion a profile can start from: the kit's and the project's motion profiles, then the ones saved here."""
    out = [{"slug": k, "name": k, "about": v, "kind": "kit" if k in KIT_MOTION else "project", "base": k} for k, v in paths.PROFILES.items()]
    return out + [{"slug": k, "kind": "saved", "about": "", **v} for k, v in saved_motions().items()]


def motion_start(name):
    if name in paths.PROFILES:
        return {"base": name}
    m = saved_motions().get(name)
    if not m:
        raise ValueError(f"no motion called {name!r} (`{paths.CLI} profile motions` lists them)")
    return m


def save_motion(slug, name):
    """Keep a profile's motion as a starting point any profile can begin from."""
    p = get(slug)
    name = str(name or "").strip()
    key = slugify(name)
    if not key or key in paths.PROFILES:
        raise ValueError(f"{name!r} can't be a motion's name" + (" (the kit has one called that)" if key in paths.PROFILES else ""))
    d = saved_motions()
    d[key] = {"name": name, **{k: v for k, v in p["motion"].items() if k != "from"}}
    _write(motions_file(), json.dumps(d, indent=1, ensure_ascii=False) + "\n")
    return key


def remove_motion(key):
    d = saved_motions()
    if key not in d:
        raise ValueError(f"no saved motion called {key!r}")
    del d[key]
    _write(motions_file(), json.dumps(d, indent=1, ensure_ascii=False) + "\n")


SITE = ".site.md"   # a website Spliced read for a profile: <site>.site.md, its pictures beside it as "<site> logo.svg" ...
SITE_FILES = ("logo", "icon", "share", "first screen", "page")


def sources(slug):
    """What a profile was drafted from: [{file, name, kind, bytes}], project-relative paths. A website's read is kind "site"."""
    d = os.path.join(_dir(slug), "sources")
    if not os.path.isdir(d):
        return []
    kind = lambda n, e: "site" if n.endswith(SITE) else "video" if e in (".mp4", ".mov", ".m4v", ".webm") else \
        "image" if e in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg") else "document"
    return [{"file": paths.rel(os.path.join(d, n)), "name": n, "kind": kind(n, os.path.splitext(n)[1].lower()), "bytes": os.path.getsize(os.path.join(d, n))}
            for n in sorted(os.listdir(d)) if not n.startswith(".") and os.path.isfile(os.path.join(d, n))]


def is_site(arg):
    """Whether something given to `profile draft` is a web address rather than a file: http(s)://, or a bare
    acme.com/about that is no file here."""
    arg = str(arg or "").strip()
    if re.match(r"^https?://", arg, re.I):
        return True
    if os.path.exists(os.path.expanduser(arg)) or os.path.splitext(arg.split("/")[0])[1].lower() in SOURCE_EXT:
        return False   # brand-book.pdf is a file, even where .pdf could be a domain
    return bool(re.match(r"^(([\w-]+\.)+[a-z]{2,}|localhost|\d{1,3}(\.\d{1,3}){3})(:\d+)?([/?#]\S*)?$", arg, re.I))   # acme.com, localhost:3000


def add_site(slug, url, progress=None):
    """Read a website into a profile's sources/ (website.py): <site>.site.md, what its page is made of, with its
    logo, icon, share picture and screenshots beside it. A site read again replaces its last read. Returns
    {site, url, files}; a ValueError in a sentence when the page can't be read."""
    get(slug)
    import website
    r = website.read(url, progress)
    d = os.path.join(_dir(slug), "sources")
    label = r["label"]
    if os.path.isdir(d):   # the last read of this site goes, only the files Spliced named for it
        for n in os.listdir(d):
            stem, ext = os.path.splitext(n)
            if n == label + SITE or (ext.lower() in {*website.IMAGE_EXT.values(), ".jpeg"} and stem in {f"{label} {w}" for w in SITE_FILES}):
                os.remove(os.path.join(d, n))
    saved = {what: add_source(slug, name, data) for what, name, data in r["files"]}
    md = add_source(slug, label + SITE, website.markdown(r, saved).encode())
    return {"site": label, "url": r["final"], "files": [md, *saved.values()]}


def add_source(slug, name, data):
    """Keep one file a profile is drafted from in its sources/: a safe name, a kind Spliced knows, never over another."""
    get(slug)
    base, ext = os.path.splitext(os.path.basename(str(name or "")))
    ext = ext.lower()
    if ext not in SOURCE_EXT:
        raise ValueError(f"{ext or 'a file with no extension'} can't be a profile's source: a PDF, an image, a film, a deck or text")
    if len(data) > SOURCE_MAX:
        raise ValueError("that file is too big (under 400 MB, please)")
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "", base).strip(" .")[:80] or "source"
    d = os.path.join(_dir(slug), "sources")
    os.makedirs(d, exist_ok=True)
    out, n = os.path.join(d, stem + ext), 2
    while os.path.exists(out):
        out, n = os.path.join(d, f"{stem} {n}{ext}"), n + 1
    with open(out, "wb") as f:
        f.write(data)
    return paths.rel(out)


def draft(slug, request=""):
    """Have the person's AI fill the profile in from its sources and its words, or make a change they asked for: an
    import job (importer.py), so it is worked like a film's breakdown (in the background, or by their own AI)."""
    p = get(slug)
    request = " ".join(str(request or "").split())
    if not (p["sources"] or p["md"].strip() or request):
        raise ValueError(f"{slug} has nothing to draft from: drop a brand book, logo, screenshots, a film or a website on it, or say what it should be")
    import importer
    return importer.add_profile_job(slug, request)


def colours_in(text):
    """The colours a text names, as a palette: every hex code, named by the word just before it ("ink `#0B152B`")."""
    out, seen = [], set()
    for m in re.finditer(r"([A-Za-z][\w-]{1,24})?[\s:=(`'\"]*(#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b)", text or ""):
        hx = m.group(2).upper()
        if hx in seen:
            continue
        seen.add(hx)
        name = (m.group(1) or "").strip("-")
        out.append({"hex": hx, **({"name": name} if name and name.lower() not in ("the", "and", "or", "on", "is", "a", "to", "sampled", "of") else {})})
    return out[:8]


def mark_drafted(slug):
    p = get(slug)
    p["drafted"] = now()
    p["updated"] = now()
    _save(slug, p)
    return get(slug)


_FONTS = [0.0, []]


def installed_fonts():
    """The font families on this machine (macOS: what Font Book has; Linux: fontconfig), asked once an hour at most."""
    import subprocess, time
    if _FONTS[1] and time.time() - _FONTS[0] < 3600:
        return _FONTS[1]
    out = []
    try:
        if sys.platform == "darwin":
            r = subprocess.run(["osascript", "-l", "JavaScript", "-e",
                                'ObjC.import("AppKit"); JSON.stringify($.NSFontManager.sharedFontManager.availableFontFamilies.js.map(x => x.js))'],
                               capture_output=True, text=True, timeout=20)
            out = json.loads(r.stdout or "[]")
        elif shutil.which("fc-list"):
            r = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=20)
            out = [ln.split(",")[0].strip() for ln in r.stdout.splitlines() if ln.strip()]
    except (OSError, ValueError, subprocess.SubprocessError):
        out = []
    fams = sorted({f for f in out if f and not f.startswith(".")}, key=str.lower)
    _FONTS[:] = [time.time(), fams]
    return fams


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
    home = paths.ROOT if p["local"] else paths.profile_home()   # kept beside the store it came from
    keep = os.path.join(home, ".cache", "profiles-removed", dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
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
    p = create(name, about=f"{name}'s own look: its brand, type and product.",
               md=house if house.strip() else f"How {name}'s films look and sound.\n", is_default=True)
    if colours_in(house):   # the colours its house rules name are its palette from the start
        p = update(p["slug"], {"palette": colours_in(house)})
    return p


def motion_lines(m):
    """A profile's motion as an agent builds it: the base, then each thing the look changes."""
    base = m["base"]
    out = [f"Base: `{base}` ({paths.PROFILES.get(base, '')})."]
    changed = [k for k in MOTION if k in m]
    if not changed:
        return out + ["Nothing changed from the base: build with motion('" + base + "')."]
    for k in changed:
        v = m[k]
        if k in LISTS:
            label = {"transition": "scene changes", "text": "words"}[k]
            out.append(f"- {label} ({MOTION[k][1]}):")
            for i, x in enumerate(v):
                what, kit, tag = LISTS[k][x]
                out.append(f"  - {x}{' (leads)' if i == 0 and len(v) > 1 else ''}: {what}; " + (f"in the kit: {kit}" if kit else f"no kit helper: build it in the film, and see the library's `{tag}` scenes"))
        else:
            out.append(f"- {k}: {v} ({MOTION[k][1]})")
    out.append(f"Build it as a motion profile named after this profile in remotion/src/profiles.ts: start from `{base}`'s roles, "
               "scale every role's seconds by pace, give UI and emphasis springs the bounce, set stagger and idle as above, and "
               "viewChange.kind and text.style from the first scene change and word style the kit has a helper for. Use the others "
               "where a beat calls for them, so the film varies inside the look. Then use it with motion('<that name>').")
    return out


def brief(slug):
    """A profile as an agent reads it before building in it: what `spliced profile show` prints."""
    p = get(slug)
    home = where(slug)
    lines = [f"# Profile: {p['name']}", "", f"{home}/{' · the default' if p['default'] else ''}"
             + (" · kept in this worktree only (`" + paths.CLI + f" profile move-home {slug}` moves it to the main checkout)" if p["local"]
                else " · the main checkout's: every worktree shares it, and edits land there" if os.path.isabs(home) else ""), ""]
    if p["about"]:
        lines += [p["about"], ""]
    if p["palette"]:
        lines += ["**Palette:** " + ", ".join(f"{c['hex']}{(' (' + c['name'] + ')') if c.get('name') else ''}" for c in p["palette"]), ""]
    face = lambda f, src: f"{f} ({'Google Fonts: load it with @remotion/google-fonts' if src == 'google' else 'installed on this Mac'})" if f else ""
    if p["font"] or p["text_font"] or p["type"]:
        lines += ["**Type:** " + "; ".join(x for x in (p["font"] and f"headlines in {face(p['font'], p['font_source'])}",
                                                         p["text_font"] and f"text in {face(p['text_font'], p['text_font_source'])}", p["type"]) if x), ""]
    lines += ["## Motion", "", *motion_lines(p["motion"]), ""]
    if p["md"].strip():
        lines += [p["md"].strip(), ""]
    if p["rules"]:
        lines += ["## Rules learned while making films", ""] + [f"{i}. {r['text']}{(' (from ' + r['from'] + ')') if r.get('from') else ''}" for i, r in enumerate(p["rules"], 1)] + [""]
    if p["sources"]:
        lines += ["## What it was drafted from", "", ", ".join(f"`{agent_path(x['file'])}`" for x in p["sources"]), ""]
    if p["scenes"]:
        lines += ["## Scenes that show the look", "", "Read each with `" + paths.CLI + " board scene <id>`: " + ", ".join(f"`{k}`" for k in p["scenes"]), ""]
    return "\n".join(lines).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    x = sub.add_parser("show"); x.add_argument("profile")
    x = sub.add_parser("new"); x.add_argument("name"); x.add_argument("--motion")
    x.add_argument("--about", default=""); x.add_argument("--from-film"); x.add_argument("--default", action="store_true")
    x = sub.add_parser("set"); x.add_argument("profile")
    for f in ("name", "about", "font", "font-source", "text-font", "text-font-source", "type", "palette"):
        x.add_argument(f"--{f}")
    x = sub.add_parser("motion"); x.add_argument("profile"); x.add_argument("--base"); x.add_argument("--from", dest="start")
    for f in MOTION:
        x.add_argument(f"--{f}")
    sub.add_parser("motions")
    x = sub.add_parser("save-motion"); x.add_argument("profile"); x.add_argument("name")
    x = sub.add_parser("draft"); x.add_argument("profile"); x.add_argument("files", nargs="+", help="files, or websites (acme.com)")
    x = sub.add_parser("drafted"); x.add_argument("profile")
    x = sub.add_parser("ask"); x.add_argument("profile"); x.add_argument("request")
    x = sub.add_parser("default"); x.add_argument("profile")
    x = sub.add_parser("learn"); x.add_argument("profile"); x.add_argument("rule"); x.add_argument("--from", dest="source", default="")
    x = sub.add_parser("forget"); x.add_argument("profile"); x.add_argument("n", type=int)
    for name in ("pin", "unpin"):
        x = sub.add_parser(name); x.add_argument("profile"); x.add_argument("scene")
    x = sub.add_parser("remove"); x.add_argument("profile")
    x = sub.add_parser("move-home"); x.add_argument("profile")
    sub.add_parser("setup", help="spliced setup's step: a project from before profiles gets its first one")
    a = ap.parse_args()
    try:
        if a.cmd in (None, "list"):
            ps = every()
            if not ps:
                print(f"No profiles yet. Make one: {paths.CLI} profile new \"<name>\" (or in the app: Profiles)")
                return
            for p in ps:
                print(f"{'*' if p['default'] else ' '} {p['slug']:24} {p['name']:28} motion {p['motion']['base']:9} {len(p['rules'])} rules  {len(p['scenes'])} scenes"
                      + ("  (local: this worktree only)" if p["local"] else ""))
            print(f"\n* the default: a brief starts in it. `{paths.CLI} profile show <profile>` before building in one.")
            if store() != LOCAL:
                print(f"Profiles live in the main checkout ({store()}): every worktree shares them, and edits land there.")
            if any(p["local"] for p in ps):
                print(f"A local one was made in this worktree before that: `{paths.CLI} profile move-home <profile>` moves it to the main checkout.")
            for x in shadowed():
                print(f"This worktree's own profiles/{x} is not used: the main checkout has a profile called {x} too. Both are kept.")
        elif a.cmd == "show":
            print(brief(a.profile), end="")
        elif a.cmd == "new":
            p = create(a.name, a.motion, a.about, a.from_film, is_default=a.default)
            print(f"Made the profile {p['slug']}{', the default' if p['default'] else ''}: profiles/{p['slug']}/PROFILE.md is its text.")
        elif a.cmd == "set":
            p = update(a.profile, {k: getattr(a, k) for k in ("name", "about", "font", "font_source", "text_font", "text_font_source", "type", "palette")})
            print(f"{p['slug']}: saved")
        elif a.cmd == "motion":
            ch = {k: getattr(a, k) for k in ("base", *MOTION) if getattr(a, k) is not None}
            if a.start:
                ch["from"] = a.start
            p = set_motion(a.profile, ch) if ch else get(a.profile)
            print("\n".join(motion_lines(p["motion"])))
        elif a.cmd == "motions":
            for m in motions():
                print(f"  {m['slug']:24} {m['kind']:8} " + (m["about"] if m["kind"] != "saved" else f"on {m['base']}: " + ", ".join(f"{k} {m[k]}" for k in MOTION if k in m)))
            print(f"\nStart a profile's motion from one: {paths.CLI} profile motion <profile> --from <motion>")
        elif a.cmd == "save-motion":
            print(f"Saved the motion {save_motion(a.profile, a.name)}: any profile can start from it now")
        elif a.cmd == "draft":
            if not SLUG.match(a.profile) or not _read(a.profile):
                a.profile = create(a.profile)["slug"] if not _read(slugify(a.profile)) else slugify(a.profile)
            for fp in a.files:
                if is_site(fp):
                    r = add_site(a.profile, fp, progress=lambda m: print(f"  {m}...", flush=True))
                    print(f"  read {r['url']}: " + ", ".join(r["files"]))
                    continue
                with open(os.path.expanduser(fp), "rb") as f:
                    print(f"  {add_source(a.profile, os.path.basename(fp), f.read())}")
            j = draft(a.profile)
            print(f"Drafting the profile {a.profile} from {len(sources(a.profile))} source(s): import {j['id']} ({j['status']}). `{paths.CLI} imports list` follows it.")
        elif a.cmd == "ask":
            j = draft(a.profile, a.request)
            print(f"Asked: import {j['id']} ({j['status']}). Your AI makes the change; `{paths.CLI} imports list` follows it.")
        elif a.cmd == "drafted":
            mark_drafted(a.profile)
            print(f"{a.profile}: drafted")
        elif a.cmd == "default":
            d = set_default("" if a.profile == NONE else a.profile)
            print(f"The default profile is {d}" if d else "No default profile: a brief starts with no profile, recreating its reference as it is")
        elif a.cmd == "learn":
            p = learn(a.profile, a.rule, a.source)
            print(f"{p['slug']}: {len(p['rules'])} rules")
        elif a.cmd == "forget":
            p = forget(a.profile, a.n)
            print(f"{p['slug']}: {len(p['rules'])} rules")
        elif a.cmd in ("pin", "unpin"):
            p = pin(a.profile, a.scene, a.cmd == "pin")
            print(f"{p['slug']}: {len(p['scenes'])} scenes")
        elif a.cmd == "remove":
            print(f"Removed; kept in {shown(remove(a.profile))}")
        elif a.cmd == "move-home":
            print(f"Moved {a.profile} to the main checkout: {move_home(a.profile)}. Every worktree sees it now; commit it there.")
        elif a.cmd == "setup":
            p = take_in_house()
            print(f"Your house rules are now the profile {p['name']} (profiles/{p['slug']}/), the default. Profiles holds it, and any other looks you make."
                  if p else f"{len(every())} profile{'' if len(every()) == 1 else 's'}" if every() else "No profiles yet: make one in the app (Profiles) when you want one.")
    except (KeyError, ValueError) as e:
        sys.exit(str(e.args[0]) if e.args else str(e))
    except OSError as e:   # a file to draft from that isn't there, or can't be read
        sys.exit(f"Couldn't read {e.filename or 'it'}: {e.strerror or e}" + (" (for a website, give its address: acme.com)" if getattr(e, "filename", None) else ""))


if __name__ == "__main__":
    main()
