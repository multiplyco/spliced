"""The project's folders: how its films, boards and assets are sorted, say one folder per kind of video, or per client.

  spliced folders                                  each folder, with its films and boards
  spliced folders add <folder> [--name "Name"]     make one (the folder is created if it isn't there)
  spliced folders remove <folder>                  stop sorting into it (nothing in it is moved or deleted)
  spliced film move <film> <folder>                put a film in a folder (- for none); its renders move with it
  spliced board folder <board> <folder>            put a board in a folder (- for none)

A folder is a folder inside the project, listed in spliced.json under "folders". A Remotion film's code stays in
remotion/ and its storyboard names the folder; its renders go to <folder>/renders/. A HyperFrames film lives in its
folder (<folder>/<slug>/). Pictures, clips and sounds you put in a folder show under it in Assets. Whatever is in no
folder is shared by all of them, and the library is never in one: every folder borrows from all of it.

Work started inside a folder belongs to it: a film started by an agent opened in branding-videos/ goes there.
"""
import json, os, sys

import paths


def _write_config(change):
    """Change spliced.json and write it back as it was laid out (its indent, its key order)."""
    path = os.path.join(paths.ROOT, paths.MARKER)
    with open(path) as f:
        raw = f.read()
    c = json.loads(raw) if raw.strip() else {}
    lines = raw.splitlines()
    indent = len(lines[1]) - len(lines[1].lstrip()) if len(lines) > 1 and lines[1].strip() else 2
    change(c)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(json.dumps(c, indent=indent or 2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    paths.reload_folders(c)
    return c


def add(folder, name=""):
    """Add a folder to the project's list (making it on disk if need be). Returns its entry."""
    f = paths.clean_folder(folder)
    if not f:
        raise ValueError(f"{folder!r} can't be a folder: give a folder inside the project, not one of Spliced's own ({', '.join(paths.RESERVED)})")
    real = os.path.realpath(paths.folder_path(f))
    if not real.startswith(paths.ROOT + os.sep):
        raise ValueError(f"{folder!r} is outside the project")
    if os.path.exists(real) and not os.path.isdir(real):
        raise ValueError(f"{f} is a file, not a folder")
    os.makedirs(real, exist_ok=True)
    name = str(name or "").strip()

    def change(c):
        items = [x for x in (c.get("folders") or []) if (x if isinstance(x, str) else (x or {}).get("folder")) != f]
        old = next((x for x in (c.get("folders") or []) if (x if isinstance(x, str) else (x or {}).get("folder")) == f), None)
        keep = name or (old.get("name", "") if isinstance(old, dict) else "")
        entry = {"folder": f, "name": keep} if keep and keep != paths.folder_title(f) else f
        if old is not None:   # already listed: keep its place
            i = (c.get("folders") or []).index(old)
            items.insert(i, entry)
        else:
            items.append(entry)
        c["folders"] = items

    _write_config(change)
    return next(x for x in paths.FOLDERS if x["folder"] == f)


def remove(folder):
    f = paths.clean_folder(folder)
    if f not in paths.FOLDER_NAMES:
        raise KeyError(f"no folder called {folder!r}")

    def change(c):
        c["folders"] = [x for x in (c.get("folders") or []) if (x if isinstance(x, str) else (x or {}).get("folder")) != f]
        if not c["folders"]:
            del c["folders"]

    _write_config(change)


def listing():
    """Each folder with the films and boards in it, and what is in none."""
    import film
    try:
        with open(paths.state_file()) as fh:
            boards = (json.load(fh) or {}).get("boards", {})
    except (OSError, ValueError):
        boards = {}
    films = film.summaries()
    out = []
    for x in paths.FOLDERS + [{"folder": "", "name": "Shared"}]:
        out.append({**x, "films": [p["slug"] for p in films if p.get("folder", "") == x["folder"]],
                    "boards": [n for n, b in boards.items() if (b.get("folder") if b.get("folder") in paths.FOLDER_NAMES else "") == x["folder"]]})
    return out


def main():
    a = sys.argv[1:]
    try:
        if not a or a[0] == "list":
            if not paths.FOLDERS:
                print("No folders yet: every film, board and asset is in the project itself.\n"
                      f"Sort them into folders, say one per kind of video:  {paths.CLI} folders add branding-videos")
                return
            for x in listing():
                head = f"{x['name']}" + (f"  ({x['folder']}/)" if x["folder"] else "  (in no folder)")
                print(head)
                print(f"  films:  {', '.join(x['films']) or 'none'}")
                print(f"  boards: {', '.join(x['boards']) or 'none'}")
            here = paths.here_folder()
            if here:
                print(f"\nYou are in {here}/: films and boards started here go into it.")
        elif a[0] == "add" and len(a) >= 2:
            name = a[a.index("--name") + 1] if "--name" in a and a.index("--name") + 1 < len(a) else ""
            x = add(a[1], name)
            print(f"{x['name']}: {x['folder']}/ is one of the project's folders. "
                  f"Put a film in it with {paths.CLI} film move <film> {x['folder']}")
        elif a[0] in ("remove", "rm") and len(a) >= 2:
            remove(a[1])
            print(f"{a[1]}: no longer one of the project's folders. Nothing in it was moved; its films and boards show as in no folder.")
        else:
            print(__doc__.strip())
            sys.exit(2)
    except (KeyError, ValueError) as e:
        sys.exit(f"Spliced: {str(e).strip(chr(39))}")


if __name__ == "__main__":
    main()
