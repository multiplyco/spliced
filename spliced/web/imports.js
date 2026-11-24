/* Add reference: paste a link, get a film in the library. The sidebar's "Add reference", ⌘K, or pasting a link anywhere
   in the app opens a small sheet; importer.py downloads, analyses and breaks each film down (Claude, headless) in
   the background, and the library reloads itself when it's in. Data: /api/imports. */
window.Imports = (() => {
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const icon = (n) => window.icon(n);
let toastT = 0;
const toast = (msg, ms = 1800) => {
  if (typeof window.crToast === "function") return window.crToast(msg, ms);
  const t = document.getElementById("toast"); if (!t) return;
  t.textContent = msg; t.classList.add("show"); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("show"), ms);
};
const URL_RE = /https?:\/\/[^\s<>"']+/g;
const STEPS = [["download", "Download"], ["analyse", "Analyse"], ["breakdown", "Break down"], ["library", "Add to library"]];
let jobs = [], claude = true, runner = "claude", sheet = null, pollT = 0, seenDone = new Set(JSON.parse(localStorage.getItem("cr.importsSeen") || "[]"));

async function call(path, opts) {
  const r = await fetch(path, opts); const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText); return j;
}
// Who does the reading (the project's choice, runners.py): its own AI on request, or a headless Claude in the background.
const PICKUP = "Run `" + SP.cmd("imports", "next") + "` and do what it prints.";
const HINT = () => runner === "none" ? "Downloaded and analysed here. The breakdown then waits for your AI: ask it to pick up the import."
  : claude ? "Runs in the background, about 10 to 15 minutes a film. You can close this."
  : "Claude Code isn't on this Mac's PATH: films are downloaded and analysed, then ask Claude in the chat to break them down.";
const HISTORY = "cr.importsHistory";   // "0": the Add reference sheet keeps its finished jobs out of sight
const active = () => jobs.filter((j) => j.status === "queued" || j.status === "running");
const since = (iso) => { if (!iso) return ""; const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000); return s < 60 ? `${Math.round(s)}s` : `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, "0")}s`; };

async function refresh() {
  try { const r = await call("/api/imports"); jobs = r.jobs; claude = r.claude; runner = r.runner || "claude"; } catch { return; }
  badge(); if (sheet) paintList();
  if (jobs.some((j) => j.type === "uploads" && (j.status === "running" || j.status === "queued")) || dockUps()) await loadPending();
  for (const j of jobs) if (j.status === "done" && !seenDone.has(j.id)) {
    seenDone.add(j.id); localStorage.setItem("cr.importsSeen", JSON.stringify([...seenDone]));
    if (j.type === "uploads" && !j.scenes) continue;
    // the Mac app: a notification when the person is in another app (only for jobs this page saw running)
    if (watched.has(j.id)) notify(j.type === "folder" ? "Folder brought in" : j.type === "uploads" ? "Uploads analysed" : "Film added",
      j.type === "folder" ? (j.summary || "The folder is in the library") : j.type === "uploads" ? `${j.scenes} upload${j.scenes > 1 ? "s" : ""} analysed` : `${j.film}${j.scenes ? `, ${j.scenes} scenes` : ""} is in the library`);
    if (j.type === "folder") { if (!(watched.has(j.id) || dockShown())) toast(j.summary || "The folder is in", 5000); else finished.set(j.id, Date.now()); continue; }
    if (watched.has(j.id) || dockShown()) { finished.set(j.id, Date.now()); continue; }   // the dock says it
    toast(j.type === "uploads" ? `${j.scenes} upload${j.scenes > 1 ? "s" : ""} analysed: they filter like film scenes now` : `In the library: ${j.film}${j.scenes ? `, ${j.scenes} scenes` : ""}`, 4000);
  }
  for (const j of jobs) if (watched.has(j.id) && j.status === "cancelled" && !finished.has(j.id)) finished.set(j.id, Date.now());
  for (const j of active()) watched.add(j.id);
  paintDock();
  clearTimeout(pollT); pollT = setTimeout(refresh, active().length || sheet || up ? 2000 : 15000);
}
/* An import finished while the person is elsewhere: the Mac app posts a notification; a browser does too, once they
   have said it may (asked the first time they start an import, never out of the blue), and only when the tab is hidden. */
