# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Real footage and photos from free libraries, so not everything has to be generated.

Sources (free; the ones marked "key" need a free API key in the environment or in .env at the repo root):
  pexels     photos + videos   key PEXELS_API_KEY       Pexels License: free, commercial use, no attribution required
  pixabay    photos + videos   key PIXABAY_API_KEY      Pixabay Content License: free, commercial use
  unsplash   photos            key UNSPLASH_ACCESS_KEY  Unsplash License; the API asks to credit the photographer
  nasa       photos + videos   no key                   NASA Image and Video Library: generally public domain
  openverse  photos            no key                   Creative Commons (license per item, commercial-use only)

usage:
  spliced stock sources
  spliced stock search "studio photoshoot" [--kind photo|video] [--source pexels,nasa] [--n 20]
  spliced stock get pexels:video:12345 --film companion [--name photoshoot]

`get` downloads into remotion/public/films/<film>/stock/ and records the source, author, licence and page in the
film's assets.json, so Spliced's Assets view shows where it came from. Depicted people, brands and logos
can still carry rights of their own: check before a person or a trademark is the subject of a shot.
"""
import datetime, json, os, re, sys, urllib.parse, urllib.request

import paths

ROOT = paths.ROOT
UA = {"User-Agent": "Spliced/1.0 (motion design library tool)"}
LICENSES = {
    "pexels": ("Pexels License", "https://www.pexels.com/license/"),
    "pixabay": ("Pixabay Content License", "https://pixabay.com/service/license-summary/"),
    "unsplash": ("Unsplash License", "https://unsplash.com/license"),
    "nasa": ("NASA media guidelines (generally public domain)", "https://www.nasa.gov/nasa-brand-center/images-and-media/"),
}


def env(name):
    if os.environ.get(name):
        return os.environ[name]
    p = paths.ENV
    if os.path.exists(p):
        for line in open(p):
            k, _, v = line.strip().partition("=")
            if k.strip() == name:
                return v.strip().strip('"\'')
    return ""


KEYS = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY", "unsplash": "UNSPLASH_ACCESS_KEY"}
KINDS = {"pexels": ("photo", "video"), "pixabay": ("photo", "video"), "unsplash": ("photo",), "nasa": ("photo", "video"), "openverse": ("photo",)}


def sources():
    return [{"id": s, "kinds": list(KINDS[s]), "ready": not KEYS.get(s) or bool(env(KEYS[s])), "key": KEYS.get(s, "")} for s in KINDS]


def set_key(source, value):
    """Save a library's API key in the project's .env (apikeys.py; git ignores it). The next search uses it."""
    if not KEYS.get(source):
        raise ValueError(f"{source} doesn't need a key")
    import apikeys
    return {"source": source, "key": apikeys.set_key(source, value)["env"]}


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def q(params):
    return urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})


def item(**kw):
    lic = LICENSES.get(kw["source"], ("", ""))
    return {"license": lic[0], "license_url": lic[1], "duration": None, "preview": None, **kw}


# ---------- providers: each returns normalised items ----------
def pexels(query, kind, n):
    h = {"Authorization": env("PEXELS_API_KEY")}
    if kind == "video":
        d = get_json(f"https://api.pexels.com/v1/videos/search?{q({'query': query, 'per_page': n})}", h)
        out = []
        for v in d.get("videos", []):
            files = sorted([f for f in v.get("video_files", []) if f.get("width")], key=lambda f: f["width"])
            best = next((f for f in files if f["width"] >= 1920), files[-1] if files else None)
            small = next((f for f in files if f["width"] >= 480), best)
            if not best:
                continue
            out.append(item(id=f"pexels:video:{v['id']}", source="pexels", kind="video", title=re.sub(r"[-/]", " ", v.get("url", "").rstrip("/").split("/")[-1]).strip(),
                            author=(v.get("user") or {}).get("name", ""), author_url=(v.get("user") or {}).get("url", ""), page=v.get("url", ""),
                            thumb=v.get("image"), preview=small and small["link"], download=best["link"], ext="mp4",
                            width=best["width"], height=best.get("height"), duration=v.get("duration")))
        return out
    d = get_json(f"https://api.pexels.com/v1/search?{q({'query': query, 'per_page': n})}", h)
    return [item(id=f"pexels:photo:{p['id']}", source="pexels", kind="photo", title=p.get("alt") or "", author=p.get("photographer", ""),
                 author_url=p.get("photographer_url", ""), page=p.get("url", ""), thumb=p["src"]["medium"], download=p["src"]["original"], ext="jpg",
                 width=p.get("width"), height=p.get("height")) for p in d.get("photos", [])]


def pixabay(query, kind, n):
    key = env("PIXABAY_API_KEY")
    if kind == "video":
        d = get_json(f"https://pixabay.com/api/videos/?{q({'key': key, 'q': query, 'per_page': max(3, n), 'safesearch': 'true'})}")
        out = []
        for v in d.get("hits", []):
            vs = v.get("videos", {})
            best = vs.get("large") if (vs.get("large") or {}).get("url") else vs.get("medium")
            small = vs.get("tiny") or vs.get("small") or best
            out.append(item(id=f"pixabay:video:{v['id']}", source="pixabay", kind="video", title=v.get("tags", ""), author=v.get("user", ""),
                            author_url=f"https://pixabay.com/users/{v.get('user')}-{v.get('user_id')}/", page=v.get("pageURL", ""),
                            thumb=(small or {}).get("thumbnail") or "", preview=(small or {}).get("url"), download=best["url"], ext="mp4",
                            width=best.get("width"), height=best.get("height"), duration=v.get("duration")))
        return out
    d = get_json(f"https://pixabay.com/api/?{q({'key': key, 'q': query, 'per_page': max(3, n), 'safesearch': 'true', 'image_type': 'photo'})}")
    return [item(id=f"pixabay:photo:{p['id']}", source="pixabay", kind="photo", title=p.get("tags", ""), author=p.get("user", ""),
                 author_url=f"https://pixabay.com/users/{p.get('user')}-{p.get('user_id')}/", page=p.get("pageURL", ""), thumb=p.get("webformatURL"),
                 download=p.get("largeImageURL"), ext="jpg", width=p.get("imageWidth"), height=p.get("imageHeight")) for p in d.get("hits", [])]


def unsplash(query, kind, n):
    if kind == "video":
        return []
    d = get_json(f"https://api.unsplash.com/search/photos?{q({'query': query, 'per_page': n})}", {"Authorization": f"Client-ID {env('UNSPLASH_ACCESS_KEY')}", "Accept-Version": "v1"})
    return [item(id=f"unsplash:photo:{p['id']}", source="unsplash", kind="photo", title=p.get("alt_description") or p.get("description") or "",
                 author=p["user"]["name"], author_url=p["user"]["links"]["html"] + "?utm_source=cutting_room&utm_medium=referral",
                 page=p["links"]["html"] + "?utm_source=cutting_room&utm_medium=referral", thumb=p["urls"]["small"],
                 download=p["urls"]["raw"] + "&w=2560&q=85&fm=jpg", ext="jpg", width=p.get("width"), height=p.get("height"),
                 track=p["links"].get("download_location")) for p in d.get("results", [])]


def nasa(query, kind, n):
    d = get_json(f"https://images-api.nasa.gov/search?{q({'q': query, 'media_type': 'video' if kind == 'video' else 'image', 'page_size': n})}")
    out = []
    for it in d.get("collection", {}).get("items", [])[:n]:
        data = (it.get("data") or [{}])[0]
        thumb = next((l["href"] for l in it.get("links", []) if l.get("rel") == "preview"), "")
        out.append(item(id=f"nasa:{kind}:{data.get('nasa_id')}", source="nasa", kind=kind, title=data.get("title", ""),
                        author=data.get("center") or data.get("photographer") or "NASA", author_url="",
                        page=f"https://images.nasa.gov/details/{urllib.parse.quote(data.get('nasa_id', ''))}", thumb=thumb,
                        download=None, ext="mp4" if kind == "video" else "jpg", width=None, height=None,
                        preview=safe_url(f"https://images-assets.nasa.gov/video/{data.get('nasa_id')}/{data.get('nasa_id')}~preview.mp4") if kind == "video" else None,
                        manifest=it.get("href")))
    return out


def openverse(query, kind, n):
    if kind == "video":
        return []
    d = get_json(f"https://api.openverse.org/v1/images/?{q({'q': query, 'page_size': n, 'license_type': 'commercial,modification'})}")
    return [item(id=f"openverse:photo:{r['id']}", source="openverse", kind="photo", title=r.get("title", ""), author=r.get("creator") or "",
                 author_url=r.get("creator_url") or "", page=r.get("foreign_landing_url") or "", thumb=r.get("thumbnail") or r.get("url"),
                 download=r.get("url"), ext=(r.get("filetype") or "jpg").replace("jpeg", "jpg"), width=r.get("width"), height=r.get("height"),
                 license=f"CC {r.get('license', '').upper()} {r.get('license_version', '')}".strip(), license_url=r.get("license_url") or "",
                 credit=r.get("attribution") or "") for r in d.get("results", [])]


PROVIDERS = {"pexels": pexels, "pixabay": pixabay, "unsplash": unsplash, "nasa": nasa, "openverse": openverse}


def search(query, kind="video", only=None, n=18):
    """Search every ready source (or `only`) at once; one failing source doesn't stop the others."""
    from concurrent.futures import ThreadPoolExecutor
    srcs = [s for s in sources() if s["ready"] and kind in s["kinds"] and (not only or s["id"] in only)]
    results, errors = [], {}

    def one(s):
        try:
            return s["id"], PROVIDERS[s["id"]](query, kind, n)
        except Exception as e:  # noqa: BLE001
            return s["id"], e
    with ThreadPoolExecutor(max_workers=5) as ex:
        for sid, r in ex.map(one, srcs):
            if isinstance(r, Exception):
                errors[sid] = str(r)[:200]
            else:
                results.append(r)
    # interleave the sources so one library doesn't fill the first screen
    out = [x for group in zip_longest(*results) for x in group if x]
    return {"query": query, "kind": kind, "results": out, "errors": errors,
            "missing": [s["id"] for s in sources() if not s["ready"] and kind in s["kinds"]]}


