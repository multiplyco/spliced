---
title: The Library
description: Every scene from the films you have added, and the pictures and clips you uploaded. Browse, filter, and borrow.
section: app
order: 1
clip: Find it
---

The Library holds every scene from your reference films, next to the images, GIFs and clips you uploaded. It is where you look for a move and decide what to borrow.

## Browse

- Move the pointer across a card to run through the scene.
- Click a card to open it. It plays just that scene, and says what is on screen, how it moves and how to recreate it.
- Press **+** on a card to borrow it for your board, and the heart to keep it as a favourite.
- <kbd>-</kbd> and <kbd>=</kbd> make the cards smaller and bigger.

The Library makes only the cards near the window, so thousands of scenes open as quickly as a few hundred.

## Filter and sort

**Filter**, or <kbd>F</kbd>, narrows the Library by any tag. Tags come from the project's own fixed list in `library/TAXONOMY.md`, so scenes from different films can be found together: every `mask-reveal`, every `typewriter`.

Sort by **Best first**, **Film order**, **Shortest** or **Longest**. **All**, **Favourites** and **With notes** show everything, only your favourites, or only the scenes you left a note on.

## A scene, open

A scene is written as `film/s05`: the fifth scene of that film.

Under its title is a box for a note of your own: what you would steal from the scene, and what you would change. <kbd>N</kbd> puts the caret in it, and it saves as you type. A scene with a note gets a mark on its card, **With notes** finds it, and the note goes into the brief you copy, so your AI reads your take along with the breakdown.

With a scene open:

| Key | What it does |
| --- | --- |
| <kbd>↓</kbd> or <kbd>]</kbd>, <kbd>↑</kbd> or <kbd>[</kbd> | Next scene, previous scene |
| <kbd>Space</kbd> | Play or pause |
| <kbd>,</kbd> and <kbd>.</kbd> | Back and forward one frame |
| <kbd>←</kbd> and <kbd>→</kbd> | Back and forward one second. With <kbd>Shift</kbd>, a tenth |
| <kbd>F</kbd> | Favourite |
| <kbd>K</kbd> | Save the frame as a moment |
| <kbd>B</kbd> | Add the scene to the current board |
| <kbd>N</kbd> | Write a note on the scene |
| <kbd>C</kbd> | Copy the brief, to paste into your AI |
| <kbd>T</kbd> | Copy the time with the scene's ID |

## Films, Moves, Styles and Moments

The sidebar has more ways into the same library:

| View | What it shows |
| --- | --- |
| Films | Each reference film as a whole: its video, its look and its signature moves |
| Moves | The named pieces of motion the films are known for, with the scenes that show them |
| Systems | The film kit's own moves, each as a scene you can borrow like any other |
| Styles | What the films do, grouped into looks, pace and moves |
| Moments | The exact frames you saved with <kbd>K</kbd> |

## Recreate a whole film

A reference film's page has **Copy build brief**: one prompt for your AI to rebuild the whole film as closely as it can. It holds the whole breakdown, every scene with its timing, what is on screen, how it moves and how to recreate it, and the film's palette, type, tempo and signature moves. It asks for a study, not a restyle: the same scenes in the same order and length, in the film's own look. Your AI starts it as a board of every scene and a film from that board, so [Build](build.md) plays each beat beside the scene it recreates.

## From the command line

```bash
spliced board find "slot reel"                    # search the library
spliced board find "headline" --tag motion=typewriter --film launch
spliced board scene launch-film/s05               # one scene's breakdown
spliced board review launch-film/s05 --fav        # favourite it
spliced board moment launch-film/s12 0:42.51 "the whip"   # save a moment
spliced board new "Study: launch" --from-film launch-film # a board of every scene of one film, in order
```
