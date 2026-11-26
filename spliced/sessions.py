"""What a Claude Code session opened in this project loads, and a lean setting for film work.

  spliced agents context                                   what a session here loads, roughly how heavy, how to slim it
  spliced agents install --lean [--keep <server>]... [--keep-connectors]
  spliced agents install --lean off                        undo: removes exactly what --lean added

Every MCP server a session can reach puts its tool names and instructions into every call, and every call re-reads
the whole conversation, so a film session that also carries a sales, email or hosting toolbox pays for it all along.

What a project can switch off, from Claude Code's docs (code.claude.com/docs/en/settings-reference and /en/mcp):
  disabledMcpjsonServers     names from the project's .mcp.json to reject; a rejection in any settings file applies
  deniedMcpServers           [{"serverName": "..."}]: one denylist merged from every settings file; refused wherever defined
  disableClaudeAiConnectors  true: the folder is opted out of the claude.ai connectors Claude Code fetches itself
                             (all or nothing: one connector can't be kept)
--lean writes them into .claude/settings.local.json, the person's own settings for this folder: they name the person's
own servers, so they are kept out of git (.git/info/exclude) and never go into the shared .claude/settings.json.

~/.claude.json is read only to count and name servers (never a value, never written). Its layout is Claude Code's
own and not all of it is documented: user servers are its top-level "mcpServers", this folder's own are under
"projects" by path, and "claudeAiMcpEverConnected" lists the connectors the account has connected. Standard library only.
"""
import json, os, subprocess

import paths

ROOT = paths.ROOT
SETTINGS = os.path.join(ROOT, ".claude", "settings.json")
LOCAL = os.path.join(ROOT, ".claude", "settings.local.json")
RECORD = os.path.join(paths.CACHE, "agents-lean.json")    # what --lean added, so --lean off removes that and nothing else
OWN = "spliced"


def _home():
    return os.path.expanduser("~")


def _json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else default
    except (OSError, ValueError):
        return default


def _names(d):
    return sorted(d) if isinstance(d, dict) else []


def _tokens(path):
    try:
        return os.path.getsize(path) // 4
    except OSError:
        return None


def _skills(folder):
    return sorted(d for d in os.listdir(folder) if os.path.isfile(os.path.join(folder, d, "SKILL.md"))) if os.path.isdir(folder) else []


def inventory():
    """Names and counts only: the MCP servers a Claude Code session in this folder would load, from where, what is
    switched off, plugins, skills, the instruction files read on every call, and the last session's tokens if recorded."""
    home = _home()
    cj = _json(os.path.join(home, ".claude.json"), {}) or {}
    real, here = os.path.realpath(ROOT), {}
    for key, v in (cj.get("projects") or {}).items():   # kept by the path the session was started from (/tmp or /private/tmp)
        if isinstance(v, dict) and (key == ROOT or os.path.realpath(key) == real):
            here = v
    user_st = _json(os.path.join(home, ".claude", "settings.json"), {}) or {}
    proj_st = _json(SETTINGS, {}) or {}
    local_st = _json(LOCAL, {}) or {}
    files = (user_st, proj_st, local_st)
    rejected = set(n for st in files for n in st.get("disabledMcpjsonServers") or [] if isinstance(n, str))
    rejected |= set(n for n in here.get("disabledMcpjsonServers") or [] if isinstance(n, str))
    denied = set(e.get("serverName") for st in files for e in st.get("deniedMcpServers") or [] if isinstance(e, dict) and e.get("serverName"))
    toggled = set(n for n in here.get("disabledMcpServers") or [] if isinstance(n, str))   # switched off with /mcp
    project = _names((_json(os.path.join(ROOT, ".mcp.json"), {}) or {}).get("mcpServers"))
    local, user = _names(here.get("mcpServers")), _names(cj.get("mcpServers"))
    off = lambda n: n in denied or n in toggled
    connectors_off = any(st.get("disableClaudeAiConnectors") is True for st in files)
    plugins = {}
    for st in files:   # local over project over user
        for k, v in (st.get("enabledPlugins") or {}).items():
            plugins[k] = v
    instr = [(name, path, _tokens(path)) for name, path in (("CLAUDE.md", os.path.join(ROOT, "CLAUDE.md")), ("AGENTS.md", os.path.join(ROOT, "AGENTS.md")),
                                                           ("~/.claude/CLAUDE.md", os.path.join(home, ".claude", "CLAUDE.md"))) if os.path.isfile(path)]
    last = {k: here[k] for k in ("lastTotalInputTokens", "lastTotalCacheReadInputTokens", "lastTotalCacheCreationInputTokens", "lastTotalOutputTokens") if isinstance(here.get(k), (int, float))}
    return {
        "project": [{"name": n, "on": not (n in rejected or off(n))} for n in project],
        "local": [{"name": n, "on": not off(n)} for n in local],
        "user": [{"name": n, "on": not off(n)} for n in user],
        "connectors": {"on": not connectors_off, "known": len(cj.get("claudeAiMcpEverConnected") or [])},
        "plugins": sorted(k for k, v in plugins.items() if v is True),
        "skills": {"project": len(_skills(os.path.join(ROOT, ".claude", "skills"))), "user": len(_skills(os.path.join(home, ".claude", "skills")))},
        "instructions": [{"name": n, "tokens": t} for n, _p, t in instr],
        "last_session": last, "lean": bool(_json(RECORD)),
    }


