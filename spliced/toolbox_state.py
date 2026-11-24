"""Spliced's shared state and the operations that change it.

One engine, used by the toolbox server (toolbox.py) and the command line (board.py), so a browser tab
and Claude can edit the same boards at the same time without overwriting each other: every change is a small,
named operation applied to the latest state, never a whole-file replace.

State (library/state.json):
  {
    "rev": 12,                                  # bumps on every change
    "reviews": {"film/s05": {"fav": true, "verdict": "use", "note": "..."}},
    "boards": {
      "Areas launch v1": {
        "profile": "soft",
        "folder": "branding-videos",            # one of the project's folders (spliced.json "folders"), or absent
        "brief": {"news": "...", "audience": "...", "aspect": "16:9", "length": 40, "notes": "..."},
        "items": [{"uid": "a1b2c3", "id": "film/s05", "t": 42.51, "beat": "hook", "copy": "On-screen words", "vo": "Voice-over line", "seconds": 3.0, "note": "..."}],
        "created": "2026-11-16", "updated": "2026-11-16T15:02:11"
      }
    },
    "moments": [{"uid": "d4e5f6", "key": "film/s12", "t": 42.51, "note": "layers gather into the UI", "at": "...", "by": "browser"}],
    "log": [{"rev": 12, "by": "claude", "at": "...", "summary": "..."}]   # last 50 changes
  }
An item's optional `t` is the moment inside the scene it borrows (film seconds of the reference, like a moment's t).
A moment is one exact frame the person pointed at: a scene key and a time in that reference film.

Operations (a list of dicts, applied in order, all or nothing):
  review.set   {key, patch: {fav, verdict, note}}           empty / false / null values clear a field
  board.create {name, profile?, folder?, brief?, items?}     folder: one of the project's folders (default: none)
  board.rename {name, to}
  board.delete {name}
  board.set    {name, profile?, folder?, brief?: {...merged}}   folder "" takes it out of its folder
  item.add     {board, id, uid?, t?, beat?, copy?, vo?, seconds?, note?, at?}   at: 1-based position, default end
  item.update  {board, uid | n, patch: {id?, t?, beat?, copy?, vo?, seconds?, note?}}   "" clears t or seconds
  item.remove  {board, uid | n}
  item.move    {board, uid | n, to}                          to: 1-based position
  moment.add   {key, t, note?, uid?}                         t: seconds in the reference film, inside the scene
  moment.update {uid, patch: {note?, t?}}
  moment.remove {uid}
Unknown fields on items, briefs and moments are refused (an OpError), never silently dropped.
Items are addressed by their stable uid, or by n (1-based position at the time the op runs).
"""
import copy, datetime, json, os, secrets

import paths

ROOT = paths.ROOT
STATE = paths.STATE
PROFILES = list(paths.PROFILES)      # the project's own (spliced.json) and the kit's
DEFAULT_PROFILE = paths.DEFAULT_PROFILE
ITEM_FIELDS = ["id", "t", "beat", "copy", "vo", "seconds", "note"]
BRIEF_FIELDS = ["news", "audience", "aspect", "length", "notes"]
VERDICTS = ["use", "maybe", "skip"]


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def uid():
    return secrets.token_hex(3)


def empty():
    return {"rev": 0, "reviews": {}, "boards": {}, "moments": [], "log": []}


def normalise(state):
    """Fill defaults and give every item a uid (older state files have none)."""
    state = state or {}
    for k, v in empty().items():
        state.setdefault(k, copy.deepcopy(v))
    for b in state["boards"].values():
        b.setdefault("items", [])
        b.setdefault("profile", DEFAULT_PROFILE)
        b.setdefault("brief", {})
        for it in b["items"]:
            it.setdefault("uid", uid())
            for f in ("beat", "copy", "vo", "note"):
                it.setdefault(f, "")
    for m in state["moments"]:
        m.setdefault("uid", uid())
        m.setdefault("note", "")
    return state


def load(path=None):
    """The state on disk (an empty one if there is none). Saving always writes STATE; a project last saved before
    the file moved is read from its old place once, and lands in the new one on its next change."""
    try:
        with open(path or paths.state_file()) as f:
            return normalise(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return normalise(None)


def save(state, path=STATE):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)


class OpError(ValueError):
    pass


def _folder(op):
    f = paths.clean_folder(op.get("folder") or "")
    if (op.get("folder") or "") and f not in paths.FOLDER_NAMES:
        paths.reload_folders()   # (added since this process started?)
        if f not in paths.FOLDER_NAMES:
            raise OpError(f"no folder called {op['folder']!r} (folders: {', '.join(sorted(paths.FOLDER_NAMES)) or 'none yet'})")
    return f


def _board(state, name):
    if name not in state["boards"]:
        raise OpError(f"no board called {name!r} (boards: {', '.join(state['boards']) or 'none'})")
    return state["boards"][name]


