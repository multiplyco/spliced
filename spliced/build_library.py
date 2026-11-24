# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pillow", "markdown"]
# ///
"""Validate every library/references/*/breakdown.json against library/TAXONOMY.md, render a frame strip per
scene, write each film's breakdown.md, the cross-film library/INDEX.md, and .cache/library.json (the data
the toolbox app reads: open it with `spliced open`).

usage:
  spliced library            # all films
  spliced library <slug>...  # some films (INDEX.md is still rebuilt from all)
  spliced library --check [<slug>...]   # validate only (all films, or just these), no writing
  spliced library --links               # check film/scene references in STYLES.md and README.md
  spliced library --moves <slug>...     # digest of films' signature moves, for updating STYLES.md
"""
import glob, json, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

ROOT = paths.ROOT
LIB = paths.LIB

FILM_ONE = ["category", "format", "voice"]
FILM_MANY = ["music_feel"]
SCENE_ONE = ["role", "world", "transition_in", "pace", "energy"]
SCENE_MANY = ["subject", "camera", "motion", "type_treatment", "sound_sync", "production"]
INDEXED = ["role", "world", "camera", "motion", "transition_in", "type_treatment", "subject", "production"]


def taxonomy():
    """field -> set of tags, from the '### `field`' sections of TAXONOMY.md."""
    text = open(os.path.join(LIB, "TAXONOMY.md")).read()
    out = {}
    for m in re.finditer(r"^### `([a-z_]+)`(.*?)(?=^#{2,3} |\Z)", text, re.S | re.M):
        field, body = m.group(1), m.group(2)
        out[field] = {t for t in re.findall(r"`([a-z0-9][a-z0-9-]*)`", body) if t != field}
    return out


def tag_definitions():
    """field -> {tag: one-line definition}, from TAXONOMY.md tables (| `tag` | def |) and inline lists (`tag` (def))."""
    text = open(os.path.join(LIB, "TAXONOMY.md")).read(); out = {}
    for m in re.finditer(r"^### `([a-z_]+)`(.*?)(?=^#{2,3} |\Z)", text, re.S | re.M):
        field, body = m.group(1), m.group(2); d = {}
        for tag, df in re.findall(r"^\| `([a-z0-9-]+)` \| (.+?) \|", body, re.M):
            d[tag] = " · ".join(c.strip() for c in df.split(" | "))
        for tag, df in re.findall(r"`([a-z0-9-]+)` \(([^)]*)\)", body):
            d.setdefault(tag, df.strip())
        for tag in re.findall(r"`([a-z0-9][a-z0-9-]*)`", body):
            if tag != field: d.setdefault(tag, "")
        out[field] = d
    return out


def styles_html():
    """STYLES.md as HTML, with links to breakdowns rewritten to toolbox routes."""
    import markdown
    text = open(os.path.join(LIB, "STYLES.md")).read()
    text = re.sub(r"(?m)^(?!\s*[-*] |\s*$)(.+)\n(\s*[-*] )", r"\1\n\n\2", text)  # Python-Markdown needs a blank line before a list
    text = re.sub(r"\(references/([a-z0-9-]+)/breakdown\.md#(s\d+)\)", r"(#/scene/\1/\2)", text)
    text = re.sub(r"\(references/([a-z0-9-]+)/breakdown\.md\)", r"(#/film/\1)", text)
    return markdown.markdown(text, extensions=["tables"])


REF_LINK = re.compile(r"\[([^\]]+)\]\(references/([a-z0-9-]+)/breakdown\.md(?:#(s\d+))?\)(?:\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\))?")


def _inline(md):
    """One fragment of STYLES.md as inline HTML (links to toolbox routes)."""
    import markdown
    md = re.sub(r"\(references/([a-z0-9-]+)/breakdown\.md#(s\d+)\)", r"(#/scene/\1/\2)", md)
    md = re.sub(r"\(references/([a-z0-9-]+)/breakdown\.md\)", r"(#/film/\1)", md)
    html = markdown.markdown(md, extensions=["tables"]).strip()
    return re.sub(r"^<p>(.*)</p>$", r"\1", html, flags=re.S)


