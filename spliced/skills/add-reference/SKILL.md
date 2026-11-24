---
name: add-reference
description: Add reference videos to the motion library and break them down scene by scene. Use when the user gives video links or files they like ("add these references", "analyze this video", "break down this launch film"), or asks to analyse, catalogue or extend the library of styles. Downloads, runs the machine pass, dispatches breakdown agents, validates, merges new tags, and updates STYLES.md.
---

# Add references to the library

Turns reference videos into tagged, recreatable scenes in `library/`. Background: `library/README.md`.
The method agents follow: `HOW-TO-BREAK-DOWN.md`. Their brief: `BREAKDOWN-AGENT.md`. Both are next to this file.

Spliced runs this skill too: links pasted into its "Add reference" become import jobs. Spliced does step 1
itself; steps 2 to 6 are an agent's work. Check first whether one is waiting for you: `spliced imports next`
prints the job and what to do, and `spliced imports done <id>` hands it back when you have finished. (A project
can instead have a headless session do that part in the background: `agent` in its `spliced.json`.) To queue
links from the chat instead of doing them here: `spliced imports add <url>...`; `list` shows progress.

A whole folder the person already has (pictures, GIFs, clips, films): `spliced import <folder>` says what is in it
and how much there is to read; tell them, then `spliced import <folder> --go` once they agree. Its pictures and
short clips become uploads to read (`spliced uploads pending`), its longer videos one import job each
(`spliced imports next`). Anything already in the library is skipped, so it is safe to run again.

Input: one or more URLs (YouTube, X, Vimeo, LinkedIn...) or local video files. If the user gives nothing,
run `spliced reference status` and offer to break down any film without a breakdown.

## 1. Download, register, machine pass

For each source, pick a slug: kebab-case `brand-what`, for example `acme-launch-2025` or `globex-how-it-works`.
Slugs become permanent scene IDs, so make them readable. If the brand isn't knowable from the URL or filename,
use `ref-<short-id>` and rename it in step 4.

```bash
spliced reference add "<url-or-file>" --slug <slug>
```

This downloads into `reference/`, appends `library/references.tsv`, and writes `analysis.json` and the contact
sheets. Already-registered sources are skipped, not duplicated. Run several sources one after another; each
takes ~15–60s.

If a download fails (private, age-gated or login-only), tell the user and ask before trying browser cookies
(`yt-dlp --cookies-from-browser chrome`).

## 2. Dispatch breakdown agents

Don't write the breakdowns in the main conversation: each film means reading many images.

1. Group the films so each agent gets ~150–200s of total running time (usually 2–4 films; one long film
   can be alone). Durations: `spliced reference status`.
2. Start one background agent per group, all in one message so they run in parallel. Each prompt starts
   with `Project: <absolute path of the project>. Work only from that directory.`, then the full text of
   `BREAKDOWN-AGENT.md` below its `---` line, then:
   ```
   ## Your films
   - `<slug>` (<duration>s, "<title>", <brand or "unknown: identify it from the screen">). Notes: <anything
     useful from analysis.json, e.g. "68 detected shots, group them" or "only 2 hard cuts, mostly continuous">
   ```
3. While they run, tell the user what's happening and roughly how long it takes: 10–15 minutes per agent.

## 3. Validate and build

When every agent has reported:

```bash
spliced library
```

This validates every film, renders strips, writes each `breakdown.md`, `INDEX.md` and the toolbox data
(`.cache/library.json`, which the server hands to the app), and checks every scene reference in `STYLES.md` and `README.md`. Fix any failure (bad tag, gap between scenes) directly in the
`breakdown.json`, or resume the agent that wrote it.

## 4. Rename identified films

If an agent identified the brand of a placeholder slug:

```bash
spliced reference rename ref-abc123 brand-what
```

## 5. Merge proposed tags

Agents propose tags they missed. For each proposal:
- **Add it** if it names a distinct technique that recurs or is likely to recur. Write a one-line definition in
  the right section of `library/TAXONOMY.md` (follow the existing table or list format), then add the tag to
  the scenes the agent named in their `breakdown.json`. Search the other films' prose for the same technique
  and tag those scenes too.
- **Skip it** if an existing tag covers it closely enough.

Rebuild after (`spliced library`).

## 6. Update STYLES.md

```bash
spliced library --moves <slug> <slug>...
```

This prints each new film's structure, signature moves and ★★★ scenes. Fold them into `library/STYLES.md`:
- a move that matches an existing row: add the new scene as another example in that row;
- a new move worth reusing: add a row to the right table (type, product/UI, transition, ending);
- a new overall look or story structure: add an entry in §1 or §6;
- the pace table in §7: add the film to its tier.

Keep the existing format: scene links as `[film/sNN](references/<film>/breakdown.md#sNN)`, numbers kept, no
em dashes. Then run `spliced library --links` and fix anything it reports.

## 7. Report to the user

Keep it short:
- the films added, with scene counts and any brands identified;
- the standout signature moves, each with a scene ID;
- what changed in `STYLES.md` and `TAXONOMY.md`;
- anything uncertain (inferred audio, unresolved copy).

Embed one or two scene strips (`library/references/<slug>/scenes/sNN.jpg`) as images, and remind them the new
films are in the app (`spliced open`). Don't commit unless
the user asks.
