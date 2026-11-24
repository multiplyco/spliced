"""Register the motion kit's own moves in the library as the film `system-moves`.

remotion/src/specimen/moves.json lists every move (Material 3, Apple-style, kit, Liquid Glass) with its tags and
code. The Specimen-Moves composition renders them one after another (remotion/docs/media/system-moves.mp4). This
writes library/references/system-moves/breakdown.json from the same list, so each move is a scene in the toolbox:
filterable by tag, reviewable and addable to a board next to reference scenes.

usage (after `npm run specimens` in remotion/):
  spliced moves && spliced library
"""
import json, os

import paths

ROOT = paths.ROOT
SLUG = "system-moves"
VIDEO = "remotion/docs/media/system-moves.mp4"

data = json.load(open(os.path.join(ROOT, "remotion/src/specimen/moves.json")))
sec = data["scene_seconds"]
scenes = []
for i, m in enumerate(data["moves"]):
    scenes.append({
        "id": f"s{i + 1:02d}", "start": round(i * sec, 3), "end": round((i + 1) * sec, 3),
        "title": f"{m['title']} ({m['key']})",
        "role": m["role"], "world": m["world"], "subject": m["subject"], "camera": m["camera"], "motion": m["motion"],
        "transition_in": m["transition_in"], "type_treatment": m["type_treatment"],
        "pace": "medium", "energy": "steady", "sound_sync": [], "production": ["code-only"],
        "on_screen": f"{m['system']} move `{m['key']}`, shown alone on the specimen stage.",
        "how_it_moves": m["description"],
        "recreate": f"Built into the Remotion kit (remotion/src/lib/motion/, docs/MOTION-SYSTEMS.md). {m['snippet']}",
        "steal": 2,
    })
breakdown = {
    "title": "Motion systems: every move", "brand": "Motion kit",
    "source": "remotion/src/specimen/SystemMoves.tsx (Specimen-Moves)", "file": VIDEO,
    "duration": round(len(scenes) * sec, 3), "format": "16x9", "category": "system-specimen",
    "voice": "on-screen-type-only", "music_feel": ["silent"],
    "summary": "Not a reference film: the moves our own Remotion kit can do, one per scene, so they sit in the library and the toolbox "
               "next to the reference scenes. Material 3 transitions and springs, Apple-style springs and icon effects, the kit's "
               "own text and camera moves, and the Liquid-Glass-style material. Each scene's Recreate field is the code.",
    "tempo": {"avg_shot_s": sec, "cuts_per_min": round(60 / sec, 1), "notes": "Specimen: one move per 2.4s scene, the move starts 0.5s in."},
    "structure": " → ".join(m["key"] for m in data["moves"]),
    "signature_moves": [],
    "scenes": scenes,
    "takeaways": ["Choose a film's motion profile first (remotion/docs/MOTION-SYSTEMS.md), then use these moves through it."],
}
d = os.path.join(ROOT, "library", "references", SLUG)
os.makedirs(d, exist_ok=True)
json.dump(breakdown, open(os.path.join(d, "breakdown.json"), "w"), indent=2, ensure_ascii=False)

tsv = os.path.join(ROOT, "library", "references.tsv")
rows = open(tsv).read().splitlines()
if not any(r.split("\t")[0] == SLUG for r in rows):
    rows.append(f"{SLUG}\t{VIDEO}\tremotion/src/specimen/SystemMoves.tsx")
    open(tsv, "w").write("\n".join(rows) + "\n")
print(f"{SLUG}: {len(scenes)} moves written")