def zip_longest(*lists):
    m = max([len(l) for l in lists] or [0])
    return [[l[i] if i < len(l) else None for l in lists] for i in range(m)]


def resolve(sid):
    """A result again from its id (source:kind:id), with a download URL."""
    src, kind, ident = sid.split(":", 2)
    if src == "nasa":
        files = get_json(f"https://images-api.nasa.gov/asset/{urllib.parse.quote(ident, safe='')}")["collection"]["items"]
        hrefs = [f["href"] for f in files]
        pick = ([h for h in hrefs if h.endswith("~large.mp4")] + [h for h in hrefs if h.endswith("~orig.mp4")] + [h for h in hrefs if h.endswith(".mp4")]) if kind == "video" else \
               ([h for h in hrefs if h.endswith("~large.jpg")] + [h for h in hrefs if h.endswith("~orig.jpg")] + [h for h in hrefs if h.endswith(".jpg")])
        if not pick:
            raise ValueError(f"NASA has no {kind} file for {ident}")
        data = get_json(f"https://images-api.nasa.gov/search?{q({'nasa_id': ident})}")["collection"]["items"][0]["data"][0]
        return item(id=sid, source="nasa", kind=kind, title=data.get("title", ""), author=data.get("center") or "NASA", author_url="",
                    page=f"https://images.nasa.gov/details/{urllib.parse.quote(ident)}", thumb="", download=pick[0].replace("http://", "https://"),
                    ext="mp4" if kind == "video" else "jpg", width=None, height=None)
    if src == "pexels":
        h = {"Authorization": env("PEXELS_API_KEY")}
        if kind == "video":
            v = get_json(f"https://api.pexels.com/v1/videos/videos/{ident}", h)
            return pexels_one_video(v)
        p = get_json(f"https://api.pexels.com/v1/photos/{ident}", h)
        return item(id=sid, source="pexels", kind="photo", title=p.get("alt") or "", author=p.get("photographer", ""), author_url=p.get("photographer_url", ""),
                    page=p.get("url", ""), thumb=p["src"]["medium"], download=p["src"]["original"], ext="jpg", width=p.get("width"), height=p.get("height"))
    if src == "pixabay":
        key = env("PIXABAY_API_KEY")
        d = get_json(f"https://pixabay.com/api/{'videos/' if kind == 'video' else ''}?{q({'key': key, 'id': ident})}")
        hit = d["hits"][0]
        return (pixabay_hits_video(hit) if kind == "video" else
                item(id=sid, source="pixabay", kind="photo", title=hit.get("tags", ""), author=hit.get("user", ""), author_url="", page=hit.get("pageURL", ""),
                     thumb=hit.get("webformatURL"), download=hit.get("largeImageURL"), ext="jpg", width=hit.get("imageWidth"), height=hit.get("imageHeight")))
    if src == "unsplash":
        p = get_json(f"https://api.unsplash.com/photos/{ident}", {"Authorization": f"Client-ID {env('UNSPLASH_ACCESS_KEY')}", "Accept-Version": "v1"})
        return item(id=sid, source="unsplash", kind="photo", title=p.get("alt_description") or "", author=p["user"]["name"],
                    author_url=p["user"]["links"]["html"], page=p["links"]["html"], thumb=p["urls"]["small"],
                    download=p["urls"]["raw"] + "&w=2560&q=85&fm=jpg", ext="jpg", width=p.get("width"), height=p.get("height"), track=p["links"].get("download_location"))
    if src == "openverse":
        r = get_json(f"https://api.openverse.org/v1/images/{ident}/")
        return item(id=sid, source="openverse", kind="photo", title=r.get("title", ""), author=r.get("creator") or "", author_url=r.get("creator_url") or "",
                    page=r.get("foreign_landing_url") or "", thumb=r.get("thumbnail"), download=r.get("url"), ext=(r.get("filetype") or "jpg").replace("jpeg", "jpg"),
                    width=r.get("width"), height=r.get("height"), license=f"CC {r.get('license', '').upper()} {r.get('license_version', '')}".strip(),
                    license_url=r.get("license_url") or "", credit=r.get("attribution") or "")
    raise ValueError(f"unknown source {src}")


