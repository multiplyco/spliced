# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Bring a folder of things you have already collected into the library.

Point it at a folder (and everything under it). Pictures and GIFs become uploaded references. Videos are sorted by
length: a short one is a clip (an uploaded reference, one moment to borrow), a longer one is a film (cut into
scenes like a pasted link). Anything already in the library is left out, by what the file holds and not by its
name, so running it again on the same folder only brings in what is new.

usage:
  spliced import <folder>                     # look only: what is in there and what would come in
  spliced import <folder> --go                # bring it in (a job in the import queue; `spliced imports list`)
      --clip-under <seconds>                  # videos up to this long are clips, longer ones films (default 15)
      --no-reading                            # bring the files in, but don't queue the reading by an AI

What it costs: looking, copying and the machine pass on films (shots, tempo, frames) run on this machine for free.
Reading (each picture described and tagged, each film broken down scene by scene) is an AI's work: one job for all
the pictures and clips and one per film, waiting for your own AI unless the project lets one run unasked
(`agent` in spliced.json). The look says how many there are before anything starts.

The files are copied into the project (library/uploads/ and reference/), so the project stays whole when the
folder moves or the disk is unplugged. On a Mac, a copy on the same disk takes no extra room until one side changes.
"""
import hashlib, json, os, re, shutil, subprocess, sys

import paths, uploads

PICTURE = uploads.IMAGE + (".gif",)
VIDEO = uploads.VIDEO
CLIP_UNDER = 15.0
BIG = 32 * 2**20     # past this a file is told apart by its size and its two ends, not by every byte
END = 4 * 2**20
SKIP_DIRS = {"node_modules", "__pycache__"}
BUNDLES = (".app", ".photoslibrary", ".fcpbundle", ".imovielibrary", ".lrdata")   # folders that are one thing: don't look inside


def fingerprint(path):
    """What a file holds, as a short string: two files with the same one are the same picture or film, whatever they are called."""
    size = os.path.getsize(path)
    h = hashlib.sha1(str(size).encode())
    with open(path, "rb") as f:
        if size <= BIG:
            for block in iter(lambda: f.read(2**20), b""):
                h.update(block)
        else:
            h.update(f.read(END))
            f.seek(size - END)
            h.update(f.read(END))
    return h.hexdigest()[:20]


def kind_of(name):
    n = name.lower()
    return "picture" if n.endswith(PICTURE) else "video" if n.endswith(VIDEO) else None


def resolve(folder):
    """The folder as a real path. Refuses what isn't a folder, and the project's own library (it is already in)."""
    d = os.path.realpath(os.path.expanduser(str(folder or "").strip()))
    if not folder or not os.path.isdir(d):
        raise ValueError(f"there is no folder at {folder or '(nothing given)'}")
    for own in (paths.LIB, paths.REFERENCE, paths.CACHE):
        own = os.path.realpath(own)
        if d == own or d.startswith(own + os.sep):
            raise ValueError("that folder is this project's own library: everything in it is already here")
    return d


def walk(folder):
    """Every file under the folder a library could hold, in a steady order: (path, "picture" | "video" | None)."""
    for dp, dn, fn in os.walk(folder):
        dn[:] = sorted(x for x in dn if not x.startswith(".") and x not in SKIP_DIRS and not x.lower().endswith(BUNDLES))
        for f in sorted(fn):
            if not f.startswith("."):
                yield os.path.join(dp, f), kind_of(f)


def look(folder):
    """What is in the folder, without opening a file: quick enough to answer while someone waits."""
    d = resolve(folder)
    out = {"folder": d, "name": os.path.basename(d) or d, "pictures": 0, "videos": 0, "other": 0, "bytes": 0, "examples": []}
    for p, kind in walk(d):
        if not kind:
            out["other"] += 1
            continue
        out["pictures" if kind == "picture" else "videos"] += 1
        try:
            out["bytes"] += os.path.getsize(p)
        except OSError:
            pass
        if len(out["examples"]) < 6:
            out["examples"].append(os.path.relpath(p, d))
    out["can_sort_videos"] = bool(shutil.which("ffprobe"))
    return out


def have():
    """Fingerprints of what the library already holds: the uploaded files and the films."""
    seen = set()
    for top in (paths.UPLOADS, paths.REFERENCE):
        if not os.path.isdir(top):
            continue
        for dp, dn, fn in os.walk(top):
            dn[:] = [x for x in dn if not x.startswith(".")]
            for f in fn:
                if kind_of(f):
                    try:
                        seen.add(fingerprint(os.path.join(dp, f)))
                    except OSError:
                        pass
    return seen


def copy(src, dst):
    """Copy a file into the project. On a Mac the copy shares the original's blocks when both are on one disk."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if sys.platform == "darwin" and subprocess.run(["cp", "-c", src, dst], capture_output=True).returncode == 0:
        return
    shutil.copyfile(src, dst)


def free_name(folder, name):
    """A file name not taken in the folder: film.mp4, then film-2.mp4."""
    base, ext = os.path.splitext(name)
    n, out = 1, name
    while os.path.exists(os.path.join(folder, out)):
        n += 1
        out = f"{base}-{n}{ext}"
    return out


def film_slug(name, taken):
    """A slug for a film from its file name, not one already used."""
    import add_reference
    base = add_reference.kebab(re.sub(r"\[[^\]]*\]$", "", os.path.splitext(name)[0]))
    n, out = 1, base
    while out in taken:
        n += 1
        out = f"{base}-{n}"
    taken.add(out)
    return out


