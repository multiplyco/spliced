/* Setup (#/setup): what Spliced can do on this machine and in this project, level by level, and the one step that
   unlocks each next thing. The answer is the server's (/api/doctor, the same as `spliced doctor`); this only shows it.
   Nothing here is required to browse: every level adds something, and the person chooses how far to go. */
/* Service keys (ElevenLabs, the footage libraries): pasted here, saved by the server into the project's .env, and
   never shown again. The page only learns whether a key is set (/api/keys); the value goes one way. */
window.ApiKeys = (() => {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const list = () => fetch("/api/keys", { cache: "no-store" }).then((r) => r.json()).then((j) => j.keys);
  async function post(body) {
    const r = await fetch("/api/keys", { method: "POST", body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Couldn't save it");
    return j;
  }
  /** The controls for one key: Add key, or Set with Replace and Remove; pasting opens in place. done() after a change. */
  function control(k, done) {
    const box = h(`<div class="key-ctl"></div>`);
    const idle = () => {
      box.innerHTML = k.set
        ? `<span class="set-ok">${window.icon("check")}Set</span><button class="icon-btn ghost sm" data-a="edit" title="Paste a new ${esc(k.name)} key in place of this one">Replace</button><button class="icon-btn ghost sm" data-a="rm" title="Take the ${esc(k.name)} key out of this project's .env">Remove</button>`
        : `<button class="icon-btn sm" data-a="edit" title="Paste your ${esc(k.name)} key: it is saved in this project's .env and never shown again">Add key</button>`;
      box.querySelector('[data-a="edit"]').onclick = edit;
      const rm = box.querySelector('[data-a="rm"]');
      if (rm) rm.onclick = async () => {
        if (!confirm(`Take the ${k.name} key out of this project?`)) return;
        try { await post({ id: k.id, remove: true }); k.set = false; window.crToast?.(`${k.name} key removed`); idle(); done?.(); } catch (e) { window.crToast?.(e.message); }
      };
    };
    const edit = () => {
      box.innerHTML = `<input class="key-in" type="password" autocomplete="off" spellcheck="false" placeholder="Paste your ${esc(k.name)} key" aria-label="${esc(k.name)} key">
        <button class="icon-btn sm primary" data-a="save" title="Save it in this project's .env">Save</button><button class="icon-btn ghost sm" data-a="cancel" title="Keep things as they are">Cancel</button>
        <a class="key-get" href="${esc(k.url)}" target="_blank" rel="noopener" title="Where ${esc(k.name)} gives you a key">Get a key</a>`;
      const input = box.querySelector("input");
      const save = async () => {
        const v = input.value.trim(); if (!v) { input.focus(); return; }
        input.value = "";   // the value leaves the page with the request and isn't kept anywhere here
        try { await post({ id: k.id, value: v }); k.set = true; window.crToast?.(`${k.name} key saved`); idle(); done?.(); }
        catch (e) { window.crToast?.(e.message); input.focus(); }
      };
      box.querySelector('[data-a="save"]').onclick = save;
      box.querySelector('[data-a="cancel"]').onclick = idle;
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); save(); } else if (e.key === "Escape") { e.preventDefault(); idle(); } });
      input.focus();
    };
    idle();
    return box;
  }
  return { list, control };
})();

