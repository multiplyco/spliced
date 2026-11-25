---
title: Assets and folders
description: Every still, clip and sound your films use, and a way to sort your work by kind of video or by client.
section: app
order: 6
---

## Assets

Assets lists every still, clip and sound across your films, with what made each one and whether it is used.

The search also looks in free footage libraries. **Add** pulls a clip or photo into a film and writes down its author and licence, so you can see later where it came from.

### Sounds

With a sound picked in Assets:

| Key | What it does |
| --- | --- |
| <kbd>Space</kbd> | Play or pause |
| <kbd>↓</kbd> or <kbd>]</kbd>, <kbd>↑</kbd> or <kbd>[</kbd> | Next sound, previous sound |
| <kbd>←</kbd> and <kbd>→</kbd> | Back and forward five seconds. With <kbd>Shift</kbd>, one |
| <kbd>L</kbd> | Loop the sound, or play through the list |

### Stacks

When a render lands as numbered frames (`f_0001.png`, `f_0002.png` and so on), Assets shows them as one stack: the middle frame, how many there are, and the frames running under your pointer as you move across it. Click a stack to see every frame. Each is still its own file, and the arrow keys step from one to the next.

**Copy the path** gives the frames' path with `#` for the number, to hand to your AI.

## Folders

Sort your work into folders, one per kind of video or one per client. Build, Boards and Assets group by folder, and the filter above them shows one folder or everything. The filter stays the same as you move between the three.

- Make a folder with the **+** beside the folder filter. It is a real folder inside your project.
- Open a film's menu or a board's menu and choose **Move to folder**.
- A new board made while a folder is picked goes into it, and a film started from a board goes where the board is.
- A film's renders go into its folder's `renders/`, so you find them where you expect them.
- Pictures, clips and sounds you put straight into a folder show under it in Assets.

Everything not in a folder is **Shared**. The Library is never sorted: every folder borrows from all of it.

```bash
spliced folders                              # each folder, with its films and boards
spliced folders add branding-videos --name "Branding videos"
spliced film move launch branding-videos     # its renders move with it
spliced board folder "Launch" branding-videos
spliced folders remove branding-videos       # stop sorting into it; nothing is moved or deleted
```

Your AI follows the same folders: opened inside one, it starts its films and boards there.
