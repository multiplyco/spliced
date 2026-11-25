---
title: Imports and breakdowns
description: What happens to a film after you add it. The machine pass runs on your machine, and the reading waits for your AI.
section: ai
order: 4
clip: Cut into scenes
---

Adding a film is a job in a queue. A job has four steps, and only one of them needs an AI.

| Step | Who does it | What happens |
| --- | --- | --- |
| Download | Spliced | The film is fetched into `reference/` |
| Analyse | Spliced | The machine pass: cuts, tempo, palette and contact sheets |
| Break down | Your AI | The film is read and written down scene by scene |
| Library | Spliced | The breakdown is validated and the library is rebuilt. Open tabs reload themselves |

## In the corner

While a film comes in, the panel in the app's bottom corner shows its step. A finished import or analysis stays there, with **Open** to go straight to it, until you close it with its own ×, or all of them with the panel's. It stays after a reload too.

## The machine pass

Agents can't watch video or hear audio, so the machine pass turns both into things they can read. It writes `library/references/<slug>/`:

- `analysis.json`: the hard cuts, the shots between them with their energy, palette and brightness, and the audio's tempo and beats.
- `sheets/overview.jpg`: the whole film as one contact sheet, with timestamps.
- `sheets/shot-NN.jpg`: a few frames of each shot.

Shots are machine-detected spans from cut to cut. Scenes are decided by whoever writes the breakdown.

## By default, nothing starts on its own

The breakdown is your AI's work, and it waits for you to hand it over. The job shows as "needs your AI", with the line to give it. In your AI's session:

```bash
spliced imports next          # the oldest job waiting, with exactly what to do
spliced imports done <id>     # that reading is finished: the job carries on
```

Or just tell it: "Pick up the import and break the film down."

```bash
spliced imports list          # every job and its step
spliced imports cancel <id>
```

## Or let a background session do it

If you would rather have it happen in the background, say so in `spliced.json`:

```json
{ "agent": { "runner": "claude", "permissions": "ask" } }
```

With `claude`, each import starts a headless Claude Code session. It costs a session per film.

| Permissions | What the background session may do |
| --- | --- |
| `ask` | The default. Read, edit files in the project, and run Spliced's own commands. Anything else is refused |
| `bypass` | Anything. Removes the fence |

> A film's page or an uploaded file is content from the internet, read by an agent. Choose `bypass` knowingly, and only for a project whose sources you trust.

## The breakdown

A breakdown is `library/references/<slug>/breakdown.json`. For each scene it says what is on screen, how it moves and how to recreate it, with tags from the project's taxonomy.

Tags come only from `library/TAXONOMY.md`. A scene is tagged by its role, world, subject, camera, motion, how it arrives, type treatment, pace, energy and what it would take to recreate. To add a tag, add it to the taxonomy first with a one-line definition, then use it.

```bash
spliced library                 # validate every breakdown and rebuild the library
spliced library --check         # validate only, write nothing
spliced library <slug>          # one film
```

`library/INDEX.md` and every `breakdown.md` are generated. Edit `breakdown.json`, then run `spliced library`.
