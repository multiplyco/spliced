"""Where everything is: the one module that knows the project's root and the places inside it.

Two different things, kept apart:
  TOOLS, WEB, SKILLS, TEMPLATES   Spliced's own code and files (this package)
  ROOT                            the project being worked on: a folder with a spliced.json, holding a library,
                                  reference films and films in production

Which folder is the project is locate.py's business (--project, SPLICED_PROJECT, or the nearest spliced.json above
where you are). A tool that imports this module needs one: without it, it stops and says how to get one. Whatever
is found is exported as SPLICED_PROJECT, so the tools one tool starts work on the same project.

A project's layout (every name relative to ROOT; spliced.json may override a folder under "layout"):
  spliced.json                   marks the folder as a project: its name, brand, motion profiles, who reads imports
  library/                       TAXONOMY.md, STYLES.md, INDEX.md, references.tsv, references/<slug>/, uploads/,
                                 state.json (reviews, boards, moments)
  reference/                     downloaded reference films
  remotion/                      films in production: src/films/<slug>/, public/films/<slug>/, out/ (renders)
  videos/, music/                HyperFrames films and music beds, when the project has them
  <folder>/                      the project's own folders, when it sorts its work (spliced.json "folders"): a
                                 folder's renders/, its HyperFrames films, and any files the person put there
  .cache/                        frames, sound maps, import jobs, the library index: rebuilt on demand, never in git
  .env                           API keys: never in git, never served
"""
import json, os, re, shlex, shutil, subprocess, sys

import locate

TOOLS = os.path.dirname(os.path.abspath(__file__))
APP = TOOLS                                  # where Spliced's own instructions and templates are looked up
WEB = os.path.join(TOOLS, "web")             # the app's files, served as /app/
SKILLS = os.path.join(TOOLS, "skills")       # the instructions an agent follows (spliced agents install copies them into a project)
TEMPLATES = os.path.join(TOOLS, "templates")
MARKER = locate.MARKER
# How a prompt or a hint writes a Spliced command: the installed command when there is one, this checkout otherwise.
# The Mac app sets SPLICED_COMMAND to the command inside it (Spliced.app/Contents/Resources/bin/spliced), for when
# nothing called spliced is on the PATH.
COMMAND = os.environ.get("SPLICED_COMMAND", "") if os.path.isfile(os.environ.get("SPLICED_COMMAND", "")) else ""
# The npm launcher (bin/spliced.js) sets SPLICED_VIA to how it was started when that isn't an installed command:
# "npx -y <package>". Prompts, AGENTS.md and MCP entries then name that, not a path in npx's cache.
VIA = os.environ.get("SPLICED_VIA", "").strip()
CLI = (VIA if VIA else "spliced" if shutil.which("spliced") else shlex.quote(COMMAND) if COMMAND
       else "uv run " + os.path.join(TOOLS, "cli.py"))


