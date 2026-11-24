"""Work on Spliced boards from the command line: how Claude builds and edits boards while you watch.

If the toolbox is running (spliced open), changes go through it and appear in every open tab at once;
otherwise they're written to library/state.json and show up next time the app loads (a running toolbox also
picks up the file within ~2s). SPLICED_OFFLINE=1 forces the file path.

  spliced board boards                                  list boards
  spliced board show "Areas launch v1" [--md]           the board as a script (brief, beats, copy, timecode)
  spliced board new "Areas launch v1" [--profile soft] [--folder branding-videos] [--news "..."] [--audience ..] [--aspect 16:9] [--length 40]
                                                        (no --folder: the folder you are in, if you are in one of the project's)
  spliced board brief "Areas launch v1" [--news ..] [--audience ..] [--aspect ..] [--length ..] [--notes ..] [--profile ..]
  spliced board add "Areas launch v1" film/s05 [--time 0:21.40] [--beat hook] [--copy "On-screen words"] [--vo "Voice-over line"] [--seconds 3] [--note ..] [--at 2]
  spliced board edit "Areas launch v1" 3 [--scene film/s07] [--time 0:21.40 | --time none] [--beat ..] [--copy ..] [--vo ..] [--seconds ..] [--note ..]
      --time is the moment inside the scene the beat borrows (seconds or m:ss.xx in the reference film); --at is the beat's position.
  spliced board rm "Areas launch v1" 3
  spliced board mv "Areas launch v1" 3 1
  spliced board rename "Old" "New"      |  delete "Name"
  spliced board folder "Areas launch v1" branding-videos  put it in one of the project's folders (- for none)
  spliced board review film/s05 [--fav | --unfav] [--verdict use|maybe|skip|none] [--note ..]
  spliced board moments                                 the moments the person saved (exact frames: film/sNN @ time)
  spliced board moment acme-launch/s12 0:42.51 ["note"] save a moment
  spliced board moment-rm <uid>                         remove one
  spliced board find "slot reel" [--tag motion=slot-reel] [--tag world=white-stage] [--steal 2] [--film globex] [--limit 15]
  spliced board scene film/s05                          one scene's breakdown, for writing a beat
  spliced board show-in-app "Areas launch v1" | film/s05 [--note "..."]   point the open app at it
  spliced board apply ops.json | -                      a batch of operations (see toolbox_state.py)
"""
import argparse, json, os, sys, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
import toolbox_state as ts

def _url():
    """Where this project's app runs: SPLICED_URL, else what the running server wrote in .cache/server.json, else 8765."""
    try:
        with open(paths.SERVER_FILE) as f:
            port = int(json.load(f)["port"])
    except (OSError, ValueError, KeyError, TypeError):
        port = 8765
    return paths.env("URL", f"http://127.0.0.1:{port}")


URL = _url()
BY = paths.env("BY", "claude")                     # SPLICED_BY: who the changes are signed as


OTHER = [None]  # the project a running toolbox serves, when it isn't ours


def server():
    """The running toolbox, if it serves this project. One that serves another project or worktree is not ours:
    its boards are different boards, so we work on this project's state.json instead."""
    if paths.env("OFFLINE"):  # SPLICED_OFFLINE=1: never talk to a running toolbox, work on state.json
        return None
    try:
        with urllib.request.urlopen(URL + "/api/info", timeout=1.5) as r:
            info = json.load(r)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if os.path.realpath(str(info.get("root") or "")) != paths.ROOT:
        OTHER[0] = info.get("root")
        return None
    return info


def offline_note():
    return f"the toolbox at {URL} serves another project, {OTHER[0]}" if OTHER[0] else "toolbox not running"


def post(path, payload):
    req = urllib.request.Request(URL + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"error: {json.load(e).get('error', e)}")


def state():
    if server():
        with urllib.request.urlopen(URL + "/api/state", timeout=5) as r:
            return ts.normalise(json.load(r))
    return ts.load()


