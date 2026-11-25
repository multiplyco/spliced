# Spliced's docs

How to use Spliced, one page per file, written for someone who has never edited a film. They are part of the tool:
a change to what Spliced does updates the pages it touches in the same pull request, the way it adds a changelog
entry. spliced.video/docs is this folder rendered, at the release npm serves (the site fetches `docs/` at the tag
`v<version>` when it builds, and builds again when a new version is out), so the docs always describe what
`npm install -g spliced-app` gives you.

## A page

```markdown
---
title: Build
description: One sentence: what the page is for. The site shows it under the title and in search.
section: app
order: 4
clip: Build view
---

The page, in Markdown.
```

- **section** places it in the site's sidebar: `start` (Get started), `app` (The app), `ai` (Your AI), `make`
  (Making films) or `reference`. **order** is its place in that section; no two pages share both.
- **clip** is optional: a beat of the film at the top of spliced.video (its name there, such as `Find it` or
  `Build view`), or `film` for all of it. It never points to a second film.
- `welcome.md` is the page served at /docs.

## Links and pictures

- Link a page by its file: `[Build](build.md)`, `[the notes](build.md#leave-a-note)`. On GitHub that opens the
  file; on the site, the page.
- Pictures go in `images/`, linked as `![what it shows](images/build.jpg)`: the app's own screenshots, taken on the
  fixture project or an empty one, never on a real library (a real library's thumbnails are frames of other people's
  films). A JPEG below 250 KB.
- `readme/` holds the README's pictures, not the docs'.

## What a page says

- Only what Spliced does today: every sentence, command, key and label comes from the tool (the README, a command's
  own `--help`, the app's source). Nothing planned.
- A change that renames, moves or removes something a page mentions (a command, a key, a label, a view) updates that
  page in the same pull request. `tests/test_docs.py` fails when a page names a `spliced` command that doesn't
  exist, or links to a page or picture that isn't here.
- Plain words, short sentences, a film word explained the first time. Keys as `<kbd>N</kbd>`. No em dashes.