const canNotify = () => !SP.native && "Notification" in window;
function askToNotify() { if (canNotify() && Notification.permission === "default") { try { Notification.requestPermission(); } catch {} } }
function notify(title, body) {
  if (SP.native) return SP.native.ask("notify", { title, body });
  if (canNotify() && Notification.permission === "granted" && document.hidden) { try { new Notification(title, { body, icon: "/app/brand/splice-appicon-ink.svg", tag: "spliced-import" }); } catch {} }
}
const TITLE = document.title;
let docked = -1;   // what the Mac app's Dock icon, or the browser tab's title, last showed
function badge() {
  const n = active().length;
  if (n !== docked) {
    docked = n;
    if (SP.native) SP.native.ask("badge", { count: n });
    else document.title = n ? `(${n}) ${TITLE}` : TITLE;   // a browser has no Dock icon: the tab says how many are running
  }
  const b = document.getElementById("add-ref"); if (!b) return;
  let el = b.querySelector(".imp-badge");
  if (!n) { el?.remove(); b.classList.remove("busy"); return; }
  if (!el) { el = h(`<span class="imp-badge"></span>`); b.append(el); }
  el.innerHTML = `<i></i>${n}`; el.title = `${n} job${n > 1 ? "s" : ""} running: importing or analysing references`;
  b.classList.add("busy");
}

