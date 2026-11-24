# Breakdown agent brief

The prompt for an agent that writes `breakdown.json` for one or more films. The `/add-reference` skill sends
this file's text (everything below the line) plus a **Your films** list. To run it by hand, paste it into a
fresh agent and append the list in the same format:

```
## Your films
- `acme-launch-2025` (81s, "Everything we launched in 2025", Acme). Notes: 27 detected shots, group them.
```

---

You are adding films to a reference library of motion design. The project is the current working directory;
its `spliced.json` says whose films are made from this library (`brand`). The library lets a person say
"recreate the style of `<film>/<scene>`" and have an agent build it in Remotion with their own UI and brand.
Your job: write a
scene-by-scene `breakdown.json` for each film in **Your films** at the end of this brief.

## Read first, in full

1. `HOW-TO-BREAK-DOWN.md`: the method, the JSON schema and the quality bar. Follow it exactly.
2. `library/TAXONOMY.md`: the only allowed tags. Do NOT edit it. If a tag is missing, use the closest one,
   describe the difference in the prose, and list the proposed tag in your final report.
3. If the project has its own film docs (`remotion/docs/`, for example `MOTION-SYSTEMS.md` or a craft guide), skim
   them for the motion roles and helpers to name in `recreate` fields.
4. One finished breakdown from this library as a model for depth and tone, if there is one yet
   (any `library/references/*/breakdown.json`). Otherwise the template in `HOW-TO-BREAK-DOWN.md` is the model.

## What's already done

The machine pass has run for every film: `library/references/<slug>/analysis.json` and `sheets/`
(`overview.jpg`, plus `shot-NN.jpg` per detected hard cut). The video path for each slug is in
`library/references.tsv`.

Work order per film:
1. Read `sheets/overview.jpg` once (it's large).
2. Read `analysis.json`: `shots`, `change_events`, `audio`.
3. Look at shot sheets where needed.
4. Make dense strips of transitions and fast moves with
   `spliced analyze strip "<video>" <t0> <t1> <n> .context/look/<slug>/<name>.jpg`.
   Keep scratch files only under `.context/look/<slug>/`, never in `library/` and never in a shared filename;
   other agents run in parallel.

## Known traps (learned from the first 22 films)

- **Hard-cut detection misses about half of real scene changes:** mask and colour wipes, morphs, blur
  transitions, and any cut between two white or light frames. Find those with `change_events` and your eyes.
  Detected cut times can also be off by ~0.15s; check boundaries you rely on with a dense strip.
- **`change_events` also fire inside scenes** (a sort, a reveal, a big move). Not every event is a boundary.
- **BPM is often doubled** (152 for a ~76 BPM track). Check against the cut rhythm and write the tempo you believe, with a note.
- **You can't hear anything.** Voice-over, music feel and sound effects are inferred from loudness, captions and
  timing. Say "inferred".
- **Unknown sources:** if the slug or title is a placeholder, identify the brand and film from what's on screen
  (wordmarks, URLs, end cards) and put them in `brand` and `title`. Don't rename the folder; report the brand
  so the coordinator can rename the slug.
- **No em dashes anywhere**, including quoted copy: write on-screen em dashes as hyphens and say so.
- **Group montages:** keep to 6–30 scenes per film. A run of shots with one idea is one scene.

## Rules

- Write only `library/references/<slug>/breakdown.json` for your slugs. Don't touch other films' folders,
  `TAXONOMY.md`, `STYLES.md` or the tools.
- Run `spliced library --check <slug>` until it passes, then `spliced library <slug>`
  to render the scene strips and `breakdown.md`. Open 2–3 of the rendered `scenes/sNN.jpg` strips: each should
  show one idea. Fix boundaries and rebuild if not.
- Be specific and numeric: durations, easing, stagger, scale, sizes as a share of frame height, hex colours.
  Quote on-screen copy exactly.
- `recreate` is always for the project's own films: UI rebuilt in Remotion code, code type and shapes, generated
  plates or clips (with a short prompt idea) where footage or 3D is needed. Effort S/M/L.
- Name 1–5 `signature_moves` per film with memorable names; they become the shared vocabulary.

## Final report

Keep it under 250 words; it goes to the coordinator, not the user. Per film: scene count, the brand if you
identified one, and the signature move names. Then any proposed taxonomy tags, each with a one-line definition
and the scene IDs that should carry it. Then anything you're unsure about.
