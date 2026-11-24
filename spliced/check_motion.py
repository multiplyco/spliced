"""Flag hand-written motion in film code, so every film stays on its motion profile.

Film code should ask the profile for a role (m.enter, m.move, m.ui, m.camera, m.textReveal, m.ViewChange ...),
see remotion/docs/MOTION-SYSTEMS.md. This finds easing curves, springs and GSAP-style eases written inline.

usage:
  spliced motion                 # scans remotion/src, except the motion library itself,
                                                # and the specimens
  spliced motion remotion/src/films/my-film   # one folder
A line can opt out with a trailing `// motion-ok: <reason>` comment.
"""
import os, re, sys

import paths

ROOT = paths.ROOT
SRC = os.path.join(paths.REMOTION, "src")
SKIP = [os.path.join(SRC, p) for p in ("lib", "specimen")]
PATTERNS = [
    (r"Easing\.(bezier|in|out|inOut|poly|elastic|back|bounce|bezier|cubic|quad|sin|exp|circle)\b", "Remotion Easing used directly: use a profile role (m.enter / m.move / m.ui ...)"),
    (r"cubic-bezier\(", "CSS cubic-bezier: use a profile role"),
    (r"\bspring\(\s*\{", "Remotion spring() with its own config: use m.ui / m.emphasis, or appleSpringAt / m3SpringAt"),
    (r"(damping|stiffness|mass)\s*:\s*[\d.]+", "spring constants written inline: put them in a profile"),
    (r"['\"](power[1-4]|expo|back|elastic|circ|sine|quad|cubic|quart|quint)\.(in|out|inOut)", "GSAP-style ease string: use a profile role"),
    (r"transition\s*:\s*['\"][^'\"]*(ease|cubic)", "CSS transition easing: Remotion renders frames, animate from t with a profile role"),
]


def scan(paths):
    hits = []
    for base in paths:
        for dp, dn, fn in os.walk(base):
            if any(dp.startswith(s) for s in SKIP) and base == SRC:
                continue
            for f in fn:
                if not f.endswith((".ts", ".tsx", ".js", ".jsx")):
                    continue
                p = os.path.join(dp, f)
                for n, line in enumerate(open(p, encoding="utf-8"), 1):
                    if "motion-ok" in line:
                        continue
                    for pat, why in PATTERNS:
                        if re.search(pat, line):
                            hits.append((os.path.relpath(p, ROOT), n, line.strip()[:110], why))
                            break
    return hits


if __name__ == "__main__":
    paths = [os.path.abspath(a) for a in sys.argv[1:]] or [SRC]
    hits = scan(paths)
    for p, n, line, why in hits:
        print(f"{p}:{n}: {why}\n    {line}")
    print(f"\n{len(hits)} hand-written motion line(s)" if hits else "Motion check: all motion comes from the profile.")
    sys.exit(1 if hits else 0)
