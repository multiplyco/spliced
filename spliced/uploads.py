# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Uploaded references: images, GIFs and short clips you like, next to the scenes broken down from films.

They live in library/uploads/ (the files, plus uploads.json with each one's title, note, tags and source) and show
in Spliced's Library view as `uploads/<id>`, so they can be favourited, noted and put on boards like any
scene. Upload by dropping files anywhere in the app, pasting an image, or "Upload" in Library.

usage:
  spliced uploads list
  spliced uploads add <file-or-image-url>... [--title "..."] [--note "..."] [--tags "a, b"]
  spliced uploads edit <id> [--title ..] [--note ..] [--tags ..]
  spliced uploads rm <id>
  spliced uploads pending                  # uploads not analysed yet, with the image to look at for each
  spliced uploads set <id> '<json>'        # store an analysis (tags checked against TAXONOMY.md)

Analysis: each upload is read like a film scene (role, world, subject, camera, motion, type_treatment, pace, energy,
production from TAXONOMY.md, plus on_screen, how_it_moves, recreate, steal and a title), so it filters and briefs
like one. New uploads queue it on their own (importer.py, a headless Claude session); the palette is measured.
"""
import datetime as dt, json, os, re, secrets, shutil, subprocess, sys, urllib.request

import paths

ROOT = paths.ROOT
DIR = paths.UPLOADS
INDEX = paths.UPLOADS_INDEX
IMAGE = (".png", ".jpg", ".jpeg", ".webp", ".avif", ".svg")
VIDEO = (".mp4", ".mov", ".webm", ".m4v")
MAX = 95e6  # GitHub refuses files over 100 MB


def load():
    try:
        return json.load(open(INDEX))
    except (OSError, ValueError):
        return {"_note": "Uploaded references (uploads.py). Files sit next to this; ids are Spliced's uploads/<id>.", "items": []}


def save(d):
    os.makedirs(DIR, exist_ok=True)
    tmp = INDEX + ".tmp"
    json.dump(d, open(tmp, "w"), indent=1, ensure_ascii=False)
    os.replace(tmp, INDEX)


def items():
    return load()["items"]


def keys():
    return {f"uploads/{x['id']}" for x in items()}


def kind_of(name):
    n = name.lower()
    return "gif" if n.endswith(".gif") else "video" if n.endswith(VIDEO) else "image" if n.endswith(IMAGE) else None


def probe(path):
    """Width, height and (for clips and GIFs) duration, with ffprobe; best effort."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                              "stream=width,height,duration,nb_read_packets,r_frame_rate:format=duration", "-of", "json", path],
                             capture_output=True, text=True, timeout=30).stdout
        j = json.loads(out or "{}")
        st = (j.get("streams") or [{}])[0]
        dur = float(st.get("duration") or (j.get("format") or {}).get("duration") or 0) or None
        return st.get("width"), st.get("height"), round(dur, 2) if dur else None
    except Exception:  # noqa: BLE001
        return None, None, None


def slug(s, n=32):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:n].strip("-")


def _store(data, filename, title="", note="", tags=None, source="", by="person"):
    """Write an upload's file and return its entry, not yet in the index."""
    kind = kind_of(filename)
    if not kind:
        raise ValueError("upload an image (png, jpg, webp, avif, svg), a GIF or a clip (mp4, mov, webm)")
    if len(data) > MAX:
        raise ValueError(f"{len(data) / 1e6:.0f} MB is too big for the repo (under 95 MB, please)")
    os.makedirs(DIR, exist_ok=True)
    uid = secrets.token_hex(3)
    base = os.path.splitext(os.path.basename(filename))[0]
    ext = os.path.splitext(filename)[1].lower().replace(".jpeg", ".jpg")
    fname = f"{slug(base) or kind}-{uid}{ext}"
    path = os.path.join(DIR, fname)
    open(path, "wb").write(data)
    w, h, dur = probe(path) if kind != "image" or ext != ".svg" else (None, None, None)
    it = {"id": uid, "file": os.path.relpath(path, ROOT), "kind": kind, "title": title.strip() or re.sub(r"[-_]+", " ", base).strip().capitalize(),
          "note": note.strip(), "tags": [t.strip() for t in (tags or []) if t.strip()], "source": source, "width": w, "height": h,
          "duration": dur if kind != "image" else None, "added": dt.datetime.now().isoformat(timespec="seconds"), "by": by}
    return it