def _refs(md, films=()):
    """Scene and film references in a fragment: [{film, scene?, label, note?}], plus bare film slugs (pace tiers)."""
    out, seen = [], set()
    for label, film, scene, note in REF_LINK.findall(md):
        k = f"{film}/{scene}" if scene else film
        if k in seen:
            continue
        seen.add(k)
        out.append({"film": film, "scene": scene or None, "label": label, "note": note or None})
    if not out:
        for f in sorted(films, key=lambda f: (md.find(f) if f in md else 1e9)):
            if re.search(rf"(?<![\w-]){re.escape(f)}(?![\w-])", md) and f not in seen:
                seen.add(f)
                m = re.search(rf"{re.escape(f)}\s*\(([^)]*)\)", md)
                out.append({"film": f, "scene": None, "label": f, "note": m.group(1) if m else None})
    return out


def styles_data(slugs=()):
    """STYLES.md as structured sections for the toolbox's visual Styles view. STYLES.md stays the source:
    ## N. Section -> {n, title, intro, kind}; ### Look -> items with text, bullets (**Label:** text) and refs;
    tables -> cols + rows with each cell's text and refs; anything else -> html."""
    text = open(os.path.join(LIB, "STYLES.md")).read()
    head, *parts = re.split(r"(?m)^## ", text)
    intro = "\n".join(l for l in head.splitlines()[1:] if l.strip() and l.strip() != "---")
    sections = []
    for p in parts:
        title_line, _, body = p.partition("\n")
        m = re.match(r"(\d+)\.\s*(.+)", title_line.strip())
        n, title = (int(m.group(1)), m.group(2)) if m else (None, title_line.strip())
        body = re.sub(r"(?m)^---\s*$", "", body)
        sec = {"n": n, "title": title, "id": re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")}
        if re.search(r"(?m)^### ", body):
            pre, *items = re.split(r"(?m)^### ", body)
            sec.update(kind="looks", intro=_inline(pre.strip()) if pre.strip() else "", items=[])
            for it in items:
                ititle, _, ibody = it.partition("\n")
                lines = ibody.strip().splitlines()
                desc = " ".join(l.strip() for l in lines if l.strip() and not l.lstrip().startswith("- "))
                bullets, cur = [], None
                for l in lines:
                    if l.lstrip().startswith("- "):
                        cur = l.strip()[2:]; bullets.append(cur)
                    elif cur is not None and l.startswith("  "):
                        bullets[-1] += " " + l.strip()
                det = []
                for b in bullets:
                    bm = re.match(r"\*\*([^*]+?):?\*\*:?\s*(.*)", b)
                    det.append({"label": bm.group(1).rstrip(":") if bm else "", "html": _inline(bm.group(2) if bm else b),
                                "refs": _refs(b)})
                sec["items"].append({"title": ititle.strip(), "html": _inline(desc), "details": det,
                                     "refs": [r for d in det for r in d["refs"]]})
        elif re.search(r"(?m)^\|.*\|\s*$", body):
            lines = body.strip().splitlines()
            t0 = next(i for i, l in enumerate(lines) if l.startswith("|"))
            t1 = t0
            while t1 < len(lines) and lines[t1].startswith("|"):
                t1 += 1
            row = lambda l: [c.strip() for c in l.strip().strip("|").split(" | ")]
            cols = row(lines[t0])
            rows = []
            for l in lines[t0 + 2:t1]:
                cells = row(l)
                rows.append({"cells": [_inline(c) for c in cells], "plain": [re.sub(r"\*\*|\*|`", "", REF_LINK.sub(lambda m: m.group(1), c)) for c in cells],
                             "refs": [r for c in cells for r in _refs(c, slugs)]})
            sec.update(kind="table", intro=_inline("\n".join(lines[:t0]).strip()) if "".join(lines[:t0]).strip() else "",
                       cols=cols, rows=rows, outro=_inline("\n".join(lines[t1:]).strip()) if "".join(lines[t1:]).strip() else "")
        else:
            body2 = re.sub(r"(?m)^(?!\s*[-*] |\s*$)(.+)\n(\s*[-*] )", r"\1\n\n\2", body)
            sec.update(kind="prose", html=_inline(body2.strip()), refs=_refs(body))
        sections.append(sec)
    return {"intro": _inline(intro), "sections": sections}


def write_toolbox_data(films):
    keep = ["slug", "title", "brand", "source", "file", "duration", "format", "category", "voice", "music_feel",
            "summary", "tempo", "structure", "style_signature", "signature_moves", "takeaways", "scenes"]
    out = []
    for b in sorted(films, key=lambda b: b["slug"]):
        f = {k: b[k] for k in keep if k in b}
        ap = os.path.join(LIB, "references", b["slug"], "analysis.json")
        if os.path.exists(ap):
            a = json.load(open(ap)); f.update(fps=a.get("fps"), width=a.get("width"), height=a.get("height"))
        out.append(f)
    data = {"films": out,
            "fields": {"film": FILM_ONE + FILM_MANY, "scene": SCENE_ONE + SCENE_MANY},
            "tags": tag_definitions(), "styles_html": styles_html(), "styles": styles_data([b["slug"] for b in films])}
    # generated, so it lives in the project's cache, not in git; the server hands it to the app as /api/library.js
    os.makedirs(os.path.dirname(paths.LIBRARY_JSON), exist_ok=True)
    tmp = paths.LIBRARY_JSON + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, paths.LIBRARY_JSON)


