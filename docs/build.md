---
title: Build
description: Films in production. Your latest render on one side, the scene each beat borrows from on the other.
section: app
order: 4
clip: Build view
---

Each film in Build started from a board. Open one to see it next to what it borrows from, beat by beat.

## Your film beside its references

On the left is your latest render. On the right is the scene the current beat borrows, playing alongside so you can compare. A render is a video file made from the film as it stands, and each new one gets a version number.

Under the film, the beat bar shows every beat in order. Below it are the film's tabs: Beats, Notes, Script, Sound and Assets.

## Play through, or loop a beat

Build plays the film through, and the beat bar follows the playhead. **Loop beat** (<kbd>L</kbd>) plays the selected beat over and over instead, and <kbd>L</kbd> again goes back to playing through.

You hear the render's own sound. To hear the film's parts one by one, choose **Stems** in the [Sound](sound.md) tab.

## Zoom in on the timeline

A ruler under the beat bar marks the time. Zoom with the magnifying glasses under the bar, with <kbd>=</kbd> and <kbd>-</kbd>, or with a pinch or <kbd>⌘</kbd>-scroll on the bar, which zooms where the pointer is. <kbd>0</kbd> shows the whole film again. Scroll sideways to move along, or drag the thin strip under the ruler, which shows where you are in the film.

The closer you go, the finer the ruler: seconds, half seconds, then single frames with their numbers. While the film plays, the view follows the playhead. The Sound tab's lanes share the same view.

## Leave a note

Pause on a frame and press <kbd>N</kbd> to pin a note right there. Your AI picks the notes up, fixes them and renders again. Feedback you give your AI in the chat lands in the same place.

Notes on the sound (an effect, the music, the voice or the mix) are listed in the Notes tab too, with the frame notes, in film order, each marked SFX, Music, Voice or Mix.

Every note shows when it was added, a reply shows when it came, and a done note shows when it was closed and what changed. **Hide done notes**, at the right under the beat bar, takes the done ones off the bar and leaves the open ones. Nothing is deleted: done notes stay in the Notes tab.

## Statuses

Every beat has a status.

| Status | What it means |
| --- | --- |
| `todo` | Not started |
| `wip` | Being built |
| `review` | Rendered, and waiting for you |
| `changes` | You left notes |
| `approved` | You are happy with it |

Your AI sets the first three as it works. You set `changes` and `approved`.

## Keys in Build

| Key | What it does |
| --- | --- |
| <kbd>↓</kbd> or <kbd>]</kbd>, <kbd>↑</kbd> or <kbd>[</kbd> | Next beat, previous beat |
| <kbd>Space</kbd> | Play or pause |
| <kbd>,</kbd> and <kbd>.</kbd> | Back and forward one frame |
| <kbd>←</kbd> and <kbd>→</kbd> | Back and forward one second. With <kbd>Shift</kbd>, a tenth |
| <kbd>N</kbd> | Pin a note to the frame |
| <kbd>X</kbd> | Compare with another render, and <kbd>V</kbd> swaps the two |
| <kbd>H</kbd> | Show or hide the reference beside the render |
| <kbd>L</kbd> | Loop the beat, or play through |
| <kbd>=</kbd> and <kbd>-</kbd> | Zoom the timeline in and out. <kbd>0</kbd> shows the whole film |
| <kbd>S</kbd> | Time the reference to the beat |
| <kbd>M</kbd> | Sound on or off |
| <kbd>F</kbd> | Full screen |
| <kbd>R</kbd> | Reload the plan and the renders |
| <kbd>T</kbd> | Copy the time with the beat |

Turning the sound on brings the volume knob back up if it was all the way down.

## Folders and workspaces

Build groups films by [folder](assets-and-folders.md), and the filter above shows one folder or everything. A film rendered in a git worktree lands in your main project folder, and Build lists it under **In other workspaces** until its branch is merged. See [Render and review](rendering.md).