def run(ops, quiet=False):
    info = server()
    if info:
        res = post("/api/ops", {"by": BY, "client": "cli", "ops": ops})
        where = f"live ({info['live_tabs']} tab{'s' if info['live_tabs'] != 1 else ''} open)"
    else:
        try:
            new, results, summary = ts.apply(ts.load(), ops, by=BY, known=ts.known_scenes())
        except ts.OpError as e:
            sys.exit(f"error: {e}")
        ts.save(new)
        res = {"rev": new["rev"], "results": results, "summary": summary}
        where = f"saved to state.json ({offline_note()})"
    if not quiet:
        print(f"{res['summary']}  [rev {res['rev']}, {where}]")
    return res


def library():
    out = {}
    refs = paths.REFS
    for slug in sorted(os.listdir(refs) if os.path.isdir(refs) else []):
        p = os.path.join(refs, slug, "breakdown.json")
        if os.path.exists(p):
            b = json.load(open(p))
            for s in b["scenes"]:
                out[f"{slug}/{s['id']}"] = {**s, "film": slug, "film_title": b["title"], "brand": b.get("brand", "")}
    return out


def tc(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def tcf(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def show(name, md=False):
    st, lib = state(), library()
    if name not in st["boards"]:
        sys.exit(f"no board {name!r}; boards: {', '.join(st['boards']) or 'none'}")
    b = st["boards"][name]
    br = b.get("brief", {})
    total = sum((it.get("seconds") or 0) for it in b["items"])
    L = [f"# {name}", "",
         f"Profile: {b.get('profile', ts.DEFAULT_PROFILE)} · {len(b['items'])} beats · {total:.1f}s scripted" + (f" of {br['length']}s" if br.get("length") else "") + (f" · {br['aspect']}" if br.get("aspect") else ""),
         ""]
    for k in ("news", "audience", "notes"):
        if br.get(k):
            L.append(f"**{k.capitalize()}:** {br[k]}")
    L += ["", "| # | Time | Beat | Scene | On screen | Voice-over | Note |", "| --- | --- | --- | --- | --- | --- | --- |"]
    t = 0.0
    for i, it in enumerate(b["items"], 1):
        sc = lib.get(it["id"], {})
        sec = it.get("seconds")
        span = f"{tc(t)}–{tc(t + sec)}" if sec else f"{tc(t)}"
        t += sec or 0
        at = f" @ {tcf(it['t'])}" if it.get("t") is not None else ""
        L.append(f"| {i} | {span} | {it.get('beat', '')} | `{it['id']}`{at} {sc.get('title', '?')[:48]} | {it.get('copy', '')} | {it.get('vo', '')} | {it.get('note', '')} |")
    vo = " ".join(it.get("vo", "") for it in b["items"] if it.get("vo"))
    if vo:
        words = len(vo.split())
        L += ["", f"Voice-over: {words} words, about {words / 2.5:.0f}s at a calm 150 words a minute" + (f" ({total:.0f}s scripted)" if total else "")]
    text = "\n".join(L)
    if not md:
        text = text.replace("**", "").replace("`", "")
    print(text)


def find(q, tags, steal, film, limit):
    lib, st = library(), state()
    words = q.lower().split() if q else []
    hits = []
    for key, s in lib.items():
        hay = " ".join([key, s["title"], s.get("on_screen", ""), s.get("how_it_moves", ""), s.get("recreate", ""), s["film_title"], s["brand"]]).lower()
        if any(w not in hay for w in words):
            continue
        if film and film not in s["film"]:
            continue
        if s.get("steal", 0) < steal:
            continue
        ok = True
        for t in tags:
            f, v = t.split("=", 1)
            vals = s.get(f, [])
            if v not in (vals if isinstance(vals, list) else [vals]):
                ok = False
        if ok:
            hits.append((s.get("steal", 0), key, s))
    hits.sort(key=lambda x: (-x[0], x[1]))
    for st_, key, s in hits[:limit]:
        r = st["reviews"].get(key, {})
        badge = ("♥ " if r.get("fav") else "") + (r.get("verdict", "") + " " if r.get("verdict") else "")
        print(f"{key:40} {'★' * st_:3} {badge}{s['title'][:70]}\n{'':40}     {s['world']} · {', '.join(s['motion'][:3])} · in: {s['transition_in']} · {s['end'] - s['start']:.1f}s")
    print(f"\n{len(hits)} match{'es' if len(hits) != 1 else ''}" + (f", showing {limit}" if len(hits) > limit else ""))


def scene(key):
    s = library().get(key)
    if not s:
        sys.exit(f"no scene {key!r}")
    r = state()["reviews"].get(key, {})
    print(f"{key}: {s['title']}\n{s['film_title']} ({s['brand']}) {tc(s['start'])}–{tc(s['end'])} · {'★' * s.get('steal', 0)}")
    print(f"role {s['role']} · world {s['world']} · camera {', '.join(s['camera'])} · motion {', '.join(s['motion'])} · in {s['transition_in']}")
    if r:
        print(f"review: {r}")
    for k in ("on_screen", "how_it_moves", "recreate"):
        print(f"\n{k.replace('_', ' ').capitalize()}: {s.get(k, '')}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("boards")
    x = sub.add_parser("show"); x.add_argument("board"); x.add_argument("--md", action="store_true")
    for name in ("new", "brief"):
        x = sub.add_parser(name); x.add_argument("board")
        for f in ("news", "audience", "aspect", "notes", "profile", "folder"):
            x.add_argument(f"--{f}")
        x.add_argument("--length", type=float)
    x = sub.add_parser("add"); x.add_argument("board"); x.add_argument("scene")
    for f in ("beat", "copy", "vo", "note"):
        x.add_argument(f"--{f}")
    x.add_argument("--seconds", type=float); x.add_argument("--at", type=int, help="position on the board (1-based)")
    x.add_argument("--time", help="the moment inside the scene: seconds or m:ss.xx in the reference film")
    x = sub.add_parser("edit"); x.add_argument("board"); x.add_argument("n", type=int); x.add_argument("--scene")
    for f in ("beat", "copy", "vo", "note"):
        x.add_argument(f"--{f}")
    x.add_argument("--seconds", type=float); x.add_argument("--time", help="the moment inside the scene; 'none' clears it")
    x = sub.add_parser("rm"); x.add_argument("board"); x.add_argument("n", type=int)
    x = sub.add_parser("mv"); x.add_argument("board"); x.add_argument("n", type=int); x.add_argument("to", type=int)
    x = sub.add_parser("rename"); x.add_argument("board"); x.add_argument("to")
    x = sub.add_parser("folder", help="put a board in one of the project's folders (- for none)"); x.add_argument("board"); x.add_argument("folder")
    x = sub.add_parser("delete"); x.add_argument("board")
    x = sub.add_parser("review"); x.add_argument("scene"); x.add_argument("--fav", action="store_true"); x.add_argument("--unfav", action="store_true")
    x.add_argument("--verdict"); x.add_argument("--note")
    sub.add_parser("moments")
    x = sub.add_parser("moment"); x.add_argument("scene"); x.add_argument("time"); x.add_argument("note", nargs="?", default="")
    x = sub.add_parser("moment-rm"); x.add_argument("uid")
    x = sub.add_parser("find"); x.add_argument("query", nargs="?", default=""); x.add_argument("--tag", action="append", default=[])
    x.add_argument("--steal", type=int, default=0); x.add_argument("--film"); x.add_argument("--limit", type=int, default=15)
    x = sub.add_parser("scene"); x.add_argument("scene")
    x = sub.add_parser("show-in-app"); x.add_argument("target"); x.add_argument("--note", default="")
    x = sub.add_parser("apply"); x.add_argument("file")
    if len(sys.argv) == 1:  # no command: the list of them, not an error
        print(__doc__.strip())
        return
    a = p.parse_args()

    if a.cmd == "boards":
        st = state()
        for n, b in st["boards"].items():
            tot = sum((it.get("seconds") or 0) for it in b["items"])
            print(f"{n:32} {b.get('profile', ts.DEFAULT_PROFILE):9} " + (f"{(b.get('folder') or '-'):20} " if paths.FOLDERS else "")
                  + f"{len(b['items']):3} beats  {tot:5.1f}s  updated {b.get('updated', '')}")
        info = server()
        print(f"\nrev {st['rev']} · " + (f"toolbox live at {URL} ({info['live_tabs']} tabs open), serving {info['root']}" if info else offline_note()))
    elif a.cmd == "show":
        show(a.board, a.md)
    elif a.cmd in ("new", "brief"):
        brief = {k: getattr(a, k) for k in ("news", "audience", "aspect", "notes", "length") if getattr(a, k) is not None}
        if a.cmd == "new":
            op = {"op": "board.create", "name": a.board, "brief": brief}
            if a.profile:
                op["profile"] = a.profile
            folder = a.folder if a.folder is not None else paths.here_folder()   # a board started inside a folder is that folder's
            if folder and folder != "-":
                op["folder"] = folder
        else:
            op = {"op": "board.set", "name": a.board, "brief": brief}
            if a.profile:
                op["profile"] = a.profile
            if a.folder is not None:
                op["folder"] = "" if a.folder == "-" else a.folder
        run([op])
    elif a.cmd == "add":
        op = {"op": "item.add", "board": a.board, "id": a.scene}
        for f in ("beat", "copy", "vo", "note", "seconds", "at"):
            if getattr(a, f) is not None:
                op[f] = getattr(a, f)
        if a.time is not None:
            op["t"] = a.time
        run([op])
    elif a.cmd == "edit":
        patch = {f: getattr(a, f) for f in ("beat", "copy", "vo", "note", "seconds") if getattr(a, f) is not None}
        if a.scene:
            patch["id"] = a.scene
        if a.time is not None:
            patch["t"] = "" if a.time.lower() in ("none", "") else a.time
        run([{"op": "item.update", "board": a.board, "n": a.n, "patch": patch}])
    elif a.cmd == "rm":
        run([{"op": "item.remove", "board": a.board, "n": a.n}])
    elif a.cmd == "mv":
        run([{"op": "item.move", "board": a.board, "n": a.n, "to": a.to}])
    elif a.cmd == "folder":
        run([{"op": "board.set", "name": a.board, "folder": "" if a.folder == "-" else a.folder}])
    elif a.cmd == "rename":
        run([{"op": "board.rename", "name": a.board, "to": a.to}])
    elif a.cmd == "delete":
        run([{"op": "board.delete", "name": a.board}])
    elif a.cmd == "review":
        patch = {}
        if a.fav: patch["fav"] = True
        if a.unfav: patch["fav"] = False
        if a.verdict: patch["verdict"] = "" if a.verdict == "none" else a.verdict
        if a.note is not None: patch["note"] = a.note
        run([{"op": "review.set", "key": a.scene, "patch": patch}])
    elif a.cmd == "moments":
        ms = state().get("moments", [])
        for m in ms:
            print(f"{m['uid']}  {m['key']} @ {tcf(m['t'])}  {m.get('note', '')}  ({m.get('by', '')}, {m.get('at', '')[:16].replace('T', ' ')})")
        print(f"{len(ms)} moment{'s' if len(ms) != 1 else ''}")
    elif a.cmd == "moment":
        run([{"op": "moment.add", "key": a.scene, "t": a.time, "note": a.note}])
    elif a.cmd == "moment-rm":
        run([{"op": "moment.remove", "uid": a.uid}])
    elif a.cmd == "find":
        find(a.query, a.tag, a.steal, a.film, a.limit)
    elif a.cmd == "scene":
        scene(a.scene)
    elif a.cmd == "show-in-app":
        if not server():
            sys.exit("the toolbox isn't running: start it with `spliced open`")
        t = a.target
        is_scene = "/" in t and t.split("/")[-1][:1] == "s" and t.split("/")[-1][1:].isdigit()
        target = t if t.startswith("#/") else f"#/scene/{t}" if is_scene else f"#/boards/{urllib.parse.quote(t)}"
        post("/api/focus", {"by": BY, "target": target, "note": a.note})
        print(f"showing {target}")
    elif a.cmd == "apply":
        ops = json.load(sys.stdin if a.file == "-" else open(a.file))
        run(ops if isinstance(ops, list) else ops["ops"])


if __name__ == "__main__":
    main()