def validate(b, tax):
    errs = []
    def chk(field, val, where):
        vals = val if isinstance(val, list) else [val]
        for v in vals:
            if v not in tax.get(field, ()):
                errs.append(f"{where}: {field} '{v}' is not in TAXONOMY.md")
    for f in FILM_ONE + FILM_MANY:
        if f not in b: errs.append(f"film: missing {f}")
        else: chk(f, b[f], "film")
    if not b.get("scenes"):
        errs.append("film: no scenes")
    prev_end = 0.0
    for s in b.get("scenes", []):
        w = s.get("id", "?")
        for f in SCENE_ONE + SCENE_MANY:
            if f not in s: errs.append(f"{w}: missing {f}")
            else: chk(f, s[f], w)
        for f in ["start", "end", "title", "on_screen", "how_it_moves", "recreate", "steal"]:
            if f not in s: errs.append(f"{w}: missing {f}")
        if "start" in s and "end" in s:
            if s["end"] <= s["start"]: errs.append(f"{w}: end <= start")
            if abs(s["start"] - prev_end) > 0.15: errs.append(f"{w}: starts at {s['start']} but previous ended {prev_end} (gap/overlap)")
            prev_end = s["end"]
    for mv in b.get("signature_moves", []):
        ids = {s["id"] for s in b.get("scenes", [])}
        for sid in mv.get("scenes", []):
            if sid not in ids: errs.append(f"signature move '{mv.get('name')}': unknown scene {sid}")
    return errs


