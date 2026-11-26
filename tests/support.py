"""Shared by the tests: where things are, and a throwaway copy of the fixture project."""
import atexit, hashlib, os, re, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TOOLS = os.path.join(REPO, "spliced")   # the package: the tools are its modules
FIXTURE = os.path.join(HERE, "fixture")
SENTINEL = "SENTINEL_DO_NOT_SERVE"

# The list of projects a person has opened lives with their settings (projects.py): the tests keep their own, so the
# throwaway projects they open never show up in the menu of the person running them.
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="spliced-cfg-")
atexit.register(shutil.rmtree, os.environ["XDG_CONFIG_HOME"], ignore_errors=True)

# Tests that import a tool in this process need a project to exist: the fixture, which they only read.
os.environ.setdefault("SPLICED_PROJECT", FIXTURE)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)


# Names that must never appear in the tool: a company, a person, a private product. Kept as hashes, so the tests don't
# write them out either: sha256 of the lowercased word, first 16 hex digits. Add one with:
#   python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.argv[1].lower().encode()).hexdigest()[:16])' <word>
UNNAMED = {"0d31bc618d289b7e", "bbae7d24e16ffb81", "bd558de5f7945767", "ee4ee75a73756629"}
LENGTHS = (5, 8, 10)   # how long those names are: a longer word that starts with one of them counts too
# The one word among them that is also a CSS keyword (a blend mode): allowed where it is that.
CSS_BLEND = re.compile(r"(mix-blend-mode|--hw-grit-mode|background-blend-mode):\s*[a-z]+")


def named(text):
    """Does this text hold one of those names, as a word of its own or as part of a longer one (name, name-film, Nameco)?"""
    low = CSS_BLEND.sub("", str(text).lower())
    words = set(re.findall(r"[a-z0-9]+", low))
    if any(hashlib.sha256(w.encode()).hexdigest()[:16] in UNNAMED for w in words):
        return True
    return any(hashlib.sha256(w[:n].encode()).hexdigest()[:16] in UNNAMED for w in words for n in LENGTHS if len(w) > n)


def project(test):
    """Copy the fixture to a temp folder (removed when the test ends) and give it a .env no response may ever contain."""
    d = os.path.realpath(tempfile.mkdtemp(prefix="spliced-fx-"))
    test.addCleanup(shutil.rmtree, d, ignore_errors=True)
    root = os.path.join(d, "project")
    shutil.copytree(FIXTURE, root)
    with open(os.path.join(root, ".env"), "w") as f:
        f.write(f"UNSPLASH_ACCESS_KEY={SENTINEL}\n")
    return root


def fake_npm(bin_dir):
    """A stand-in for npm in bin_dir: `npm ci|install` in a folder puts node_modules/remotion there, as the real one would."""
    npm = os.path.join(bin_dir, "npm")
    with open(npm, "w") as f:
        f.write("#!/bin/sh\necho \"npm $1 (stand-in)\"\nmkdir -p node_modules/remotion\necho 'added 1 package'\n")
    os.chmod(npm, 0o755)
    return npm


def next_import(ask, timeout=300):
    """`imports next` once a job is ready for an agent: a profile job digests its sources first (digest.py), which
    takes a while on a machine where the digest's packages aren't installed yet. ask() runs it: (code, output)."""
    import time
    end = time.time() + timeout
    while True:
        code, out = ask()
        if "Nothing is waiting" not in out or time.time() > end:
            return code, out
        time.sleep(1)
