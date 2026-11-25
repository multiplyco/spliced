---
title: Voice, sound and footage
description: The voice-over line by line, the score arranged to the cuts, UI sounds on the cues, and free footage with its licence.
section: make
order: 3
---

Spliced generates nothing itself. Voice and music come from your own services, and Spliced does the bookkeeping: which line changed, which take is chosen, where each sound lands.

## Voice-over

The script is the storyboard: each beat's spoken line. A line whose script differs from what was recorded is "changed", and only those are recorded again. Every take is levelled to the same loudness and kept, and you choose which one plays in the [Sound](sound.md) tab.

```bash
spliced voice status launch       # every line: script against recorded, takes, fits its beat?
spliced voice record launch       # record the changed lines
spliced voice fit launch          # time the film to the chosen reads
```

A film needs no voice at all: without one, its words are the ones on screen. When it has one, there are three ways to get the reads, whichever you have.

### An ElevenLabs key

`record` reads through ElevenLabs with a key in the project's `.env`. Add one in Settings, or with `spliced keys set elevenlabs`.

### A voice service your AI is connected to

ElevenLabs or any other: your AI makes the reads with its own connector, and Spliced files them. No key is needed in the project.

```bash
spliced voice record launch --agent           # each changed line as a ready prompt, and the command that files it
spliced voice file launch <line> <files>      # take its reads in as takes
```

For a service other than ElevenLabs, name it in `spliced.json`: `"voice": {"provider": "<its name>", "name": "<the voice>"}`.

### Your own recording

One audio file a line, filed the same way:

```bash
spliced voice file launch <line> <file> --plain --source recording
```

## Music and UI sounds

```bash
spliced soundkit takes launch       # every music take: length, tempo, brightness; splits its stems
spliced soundkit score launch       # arranges each take to the picture
spliced soundkit sfx launch         # places the film's UI sounds on its cues
spliced soundkit loudness <file>    # a render's loudness; aim for about -16 LUFS
```

A music take is an audio file from anywhere: a music generator your AI is connected to, a track you have the rights to, or none. The UI sounds come with the film kit and need no service. The kit's `docs/SOUND.md` has the whole recipe, and says how each kind of take is filed.

## A film's sound, taken apart

```bash
spliced sound analyze launch      # voice, music and effects on separate lanes, on the music's beat grid
spliced sound show launch         # the sound map as text, with open sound notes
spliced sound analyze --video <file> --separate    # any video or audio file, such as a reference
```

## Free footage and photos

Not everything has to be generated. `spliced stock` searches free libraries and records where each file came from.

| Source | What it has | Key |
| --- | --- | --- |
| `pexels` | Photos and videos | A free key |
| `pixabay` | Photos and videos | A free key |
| `unsplash` | Photos | A free key |
| `nasa` | Photos and videos | None |
| `openverse` | Photos | None |

```bash
spliced stock sources
spliced stock search "studio photoshoot" --kind video
spliced stock get pexels:video:12345 --film launch
```

`get` downloads the file into the film and records its source, author, licence and page, so Assets shows where it came from.

> Depicted people, brands and logos can carry rights of their own. Check before a person or a trademark is the subject of a shot.
