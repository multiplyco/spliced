---
title: Profiles
description: The looks your films are made in. Keep your company's own, try others, and choose one, or none, each time you copy a brief.
section: app
order: 10
---

A profile is a look your films are made in: your company's own, or one you want to try. It holds a palette, typefaces, a motion, a few words in your own voice, the scenes that show the look, and the rules your AI learns while making films in it. Profiles is under **Make** in the sidebar.

## Make one

**New profile** sets one up in a click:

- Drop a brand book, a logo, screenshots or a film on it, and your AI fills it in from them: palette, typefaces, motion, its own words and its rules.
- Start from a film in your library, which brings its palette, type and moves. A reference film's page can start one from its look too.
- Or start blank.

On a profile's page, tell your AI what to change in your own words, and it does. The profile plays itself at the top of its page, in its palette and typefaces, with its motion.

## What a profile holds

| Part | What it is |
| --- | --- |
| Palette | Its colours. Take them from the scenes that show the look in one click |
| Typefaces | One for headlines and one for text, from the ones on your Mac or from Google Fonts, each shown in its own face |
| Motion | A starting motion (one of the built-in ones, or one you saved), then its pace, bounce, stagger and float, the scene changes and the ways words arrive that fit the look, the first leading |
| Its words | The profile in prose: the voice, the stage, the type, what its films always and never do. Your AI reads it before building a film in it |
| Scenes | The scenes from your library that show the look, picked with the closest palettes first |
| Rules | What your AI learned while making films in it, each with where it came from |

A motion's settings each have a small picture of what they do, hovering a style plays it, and **Reset** takes you back. **New** makes a motion of your own that any profile can use.

## Choosing one for a brief

One profile can be the default (the switch at the top of its page): a brief starts in it. A board, a scene's brief and a whole film's brief each have a profile beside the copy button: pick another, or **No profile** to recreate the reference as it is, in its own look.

A project that had one brand and house rules before profiles has them as its first profile.

## From the command line

```bash
spliced profile                                  # the profiles, the default marked
spliced profile show acme                        # what an agent reads before building in it
spliced profile new "Acme" --motion soft --default
spliced profile new "Study" --from-film launch-film   # from a film's look
spliced profile set acme --palette "#0B0B0C ink, #F4F4F1 chalk"
spliced profile motion acme --pace 1.2 --bounce 0 --transition "blur, whip"
spliced profile draft acme brand-book.pdf logo.svg    # your AI fills it in
spliced profile learn acme "never bounce the logo"
spliced profile default none                     # briefs start in no profile
```

A profile is a folder in the project, `profiles/<name>/`: `profile.json`, its words in `PROFILE.md`, and what it was drafted from in `sources/`. Your AI reaches the same through the `profile` tool over [MCP](mcp.md).
