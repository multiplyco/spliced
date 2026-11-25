---
title: Connect your AI
description: Give your AI Spliced's skills and tools, in a project folder or in a chat app.
section: ai
order: 1
clip: With Claude
---

Spliced does no AI work itself. Your agent reads the films, writes the breakdowns, builds the film and answers your notes. Two commands connect it.

## An agent that opens the project folder

```bash
spliced agents install
```

Run it inside your project (`spliced setup` already did, as one of its steps). It gives the project's AI what it needs:

- Spliced's skills, in `.claude/skills/`. A skill file you changed is kept. See [Skills](skills.md).
- A section in the project's `AGENTS.md` that says how to work here.
- Spliced's MCP server in `.mcp.json`, for agents that have no shell. See [The MCP server](mcp.md).

It also keeps your keys out of reach: Claude Code is set to refuse to read `.env`, and Gemini CLI's file tools are told to skip it.

| Your AI | How it picks Spliced up |
| --- | --- |
| Claude Code | Finds the skills in `.claude/skills/` and the tools in `.mcp.json`. It asks before using the tools the first time |
| Codex | Reads `AGENTS.md`. Register the tools with `codex mcp add spliced -- spliced mcp` |
| Cursor | Reads `AGENTS.md` and `.mcp.json` |
| Gemini CLI | Reads `GEMINI.md`, which points at `AGENTS.md`, and `.gemini/settings.json`. The first time, it asks whether to trust the folder: say yes and the tools switch on |

Several agents can work on one film in the same folder, each reading the same plan. Another agent that can run commands in your project can use the same `spliced` commands.

## A chat app

Chat apps don't open a folder, so they keep their own list of tools. `spliced connect` adds this project to that list, as `spliced-<project>`.

```bash
spliced connect                        # which apps are connected to this project
spliced connect claude-desktop         # the Claude desktop app; quit and reopen it afterwards
spliced connect cursor                 # Cursor, for every window
spliced connect codex                  # Codex
spliced connect cursor --remove        # take this project out again
spliced connect cursor --dry-run       # show what would change, change nothing
```

Then, in any chat, the app can search your library, read a scene, and read or change a board, the same as an AI working in the folder. Each project is added under its own name, so you can connect several. Everything else in the app's settings is kept, and so is the file as it was before the first change.

In the app, **Connect your AI** in Setup does both steps from one sheet: a box for the agents that open the folder, and one for each chat app it found on your machine, ticked when already connected. In the Mac app it is also in the Project menu.

> Run `spliced connect` from your main checkout, not from a git worktree. An app pointed at a worktree breaks when the worktree is removed. `--here` connects a worktree anyway.

## What the app calls your AI

The app says "Claude" when the project has Claude read its imports, and "your AI" otherwise. Set your own name for it in `spliced.json`:

```json
{ "agent": { "name": "Robin" } }
```

## Let your AI do the setup

The home page has [one message to paste](https://spliced.video/#works) into Claude, Codex, Cursor or Gemini. It installs Spliced, sets up your first project and connects itself.