/* ---------- the sheet ---------- */
function open(prefill = "") {
  if (sheet) { const ta = $("textarea", sheet); if (prefill) ta.value = prefill; ta.focus(); return; }
  sheet = h(`<div class="imp-scrim"><div class="imp-sheet" role="dialog" aria-label="Add references">
    <div class="imp-head"><h2>Add references</h2><button class="icon-btn sm sq ghost" data-a="x" title="Close (Esc)">${icon("x")}</button></div>
    <p class="imp-lead">Paste links, drop files, or add a whole folder you already have. A film link (YouTube, Vimeo, X…) is downloaded and broken down scene by scene; images, GIFs and clips are added as they are and analysed. Everything lands in the Library.</p>
    <div class="imp-drop" tabindex="-1">
      <textarea rows="3" placeholder="Paste links, one per line" spellcheck="false">${esc(prefill)}</textarea>
      <div class="imp-files"><span>${icon("upload")}Drop images, GIFs or clips here, or</span><button class="icon-btn sm" data-a="pick">Choose files…</button><button class="icon-btn sm" data-a="folder" title="Bring in a whole folder of pictures, clips and films you already have">Add a folder…</button></div>
    </div>
    <div class="imp-folder" hidden>
      <label class="imp-slug"><span>Folder</span><input placeholder="~/Movies/references" spellcheck="false" aria-label="The folder's path on this computer"></label>
      <button class="icon-btn sm" data-a="look">Look inside</button>
      <p class="imp-fhint">${SP.native ? `Choose it, drop it anywhere on this window, or type its path.` : `Choose it with Add a folder, or type its path. In Finder, right-click the folder, hold <kbd>⌥</kbd> and choose Copy as Pathname.`} Or ask ${esc(SP.ai)}: “import my folder of references”.</p>
      <div class="imp-found" aria-live="polite"></div>
    </div>
    <div class="imp-opts">
      <label class="imp-slug"><span>Name</span><input placeholder="brand-what, e.g. acme-launch-2025 (optional)" spellcheck="false"></label>
      <label class="imp-chk" title="Without it the film is downloaded and analysed only; ask your AI to break it down later"><input type="checkbox" checked> ${runner === "none" ? "Break it down" : "Break it down with Claude"}</label>
    </div>
    <div class="imp-foot"><span class="imp-hint">${HINT()}</span>
      <button class="icon-btn primary" data-a="go">${icon("plus")}Add</button></div>
    <div class="imp-list"></div></div></div>`);
  document.body.append(sheet);
  requestAnimationFrame(() => sheet.classList.add("in"));
  const drop = $(".imp-drop", sheet);
  const files = (list) => { if (window.CR?.uploadFiles) { close(); window.CR.uploadFiles(list); } };
  $('[data-a="pick"]', sheet).onclick = () => { const inp = document.createElement("input"); inp.type = "file"; inp.multiple = true; inp.accept = "image/*,video/*,.gif"; inp.onchange = () => files(inp.files); inp.click(); };
  drop.addEventListener("dragover", (e) => { e.preventDefault(); e.stopPropagation(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); e.stopPropagation(); drop.classList.remove("over"); document.body.classList.remove("dropping"); if (e.dataTransfer.files.length) files(e.dataTransfer.files); });
  const ta = $("textarea", sheet), go = $('[data-a="go"]', sheet), slug = $(".imp-slug input", sheet), chk = $(".imp-chk input", sheet);
  if (!claude) chk.checked = false;
  const sync = () => { const n = (ta.value.match(URL_RE) || []).length + (ta.value.trim() && !URL_RE.test(ta.value) ? 1 : 0); URL_RE.lastIndex = 0; slug.disabled = n > 1; slug.parentElement.classList.toggle("off", n > 1); go.disabled = !ta.value.trim(); };
  ta.oninput = sync; sync();
  ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length);
  const submit = async () => {
    const found = ta.value.match(URL_RE);
    let urls = found ? [...new Set(found)] : ta.value.split(/\n/).map((x) => x.trim()).filter(Boolean);
    if (!urls.length) return;
    askToNotify();   // (a click: the one moment a browser lets a page ask)
    go.disabled = true;
    // links straight to an image, GIF or clip file are uploads; everything else is a film to import
    const media = urls.filter((u) => window.CR?.isMediaUrl?.(u));
    urls = urls.filter((u) => !media.includes(u));
    for (const u of media) await window.CR.uploadUrl(u, { stay: true });
    if (!urls.length) { ta.value = ""; sync(); go.disabled = false; if (media.length) close(); return; }
    try {
      const r = await call("/api/imports", { method: "POST", body: JSON.stringify({ urls, slug: slug.value.trim() || undefined, breakdown: chk.checked }) });
      ta.value = ""; slug.value = ""; sync();
      toast(`${r.jobs.length} film${r.jobs.length > 1 ? "s" : ""} on the way`);
      refresh();
    } catch (e) { toast(`Couldn't add it: ${e.message}`); go.disabled = false; }
  };
  // A folder: look first (how many of what), bring it in only when the person says so
  const fbox = $(".imp-folder", sheet), fin = $("input", fbox), found = $(".imp-found", fbox), lookBtn = $('[data-a="look"]', fbox);
  $('[data-a="folder"]', sheet).onclick = async () => {
    if (SP.native) {   // the Mac app: a real folder picker, then straight to looking inside
      const path = await SP.native.ask("pickFolder");
      if (path) { fbox.hidden = false; fin.value = path; look(); }
      return;
    }
    // a browser is never told where a folder is, so the server asks with the system's own picker (/api/pick-folder);
    // where there is none, or they cancel, the path can still be typed
    if (fbox.hidden) {
      const r = await fetch("/api/pick-folder", { method: "POST", body: JSON.stringify({ for: "import" }) }).then((x) => (x.ok ? x.json() : null)).catch(() => null);
      if (r?.path) { fbox.hidden = false; fin.value = r.path; look(); return; }
    }
    fbox.hidden = !fbox.hidden; if (!fbox.hidden) fin.focus();
  };
  sheet.lookAt = (path) => { fbox.hidden = false; fin.value = path; look(); };
  const n = (k, one, many) => `${k.toLocaleString()} ${k === 1 ? one : many || one + "s"}`;
  const look = async () => {
    if (!fin.value.trim()) return;
    lookBtn.disabled = true; found.textContent = "Looking…";
    try {
      const r = await call("/api/folder/look", { method: "POST", body: JSON.stringify({ folder: fin.value.trim() }) }), tot = r.pictures + r.videos;
      const parts = [r.pictures && `${n(r.pictures, "picture")} and GIFs`, r.videos && n(r.videos, "video")].filter(Boolean).join(", ");
      found.innerHTML = !tot ? `<p><b>${esc(r.name)}</b> holds nothing a library takes: pictures, GIFs and videos.</p>`
        : `<p><b>${esc(r.name)}</b>: ${parts}, ${Math.round(r.bytes / 1e6).toLocaleString()} MB${r.other ? `. ${n(r.other, "other file")} left alone` : ""}.</p>
           <p>${r.videos ? (r.can_sort_videos ? `Videos up to ${r.clip_under} seconds come in as clips, longer ones as films cut into scenes. ` : `Videos wait until ffmpeg is installed (see Setup). `) : ""}Anything already in the library is skipped. Bringing them in is free; reading them is ${esc(SP.ai)}'s work${chk.checked ? "" : ", and is switched off below"}.</p>
           <button class="icon-btn sm primary" data-a="bring">Bring in ${n(tot, "file")}</button>`;
      const bring = $('[data-a="bring"]', found);
      if (bring) bring.onclick = async () => {
        askToNotify();
        bring.disabled = true;
        try { await call("/api/folder/import", { method: "POST", body: JSON.stringify({ folder: r.folder, reading: chk.checked }) }); found.textContent = ""; fin.value = ""; fbox.hidden = true; ta.focus(); toast(`Bringing in ${r.name}`); refresh(); }   // (focus stays in the sheet, so Esc still closes it)
        catch (e) { toast(`Couldn't bring it in: ${e.message}`); bring.disabled = false; }
      };
    } catch (e) { found.innerHTML = `<p class="imp-err">${esc(e.message)}</p>`; }
    lookBtn.disabled = false;
    ($('[data-a="bring"]', found) || fin).focus();   // the pressed button was off while it looked and lost the focus: keep it in the sheet (Enter brings in, Esc closes)
  };
  lookBtn.onclick = look;
  fin.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); look(); } };
  go.onclick = submit;
  ta.onkeydown = (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit(); } };
  $('[data-a="x"]', sheet).onclick = close;
  sheet.addEventListener("mousedown", (e) => { if (e.target === sheet) close(); });
  sheet.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } });
  paintList(); refresh();
}
/** Open the sheet on a folder and look inside it (the Mac app calls this when a folder is dropped on its window). */
function folder(path) { open(); sheet.lookAt(String(path || "")); }
function close() { if (!sheet) return; const s = sheet; sheet = null; s.classList.remove("in"); setTimeout(() => s.remove(), 180); }

