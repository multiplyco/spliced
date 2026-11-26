---
title: The project folder
description: A project is a folder with a spliced.json in it. Put it in git, move it, hand it to someone else.
section: reference
order: 2
---

Everything Spliced knows about your work is in one folder on your machine. There is no account and no cloud of its own.

## What is in it

| In the project | What it holds |
| --- | --- |
| `spliced.json` | The project's settings |
| `library/` | Reference films broken down scene by scene, your uploads, your boards and reviews |
| `reference/` | The downloaded films |
| `profiles/` | Your [profiles](profiles.md): the looks your films are made in, one folder each |
| `remotion/`, `videos/` | Films in production, if you make them here |
| `.cache/` | Rebuilt on demand. Never served or committed |
| `.env` | Your service keys. Never served or committed |

### Inside `library/`

| File | What it is |
| --- | --- |
| `TAXONOMY.md` | The project's fixed list of tags |
| `STYLES.md` | The project's notes on looks, pace and moves |
| `references/<slug>/breakdown.json` | One film's breakdown. This is the file to edit |
| `references/<slug>/analysis.json`, `sheets/` | The machine pass |
| `INDEX.md`, `breakdown.md` | Generated. Run `spliced library` to rebuild them |
| `state.json` | Your boards, reviews and saved moments |
| `uploads/` | Uploaded pictures, GIFs and clips |

Breakdowns, boards and notes are JSON and Markdown, readable without Spliced.

## spliced.json

`spliced setup` (or `spliced init`, which makes only the project) writes the first three lines. Everything else is optional.

```json
{
  "format": 1,
  "name": "Mine",
  "brand": { "name": "Acme" },
  "default_profile": "soft",
  "profiles": { "acme": "Quick arrivals, a hard stop, no bounce" },
  "agent": { "runner": "claude", "permissions": "ask", "name": "Robin" },
  "app": { "code": "~/code/your-app" },
  "folders": [{ "folder": "branding-videos", "name": "Branding videos" }],
  "worktree_renders": "main",
  "worktree_profiles": "main"
}
```

| Key | What it says |
| --- | --- |
| `name` | The project's name |
| `brand.name` | Whose films these are |
| `default_profile`, `profiles` | The motion profile films start with, and the ones this project adds. See [The film kit](film-kit.md) |
| `agent.runner` | Who reads imports: `none` (the default, your own AI session) or `claude` (a background session) |
| `agent.permissions` | What a background session may do: `ask` or `bypass`. See [Imports and breakdowns](imports.md) |
| `agent.name` | What the app calls your AI |
| `app.code` | Where your product's real code is: a folder or a GitHub address, or a list of them |
| `folders` | The project's folders. `spliced folders add` writes them |
| `worktree_renders` | Where a render made in a git worktree goes: `main` (the default) or `worktree` |
| `worktree_profiles` | Where a git worktree reads and writes profiles: the main checkout's (`main`, the default) or its own (`worktree`). See [Profiles](profiles.md#git-worktrees) |

## In git

A new project's `.gitignore` keeps `.cache/` and `.env` out. The rest is yours to commit: the library, the boards, the films' code.

## More than one project

Each project is its own folder. Run commands from inside one, or name it:

```bash
spliced --project ~/films/other board boards
```
