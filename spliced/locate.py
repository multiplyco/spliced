"""Which folder is the project? Kept apart from paths.py so the command line can ask without needing an answer.

A project is a folder with a spliced.json in it. It is found in this order:
  1. --project <folder> on the command line (any tool; the flag is taken off the arguments)
  2. the SPLICED_PROJECT environment variable
  3. the nearest folder at or above the current one that holds a spliced.json
"""
import os, sys

MARKER = "spliced.json"
NO_PROJECT = ("Spliced: this folder isn't inside a project (no spliced.json here or above).\n"
              "Go to your project's folder, pass --project <folder>, or start a new one with: spliced init <folder>")


def flag(argv=None):
    """--project <folder> or --project=<folder>, removed from the arguments so each tool's own parsing never sees it."""
    a = sys.argv if argv is None else argv
    for i, x in enumerate(a):
        if x == "--project" and i + 1 < len(a):
            v = a[i + 1]
            del a[i:i + 2]
            return v
        if x.startswith("--project="):
            del a[i]
            return x.split("=", 1)[1]
    return None


def find(explicit=None, start=None, env=None):
    """The project's root folder, or None when there is none. A folder that is named but doesn't exist is an error."""
    env = os.environ if env is None else env
    named = explicit or env.get("SPLICED_PROJECT")
    if named:
        p = os.path.realpath(os.path.expanduser(named))
        if not os.path.isdir(p):
            sys.exit(f"Spliced: no project folder at {named}")
        return p
    d = os.path.realpath(start or os.getcwd())
    while True:
        if os.path.isfile(os.path.join(d, MARKER)):
            return d
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up
