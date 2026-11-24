"""Put the Spliced explainer's picture on the score's beat grid (120 BPM: a beat is 0.5 s, exactly 15 frames).

  python3 remotion/src/films/splice-explainer/sync.py

The scenes are designed on their own clock (cues.json `design`: every time in the scene code). This writes the film's
clock: `scenes` (each beat's window in the film, every cut on a beat) and `sync` (anchors [design time, film time]).
Film.tsx turns film time back into design time by interpolating between the anchors, so a scene runs a little faster
or slower between anchors and its key moments (a click, a word, a card landing, a reel stopping) fall on a beat.
Change PLAN to move cuts, EVENTS to choose what must hit the beat; then run this and render.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
BEAT = 0.5
# each beat's length in the film, in seconds (on the beat grid); the groove ends on the end card's cut at 32.0 s
PLAN = {"open-a-caret": 3.0, "paste-a-link": 4.0, "cut-into-scenes": 4.0, "name-every-move": 3.0, "find-it": 4.0,
        "board-it": 5.0, "with-claude": 4.0, "build-view": 5.0, "end-card": 4.4}
# the design-clock moments that should land on a beat: (section, key[, index])
EVENTS = [("open", "typeAt", 0), ("open", "typeAt", 1),
          ("paste", "focus"), ("paste", "click"), ("paste", "job"), ("paste", "steps", 0), ("paste", "steps", 1),
          ("cut", "scan", 0), ("cut", "scan", 1), ("cut", "cards"), ("cut", "labels"),
          ("name", "reel"), ("name", "land"), ("name", "tags"),
          ("find", "click"), ("find", "sort"), ("find", "pick", 0), ("find", "pickClick"),
          ("boardIt", "pile"), ("boardIt", "snap"), ("boardIt", "focus"),
          ("claude", "add", 0), ("claude", "add", 1), ("claude", "edit"),
          ("build", "plays"), ("build", "click"), ("build", "compose")]
SLOPE = (0.6, 1.7)  # how much faster or slower a stretch between anchors may run


def main():
    p = os.path.join(HERE, "cues.json")
    C = json.load(open(p))
    design = C.setdefault("design", C["scenes"])        # first run: the scenes as built are the design clock
    C["designDuration"] = C.get("designDuration", C["duration"])
    ids = list(design)
    film, t = {}, 0.0
    for i in ids:
        film[i] = [round(t, 3), round(t + PLAN[i], 3)]; t += PLAN[i]
    ev = []
    for e in EVENTS:
        v = C[e[0]][e[1]]
        ev.append(v[e[2]] if len(e) == 3 else v)
    anchors = []
    for i in ids:
        (a, b), (A, B) = design[i], film[i]
        if i == "end-card":                              # after the groove: the end card plays at its own pace
            anchors += [[a, A], [b, B]]; continue
        pts = [[a, A]]
        for d in sorted(x for x in ev if a < x < b):
            u = A + (d - a) * (B - A) / (b - a)
            for grid in (BEAT, BEAT / 2):
                f = round(round(u / grid) * grid, 3)
                d0, f0 = pts[-1]
                ok = f > f0 and SLOPE[0] <= (f - f0) / (d - d0) <= SLOPE[1] and SLOPE[0] <= (B - f) / (b - d) <= SLOPE[1]
                if ok:
                    pts.append([d, f]); break
        pts.append([b, B])
        anchors += pts
    out = []
    for x in anchors:                                    # drop repeated boundary anchors
        if not out or x != out[-1]:
            out.append(x)
    C["scenes"] = film
    C["duration"] = round(t, 3)
    C["sync"] = out
    C["_sync"] = "sync.py: [design time, film time] anchors; Film.tsx interpolates film time back to design time. design = the clock the scene code uses."
    json.dump(C, open(p, "w"), indent=1, ensure_ascii=False)
    on = [f for d, f in out if abs(f / BEAT - round(f / BEAT)) < 1e-6]
    print(f"film {t:.1f}s; {len(out)} anchors, {len(on)} on a beat, the rest on an 8th; cuts: " + ", ".join(f"{film[i][0]:.1f}" for i in ids))
    for d, f in out:
        print(f"  design {d:6.2f} -> film {f:6.2f}")


if __name__ == "__main__":
    main()
