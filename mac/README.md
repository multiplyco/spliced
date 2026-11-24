# Spliced for Mac

A native Mac app around the same Spliced: each project opens in its own window, served by its own copy of the
server that `spliced open` runs. Everything inside the window is the app you know from the browser; the window adds
what a browser can't do.

- **Projects as windows.** A start window lists recent projects, opens one (a folder with a `spliced.json`) or makes
  a new one. Drop a project folder on Spliced in the Dock to open it. Projects open at quit open again at launch.
  The project's name sits at the top of the page's sidebar (`html.in-app`); clicking it opens a native menu of
  projects (`AppDelegate.projectMenu`): a recent one replaces this window, or open or make another in its place, or
  Close Project (⇧⌘W) for the start window.
- **No terminal needed.** The engine (the `spliced` package) and `uv` are inside the app. It runs with the
  person's own Python 3.10+ if there is one, and otherwise has uv fetch one, once.
- **Folders.** "Add a folder…" in Add references is a real folder picker, and a folder dropped anywhere on the window
  opens Add references on it. Files dropped on the window still upload as before.
- **Connect your AI** (Project menu, or Setup in the window): one sheet for `spliced agents install` (agents that
  open the folder: Claude Code, Codex, Cursor) and `spliced connect` for each chat app found on the Mac (the
  Claude desktop app, Cursor, Codex), ticked when already connected. Entries point at the command inside the app.
- **Command line tool** (Spliced menu or Settings): links `~/.local/bin/spliced` to the command inside the app.
- **Imports in the Dock.** The Dock icon counts the imports running in every open project, and a notification says
  when one finishes while you are in another app (click it to go to the project).
- **No title bar.** The page runs to the top edge; the traffic lights sit over the sidebar's top strip, and the
  tab strip's empty space moves the window (the page reports where that is, `DragStrip` in `ProjectWindow.swift`).
  At the start of the tab strip: back, forward (⌘[ ⌘]) and Recently viewed (⌘Y), drawn by the page only in the app
  (`html.in-app`, `SP.native`).
- **Downloads** go to Downloads; links to other sites open in the browser; `prompt()` and file pickers are native.

## How it fits together

| File | What |
| --- | --- |
| `Sources/Spliced/AppDelegate.swift` | Launch, the menu bar, opening and making projects |
| `Sources/Spliced/Server.swift` | One project's server: starts `spliced --project <folder> open --no-open --port <n>`, or uses the one already running (`.cache/server.json`), and stops it with the window |
| `Sources/Spliced/ProjectWindow.swift` | The window: the web view, the bridge the page calls (`SP.native` in `web/core.js`), folder drops, downloads |
| `Sources/Spliced/Engine.swift` | Which `spliced` runs (built in, or the one on this Mac) and the environment it gets (the login shell's PATH: an app opened from the Dock gets a bare one) |
| `Sources/Spliced/Projects.swift` | Recent projects, and each project's port, kept so the page's own memory (welcome seen, theme) survives |
| `Sources/Spliced/StartWindow.swift`, `Settings.swift` | The start window; Settings (engine, reopen, command line tool) |
| `Sources/Spliced/Debug.swift` | Screenshots and JavaScript for checks, only with `SPLICED_DEBUG=1` (`scripts/snap.swift`) |
| `Resources/spliced` | The command inside the app: finds a Python and runs the bundled engine |
| `build.sh` | Builds `build/Spliced.app` (`--dmg` for a disk image, `--universal` for Intel too) |

Each project keeps its own port (8766 and up; 8765 is the terminal's). The server writes `.cache/server.json`, so
`spliced board` and other commands find the window's server, and a `spliced open` in a terminal opens the running
one instead of starting a second.

## Build and run

Needs the Swift toolchain (Xcode or the Command Line Tools, `xcode-select --install`) and `uv`.

```sh
mac/build.sh                         # build/Spliced.app, signed ad hoc for this Mac
open mac/build/Spliced.app
open -a mac/build/Spliced.app ~/films/my-project   # straight into a project
```

The app carries a copy of `spliced/` from the checkout it was built from. To run your checkout's live code instead
(working on Spliced itself), choose "The spliced command on this Mac" in Settings.

For checks and pictures: start it with `open --env SPLICED_DEBUG=1 -a mac/build/Spliced.app`, then
`swift mac/scripts/snap.swift out.png` writes the front window, `--menu "<item>"` runs an item of its menu of projects, and `swift mac/scripts/snap.swift --js "..."` runs
JavaScript in its pages.

## Releases

`scripts/release.py publish` makes the GitHub release (private, like the repo). Running `.github/workflows/release.yml`
by hand (Actions, "mac app for a release", with the tag) then builds the app for both chips (`build.sh --universal --dmg`, with uv for both, downloaded at the version of the uv that built it) and attaches
`Spliced-<version>.dmg` to that release.

**Updates** (`Updates.swift`): checked at launch, every four hours, when the app comes to the front after half an hour
or more, and with Spliced, Check for Updates. A copy installed from a release asks for the latest release of Info.plist's
`SplicedReleases`; Update app downloads its .dmg, puts the new app where this one is and opens it. A copy built from a
checkout (`mac/build/Spliced.app` inside a clone, or a copy of it moved elsewhere, such as Applications: `build.sh`
writes the clone's path into its Info.plist as `SplicedCheckout`, except for a .dmg) asks git whether its branch's
upstream has new commits; Update app pulls them (`--ff-only`), runs `build.sh`, puts the new build where this copy is
and opens it. Either way the project windows come back. The page shows Update app at the end of the tab strip and under
Settings; the log is `~/Library/Logs/Spliced/update.log`. While the release repo is private or has no release, a
release copy says nothing. `SPLICED_RELEASES_URL` points a copy at a stand-in for checks.

**Signing.** Without signing secrets the dmg is signed ad hoc: it runs on the Mac that built it, and elsewhere only
after the person allows it under System Settings, Privacy & Security. To sign and notarise, the company's Apple
Developer account provides a Developer ID Application certificate; add these repository secrets: `MAC_CERT_P12`
(the certificate and key as .p12, base64), `MAC_CERT_PASSWORD`, `MAC_SIGN_IDENTITY` (`Developer ID Application:
<Company> (<TEAMID>)`), and for notarising `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD` (an app-specific
password). Locally the same is `SPLICED_SIGN_IDENTITY=... SPLICED_NOTARY_PROFILE=<profile> mac/build.sh --universal --dmg`.
The signing path is written but has not run yet, since no certificate exists.

## Not done yet

- **Installing updates in place.** The app points at the new release; Sparkle could install it, once the app is signed.
- **ChatGPT.** It connects to tool servers by web address, not to one running on this Mac; Codex is OpenAI's way
  in for now.
