---
title: Safety and responsibility
description: What Spliced keeps to itself, what it never touches, and what is yours to answer for.
section: reference
order: 4
---

## It runs on your machine

- The app is served from your own machine. Spliced has no account and no cloud of its own.
- The app's server refuses requests from any other website open in your browser.
- It serves only pictures, clips and sounds from your project: never its code, its settings or your keys.

## Your keys

- Service keys live in the project's `.env`, which git ignores.
- Spliced never shows, prints or returns a key's value. The app and `spliced keys` only say whether one is set.
- No agent tool can set or read a key. `spliced keys set` asks the person at the keyboard, and refuses when an agent runs it.
- Your AI is told not to open `.env`, and Claude Code is set to refuse to read it.

## Your AI, fenced in

By default nothing starts on its own. A background session, if you ask for one, may read, edit files in the project and run Spliced's own commands, nothing else. See [Imports and breakdowns](imports.md).

## Your responsibility

Spliced is for studying how films are made, not for copying them. What you download, study and make with it is yours to answer for.

- Only add films you have the right to download, and keep to the terms of the site they come from.
- Do not reuse anyone's footage, music, design or likeness without permission. A breakdown is for learning a move, not for lifting the work.
- Before you publish a film, check that you hold the rights to everything in it.

Spliced is open-source software under the [Apache 2.0 licence](https://github.com/multiplyco/spliced/blob/main/LICENSE), provided as is and without warranty of any kind. You use it at your own risk. Multiply does not condone copyright infringement or the use of anyone's work or likeness without permission and, to the extent the law allows, accepts no liability for how the tool is used.

Making films with Remotion needs a Remotion licence of your own above a certain company size. Spliced does not include Remotion.