def add_bytes(data, filename, **kw):
    it = _store(data, filename, **kw)
    d = load()
    d["items"].append(it)
    save(d)
    return it


def add_paths(files, by="person"):
    """Several files at once, with one write of the index: [(path, source)] -> (the new entries, [(path, why not)])."""
    made, left = [], []
    for path, source in files:
        try:
            with open(path, "rb") as f:
                made.append(_store(f.read(), os.path.basename(path), source=source, by=by))
        except (OSError, ValueError) as e:
            left.append((path, str(e)))
    if made:
        d = load()
        d["items"].extend(made)
        save(d)
    return made, left


def add_path(path, **kw):
    path = os.path.expanduser(path)
    return add_bytes(open(path, "rb").read(), os.path.basename(path), **kw)


def add_url(url, **kw):
    if not re.match(r"https?://", url, re.I):  # a web link only: never file:// or another scheme the server could be made to read
        raise ValueError("that isn't a web link (it should start with http:// or https://)")
    req = urllib.request.Request(url, headers={"User-Agent": "Spliced/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(int(MAX) + 1)
        ctype = (r.headers.get("Content-Type") or "").split(";")[0]
    name = os.path.basename(url.split("?")[0]) or "image"
    if not kind_of(name):
        ext = {"image/gif": ".gif", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/avif": ".avif", "video/mp4": ".mp4", "video/webm": ".webm"}.get(ctype)
        if not ext:
            raise ValueError(f"that link isn't an image, GIF or clip ({ctype or 'unknown type'}). For a film on YouTube or Vimeo use Add reference.")
        name = (slug(name) or "upload") + ext
    return add_bytes(data, name, source=kw.pop("source", "") or url, **kw)


def update(uid, patch):
    d = load()
    it = next((x for x in d["items"] if x["id"] == uid), None)
    if not it:
        raise KeyError(f"no upload {uid}")
    for k, v in patch.items():
        if k in ("title", "note", "source"):
            it[k] = str(v).strip()
        elif k == "tags":
            it["tags"] = [t.strip() for t in (v if isinstance(v, list) else str(v).split(",")) if t.strip()]
        else:
            raise ValueError(f"uploads have title, note, tags and source, not {k!r}")
    save(d)
    return it


def remove(uid):
    d = load()
    it = next((x for x in d["items"] if x["id"] == uid), None)
    if not it:
        raise KeyError(f"no upload {uid}")
    d["items"].remove(it)
    save(d)
    try:
        os.remove(os.path.join(ROOT, it["file"]))
    except OSError:
        pass
    return it


# ---------- analysis: the same reading as a film scene (tags from TAXONOMY.md, on screen, how it moves, recreate) ----------
ONE = ["role", "world", "pace", "energy"]
MANY = ["subject", "camera", "motion", "type_treatment", "production"]
TEXT = ["title", "on_screen", "how_it_moves", "recreate"]
CACHE = paths.UPLOADS_CACHE


def taxonomy():
    text = open(paths.TAXONOMY).read()
    out = {}
    for m in re.finditer(r"^### `([a-z_]+)`(.*?)(?=^#{2,3} |\Z)", text, re.S | re.M):
        out[m.group(1)] = {t for t in re.findall(r"`([a-z0-9][a-z0-9-]*)`", m.group(2)) if t != m.group(1)}
    return out


def sheet(it):
    """What to look at: the image itself, or a 3x2 contact sheet of a clip's or GIF's frames (.cache/uploads/)."""
    path = os.path.join(ROOT, it["file"])
    if it["kind"] == "image":
        if path.lower().endswith((".svg", ".avif")):
            os.makedirs(CACHE, exist_ok=True)
            out = os.path.join(CACHE, f"{it['id']}.png")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-frames:v", "1", out], capture_output=True)
            return out if os.path.exists(out) else path
        return path
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, f"{it['id']}-sheet.jpg")
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(path):
        dur = it.get("duration") or probe(path)[2] or 2
        fps = 6 / max(0.5, dur)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf", f"fps={fps:.4f},scale=640:-2,tile=3x2:padding=6:color=black",
                        "-frames:v", "1", "-q:v", "4", out], capture_output=True)
    return out if os.path.exists(out) else path