def summary(inv=None):
    """One line for the doctor: how many other MCP sources a session here carries."""
    inv = inv or inventory()
    others = [s["name"] for k in ("project", "local", "user") for s in inv[k] if s["on"] and s["name"] != OWN]
    conn = inv["connectors"]["on"]
    if not others and not conn:
        return True, "Sessions here load only Spliced's own tools" + (" (lean)" if inv["lean"] else "")
    bits = ([f"{len(others)} other MCP server{'s' if len(others) != 1 else ''}"] if others else []) + (["your claude.ai connectors"] if conn else [])
    return False, "A Claude Code session here also loads " + " and ".join(bits) + ", read again on every call"


def report():
    inv, cli = inventory(), paths.CLI
    out = [f"What a Claude Code session opened in {ROOT} loads (names and counts only; nothing is changed):", "", "MCP servers (each one's tool names and instructions are part of every call):"]
    for key, where in (("project", "this project's .mcp.json"), ("local", "yours, for this folder only (~/.claude.json)"), ("user", "yours, in every folder (~/.claude.json)")):
        rows = inv[key]
        on = [s["name"] for s in rows if s["on"]]
        offs = [s["name"] for s in rows if not s["on"]]
        out.append(f"  {where}: " + (", ".join(on) if on else "none") + (f"   (off here: {', '.join(offs)})" if offs else ""))
    c = inv["connectors"]
    out.append("  claude.ai connectors: " + ("on" + (f", about {c['known']} connected to your account" if c["known"] else ", whatever your claude.ai account connects")
                                             if c["on"] else "off for this folder (disableClaudeAiConnectors)"))
    out.append(f"Plugins enabled: {len(inv['plugins'])}" + (f" ({', '.join(inv['plugins'][:6])}{', ...' if len(inv['plugins']) > 6 else ''})" if inv["plugins"] else "")
               + "; each can bring skills and MCP servers of its own")
    out.append(f"Skills: {inv['skills']['project']} in this project, {inv['skills']['user']} of yours (~/.claude/skills); each one's name and description is listed in every session")
    if inv["instructions"]:
        out.append("Read on every call: " + ", ".join(f"{i['name']} ~{i['tokens']:,} tokens" for i in inv["instructions"]))
    ls = inv["last_session"]
    if ls.get("lastTotalCacheReadInputTokens") is not None:
        out.append(f"The last session here (Claude Code's own record): {ls.get('lastTotalInputTokens', 0):,} input, {ls.get('lastTotalCacheReadInputTokens', 0):,} read from cache, "
                   f"{ls.get('lastTotalCacheCreationInputTokens', 0):,} written to cache")
    out += ["", "To slim it:"]
    lean_ok, _ = summary(inv)
    if not lean_ok:
        out.append(f"  - {cli} agents install --lean: sessions here load only Spliced's own MCP server. Keep a generator you use with --keep <server>,"
                   " and the claude.ai connectors with --keep-connectors (they go all together). It writes .claude/settings.local.json"
                   f" (yours, kept out of git) and never touches ~/.claude.json; {cli} agents install --lean off undoes it.")
    elif inv["lean"]:
        out.append(f"  - Lean is on ({cli} agents install --lean off undoes it).")
    out.append(f"  - Start each round of notes in a new session with {cli} film context <slug>, instead of resuming a long one: a long conversation is"
               " re-read on every call, and after an hour away its whole context is written to the cache again.")
    if len(inv["plugins"]) > 3 or inv["skills"]["user"] > 20:
        out.append("  - Turn off the plugins and skills film work doesn't need, for this folder only, in Claude Code (/plugin, /skills).")
    return "\n".join(out)


# ---------- --lean ----------
def _write(path, st):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2)
        f.write("\n")


