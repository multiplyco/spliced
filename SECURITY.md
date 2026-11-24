# Security

Spliced runs on your own machine: a local server that answers only its own page, pipelines that read media you
give it, and an MCP server your AI starts. This is what it promises, and how to tell us when it doesn't hold.

## What Spliced promises

- **The server answers only its own page.** It listens on `127.0.0.1`, and every request must come from its own
  address with its own origin (`Handler._guard()` in `spliced/toolbox.py`). Another site open in your browser can
  read nothing and change nothing.
- **Only media is served from a project.** Pictures, clips and sound, never source files, JSON, `.env` or anything
  under a dot folder (`paths.media`).
- **Keys never pass through an agent.** Service keys live in the project's `.env`. No MCP tool sets or reads one, no
  endpoint or command prints a value, and `spliced agents install` tells Claude Code and Gemini CLI not to open the
  file.
- **A background agent is fenced in** unless the project asks otherwise (`"permissions": "bypass"` in `spliced.json`).
  A film's page is content from the internet, read by an agent: choose `bypass` knowingly.
- **It goes online for itself only to ask for the newest version number**, once a day, and that can be turned off
  (see Updates in the README). Everything else it fetches is something you asked for: a film from a link, footage
  from a library you searched, packages for the film kit.

## What it does not protect against

- Other programs running as you on the same machine. They can read the project folder as you can.
- What a film, a web page or a downloaded file tells your AI to do. Spliced fences its own background runs; an
  agent you start yourself has the permissions you gave it.
- The tools it runs for you (`yt-dlp`, `ffmpeg`, Node packages, `static-ffmpeg` if you chose it). Keep them current.

## Reporting a problem

Please do not open a public issue for something that could put people's machines or keys at risk. Use GitHub's
private reporting instead: the repository's Security tab, "Report a vulnerability". Say what you did, what happened,
and which version (`spliced --version`).

Only the latest release gets security fixes while Spliced is below 1.0.