def _version():
    """Spliced's version (from the package), and the build when it runs from a git checkout: ("0.3.0", "adda766")."""
    try:
        with open(os.path.join(TOOLS, "__init__.py")) as f:
            number = (re.search(r'__version__\s*=\s*"([^"]+)"', f.read()) or [None, ""])[1]
    except OSError:
        number = ""
    build = ""
    try:   # a copy that isn't a checkout (the Mac app's engine) carries its build in a file
        with open(os.path.join(TOOLS, "BUILD")) as f:
            build = f.read().strip()
    except OSError:
        pass
    if not build and os.path.exists(os.path.join(os.path.dirname(TOOLS), ".git")):
        try:
            build = subprocess.run(["git", "-C", TOOLS, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return number, build


VERSION, BUILD = _version()


def env(name, default=None):
    """A setting from the environment: SPLICED_<NAME>, or CUTTING_ROOM_<NAME>, the app's name before it was Spliced."""
    return os.environ.get("SPLICED_" + name) or os.environ.get("CUTTING_ROOM_" + name) or default


def tool(name):
    """The path of one of Spliced's own scripts: tool("sound") -> <package>/sound.py."""
    return os.path.join(TOOLS, name if name.endswith(".py") else name + ".py")


ROOT = locate.find(locate.flag()) or sys.exit(locate.NO_PROJECT)
os.environ["SPLICED_PROJECT"] = ROOT


def _config():
    try:
        with open(os.path.join(ROOT, MARKER)) as f:
            c = json.load(f)
        return c if isinstance(c, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


CONFIG = _config()
LAYOUT = {"library": "library", "reference": "reference", "remotion": "remotion", "videos": "videos", "music": "music", "profiles": "profiles",
          **{k: v for k, v in (CONFIG.get("layout") or {}).items() if isinstance(v, str) and v}}


def _p(*parts):
    return os.path.join(ROOT, *parts)


# Whose films these are, and the motion profiles a board or film may name. A project adds its own profiles and picks
# its default in spliced.json ("brand": {"name": ...}, "profiles": {name: one line}, "default_profile"); the four
# below ship with the film kit (remotion/src/lib/motion/profile.tsx, docs/MOTION-SYSTEMS.md).
KIT_PROFILES = {
    "soft": "Calm and precise: arrive fast, land soft, slow camera, no bounce",
    "material": "Material 3: emphasized curves, shared-axis view changes",
    "apple": "Apple-style: springs everywhere, a small bounce on UI",
    "splice": "Spliced brand: crisp ease-out arrivals, ease-sink camera and blocks, no bounce",
}
NAME = str(CONFIG.get("name") or os.path.basename(ROOT))
BRAND = str((CONFIG.get("brand") or {}).get("name") or "").strip()
PROFILES = {**{str(k): str(v) for k, v in (CONFIG.get("profiles") or {}).items()}, **{k: v for k, v in KIT_PROFILES.items() if k not in (CONFIG.get("profiles") or {})}}
DEFAULT_PROFILE = CONFIG.get("default_profile") if CONFIG.get("default_profile") in PROFILES else "soft"

# Where the product the films are about really lives: its code, as folders on this machine or addresses an agent can
# read (spliced.json "app": {"code": "~/code/acme-app"}, or a list). A film's UI is rebuilt from what ships there.
def _app_code():
    v = (CONFIG.get("app") or {}).get("code") if isinstance(CONFIG.get("app"), dict) else None
    return [str(x).strip() for x in (v if isinstance(v, list) else [v] if v else []) if str(x).strip()]


APP_CODE = _app_code()

# Folders: how the project sorts its films, boards and assets, say one per kind of video or one per client
# (spliced.json "folders": a list of folder paths inside the project, each a string or {"folder": ..., "name": ...}).
# A Remotion film's code stays in remotion/ and names its folder in storyboard.json; its renders go to the folder's
# renders/. A HyperFrames film lives in its folder (<folder>/<slug>/). A board names its folder in library/state.json.
# Whatever names no folder is the project's own: "" in code, Shared in the app. The library is never in a folder.
RESERVED = ("library", "reference", "remotion", "videos", "music", "profiles", "node_modules")
FOLDERS = []          # [{"folder": "branding-videos", "name": "Branding videos"}], in the order spliced.json gives
FOLDER_NAMES = set()  # (both are changed in place by reload_folders, so a module holding them sees a new folder)


def folder_title(folder):
    """A folder's name as the app writes it when spliced.json gives none: "branding-videos" -> "Branding videos"."""
    s = re.sub(r"[-_]+", " ", folder.rsplit("/", 1)[-1]).strip()
    return s[:1].upper() + s[1:] if s else folder


def clean_folder(folder):
    """A folder path as spliced.json keeps it ("branding-videos", "clients/acme"), or "" if it can't be one: outside
    the project, a dot name, or one of Spliced's own folders."""
    f = str(folder or "").strip().replace("\\", "/")
    if f.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", f):   # a path on the machine, not one inside the project
        return ""
    f = f.strip("/")
    parts = [p for p in f.split("/") if p]
    if not parts or any(p.startswith(".") for p in parts) or parts[0] in RESERVED or "/".join(parts) != f:
        return ""
    return f


def reload_folders(config=None):
    """Read the folders from spliced.json again (a command in another process may have added one)."""
    c = config if config is not None else _config()
    out, seen = [], set()
    for x in c.get("folders") or []:
        f, n = (x, "") if isinstance(x, str) else (x.get("folder", ""), x.get("name", "")) if isinstance(x, dict) else ("", "")
        f = clean_folder(f)
        if f and f not in seen:
            seen.add(f)
            out.append({"folder": f, "name": str(n or "").strip() or folder_title(f)})
    FOLDERS[:] = out
    FOLDER_NAMES.clear()
    FOLDER_NAMES.update(seen)
    return FOLDERS


reload_folders(CONFIG)


def folder_path(folder):
    """The real path of a folder ("" is the project itself)."""
    return os.path.join(ROOT, folder) if folder else ROOT


def folder_of(path):
    """Which of the project's folders a real path is in ("" for none)."""
    p = os.path.realpath(path)
    best = ""
    for f in FOLDER_NAMES:
        d = os.path.realpath(folder_path(f))
        if (p == d or p.startswith(d + os.sep)) and len(f) > len(best):
            best = f
    return best


def here_folder():
    """The folder work started here belongs in: SPLICED_FOLDER (set by whoever started this, say the MCP server for
    an agent opened in a folder), else the folder the current directory is in. "" for none."""
    f = clean_folder(env("FOLDER", ""))
    if f in FOLDER_NAMES:
        return f
    try:
        return folder_of(os.getcwd())
    except OSError:
        return ""

# the library
LIB = _p(LAYOUT["library"])
REFS = os.path.join(LIB, "references")
REFS_TSV = os.path.join(LIB, "references.tsv")
UPLOADS = os.path.join(LIB, "uploads")
UPLOADS_INDEX = os.path.join(UPLOADS, "uploads.json")
TAXONOMY = os.path.join(LIB, "TAXONOMY.md")
STYLES = os.path.join(LIB, "STYLES.md")
INDEX_MD = os.path.join(LIB, "INDEX.md")
STATE = os.path.join(LIB, "state.json")                 # reviews, boards, moments (toolbox_state.py)
STATE_OLD = os.path.join(LIB, "toolbox", "state.json")  # where it was while the app lived inside the library
REFERENCE = _p(LAYOUT["reference"])

# films in production
REMOTION = _p(LAYOUT["remotion"])
FILMS = os.path.join(REMOTION, "src", "films")
OUT = os.path.join(REMOTION, "out")                 # a Remotion film's renders when it is in no folder
HOUSE_MD = os.path.join(REMOTION, "docs", "HOUSE.md")   # house rules from before profiles (profiles.py takes them in)

# the project's profiles: how its films look and move, one folder each (profiles.py). Not the motion profiles above:
# a profile names the motion profile its films use, beside its palette, type and rules.
PROFILE_DIR = _p(LAYOUT["profiles"])


def renders_dir(folder, home=None):
    """Where a Remotion film in this folder renders to: <folder>/renders, or remotion/out for a film in none. In a git
    worktree they go to the main checkout's (render_home), unless the project keeps renders with the branch."""
    base = home or render_home()
    return os.path.join(base, folder, "renders") if folder else os.path.join(base, LAYOUT["remotion"], "out")
PUBLIC = os.path.join(REMOTION, "public")
PUBLIC_FILMS = os.path.join(PUBLIC, "films")
VIDEOS = _p(LAYOUT["videos"])
MUSIC = _p(LAYOUT["music"])

# rebuilt on demand
CACHE = _p(".cache")
FRAMES_CACHE = os.path.join(CACHE, "frames")
SOUND_CACHE = os.path.join(CACHE, "sound")
UPLOADS_CACHE = os.path.join(CACHE, "uploads")
JOBS = os.path.join(CACHE, "imports")
LIBRARY_JSON = os.path.join(CACHE, "library.json")  # the library as the app reads it, written by build_library.py
WATCH = os.path.join(CACHE, "watch")
SERVER_FILE = os.path.join(CACHE, "server.json")    # where this project's app is served while it runs: {port, url, pid, root}

ENV = _p(".env")

# ffmpeg without a package manager: a machine with no Homebrew (or apt) can get a ready-built ffmpeg and ffprobe with
# `uv tool install static-ffmpeg`, which needs no password. That package calls them static_ffmpeg and
# static_ffprobe, so when no ffmpeg is on the PATH and those are, the project keeps links under the names every
# tool here uses (.cache/bin/ffmpeg, ffprobe) and puts that folder on the PATH for this run and whatever it starts.
TOOL_BIN = os.path.join(CACHE, "bin")
STATIC_FFMPEG = "uv tool install static-ffmpeg"   # the command doctor suggests, and the package the links come from


def _ffmpeg_fallback():
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    links = {n: os.path.join(TOOL_BIN, n) for n in ("ffmpeg", "ffprobe")}
    if not all(os.path.exists(p) for p in links.values()):   # (exists follows the link: a removed package is seen)
        finder = shutil.which("static_ffmpeg_paths") or next(
            (p for p in (os.path.expanduser("~/.local/bin/static_ffmpeg_paths"),) if os.path.isfile(p)), None)
        if not finder:
            return
        try:   # the first call fetches the binaries (a few seconds), and says where they are: FFMPEG=<path>, FFPROBE=<path>
            out = subprocess.run([finder], capture_output=True, text=True, timeout=120).stdout
        except (OSError, subprocess.SubprocessError):
            return
        found = dict(re.findall(r"(?m)^(FFMPEG|FFPROBE)=(.+)$", out))
        real = {"ffmpeg": found.get("FFMPEG", "").strip(), "ffprobe": found.get("FFPROBE", "").strip()}
        if not all(os.path.isfile(p) for p in real.values()):
            return
        try:
            os.makedirs(TOOL_BIN, exist_ok=True)
            for n, p in links.items():
                if os.path.lexists(p):
                    os.remove(p)
                os.symlink(real[n], p)
        except OSError:
            return
    os.environ["PATH"] = TOOL_BIN + os.pathsep + os.environ.get("PATH", "")


_ffmpeg_fallback()

def state_file():
    """Where the boards and reviews are read from: STATE, or the old place in a project that hasn't been saved since the move."""
    return STATE_OLD if not os.path.exists(STATE) and os.path.exists(STATE_OLD) else STATE


_MAIN = []


def main_checkout():
    """When the project is a linked git worktree (a Conductor workspace, `git worktree add`), the main checkout's
    project folder: an app opened there sees its own renders and settings, not this folder's. Otherwise None."""
    if not _MAIN:
        _MAIN.append(_main_checkout())
    return _MAIN[0]


# Renders made in a git worktree (a Conductor workspace, `git worktree add`), spliced.json "worktree_renders":
#   "main"      (the default) they go to the main checkout's folders: one place for every render, seen by Spliced
#               opened there, kept when the worktree is removed, and kept out of the branch (git never carries them)
#   "worktree"  they stay in the worktree's own folders and travel with the branch, like code: commit them and they
#               arrive with the merge (GitHub as where videos are shared; mind its file and repository size limits)
WORKTREE_RENDERS = CONFIG.get("worktree_renders") if CONFIG.get("worktree_renders") in ("main", "worktree") else "main"
MAIN_PREFIX = "@main/"   # how a file in the main checkout is written down by a project that is a worktree of it


def render_home():
    """The project folder renders are written into: the main checkout when this is a worktree of one and renders go
    there (WORKTREE_RENDERS), else this project."""
    m = main_checkout() if WORKTREE_RENDERS == "main" else None
    return m if m and os.path.isfile(os.path.join(m, MARKER)) else ROOT


def _main_checkout():
    try:
        out = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir", "--show-prefix"],
                             cwd=ROOT, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = out.stdout.splitlines()
    if out.returncode or len(lines) < 2 or os.path.realpath(lines[0]) == os.path.realpath(lines[1]):
        return None
    main = os.path.dirname(os.path.realpath(lines[1]))           # <main>/.git -> <main>
    prefix = lines[2].strip() if len(lines) > 2 else ""          # the project's place inside the repo
    return os.path.join(main, prefix).rstrip("/") if main else None


MEDIA_EXT = (".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".svg",
             ".mp4", ".mov", ".webm", ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".ogg")


def rel(path):
    """A path as the project writes it down: relative to ROOT, forward slashes. A file in the main checkout of a
    worktree (a render that went home) is written "@main/<path in it>"."""
    p = os.path.abspath(path)
    if p != ROOT and not p.startswith(ROOT + os.sep):
        m = main_checkout()
        if m and (p == m or p.startswith(m + os.sep)):
            return MAIN_PREFIX + os.path.relpath(p, m).replace(os.sep, "/")
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def resolve(relpath, main_ok=False):
    """The real path of a project-relative path. ValueError if it leaves the project (.., an absolute path, a link out).
    With main_ok, "@main/<path>" is a path in the main checkout this worktree belongs to, held to the same rule there."""
    relpath = str(relpath or "")
    base = ROOT
    if relpath.startswith(MAIN_PREFIX):
        m = main_checkout() if main_ok else None
        if not m:
            raise ValueError(f"{relpath!r} is outside the project")
        base, relpath = os.path.realpath(m), relpath[len(MAIN_PREFIX):]
    p = os.path.realpath(os.path.join(base, relpath))
    if p != base and not p.startswith(base + os.sep):
        raise ValueError(f"{relpath!r} is outside the project")
    return p


def abspath(relpath):
    """The real path of a file the project wrote down (rel), the main checkout's included. No checks: for paths
    Spliced itself wrote, never for one a request brought."""
    relpath = str(relpath or "")
    m = main_checkout() if relpath.startswith(MAIN_PREFIX) else None
    return os.path.join(m, relpath[len(MAIN_PREFIX):]) if m else os.path.join(ROOT, relpath)


def media(relpath, hidden_ok=((".cache", "sound"),)):
    """The real path of a picture, clip or sound the app may be given, or None: inside the project, a media file,
    and no dot name anywhere on the way (.env, .git, .cache/imports). The one dot folder allowed is the Sound
    panel's separated stems."""
    relpath = str(relpath or "").replace("\\", "/")
    home = MAIN_PREFIX if relpath.startswith(MAIN_PREFIX) else ""   # a render the worktree sent to the main checkout
    segs = tuple(s for s in relpath[len(home):].split("/") if s)
    rest = segs
    for ok in hidden_ok:
        if segs[:len(ok)] == ok:
            rest = segs[len(ok):]
    if not segs or any(s.startswith(".") for s in rest) or not segs[-1].lower().endswith(MEDIA_EXT):
        return None
    try:
        p = resolve(home + "/".join(segs), main_ok=bool(home))
    except ValueError:
        return None
    return p if os.path.isfile(p) else None