function paintList() {
  const box = sheet && $(".imp-list", sheet); if (!box) return;
  // What is under way always shows. What has finished is history, and can be put away (remembered in this browser).
  const all = jobs.slice().reverse().slice(0, 12);
  const live = all.filter((j) => ["running", "queued", "waiting"].includes(j.status)), past = all.filter((j) => !live.includes(j));
  const tucked = localStorage.getItem(HISTORY) === "0";
  const list = tucked ? live : all;
  box.innerHTML = "";
  if (all.length) {
    const head = h(`<div class="imp-rec"><h3>${tucked ? (live.length ? "Under way" : "Recent") : "Recent"}</h3>${past.length ? `<button class="imp-toggle" title="${tucked ? "Show what has finished" : "Put what has finished out of sight"}">${tucked ? `Show history (${past.length})` : "Hide history"}</button>` : ""}</div>`);
    const tog = head.querySelector(".imp-toggle");
    if (tog) tog.onclick = () => { localStorage.setItem(HISTORY, tucked ? "1" : "0"); paintList(); $(".imp-toggle", sheet)?.focus(); };   // (the pressed button is redrawn: keep the focus in the sheet, so Esc still closes it)
    box.append(head);
  }
  for (const j of list) {
    const cur = j.step || "download";
    const el = h(`<div class="imp-job s-${esc(j.status)}">
      <div class="imp-top"><div class="imp-t"><b>${esc(j.title || j.film || j.src.replace(/^https?:\/\/(www\.)?/, ""))}</b><span>${esc(j.film ? j.film : j.src)}</span></div>
        <span class="imp-when">${j.status === "running" ? since(j.started) : j.status === "done" ? "done" : j.status === "failed" ? "failed" : j.status === "cancelled" ? "cancelled" : j.status === "waiting" ? "needs your AI" : "waiting"}</span>
        <span class="imp-acts"></span></div>
      <div class="imp-steps">${(j.type === "uploads" ? [["analyse", "Analyse each upload"]] : j.type === "folder" ? [["bring", "Bring the files in"]] : STEPS).map(([k, l]) => `<span class="st-${esc(j.steps[k]?.status || "todo")}${k === cur && j.status === "running" ? " cur" : ""}"><i></i>${l}</span>`).join("")}</div>
      ${j.status === "running" || j.status === "queued" ? `<div class="imp-act">${esc(j.activity || "")}</div>` : ""}
      ${j.status === "waiting" ? `<div class="imp-act">Downloaded and analysed. Ask your AI to pick it up: <code>${esc(PICKUP)}</code></div>` : ""}
      ${j.status === "failed" ? `<div class="imp-err">${esc((j.error || "").split("\n").slice(-3).join(" "))}</div>` : ""}
      ${j.status === "done" && j.type === "folder" ? `<div class="imp-act">${esc(j.summary || "")}</div>${j.brought?.left?.length ? `<details class="imp-sum"><summary>What was left alone</summary><p>${j.brought.left.slice(0, 40).map(([f, why]) => `${esc(f)}: ${esc(why)}`).join("<br>")}</p></details>` : ""}`
        : j.status === "done" && j.summary ? `<details class="imp-sum"><summary>What ${SP.ai} found</summary><p>${esc(j.summary)}</p></details>` : ""}
    </div>`);
    const acts = $(".imp-acts", el);
    const btn = (label, ic, fn, title = "") => { const b = h(`<button class="icon-btn sm ghost" title="${esc(title)}">${icon(ic)}${label}</button>`); b.onclick = fn; acts.append(b); };
    if (j.status === "done" && (j.type === "uploads" || (j.type === "folder" && j.scenes))) btn("Open", "library-big", () => { close(); location.hash = "#/scenes?film=uploads"; }, "See them in the Library");
    if (j.status === "done" && j.film) btn("Open", "film", () => { close(); location.hash = `#/film/${j.film}`; }, "Open the film in the library");
    if (j.status === "waiting") btn("Copy for your AI", "copy", () => { navigator.clipboard?.writeText(PICKUP); toast("Copied: paste it to your AI"); }, "Copy the line that tells your AI to pick this import up");
    if (j.status === "running" || j.status === "queued" || j.status === "waiting") btn("", "x", () => act(j, "cancel"), "Cancel");
    if (j.status === "failed" || j.status === "cancelled") btn("Retry", "rotate-cw", () => act(j, "retry"));
    if (!["running", "queued", "waiting"].includes(j.status)) btn("", "trash-2", () => act(j, "delete"), "Remove from the list");
    box.append(el);
  }
}
async function act(j, what) {
  try {
    if (what === "delete") await call(`/api/imports/${j.id}`, { method: "DELETE" });
    else await call(`/api/imports/${j.id}/${what}`, { method: "POST", body: "{}" });
  } catch (e) { toast(e.message); }
  refresh();
}

