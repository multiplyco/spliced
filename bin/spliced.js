#!/usr/bin/env node
// The `spliced` command from npm (npx spliced-app, or npm install -g spliced-app). Spliced itself is the Python package
// beside this file; this finds a way to run it: the person's own Python 3.10+ if there is one, otherwise uv, which
// fetches a Python once. Spliced's heavier tools need uv anyway, so without either it says how to get uv.
"use strict";
const { spawnSync, spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");

const PKG = path.resolve(__dirname, "..");
const NAME = require(path.join(PKG, "package.json")).name;
const args = process.argv.slice(2);

const env = { ...process.env, PYTHONPATH: PKG + (process.env.PYTHONPATH ? path.delimiter + process.env.PYTHONPATH : "") };
// Run through npx, not installed: npx puts its temporary copy of this file on the PATH as `spliced`, gone after the
// run. Tell Spliced, so what it writes for agents (AGENTS.md, .mcp.json) says "npx -y <name>" instead.
if (process.env.npm_command === "exec") {
  const found = which("spliced");
  if (!found || real(found) === real(__filename)) env.SPLICED_VIA = `npx -y ${NAME}`;
}

function real(p) { try { return fs.realpathSync(p); } catch { return p; } }
function which(cmd) {
  for (const d of (process.env.PATH || "").split(path.delimiter)) {
    const p = path.join(d, cmd);
    try { if (fs.statSync(p).isFile()) return p; } catch { /* not here */ }
  }
  return null;
}
const onPath = (cmd) => !!which(cmd);
function works(py) {
  const r = spawnSync(py, ["-c", "import sys; sys.exit(sys.version_info < (3, 10))"], { stdio: "ignore" });
  return r.status === 0;
}

// a Python of the person's own (not /usr/bin/python3 on a Mac: without developer tools it pops up an installer)
const pythons = [process.env.SPLICED_PYTHON, "python3.13", "python3.12", "python3.11", "python3.10", "/opt/homebrew/bin/python3", "/usr/local/bin/python3",
  process.platform === "darwin" ? null : "python3"].filter(Boolean);
let cmd = null;
for (const py of pythons) if ((py.includes("/") ? fs.existsSync(py) : onPath(py)) && works(py)) { cmd = [py, "-m", "spliced"]; break; }
if (!cmd && onPath("uv")) cmd = ["uv", "run", "--no-project", "--python", ">=3.10", "--", "python", "-m", "spliced"];
if (!cmd) {
  console.error(`Spliced needs uv (it also fetches Python for you). Install it with:

  curl -LsSf https://astral.sh/uv/install.sh | sh

then open a new terminal and run this again. More: https://docs.astral.sh/uv/getting-started/installation/`);
  process.exit(1);
}

const child = spawn(cmd[0], [...cmd.slice(1), ...args], { stdio: "inherit", env });
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) process.on(sig, () => child.kill(sig));   // Ctrl+C reaches the server
child.on("exit", (code, signal) => process.exit(signal ? 1 : code ?? 0));
