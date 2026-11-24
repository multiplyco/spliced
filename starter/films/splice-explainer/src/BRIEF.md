# Spliced: how it works

An example film that ships with Spliced: the film the app's welcome plays. Read it, render it, and borrow from it.

**News:** Spliced turns the films you love into named, reusable moves, and builds new films from them.
**Audience:** people new to Spliced. **Destination:** the app's welcome, the Spliced page.
**Aspect / length:** 16:9, 36 s. On-screen type, a deep techno score and UI sounds; no voice.

**Brand:** Spliced. Dark by default; volt (`#DFFF1A`) only for the primary button, selection, playhead and focus;
Anybody wide uppercase for the headlines, Inter for UI, JetBrains Mono for labels and timecodes. The logo is the
outlined lockup (`public/films/splice-explainer/brand/`); the mark is drawn in code (`brand.tsx`) so its four blocks
can run the brand's own build-in and sink-and-rise.

**Motion profile:** `splice` (built into the kit, `src/lib/motion/profile.tsx`): the brand's ease-out, ease-ui and
ease-sink curves, film-slowed. Words sharpen in; no bounce.

**What is on screen:** the app itself, rebuilt in code (`ui.tsx`, `Scenes.tsx`). The library and the board in it show
frames of a made-up film ("Plan it together", for a product that doesn't exist) and of the kit's own moves
(`frames.json`, `public/films/splice-explainer/frames/`). Nothing of a real film or a real company is on screen, so
all of it is free to borrow.

| # | Beat | The move | Copy |
| --- | --- | --- | --- |
| 1 | open-a-caret | a blank field, a caret blinks, words type in | Films you love. / Frame by frame. |
| 2 | paste-a-link | a whip into the prompt box, a link pastes in | Paste a link. |
| 3 | cut-into-scenes | a scan line runs down the film, then its scenes fan out into a row | Cut into scenes. |
| 4 | name-every-move | a chip whose label rolls like a slot reel through the move names | Every move, named. |
| 5 | find-it | a search, the grid sorts, the match gets a ring | Find it in seconds. |
| 6 | board-it | a loose pile of scenes snaps into an ordered row | Borrow the move. / Write the script. |
| 7 | with-claude | a second cursor edits the board live | Claude works with you. |
| 8 | build-view | blur through to the render beside what it borrows, notes pinned on the timeline | Every beat, / beside its reference. |
| 9 | end-card | the mark's blocks assemble, the lockup settles | Spliced / Study it. Name it. Make it. |

**How it was made:** `demo_frames.py` drew the made-up film's frames in HTML and CSS, `score.py` fitted the score to the cuts, `sfx.py` made
the UI sounds from ElevenLabs Sound Effects takes (the raw takes aren't included), `sync.py` placed them on the cues.
The score is an original ElevenLabs Music take.
