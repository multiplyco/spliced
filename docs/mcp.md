---
title: The MCP server
description: Spliced's tools for an agent that has no shell. The same things the commands do, offered over MCP.
section: ai
order: 3
---

An agent with a shell uses the `spliced` command. The MCP server offers the same to agents without one. Your agent starts it, not you:

```bash
spliced mcp
```

`spliced agents install` registers it in the project's `.mcp.json`, and in `.gemini/settings.json` for Gemini CLI. `spliced connect` adds it to a chat app. See [Connect your AI](connect-your-ai.md).

## The tools

### The project and the library

| Tool | What it does |
| --- | --- |
| `project_info` | Where an agent starts: what this project is, what is set up, its boards, its films, and any import waiting |
| `library_search` | Search the library's scenes by words and tags |
| `library_scene` | One scene's breakdown, with its frames as a picture |
| `library_build` | Rebuild the library after a breakdown changed, or only validate it |
| `folders` | The project's folders |
| `profile` | The project's [profiles](profiles.md): list them, read one before building in it, start one, draft one from files or a website, keep a rule the person stated, pin a scene that shows the look |

### Boards

| Tool | What it does |
| --- | --- |
| `board_read` | A board as a script: its brief, motion profile and beats. With no board, the list of boards |
| `board_edit` | Change boards, reviews and saved moments with named operations, applied in order, all or nothing |
| `show_in_app` | Point your open Spliced tab at a board or a scene |

### Films in production

| Tool | What it does |
| --- | --- |
| `film_new` | Start a film from a board |
| `film_status` | A film beat by beat: each beat's window, status, references and open notes, and its renders |
| `film_notes` | The notes you pinned to moments of a film, open ones first |
| `film_note` | File, answer or close a note |
| `film_mark` | Set a beat's status as the agent works |
| `film_sheet` | A film's newest render against its plan, beat by beat, as one picture |
| `film_render` | Render a film, or one beat of it, in the background |
| `film_voice` | A film's voice-over, read with the agent's own ElevenLabs connector |
| `film_kit` | The film kit: is it installed and current |

### Bringing things in

| Tool | What it does |
| --- | --- |
| `reference_add` | Queue reference films from links or file paths |
| `import_folder` | Look inside a folder you already have, and bring it in |
| `imports` | The import queue: list, pick up the next job, report it done |
| `uploads` | Uploaded images, GIFs and clips: the ones not read yet, and storing a reading |

## What it will not do

No MCP tool sets or reads a service key. Keys are yours: you add them in Settings, or with `spliced keys set <service>` in your own terminal.
