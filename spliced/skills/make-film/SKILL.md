---
name: make-film
description: Build a launch, feature, explainer or social film in Remotion with Spliced's film kit, from a Spliced board's build prompt or from a brief. Use when the person wants to make, storyboard, animate or render a film in a Spliced project ("make a launch film for X", "build this board", a pasted prompt starting with /make-film, notes on a render from the Build view). Covers brief, motion profile, storyboard, screen rebuilds, build, sound, checks and render. Not for adding reference films (/add-reference).
---

# Make a film

The pipeline: **references and system moves** (the library) → **a board** (ordered beats) → **brief with a motion
profile** → **storyboard** → **build in Remotion, beat by beat** → **sound** → **checks** → **render**. Read only what
each step names; don't preload the docs.

**Before anything, know which profile the film is made in.** A profile is a look the project keeps: a house look (its
brand, type, stage, product and sound direction) or a look to explore, with its motion profile and the rules learned
on earlier films. The prompt names it, or `spliced film status <slug>` does once the film is started; with neither,
it is the project's default (`spliced profile` marks it). Read it with `spliced profile show <profile>`: it wins over
the kit's defaults in `remotion/docs/CRAFT.md`. **No profile** ("none", or "as the reference") means recreate what the
references show, in their own look: see "A study of one film". A project with no profiles but a
`remotion/docs/HOUSE.md` keeps its rules there.