def bring(folder, clip_under=CLIP_UNDER, say=None, slugs=()):
    """Bring the folder's pictures, clips and films into the project. Returns what happened:
    {"pictures": n, "clips": n, "films": [{"file", "slug"}], "already": n, "left": [[name, why]]}.
    `say(text)` is told as it goes (and may raise to stop it). `slugs`: film names spoken for but not in the library yet."""
    d = resolve(folder)
    say = say or (lambda text: None)
    name = os.path.basename(d) or d
    seen = have()
    try:
        taken = {l.split("\t")[0] for l in open(paths.REFS_TSV).read().splitlines()[1:] if l.strip()}
    except OSError:
        taken = set()
    taken |= set(slugs)
    can_probe = bool(shutil.which("ffprobe"))
    out = {"pictures": 0, "clips": 0, "films": [], "already": 0, "left": []}
    files = [(p, k) for p, k in walk(d) if k]
    batch = []   # pictures and clips go into the index a handful at a time: one write for each handful, not for each file

    def flush():
        made, left = uploads.add_paths([(p, src) for p, src, _ in batch], by="folder")
        for it in made:
            out["clips" if it["kind"] == "video" else "pictures"] += 1
        out["left"] += [[os.path.relpath(p, d), why] for p, why in left]
        batch.clear()

    for i, (p, kind) in enumerate(files):
        relp = os.path.relpath(p, d)
        if i % 10 == 0:
            say(f"Looking at {i + 1} of {len(files)}")
        try:
            fp = fingerprint(p)
            size = os.path.getsize(p)
        except OSError as e:
            out["left"].append([relp, f"could not be read ({e.strerror or e})"])
            continue
        if fp in seen:
            out["already"] += 1
            continue
        seen.add(fp)   # the same picture twice in the folder comes in once
        source = f"folder: {name}/{relp}"
        if kind == "video":
            if not can_probe:
                out["left"].append([relp, "videos need ffmpeg to be sorted and cut (see Setup)"])
                continue
            _, _, dur = uploads.probe(p)
            if not dur:
                out["left"].append([relp, "not a video this machine can read"])
                continue
            if dur > clip_under or size > uploads.MAX:
                os.makedirs(paths.REFERENCE, exist_ok=True)
                dst = os.path.join(paths.REFERENCE, free_name(paths.REFERENCE, os.path.basename(p)))
                copy(p, dst)
                out["films"].append({"file": paths.rel(dst), "slug": film_slug(os.path.basename(p), taken), "from": source})
                continue
        if size > uploads.MAX:
            out["left"].append([relp, f"{size / 1e6:.0f} MB is too big for an uploaded picture (under 95 MB)"])
            continue
        batch.append((p, source, kind))
        if len(batch) >= 20:
            flush()
    flush()
    return out


def plural(n, one, many=None):
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def summary(r):
    """What a `bring` did, in a sentence."""
    got = [plural(r["pictures"], "picture"), plural(r["clips"], "clip"), plural(len(r["films"]), "film")]
    got = [g for g, n in zip(got, (r["pictures"], r["clips"], len(r["films"]))) if n]
    s = ("Brought in " + ", ".join(got)) if got else "Nothing new to bring in"
    if r["already"]:
        s += f"; {plural(r['already'], 'was', 'were')} already in the library"
    if r["left"]:
        s += f"; {plural(len(r['left']), 'file')} left alone"
    return s


def describe(lk, clip_under=CLIP_UNDER):
    """What a `look` found, as lines for a person (the command line, and the prompt an agent reads)."""
    n = lk["pictures"] + lk["videos"]
    lines = [f"{lk['folder']}", f"  {plural(lk['pictures'], 'picture')} and GIFs, {plural(lk['videos'], 'video')}, {lk['bytes'] / 1e6:,.0f} MB"
             + (f"; {plural(lk['other'], 'other file')} left alone" if lk["other"] else "")]
    if not n:
        return lines + ["  Nothing a library holds: pictures (png, jpg, webp, avif, svg), GIFs and videos (mp4, mov, webm, m4v)."]
    if lk["videos"]:
        lines.append(f"  Videos up to {clip_under:g} s come in as clips, longer ones as films cut into scenes." if lk["can_sort_videos"]
                     else "  Videos are left alone until ffmpeg is installed (see Setup): it sorts and cuts them.")
    read = [f"{plural(lk['pictures'], 'picture')} and GIFs to describe"] if lk["pictures"] else []
    if lk["videos"] and lk["can_sort_videos"]:
        read.append(f"{plural(lk['videos'], 'video')}, each a clip to describe or a film to break down")
    lines.append("  Anything already in the library is skipped. Looking and copying are free.")
    if read:
        lines.append("  Reading is your AI's work: " + ", and ".join(read) + ".")
    return lines


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        sys.exit(__doc__)
    if a[0] in ("add", "list", "cancel", "next", "done", "worker"):   # `spliced import add <link>` used to mean the queue: it still does
        import importer
        sys.argv = [sys.argv[0]] + a
        return importer.main()
    clip = float(a[a.index("--clip-under") + 1]) if "--clip-under" in a else CLIP_UNDER
    rest = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] != "--clip-under")]
    if len(rest) != 1:
        sys.exit(f"one folder at a time: {paths.CLI} import <folder> [--go]")
    try:
        lk = look(rest[0])
    except ValueError as e:
        sys.exit(str(e))
    if "--json" in a and "--go" not in a:
        print(json.dumps(lk))
        return
    print("\n".join(describe(lk, clip)))
    if not lk["pictures"] + lk["videos"]:
        return
    if "--go" not in a:
        print(f"\nNothing has been brought in. To do it:  {paths.CLI} import {json.dumps(rest[0])} --go")
        return
    import importer
    j = importer.add_folder(lk["folder"], clip_under=clip, reading="--no-reading" not in a)
    print(f"\n{j['id']}  {j['status']}  bringing it in. Follow it with:  {paths.CLI} imports list")


if __name__ == "__main__":
    main()
