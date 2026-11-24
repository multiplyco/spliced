"""Who does the reading: the agent that writes a film's breakdown or analyses uploads for an import job.

Spliced does no AI work itself. A job's download and machine pass run here; the part that needs judgement is handed
to the person's own agent, in one of these ways (spliced.json "agent": {"runner": ..., "permissions": ...}, or the
SPLICED_RUNNER environment variable):

  none     (the default) Nothing is started. The job waits as "needs your AI" with its prompt; the person's own
           agent session picks it up (`spliced imports next`), does the work and reports it done
           (`spliced imports done <id>`). Nothing runs that the person can't see.
  claude   A headless Claude Code session per job (`claude -p`), streamed into the job's activity.

"permissions" says how much a headless session may do without asking, since nobody is there to ask:
  ask      (the default) It may read, edit files in the project, and run Spliced's own tools; anything else is refused.
  bypass   It may do anything (Claude Code's bypassPermissions). Only for a project you trust the prompts and
           sources of: a film's page or an uploaded file is content from the internet, read by an agent.
"""
import json, os, shutil

import paths

RUNNERS = ("none", "claude")
# what a headless session needs for an import job and nothing more: files in the project, and Spliced's own tools
# (by the installed command, and by this checkout's own, since a prompt names whichever paths.CLI is)
FENCED_COMMANDS = ("library", "uploads", "reference", "analyze", "imports")


def allowed():
    forms = sorted({"spliced", paths.CLI})
    return ["Read", "Glob", "Grep", "Edit", "Write"] + [f"Bash({f} {c}:*)" for f in forms for c in FENCED_COMMANDS]


def _agent():
    a = paths.CONFIG.get("agent")
    return a if isinstance(a, dict) else {}


def name():
    """The runner in force: the environment, then the project, then none."""
    n = str(os.environ.get("SPLICED_RUNNER") or _agent().get("runner") or "none").strip().lower()
    return n if n in RUNNERS else "none"


def called():
    """What the app calls the person's AI: the project's own name for it (spliced.json "agent": {"name": ...}), "Claude"
    when it has Claude read its imports, and nothing otherwise (the app then says "your AI")."""
    n = str(_agent().get("name") or "").strip()
    return n or ("Claude" if name() == "claude" else "")


def bypass():
    return str(os.environ.get("SPLICED_PERMISSIONS") or _agent().get("permissions") or "ask").strip().lower() == "bypass"


def available(n=None):
    """Whether the runner's program is installed (none always is)."""
    n = n or name()
    return True if n == "none" else bool(shutil.which(n))


def argv(prompt):
    """The command that starts the runner on a prompt, or None when there is nothing to start (none)."""
    if name() != "claude":
        return None
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose"]
    if bypass():
        return cmd + ["--permission-mode", "bypassPermissions"]
    return cmd + ["--permission-mode", "acceptEdits", "--allowedTools", ",".join(allowed())]


def activity_of(c):
    """One line for what a Claude Code tool call is doing, for the job's activity."""
    tool, inp = c.get("name", ""), c.get("input", {}) or {}
    if tool == "Read":
        f = os.path.basename(str(inp.get("file_path", "")))
        return f"Looking at {f}" if f.endswith((".jpg", ".png")) else f"Reading {f}"
    if tool in ("Write", "Edit"):
        return f"Writing {os.path.basename(str(inp.get('file_path', '')))}"
    if tool == "Bash":
        return "Running " + (inp.get("description") or str(inp.get("command", ""))[:80])
    if tool == "Agent":
        return "Starting a breakdown agent"
    return tool


def read(line):
    """One line of the runner's output -> a list of events: ("text", str), ("tool", log line, activity),
    ("final", str, cost), or ("raw", line) for anything that isn't the runner's own format."""
    try:
        ev = json.loads(line)
    except ValueError:
        return [("raw", line)] if line.strip() else []
    out = []
    if ev.get("type") == "assistant":
        for c in ev.get("message", {}).get("content", []):
            if c.get("type") == "text" and c.get("text", "").strip():
                out.append(("text", c["text"].strip()))
            elif c.get("type") == "tool_use":
                out.append(("tool", f"{c.get('name')}: {json.dumps(c.get('input', {}), ensure_ascii=False)[:200]}", activity_of(c)))
    elif ev.get("type") == "result":
        out.append(("final", ev.get("result") or "", ev.get("total_cost_usd")))
    return out
