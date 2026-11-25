---
title: Boards
description: A board is one film, written down. The scenes it borrows, in order, each with its words and its length.
section: app
order: 3
clip: Board it
---

A board is your film's script. Each row is a beat: the scene it borrows, the words on screen, the line that is spoken, and how many seconds it lasts. The running time adds them up.

## Start one

Press **New board**, or ask your AI to put one together from a sentence about what the film should say. A board has a brief: what the film announces, who it is for, its aspect and its length, and the motion profile it uses.

## Write the script

- Add scenes from the [Library](library.md) with **+** on a card, or <kbd>B</kbd> while a scene is open.
- Drag a row to reorder.
- Type straight into any field.

Your AI can edit the same board while you watch. With the app open, a change it makes appears at once. The follow button at the bottom of the sidebar goes where your AI points: when it shows you a board or a scene, the app opens it. Click it to stop.

## Hand it over

| Action | What it does |
| --- | --- |
| Copy build prompt | Hands the script to your AI to build |
| Start film | Turns the board into a film in production, which you then follow in [Build](build.md) |
| Copy the board as a plan | The script as Markdown, on the clipboard |
| Download the board as .md | The script as a Markdown file |
| Export all boards and reviews | One file to keep or move, and **Import boards from an export** to bring it back |

All of these are in <kbd>⌘K</kbd>.

## From the command line

Boards are the part of Spliced your AI works on most, so every edit has a command.

```bash
spliced board boards                                   # list boards
spliced board show "Launch"                            # the board as a script
spliced board new "Launch" --profile soft --length 40
spliced board add "Launch" launch-film/s05 --beat hook --copy "On-screen words" --seconds 3
spliced board edit "Launch" 3 --copy "New words" --seconds 2.5
spliced board mv "Launch" 3 1                          # move beat 3 to the top
spliced board rm "Launch" 3
spliced board show-in-app "Launch"                     # point the open app at it
```

If the app is running, changes go through it and appear in every open tab at once. Otherwise they are written to `library/state.json` and show the next time the app loads.