/* ---------- the dock: a small panel at the bottom right while references upload and get analysed ----------
   Rows: the files uploading (real progress per file), the analysis working through the uploads (what it's looking at,
   a strip of what's left), and any film being imported (its step). Finished rows say so for a few seconds, then the
   dock folds away. It takes the place of the toasts for the work it shows. */
let up = null;                       // the batch uploading from this tab: {files: [{name, url, kind}], i, frac, ok, failed, fetching, ended}
let pending = [];                    // uploads not analysed yet (from /api/uploads)
const watched = new Set(), finished = new Map(), most = new Map();   // most: the largest queue an analysis job has had, to count it down
let dockEl = null, dockMin = localStorage.getItem("cr.dockMin") === "1", dockClosed = false, closedIds = new Set(), rowsSig = [];
const dockUps = () => up && (!up.ended || Date.now() - up.ended < 6000);
const dockShown = () => !!dockEl && !dockEl.hidden;
const fileUrl = SP.fileUrl;
const thumbOf = (it) => it.kind === "video" ? `/api/frame?file=${encodeURIComponent(it.file)}&t=0.5&w=120` : fileUrl(it.file);
async function loadPending() {
  try { const r = await call("/api/uploads"); pending = (r.items || []).filter((x) => !x.analysis); } catch {}
}
const loader = `<span class="dk-load"><img class="on-dark" src="brand/splice-loader-white.svg" alt=""><img class="on-light" src="brand/splice-loader-black.svg" alt=""></span>`;
const mark = (st) => st === "done" ? `<span class="dk-mark ok">${icon("check")}</span>` : st === "failed" ? `<span class="dk-mark bad">${icon("x")}</span>` : st === "off" ? `<span class="dk-mark off">${icon("x")}</span>` : loader;
const cancels = new Map();   // row key -> how to stop it (an upload aborts its request; a job asks the server)
function paintDock() {
  const now = Date.now();
  for (const [id, t] of finished) if (now - t > 8000) finished.delete(id);
  const rows = [];
  if (dockUps()) {
    const n = up.files.length, doneN = up.ok + up.failed, frac = up.ended ? 1 : (doneN + (up.frac || 0)) / n, f = up.files[Math.min(up.i, n - 1)];
    rows.push({ st: up.ended ? (up.cancelled ? (up.ok ? "done" : "off") : up.ok ? "done" : "failed") : "run", cancel: !up.ended && up.cancel ? up.cancel : null,
      t: up.ended ? (up.cancelled ? (up.ok ? `${up.ok} uploaded, the rest cancelled` : "Upload cancelled") : up.ok ? `${up.ok} uploaded${up.failed ? `, ${up.failed} failed` : ""}` : "Upload failed") : up.fetching ? "Fetching the file" : `Uploading ${n > 1 ? `${Math.min(up.i + 1, n)} of ${n}` : ""}`.trim(),
      open: up.ended && up.ok ? up.openHash : "",
      sub: up.ended ? (up.ok ? up.after : up.cancelled ? "Nothing was added" : "") : `${f?.name || ""}${up.fetching ? "" : ` · ${Math.round((up.frac || 0) * 100)}%`}`,
      bar: up.ended ? null : up.fetching ? -1 : frac,
      strip: up.ended ? [] : up.files.slice(0, 8).map((x, i) => ({ src: x.url, kind: x.kind, cur: i === up.i, done: i < doneN })) });
  }
  const shownJobs = jobs.filter((j) => j.status === "running" || j.status === "queued" || finished.has(j.id) || (j.status === "waiting" && watched.has(j.id)));
  for (const j of shownJobs) {
    const run = j.status === "running" || j.status === "queued", el = j.started ? since(j.started) : "";
    if (j.status === "waiting") { rows.push({ st: "off", job: j, t: `${j.type === "uploads" ? "Uploads" : j.title || j.film || "Import"}: ready for your AI`, sub: "Ask it to pick up the import (Add reference has the line to copy)" }); continue; }
    if (j.status === "cancelled") { rows.push({ st: "off", job: j, t: j.type === "uploads" ? "Analysis cancelled" : `${j.title || j.film || "Import"} cancelled`, sub: "Stopped; Add reference can retry it" }); continue; }
    const cancelJob = run ? () => act(j, "cancel") : null;
    if (j.type === "uploads") {
      const looking = (j.activity || "").match(/Looking at (.+)$/)?.[1] || "", seen = pending.find((x) => looking && x.file.endsWith(looking));
      if (run) most.set(j.id, Math.max(most.get(j.id) || 0, pending.length));
      const tot = most.get(j.id) || 0, at = Math.min(tot, tot - pending.length + 1);
      rows.push({ st: run ? "run" : j.status === "done" ? "done" : "failed", job: j, cancel: cancelJob,
        t: run ? (j.status === "queued" ? "Waiting to analyse" : tot > 1 ? `Analysing ${at} of ${tot}` : "Analysing the upload") : j.status === "done" ? `${j.scenes || ""} upload${j.scenes === 1 ? "" : "s"} analysed`.trim() : "Analysis failed",
        sub: run ? (looking ? `Looking at ${seen?.title || looking}` : j.activity || "") : j.status === "done" ? "Tags, palette and how it moves: they filter like film scenes now" : (j.error || "").split("\n").pop(),
        right: run ? el : "", bar: run ? (tot > 1 ? (at - 0.5) / tot : -1) : null, open: j.status === "done" ? "#/scenes?film=uploads" : "",
        strip: run ? pending.slice(0, 8).map((x) => ({ src: thumbOf(x), kind: x.kind, cur: !!looking && x.file.endsWith(looking) })) : [] });
    } else if (j.type === "folder") {
      rows.push({ st: run ? "run" : j.status === "done" ? "done" : "failed", job: j, cancel: cancelJob, t: j.title || "Folder",
        sub: run ? j.activity || "" : j.status === "done" ? j.summary || "" : (j.error || "").split("\n").pop(), right: run ? el : "", bar: run ? -1 : null,
        open: j.status === "done" && j.scenes ? "#/scenes?film=uploads" : "" });
    } else {
      const step = STEPS.find(([k]) => k === (j.step || "download"));
      rows.push({ st: run ? "run" : j.status === "done" ? "done" : "failed", job: j, cancel: cancelJob,
        t: j.title || j.film || j.src.replace(/^https?:\/\/(www\.)?/, ""),
        sub: run ? `${step ? step[1] : "Waiting"}${j.activity ? ` · ${j.activity}` : ""}` : j.status === "done" ? `In the library${j.scenes ? `: ${j.scenes} scenes` : ""}` : (j.error || "").split("\n").pop(),
        right: run ? el : "", steps: STEPS.map(([k]) => j.steps?.[k]?.status || "todo"), open: j.status === "done" && j.film ? `#/film/${j.film}` : "" });
    }
  }
  if (!rows.length) { if (dockEl) { dockEl.hidden = true; document.body.classList.remove("has-dock"); } dockClosed = false; return; }
  // closing hides what's running now; anything that starts after brings the dock back
  const sig = rows.filter((r) => r.st === "run").map((r) => r.job?.id || `up${up?.id || ""}`);
  if (dockClosed && sig.some((id) => !closedIds.has(id))) dockClosed = false;
  if (dockClosed) { if (dockEl) dockEl.hidden = true; document.body.classList.remove("has-dock"); return; }
  if (!dockEl) {
    dockEl = h(`<div class="dock" role="status" aria-live="polite"></div>`); document.body.append(dockEl);
    dockEl.addEventListener("click", (e) => {
      const b = e.target.closest("[data-a]"); if (!b) return;
      if (b.dataset.a === "min") { dockMin = !dockMin; localStorage.setItem("cr.dockMin", dockMin ? "1" : "0"); paintDock(); }
      else if (b.dataset.a === "x") { dockClosed = true; closedIds = new Set(rowsSig); paintDock(); }
      else if (b.dataset.a === "open") location.hash = b.dataset.h;
      else if (b.dataset.a === "cancel") { const fn = cancels.get(b.dataset.k); b.disabled = true; b.textContent = "Stopping"; fn?.(); }
      else if (b.dataset.a === "more") open();
    });
  }
  rowsSig = sig;
  const running = rows.filter((r) => r.st === "run").length;
  dockEl.hidden = false; dockEl.classList.toggle("min", dockMin); document.body.classList.add("has-dock");
  const head = running ? `Adding references${running > 1 ? ` · ${running} running` : ""}` : "All done";
  /* patched in place, never rebuilt: a loader that's replaced starts its animation over (it repaints every second),
     and a bar that's replaced can't ease to its new width */
  if (!dockEl.firstChild) dockEl.innerHTML = `<div class="dk-head"><span class="dk-hm"></span><b></b>
      <button class="icon-btn sm sq ghost" data-a="more" title="Details: every import and analysis">${icon("list-video")}</button>
      <button class="icon-btn sm sq ghost" data-a="min"></button><button class="icon-btn sm sq ghost" data-a="x">${icon("x")}</button></div><div class="dk-rows"></div>`;
  const set = (el, prop, v) => { if (el[prop] !== v) el[prop] = v; };
  const hm = $(".dk-hm", dockEl), hst = running ? "run" : "done";
  if (hm.dataset.st !== hst) { hm.dataset.st = hst; hm.innerHTML = mark(hst); }
  set($(".dk-head b", dockEl), "textContent", head);
  const mb = $('[data-a="min"]', dockEl), mt = dockMin ? "Show the details" : "Fold it small";
  if (mb.title !== mt) { mb.title = mt; mb.innerHTML = icon(dockMin ? "chevron-up" : "chevron-down"); }
  set($('[data-a="x"]', dockEl), "title", running ? "Hide it (the work goes on; Add reference shows it)" : "Close");
  const box = $(".dk-rows", dockEl); box.hidden = dockMin;
  const keep = new Set();
  rows.forEach((r, i) => {
    const k = r.job?.id || `up${up?.id || ""}`; keep.add(k);
    let el = box.querySelector(`:scope > [data-k="${CSS.escape(k)}"]`);
    if (!el) {
      el = h(`<div class="dk-row" data-k="${esc(k)}"><span class="dk-mk"></span><div class="dk-t"><div class="dk-l1"></div><div class="dk-sub"></div><div class="dk-steps"></div><div class="dk-strip"></div><div class="dk-bar"><i></i></div></div></div>`);
    }
    if (box.children[i] !== el) box.insertBefore(el, box.children[i] || null);
    set(el, "className", `dk-row s-${r.st}`);
    const mk = $(".dk-mk", el); if (mk.dataset.st !== r.st) { mk.dataset.st = r.st; mk.innerHTML = mark(r.st); }
    if (r.cancel) cancels.set(k, r.cancel); else cancels.delete(k);
    const l1 = `<b>${esc(r.t)}</b>${r.right ? `<span class="dk-r">${esc(r.right)}</span>` : ""}${r.open ? `<button class="dk-open" data-a="open" data-h="${esc(r.open)}">Open</button>` : ""}${r.cancel ? `<button class="dk-open dk-cancel" data-a="cancel" data-k="${esc(k)}" title="Stop it">Cancel</button>` : ""}`;
    set($(".dk-l1", el), "innerHTML", l1);
    const sub = $(".dk-sub", el); set(sub, "textContent", r.sub || ""); sub.hidden = !r.sub;
    const st = $(".dk-steps", el), stH = (r.steps || []).map((x) => `<i class="st-${esc(x)}"></i>`).join(""); if (st.dataset.h !== stH) { st.dataset.h = stH; st.innerHTML = stH; } st.hidden = !r.steps;
    const sp = $(".dk-strip", el), spH = (r.strip || []).map((x) => `<span class="${x.cur ? "cur" : ""} ${x.done ? "done" : ""}">${x.src ? `<img alt="" src="${esc(x.src)}">` : ""}</span>`).join("");
    if (sp.dataset.h !== spH) { sp.dataset.h = spH; sp.innerHTML = spH; } sp.hidden = !r.strip?.length;
    const bar = $(".dk-bar", el); bar.hidden = r.bar == null;
    if (r.bar != null) { bar.classList.toggle("ind", r.bar < 0); set($("i", bar).style, "width", `${r.bar < 0 ? 30 : Math.round(r.bar * 100)}%`); }
  });
  [...box.children].forEach((el) => { if (!keep.has(el.dataset.k)) el.remove(); });
  document.documentElement.style.setProperty("--dock-h", `${dockEl.offsetHeight + 12}px`);
}
// a clip's first frame as a small still, for the dock's strip (made once, so repainting doesn't reload a video)
function posterOf(f) {
  return new Promise((res) => {
    const v = document.createElement("video"), u = URL.createObjectURL(f), done = (x) => { URL.revokeObjectURL(u); res(x); };
    v.muted = true; v.preload = "auto"; v.src = u;
    v.onloadeddata = () => { v.currentTime = Math.min(0.5, (v.duration || 1) / 3); };
    v.onseeked = () => { try { const c = document.createElement("canvas"); c.width = 96; c.height = Math.round(96 * (v.videoHeight / v.videoWidth || 1)); c.getContext("2d").drawImage(v, 0, 0, c.width, c.height); done(c.toDataURL("image/jpeg", 0.7)); } catch { done(""); } };
    v.onerror = () => done(""); setTimeout(() => done(""), 4000);
  });
}
// app.js reports the files it sends (Library: drop, paste, Add reference's file picker)
const upload = {
  start(files, { fetching = false, after = "Analysis starts next", open: openHash = "", cancel = null } = {}) {
    dockClosed = false;
    up = { id: Date.now(), after, openHash, cancel, cancelled: false, files: [...files].map((f) => ({ name: f.name || f, kind: /^video\//.test(f.type || "") ? "video" : "image", url: f instanceof Blob && /^image\//.test(f.type) ? URL.createObjectURL(f) : "" })), i: 0, frac: 0, ok: 0, failed: 0, fetching, ended: 0 };
    [...files].forEach((f, i) => f instanceof Blob && /^video\//.test(f.type) && posterOf(f).then((u) => { if (u && up?.files[i]) { up.files[i].url = u; paintDock(); } }));
    paintDock();
  },
  file(i, name) { if (!up) return; up.i = i; up.frac = 0; if (name) up.files[i].name = name; paintDock(); },
  progress(frac) { if (!up) return; up.frac = frac; paintDock(); },
  done(ok) { if (!up) return; ok ? up.ok++ : up.failed++; up.frac = 0; paintDock(); },
  end({ cancelled = false } = {}) { if (!up) return; up.cancelled = cancelled; up.ended = Date.now(); up.i = up.files.length; paintDock(); refresh(); setTimeout(paintDock, 6200); },
};
setInterval(() => { if (dockShown()) paintDock(); }, 1000);   // the clocks, and finished rows folding away

/* paste a link anywhere (not into a field) to add it */
document.addEventListener("paste", (e) => {
  if (/input|textarea|select/i.test(document.activeElement?.tagName || "") || document.activeElement?.isContentEditable) return;
  const text = e.clipboardData?.getData("text") || "";
  const urls = text.match(URL_RE); URL_RE.lastIndex = 0;
  if (!urls) return;
  e.preventDefault();
  // a link straight to an image, GIF or clip file is a reference to upload; a page (YouTube, Vimeo…) is a film to import
  if (urls.length === 1 && window.CR?.isMediaUrl?.(urls[0])) { window.CR.uploadUrl(urls[0]); return; }
  open(urls.join("\n"));
});

function mount() {
  const b = document.getElementById("add-ref");
  if (b && !b.dataset.wired) { b.dataset.wired = "1"; b.addEventListener("click", () => open()); }
  window.CR?.command({ id: "imp.add", title: "Add reference…", hint: "Paste a link: download, analyse, break down", group: "App", run: () => open() });
  refresh();
}
return { open, close, mount, refresh, upload, folder };
})();