def ts(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def render_strips(b, d):
    from analyze_reference import strip
    os.makedirs(os.path.join(d, "scenes"), exist_ok=True)
    video = os.path.join(ROOT, b["file"])
    # scenes/.ranges.json remembers which time range each strip was rendered from, so only changed scenes re-render
    ranges_p = os.path.join(d, "scenes", ".ranges.json")
    ranges = json.load(open(ranges_p)) if os.path.exists(ranges_p) else {}
    for s in b["scenes"]:
        out = os.path.join(d, "scenes", f"{s['id']}.jpg")
        key = f"{s['start']:.3f}-{s['end']:.3f}"
        if os.path.exists(out) and ranges.get(s["id"]) == key:
            continue
        dur = s["end"] - s["start"]; n = 3 if dur <= 2.5 else 4 if dur <= 5 else 5
        pad = min(0.08, dur * 0.1)
        strip(video, s["start"] + pad, s["end"] - pad, n, out)
        ranges[s["id"]] = key
    ids = {s["id"] for s in b["scenes"]}
    for f in os.listdir(os.path.join(d, "scenes")):  # drop strips of scenes that no longer exist
        if f.endswith(".jpg") and f[:-4] not in ids:
            os.remove(os.path.join(d, "scenes", f))
    json.dump({k: v for k, v in ranges.items() if k in ids}, open(ranges_p, "w"), indent=0)


def tags(s, fields):
    out = []
    for f in fields:
        v = s.get(f); v = v if isinstance(v, list) else [v]
        out += [f"`{x}`" for x in v if x]
    return " ".join(out)


def film_md(b):
    L = [f"# {b['title']}", "",
         f"**{b.get('brand', '')}** · {b['category']} · {b['format']} · {ts(b['duration'])} · voice: {b['voice']} · "
         f"music: {', '.join(b['music_feel'])}", "",
         f"Source: {b.get('source', '')} · File: `{b['file']}`", "", b.get("summary", ""), ""]
    t = b.get("tempo", {})
    if t:
        L += ["## Tempo", "", f"- BPM: {t.get('bpm', 'n/a')} · average shot {t.get('avg_shot_s', 'n/a')}s · "
              f"{t.get('cuts_per_min', 'n/a')} cuts/min", f"- {t.get('notes', '')}", ""]
    if b.get("structure"):
        L += ["## Structure", "", b["structure"], ""]
    sig = b.get("style_signature", {})
    if sig:
        L += ["## Style signature", ""]
        for k, v in sig.items():
            if k == "palette":
                v = " ".join(f"`{p['hex']}` {p.get('name', '')}".strip() for p in v)
            L.append(f"- **{k.replace('_', ' ').capitalize()}:** {v}")
        L.append("")
    if b.get("signature_moves"):
        L += ["## Signature moves", ""]
        for m in b["signature_moves"]:
            L += [f"### {m['name']} ({', '.join(m.get('scenes', []))})", "", m.get("description", ""), "",
                  f"*Recreate:* {m.get('recreate', '')}", ""]
    L += ["## Scenes", "", "| ID | Time | Scene | Role | Steal |", "| --- | --- | --- | --- | --- |"]
    for s in b["scenes"]:
        L.append(f"| [{s['id']}](#{s['id']}) | {ts(s['start'])}–{ts(s['end'])} | {s['title']} | `{s['role']}` | {'★' * s['steal']} |")
    L.append("")
    for s in b["scenes"]:
        L += [f"### {s['id']}", "", f"**{s['title']}** · {ts(s['start'])}–{ts(s['end'])} ({s['end'] - s['start']:.1f}s) · "
              f"steal {'★' * s['steal'] or '–'}", "", f"![{s['id']}](scenes/{s['id']}.jpg)", "",
              f"- **Tags:** {tags(s, ['role', 'world', 'pace', 'energy'])} · {tags(s, ['transition_in'])} in",
              f"- **Subject / camera / motion:** {tags(s, ['subject'])} · {tags(s, ['camera'])} · {tags(s, ['motion'])}",
              f"- **Type / sound / production:** {tags(s, ['type_treatment']) or 'none'} · {tags(s, ['sound_sync']) or 'none'} · "
              f"{tags(s, ['production'])}"]
        if s.get("palette"): L.append(f"- **Palette:** {' '.join('`' + p + '`' for p in s['palette'])}")
        L += ["", f"**On screen.** {s['on_screen']}", "", f"**How it moves.** {s['how_it_moves']}", "",
              f"**Recreate.** {s['recreate']}", ""]
    if b.get("takeaways"):
        L += [f"## Takeaways{' for ' + paths.BRAND if paths.BRAND else ''}", ""] + [f"- {x}" for x in b["takeaways"]] + [""]
    return "\n".join(L)


def index_md(films):
    L = ["# Library index", "",
         "Generated by `build_library.py` from every `references/*/breakdown.json`. Don't edit by hand.", "",
         "Point at a scene by its ID, `<film>/<scene>` (for example `some-film/s04`), to recreate it.", "",
         "## Films", "", "| Film | Category | Length | Voice | BPM | Avg shot | Scenes |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for b in sorted(films, key=lambda b: (b["category"], b["slug"])):
        t = b.get("tempo", {})
        L.append(f"| [{b['title']}](references/{b['slug']}/breakdown.md) | `{b['category']}` | {ts(b['duration'])} | "
                 f"{b['voice']} | {t.get('bpm', 'n/a')} | {t.get('avg_shot_s', 'n/a')}s | {len(b['scenes'])} |")
    L += ["", "## Signature moves", "", "The named techniques worth stealing, across all films.", ""]
    for b in sorted(films, key=lambda b: b["slug"]):
        for m in b.get("signature_moves", []):
            refs = ", ".join(f"[{b['slug']}/{sid}](references/{b['slug']}/breakdown.md#{sid})" for sid in m.get("scenes", []))
            L.append(f"- **{m['name']}** ({refs}): {m.get('description', '')}")
    L += ["", "## Best scenes (★★★)", ""]
    for b in sorted(films, key=lambda b: b["slug"]):
        for s in b["scenes"]:
            if s["steal"] >= 3:
                L.append(f"- [{b['slug']}/{s['id']}](references/{b['slug']}/breakdown.md#{s['id']}) {s['title']} · "
                         f"{tags(s, ['world', 'motion'])}")
    for f in INDEXED:
        groups = defaultdict(list)
        for b in films:
            for s in b["scenes"]:
                v = s[f] if isinstance(s[f], list) else [s[f]]
                for x in v:
                    groups[x].append((s["steal"], b["slug"], s))
        L += ["", f"## By {f.replace('_', ' ')}", ""]
        for tag in sorted(groups, key=lambda k: -len(groups[k])):
            items = sorted(groups[tag], key=lambda x: (-x[0], x[1]))
            refs = ", ".join(f"[{slug}/{s['id']}](references/{slug}/breakdown.md#{s['id']}){'★' * st}" for st, slug, s in items)
            L.append(f"- **`{tag}`** ({len(items)}): {refs}")
    return "\n".join(L) + "\n"


def check_links():
    """Every film/scene reference in the hand-written docs must exist. Returns the number of broken ones."""
    scenes = {}
    for p in glob.glob(os.path.join(LIB, "references", "*", "breakdown.json")):
        try:
            scenes[os.path.basename(os.path.dirname(p))] = {s["id"] for s in json.load(open(p))["scenes"]}
        except (json.JSONDecodeError, KeyError):
            pass
    broken = 0
    for doc in ["STYLES.md", "README.md"]:
        text = open(os.path.join(LIB, doc)).read()
        refs = set(re.findall(r"references/([a-z0-9-]+)/breakdown\.md(?:#(s\d+))?", text))
        refs |= {(f, s) for f, s in re.findall(r"`([a-z0-9]+(?:-[a-z0-9]+)+)/(s\d+)", text)}
        for film, sid in sorted(refs):
            if film not in scenes or (sid and sid not in scenes[film]):
                broken += 1; print(f"{doc}: broken reference {film}{'/' + sid if sid else ''}")
    return broken


def moves(slugs):
    """Compact digest of films for updating STYLES.md: category, tempo, worlds, signature moves."""
    from collections import Counter
    for slug in slugs:
        b = json.load(open(os.path.join(LIB, "references", slug, "breakdown.json"))); t = b.get("tempo", {})
        worlds = Counter(s["world"] for s in b["scenes"]).most_common(3)
        print(f"## {slug}: {b['title']} ({b.get('brand', '')})\n{b['category']} · {b['duration']:.0f}s · voice {b['voice']} · "
              f"bpm {t.get('bpm')} · avg shot {t.get('avg_shot_s')}s · worlds {', '.join(f'{w} {n}' for w, n in worlds)}")
        print(f"structure: {b.get('structure', '')}")
        for m in b.get("signature_moves", []):
            print(f"* {m['name']} [{', '.join(m.get('scenes', []))}]: {m.get('description', '')}")
        for s in b["scenes"]:
            if s["steal"] >= 3:
                print(f"  ★★★ {s['id']} {s['title']} · {s['role']} · {s['world']} · {', '.join(s['motion'])}")
        print()


def main():
    args = sys.argv[1:]
    if {"-h", "--help"} & set(args):
        print(__doc__); return
    known_flags = {"--check", "--moves", "--links", "--index-only"}
    bad_flags = [a for a in args if a.startswith("-") and a not in known_flags]
    if bad_flags:
        sys.exit(f"unknown option {bad_flags[0]}; see --help")
    check = "--check" in args; only = [a for a in args if not a.startswith("--")]
    index_only = "--index-only" in args  # only the app's data (.cache/library.json): no strips, no .md files touched
    if "--moves" in args:
        moves(only); return
    if "--links" in args:
        sys.exit(1 if check_links() else 0)
    tax = taxonomy(); films = []; bad = 0
    for p in sorted(glob.glob(os.path.join(LIB, "references", "*", "breakdown.json"))):
        d = os.path.dirname(p); slug = os.path.basename(d)
        try:
            b = json.load(open(p))
        except json.JSONDecodeError as e:
            print(f"{slug}: invalid JSON: {e}"); bad += 1; continue
        b["slug"] = slug
        old = next((k for k in b if k.startswith("takeaways_for_")), None)   # the field once carried a brand's name: still read
        if old:
            b.setdefault("takeaways", b[old])
            del b[old]
        if check and only and slug not in only:
            continue
        errs = validate(b, tax)
        if errs:
            bad += 1; print(f"{slug}: {len(errs)} problem(s)"); [print("  -", e) for e in errs[:40]]
            continue
        films.append(b)
        if check or index_only or (only and slug not in only):
            continue
        render_strips(b, d)
        open(os.path.join(d, "breakdown.md"), "w").write(film_md(b))
        print(f"{slug}: ok, {len(b['scenes'])} scenes")
    if index_only:
        write_toolbox_data(films); print(f"library index written: {len(films)} films")
        sys.exit(1 if bad else 0)
    if not check:
        open(os.path.join(LIB, "INDEX.md"), "w").write(index_md(films))
        print(f"INDEX.md: {len(films)} films")
        if not only:
            write_toolbox_data(films); print("library index written")
    if not only:
        bad += check_links()
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
