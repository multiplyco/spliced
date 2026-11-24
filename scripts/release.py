"""Cut a release of Spliced: give what has changed a version number, then tag it.

  python3 scripts/release.py status              what would be in the next release
  python3 scripts/release.py prepare minor       0.1.3 -> 0.2.0: something a person using Spliced would notice
  python3 scripts/release.py prepare patch       0.1.3 -> 0.1.4: fixes only
  python3 scripts/release.py prepare 1.0.0       an exact number
  python3 scripts/release.py publish             after that change is on main: tag it and make the GitHub release

The policy. Below 1.0: the middle number moves for a release that adds something a user would notice, the last for
fixes only; 1.0 is the day the repo goes public. A release is cut when the owner says so; there is no schedule.

Two steps, because every change to main is reviewed:
  prepare   writes the number into spliced/__init__.py and pyproject.toml, and marks in spliced/web/changelog.md
            where the release begins (a `<!-- release 0.2.0 2026-12-01 -->` line above the entries it contains).
            It touches no git. Commit that on a branch and open a pull request as usual.
  publish   once that is merged and you are on it: checks the number, the mark and the tag agree, tags vX.Y.Z,
            pushes the tag and creates the GitHub release, with the changelog entries as its notes. The release is as
            private as the repository. The Mac app is built and attached by running .github/workflows/release.yml
            by hand. Nothing is published to npm or PyPI: both packages refuse to be (see "Going public" in README.md).

Standard library only.
"""
import datetime, os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT = os.path.join(REPO, "spliced", "__init__.py")
PYPROJECT = os.path.join(REPO, "pyproject.toml")
PACKAGE = os.path.join(REPO, "package.json")
CHANGELOG = os.path.join(REPO, "spliced", "web", "changelog.md")
MARK = re.compile(r"^<!-- release (\d+\.\d+\.\d+) (\d{4}-\d{2}-\d{2}) -->\s*$", re.M)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def current(init_text=None):
    return re.search(r'__version__\s*=\s*"(\d+\.\d+\.\d+)"', init_text if init_text is not None else read(INIT)).group(1)


def bump(version, how):
    """ "0.1.3" and "minor" | "patch" | "major" | an exact "X.Y.Z" -> the next number. It must go up."""
    a, b, c = (int(x) for x in version.split("."))
    if how == "major":
        new = (a + 1, 0, 0)
    elif how == "minor":
        new = (a, b + 1, 0)
    elif how == "patch":
        new = (a, b, c + 1)
    elif re.fullmatch(r"\d+\.\d+\.\d+", how):
        new = tuple(int(x) for x in how.split("."))
    else:
        raise ValueError(f"{how!r} is not minor, patch, major or a number like 0.2.0")
    if new <= (a, b, c):
        raise ValueError(f"{'.'.join(map(str, new))} is not after {version}")
    return ".".join(map(str, new))


def entries(changelog):
    """The changelog as [(title, version or None, text)]: version is None for what no release contains yet."""
    intro, *parts = re.split(r"(?m)^## ", changelog)
    out, version = [], (MARK.search(intro).group(1) if MARK.search(intro) else None)
    for part in parts:
        title, _, body = part.partition("\n")
        out.append((title.strip(), version, MARK.sub("", body).strip()))
        m = MARK.search(body)
        if m:
            version = m.group(1)
    return out


def unreleased(changelog):
    return [(t, body) for t, v, body in entries(changelog) if v is None]


def mark(changelog, version, date):
    """Put the release's mark above the entries it contains: right before the first entry."""
    if not unreleased(changelog):
        raise ValueError("nothing has changed since the last release: the changelog has no new entry")
    i = changelog.index("\n## ") + 1
    return changelog[:i] + f"<!-- release {version} {date} -->\n\n" + changelog[i:]


