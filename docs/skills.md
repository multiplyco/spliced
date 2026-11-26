---
title: Skills
description: What your AI follows. Two skills, copied into your project, written for an agent that opens the folder and runs commands.
section: ai
order: 2
---

`spliced agents install` copies Spliced's skills into your project's `.claude/skills/`, and tells every agent where they are in the project's `AGENTS.md`. Running it again after you update Spliced (or running `spliced setup`) brings them up to the newest ones.

Spliced remembers what it put there, so a skill file you changed is yours: it is left alone and named. `spliced agents install --force` replaces it and keeps your version in `.cache/skills-kept/`. Files you add to a skill's folder are never touched.

## add-reference

Adds reference films to the library and breaks them down scene by scene. Your AI uses it when you give it links or files you like: "add these references", "break down this launch film".

What it does, in order:

1. Downloads each film, registers it and runs the machine pass.
2. Writes the breakdown, scene by scene: what is on screen, how it moves, how to recreate it.
3. Validates the breakdowns and rebuilds the library.
4. Renames a film once it knows what it is.
5. Merges any new tags into the project's taxonomy.
6. Updates `library/STYLES.md`, the project's own notes on looks, pace and moves.
7. Tells you what it added.

## make-film

Builds a launch, feature, explainer or social film in Remotion with Spliced's [film kit](film-kit.md), from a board's build prompt or from a brief. Your AI uses it when you ask it to make, storyboard, animate or render a film, or when you leave notes on a render in Build.

What it covers:

1. **Brief.** What the film says and who it is for.
2. **Storyboard.** It gets a yes from you before writing code.
3. **Screens.** Your product's interface, rebuilt from its real code if the project says where that is.
4. **Build.** The film, beat by beat, with motion from its motion profile.
5. **Sound.** Once the picture is close to locked.
6. **Check.** It says what it checked and what it could not.
7. **Deliver.** The render, and what changed.

It keeps sessions short: each one starts from `spliced film context <slug>`, a brief of the film, instead of its code, and a new round of notes gets a new session.

## Your own house rules

House rules for your films go in `remotion/docs/HOUSE.md`: brand, type, sound direction, where your product's code is. Your AI reads them before the kit's defaults.

## Your app's real code

The best source for a film's interface is the code behind it. Say where it is in `spliced.json`, as a folder on your machine or a GitHub address:

```json
{ "app": { "code": "~/code/your-app" } }
```

`spliced agents install` then tells your AI to rebuild screens from the components, styles and words that ship there, never from memory or a screenshot. Setup shows it under Make films.
