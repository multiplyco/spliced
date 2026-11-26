---
title: Render and review
description: The loop of a film in production. Start from a board, render, leave notes, and render again.
section: make
order: 2
---

A film in production has a storyboard: one beat per board item, each with its window in film time, the scenes it borrows, a status and your notes. Every render is cut up beat by beat and laid next to that plan in [Build](build.md).

## Start a film

Press **Start film** on a board, or:

```bash
spliced film new launch --board "Launch"
spliced film list
spliced film status launch        # beat by beat: window, status, references, open notes
spliced film context launch       # a short brief for a new AI session: plan, open notes by beat, cues, file map
```

`film context` is what your AI reads first when it picks a film up in a new conversation, instead of the film's
code: about 3,000 tokens with the plan, the open notes under their beats with their ids, each beat's cues, the
latest render and whether the code changed since, every file in the film's folder with what it holds and exports,
the assets and sound in a line or two, and the commands to render a beat and close notes.

## Render

```bash
spliced film render launch                      # the whole film
spliced film render launch --beat hook          # one beat
spliced film render launch --beat 1..2          # a run of beats
spliced film render launch --scale 0.5          # smaller and quicker
```

A render takes minutes, so it can be started and then asked about:

```bash
spliced film render launch --background
spliced film render-status launch
```

Each render gets a version number, so you can compare one with another in Build.

## Notes, and closing them

You pin a note to a frame in Build with <kbd>N</kbd>. Your AI works through them:

```bash
spliced film notes launch                                # the pinned notes, open first
spliced film note launch 0:18.66 "Hold the word longer"  # file feedback from the chat on its frame
spliced film note-reply launch <id> "Copy changed, voice pending"
spliced film done launch <id> --done "Held two frames longer"
spliced film render launch --fixes <id>,<id> --note "..."   # render, and close the notes it fixes
```

A closed note records what changed and the render that has the fix.

## See a render against its plan

```bash
spliced film sheet launch              # storyboard, reference frames and render frames, as one picture
spliced film sheet launch --beat hook  # one beat, larger
spliced film assets launch             # every still and clip, and where it is used
```

The sheet is how an agent that cannot watch video checks its own work.

## Git worktrees

A film rendered in a git worktree lands in your main project folder, where Spliced shows it. Opened on your main project, Build lists the film under **In other workspaces**, with the workspace's name and branch, until the branch is merged.

To keep renders with the branch instead, so they travel with it when you commit them:

```json
{ "worktree_renders": "worktree" }
```

## Other render engines

Build also reads HyperFrames films, kept in `videos/<slug>/`. Their storyboard is `STORYBOARD.md` and their renders go to `videos/<slug>/renders/`.