**A profile grows.** When the person states a lasting preference ("never bounce the logo", "our type is always
left-aligned"), not a fix for one frame, ask whether to keep it in the profile, then `spliced profile learn <profile>
"<the rule>" --from "<film> note <id>"`. Don't learn a rule into a profile the film isn't made in.

**The kit.** Films are built on Spliced's film kit in `remotion/`: the motion library (`src/lib/motion`), its
specimens, `docs/CRAFT.md`, `docs/MOTION-SYSTEMS.md`, `docs/SOUND.md` and the UI sounds. `spliced kit` says whether
it is in and current, and whether its packages (Remotion, React) are installed. If it isn't: `spliced kit install`, which
installs the packages too (say that Remotion is free for individuals and small teams and needs a paid licence above
that). A clone or new worktree without them gets them from `spliced kit packages`, from opening the project in Spliced,
or from the first `spliced film render`. The kit's files are Spliced's and are replaced
by `spliced kit update`: never edit them. A film's own code goes in its folder; a project's own motion profile goes in
`remotion/src/profiles.ts`. `spliced kit starter` adds the example film `splice-explainer`, the smallest complete film
to read before building one.

**The red thread is `remotion/src/films/<slug>/storyboard.json`.** Every beat in it has an id (= its key in the film's
`cues.json` scenes), its reference scenes, what's on screen, the copy, a status and the person's open review note. The
person reviews in Spliced's Build view, which plays each beat of the render next to its reference and saves their
notes into that file. Read it at the start of every session and keep it true:

```bash
spliced film status <slug>                  # the plan beat by beat, open notes, renders, what's next
spliced film mark <slug> <beat> wip         # todo → wip → review; the person sets changes / approved
spliced film render <slug> [--beat <id>]    # <slug>-vN[-beat].mp4 + a sidecar of the beat times, in remotion/out/ or the film's folder's renders/
spliced film sheet <slug> [--beat <id>]     # storyboard | reference frames | render frames, per beat, as a JPEG
spliced film mark <slug> <beat> review --done "what you changed"   # files the person's note in the beat's log
spliced sound show <slug>                   # sound: beat grid, music sections, every effect on the grid
spliced film sound-done <slug> <note-id> --done "what you changed" # closes a sound note
spliced film note <slug> <0:18.66 | beat> "the note" --by chat       # file the person's chat feedback on its frame
spliced film notes <slug>                   # notes pinned to moments (the Build view's N key), open first
spliced film render <slug> --beat <id> --fixes <ids> --note "what changed"  # render and close the notes it fixes
spliced film done <slug> <ids> --done "what you changed"         # close notes (pinned, beat or sound) after the fact
spliced film note-reply <slug> <id> "copy changed, voice pending" # partly done: say what's left, it stays open
spliced film assets <slug>                  # every still and clip, where it's used, generated or not
spliced film mode <slug> [auto|manual]      # who picks up the person's notes (the Build view's Auto / Manual)
spliced film watch <slug>                   # auto mode: wait for the next notes, print them, return (run in the background)
```

(If `spliced` isn't on the PATH, use the command the project's `AGENTS.md` names, for example `npx -y <package>`.)

**Notes at a moment.** The person pins notes to a frame in the Build view (key N); they're in storyboard.json `pins`
with the film time, the beat and the render they saw. When they give feedback in the chat instead ("at 0:18.66 in v29
the words should burst"), file it the same way with `spliced film note ... --by chat`, so every note lives on the film
and shows on its frame.

**Auto or manual notes.** Each film has a notes mode, set by the person in the Build view and printed by `status`.
*Auto:* open notes are yours to fix as they arrive. Once you've closed the ones you have, run `spliced film watch
<slug>` in the background; it returns with the next notes, and the Build view shows that you are listening while it
waits. Fix those, close them, start `watch` again. *Manual:* work only on the notes a pasted prompt names; leave other
open notes alone and don't start `watch`.

**Close what you fix, every time.** The person sees each note turn done, with what changed and the render that has it,
so a fixed note left open reads as ignored. Close notes in the render that fixes them (`render ... --fixes <ids>`) or
right after (`spliced film done`). If a note is only partly done, leave it open and `note-reply` with what's done and
what's left.

**The script.** Each beat's on-screen words and voice-over line are `copy` and `vo` in storyboard.json; the Build
view's Script tab shows them next to a frame of the render. When you change the words in the film, update `copy` /
`vo` too. When you generate a still or clip, or pull stock footage, record it in the film's `assets.json` so the
Assets view shows it.

## 0. Start from what you're given

- **A build prompt from Spliced** (a board's "copy build prompt"): it has the beats, the scene IDs, the profile and
  the motion profile. Start the film with `spliced film new <slug> --board "<board>"` (skip if the board already has one: the
  Boards view's "start film" does the same), then go to step 1. If the project sorts its work into folders
  (`spliced folders`), the film goes in the board's folder, or the one you were opened in; `--folder` picks another.
- **A film brief from Spliced** (a reference film's "Copy build brief", or "recreate this film"): a study, not a new
  film. Make the board and the film from the reference (`spliced board new "Study: <title>" --from-film <ref>`, then
  `spliced film new <slug> --board "Study: <title>"`), so each beat is one of its scenes and the Build view plays it
  beside that scene. Then the goal is the reference, not the house: see "A study of one film" below.
- **A beat prompt or notes prompt from the Build view:** the film exists. Run `spliced film status <slug>`, then do
  just that beat or those notes (step 4's loop).
- **Only a brief or an idea:** ask for what's missing in one message: the feature or message, who it's for, where it
  runs (aspect ratio) and roughly how long. Then build the board with the person, live: `spliced board new "<name>"
  --news .. --length ..`, find candidates with `spliced board find`, add beats with copy and seconds, and
  `spliced board show-in-app "<name>"` so they see it in Spliced. Iterate on the script in the chat; they can edit in
  the app at the same time.

## A study of one film

When the person asks to recreate a reference film as closely as you can, match what you see and change nothing to
suit the project:
- **Its look, not a profile's.** Skip the project's profiles, `HOUSE.md` and its motion profile for this film. Its
  palette, type, stage, framing, copy and pacing come from the reference: the breakdown's palette and style signature,
  and the frames (`library/references/<ref>/scenes/<id>.jpg`, `sheets/` when the analysis made them). Its own words
  are the copy.
- **Its motion.** Write a motion profile for this film in `remotion/src/profiles.ts` (named after it) whose curves and
  durations match each scene's "How it moves", and build through it as usual, so `check:motion` still holds.
- **Its screens from its frames.** Where it shows a product, rebuild that UI in code as it looks in the frames: §3's
  "from its own source" is for the project's own product.
- **Same scenes, same lengths.** Keep the beats as the board has them, one per scene. Compare every beat with its
  scene in `spliced film sheet <slug> --beat <id>` and fix what differs (position, size, timing, colour) before marking
  it review. Say what you could not match.

## 1. Brief

The board is the script (read it with `spliced board show "<name>" --md`). Create
`remotion/src/films/<slug>/BRIEF.md` (slug: `feature-what`, e.g. `search-launch`) from it, with:
- the news in one sentence, audience, destination, aspect, length;
- **the motion profile** (from the board, else the project's default in `spliced.json`). Compare profiles in the
  composition `Specimen-Profiles` (`npm run dev`);
- the beats: for each, the reference scene IDs (`film/sNN`) and system moves (`system-moves/sNN`) it borrows.

**Facts come from sources, never from guesses:** the product itself (its code, where `spliced.json` `"app"` says),
the company's documentation, launch material, or the person. Find the moments the film shows with
`remotion/docs/CRAFT.md` §1; if you can't get strong ones, ask its questions instead of inventing.

## 2. Storyboard (get a yes before code)

Fill in `storyboard.json`, one entry per beat: `id` (its key in `cues.json` scenes, where its time on the beat grid
lives), `title`, `refs` (the borrowed scene and system-move IDs), `on_screen`, exact `copy`, `roles` (which profile
roles carry the motion: enter, move, ui, emphasis, camera, textReveal, viewChange), `sound`, `status` and `review`.
Set `composition` once it's registered in `remotion/src/Root.tsx`. The person reads and approves it in the Build view
(it shows each beat next to its references before anything is rendered). For each borrowed scene, read its section in
`library/references/<film>/breakdown.md` (how it moves, recreate). Rules for copy, type, stage, camera and sound:
`remotion/docs/CRAFT.md` (§2 to §5, §8), then the film's profile.

## 3. Screens

Rebuild the product's UI in code from its own source, never from screenshots: `remotion/docs/CRAFT.md` §6 (the code
`spliced.json` points at, read-only; real labels with fictional data). Logos come from the product's own SVGs.
If you have UI or motion skills of your own (for restraint, framing, sequencing), use them for what's inside a panel,
with timings always from the film's motion profile.

## 4. Build

- Code lives in `remotion/src/films/<slug>/`; register a composition in `remotion/src/Root.tsx`. Start from an
  existing film's structure (`splice-explainer` from `spliced kit starter` is the smallest complete one): `cues.json`
  holds every time, components take film time `t`, `Film.tsx` lays the scenes on the cues.
- **Beat by beat.** Take the next beat from `spliced film status` (open notes first). `mark` it wip, build it, render
  just that beat (`spliced film render <slug> --beat <id>`), and read its sheet (`spliced film sheet <slug> --beat
  <id>`): does the render do what the storyboard says, and does it borrow the reference's move? Then `mark` it review.
  Keep beat ids and `cues.json` scene keys in step: rename both or neither. A new beat goes in both files.
- **All motion goes through the profile:** `const m = motion('<profile>')` from `../../lib/motion`, then `m.enter`,
  `m.exit`, `m.move`, `m.ui`, `m.emphasis`, `m.camera`, `m.textReveal(t, start, i)`, `m.word(t, start, i, ink)` (a word
  in the profile's text style), `<m.ViewChange>`, `m.idle`. Specific system moves (container transform, symbol
  effects, Liquid Glass) are components and helpers in the same library; their code is in the `system-moves` scenes'
  Recreate field and in `remotion/docs/MOTION-SYSTEMS.md`, which also maps library tags to helpers. Holds creep in
  with `holdPush`. Never write easing, springs or GSAP-style eases inline (`npm run check:motion` finds them).
- **Real footage first** for what code can't draw (places, hands at work, nature): `spliced stock search "<query>"
  --kind video|photo`, then `spliced stock get <id> --film <slug>`, which records author and licence. Avoid shots
  where a recognisable person or brand is the subject. Generate only when nothing real fits and the person has a
  generator connected (any image or video model your AI can reach), never anything with words or a graphic style, and
  propose the prompts before spending credits. With no generator, code and real footage are the whole palette.
- **Voice-over is optional.** A film with no voice carries its words on screen: say so and go on, never block on it.
  When there is one, the board's `vo` lines are the script. Keep about 150 words a minute; time beats to the read
  (`spliced voice`). Three ways to get the reads, whichever the person has:
  - *An ElevenLabs key in the project's `.env`:* `spliced voice record <slug>` reads the changed lines itself.
  - *A voice service your AI is connected to* (ElevenLabs or any other): `spliced voice record <slug> --agent` (MCP:
    `film_voice` with action `lines`) gives each line with its prompt and voice; generate each exactly as written,
    download the reads, and file them with the `then` command it prints (`spliced voice file <slug> <line> <files>`,
    `film_voice` action `file`), which levels them (and, for ElevenLabs, cuts the lead-in away).
  - *The person reads it themselves:* one audio file a line, filed with
    `spliced voice file <slug> <line> <file> --plain --source recording`.

  Then `spliced voice fit <slug>`. The project's voice is spliced.json `"voice"` (`provider`, `name`, and for
  ElevenLabs `voice_id` and `model_id`).

## 4b. Sound (once the picture is close to locked)

Follow `remotion/docs/SOUND.md`: ask for the direction first (or take it from the film's profile), then music takes split into
stems and arranged to the cuts (drums alone from the first click, then bass, then the band), and the shared UI kit
placed on the film's cues. Music can come from any generator your AI is connected to, from a track the person has the
rights to, or be left out: SOUND.md section 2 says how each is filed. The UI kit ships with Spliced and needs no service.

```bash
spliced soundkit takes <slug>     # measure the takes, split stems, flag vocals or quiet drums
spliced soundkit score <slug>     # cues.json music: anchor, arrangement, takes -> takes.json + music lane
spliced soundkit sfx <slug>       # the film's sound_events.py on the shared kit -> sfx lane
spliced soundkit loudness <render>   # about -16 LUFS
```

All takes are level-matched in the Sound panel's Takes, so the person picks by ear. Sound notes close with
`spliced film sound-done`; a retimed beat needs `score` and `sfx` run again.

## 5. Check (say what you checked and what you couldn't)

```bash
cd remotion
npm run typecheck
npm run check:motion                     # no hand-written motion outside the profile
spliced film render <slug>               # whole film, half size, versioned
spliced film sheet <slug>                # every beat: storyboard | reference | render
```

Look at the pairing sheet and full-size stills of every product close-up (`npx remotion still src/index.ts
<Composition> out/x.png --frame=<n>`, or a frame from the render with `npx remotion ffmpeg -ss <seconds> -i
out/<render>.mp4 -frames:v 1 out/x.png`), then go through the checklist in `remotion/docs/CRAFT.md` §10. You can't
watch it in motion or hear it: say so.

## 6. Deliver

Render at full size (`spliced film render <slug> --scale 1`, or 2 for a 4K master; versions count up on their own),
and report: the file, its length, the profile, which beats borrow which scenes, what you checked and anything
uncertain. Point the person at the Build view to review it. On notes, make the changes, close each one, and send the
next version without re-planning.
