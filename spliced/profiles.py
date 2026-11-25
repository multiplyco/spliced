"""A project's profiles: the looks its films are made in, each one built up over time.

A profile is a folder in the project, profiles/<slug>/:
  profile.json   its name, palette, typefaces (headlines and text, each from this Mac or Google Fonts), motion, the
                 scenes that show the look, the rules learned while making films
  PROFILE.md     the profile in prose: voice, stage, type, what to do and never do. The person's to write, and the
                 first thing an agent reads before building in it.
  sources/       what a profile was drafted from, when the person dropped a brand book, logo, screenshots or a film on
                 it: the person's AI reads them and fills the profile in (an import job, importer.py, type "profile")

One profile may be the default: a brief starts in it. Every brief can choose another, or none ("as the reference":
recreate what the reference shows, in its own look).

Motion is a base (one of the project's motion profiles: the kit's soft, material, apple, splice, or its own) and
what this look changes about it: pace (how long every move takes, against the base), bounce, stagger, how scenes
change, how words arrive, and whether things float while held. Each is optional: unset follows the base. They are
the fields of the film kit's Profile (remotion/src/lib/motion/spec.ts), so an agent builds the film's motion profile
from them in remotion/src/profiles.ts.

A project from before profiles had one brand (spliced.json) and remotion/docs/HOUSE.md: `spliced setup` makes them
its first profile, once, and leaves both files where they were.

  spliced profile                                   the profiles, the default marked
  spliced profile show <profile>                    everything an agent needs to build in it (words, motion, rules, scenes)
  spliced profile new "<name>" [--motion soft] [--about ".."] [--from-film <slug>] [--default]
                                                    --from-film starts it from a reference film's palette, type and moves
  spliced profile set <profile> [--name ..] [--about ..] [--font ..] [--font-source local|google] [--text-font ..]
                      [--text-font-source local|google] [--type ..] [--palette "#hex name, #hex name"]
  spliced profile motion <profile> [--base soft] [--pace 1.2] [--bounce 0.15] [--stagger 0.08]
                         [--transition cut|blurThrough|fadeThrough|sharedAxisX|sharedAxisZ] [--text sharpen|greyToInk] [--idle 0.4]
                                                    "base" for any of them goes back to the base's own
  spliced profile motion <profile> --from <motion>  start again from a kit motion profile or a saved motion (spliced profile motions)
  spliced profile motions                           the motions to start from: the kit's, the project's, and the ones saved here
  spliced profile save-motion <profile> "<name>"    keep this profile's motion as a starting point for others
  spliced profile draft <profile | "New name"> <file>...   copy a brand book, logo, screenshots or a film into its
                                                    sources/ and have the person's AI fill the profile in from them
  spliced profile ask <profile> "<what to change>"  the person's request, for their AI to make in the profile
  spliced profile drafted <profile>                 the agent that drafted or changed it says it is done
  spliced profile default <profile | none>          the profile a brief starts in
  spliced profile learn <profile> "never bounce the logo" [--from "launch-film note 3"]
  spliced profile forget <profile> <n>              take rule n out
  spliced profile pin <profile> <film/sNN>          a scene that shows the look; unpin takes it out
  spliced profile remove <profile>                  kept in .cache/profiles-removed/ first
"""
import argparse, datetime as dt, json, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

