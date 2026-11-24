# AGENTS.md: working on Spliced

Spliced is a tool that works on a project. Keep the two apart in everything you write.

- **The tool** is this repo: the package in `spliced/` (the command line, the server, the pipelines, the web app
  in `spliced/web/`, the skills in `spliced/skills/`), the tests, and nothing that belongs to one company or person.
- **A project** is a folder with a `spliced.json`: someone's library, boards and films. The tool never assumes
  one exists beside it, and never keeps a user's data in its own folders.

| Path | What |
| --- | --- |
| `spliced/cli.py` | The `spliced` command: lists and dispatches to the tools; `setup` (everything in one go), `init`, `agents install` |
| `spliced/updates.py` | Whether a newer Spliced is out (`spliced update`, `/api/update`, the doctor's first lines), and how this copy is updated |
| `spliced/doctor.py` | What this machine and project can do, and the next step. Also `/api/doctor`, which the app's Setup view (`web/setup.js`) shows |
| `spliced/connect.py` | `spliced connect`: this project's MCP entry in a chat app's own settings (Claude desktop app, Cursor, Codex) |
| `spliced/mcp_server.py` | The tools offered to an agent over MCP. Each one is a `spliced` command run as its own process |
| `spliced/projects.py` | The projects this person has opened (kept with their settings, `~/.config/spliced/`): `spliced projects`, and the browser sidebar's menu of projects (`/api/projects`) |
| `spliced/locate.py`, `paths.py` | Which folder is the project, and where everything in it is. The only place that knows |
| `spliced/toolbox.py` | The server: `/app/` (the web app), `/project/<path>` (media only), `/api/` |
| `spliced/toolbox_state.py`, `board.py` | Boards, reviews, moments: named operations on `library/state.json` |
| `spliced/film.py`, `sound.py`, `soundkit.py`, `voice.py` | Films in production |
| `spliced/folders.py`, `web/folders.js` | The project's folders (spliced.json "folders"): films, boards and assets sorted by kind of video or by client. Build, Boards and Assets group and filter by them; the Library never |
| `spliced/add_reference.py`, `analyze_reference.py`, `build_library.py`, `importer.py`, `runners.py`, `uploads.py`, `stock.py` | The library and what feeds it |
| `spliced/web/` | The app: plain HTML, CSS and JavaScript, no build step |
| `spliced/web/welcome.js` | The first-run welcome (three steps; plays `web/intro.mp4` when the app ships one) |
| `spliced/skills/`, `skillset.py` | What an agent follows; `spliced agents install` copies them into a project. `skillset.py` remembers what it put there, so a file the person changed is kept |
| `spliced/templates/project/` | What `spliced init` writes |
| `spliced/kit.py`, `spliced/kit/` | The film kit: `managed/` is copied into a project's `remotion/` and replaced on `spliced kit update` (the motion library, specimens, CRAFT/MOTION-SYSTEMS/SOUND docs, UI sounds); `project/` is written once if missing (package.json, Root.tsx, `src/profiles.ts`) and is the project's from then on |
| `starter/films/` | Example films `spliced kit starter` adds to a project (outside the package: a checkout, the npm package and the Mac app carry it). Each has a `starter.json` |
| `package.json`, `bin/spliced.js` | The npm package `spliced-app`: the `spliced/` package plus a Node launcher that finds a Python (or uv) and runs it. Under npx it sets `SPLICED_VIA`, so what Spliced writes for agents names `npx -y spliced-app` |
| `mac/` | The Mac app: a native window per project around the same server and page (`mac/README.md`). Swift, built by `mac/build.sh` |
| `tests/` | Unit tests, `smoke.py` (a real browser), and `fixture/`, the tiny project they run on. `perf.py` measures the app on a synthetic library of 600 and 5,000 scenes |
| `scripts/readme_shots.py`, `docs/readme/` | The README's pictures of the app, taken on a made-up project (the example film's made-up Acme film), never a real library |

## Rules

- **Paths come from `paths.py`.** No tool works out a root from its own file. A project-relative path is turned
  into a real one with `paths.resolve` (stays inside the project) or `paths.media` (also: a media file, no dot name).
- **In the web app**, a file URL is `SP.fileUrl(path)` and a command the person or their AI would type is
  `SP.cmd("film", "status", slug)` (`spliced/web/core.js`). Never build either by hand.
- **Nothing company-specific in the tool.** A brand, a motion profile, a voice, a default: those are the
  project's, in `spliced.json`. `tests/test_guard.py` fails if one creeps in (see "Nothing in the repo is one company's").
- **The server only answers its own page.** Every request passes `Handler._guard()`; a new endpoint needs no
  extra work, and must not weaken it. Only media is served from a project, never source, JSON or keys.