def _index(b, op):
    items = b["items"]
    if op.get("uid"):
        for i, it in enumerate(items):
            if it["uid"] == op["uid"]:
                return i
        raise OpError(f"no item {op['uid']} on this board")
    n = op.get("n")
    if not isinstance(n, int) or not 1 <= n <= len(items):
        raise OpError(f"item position must be 1..{len(items)}, got {n!r}")
    return n - 1


def _only(d, allowed, what):
    extra = [k for k in d if k not in allowed]
    if extra:
        raise OpError(f"{what} have {', '.join(allowed)}, not {', '.join(map(repr, extra))}")


def _secs(v, what):
    """A time in seconds: 42.51 or "0:42.51" (m:ss.xx)."""
    if isinstance(v, str) and ":" in v:
        m, _, sec = v.partition(":")
        v = int(m) * 60 + float(sec)
    v = round(float(v), 2)
    if v < 0:
        raise OpError(f"{what} must be 0 or more")
    return v


def _clean_item(patch, known=None):
    out = {}
    for f in ITEM_FIELDS:
        if f not in patch or patch[f] is None:
            continue
        v = patch[f]
        if f in ("seconds", "t"):
            v = _secs(v, f) if v != "" else None
            if v is None:
                out[f] = None
                continue
        elif f == "id":
            v = str(v)
            if known is not None and v not in known:
                raise OpError(f"unknown scene {v!r}")
        else:
            v = str(v)
        out[f] = v
    return out