def _exclude_from_git():
    """Keep .claude/settings.local.json out of git in this clone only (.git/info/exclude): it names the person's servers."""
    try:
        top = subprocess.run(["git", "-C", ROOT, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
        if top.returncode != 0:
            return False
        if subprocess.run(["git", "-C", ROOT, "check-ignore", "-q", LOCAL], timeout=10).returncode == 0:
            return True   # already ignored
        ex = subprocess.run(["git", "-C", ROOT, "rev-parse", "--git-path", "info/exclude"], capture_output=True, text=True, timeout=10).stdout.strip()
        ex = ex if os.path.isabs(ex) else os.path.join(ROOT, ex)
        line = "/" + os.path.relpath(LOCAL, top.stdout.strip()).replace(os.sep, "/")
        os.makedirs(os.path.dirname(ex), exist_ok=True)
        have = open(ex).read() if os.path.exists(ex) else ""
        with open(ex, "a") as f:
            f.write(("" if not have or have.endswith("\n") else "\n") + line + "\n")
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _unapply(st, rec):
    """Take out of a settings dict exactly what a previous --lean added (rec), and nothing the person put there."""
    names = set(rec.get("denied") or [])
    if "deniedMcpServers" in st:
        st["deniedMcpServers"] = [e for e in st["deniedMcpServers"] if not (isinstance(e, dict) and list(e) == ["serverName"] and e["serverName"] in names)]
        if not st["deniedMcpServers"]:
            del st["deniedMcpServers"]
    gone = set(rec.get("rejected") or [])
    if "disabledMcpjsonServers" in st:
        st["disabledMcpjsonServers"] = [n for n in st["disabledMcpjsonServers"] if n not in gone]
        if not st["disabledMcpjsonServers"]:
            del st["disabledMcpjsonServers"]
    if rec.get("connectors") and st.get("disableClaudeAiConnectors") is True:
        del st["disableClaudeAiConnectors"]
    return st


def lean(keep=(), keep_connectors=False, off=False):
    """Write (or with off, take back) the settings that leave a Claude Code session here with Spliced's own MCP server and
    the ones named in keep. Safe to run twice: what a previous run added is taken out first, then the new set goes in."""
    st = _json(LOCAL, None) if os.path.exists(LOCAL) else {}
    if st is None:
        return [".claude/settings.local.json isn't valid JSON, so nothing was changed; fix or remove it, then run this again"]
    rec = _json(RECORD, {}) or {}
    st = _unapply(st, rec)
    lines = []
    if off:
        if st:
            _write(LOCAL, st)
        elif os.path.exists(LOCAL):
            os.remove(LOCAL)
        if os.path.exists(RECORD):
            os.remove(RECORD)
        return [("lean       off: sessions here load every MCP server and connector again" if rec else "lean       was not on here; nothing to undo")]
    inv = inventory()   # read after the old lean is taken out of the file it reads
    keep = set(keep) | {OWN}
    known = {s["name"] for k in ("project", "local", "user") for s in inv[k]}
    unknown = sorted(set(keep) - known - {OWN})
    if unknown:
        lines.append(f"           not one of your MCP servers: {', '.join(unknown)} (claude.ai connectors go all together: --keep-connectors)")
    have_denied = {e.get("serverName") for e in st.get("deniedMcpServers") or [] if isinstance(e, dict)}
    have_rejected = set(st.get("disabledMcpjsonServers") or [])
    deny = [s["name"] for k in ("local", "user") for s in inv[k] if s["name"] not in keep and s["name"] not in have_denied]
    reject = [s["name"] for s in inv["project"] if s["name"] not in keep and s["name"] not in have_rejected]
    new = {"denied": sorted(set(deny)), "rejected": reject, "connectors": False}
    if deny:
        st["deniedMcpServers"] = (st.get("deniedMcpServers") or []) + [{"serverName": n} for n in new["denied"]]
    if reject:
        st["disabledMcpjsonServers"] = (st.get("disabledMcpjsonServers") or []) + reject
    if not keep_connectors and st.get("disableClaudeAiConnectors") is not True:
        st["disableClaudeAiConnectors"] = True
        new["connectors"] = True
    _write(LOCAL, st)
    _write(RECORD, new)
    excluded = _exclude_from_git()
    kept = sorted(n for n in known if n in keep)
    lines.insert(0, "lean       .claude/settings.local.json: sessions here load " + (", ".join(kept) if kept else "no MCP server")
                 + (" and your claude.ai connectors" if keep_connectors else "") + f"; {len(new['denied']) + len(reject)} other server{'s' if len(new['denied']) + len(reject) != 1 else ''} off"
                 + ("" if keep_connectors else ", claude.ai connectors off") + (" (kept out of git)" if excluded else ""))
    lines.append(f"           a session already open keeps what it loaded: start a new one. Undo: {paths.CLI} agents install --lean off")
    return lines


def main(args):
    if args[:1] == ["context"]:
        print(report())
        return
    raise SystemExit("usage: spliced agents context")