DIR = paths.PROFILE_DIR
NONE = "none"   # a build in no profile: as the reference
FONT_SOURCES = ("local", "google")
SOURCE_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", ".mov", ".m4v", ".webm", ".txt", ".md", ".key", ".pptx"}
SOURCE_MAX = 400 * 1024 * 1024
MOTIONS = os.path.join(DIR, "motions.json")   # motions saved as starting points: {slug: {name, base, pace?, ...}}
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
    "transition": (("cut", "blurThrough", "fadeThrough", "sharedAxisX", "sharedAxisZ"), "how one scene becomes the next"),
    "text": (("sharpen", "greyToInk"), "how words arrive: sharpen from a blur, or land grey and darken"),
    "idle": ((0.0, 1.0), "how much held things float (0 = still)"),
}
# The kit's own motion profiles as the app shows them (remotion/src/lib/motion/profile.tsx): the base values a
# look changes, and the curve and length of an entrance, for the app's preview. A project's own profiles have no row
# here; they are previewed with the soft row's values.
KIT_MOTION = {
    "soft": {"pace": 1, "bounce": 0, "stagger": 0.1, "transition": "cut", "text": "sharpen", "idle": 1, "curve": [0.2, 0.8, 0.2, 1], "enter": 0.6},
    "material": {"pace": 1, "bounce": 0.1, "stagger": 0.05, "transition": "sharedAxisZ", "text": "sharpen", "idle": 0, "curve": [0.05, 0.7, 0.1, 1], "enter": 0.8},
    "apple": {"pace": 1, "bounce": 0.15, "stagger": 0.06, "transition": "sharedAxisX", "text": "sharpen", "idle": 0.6, "curve": [0.25, 0.9, 0.3, 1], "enter": 0.6},
    "splice": {"pace": 1, "bounce": 0, "stagger": 0.07, "transition": "blurThrough", "text": "sharpen", "idle": 0.3, "curve": [0.16, 1, 0.3, 1], "enter": 0.75},
}
WORDS = {"cut": "a straight cut", "blurThrough": "blur through", "fadeThrough": "fade through", "sharedAxisX": "slide along the x axis",
         "sharedAxisZ": "push along the z axis (scale and fade)", "sharpen": "sharpen in from a blur", "greyToInk": "land grey, then darken"}


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
        if isinstance(allowed[0], str):
            if x in allowed:
                out[k] = x
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
            "found": {"palette": colours_in(md)}}   # what its words name, for the app to offer in one click


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
            if isinstance(allowed[0], str):
                if v not in allowed:
                    raise ValueError(f"{k} is one of {', '.join(allowed)}")
                m[k] = v
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
        with open(MOTIONS) as f:
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
    _write(MOTIONS, json.dumps(d, indent=1, ensure_ascii=False) + "\n")
    return key


def remove_motion(key):
    d = saved_motions()
    if key not in d:
        raise ValueError(f"no saved motion called {key!r}")
    del d[key]
    _write(MOTIONS, json.dumps(d, indent=1, ensure_ascii=False) + "\n")


def sources(slug):
    """What a profile was drafted from: [{file, kind, bytes}], project-relative paths."""
    d = os.path.join(DIR, slug, "sources")
    if not os.path.isdir(d):
        return []
    kind = lambda e: "video" if e in (".mp4", ".mov", ".m4v", ".webm") else "image" if e in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg") else "document"
    return [{"file": paths.rel(os.path.join(d, n)), "name": n, "kind": kind(os.path.splitext(n)[1].lower()), "bytes": os.path.getsize(os.path.join(d, n))}
            for n in sorted(os.listdir(d)) if not n.startswith(".") and os.path.isfile(os.path.join(d, n))]


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
        raise ValueError(f"{slug} has nothing to draft from: drop a brand book, logo, screenshots or a film on it, or say what it should be")
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
        out.append(f"- {k}: {WORDS.get(v, v)} ({MOTION[k][1]})")
    out.append(f"Build it as a motion profile named after this profile in remotion/src/profiles.ts: start from `{base}`'s roles, "
               "scale every role's seconds by pace, give UI and emphasis springs the bounce, and set stagger, viewChange.kind "
               "(transition), text.style and idle as above. Then use it with motion('<that name>').")
    return out


def brief(slug):
    """A profile as an agent reads it before building in it: what `spliced profile show` prints."""
    p = get(slug)
    lines = [f"# Profile: {p['name']}", "", f"profiles/{slug}/{' · the default' if p['default'] else ''}", ""]
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
        lines += ["## What it was drafted from", "", ", ".join(f"`{x['file']}`" for x in p["sources"]), ""]
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
    x = sub.add_parser("draft"); x.add_argument("profile"); x.add_argument("files", nargs="+")
    x = sub.add_parser("drafted"); x.add_argument("profile")
    x = sub.add_parser("ask"); x.add_argument("profile"); x.add_argument("request")
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
                print(f"No profiles yet. Make one: {paths.CLI} profile new \"<name>\" (or in the app: Profiles)")
                return
            for p in ps:
                print(f"{'*' if p['default'] else ' '} {p['slug']:24} {p['name']:28} motion {p['motion']['base']:9} {len(p['rules'])} rules  {len(p['scenes'])} scenes")
            print(f"\n* the default: a brief starts in it. `{paths.CLI} profile show <profile>` before building in one.")
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
            print(f"Removed; kept in {os.path.relpath(remove(a.profile), paths.ROOT)}")
        elif a.cmd == "setup":
            p = take_in_house()
            print(f"Your house rules are now the profile {p['name']} (profiles/{p['slug']}/), the default. Profiles holds it, and any other looks you make."
                  if p else f"{len(every())} profile{'' if len(every()) == 1 else 's'}" if every() else "No profiles yet: make one in the app (Profiles) when you want one.")
    except (KeyError, ValueError) as e:
        sys.exit(str(e.args[0]) if e.args else str(e))


if __name__ == "__main__":
    main()