def pexels_one_video(v):
    files = sorted([f for f in v.get("video_files", []) if f.get("width")], key=lambda f: f["width"])
    best = next((f for f in files if f["width"] >= 1920), files[-1])
    return item(id=f"pexels:video:{v['id']}", source="pexels", kind="video", title=v.get("url", "").rstrip("/").split("/")[-1].replace("-", " "),
                author=(v.get("user") or {}).get("name", ""), author_url=(v.get("user") or {}).get("url", ""), page=v.get("url", ""), thumb=v.get("image"),
                download=best["link"], ext="mp4", width=best["width"], height=best.get("height"), duration=v.get("duration"))


def pixabay_hits_video(v):
    vs = v.get("videos", {})
    best = vs.get("large") if (vs.get("large") or {}).get("url") else vs.get("medium")
    return item(id=f"pixabay:video:{v['id']}", source="pixabay", kind="video", title=v.get("tags", ""), author=v.get("user", ""), author_url="",
                page=v.get("pageURL", ""), thumb="", download=best["url"], ext="mp4", width=best.get("width"), height=best.get("height"), duration=v.get("duration"))


def safe_url(u):
    """Percent-encode a URL's path and query (NASA ids can hold spaces and characters like "…")."""
    p = urllib.parse.urlsplit(u)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(urllib.parse.unquote(p.path), safe="/~"),
                                    urllib.parse.quote(urllib.parse.unquote(p.query), safe="=&"), p.fragment))