- **The app explains itself.** Every control has a `title` (it is shown by the app's own tooltip, `web/tips.js`; the
  browser test fails a control with no label). A film word in the app's copy is written `SP.term("beat")`, so its
  meaning is one hover away; a new word goes into the glossary in `tips.js`, in plain terms. The app calls the
  person's AI `SP.ai`, never a product's name.
- **A change someone using Spliced would notice gets an entry in `spliced/web/changelog.md`**, at the top, written
  for them: a title, the date, one line in italics, a paragraph, a picture if it helps (under `web/changelog/`, a
  JPEG below 250 KB, taken on the fixture project or an empty one, never on a real library: a real library's
  thumbnails are frames of other people's films). The app shows it under Settings, What's new. Never edit the version by hand.
- **A release is cut when the owner says "release"**, with `scripts/release.py`: `prepare minor` (something a user would
  notice) or `prepare patch` (fixes only) writes the number and marks the changelog; that goes through a pull request
  like any change; after the merge, `publish` tags it and makes the GitHub release. Below 1.0 until the repo is public.
- **A folder import copies, and takes each thing once** (`spliced/folder.py`). Files come into the project (uploads and
  `reference/`), never served from where they were; what is already in the library is told by what a file holds
  (`fingerprint`), not its name. Looking is cheap and queues nothing; only `--go` (or the app's button) brings anything in.
- **The Library is windowed.** Only cards near the window exist; every other scene is a `.card-ph` in its place with the
  same `data-key` (`libWindow` in `web/app.js`). Code that looks for a scene's card must expect the place instead, and
  must not assume every card is in the page. `uv run tests/perf.py` measures it at 600 and 5,000 scenes; run it
  before and after a change to how the Library draws.
- **Stacks.** Images in one folder whose names differ only by a number (three or more) are a stack
  (`film.stack_assets`). The asset lists still carry every frame, marked with `stack` and `frame`, so an agent reaches
  each one; only the app folds them into one card. Don't drop frames from an API to make a list shorter.
- **A new main view gets an explainer**: an entry in `VIEWS` in `web/explain.js` (a title and two or three lines, for
  someone who has never edited a film). Views don't call it; it places itself under the view's heading. A loop can
  sit beside the words when `web/explainers/<key>.mp4` exists.
- **The introduction film ships with the app**: `spliced/web/intro.mp4`, with `intro.jpg` as its first frame. The welcome
  plays it beside the three steps. It is the example film (`starter/films/splice-explainer`) rendered and scaled to
  1280 wide, near 2 MB. It shows only what is made up or ours: the app rebuilt in code, the frames of a film that
  doesn't exist (`demo_frames.py` draws them), and the kit's own moves. No frame of a real film, no real company.
  A change to the example film means a new cut of this file.
- **Nothing in the repo is one company's.** No brand, product word, person, private path or link into someone's
  account, in the tool, the kit, the example film, the tests or the docs; examples use made-up names (Acme, Globex).
  The names it must not hold are hashes in `tests/support.py` (`named`), and `tests/test_guard.py` checks every
  tracked file. The publisher is named only in the files that test lists (copyright, the repository's address, the
  Mac app's identifier).
- **The Mac app is a window, not a second app.** Everything a person does happens in `spliced/web/`, the same in the
  browser and the app. The app only adds what a browser can't (a folder picker, folders dropped on the window, Finder,
  downloads); the page reaches it through `SP.native` (null in a browser), and every such control has a browser
  fallback. Logic stays in the engine: when the app needs something new, it runs a `spliced` command.
- **A render made in a git worktree goes home.** A Conductor workspace is a worktree: `spliced film render` there writes
  to the main checkout (`paths.render_home`), and a file there is written down as `@main/<path>` (`paths.rel`), served
  by the same media rule as the project's own. The main checkout lists the worktrees' films (`film.workspace_films`).
  spliced.json `"worktree_renders": "worktree"` keeps renders with the branch instead.
- **A running server says where it is** in the project's `.cache/server.json` (port, pid). Anything that talks to a
  running app (`board.py`) reads it; never assume port 8765. With no `--port`, a project takes the port it had last
  (`.cache/port`) or the next free one, so two projects open side by side. A port that is taken is said in a
  sentence, never a traceback. `spliced open --background` is how an agent opens the app: it returns once the app
  answers.
- **`spliced setup` is the front door, and safe to run twice.** It is what the README's setup message runs and what
  brings a project up to date after an update. Each step does only what is missing; a new step must do the same, and
  must never turn a folder that holds someone's files into a project.
- **No service is required.** A film can be made with no key and no connector: voice, music and generated footage
  are extras, each from any provider (a service Spliced calls, one the person's AI is connected to, or a file the
  person brings). The doctor, the skills and the kit's docs must not read as if one service were needed, and a new
  provider is a recipe in the kit's docs plus, at most, a key in `apikeys.py`.
- **Spliced goes online for itself once a day, and says so**, and only while it is published (`updates.PUBLISHED`,
  held to package.json's `private` by `tests/test_guard.py`): a package name that isn't ours is never asked about and
  never offered to a person to install. One request for the newest version number
  (`updates.py`), nothing about the person or the project, switched off by `"updates": false` in spliced.json or
  `SPLICED_NO_UPDATE_CHECK`. The doctor only reports what that learned. Anything else that would phone home needs the
  same: said in the README, and a switch.
- **A person's change to a skill is theirs.** `skillset.py` records what each skill file held when Spliced put it in
  a project (`.claude/skills/.spliced.json`). A file unchanged since then is replaced by a newer version; one changed
  by hand is left and named, unless `--force`, and then the old one is kept in `.cache/skills-kept/`. Never copy a
  skill into a project any other way.
- **What a browser can't do, the server does, and the tests never see it.** The system's folder picker
  (`/api/pick-folder`), a new project from the page (`/api/projects/new`), Connect your AI (`/api/connect`): each is
  the Mac app's extra offered to a browser, and each runs a `spliced` command or a system dialog on this machine. A
  test that could reach the picker sets `SPLICED_PICKER` to a stand-in, so no dialog opens on anyone's screen.
- **A missing program gets a command that works here.** The doctor's fix for a tool is the command for this machine
  (Homebrew when it is there; for ffmpeg otherwise `uv tool install static-ffmpeg`, which `paths.py` links in as
  `ffmpeg` and `ffprobe`). A hint that names a Spliced command writes it `paths.CLI`, never a bare `spliced`.
- **The film kit is the source of the motion library.** Change motion, specimens, the craft or sound docs in
  `spliced/kit/managed/`, never in a project's copy: `spliced kit update` brings it there. A company's own profile
  belongs in that project's `remotion/src/profiles.ts`, not in the kit. An example film in `starter/` shows only what
  is ours (no frames of other people's films, no citations of their films, no review history): `tests/test_kit.py`
  checks it.
- **Keys never pass through an agent.** Service keys live in the project's `.env`, written by `apikeys.py` (Settings,
  Service keys, or `spliced keys set` at a person's keyboard). No MCP tool sets or reads one, no endpoint or command
  output carries a value back, and `agents install` fences `.env` off from Claude Code. `spliced keys` is the one
  command with no MCP tool, on purpose.
- **A new command for agents gets an MCP tool too**, as a thin wrapper in `mcp_server.py` that runs the command.
  No logic lives only in the server, and nothing but protocol messages may reach its stdout.
- **An agent is the user's.** Spliced starts one only when the project asks (`runners.py`), fenced in unless
  the project asks otherwise.
- **Heavy packages stay out of the core.** `cli.py`, the server and the state engine are standard library only.
  A pipeline that needs numpy, librosa or the like declares it in its own `# /// script` header and is run with `uv run`.
- **Check before you say it works:** `python3 -m unittest discover tests` and `uv run tests/smoke.py`. A change
  to the app is looked at in a browser, not only tested.
- No em dashes in any copy or docs.

## The Spliced brand (the app)

`spliced/web/splice-tokens.css` and `spliced/web/brand/`. Dark by default; volt (`#DFFF1A`) only for the primary
button, selection, playhead and focus, and never as text or a line on light; one font, Inter, with hierarchy from
size, weight and colour (timecodes in tabular figures); use the outlined logo files, never retype the wordmark
(`scripts/brand_wordmark.py` cuts it from the typeface).

## Studio hardware

The tactile controls in Build's transport bar (keys, the loop slide switch, the speed and volume knobs) are a
kit of their own: `spliced/web/hardware.css` and `hardware.js` (`HW.knob`, `HW.slide`), with their own `hw-*`
classes so the shared `.icon-btn` and `.seg` stay flat. One light from the top, depth from tone, grit that
follows Settings' grain switch; a lit pip or stop is the only volt and counts as selection. Every control and
state is on the specimen sheet, `/app/hardware.html` (`?both` for dark and light, `?selftest` to drive them).
The controls have their own sounds (`HW.sound`, synthesised in code, no files): off by default, turned on in
Settings (Control sounds, `cr.uiSound`) or with ⌘K, played when a control is operated by hand, on screen or with
its keyboard shortcut (app.js `hwKey`), and never while a film plays with its sound on.