def apply(state, ops, by="someone", known=None):
    """Apply ops to a copy of state; return (new_state, results, summary). Raises OpError, leaving state untouched."""
    s = normalise(copy.deepcopy(state))
    results, notes = [], []
    for op in ops:
        kind = op.get("op")
        if kind == "review.set":
            key = op["key"]
            if known is not None and key not in known:
                raise OpError(f"unknown scene {key!r}")
            r = dict(s["reviews"].get(key, {}))
            for k, v in (op.get("patch") or {}).items():
                if k not in ("fav", "verdict", "note"):
                    raise OpError(f"reviews have fav, verdict and note, not {k!r}")
                if k == "verdict" and v not in (None, "", *VERDICTS):
                    raise OpError(f"verdict must be one of {VERDICTS}")
                if v in (None, "", False):
                    r.pop(k, None)
                else:
                    r[k] = v
            if r:
                s["reviews"][key] = r
            else:
                s["reviews"].pop(key, None)
            notes.append(f"reviewed {key}")
        elif kind == "board.create":
            name = str(op["name"]).strip()
            if not name:
                raise OpError("a board needs a name")
            if name in s["boards"]:
                raise OpError(f"a board called {name!r} exists")
            prof = op.get("profile") or DEFAULT_PROFILE
            if prof not in PROFILES:
                raise OpError(f"profile must be one of {PROFILES}")
            _only(op.get("brief") or {}, BRIEF_FIELDS, "briefs")
            b = {"items": [], "profile": prof, "brief": dict(op.get("brief") or {}),
                 "created": now()[:10], "updated": now()}
            if _folder(op):
                b["folder"] = _folder(op)
            for it in op.get("items") or []:
                _only(it, ["uid"] + ITEM_FIELDS, "items")
                b["items"].append({"uid": it.get("uid") or uid(), "beat": "", "copy": "", "vo": "", "note": "", **_clean_item(it, known)})
            s["boards"][name] = b
            results.append({"board": name})
            notes.append(f"created board {name!r}")
        elif kind == "board.rename":
            b = _board(s, op["name"])
            to = str(op["to"]).strip()
            if not to or to in s["boards"]:
                raise OpError(f"can't rename to {to!r}")
            s["boards"] = {(to if k == op["name"] else k): v for k, v in s["boards"].items()}
            notes.append(f"renamed {op['name']!r} to {to!r}")
        elif kind == "board.delete":
            _board(s, op["name"])
            del s["boards"][op["name"]]
            notes.append(f"deleted board {op['name']!r}")
        elif kind == "board.set":
            b = _board(s, op["name"])
            if "profile" in op:
                if op["profile"] not in PROFILES:
                    raise OpError(f"profile must be one of {PROFILES}")
                b["profile"] = op["profile"]
            if "folder" in op:
                f = _folder(op)
                if f:
                    b["folder"] = f
                else:
                    b.pop("folder", None)
            for k, v in (op.get("brief") or {}).items():
                if k not in BRIEF_FIELDS:
                    raise OpError(f"brief fields are {BRIEF_FIELDS}, not {k!r}")
                if v in (None, ""):
                    b["brief"].pop(k, None)
                else:
                    b["brief"][k] = v
            b["updated"] = now()
            notes.append(f"updated {op['name']!r}")
        elif kind == "item.add":
            b = _board(s, op["board"])
            if not op.get("id"):
                raise OpError("item.add needs a scene id")
            _only(op, ["op", "board", "uid", "at"] + ITEM_FIELDS, "items")
            given = op.get("uid")
            if given and any(x["uid"] == given for x in b["items"]):
                raise OpError(f"item uid {given} already on this board")
            it = {"uid": str(given or uid()), "beat": "", "copy": "", "vo": "", "note": "", **_clean_item(op, known)}
            at = op.get("at")
            pos = len(b["items"]) if at is None else max(0, min(len(b["items"]), int(at) - 1))
            b["items"].insert(pos, it)
            b["updated"] = now()
            results.append({"uid": it["uid"], "n": pos + 1})
            notes.append(f"added {it['id']} to {op['board']!r}")
        elif kind == "item.update":
            b = _board(s, op["board"])
            i = _index(b, op)
            _only(op.get("patch") or {}, ITEM_FIELDS, "items")
            for k, v in _clean_item(op.get("patch") or {}, known).items():
                if v is None:
                    b["items"][i].pop(k, None)
                else:
                    b["items"][i][k] = v
            b["updated"] = now()
            results.append({"uid": b["items"][i]["uid"], "n": i + 1})
            notes.append(f"edited beat {i + 1} of {op['board']!r}")
        elif kind == "item.remove":
            b = _board(s, op["board"])
            i = _index(b, op)
            gone = b["items"].pop(i)
            b["updated"] = now()
            notes.append(f"removed {gone['id']} from {op['board']!r}")
        elif kind == "item.move":
            b = _board(s, op["board"])
            i = _index(b, op)
            to = max(1, min(len(b["items"]), int(op["to"])))
            b["items"].insert(to - 1, b["items"].pop(i))
            b["updated"] = now()
            notes.append(f"moved beat {i + 1} to {to} in {op['board']!r}")
        elif kind == "moment.add":
            key = str(op.get("key") or "")
            if not key or (known is not None and key not in known):
                raise OpError(f"unknown scene {key!r}")
            _only(op, ["op", "key", "t", "note", "uid"], "moments")
            if op.get("t") in (None, ""):
                raise OpError("a moment needs its time t")
            given = op.get("uid")
            if given and any(m["uid"] == given for m in s["moments"]):
                raise OpError(f"moment {given} exists")
            m = {"uid": str(given or uid()), "key": key, "t": _secs(op["t"], "t"), "note": str(op.get("note") or ""), "at": now(), "by": by}
            s["moments"].append(m)
            results.append({"uid": m["uid"]})
            notes.append(f"saved a moment in {key} at {int(m['t'] // 60)}:{m['t'] % 60:05.2f}")
        elif kind in ("moment.update", "moment.remove"):
            i = next((j for j, m in enumerate(s["moments"]) if m["uid"] == op.get("uid")), None)
            if i is None:
                raise OpError(f"no moment {op.get('uid')!r}")
            if kind == "moment.remove":
                gone = s["moments"].pop(i)
                notes.append(f"removed a moment in {gone['key']}")
            else:
                patch = op.get("patch") or {}
                _only(patch, ["note", "t"], "moments")
                if "note" in patch:
                    s["moments"][i]["note"] = str(patch["note"] or "")
                if patch.get("t") not in (None, ""):
                    s["moments"][i]["t"] = _secs(patch["t"], "t")
                notes.append(f"edited a moment in {s['moments'][i]['key']}")
        else:
            raise OpError(f"unknown op {kind!r}")
    if ops:
        s["rev"] = int(s.get("rev", 0)) + 1
        summary = "; ".join(dict.fromkeys(notes)) if len(notes) <= 4 else f"{len(notes)} changes: " + "; ".join(list(dict.fromkeys(notes))[:3]) + " ..."
        s["log"] = (s.get("log") or [])[-49:] + [{"rev": s["rev"], "by": by, "at": now(), "summary": summary}]
    else:
        summary = ""
    return s, results, summary


def known_scenes():
    """Every scene ID in the library (film/sNN), for validating ops."""
    out = set()
    refs = paths.REFS
    for slug in (os.listdir(refs) if os.path.isdir(refs) else []):
        p = os.path.join(refs, slug, "breakdown.json")
        if os.path.exists(p):
            try:
                out |= {f"{slug}/{sc['id']}" for sc in json.load(open(p))["scenes"]}
            except (json.JSONDecodeError, KeyError):
                pass
    up = paths.UPLOADS_INDEX  # uploaded references (uploads.py)
    if os.path.exists(up):
        try:
            out |= {f"uploads/{x['id']}" for x in json.load(open(up)).get("items", [])}
        except (json.JSONDecodeError, KeyError):
            pass
    return out
