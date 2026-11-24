# How to break down a reference video

The library turns reference videos we like into scenes we can point at and recreate:
"make the intro like `globex-how-it-works/s03`, with the camera of `initech-laptop/s12`".
Every film gets the same treatment, so scenes from different films can be compared and mixed.

The method: describe motion with **numbers you could build from** (durations, easing, stagger, scale, positions), not adjectives. "Words
arrive one at a time, ~0.12s apart, rising ~20px and sharpening from blur, ease-out with no overshoot"
is useful. "Smooth, elegant text animation" is not.

## 1–2. Add the video and run the machine pass

In Claude Code, `/add-reference <url-or-file> ...` runs this whole process, including the breakdown agents.
By hand:

```bash
spliced reference add "<url-or-file>" --slug <slug>   # download, register, machine pass
spliced reference status                             # what's analysed and broken down
spliced reference rename <old-slug> <new-slug>       # once an unknown film's brand is known
```

The slug is a short kebab-case `brand-what` (`acme-launch-2025`). It becomes the permanent ID in every scene
reference, so make it readable. The machine pass on its own:

```bash
spliced analyze analyze "reference/<file>.mp4" <slug>
```

This writes `library/references/<slug>/`:

- `analysis.json`: duration, fps, size; detected **hard cuts** (`shots`: the spans between detected cuts);
  `change_events` (moments of big visual change over ~0.33s, which catch soft transitions like fades on
  white, mask wipes and reshuffles, plus big events inside a scene); per-shot `motion_energy` (mean pixel
  change per 1/12s, 0–255: under ~2 is near-still, 2–8 gentle, 8–20 busy, 20+ frantic); palette;
  `audio` (BPM, beat times, loudness per second, share of cuts within 80ms of a beat).
- `sheets/overview.jpg`: the whole film as a grid, one tile every `overview_step_s` seconds, timestamps burned in.
- `sheets/shot-NN.jpg`: 3–5 frames from each detected shot.

Treat the detection as hints. Hard-cut detection misses mask wipes, colour wipes, morphs and anything
on a white background. BPM can be off by half or double.

To look closely at a moment (a transition, a fast move), make a dense strip:

```bash
spliced analyze strip "reference/<file>.mp4" 12.0 13.2 10 .context/look.jpg
```

Ten frames over 1.2s show the easing: equal spacing means linear, big gaps first then tiny gaps means
ease-out, overshoot shows as a frame past the final position.

## 3. Decide the scenes

A **scene** is one idea on screen: a title card, a demo moment, a quote, a logo. It ends when the idea
changes, whether by a hard cut, a wipe, a morph or a camera move to new content. A continuous shot
can hold two or three scenes. A fast montage of 8 shots of the same idea can be one scene (say so in the
text). Scenes must be contiguous: each starts where the previous one ends, from 0 to the film's duration.

Aim for 6–30 scenes per film. If there are more, group the montage parts.

## 4. Write `breakdown.json`

Tags come only from `library/TAXONOMY.md`. Every film-level and scene-level field is required.

```json
{
  "title": "How It Works",
  "brand": "Globex",
  "source": "films.example.com/how-it-works",
  "file": "reference/How It Works ｜ Globex [a1b2c3d4e5f].mp4",
  "duration": 30.09,
  "format": "16x9",
  "category": "brand-film",
  "voice": "on-screen-type-only",
  "music_feel": ["indie-pop"],
  "summary": "2–3 sentences: what the film is, and what makes it worth having in the library.",
  "tempo": {"bpm": 112, "avg_shot_s": 1.2, "cuts_per_min": 50,
            "notes": "How the edit relates to the music: what lands on beats, where it breathes, where it speeds up."},
  "structure": "The beat outline in one paragraph with times: cold open (0–1s) → question typed (1–3.5s) → ...",
  "style_signature": {
    "palette": [{"hex": "#12343B", "name": "deep teal"}, {"hex": "#FFFFFF", "name": "white"}],
    "type": "Faces (name them if you recognise them, else describe), weights, sizes as share of frame height, case, tracking, alignment.",
    "layout": "Grid, margins, where things sit, how much is empty.",
    "motion": "The house motion language: easing, typical durations, staggers, overshoot or not.",
    "camera": "How the camera behaves across the film.",
    "transitions": "The transition vocabulary and how often each is used.",
    "sound": "What you can infer: music feel, BPM, what's on beat. You can't hear it; say what's inferred."
  },
  "scenes": [
    {
      "id": "s01", "start": 0.0, "end": 1.0,
      "title": "Logo blooms from the mark",
      "role": "cold-open", "world": "white-stage",
      "subject": ["logo"], "camera": ["locked"], "motion": ["scale-pop", "morph"],
      "transition_in": "none", "type_treatment": [], "pace": "fast", "energy": "punchy",
      "sound_sync": ["motion-on-beat"], "production": ["code-only"],
      "palette": ["#FFFFFF", "#2EC4B6"],
      "on_screen": "Exactly what is visible, with any copy in quotes, word for word.",
      "how_it_moves": "Precise, with estimated numbers: what moves, from where to where, how long, easing, stagger, what triggers what, how it exits.",
      "recreate": "How we'd build it for our own films: the approach in Remotion (name the project's own motion roles and helpers where they fit, e.g. remotion/docs/MOTION-SYSTEMS.md if it has one), what would need generating (with a short prompt idea), and effort S/M/L.",
      "steal": 2
    }
  ],
  "signature_moves": [
    {"name": "Pill-mask quote wipe", "scenes": ["s05", "s09"],
     "description": "The move in one or two sentences, with the numbers that make it work.",
     "recreate": "How to build it once as a reusable component."}
  ],
  "takeaways": ["What this film teaches us for our own videos, 3–6 bullets, specific."]
}
```

**`steal`** (0–3): how much this scene is worth recreating. 3 = a signature move, the reason the film is
in the library. 2 = solid, reusable technique. 1 = fine but generic. 0 = filler (logos, legal, a plain hold).

**`signature_moves`**: 1–5 named techniques per film. Give each a name a person would remember
("pill-mask quote wipe", "fly into the letter"), because these names become the shared vocabulary.

## 5. Build and check

```bash
spliced library --check <slug> # tags and timing valid?
spliced library <slug>         # renders scenes/sNN.jpg strips + breakdown.md, rebuilds INDEX.md
```

Then open `library/references/<slug>/breakdown.md` and look at the strips: does each strip show one idea?
If a strip shows two scenes, the boundary is wrong.

## Quality bar

- **Specific copy.** Quote the on-screen words exactly.
- **Numbers.** Durations, staggers, scale factors, sizes as a share of the frame, colours as hex.
  Estimates are fine; label them with "~".
- **Say what you can't know.** You can't hear the audio or see between frames. Say "inferred" when you are.
- **Recreate for us.** Every `recreate` names the method for our own films: rebuilt UI, code type, a generated
  plate. Never "film this".
- **No em dashes** in any text (house style).
