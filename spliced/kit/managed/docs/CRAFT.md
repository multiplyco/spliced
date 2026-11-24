# Craft: how a film should look, read and sound

Defaults learned from making product films with this kit, mostly from notes left on renders. The brief or the person
can overrule any of them, and a project can add its own house rules beside this file (for example
`docs/HOUSE.md`: its typefaces, its stage, its product's code). Motion values live in the film's motion profile
(`MOTION-SYSTEMS.md`), sound in `SOUND.md`; this file is everything around them.

This file is Spliced's (`spliced kit update` replaces it). Put your own rules in your own file.

## 1. Finding what the film shows

A film is as good as the moments it picks. Before the board, list what the film could show and keep the strongest.

- **Sources, in this order:** the product itself (its code, where `spliced.json` says it is: `"app": {"code": ...}`,
  see §6), the company's own documentation, launch material (release notes, the pull request, the changelog), then
  the person. Never fill a gap with a guess: a beat that shows something the product doesn't do sinks the film.
- **What makes a strong moment:** it exists today, end to end; the audience recognises the job in two seconds;
  something visibly changes on screen (a list fills, a status ticks, a card arrives, a draft appears); and it can be
  triggered by one click or a short typed line.
- **Write more than you need,** five or so, each as: the line on screen, the action, the visible result. Keep the
  ones whose results look different from each other, order them from simple to most valuable, and end on something
  the viewer would want to have.
- **When you can't find three strong ones, ask** instead of padding: what can a user do now that they couldn't
  before, where does it start in the app, what changes on screen when it works, what must the film not claim, and
  where will it run (format and date). A shorter film with two strong moments beats three with a weak one.

## 2. Copy

- **Lines are short and spoken.** One idea per line, two lines at most on screen, words the audience would say.
  Read every line next to the one before and after it: repeated words and lines that don't connect are the notes
  that come back most.
- **Claims must hold up.** A value line needs its subject defined on screen ("there" with nothing to point at fails).
  Prefer a concrete promise to a slogan.
- **Product words are the product's.** If the UI says "Opportunities", the film says opportunity, not idea.
- **Ellipses in a script mark a breath in the voice-over;** don't print them unless asked.

## 3. Type

- **One family per film for film type,** at one or two weights: the product's own face, or a house face the brief
  names.
- **Words arrive in the profile's text style** (`m.word`): blur to sharp, or grey to ink for a profile with
  `text: {style: 'greyToInk'}`. Unsaid words keep their space so a line never reflows while it builds.
- **Size for the frame, then smaller.** Notes ask for smaller type and a camera far enough back to see the whole line
  more often than the reverse. A word that stays while others leave stays centred and the same size.
- **Colour on a word only if it earns it;** white or ink is the safe answer.
- Type is code, never baked into a generated image, so it can be changed later.

## 4. Stage, grid and light

- **One world per film,** chosen in the brief: a white stage with soft shadows, a dark stage with one coloured light,
  or the brand's own ground.
- **An opening frame should draw the eye:** an ambient background with some colour and one high-quality object in the
  middle (a glass badge, a prompt box, the mark), not a flat grey field.
- **Light belongs to the scene, not to each card.** One light falls across every panel; no per-card blooms or glows.
- **Backgrounds can move a little** (a slow dot field, grain) but never compete with the subject.
- If a film uses a grid or guides, they are part of the world: they move with the camera, never on their own.

## 5. Camera

- **One camera per shot.** Everything in the shot (stage, UI, type) sits under one transform driven by `m.camera`,
  so nothing slides against anything else.
- **Slow enough to read.** Camera moves run about a second; after an answer or a result lands, hold long enough to
  read it before the camera moves on.
- **Move the camera or the content, not both.** Pull back first, then let the list sort or the cards fly.
- **Holds keep breathing:** `holdPush` (from `src/lib/motion`) creeps a held shot in, gentler on wide UI (about 0.0008
  per frame) than on footage (0.0025 to 0.004).
- **No dead air between scenes.** A pause inside a beat is fine; a gap at a cut reads as a mistake.
- **Cursors are characters.** A cursor clicks exactly on the real button it presses, moves on an arc, and is large
  enough to see.

## 6. Real UI, rebuilt in code

Every screen of the product in a film is its real UI, rebuilt as components: sharp at any zoom, every piece can move
on its own, and labels and data can be set to tell the beat.

1. **Read the product's code, don't invent.** Where it is comes from `spliced.json` (`"app": {"code": ...}`); read
   it without changing the checkout (`git show origin/main:<path>`). Take the views, the components and the design
   tokens (colours, radii, type) from there. Logos come from the product's own SVGs, never retyped.
2. **Real labels and states, fictional data.** Keep one fictional cast across a project's films. Never real customer
   data.
3. **Simplify to the concept.** Keep only the chrome a viewer needs to recognise the product; one prompt, one tile,
   one answer. Widgets keep their size when their state changes, and a panel shows all its rows from the start while
   the animation fills them in.
4. **Inside a panel, keep it plain:** one neutral ramp, three text roles, two weights, tabular figures, no emoji or
   colour washes. Motion timings come from the profile.
5. **Stylise by light, depth and material only:** tilt, glass, shadow, placement in the scene. Never by changing what
   the product says or how it's laid out.
6. **Third-party UI** in a film (a mail client, a chat app) looks right and uses that company's real logo as it is:
   a squashed or wrong logo is the first thing a viewer notices.
7. Check the rebuild as a still before animating: `npx remotion still src/index.ts <Composition> out/x.png --frame=N`.

## 7. Footage and generated images

- **Real footage first** (`spliced stock search`), generated only where nothing real fits, and never for anything
  with words, patterns or a graphic style (those are code, 3D or a script).
- **Moving, not still:** a still in a montage reads as a hole. Every visual in a reel moves.
- **One continuous capture per beat:** the same person, the same light, the shot continuing, not a run of unrelated
  clips.
- **Generated clips need direction:** saturated colour, a camera that moves with intent, a clear sense of scale, one
  colour world per clip. Muted one-line prompts come back faded and samey. Propose prompts before spending.
- Check generated laptops and phones for brand logos and remove them.
- Record every generation (prompt, model, credits) and every stock file (author, licence) in the film's
  `assets.json`.

## 8. Sound

The full recipe is `SOUND.md`. The rules behind it:

- Original music per film, fitted to the cuts: drums alone from the first moment, then bass, then the band. The
  music starts with the film, not a second in.
- Cuts and moves land on the beat. Never jump from a high note into the start of a loop; cut on bar lines.
- UI sounds are crisp and tactile (the shared kit in `public/audio/kit/`), a subtle swoosh where things fly. No bells,
  dings or trailer hits.
- Voice: crisp, line by line (`spliced voice`), about 150 words a minute, and music and voice make room for each other.

## 9. The ending

- **The logo is the product's own file** (lockup or mark, black and white unless the film's world says otherwise),
  placed with care: centred or beside one well-placed piece of UI, nothing half visible at the edge.
- **One clean move into the end card,** no doubled or ghosted logo mid-animation (check the frames of the transition
  one by one).
- **Quiet:** a soft final hit or the music's last note, never a big impact.
- The end line is the film's thesis in a few words.

## 10. Before you send a render

- [ ] `npm run typecheck` and `npm run check:motion` pass; every move comes from the film's profile.
- [ ] `spliced film sheet <slug>`: each beat does what the storyboard says and borrows its reference's move.
- [ ] Full-size stills of every UI close-up and of the end card (`npx remotion still ...`, or pull frames from the
      render with `npx remotion ffmpeg -ss <seconds> -i out/<render>.mp4 -frames:v 1 out/<name>.png`).
- [ ] Every line read in sequence: no repeats, claims true today, product words verbatim.
- [ ] UI is the real UI with fictional data; cursors hit their buttons; third-party logos are right.
- [ ] No stills in montages, no dead air at cuts, no doubled logo at the end.
- [ ] Music starts with the film, cuts land on the beat, the mix sits around -16 LUFS (`spliced soundkit loudness`).
- [ ] Notes you fixed are closed (`render --fixes` or `spliced film done`); partly done ones have a `note-reply`.
- [ ] Say what you checked and what you couldn't: an AI can't watch the film in motion or hear it.
