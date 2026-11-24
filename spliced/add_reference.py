# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Bring reference videos into the library: download, register, machine pass. Steps 1-3 of
HOW-TO-BREAK-DOWN.md in one command. The breakdown itself (step 4) is written by a person or agent.

usage:
  spliced reference add <url-or-file> [--slug <slug>] [--source "<where it is from>"] [--no-analyze]
  spliced reference rename <old-slug> <new-slug>    # e.g. once the brand of an unknown file is known
  spliced reference status                          # every film: analysed? broken down?

add:
  - URL (YouTube, X, Vimeo, LinkedIn, ...): downloaded with yt-dlp to reference/ as "<title> [<id>].mp4",
    H.264 + AAC up to 1080p (4K kept when the source only offers it as one stream). Already downloaded = reused.
  - Local file: used where it is (copy it into reference/ first if it lives elsewhere).
  - --slug: kebab-case "brand-what" (acme-launch-2025). Without it a slug is suggested from uploader + title;
    pass --slug to choose your own. Slugs are permanent IDs once scenes are referenced, so pick a good one.
"""
import json, os, re, subprocess, sys, unicodedata

import paths

ROOT = paths.ROOT
REF = paths.REFERENCE
LIB = paths.LIB
TSV = paths.REFS_TSV
FORMAT = "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b"


def read_tsv():
    rows = [l.split("\t") for l in open(TSV).read().splitlines() if l.strip()]
    return rows[0], rows[1:]


def write_tsv(head, rows):
    open(TSV, "w").write("\n".join("\t".join(r) for r in [head] + rows) + "\n")


def kebab(s, words=5):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    w = [x for x in re.split(r"[^a-z0-9]+", s) if x and x not in {"the", "a", "an", "and", "of", "for", "with", "is", "your", "now", "here", "introducing"}]
    return "-".join(w[:words]) or "ref"


def download(url):
    meta = json.loads(subprocess.run(["yt-dlp", "-j", "--no-playlist", url], capture_output=True, text=True, check=True).stdout)
    os.makedirs(REF, exist_ok=True)
    r = subprocess.run(["yt-dlp", "--no-playlist", "-f", FORMAT, "--merge-output-format", "mp4", "--remux-video", "mp4",
                        "-o", os.path.join(REF, "%(title)s [%(id)s].%(ext)s"), "--no-progress", url],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"yt-dlp failed for {url}:\n{r.stderr[-2000:]}")
    hits = [f for f in os.listdir(REF) if f.endswith(f"[{meta['id']}].mp4")]
    if not hits:
        sys.exit(f"downloaded {url} but can't find reference/*[{meta['id']}].mp4")
    return os.path.join(REF, hits[0]), meta


def add(src, slug=None, analyze=True, said_source=None):
    if re.match(r"https?://", src):
        path, meta = download(src)
        source = meta.get("webpage_url", src).replace("https://", "").replace("www.", "")
        guess = kebab(f"{meta.get('uploader') or ''} {meta.get('title') or ''}")
    else:
        path = os.path.abspath(src)
        if not os.path.exists(path):
            sys.exit(f"no such file: {src}")
        name = os.path.splitext(os.path.basename(path))[0]
        guess = kebab(re.sub(r"\[[^\]]*\]$", "", name))
        m = re.search(r"\[([^\]]+)\]$", name)  # yt-dlp names files "<title> [<id>]"
        if m and re.fullmatch(r"\d{15,}", m.group(1)):
            source = f"x.com status {m.group(1)}"
        elif m and re.fullmatch(r"[A-Za-z0-9_-]{11}", m.group(1)):
            source = f"youtube.com/watch?v={m.group(1)}"
        else:
            source = "unknown"
    rel = os.path.relpath(path, ROOT)
    source = re.sub(r"\s+", " ", said_source).strip() if said_source else source   # where the caller says it came from (a folder import)
    head, rows = read_tsv()
    for r in rows:
        if r[1] == rel:
            print(f"already registered: {r[0]}  ({rel})")
            slug = r[0]; break
    else:
        slug = slug or guess
        if any(r[0] == slug for r in rows):
            sys.exit(f"slug '{slug}' is taken by another file; pass --slug")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
            sys.exit(f"slug '{slug}' must be kebab-case")
        rows.append([slug, rel, source]); write_tsv(head, rows)
        print(f"registered: {slug}  ({rel})")
    done = os.path.exists(os.path.join(LIB, "references", slug, "analysis.json"))
    if analyze and not done:
        subprocess.run(["uv", "run", "-q", paths.tool("analyze_reference"), "analyze", path, slug], check=True)
    elif done:
        print(f"analysis exists: library/references/{slug}/")
    return slug


def rename(old, new):
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", new):
        sys.exit("new slug must be kebab-case")
    head, rows = read_tsv()
    if not any(r[0] == old for r in rows): sys.exit(f"unknown slug {old}")
    if any(r[0] == new for r in rows): sys.exit(f"slug {new} already exists")
    rows = [[new] + r[1:] if r[0] == old else r for r in rows]; write_tsv(head, rows)
    d_old, d_new = os.path.join(LIB, "references", old), os.path.join(LIB, "references", new)
    if os.path.isdir(d_old):
        os.rename(d_old, d_new)
        a = os.path.join(d_new, "analysis.json")
        if os.path.exists(a):
            j = json.load(open(a)); j["slug"] = new; json.dump(j, open(a, "w"), indent=1)
    hits = [p for p in ["STYLES.md", "README.md"] if old in open(os.path.join(LIB, p)).read()]
    print(f"renamed {old} -> {new}" + (f". Update references in: {', '.join(hits)}" if hits else ""))


def status():
    _, rows = read_tsv(); pending = []
    for slug, rel, *_ in rows:
        d = os.path.join(LIB, "references", slug)
        a = os.path.exists(os.path.join(d, "analysis.json")); b = os.path.exists(os.path.join(d, "breakdown.json"))
        dur = json.load(open(os.path.join(d, "analysis.json")))["duration"] if a else 0
        print(f"{slug:32} {dur:6.1f}s  analysed {'yes' if a else 'NO '}  breakdown {'yes' if b else 'NO'}")
        if not b: pending.append(slug)
    print(f"\n{len(rows)} films, {len(pending)} without a breakdown" + (f": {' '.join(pending)}" if pending else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("add", "rename", "status"):
        sys.exit(__doc__)
    if a[0] == "status":
        status()
    elif a[0] == "rename":
        rename(a[1], a[2])
    else:
        slug = a[a.index("--slug") + 1] if "--slug" in a else None
        said = a[a.index("--source") + 1] if "--source" in a else None
        srcs = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and a[i - 1] not in ("--slug", "--source")]
        if (slug or said) and len(srcs) > 1:
            sys.exit("--slug and --source work with one source at a time")
        for s in srcs:
            add(s, slug, "--no-analyze" not in a, said)
