---
title: Setup and doctor
description: One screen that says what is ready on this machine, and the single step that unlocks the next thing.
section: start
order: 4
---

Setup lists what Spliced can do here, level by level. Nothing beyond browsing is required. Every line says what it unlocks and how to add it, with the command to copy.

In the app, open **Setup** from <kbd>⌘K</kbd>. In a terminal:

```bash
spliced doctor
spliced doctor --json     # the same answer, for a script
```

## The five levels

| Level | What Setup checks |
| --- | --- |
| Browse | The project, Spliced itself (and whether a newer version is out), uv, and whether the library has films in it |
| Collect | `ffmpeg` and `yt-dlp` |
| Analyse | An AI agent on this machine, Spliced's skills in the project, Spliced's tools offered to your agent, the AI apps connected to the project, and who reads imported films |
| Make films | Node.js, a render engine in the project, Spliced's film kit, and where your app's real code is |
| Generate | Free footage and photos, voice-over, music, and the generators in your AI. None of these is needed to make a film |

## Hand the job to your AI

**Copy for your AI** in Setup hands the whole job to your own AI, one step at a time. **Connect your AI** opens one sheet for the agents that open the folder and the chat apps on your machine: see [Connect your AI](connect-your-ai.md).

A missing tool comes with the command for your machine, and a copy key beside it. `spliced setup` does the first steps in one go: see [Install](install.md).

## Service keys

Nothing here is required. Spliced can record voice-over itself with an ElevenLabs key, and some footage libraries need a free key. Setup offers the place to paste one where a key is missing, and Settings has a Service keys section. The key goes straight into the project's `.env`. Spliced never shows it again: the app and `spliced keys` only say whether a key is set.

```bash
spliced keys                    # which keys this project has, names only
spliced keys set elevenlabs     # paste a key; it is not shown or echoed
spliced keys remove elevenlabs
```

The services are `elevenlabs`, `pexels`, `pixabay` and `unsplash`. `set` asks the person at the keyboard. Run by an agent, it refuses, so a key never passes through an agent's transcript.