def notes(changelog, version):
    """The GitHub release's text: each entry's title, the line that says it, and its paragraphs (no pictures)."""
    out = []
    for title, v, body in entries(changelog):
        if v != version:
            continue
        lines = [l for l in body.split("\n") if not re.match(r"^\d{4}-\d{2}-\d{2}$", l.strip()) and not l.strip().startswith("![")]
        out.append(f"## {title}\n\n" + "\n".join(lines).strip())
    return "\n\n".join(out)


def set_version(version):
    s = read(INIT)
    write(INIT, re.sub(r'(__version__\s*=\s*")[^"]+(")', rf"\g<1>{version}\g<2>", s, count=1))
    s = read(PYPROJECT)
    write(PYPROJECT, re.sub(r'(?m)^(version\s*=\s*")[^"]+(")', rf"\g<1>{version}\g<2>", s, count=1))
    s = read(PACKAGE)   # the npm package (bin/spliced.js) carries the same number
    write(PACKAGE, re.sub(r'("version"\s*:\s*")[^"]+(")', rf"\g<1>{version}\g<2>", s, count=1))


def git(*args, check=True):
    r = subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout.strip()


def status():
    v, new = current(), unreleased(read(CHANGELOG))
    print(f"Spliced is at {v}." + (f" {len(new)} change{'s' if len(new) != 1 else ''} not in a release yet:" if new else " Nothing has changed since it was released."))
    for title, _ in new:
        print(f"  {title}")
    if new:
        print(f"\nNext: python3 scripts/release.py prepare minor   (-> {bump(v, 'minor')})   or   prepare patch   (-> {bump(v, 'patch')})")


def prepare(how):
    try:
        v = current()
        new = bump(v, how)
        log = mark(read(CHANGELOG), new, datetime.date.today().isoformat())
    except ValueError as e:
        sys.exit(f"release: {e}")
    set_version(new)
    write(CHANGELOG, log)
    n = len([1 for _, ver, _ in entries(log) if ver == new])
    print(f"{v} -> {new}, with {n} change{'s' if n != 1 else ''}. Written to spliced/__init__.py, pyproject.toml and spliced/web/changelog.md.\n"
          f"Commit that on a branch (\"Release {new}\"), open a pull request, and once it is merged run: python3 scripts/release.py publish")


def publish():
    v, tag = current(), f"v{current()}"
    if not re.search(rf'(?m)^version\s*=\s*"{re.escape(v)}"', read(PYPROJECT)):
        sys.exit("release: spliced/__init__.py and pyproject.toml disagree about the version")
    if not re.search(rf'"version"\s*:\s*"{re.escape(v)}"', read(PACKAGE)):
        sys.exit("release: spliced/__init__.py and package.json disagree about the version")
    log = read(CHANGELOG)
    if not any(m.group(1) == v for m in MARK.finditer(log)):
        sys.exit(f"release: the changelog has no mark for {v}; run prepare first")
    if git("status", "--porcelain"):
        sys.exit("release: there are uncommitted changes")
    git("fetch", "-q", "origin", "--tags")
    if git("rev-parse", "HEAD") != git("rev-parse", "origin/main"):
        sys.exit("release: this is not origin/main. Merge the release's pull request, then pull main and run publish there")
    if git("tag", "--list", tag):
        sys.exit(f"release: {tag} already exists")
    text = notes(log, v)
    git("tag", "-a", tag, "-m", f"Spliced {v}")
    git("push", "-q", "origin", tag)
    r = subprocess.run(["gh", "release", "create", tag, "--title", f"Spliced {v}", "--notes", text, "--verify-tag"], cwd=REPO, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"release: {tag} is tagged and pushed, but the GitHub release could not be made:\n{r.stderr.strip()}\nMake it by hand: gh release create {tag} --title 'Spliced {v}' --notes-file <notes>")
    print(f"Released {v}: {r.stdout.strip()}")


def main():
    a = sys.argv[1:]
    if a[:1] == ["status"]:
        status()
    elif a[:1] == ["prepare"] and len(a) == 2:
        prepare(a[1])
    elif a[:1] == ["publish"]:
        publish()
    else:
        sys.exit(__doc__.strip())


if __name__ == "__main__":
    main()