def palette(it, n=6):
    """The dominant colours, as hex: k-means-free, by quantising a small frame (ffmpeg's palettegen)."""
    path = os.path.join(ROOT, it["file"])
    try:
        out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-frames:v", "1", "-vf",
                              f"scale=96:-1,palettegen=max_colors={n}:reserve_transparent=0:stats_mode=full", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, timeout=30).stdout
        cols = [out[i:i + 3] for i in range(0, len(out) - 2, 3)]
        seen = []
        for c in cols:
            hx = "#%02X%02X%02X" % tuple(c)
            if hx not in seen and hx != "#000000" or (hx == "#000000" and hx not in seen and len(seen) < n):
                seen.append(hx)
        return seen[:n]
    except Exception:  # noqa: BLE001
        return []


def set_analysis(uid, a):
    """Validate an analysis against TAXONOMY.md and store it on the upload. Raises ValueError listing bad tags."""
    tax, errs, out = taxonomy(), [], {}
    for f in ONE:
        v = a.get(f)
        if v in (None, "", "none") and f in ("role", "pace", "energy"):
            continue
        if v not in tax.get(f, set()):
            errs.append(f"{f} '{v}' is not in TAXONOMY.md ({', '.join(sorted(tax.get(f, [])))})")
        out[f] = v
    for f in MANY:
        vs = a.get(f) or []
        vs = [vs] if isinstance(vs, str) else vs
        bad = [v for v in vs if v not in tax.get(f, set())]
        if bad:
            errs.append(f"{f} {bad} not in TAXONOMY.md ({', '.join(sorted(tax.get(f, [])))})")
        out[f] = vs
    for f in TEXT:
        if a.get(f):
            out[f] = str(a[f]).strip()
    st = a.get("steal")
    out["steal"] = int(st) if str(st) in ("1", "2", "3") else 2
    if not out.get("on_screen") or not out.get("recreate"):
        errs.append("on_screen and recreate are required")
    if errs:
        raise ValueError("; ".join(errs))
    d = load()
    it = next((x for x in d["items"] if x["id"] == uid), None)
    if not it:
        raise KeyError(f"no upload {uid}")
    if not it.get("palette"):
        it["palette"] = palette(it)
    title = out.pop("title", "")
    if title and (not it.get("title") or re.fullmatch(r"(?i)(\d+ )?(pin|video|img|image|pasted|dropped|screenshot|upload)\b.*", it["title"])):
        it["title"] = title  # replace a file-name title (e.g. "29 pin 2746…"); keep one the person wrote
    it["analysis"] = out
    it["analysed"] = dt.datetime.now().isoformat(timespec="seconds")
    save(d)
    return it


def clear_analysis(uid):
    d = load()
    it = next((x for x in d["items"] if x["id"] == uid), None)
    if not it:
        raise KeyError(f"no upload {uid}")
    it.pop("analysis", None); it.pop("analysed", None)
    save(d)


def pending():
    return [x for x in items() if not x.get("analysis")]


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    opt = lambda k: a[a.index(k) + 1] if k in a else None
    if a[0] == "list":
        for x in items():
            print(f"uploads/{x['id']}  {x['kind']:<5} {x['title'][:50]:<50} {x['file']}")
    elif a[0] == "add":
        srcs = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and not a[i - 1].startswith("--")]
        kw = {"title": opt("--title") or "", "note": opt("--note") or "", "tags": (opt("--tags") or "").split(","), "by": "claude"}
        for s in srcs:
            it = add_url(s, **kw) if re.match(r"https?://", s) else add_path(s, **kw)
            print(f"uploads/{it['id']}  {it['file']}")
    elif a[0] == "edit":
        print(update(a[1], {k: opt(f"--{k}") for k in ("title", "note", "tags") if opt(f"--{k}") is not None}))
    elif a[0] == "pending":
        for x in pending():
            print(f"{x['id']}  {x['kind']:<5} look at: {os.path.relpath(sheet(x), ROOT)}   ({x['title']}{', note: ' + x['note'] if x.get('note') else ''})")
    elif a[0] == "set":
        try:
            it = set_analysis(a[1], json.loads(a[2]))
        except (ValueError, KeyError) as e:
            sys.exit(f"not saved: {e}")
        print(f"uploads/{it['id']} analysed: {it['title']}  palette {' '.join(it.get('palette', []))}")
    elif a[0] == "rm":
        print(f"removed {remove(a[1])['file']}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