def shrink(path, limit_mb=40):
    """Big clips (NASA masters run to hundreds of MB) re-encoded to 1080p H.264 so the repo can push them (GitHub's
    limit is 100 MB a file). Smaller files and photos are left as they came."""
    if not path.endswith(".mp4") or os.path.getsize(path) < limit_mb * 1e6:
        return
    import subprocess
    tmp = path[:-4] + ".small.mp4"
    try:  # long clips (a 4-minute NASA feature) get a bitrate cap so the file lands under ~85 MB
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                   capture_output=True, text=True).stdout.strip())
    except ValueError:
        dur = 0
    cap = int(min(12e6, 85e6 * 8 / dur - 200e3)) if dur else int(12e6)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf", "scale='min(1920,iw)':-2", "-c:v", "libx264", "-crf", "21",
                        "-maxrate", str(max(cap, 1_000_000)), "-bufsize", str(2 * max(cap, 1_000_000)),
                        "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", tmp],
                       capture_output=True, text=True)
    if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) < os.path.getsize(path):
        os.replace(tmp, path)
    elif os.path.exists(tmp):
        os.remove(tmp)


def slugify(s, n=40):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:n].strip("-")


def get(sid, film, name=None):
    """Download one result into the film's stock/ folder and record where it came from in assets.json."""
    if not re.fullmatch(r"[\w.-]+", film or ""):
        raise ValueError("give the film's slug, e.g. companion")
    src_dir = os.path.join(ROOT, "remotion", "src", "films", film)
    if not os.path.isdir(src_dir):
        raise ValueError(f"no Remotion film called {film}")
    it = resolve(sid)
    if not it.get("download"):
        raise ValueError("this result has no downloadable file")
    out_dir = os.path.join(ROOT, "remotion", "public", "films", film, "stock")
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{it['source']}-{slugify(name or it['title']) or it['kind']}-{slugify(sid.split(':', 2)[-1], 12) or 'x'}.{it['ext']}"
    path = os.path.join(out_dir, fname)
    if not os.path.exists(path):
        req = urllib.request.Request(safe_url(it["download"]), headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r, open(path + ".part", "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        os.replace(path + ".part", path)
        shrink(path)
        if it.get("track") and env("UNSPLASH_ACCESS_KEY"):  # Unsplash asks apps to report downloads
            try:
                get_json(it["track"], {"Authorization": f"Client-ID {env('UNSPLASH_ACCESS_KEY')}"})
            except Exception:  # noqa: BLE001
                pass
    under = os.path.relpath(path, os.path.join(ROOT, "remotion", "public"))
    mp = os.path.join(src_dir, "assets.json")
    meta = {}
    if os.path.exists(mp):
        meta = json.load(open(mp))
    meta.setdefault("_note", "What made each asset: source, model or author, prompt, credits, licence. Keys are paths under remotion/public (what staticFile() takes). Spliced's Assets view reads this.")
    meta[under] = {"source": it["source"], "label": it["title"][:120], "author": it["author"], "author_url": it.get("author_url", ""),
                   "page": it["page"], "license": it["license"], "license_url": it["license_url"], **({"credit": it["credit"]} if it.get("credit") else {}),
                   "stock_id": sid}
    tmp = mp + ".tmp"
    json.dump(meta, open(tmp, "w"), indent=2, ensure_ascii=False)
    os.replace(tmp, mp)
    return {"file": os.path.relpath(path, ROOT), "path": under, "item": it}


# ---------- your own files, uploaded from the computer into a film (Spliced's Assets, "Upload") ----------
# the kinds the Assets view lists (film.py MEDIA_EXT), so whatever is added shows there
MEDIA = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif",
         "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov", "video/x-m4v": ".m4v", "audio/mpeg": ".mp3", "audio/wav": ".wav",
         "audio/x-wav": ".wav", "audio/aac": ".aac", "audio/mp4": ".m4a", "audio/ogg": ".ogg"}
MEDIA_EXT = tuple(sorted(set(MEDIA.values()) | {".jpeg"}))
MAX_FILE = 95e6  # GitHub refuses files over 100 MB


def _record(film, path, entry):
    src_dir = os.path.join(ROOT, "remotion", "src", "films", film)
    under = os.path.relpath(path, os.path.join(ROOT, "remotion", "public"))
    mp = os.path.join(src_dir, "assets.json")
    meta = json.load(open(mp)) if os.path.exists(mp) else {}
    meta.setdefault("_note", "What made each asset: source, model or author, prompt, credits, licence. Keys are paths under remotion/public (what staticFile() takes). Spliced's Assets view reads this.")
    meta[under] = entry
    json.dump(meta, open(mp + ".tmp", "w"), indent=2, ensure_ascii=False)
    os.replace(mp + ".tmp", mp)
    return under


def add_file(film, data, filename, page="", label=""):
    """Put a file of the person's own (a design export, a clip, a sound) into the film's uploads/ folder and record it."""
    if not re.fullmatch(r"[\w.-]+", film or "") or not os.path.isdir(os.path.join(ROOT, "remotion", "src", "films", film)):
        raise ValueError(f"no Remotion film called {film!r}")
    base, ext = os.path.splitext(os.path.basename(filename or "file"))
    ext = ext.lower()
    if ext not in MEDIA_EXT:
        raise ValueError(f"{filename} isn't an image, clip or sound ({', '.join(MEDIA_EXT)})")
    if len(data) > MAX_FILE:
        raise ValueError(f"{len(data) / 1e6:.0f} MB is too big for the repo (under 95 MB, please)")
    out_dir = os.path.join(ROOT, "remotion", "public", "films", film, "uploads")
    os.makedirs(out_dir, exist_ok=True)
    name = (slugify(base, 60) or "upload") + (".jpg" if ext == ".jpeg" else ext)
    path, i = os.path.join(out_dir, name), 2
    while os.path.exists(path):
        path = os.path.join(out_dir, f"{os.path.splitext(name)[0]}-{i}{os.path.splitext(name)[1]}"); i += 1
    with open(path, "wb") as f:
        f.write(data)
    shrink(path)
    under = _record(film, path, {"source": "upload", "label": (label or base.replace("-", " ").replace("_", " ")).strip()[:120],
                                 **({"page": page} if page else {}), "added": datetime.date.today().isoformat()})
    return {"file": os.path.relpath(path, ROOT), "path": under}


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "sources":
        for s in sources():
            print(f"{s['id']:<10} {'/'.join(s['kinds']):<12} {'ready' if s['ready'] else 'needs ' + s['key']}")
    elif a[0] == "search":
        kind = a[a.index("--kind") + 1] if "--kind" in a else "video"
        only = a[a.index("--source") + 1].split(",") if "--source" in a else None
        n = int(a[a.index("--n") + 1]) if "--n" in a else 12
        r = search(a[1], kind, only, n)
        for x in r["results"]:
            print(f"{x['id']:<34} {x['author'][:20]:<20} {(str(x.get('duration') or '') + 's') if x.get('duration') else '':<5} {x['title'][:60]}")
        for k, v in r["errors"].items():
            print(f"! {k}: {v}")
        if r["missing"]:
            print(f"(no key yet: {', '.join(r['missing'])})")
    elif a[0] == "get":
        film = a[a.index("--film") + 1] if "--film" in a else ""
        name = a[a.index("--name") + 1] if "--name" in a else None
        r = get(a[1], film, name)
        print(f"{r['file']}  ({r['item']['license']}, {r['item']['author']})")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
