---
title: The film kit
description: A Remotion setup for making films from your boards. A motion library, every move as a specimen, and recipes for craft and sound.
section: make
order: 1
---

Spliced's film kit lives in your project's `remotion/` folder. A film asks for a role (an entrance, a move, the camera) and a motion profile decides how it moves.

`spliced setup` installs the kit and adds the example film. On its own:

```bash
spliced kit install      # into remotion/, with its packages (Remotion, React) from npm
spliced kit starter      # the example film (Spliced's own introduction), to read, render and borrow from
spliced kit update       # after updating Spliced: its files replaced with the new ones
spliced kit packages     # a clone without the packages: install them
spliced kit              # what is installed, and whether it is current
```

> **Remotion is not part of Spliced.** `spliced kit install` fetches it from npm. Remotion is free for individuals and small teams and needs a paid licence of your own above that. Spliced says so each time it installs it.

## What is in it

- **A motion library.** Entrances, moves and camera, each asked for by role.
- **Specimens.** Every move as a scene you can browse in the Systems view and borrow like any other.
- **Recipes.** `docs/CRAFT.md`, `MOTION-SYSTEMS.md` and `SOUND.md`.
- **UI sounds.** One shared set, so every film starts from the same sounds.

## The kit's files and yours

| Whose | Which files | What `kit update` does |
| --- | --- | --- |
| The kit's | `remotion/src/lib`, `src/specimen`, the docs, the UI sounds | Replaces them. A file you changed by hand is listed and left alone |
| Yours | Your films, `Root.tsx`, `remotion/src/profiles.ts`, `remotion/docs/HOUSE.md` | Never touches them |

## Motion profiles

A motion profile is how everything in one film moves: how fast things arrive, whether they bounce. One per film, so it feels made by one hand. Four ship with the kit:

| Profile | How it moves |
| --- | --- |
| `soft` | Calm and precise: arrive fast, land soft, slow camera, no bounce. The default |
| `material` | Material 3: emphasized curves, shared-axis view changes |
| `apple` | Apple-style: springs everywhere, a small bounce on UI |
| `splice` | Spliced's brand: crisp ease-out arrivals, no bounce |

Add your own in `remotion/src/profiles.ts`, name it in `spliced.json`, and pick the project's default:

```json
{ "profiles": { "acme": "Quick arrivals, a hard stop, no bounce" }, "default_profile": "acme" }
```

`spliced motion` checks that a film's motion comes from its profile.

## Packages install themselves

A project you clone, a new worktree or a teammate's machine has the `remotion/` folder but not its packages. Opening it in Spliced starts installing them in the background, at exactly the versions the project's lock file names, and Setup shows them as being installed until they are in. A render started before then installs them first.

## Making a film

Ask your AI to make a film and it follows the [make-film skill](skills.md). The next page, [Render and review](rendering.md), covers the loop from there.
