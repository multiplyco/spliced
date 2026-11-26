---
title: Commands
description: Everything the spliced command does. With no arguments, spliced lists them itself.
section: reference
order: 1
---

```bash
spliced <command> [arguments]
spliced --project <folder> <command>     # work on another project than the one you are in
spliced <command> --help                 # each command has its own help
spliced --version
```

Run commands from inside a project, or pass `--project <folder>`.

## Start and set up

| Command | What it does |
| --- | --- |
| `spliced setup [<folder>]` | Everything in one go: a project, your AI's skills, the film kit, the example film rendered, the app. Safe to run again, and what brings a project up to date after an update |
| `spliced init [<folder>]` | Start a new project and nothing else: `spliced.json` and an empty library |
| `spliced open` | Start the app in the browser. The server stays up until Ctrl+C. `--background` starts it and gives the terminal back, `--stop` stops it. `--port`, `--no-open` |
| `spliced doctor` | What this machine and project can do now, and the step that unlocks the next thing. `--json` |
| `spliced update` | Whether a newer Spliced is out, and the command that gets it. `--json` |
| `spliced projects` | The projects you have opened on this machine, and which are running now |
| `spliced agents install` | Spliced's skills, a section in `AGENTS.md` and its MCP server. A skill file you changed is kept; `--force` replaces it. `--lean` for [lighter Claude Code sessions](connect-your-ai.md) (`--keep <server>`, `--keep-connectors`, `--lean off`) |
| `spliced agents context` | What a Claude Code session in this project loads, and how to slim it. Changes nothing |
| `spliced connect` | Add this project's tools to an AI app: `claude-desktop`, `cursor`, `codex`. `--remove`, `--dry-run` |
| `spliced mcp` | Spliced's tools for an AI agent, over MCP. Your agent starts this, not you |
| `spliced keys` | Service keys in `.env`: which are set, and `set <service>` to paste one |

## The library

| Command | What it does |
| --- | --- |
| `spliced reference` | Add a reference film from a link or a file, and run the machine pass |
| `spliced import <folder>` | Bring in a folder of pictures, clips and films you already have. `--go` to do it |
| `spliced imports` | The import queue: `add`, `list`, `cancel`, and `next` and `done` for an agent picking a job up |
| `spliced uploads` | Uploaded images, GIFs and clips: `list`, `add`, `edit`, `pending`, `set` |
| `spliced analyze` | The machine pass on one film, and `strip` for a dense look at a moment |
| `spliced library` | Rebuild the library from the breakdowns. `--check`, `--links`, `--moves` |

## Boards and films

| Command | What it does |
| --- | --- |
| `spliced board` | Find scenes, read and edit a board's script, point the open app at one |
| `spliced film` | Films in production: status, `context` (a short brief for a new AI session), notes, render, the storyboard beside the render |
| `spliced folders` | The project's folders: list, `add`, `remove` |
| `spliced profile` | [Profiles](profiles.md): the looks your films are made in, the default, the rules learned. `show`, `new`, `set`, `motion`, `draft`, `digest`, `code`, `learn`, `default`, `move-home` |

## Making films

| Command | What it does |
| --- | --- |
| `spliced kit` | The film kit in `remotion/`: `install`, `update`, `starter`, `packages` |
| `spliced motion` | Check that a film's motion comes from its motion profile |
| `spliced moves` | Rebuild the library's film of the kit's own moves |
| `spliced voice` | Voice-over line by line |
| `spliced sound` | A film's sound taken apart: music, voice and effects on the beat grid |
| `spliced soundkit` | Make a film's sound: stems, score, UI sounds, loudness |
| `spliced stock` | Free footage and photos: search, and get one into a film with its licence |

## The ones you will use most

```bash
spliced setup ~/films/mine
spliced doctor
spliced open
spliced reference add "<link>"
spliced import ~/Movies/references --go
spliced imports next
spliced board find "typewriter"
spliced board show "Launch"
spliced film status launch
spliced film render launch
spliced library --check
```
