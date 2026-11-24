# Contributing to Spliced

Thank you for wanting to make Spliced better. This is how to get a change in.

## Before you start

- A bug or a small fix: open a pull request directly.
- Something larger (a new view, a new command, a new provider): open an issue first and say what a person using
  Spliced would get from it. It saves you building something that doesn't fit.
- `AGENTS.md` holds the rules for changing the tool. Read it: most review comments are one of its rules.

## Set up

```bash
git clone https://github.com/multiplyco/spliced && cd spliced
uv tool install --editable .          # the `spliced` command, running your checkout
spliced setup ~/films/try             # a project to try things on
```

You need [uv](https://docs.astral.sh/uv/getting-started/installation/), and Node.js for anything that renders.
macOS and Linux; Windows is not supported yet.

## Check before you send it

```bash
python3 -m unittest discover tests     # state, paths, server, library build, imports, the command line
uv run tests/smoke.py                  # the app in a real browser, on the fixture project and on an empty one
```

A change to the app is looked at in a browser too, not only tested. The tests run on `tests/fixture`, a tiny
project of our own; they never touch a project of yours.

## What a change needs

- **A changelog entry** when someone using Spliced would notice it: at the top of `spliced/web/changelog.md`,
  written for them. Never edit the version number: releases do that.
- **Nothing that belongs to one company or person** in the tool: a brand, a voice, a default path. Those are a
  project's, in its `spliced.json`.
- **Only your own material** in pictures, examples and tests: no frames, names or sound from other people's films.
- **No required service.** A feature that uses a service must leave Spliced fully usable without it.
- **Standard library only** in the command line, the server and the state engine. A pipeline that needs a package
  declares it in its own `# /// script` header.
- **No em dashes** in copy or docs.

## Licence

Spliced is Apache 2.0. By sending a pull request you agree that your contribution is licensed the same way.
