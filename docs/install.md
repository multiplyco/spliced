---
title: Install
description: What Spliced needs on your machine, and the ways to get it.
section: start
order: 2
---

## One line

```bash
npx -y spliced-app setup my-films
```

That makes a project in `my-films`, gives your AI Spliced's skills and tools, installs the film kit, renders the example film and opens the app. It takes about a minute. `setup` is safe to run again: it only does what is still missing.

If you would rather have your AI do it, the home page has [one message to paste](https://spliced.video/#works).

## What you need

| Tool | What it is for | Needed for |
| --- | --- | --- |
| [Node.js](https://nodejs.org/en/download) 18 or newer | Runs the command above, and the render engines | Installing with npm, and making films |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Runs Spliced's tools, and fetches a Python if you have none | Everything |
| `ffmpeg` | Frames and thumbnails | Adding films |
| `yt-dlp` | Adding films from a link | Adding films from a link |
| An AI agent | Reads films, builds boards, makes films | Breakdowns and films |

Spliced runs on macOS and Linux. Windows is not supported yet. No account and no service key is required.

[Setup](setup.md) shows what is ready on your machine and the single step that unlocks the next thing, with the command for your machine. On a Mac without Homebrew, `uv tool install static-ffmpeg` gets `ffmpeg` with no password asked.

## The ways in

### With npm

```bash
npx -y spliced-app <command>      # each time, always the newest
npm install -g spliced-app        # or once, for a spliced command
```

It runs with your Python 3.10 or newer, or has uv fetch one. These pages write commands as `spliced <command>`; run through `npx`, read that as `npx -y spliced-app <command>`.

### Without npm

```bash
uv tool install git+https://github.com/multiplyco/spliced
```

That gives the same `spliced` command.

### The Mac app

Download `Spliced-<version>.dmg` from the [latest release](https://github.com/multiplyco/spliced/releases/latest). The app carries the engine and uv inside it, so no terminal is needed. See [The Mac app](mac-app.md).

### From a checkout

To work on Spliced itself:

```bash
git clone https://github.com/multiplyco/spliced && cd spliced
uv tool install --editable .        # gives you the spliced command; edits to the checkout are live
```

Without installing, `uv run spliced/cli.py <command>` from the checkout is the same thing.

## Check that it works

```bash
spliced --version     # which Spliced this is
spliced doctor        # what is set up on this machine, inside a project
spliced               # with no command: the list of everything it can do
```

## Updates

Once a day, a running Spliced asks the npm registry for the newest version number. The request carries nothing about you or your project. When a newer one is out, the app shows **Update** in the tab strip with the command that gets it, and `spliced doctor` says so.

```bash
spliced update                    # ask now
npm install -g spliced-app@latest # get it, if you installed with npm
spliced setup                     # then, in your project: the newest skills and film kit
```

Run through `npx`, Spliced is the newest each time it starts. To turn the check off, put `"updates": false` in `spliced.json`. A skill file you changed is kept: `setup` and `agents install` leave it alone.
