# Sound: music and UI sounds for a film

A recipe that has worked: music that follows the picture, and small tactile sounds on every action. Do it once the picture is
close to locked: the times come from `cues.json`, so a retimed beat moves its sounds with it.

```bash
spliced soundkit takes <slug>        # measure every take, split it into stems (Demucs), flag vocals or quiet drums
spliced soundkit score <slug>        # arrange every take to the cuts, write takes.json and the music lane
spliced soundkit sfx <slug>          # place the UI sounds (the film's sound_events.py) from the shared kit
spliced film render <slug> --scale 1 # Remotion plays sound.json (lib/sound.tsx) in the render
spliced soundkit loudness remotion/out/<slug>-vN.mp4   # about -16 LUFS
```

## 1. Direction (before spending anything)

Ask for the direction in one message if the person hasn't given it: tempo, genre, energy, what to avoid. A project
can keep its approved direction in its own house rules (for example `docs/HOUSE.md`). Defaults that have held up:

- **Forward-moving**, about 120 to 126 BPM, for a product film. Slow, sparse music makes a short film feel long.
- **The beat builds with the picture:** drums alone from the first click, then the bass, then the band.
- **Never the stock-music sound:** no marimbas, no bright high melodies or plucky leads, no risers, no vocals.

## 2. Takes: where the music comes from

A take is one piece of music, about as long as the film. Everything after this step (measuring, stems, arranging to
the cuts, levelling) works the same on any audio file, so where a take comes from is a choice, and no service is
required. Ask the person which of these they have, in this order:

1. **A music generator your AI is connected to** (ElevenLabs Music, or any other that returns an audio file). Two
   takes per direction. Its recipe is below if it is ElevenLabs; for another, read that connector's own guide first.
2. **A track the person has the rights to:** their own music, a licensed library track, something a composer made for
   them. Ask for the file.
3. **Free music under an open licence**, when they have neither: public domain or CC0, or CC BY with the credit they
   will then owe. Never a licence that forbids commercial use (NC) or changes (ND): arranging stems is a change.
   Show the person the track, its author and its licence before using it.
4. **No music.** The UI sounds (step 5) carry a short film on their own, and it is a real choice, not a fallback:
   say so instead of inventing a source.

Whatever the source, a take is filed the same way:

- **The file** goes to `public/films/<slug>/audio/takes/<id>.mp3` (or .wav), and its id into `cues.json`
  `music.takes` (step 4).
- **Record it** in the film's `assets.json` (the Assets view shows it): for a generated take its prompt, service,
  model and credits; for a track someone made, its title, author and licence, and where it came from.
- **Prompts describe sound only** (genre, BPM, instruments, energy arc, what to leave out), in 1 to 3 sentences.
  Generators ignore second-by-second structure, so the arrangement to the picture is done in code (step 4).
- Ask for the film's length ("about 50 seconds") and propose the prompts before spending credits.

### With ElevenLabs Music

ElevenLabs MCP: one flow per film (`creative_create_flow`), then `creative_generate_in_flow` with node `music`, model
`eleven_music_v2_5`, `generations_count: 2`, one call per direction. A take costs about 900 credits per 50 s; the
takes come back as long as you ask for. Tool and model names change: check the connector's guide if a call fails.

- **Don't wire an audio reference** into the music node: referenced takes have failed with "unexpected error".
  Describe the reference's sound in words instead.

Two prompts that came back well:

> Upbeat organic jazz instrumental with a modern edge, B minor, driving at 126 BPM: a tight live drum groove with
> crisp snare and ride, punchy upright bass, warm Rhodes and piano comping, short low horn stabs. Confident and
> forward-moving, energy rising steadily over about 50 seconds to a clean final hit. Mid-range warmth, no marimba, no
> bright high melodies, no vocals.

> Driving electronic instrumental at 124 BPM, drum-led: a punchy live-sounding breakbeat with a crisp snare and rolling
> hats, a deep warm bass line, muted mid-range synth chords, steady forward momentum building over about 50 seconds to
> a clean final hit. Modern and tasteful, not stock music: no marimba, no plucky high leads, no risers, no vocals.

## 3. Measure and split

`soundkit.py takes <slug>` prints each take's length, tempo, high-end share (bright hats or leads) and the level of
each stem, and splits every take into `audio/stems/<id>/` (drums, bass, other, vocals). It flags:

- **VOCALS:** the takes come back marked "Instrumental: False" even when the prompt says no vocals. Check this flag.
- **Quiet drums:** a take whose drums are near silent at the start can't open drums-first. Give it `arranged: false`.

## 4. Score: arrange the stems to the cuts

In `cues.json` `music`:

```json
"music": {
  "anchor": 0.95, "fade": 1.6, "rms": -16.5, "gain": 0.9, "take": "forward-jazz-2",
  "arrangement": {"drums": 0, "bass": 3.5, "other": 7.5, "breaths": [[44.05, 44.8]]},
  "takes": [{"id": "forward-jazz-2", "name": "Forward jazz B", "note": "...", "arranged": true}, "..."]
}
```

- **anchor:** the film time where each take's first strong hit lands. Use the first click or the first visual hit;
  the frames before it stay silent.
- **arrangement:** when each stem comes in, on scene starts (`cues.scenes`). `breaths` drop to drums alone over a
  moment (the black after Send), and the band comes back at the end of it.
- **fade:** into the last frame. **rms:** takes are level-matched, so switching takes changes the style, not the
  loudness.

`soundkit.py score` writes every take (the person auditions them in Build, Sound, Takes) and puts `take` in the
music lane of `sound.json`.

## 5. UI sounds: the shared kit on the film's cues

The kit (`public/audio/kit/`, `kit.json`): crisp phone-keyboard keys and a tactile tap in
the spirit of the iPhone keyboard (all original takes, made for the kit), soft pops, crisp ticks, low thuds, slides, air and
a soft pass-by. Each kind has a level (peak dBFS of one hit) and a low-pass. A film can override them with `LEVELS` in
its `sound_events.py`.

The film's `sound_events.py` says which kind plays when, from its own cues:

```python
def events(C, E):
    B = C["beat"]
    E.one("save", "click Save", "click", "workspace", B["workspace"]["save"])       # a cursor press: its press time
    E.typing("name", "Nordvik Coffee", "workspace", *B["workspace"]["name"])     # one key per letter as it appears
    E.many("ticks", "deliverables ticked", "project", [(x, "tick") for x in B["project"]["ticks"]])
    E.file("joy", "a note as joy paints in", "remotion/public/films/<slug>/audio/fx/note-B5.wav", None, 24.54, gain=0.3)
```

`E.file` places one of the film's own sounds as it is (a played note, a sound made for this film) instead of a kit
hit; with `None` for the beat its time is already film time. Every sound the film has goes through `sound_events.py`,
so rebuilding the lane never drops a curated one.

| Moment on screen | Kind |
| --- | --- |
| a cursor press (any button) | `click`, at the press time |
| a letter typed | `key` (`space` for spaces); thin fast runs with `every=2` or `3` |
| a state or check turning on | `tick` |
| something arriving (a toast, an icon, a source) | `pop` |
| a card, panel or tile sliding in | `slide` |
| a cut, a whip, a big move | `whoosh` |
| a landing, the cut to black | `thud` |
| something sweeping past the camera | `pass` (the Connect carousel computes its own passes) |

Typing runs and groups go into one file each, so every hit stays sample-accurate.

## 6. Level and check

Aim for about -16 LUFS integrated (`soundkit.py loudness`): music `rms` -16.5, effects at the kit's levels sit
roughly 4 to 10 dB under it. You can't listen: say so, and say what you measured (loudness, take tempos, flags).

## New sounds for the kit

The kit that ships needs no service. To add a sound, use any sound-effects generator your AI is connected to, or a
recording. With ElevenLabs: node `sfx`, model `eleven_text_to_sound_v3`, `generations_count: 2`, about 17 credits
each. Prompts that made the kit:

- "Smartphone touchscreen keyboard typing: crisp, short, clean tactile key clicks, one tap at a time with small gaps
  between, light and precise, dry close-mic, no room, no music"
- "Single crisp UI button tap, a short clean tactile tock like pressing a button on a phone screen, dry, close-mic, no
  reverb" (one of the two takes came back silent: check every take's peak)
- "Soft round UI pop, a short clean bubbly pop like a card appearing on a phone screen, gentle and modern, dry, no reverb"
- "Tiny crisp tick, a very short clean tactile click like a phone toggle or checkbox, dry, close-mic"

Put the file in `public/audio/kit/`, add it to `kit.json` (`kinds`, and its prompt under `sources`), and rebuild.