window.SetupView = (() => {
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const icon = (n) => window.icon(n);
const copy = (text, said) => navigator.clipboard?.writeText(text).then(() => window.crToast?.(said));

// What to say to your own AI: it does the installing, one step at a time, in the open.
const PROMPT = () => `Set up Spliced for me on this machine. Run \`${SP.cmd("doctor")}\` and fix what it marks ✗, one at a time, telling me what each step installs before you run it. Leave the lines marked · alone unless I ask for them. Finish by running \`${SP.cmd("doctor")}\` again and showing me the result.`;
// Services an agent can be connected to. Spliced can't see them: it says what each adds, the agent says what it has.
const CONNECT = [
  ["GitHub", "Your app's real code: the components, styles and copy that ship, so the screens in your film are the real ones"],
  ["An image or video generator", "Generated clips and stills, where real footage can't give you the shot (Higgsfield, or any other)"],
  ["A voice or music service", "Voices, music beds and sound effects (ElevenLabs, or any other that hands back an audio file)"],
  ["Figma", "Your designs, for what the code doesn't show yet"],
];
const STATE = { ok: ["check", "Ready"], missing: ["x", "Missing"], off: ["circle", "Not added"] };
const rich = (s) => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>");   // `spliced voice` in the doctor's words reads as code here
// a fix that is a command gets a copy button: Spliced's own command however it is installed here (spliced, npx …), or a known tool's
const isCommand = (fix) => fix.startsWith(SP.cmd() + " ") || /^(spliced|npx|uv|brew|cd|npm|git|codex|claude) /.test(fix);

function fixLine(i) {
  if (i.state === "ok" || !i.fix) return "";
  if (/^https?:\/\//.test(i.fix)) return `<div class="su-fix"><a href="${esc(i.fix)}" target="_blank" rel="noopener">${esc(i.fix.replace(/^https?:\/\//, ""))}</a></div>`;
  if (isCommand(i.fix)) return `<div class="su-fix"><code>${esc(i.fix)}</code><button class="icon-btn ghost sm sq" data-copy="${esc(i.fix)}" title="Copy the command">${icon("copy")}</button></div>`;
  return `<div class="su-fix"><span>${rich(i.fix)}</span></div>`;
}

/* Connect your AI, in a browser: the same choices as the Mac app's sheet. The agents that open this folder get
   Spliced's skills and tools (`agents install`); each chat app found on this machine is ticked when this project is
   in its tools (`connect <app>`), and unticking takes it out. The server runs the commands (/api/connect). */
let csheet = null;
async function connectSheet(done) {
  if (csheet) return;
  const st = await fetch("/api/connect", { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (!st) return window.crToast?.("Couldn't ask what is connected: the server didn't answer");
  const row = (id, name, detail, on) => `<label class="set-row cn-row" title="${esc(detail)}"><div><b>${esc(name)}</b><span>${esc(detail)}</span></div><input type="checkbox" data-id="${esc(id)}" ${on ? "checked" : ""} aria-label="${esc(name)}"></label>`;
  csheet = h(`<div class="imp-scrim"><div class="imp-sheet" role="dialog" aria-label="Connect your AI">
    <div class="imp-head"><h2>Connect your AI to ${esc(st.project)}</h2><button class="icon-btn sm sq ghost" data-a="x" title="Close (Esc)">${icon("x")}</button></div>
    <p class="imp-lead">${esc(SP.Ai)} does the reading and the building; Spliced gives it the tools. Nothing is sent anywhere: this only writes settings on this machine.</p>
    ${row("agents", "Agents that open this folder", "Claude Code, Codex, Cursor, Gemini CLI: Spliced's skills, a section in AGENTS.md and its tools in .mcp.json. A skill you changed is kept.", true)}
    ${st.apps.map((a) => row(a.id, a.name, a.connected ? "Connected. Untick to take this project out." : a.id === "claude-desktop" ? "Adds this project to its tools. Quit the Claude app and open it again afterwards." : "Adds this project to its tools, from its next chat.", a.connected)).join("")}
    ${st.apps.length ? "" : `<p class="imp-lead">No chat app with tools (the Claude desktop app, Cursor, Codex) was found on this machine.</p>`}
    ${st.worktree ? `<p class="imp-lead">This folder is a git worktree: connect chat apps from the main checkout, which stays put.</p>` : ""}
    <div class="imp-foot"><span class="imp-hint">The same as <code>${esc(SP.cmd("agents", "install"))}</code> and <code>${esc(SP.cmd("connect"))}</code></span>
      <button class="icon-btn" data-a="x2" title="Change nothing">Cancel</button><button class="icon-btn primary" data-a="go" title="Write the settings for what is ticked">Connect</button></div></div></div>`);
  document.body.append(csheet);
  requestAnimationFrame(() => csheet?.classList.add("in"));
  const close = () => { const s = csheet; csheet = null; s?.classList.remove("in"); setTimeout(() => s?.remove(), 180); };
  csheet.querySelectorAll('[data-a="x"], [data-a="x2"]').forEach((b) => (b.onclick = close));
  csheet.addEventListener("mousedown", (e) => { if (e.target === csheet) close(); });
  csheet.tabIndex = -1;
  csheet.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } });
  csheet.focus();
  const go = $('[data-a="go"]', csheet);
  go.onclick = async () => {
    const box = (id) => csheet.querySelector(`input[data-id="${id}"]`).checked;
    go.disabled = true; go.textContent = "Connecting…";
    try {
      const r = await fetch("/api/connect", { method: "POST", body: JSON.stringify({ agents: box("agents"), apps: Object.fromEntries(st.apps.map((a) => [a.id, box(a.id)])) }) });
      const j = await r.json();
      const bad = (j.done || []).filter((d) => !d.ok);
      close(); await done?.();   // (Setup checks again, and says so: what happened here is said after it)
      window.crToast?.(bad.length ? `Didn't finish: ${bad[0].said || bad[0].step}` : (j.done || []).length ? "Connected. Open the folder in your AI, or start a new chat" : "Nothing to change", bad.length ? 8000 : 4000);
    } catch (e) { window.crToast?.(`Couldn't connect: ${e.message}`); go.disabled = false; go.textContent = "Connect"; }
  };
}

let keys = [];
function paint(main, d) {
  const next = d.items.find((i) => i.id === d.next);
  main.innerHTML = "";
  const head = h(`<div class="view-head"><h1>Setup</h1><span class="meta">What Spliced can do on this machine, for ${esc(d.project)}</span><span class="spacer"></span>
    <button class="icon-btn sm" data-a="again" title="Run the checks again">${icon("rotate-cw")}Check again</button>
    <button class="icon-btn sm" data-a="connect" title="Give the agents that open this folder, and the chat apps on this machine, Spliced's tools">${icon("link-2")}Connect your AI…</button>
    <button class="icon-btn sm ${next ? "primary" : ""}" data-a="prompt" title="Copy a request for your AI: it does the installing, one step at a time">${icon("sparkles")}Copy for your AI</button></div>`);
  const page = h(`<div class="set su"></div>`);
  page.append(h(next
    ? `<div class="su-next"><div><b>Next: ${esc(next.label)}</b><span>${rich(next.unlocks)}</span></div>${fixLine(next)}</div>`
    : `<div class="su-next done"><div><b>Everything is set up</b><span>The lines marked "Not added" are extras. Nothing is needed to browse, collect, analyse and make films here.</span></div></div>`));
  for (const lv of d.levels) {
    const items = d.items.filter((i) => i.level === lv.id && i.id !== "connectors");   // the generators get their own block below
    const sec = h(`<section><h2>${esc(lv.label)}<span class="su-lv ${lv.ready ? "ok" : ""}">${lv.ready ? "Ready" : "Not set up yet"}</span></h2><p class="set-lead">${esc(lv.what)}</p></section>`);
    for (const i of items) {
      const [ic, word] = STATE[i.state] || STATE.off;
      const row = h(`<div class="set-row su-row s-${esc(i.state)}"><div><b>${esc(i.label)}</b><span>${rich(i.detail)}</span><span class="su-why">${rich(i.unlocks)}</span>${fixLine(i)}</div>
        <span class="su-state">${icon(ic)}${word}</span></div>`);
      if (i.key && i.state !== "ok") {   // a key it needs: paste it right here
        const k = keys.find((x) => x.id === i.key);
        if (k) $("div", row).append(window.ApiKeys.control(k, () => render(main, true)));
      }
      sec.append(row);
    }
    if (lv.id === "generate") {
      sec.append(h(`<div class="su-connect"><p><b>What your AI can be connected to.</b> None of these is needed to make a film: each gives your AI one more tool. Spliced can't see them: connect them in your AI app's own settings, then ask it which it can reach. What a generator makes is recorded in the film's assets.</p>
        ${CONNECT.map(([name, what]) => `<div><b>${esc(name)}</b><span>${esc(what)}</span></div>`).join("")}</div>`));
    }
    page.append(sec);
  }
  main.append(head, page);
  $('[data-a="again"]', head).onclick = () => render(main, true);
  const conn = $('[data-a="connect"]', head);
  if (conn) conn.onclick = () => (SP.native ? SP.native.ask("connect") : connectSheet(() => render(main, true)));   // the Mac app has its own sheet; a browser gets the page's
  $('[data-a="prompt"]', head).onclick = () => copy(PROMPT(), "Copied: paste it to your AI");
  page.querySelectorAll("[data-copy]").forEach((b) => (b.onclick = () => copy(b.dataset.copy, "Command copied")));
}

async function render(main, again) {
  if (!again) main.innerHTML = `<div class="view-head"><h1>Setup</h1></div><div class="empty">Checking this machine…</div>`;
  try {
    const r = await fetch(again ? "/api/doctor?fresh=1" : "/api/doctor", { cache: "no-store" });   // Check again asks every program afresh
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
    keys = await window.ApiKeys.list().catch(() => []);
    if ((main.dataset.view || "setup") !== "setup") return;   // they moved on while the checks ran
    paint(main, await r.json());
    if (again) window.crToast?.("Checked again");
  } catch (e) {
    main.innerHTML = `<div class="view-head"><h1>Setup</h1></div><div class="empty">Couldn't check this machine: ${esc(e.message)}.<br>From a terminal, <b>${esc(SP.cmd("doctor"))}</b> gives the same answer.</div>`;
  }
}

return { render };
})();
