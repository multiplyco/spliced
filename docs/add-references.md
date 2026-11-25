---
title: Add references
description: Bring films into the library from a link, a file, or a whole folder you already have.
section: app
order: 2
clip: Paste a link
---

A reference is a film you like, added to the library to study and borrow from. Spliced downloads it and runs the machine pass. Reading it is your AI's work.

> Only add films you have the right to download, and keep to the terms of the site they come from. See [Safety and responsibility](responsibility.md).

## From a link

Press **Add reference** in the app and paste a link. Pasting a link anywhere in the app, or into <kbd>⌘K</kbd>, queues it too. From a terminal:

```bash
spliced reference add "<link>"
spliced reference add "<link>" --slug brand-what     # choose its name yourself
spliced reference status                              # every film: analysed? broken down?
```

Links are downloaded with `yt-dlp` into `reference/`, at up to 1080p. A slug is the film's permanent ID once scenes are borrowed from it, so pick a good one. `spliced reference rename <old> <new>` changes it.

## Pictures, GIFs and clips

Drop files anywhere in the app, or paste an image. They become uploaded references, shown in the Library as `uploads/<id>`, and can be favourited, noted and put on boards like any scene.

```bash
spliced uploads add <file-or-image-url> --title "..." --tags "a, b"
spliced uploads list
```

## A folder you already have

In the Add references sheet, **Add a folder** takes a folder's path, looks inside and tells you what is there before anything happens: how many pictures and GIFs, how many videos. Then one button brings it in.

- Pictures and GIFs become uploaded references.
- Videos up to 15 seconds become clips: one moment to borrow.
- Longer videos become films, cut into scenes like a link you paste.

Files are copied into the project, so nothing breaks when the folder moves, and your own folder is left exactly as it was. Each thing comes in once. Spliced tells files apart by what they hold, not by their names, so running it again on the same folder only takes what is new.

```bash
spliced import ~/Movies/references          # look only: what is in there
spliced import ~/Movies/references --go     # bring it in
```

Looking, copying and cutting films into shots happen on your machine and cost nothing. Describing and tagging them is your AI's work, and waits until you ask for it.

## What happens next

Each import is a job in a queue. The Add references sheet lists your recent imports, and **Hide history** puts the finished ones out of sight. A film that is downloaded and analysed waits as "needs your AI". [Imports and breakdowns](imports.md) says how that hand-over works.
