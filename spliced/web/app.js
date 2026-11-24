/* Spliced: browse, preview, review and collect scenes from the motion reference library.
   Data: window.LIBRARY (/api/library.js, the library index built by build_library.py).
   State: reviews + boards, saved to library/state.json through toolbox.py,
   or to localStorage when the page is opened from disk. */
(() => {
"use strict";

const L = window.LIBRARY;
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
// one timecode format everywhere: m:ss.cc (frames are added where they matter)
const ts = (t) => `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, "0")}`;
const tsf = (t) => `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, "0")}`;
const stars = (n) => "★".repeat(n) + "<i>" + "★".repeat(3 - n) + "</i>";
const icon = window.icon;
document.querySelectorAll("[data-icon]").forEach((el) => el.insertAdjacentHTML("afterbegin", icon(el.dataset.icon)));
const fileUrl = SP.fileUrl;

/* ---------- data ---------- */
const FILMS = {};
const SCENES = [];
for (const f of L.films) {
  FILMS[f.slug] = f;
  f.scenes.forEach((s, i) => {
    s.film = f.slug; s.key = `${f.slug}/${s.id}`; s.idx = i;
    s.text = [s.title, s.on_screen, s.how_it_moves, s.recreate, f.title, f.brand].join(" ").toLowerCase();
    SCENES.push(s);
  });
  (f.signature_moves || []).forEach((m) => (m.scenes || []).forEach((id) => {
    const s = f.scenes.find((x) => x.id === id);
    if (s) (s.moves = s.moves || []).push(m.name);
  }));
}
for (const s of SCENES) s.text += " " + (s.moves || []).join(" ").toLowerCase();
const BY_KEY = Object.fromEntries(SCENES.map((s) => [s.key, s]));

/* ---------- uploads: images, GIFs and clips added by hand (library/uploads, uploads.py), shown among the scenes
   as uploads/<id>. They live in the same SCENES / BY_KEY / FILMS, so favourites, notes, boards and Build all take them. */
FILMS.uploads = { slug: "uploads", title: "Uploads", brand: "Uploaded", category: "upload", scenes: [], fps: 30, file: null, duration: 0, style_signature: {}, summary: "References you uploaded: images, GIFs and clips" };
const UP_EXT = /\.(png|jpe?g|webp|avif|svg|gif|mp4|mov|webm|m4v)(\?|$)/i;
// an analysed upload carries the same fields as a film scene (uploads.py set), so it filters and briefs like one
function uploadScene(x) {
  const a = x.analysis || {};
  return { film: "uploads", id: x.id, key: `uploads/${x.id}`, upload: x, idx: 0, title: x.title || "Untitled", start: 0, end: x.duration || 0, steal: a.steal || 2,
    role: a.role || "", world: a.world || "", subject: a.subject || [], camera: a.camera || [], motion: a.motion || [], type_treatment: a.type_treatment || [],
    pace: a.pace || "", energy: a.energy || "", production: a.production || [], transition_in: "", sound_sync: [],
    on_screen: a.on_screen || x.note || "", how_it_moves: a.how_it_moves || "", recreate: a.recreate || "", palette: x.palette || [],
    text: [x.title, x.note, (x.tags || []).join(" "), x.kind, "upload uploaded", x.source, a.on_screen, a.how_it_moves, a.recreate, a.world, ...(a.motion || []), ...(a.subject || [])].join(" ").toLowerCase() };
}
async function loadUploads() {
  let list = [];
  try { const r = await fetch("/api/uploads", { cache: "no-store" }); if (r.ok) list = (await r.json()).items || []; } catch { return; }
  for (let i = SCENES.length - 1; i >= 0; i--) if (SCENES[i].upload) { delete BY_KEY[SCENES[i].key]; SCENES.splice(i, 1); }
  FILMS.uploads.scenes = list.slice().reverse().map(uploadScene);   // newest first
  FILMS.uploads.scenes.forEach((x, i) => { x.idx = i; SCENES.push(x); BY_KEY[x.key] = x; });
}
async function uploadFiles(files) {
  files = [...files].filter((f) => UP_EXT.test(f.name) || /^(image|video)\//.test(f.type));
  if (!files.length) { toast("Drop images, GIFs or clips (png, jpg, webp, gif, mp4, mov, webm)"); return; }
  if (!server) { toast(`Run ${SP.cmd("open")} to upload`); return; }
  let last = null;
  const dock = window.Imports?.upload;   // the dock at the bottom shows each file's progress, then the analysis
  let xhr = null, stop = false;
  dock?.start(files, { cancel: () => { stop = true; xhr?.abort(); } });
  for (const [i, f] of files.entries()) {
    if (stop) break;
    const name = f.name && f.name !== "image.png" ? f.name : `pasted-${new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-")}.${(f.type.split("/")[1] || "png").replace("jpeg", "jpg")}`;
    if (dock) dock.file(i, name); else toast(`Uploading ${name}…`, 8000);
    try { last = await sendUpload(f, name, (p) => dock?.progress(p), (x) => (xhr = x)); dock?.done(true); }
    catch (e) { if (stop) break; dock?.done(false); toast(`Couldn't upload ${name}: ${e.message}`, 4000); }
  }
  dock?.end({ cancelled: stop });
  if (!last) return;
  await loadUploads();
  if (!dock) toast(files.length > 1 ? `${files.length} references uploaded` : `Uploaded: ${last.title}`, 2600);
  location.hash = files.length > 1 ? "#/scenes?film=uploads" : `#/scene/uploads/${last.id}`;
}
// one file to the server, with its upload progress (fetch can't report that; XHR can)
function sendUpload(f, name, onProgress, onXhr) {
  return new Promise((res, rej) => {
    const x = new XMLHttpRequest(); onXhr?.(x);
    x.onabort = () => rej(new Error("cancelled"));
    x.open("POST", "/api/uploads"); x.setRequestHeader("X-Filename", encodeURIComponent(name));
    x.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
    x.onload = () => { let j = {}; try { j = JSON.parse(x.responseText); } catch {} x.status < 300 ? res(j) : rej(new Error(j.error || x.statusText)); };
    x.onerror = () => rej(new Error("the toolbox didn't answer"));
    x.send(f);
  });
}
async function uploadUrl(url, { stay = false } = {}) {
  const dock = window.Imports?.upload;
  if (dock) dock.start([url.split("/").pop().split("?")[0] || url], { fetching: true }); else toast("Fetching the image…", 8000);
  try {
    const r = await fetch("/api/uploads/url", { method: "POST", body: JSON.stringify({ url }) });
    const j = await r.json(); if (!r.ok) throw new Error(j.error);
    dock?.done(true); dock?.end();
    await loadUploads(); if (!dock) toast(`Uploaded: ${j.title}`); if (!stay) location.hash = `#/scene/uploads/${j.id}`;
  } catch (e) { dock?.done(false); dock?.end(); toast(`Couldn't add it: ${e.message}`, 4000); }
}
window.CR = window.CR || {}; CR.uploadUrl = uploadUrl; CR.uploadFiles = (f) => uploadFiles(f); CR.isMediaUrl = (u) => UP_EXT.test(u);
function pickFiles() {
  const inp = document.createElement("input"); inp.type = "file"; inp.multiple = true; inp.accept = "image/*,video/*,.gif";
  inp.onchange = () => uploadFiles(inp.files); inp.click();
}
// drop files anywhere; paste an image (not into a field)
let dragN = 0;
const isFileDrag = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
// the overlay lives only while files are being dragged over the page: dragover fires many times a second, so when it
// stops (the drag left the window, or was let go somewhere the counting missed) the overlay goes too
let dragT = 0;
const endDrag = () => { clearTimeout(dragT); dragN = 0; document.body.classList.remove("dropping"); };
document.addEventListener("dragenter", (e) => { if (!isFileDrag(e)) return; e.preventDefault(); if (++dragN === 1) document.body.classList.add("dropping"); });
document.addEventListener("dragover", (e) => { if (!isFileDrag(e)) return; e.preventDefault(); document.body.classList.add("dropping"); clearTimeout(dragT); dragT = setTimeout(endDrag, 350); });
["dragend", "blur"].forEach((t) => addEventListener(t, endDrag));
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && document.body.classList.contains("dropping")) endDrag(); }, true);
document.addEventListener("dragleave", (e) => { if (!isFileDrag(e)) return; if (--dragN <= 0) { dragN = 0; document.body.classList.remove("dropping"); } });
document.addEventListener("drop", (e) => {
  if (!isFileDrag(e)) return; e.preventDefault(); endDrag();
  if (route().view === "assets" && window.AssetsView?.drop) { window.AssetsView.drop(e.dataTransfer.files); return; }   // into a film's assets
  uploadFiles(e.dataTransfer.files);
});
document.addEventListener("paste", (e) => {
  if (/input|textarea|select/i.test(document.activeElement?.tagName || "") || document.activeElement?.isContentEditable) return;
  const files = [...(e.clipboardData?.files || [])];
  if (files.length) { e.preventDefault(); e.stopImmediatePropagation(); uploadFiles(files); }
}, true);

const FACETS = [
  ["media", "Media"], ["role", "Role"], ["world", "World"], ["motion", "Motion"], ["transition_in", "Transition in"], ["camera", "Camera"],
  ["type_treatment", "Type"], ["subject", "Subject"], ["production", "Production"], ["pace", "Pace"], ["energy", "Energy"],
  ["sound_sync", "Sound sync"], ["category", "Film category"], ["film", "Film"],
];
const OPEN_DEFAULT = new Set(["media", "role", "world", "motion", "transition_in"]);
// media: film scenes and uploaded clips are video; uploads can also be an image or a GIF
const mediaOf = (s) => (s.upload ? (s.upload.kind === "gif" ? "gif" : s.upload.kind) : "video");
L.tags.media = { video: "Moving footage: scenes from the reference films and uploaded clips", image: "Uploaded stills", gif: "Uploaded GIFs" };
const sceneVal = (s, f) => f === "media" ? [mediaOf(s)] : f === "category" ? [FILMS[s.film].category] : f === "film" ? [s.film] : [].concat(s[f] ?? []);
const defn = (field, tag) => (L.tags[field] || {})[tag] || "";

const ROLE_COL = {
  "cold-open": "#a1a1aa", hook: "#fbbf24", problem: "#f87171", headline: "#e4e4e7", "product-reveal": "#fb923c",
  "feature-demo": "#60a5fa", "use-case": "#4ade80", proof: "#22d3ee", montage: "#c084fc", bridge: "#71717a",
  payoff: "#facc15", "end-card": "#a8a29e",
};

/* ---------- state ---------- */
// Live: every change is an operation sent to the server (POST /api/ops) and applied to the latest state there,
// so a browser tab and Claude (board.py) can work on the same boards at once. Changes made elsewhere arrive
// over /api/events and re-render the app. Opened from disk (no server), state stays in this browser.
let state = { rev: 0, reviews: {}, boards: {}, log: [] };
let server = false, live = false;
const CLIENT = Math.random().toString(36).slice(2, 10);
let current = localStorage.getItem("cr.board") || "";
const ui = {
  filters: {}, q: "", fav: false, verdicts: new Set(), minSteal: 0, notes: false, sort: "best",
  closed: new Set(JSON.parse(localStorage.getItem("cr.closed") || "null") || FACETS.map((f) => f[0]).filter((f) => !OPEN_DEFAULT.has(f))),
  base: "#/scenes", trayOpen: false, briefOpen: false,
  follow: localStorage.getItem("cr.follow") !== "0", flash: new Set(), pending: false,
};
const uid = () => Math.random().toString(16).slice(2, 8);
function normalise(st) {
  st = st || {};
  st.rev ||= 0; st.reviews ||= {}; st.boards ||= {}; st.log ||= []; st.moments ||= [];
  for (const b of Object.values(st.boards)) {
    b.items ||= []; b.profile ||= SPLICED.default_profile; b.brief ||= {};
    for (const it of b.items) { it.uid ||= uid(); it.beat ??= ""; it.copy ??= ""; it.vo ??= ""; it.note ??= ""; }
  }
  return st;
}
async function loadState() {
  try {
    const r = await fetch("/api/state", { cache: "no-store" });
    if (!r.ok) throw 0;
    state = normalise(await r.json()); server = true;
  } catch {
    state = normalise(JSON.parse(localStorage.getItem("cr.state") || "null"));
  }
  if (!Object.keys(state.boards).length) {
    if (server) await send([{ op: "board.create", name: "First board" }]);
    else state.boards["First board"] = normalise({ boards: { x: {} } }).boards.x;
  }
  if (!state.boards[current]) current = latestBoard();
}
/** The board touched last: the default when this browser hasn't picked one (or picked one that's gone). */
const latestBoard = () => Object.entries(state.boards).sort((a, b) => String(b[1].updated || b[1].created || "").localeCompare(String(a[1].updated || a[1].created || "")))[0]?.[0] || "";
/** Send operations (already applied locally, optimistically). Field edits are debounced by the caller. */
async function send(ops) {
  if (!server) { localStorage.setItem("cr.state", JSON.stringify(state)); return; }
  try {
    const r = await fetch("/api/ops", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ by: "browser", client: CLIENT, ops }) });
    const j = await r.json();
    if (!r.ok) { toast(j.error || "Couldn't save"); return pull(); }
    if (j.rev !== state.rev + 1) await pull(); else state.rev = j.rev;
  } catch { toast("Couldn't reach the toolbox server"); }
}
/** Fetch the latest state (after someone else changed it) and re-render, flashing what changed. */
async function pull(by, summary) {
  const r = await fetch("/api/state", { cache: "no-store" });
  const next = normalise(await r.json());
  const before = new Map();
  for (const b of Object.values(state.boards)) for (const it of b.items) before.set(it.uid, JSON.stringify(it));
  for (const b of Object.values(next.boards)) for (const it of b.items) if (before.get(it.uid) !== JSON.stringify(it)) ui.flash.add(it.uid);
  for (const m of state.moments || []) before.set(m.uid, JSON.stringify(m));
  for (const m of next.moments || []) if (before.get(m.uid) !== JSON.stringify(m)) ui.flash.add(m.uid);
  const curItems = state.boards[current]?.items.length;
  state = next;
  if (!state.boards[current]) current = latestBoard();
  if (by && by !== "browser" && summary) toast(`${SP.who(by)}: ${summary}`, 3200);
  rerender();
  setTimeout(() => { ui.flash.clear(); document.querySelectorAll(".flash").forEach((e) => e.classList.remove("flash")); }, 2200);
  return curItems;
}
/** Re-render whatever is on screen, unless the person is typing in a field (then wait until they leave it). */
function rerender() {
  const a = document.activeElement;
  if (a && /input|textarea/i.test(a.tagName) && a.closest("#main, #detail")) { ui.pending = true; renderTray(); return; }
  ui.pending = false;
  render(); renderTray(); paintNavCounts(); if (detailKey) { paintReview(); paintMomentPins(); }
}
document.addEventListener("focusout", () => setTimeout(() => { if (ui.pending && !/input|textarea/i.test(document.activeElement?.tagName || "")) rerender(); }, 50));
function connectLive() {
  if (!server || !window.EventSource) return;
  const es = new EventSource("/api/events");
  es.onopen = () => { live = true; paintStatus(); };
  es.onerror = () => { live = false; paintStatus(); };
  es.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.type === "hello") {
      if (m.rev !== state.rev) pull();
      // a new server (restarted, or started again after a git pull): reload if the app's files changed meanwhile
      if (booted.web && m.web && m.web !== booted.web) codeChanged("code");
      if (booted.data && m.data && m.data !== booted.data) codeChanged("library");
      booted.web ||= m.web; booted.data ||= m.data;
      codeError(m.error || "");
    }
    else if (m.type === "restart") toast("The toolbox's code changed: restarting it", 2400);
    else if (m.type === "code-error") codeError(m.error);
    else if (m.type === "code") codeChanged("code");
    else if (m.type === "library") codeChanged("library");
    else if (m.type === "uploads") loadUploads().then(() => { if (!detailKey || !detailKey.startsWith("uploads/") || BY_KEY[detailKey]) rerender(); });
    else if (m.type === "state") { if (m.client !== CLIENT && m.rev !== state.rev) pull(m.by, m.summary); }
    else if (m.type === "focus") {
      if (ui.follow) { location.hash = m.target; if (m.note) toast(`${SP.Ai}: ${m.note}`, 3600); }
      else toast(`${SP.Ai} points at ${decodeURIComponent(m.target.replace(/^#\//, ""))}${m.note ? ": " + m.note : ""}`, 3600);
    }
  };
}
/* ---------- live code: reload this tab when the app or the library changed, once nobody's typing or playing ---------- */
const booted = { web: "", data: "" };
let reloadWhy = "", lastInput = 0;
document.addEventListener("input", () => (lastInput = performance.now()), true);
function busy() {
  const a = document.activeElement;
  if (a && /input|textarea|select/i.test(a.tagName)) return true;
  if (performance.now() - lastInput < 1500) return true;  // let a debounced field edit save first
  return [...document.querySelectorAll("video")].some((v) => !v.paused && !v.ended && !v.closest(".film-media"));
}
function codeChanged(why) {
  reloadWhy = why === "library" || reloadWhy === "library" ? "library" : "code";
  tryReload();
}
function tryReload() {
  if (!reloadWhy) return;
  if (!busy()) { location.reload(); return; }
  let bar = $("#upd-bar");
  if (!bar) {
    bar = h(`<div class="upd-bar" id="upd-bar"><span class="dot"></span><span></span><button class="icon-btn sm primary">${icon("rotate-cw")}Reload</button></div>`);
    $("button", bar).onclick = () => location.reload();
    document.body.append(bar);
  }
  $("span:nth-child(2)", bar).textContent = reloadWhy === "library" ? "The library was updated" : "The toolbox was updated";
  bar.classList.remove("err");
}
document.addEventListener("focusout", () => setTimeout(tryReload, 120));
document.addEventListener("pause", () => setTimeout(tryReload, 120), true);
setInterval(tryReload, 2000);
function codeError(msg) {
  let bar = $("#err-bar");
  if (!msg) { bar?.remove(); return; }
  if (!bar) { bar = h(`<div class="upd-bar err" id="err-bar"><span class="dot"></span><span>The toolbox's code has an error: still running the old version</span></div>`); document.body.append(bar); }
  bar.title = msg;
}
function paintStatus() {
  const st = $("#status"); if (!st) return;
  const label = server ? (live ? "Live" : "Reconnecting") : "Browser only";
  const tip = server ? `Changes save to library/state.json and appear at once in every open tab, and for ${SP.ai}` : `The server isn't answering: reviews and boards save in this browser only. Run ${SP.cmd("open")} to work live.`;
  st.innerHTML = `<span class="state ${server && live ? "" : "local"}" title="${tip}">${label}</span>
    ${server ? `<button class="icon-btn ghost sq ${ui.follow ? "on" : ""}" data-a="follow" title="${ui.follow ? `Following ${SP.ai}: when it points at a board or scene, go there. Click to stop.` : `Not following ${SP.ai}. Click to go where it points.`}">${icon(ui.follow ? "locate-fixed" : "locate-off")}</button>` : ""}
    <a class="icon-btn ghost sq" href="#/settings" data-a="settings" title="Settings">${icon("settings")}</a><button class="icon-btn ghost sq" data-a="help" title="Keyboard shortcuts (?)">${icon("circle-help")}</button><button class="icon-btn ghost sq" data-a="theme"></button>`;
  $('#status [data-a="help"]').onclick = () => toggleHelp();
  // a dot on Settings while there is news in "What's new" this browser hasn't opened
  const gear = $('#status [data-a="settings"]'), dot = () => window.Changelog?.unseen().then((n) => { gear.classList.toggle("has-news", n > 0); gear.title = n > 0 ? "Settings · something is new in Spliced" : "Settings"; });
  dot(); document.addEventListener("spliced:changelog-seen", dot, { once: true });
  $('#status [data-a="theme"]').onclick = cycleTheme;
  const f = $('#status [data-a="follow"]'); if (f) f.onclick = () => { ui.follow = !ui.follow; localStorage.setItem("cr.follow", ui.follow ? "1" : "0"); paintStatus(); };
  applyTheme();
}
const rev = (key) => state.reviews[key] || {};
function setRev(key, patch) {
  const r = { ...rev(key), ...patch };
  for (const k of Object.keys(r)) if (r[k] === "" || r[k] === false || r[k] == null) delete r[k];
  if (Object.keys(r).length) state.reviews[key] = r; else delete state.reviews[key];
  send([{ op: "review.set", key, patch }]); refreshBadges(key);
}
const board = () => state.boards[current] || { items: [], profile: SPLICED.default_profile, brief: {} };

/* ---------- theme: system / light / dark ---------- */
const THEMES = { dark: ["moon", "Theme: dark"], light: ["sun", "Theme: light"], system: ["monitor", "Theme: system"] };
const themeMode = () => { const m = localStorage.getItem("cr.theme"); return THEMES[m] ? m : "dark"; };   // anything else stored there counts as the default
function applyTheme() {
  const m = themeMode();
  const dark = m === "dark" || (m === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  const b = $('#status [data-a="theme"]');
  if (b) { b.innerHTML = icon(THEMES[m][0]); b.title = `${THEMES[m][1]} (click to change)`; }
}
function cycleTheme() {
  const order = Object.keys(THEMES), m = order[(order.indexOf(themeMode()) + 1) % order.length];
  localStorage.setItem("cr.theme", m); applyTheme(); toast(THEMES[m][1]);
}
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);

/* ---------- toast ---------- */
let toastT;
/* toast(msg, ms, actions): actions = [{label, run}] adds small buttons (Undo, Open) and keeps the toast clickable */
function toast(msg, ms = 1600, actions = null) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  t.classList.toggle("has-act", !!(actions && actions.length));
  for (const a of actions || []) { const b = h(`<button>${esc(a.label)}</button>`); b.onclick = () => { t.classList.remove("show"); a.run(); }; t.append(b); }
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("show"), actions && actions.length ? Math.max(ms, 4200) : ms);
}
window.crToast = (msg, ms, actions) => toast(msg, ms, actions);  // for imports.js, assets.js, styles.js (window.toast is the #toast element)

/* ---------- overflow menus and popovers ----------
   menu(anchor, items, onPick): items = [{value, html, on?, sep?, danger?, hint?}] (sep draws a line before the item) */
let menuEl = null;
function closeMenu() { if (menuEl) { menuEl.remove(); menuEl = null; document.removeEventListener("mousedown", menuOutside, true); } }
function menuOutside(e) { if (menuEl && !menuEl.contains(e.target)) closeMenu(); }
function menu(anchor, items, onPick) {
  closeMenu();
  menuEl = h(`<div class="menu" role="menu">${items.map((it) => `${it.sep ? `<i class="menu-sep"></i>` : ""}<button role="menuitem" data-v="${esc(it.value)}" class="${it.on ? "on" : ""} ${it.danger ? "danger" : ""}">${it.html}${it.hint ? `<kbd>${esc(it.hint)}</kbd>` : ""}${it.on ? icon("check") : ""}</button>`).join("")}</div>`);
  menuEl.querySelectorAll("button").forEach((b) => (b.onclick = () => { closeMenu(); onPick(b.dataset.v); }));
  document.body.append(menuEl);
  const r = anchor.getBoundingClientRect(), w = menuEl.offsetWidth, mh = menuEl.offsetHeight;
  menuEl.style.left = `${Math.max(8, Math.min(r.right - w, innerWidth - w - 8))}px`;
  menuEl.style.top = `${r.bottom + 6 + mh > innerHeight - 8 ? Math.max(8, r.top - mh - 6) : r.bottom + 6}px`;
  setTimeout(() => document.addEventListener("mousedown", menuOutside, true));
}
let copy = async function copy(text, msg = "Copied") {
  try { await navigator.clipboard.writeText(text); }
  catch { const a = h("<textarea></textarea>"); a.value = text; document.body.append(a); a.select(); document.execCommand("copy"); a.remove(); }
  toast(msg);
};

/* ---------- copyable timestamps ----------
   Any element with class "tc-copy" and a data-copy string copies it on click (live timecodes update data-copy
   every frame). Formats: "<id> @ 0:15.42 (f925, 1.92s into the scene)" and "<id> 0:13.50 to 0:17.25". */
const clampN = (x, a, b) => Math.min(b, Math.max(a, x));
const stampAt = (id, t, fps, start, unit = "scene") =>
  `${id} @ ${tsf(t)} (${fps ? `f${Math.round(t * fps)}` : ""}${start != null ? `${fps ? ", " : ""}${Math.max(0, t - start).toFixed(2)}s into the ${unit}` : ""})`.replace(" ()", "");
const stampRange = (id, a, e) => `${id} ${tsf(a)} to ${tsf(e)}`;
const tcCopy = (text, copyText, title = "Click to copy with the clip ID") => `<span class="tc-copy" data-copy="${esc(copyText)}" title="${esc(title)}">${text}</span>`;
document.addEventListener("click", (e) => {
  const el = e.target.closest(".tc-copy");
  if (!el || !el.dataset.copy) return;
  e.preventDefault(); e.stopPropagation();
  copy(el.dataset.copy, `Copied ${el.dataset.copy}`);
  el.classList.add("copied"); setTimeout(() => el.classList.remove("copied"), 1100);
}, true);

/* ---------- scrubbing: drag along any timeline bar ----------
   scrubber(bar, {duration, seek(t), label(t), onStart(), onEnd(t, moved), onClick(t)}): press and drag to scrub,
   a plain click (under 4px of movement) goes to onClick when given. Shift-click copies the time under the pointer.
   Hovering shows the time and what's there. */
function scrubber(bar, o) {
  bar.classList.add("scrub");
  const hover = h(`<div class="scrub-hover"></div>`), tip = h(`<div class="scrub-tip"></div>`);
  bar.append(hover, tip);
  let down = null;
  const D = () => o.duration() || 1;
  const tAt = (x) => { const r = bar.getBoundingClientRect(); return clampN((x - r.left) / r.width, 0, 1) * D(); };
  const showTip = (x) => {
    const r = bar.getBoundingClientRect(), t = tAt(x), px = clampN(x - r.left, 0, r.width);
    tip.textContent = o.label ? o.label(t) : tsf(t);
    const half = tip.offsetWidth / 2, c = o.clip ? o.clip().getBoundingClientRect() : r;   // a bar wider than its box (a zoomed timeline) keeps the tip in the box
    tip.style.left = `${clampN(px, Math.max(0, c.left - r.left) + half - 8, Math.min(r.width, c.right - r.left) - half + 8)}px`;
    hover.style.left = `${px}px`;
    return t;
  };
  bar.addEventListener("pointermove", (e) => {
    const t = showTip(e.clientX);
    if (!down) return;
    if (Math.abs(e.clientX - down.x) > 3) down.moved = true;
    if (down.moved) o.seek(t);
  });
  bar.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault(); e.stopPropagation();
    const t = tAt(e.clientX);
    if (e.shiftKey && o.copyAt) { const txt = o.copyAt(t); copy(txt, `Copied ${txt}`); return; }
    bar.setPointerCapture(e.pointerId);
    down = { x: e.clientX, moved: false };
    bar.classList.add("dragging"); document.body.classList.add("scrubbing");
    o.onStart?.();
    if (!o.onClick) o.seek(t);
  });
  const up = (e) => {
    if (!down) return;
    const t = tAt(e.clientX), moved = down.moved || !o.onClick;
    down = null;
    bar.classList.remove("dragging"); document.body.classList.remove("scrubbing");
    if (!moved) { o.onEnd?.(t, false); o.onClick(t, e); }
    else { o.seek(t); o.onEnd?.(t, true); }
  };
  bar.addEventListener("pointerup", up);
  bar.addEventListener("pointercancel", up);
  bar.addEventListener("click", (e) => e.stopPropagation());
}
const sceneAt = (f, t) => f.scenes.find((x) => t >= x.start && t < x.end) || (t >= f.duration - 0.05 ? f.scenes[f.scenes.length - 1] : null);

/* ---------- thumbnails that scrub through the scene's frames ---------- */
function frameCount(s) { const d = s.end - s.start; return d <= 2.5 ? 3 : d <= 5 ? 4 : 5; }
function upThumb(s) {
  const x = s.upload, isVid = x.kind === "video";
  const ar = x.width && x.height ? Math.min(2.4, Math.max(0.5, x.width / x.height)) : 16 / 9;
  const el = h(`<div class="thumb up" data-key="${esc(s.key)}" style="aspect-ratio:${ar.toFixed(4)}"><img loading="lazy" alt="" src="${isVid ? `/api/frame?file=${encodeURIComponent(x.file)}&t=0.4&w=480` : fileUrl(x.file)}"><span class="up-kind">${x.kind === "gif" ? "GIF" : isVid ? icon("play") : ""}</span></div>`);
  if (isVid) {
    el.addEventListener("mouseenter", () => { if (el.querySelector("video")) return; const v = document.createElement("video"); v.muted = true; v.loop = true; v.playsInline = true; v.src = fileUrl(x.file); el.append(v); v.play().catch(() => {}); });
    el.addEventListener("mouseleave", () => el.querySelector("video")?.remove());
  }
  return el;
}
function thumb(s, { scrub = true } = {}) {
  if (s.upload) return upThumb(s);
  const n = frameCount(s);
  const el = h(`<div class="thumb" data-key="${esc(s.key)}"><img loading="lazy" alt="" src="${SP.stripUrl(s.film, s.id)}"><div class="ticks">${"<span></span>".repeat(n)}</div><div class="head"><i></i></div></div>`);
  const img = $("img", el), head = $(".head i", el), ticks = [...el.querySelectorAll(".ticks span")];
  let fw = 0, W = 0;
  const show = (i) => {
    if (!W) return;
    img.style.transform = `translateX(${(-i * (fw + 6) / W) * 100}%)`;
    head.style.left = `${(i / n) * 100}%`; head.style.width = `${100 / n}%`;
    ticks.forEach((t, j) => t.classList.toggle("on", j === i));
  };
  img.onload = () => {
    W = img.naturalWidth; fw = (W - 6 * (n - 1)) / n;
    el.style.aspectRatio = `${fw} / ${img.naturalHeight}`;
    show(Math.floor(n / 2));
  };
  if (scrub) hoverLoop(el, s);
  return el;
}
/* hover a scene: its clip plays muted, looping its own range (one at a time across the app) */
let loopVid = null;
function hoverLoop(el, s) {
  let t = 0;
  const stopLoop = () => { clearTimeout(t); if (loopVid && loopVid.parentElement === el) { loopVid.pause(); loopVid.remove(); loopVid = null; } el.classList.remove("looping"); };
  el.addEventListener("mouseenter", () => {
    const f = FILMS[s.film]; if (!f?.file || localStorage.getItem("cr.hoverPlay") === "0") return;
    t = setTimeout(() => {
      if (loopVid) { loopVid.pause(); loopVid.parentElement?.classList.remove("looping"); loopVid.remove(); }
      const v = document.createElement("video");
      v.muted = true; v.playsInline = true; v.preload = "auto"; v.disablePictureInPicture = true; v.className = "loop";
      v.src = fileUrl(f.file) + `#t=${s.start.toFixed(2)}`;
      const a = s.start, e = Math.max(s.start + 0.3, s.end - 0.04);
      v.addEventListener("loadedmetadata", () => { try { v.currentTime = a + 0.01; } catch {} v.play().catch(() => {}); });
      v.addEventListener("playing", () => el.classList.add("looping"));
      const back = () => { if (v.currentTime >= e || v.currentTime < a - 0.3) { try { v.currentTime = a + 0.01; } catch {} } };
      v.addEventListener("timeupdate", back);
      if (v.requestVideoFrameCallback) { const fr = () => { if (!v.isConnected) return; back(); v.requestVideoFrameCallback(fr); }; v.requestVideoFrameCallback(fr); }  // frame-exact loop
      el.append(v); loopVid = v;
    }, 140);
  });
  el.addEventListener("mouseleave", stopLoop);
}

/* ---------- filtering ---------- */
function matches(s, except) {
  if (ui.q) for (const w of ui.q.toLowerCase().split(/\s+/).filter(Boolean)) if (!s.text.includes(w) && !s.key.includes(w)) return false;
  const r = rev(s.key);
  if (ui.fav && !r.fav) return false;
  if (ui.verdicts.size && !ui.verdicts.has(r.verdict || "none")) return false;
  if (ui.notes && !r.note) return false;
  if (s.steal < ui.minSteal) return false;
  for (const [f, set] of Object.entries(ui.filters)) {
    if (f === except || !set.size) continue;
    if (!sceneVal(s, f).some((v) => set.has(v))) return false;
  }
  return true;
}
const activeCount = () => Object.values(ui.filters).reduce((a, s) => a + s.size, 0) + (ui.fav ? 1 : 0) + ui.verdicts.size + (ui.minSteal ? 1 : 0) + (ui.notes ? 1 : 0) + (ui.q ? 1 : 0);
function toggleFilter(f, v, only = false) {
  const set = (ui.filters[f] ||= new Set());
  if (only) { Object.keys(ui.filters).forEach((k) => ui.filters[k].clear()); set.add(v); }
  else set.has(v) ? set.delete(v) : set.add(v);
  syncHash(); render();
}
function clearFilters() {
  ui.filters = {}; ui.q = ""; ui.fav = false; ui.verdicts.clear(); ui.minSteal = 0; ui.notes = false; $("#q").value = "";
  syncHash(); render();
}
function filtersToQuery() {
  const p = new URLSearchParams();
  for (const [f, set] of Object.entries(ui.filters)) if (set.size) p.set(f, [...set].join(","));
  if (ui.q) p.set("q", ui.q);
  if (ui.fav) p.set("fav", "1");
  if (ui.verdicts.size) p.set("verdict", [...ui.verdicts].join(","));
  if (ui.minSteal) p.set("steal", ui.minSteal);
  if (ui.notes) p.set("notes", "1");
  if (ui.sort !== "best") p.set("sort", ui.sort);
  return p.toString();
}
function queryToFilters(qs) {
  const p = new URLSearchParams(qs);
  ui.filters = {};
  for (const [f] of FACETS) if (p.get(f)) ui.filters[f] = new Set(p.get(f).split(","));
  ui.q = p.get("q") || "";
  if (document.activeElement !== $("#q")) $("#q").value = ui.q;
  ui.fav = p.get("fav") === "1"; ui.notes = p.get("notes") === "1";
  ui.verdicts = new Set((p.get("verdict") || "").split(",").filter(Boolean));
  ui.minSteal = +p.get("steal") || 0; ui.sort = p.get("sort") || "best";
}
function syncHash() {
  const r = route();
  if (r.view === "scenes") { const qs = filtersToQuery(); history.replaceState(null, "", "#/scenes" + (qs ? "?" + qs : "")); ui.base = location.hash; }
}

/* ---------- routing ---------- */
function route() {
  const [path, qs] = location.hash.replace(/^#\/?/, "").split("?");
  const parts = path.split("/").filter(Boolean);
  const view = parts[0] || "scenes";
  return { view, parts, qs: qs || "" };
}
function onHash() {
  const r = route();
  if (r.view === "scene") {
    const s = BY_KEY[`${r.parts[1]}/${r.parts[2]}`];
    if (!s) { location.hash = ui.base; return; }
    build.stop();
    const at = +new URLSearchParams(r.qs).get("t");
    if (at) { pendingStart = at; holdStart = true; }  // #/scene/<film>/<sNN>?t=42.51 opens the scene paused on that frame
    openDetail(s);
    if (!$("#main").dataset.view) renderBase(ui.base);
    return;
  }
  closeDetail(false);
  ui.base = location.hash || "#/scenes";
  if (r.view === "scenes") queryToFilters(r.qs);
  renderBase(ui.base);
}
let lastPath = null;
function renderBase(hash) {
  const [path] = hash.replace(/^#\/?/, "").split("?");
  const parts = path.split("/").filter(Boolean);
  const view = parts[0] || "scenes";
  const sys = view === "film" && parts[1] === "system-moves";
  document.querySelectorAll("#views a").forEach((a) => a.classList.toggle("on", sys ? a.dataset.view === "systems" : a.dataset.view === view || (view === "film" && a.dataset.view === "films")));
  document.body.classList.toggle("no-tray", view === "build");
  if (view === "build" && ui.trayOpen) setTray(false);
  if (view !== "scenes") closeFpop();
  if (path !== lastPath) { $("#main").scrollTop = 0; lastPath = path; }
  $("#main").dataset.view = view;
  build.stop(); stopPreviews(); window.AssetsView?.stop?.(); window.StylesView?.stop?.();
  filmHero = null;
  if (view === "scenes") renderScenes();
  else if (view === "moments") renderMoments();
  else if (view === "moves") renderMoves();
  else if (view === "films") renderFilms();
  else if (view === "film") renderFilm(parts[1]);
  else if (view === "styles") renderStyles();
  else if (view === "settings") renderSettings();
  else if (view === "setup") window.SetupView.render($("#main"));
  else if (view === "boards") parts[1] ? renderBoards(decodeURIComponent(parts[1])) : renderBoardGrid();
  else if (view === "build") parts[1] ? build.renderFilm($("#main"), parts[1]) : build.renderList($("#main"));
  else if (view === "assets") { if (window.AssetsView) window.AssetsView.render($("#main")); else $("#main").innerHTML = `<div class="empty">Assets aren't available.</div>`; }
  else renderScenes();
}
function render() { renderBase(ui.base); }

/* ---------- filters: a Linear-style Filter popover instead of a rail of tags ---------- */
const STEAL = [[0, "Any"], [2, "★★ and up"], [3, "★★★ only"]];
const facetValues = (f) => f === "film" ? Object.keys(FILMS) : f === "category" ? Object.keys(L.tags.category) : Object.keys(L.tags[f] || {});
const facetLabel = (f) => (FACETS.find((x) => x[0] === f) || [f, f])[1];
const valueTitle = (f, v) => f === "film" ? `${FILMS[v].title} (${FILMS[v].brand})` : defn(f, v);
let fpop = null, fpopFacet = localStorage.getItem("cr.facet") || "role", fpopQ = "";
function closeFpop() { if (fpop) { fpop.remove(); fpop = null; document.removeEventListener("mousedown", fpopOutside, true); $("#filter-btn")?.classList.remove("on"); } }
function fpopOutside(e) { if (fpop && !fpop.contains(e.target) && !e.target.closest("#filter-btn")) closeFpop(); }
function openFpop() {
  if (fpop) { closeFpop(); return; }
  const btn = $("#filter-btn"); if (!btn) return;
  btn.classList.add("on");
  fpop = h(`<div class="fpop" role="dialog" aria-label="Filter scenes"><div class="fpop-q">${icon("search")}<input placeholder="Filter by tag, film, role…" spellcheck="false"><kbd>Esc</kbd></div><div class="fpop-body"><div class="fpop-facets"></div><div class="fpop-vals"></div></div><div class="fpop-foot"><span>Click to add · <b>Alt</b>-click for only this one</span><span class="gap"></span><button class="fpop-clear">Clear all</button></div></div>`);
  document.body.append(fpop);
  const r = btn.getBoundingClientRect();
  fpop.style.top = `${r.bottom + 8}px`; fpop.style.left = `${Math.max(12, Math.min(r.right - 560, innerWidth - 572))}px`;
  const inp = $("input", fpop); inp.value = fpopQ;
  inp.oninput = () => { fpopQ = inp.value; paintFpop(); };
  inp.onkeydown = (e) => { e.stopPropagation(); if (e.key === "Escape") { e.preventDefault(); closeFpop(); } };
  $(".fpop-clear", fpop).onclick = () => { clearFilters(); paintFpop(); };
  paintFpop(); inp.focus();
  setTimeout(() => document.addEventListener("mousedown", fpopOutside, true));
}
function paintFpop() {
  if (!fpop) return;
  const facets = $(".fpop-facets", fpop), vals = $(".fpop-vals", fpop), q = fpopQ.trim().toLowerCase();
  const counts = (f) => { const c = {}; for (const s of SCENES) if (matches(s, f)) for (const v of sceneVal(s, f)) c[v] = (c[v] || 0) + 1; return c; };
  facets.innerHTML = "";
  const facetBtn = (f, label, n) => { const b = h(`<button class="${!q && fpopFacet === f ? "on" : ""}">${esc(label)}${n ? `<span class="n">${n}</span>` : ""}</button>`); b.onclick = () => { fpopFacet = f; localStorage.setItem("cr.facet", f); fpopQ = ""; $("input", fpop).value = ""; paintFpop(); }; facets.append(b); };
  facetBtn("steal", "Steal-worthy", ui.minSteal ? 1 : 0);
  for (const [f, label] of FACETS) facetBtn(f, label, (ui.filters[f] || new Set()).size);
  vals.innerHTML = "";
  const row = (f, v, n, sel) => {
    const el = h(`<button class="fv ${sel ? "on" : ""} ${n ? "" : "zero"}" title="${esc(valueTitle(f, v))}"><span class="ck">${sel ? icon("check") : ""}</span><span class="v">${esc(v)}</span>${q ? `<span class="f">${esc(facetLabel(f))}</span>` : ""}<span class="c">${n || 0}</span></button>`);
    el.onclick = (e) => { toggleFilter(f, v, e.altKey); paintFpop(); };
    vals.append(el);
  };
  if (q) {
    let any = 0;
    for (const [f] of FACETS) {
      const c = counts(f), sel = ui.filters[f] || new Set();
      for (const v of facetValues(f)) if ((v.toLowerCase().includes(q) || (f === "film" && FILMS[v].title.toLowerCase().includes(q))) && (c[v] || sel.has(v)) && any < 80) { row(f, v, c[v], sel.has(v)); any++; }
    }
    if (!any) vals.append(h(`<div class="fpop-none">No tag matches "${esc(fpopQ)}"</div>`));
    return;
  }
  if (fpopFacet === "steal") {
    for (const [v, l] of STEAL) { const el = h(`<button class="fv ${ui.minSteal === v ? "on" : ""}"><span class="ck">${ui.minSteal === v ? icon("check") : ""}</span><span class="v">${l}</span></button>`); el.onclick = () => { ui.minSteal = v; syncHash(); render(); paintFpop(); }; vals.append(el); }
    return;
  }
  const c = counts(fpopFacet), sel = ui.filters[fpopFacet] || new Set();
  facetValues(fpopFacet).filter((v) => c[v] || sel.has(v)).sort((a, b) => (c[b] || 0) - (c[a] || 0)).forEach((v) => row(fpopFacet, v, c[v], sel.has(v)));
  if (fpopFacet in L.tags || fpopFacet === "film") { const d = h(`<div class="fpop-def"></div>`); vals.prepend(d); vals.onmouseover = (e) => { const b = e.target.closest(".fv"); d.textContent = b ? b.title : ""; }; }
}

/* ---------- scenes view ---------- */
function sortScenes(list) {
  if (ui.sort === "best") return list.sort((a, b) => b.steal - a.steal || (rev(b.key).fav ? 1 : 0) - (rev(a.key).fav ? 1 : 0) || a.key.localeCompare(b.key, undefined, { numeric: true }));
  if (ui.sort === "film") return list.sort((a, b) => a.film.localeCompare(b.film) || a.idx - b.idx);
  if (ui.sort === "short") return list.sort((a, b) => (a.end - a.start) - (b.end - b.start));
  if (ui.sort === "long") return list.sort((a, b) => (b.end - b.start) - (a.end - a.start));
  return list;
}
const SORTS = [["best", "Best first"], ["film", "Film order"], ["short", "Shortest"], ["long", "Longest"]];
function card(s) {
  const f = FILMS[s.film];
  const el = h(`<article class="card" data-key="${esc(s.key)}">
    <div class="quick"><button data-a="fav" title="Favourite (F)" aria-label="Favourite">${icon("heart")}</button><button data-a="board" title="Add to ${esc(current)} (B)" aria-label="Add to board">${icon("plus")}</button></div>
    <div class="cap">
      <div class="title">${esc(s.title)}</div>
      ${s.upload ? `<div class="id"><span>Uploaded <span class="k">${esc(s.key)}</span></span><span>${s.upload.analysis ? "" : `<span class="up-ing" title="Being analysed">${icon("loader")}</span>`}${esc(s.upload.kind === "gif" ? "GIF" : s.upload.kind)}${s.upload.duration ? ` · ${s.upload.duration.toFixed(1)}s` : ""}</span></div>`
        : `<div class="id"><span>${esc(f.brand)} <span class="k">${esc(s.film)}/${s.id}</span></span><span>${s.steal >= 3 ? `<span class="stars" title="Steal-worthy">★★★</span>` : ""}${tcCopy(ts(s.start), stampRange(s.key, s.start, s.end))} · ${(s.end - s.start).toFixed(1)}s</span></div>`}
      <div class="lx">${s.on_screen ? `<p>${esc(s.on_screen)}</p>` : ""}<div class="lx-tags">${[s.role, s.world, ...(s.motion || []).slice(0, 3), s.transition_in].filter((v) => v && v !== "none").map((v) => `<span>${esc(v)}</span>`).join("")}</div></div>
    </div></article>`);
  const th = thumb(s);
  th.append(h(`<div class="badges"></div>`), h(`<div class="tags"></div>`),
    h(`<div class="ov"><span class="t">${esc(s.title)}</span><span class="m">${s.upload ? `Uploaded · ${esc(s.upload.kind === "gif" ? "GIF" : s.upload.kind)}` : `${esc(f.brand)} · ${ts(s.start)} · ${(s.end - s.start).toFixed(1)}s`}</span></div>`));
  el.prepend(th);
  const tags = $(".tags", th);
  for (const t of s.upload?.tags || []) tags.append(h(`<span class="tag">${esc(t)}</span>`));
  for (const [field, v] of [["world", s.world], ...s.motion.slice(0, 2).map((m) => ["motion", m]), ["transition_in", s.transition_in]]) {
    if (!v || v === "none") continue;
    const c = h(`<button class="tag" title="${esc(`Filter: ${facetLabel(field)} ${v}. ${defn(field, v)}`)}">${esc(v)}</button>`);
    c.onclick = (e) => { e.stopPropagation(); toggleFilter(field, v); };
    tags.append(c);
  }
  const open = () => (location.hash = `#/scene/${s.key}`);
  th.onclick = open; $(".title", el).onclick = open;
  $('[data-a="fav"]', el).onclick = (e) => { e.stopPropagation(); setRev(s.key, { fav: !rev(s.key).fav }); };
  $('[data-a="board"]', el).onclick = (e) => { e.stopPropagation(); addToBoard(s.key); };
  paintBadges(el, s.key);
  if (location.hash === `#/scene/${s.key}`) el.classList.add("sel");
  return el;
}
function paintBadges(el, key) {
  const b = $(".badges", el); if (!b) return;
  const r = rev(key);
  b.innerHTML = (r.fav ? `<span class="badge fav" title="Favourite">${icon("heart")}</span>` : "") + (r.note ? `<span class="badge" title="${esc(r.note)}">${icon("message-square")}</span>` : "") +
    (board().items.some((i) => i.id === key) ? `<span class="badge board" title="On ${esc(current)}">${icon("check")}</span>` : "");
  $('.quick [data-a="fav"]', el)?.classList.toggle("on", !!r.fav);
}
function refreshBadges(key) {
  document.querySelectorAll(`.card[data-key="${CSS.escape(key)}"]`).forEach((el) => paintBadges(el, key));
  if (detailKey === key) paintReview();
  paintCollect();
}
/* the All / Favourites / With notes control and the counts in it */
function paintCollect() {
  const seg = $("#collect"); if (!seg) return;
  const favs = SCENES.filter((s) => rev(s.key).fav).length, noted = SCENES.filter((s) => rev(s.key).note).length;
  const mode = ui.fav ? "fav" : ui.notes ? "notes" : "all";
  seg.innerHTML = [["all", "All", ""], ["fav", "Favourites", favs], ["notes", "With notes", noted]].map(([v, l, n]) => `<button data-v="${v}" class="${mode === v ? "on" : ""}">${l}${n !== "" ? `<span class="n">${n}</span>` : ""}</button>`).join("");
  seg.querySelectorAll("button").forEach((b) => (b.onclick = () => { ui.fav = b.dataset.v === "fav"; ui.notes = b.dataset.v === "notes"; syncHash(); render(); }));
}
/* the quick Media control in the header: All / Video / Images / GIFs (the same filter as Filter > Media) */
function paintMedia() {
  const seg = $("#media-seg"); if (!seg) return;
  const sel = ui.filters.media || new Set(), cur = sel.size === 1 ? [...sel][0] : sel.size ? "mixed" : "all";
  const n = (m) => SCENES.filter((x) => mediaOf(x) === m && matches(x, "media")).length;
  // no "All" here (the next control has one): click a kind to show only it, click it again to show everything
  const opts = [["video", "Video", n("video")], ["image", "Images", n("image")], ["gif", "GIFs", n("gif")]].filter(([v, , c]) => v === "video" || c || cur === v);
  seg.innerHTML = opts.map(([v, l, c]) => `<button data-v="${v}" class="${cur === v ? "on" : ""}" title="${cur === v ? "Show everything again" : `Only ${l.toLowerCase()}`}">${l}<span class="n">${c}</span></button>`).join("");
  seg.querySelectorAll("button").forEach((b) => (b.onclick = () => { if (cur === b.dataset.v) delete ui.filters.media; else ui.filters.media = new Set([b.dataset.v]); syncHash(); render(); }));
}
/* the Library as a grid (zoomable: fewer, bigger cards or more, smaller ones) or a list; remembered */
// card width, continuous from small to extra large
const ZMIN = 150, ZMAX = 460;
let libView = localStorage.getItem("cr.libView") === "list" ? "list" : "grid";
let libZoom = Math.min(ZMAX, Math.max(ZMIN, +(localStorage.getItem("cr.libCardW") || 300)));
// how many cards fit at the slider's width; the cards then stretch to fill the row
function colsFor(grid) {
  const gap = parseFloat(getComputedStyle(grid).columnGap) || 24, w = grid.clientWidth || $("#main").clientWidth - 112;
  return Math.max(1, Math.floor((w + gap) / (libZoom + gap)));
}
let zoomT = null;
function applyZoom(grid = $(".grid.lib")) {
  if (!grid) return;
  const n = colsFor(grid), was = +grid.style.getPropertyValue("--cols") || 0;
  const set = () => { grid.style.setProperty("--cols", n); grid.classList.toggle("small", libZoom < 200); masonry(grid, n); };
  if (!was || was === n || !document.startViewTransition || zoomT || matchMedia("(prefers-reduced-motion: reduce)").matches) { set(); return; }
  // the cards in view glide to their new size and place (view transitions); the rest just reflow
  const vh = innerHeight, named = [];
  grid.querySelectorAll(".card").forEach((c, i) => { const r = c.getBoundingClientRect(); if (r.bottom > -200 && r.top < vh + 200) { c.style.viewTransitionName = `card-${i}`; named.push(c); } });
  zoomT = document.startViewTransition(set);
  zoomT.finished.finally(() => { named.forEach((c) => (c.style.viewTransitionName = "")); zoomT = null; if (colsFor(grid) !== +grid.style.getPropertyValue("--cols")) applyZoom(grid); });
}
// the page's width changes too (window, sidebar, the scene panel): keep the columns fitting
new ResizeObserver(() => { const g = $(".grid.lib"); if (g && !zoomT) { const n = colsFor(g); g.style.setProperty("--cols", n); masonry(g, n); if (detailKey) revealSel(false); } }).observe(document.getElementById("main"));   // (the scene panel sliding in narrows the page: the open scene stays in view)
/* the grid as masonry (like Pinterest): every card keeps its own shape, and goes into the shortest column, so the Library
   reads left to right, top to bottom, without gaps. Heights are known up front from the film's or the upload's size. */
const aspectOf = (s) => { const w = s.upload ? s.upload.width : FILMS[s.film]?.width, hh = s.upload ? s.upload.height : FILMS[s.film]?.height; return Math.min(2.4, Math.max(0.5, w && hh ? w / hh : 16 / 9)); };
function masonry(grid, n) {
  const cards = grid._cards; if (!cards) return;
  const list = grid.classList.contains("list");
  if (grid._n === (list ? "list" : n)) return;
  for (const c of cards) if (!c.real) sizePlace(c.el, c);   // the columns changed: a place's remembered height no longer holds
  const first = !grid._laid; grid._laid = true;   // the first screenful rises in; after that cards just appear
  if (list) { grid.replaceChildren(...cards.map((c) => c.el)); grid._n = "list"; libNear(grid, first); return; }
  grid._n = n;
  const cols = Array.from({ length: n }, () => h(`<div class="mcol"></div>`)), hgt = new Array(n).fill(0);
  const extra = document.documentElement.classList.contains("cards-always") ? 0.32 : 0;  // the caption under the picture, in card widths
  for (const c of cards) { let k = 0; for (let j = 1; j < n; j++) if (hgt[j] < hgt[k] - 0.01) k = j; cols[k].append(c.el); hgt[k] += 1 / c.ar + extra + 0.06; }
  grid.replaceChildren(...cols);
  libNear(grid, first);
}
/* Only the cards near the window exist. Every scene has its place in the grid from the start: an empty box in the
   card's shape (the height is known from the film's proportions), so the page is as long as it will ever be and
   the scrollbar tells the truth. A place becomes its card when it comes within NEAR of the window and goes back
   to an empty box, at the height the card had, when it leaves. A library of thousands of scenes then costs what
   a screenful costs. Anything that looks for a scene's card by its key finds its place too ([data-key]). */
const NEAR = 1400;
let libIO = null;
// A place is as tall as its card will be: the picture's shape, plus what a card adds around it (the caption when
// captions are always shown, the text beside the picture in the list), which is measured from a real card (--cap,
// --rowx). A place that was a card remembers that card's exact height.
function sizePlace(el, c, px) {
  el.style.height = el.style.aspectRatio = el.style.paddingBottom = "";
  if (px) { el.style.height = `${px}px`; el.style.paddingBottom = "0"; }
  else if (libView === "list") el.style.height = `calc(${(200 / c.ar).toFixed(2)}px + var(--rowx, 25px))`;
  else el.style.aspectRatio = String(c.ar);
}
function measureCard(grid) {
  const c = grid._cards.find((x) => x.real); if (!c) return;
  const r = c.el.getBoundingClientRect().height, th = c.el.querySelector(".thumb")?.getBoundingClientRect().height || r;
  if (grid.classList.contains("list")) grid.style.setProperty("--rowx", `${Math.max(0, r - 200 / c.ar).toFixed(2)}px`);
  else grid.style.setProperty("--cap", `${Math.max(0, r - th).toFixed(2)}px`);
}
function place(c, px) {
  const el = h(`<div class="card-ph" data-key="${esc(c.s.key)}"></div>`);
  el._c = c; sizePlace(el, c, px);
  if (detailKey === c.s.key) el.classList.add("sel");
  return el;
}
function swap(c, el) { el._c = c; c.el.replaceWith(el); libIO?.unobserve(c.el); libIO?.observe(el); c.el = el; }
function showCard(c, i = -1) {
  if (c.real) return;
  const el = card(c.s);
  if (i >= 0) el.style.animationDelay = `${Math.min(i, 24) * 14}ms`; else el.style.animation = "none";   // only the first screenful rises in
  if (detailKey === c.s.key) el.classList.add("sel");
  const th = el.querySelector(".thumb:not(.up)"); if (th) th.style.aspectRatio = String(c.ar);   // its place's shape until its picture says otherwise: nothing shifts as it loads
  swap(c, el); c.real = true;
}
function hideCard(c) {
  if (!c.real || c.el.matches(":hover, :focus-within")) return;
  const px = c.el.getBoundingClientRect().height;   // to the fraction: a rounded pixel a card adds up over a long column
  swap(c, place(c, px)); c.real = false;
}
/** Make the cards that are near the window right now (without waiting a frame for the observer: no flash of empty boxes). */
function libNear(grid, first = false) {
  const vh = innerHeight, near = [];
  grid._cards.forEach((c) => { if (!c.real) { const r = c.el.getBoundingClientRect(); if (r.bottom > -NEAR && r.top < vh + NEAR) near.push(c); } });
  near.forEach((c, i) => showCard(c, first ? i : -1));
  measureCard(grid);
}
/** Keep the open scene's card in view: a glide when it is a card nearby, a jump when it is a place far down the page
    (a glide over thousands of cards never arrives). Called again when the columns change under it. */
function revealSel(glide) {
  const el = $(".grid.lib .card.sel, .grid.lib .card-ph.sel"); if (!el) return;
  const r = el.getBoundingClientRect();
  if (r.top >= 0 && r.bottom <= innerHeight) return;
  const far = el.classList.contains("card-ph");
  el.scrollIntoView({ block: far ? "center" : "nearest", behavior: glide && !far ? "smooth" : "auto" });
  if (far) { const g = el.closest(".grid.lib"); if (g?._cards) libNear(g); }
}
function libWindow(grid) {
  libIO?.disconnect();
  libIO = new IntersectionObserver((entries) => { for (const en of entries) { const c = en.target._c; if (c && c.el === en.target) (en.isIntersecting ? showCard : hideCard)(c); } }, { root: $("#main"), rootMargin: `${NEAR}px 0px` });
  for (const c of grid._cards) libIO.observe(c.el);
}
function setZoom(z) {
  libZoom = Math.min(ZMAX, Math.max(ZMIN, z)); localStorage.setItem("cr.libCardW", Math.round(libZoom));
  if (libView === "list") { libView = "grid"; localStorage.setItem("cr.libView", "grid"); $(".grid.lib")?.classList.remove("list"); }
  applyZoom();
  const r = $("#lib-view input"); if (r && document.activeElement !== r) r.value = libZoom;
  $("#lib-view .lib-zoom")?.classList.toggle("off", libView === "list");
}
function setLibView(v) { libView = v; localStorage.setItem("cr.libView", v); const g = $(".grid.lib"); if (g) { g.classList.toggle("list", v === "list"); g._n = null; masonry(g, colsFor(g)); } paintLibView(); }
function paintLibView() {
  const box = $("#lib-view"); if (!box) return;
  box.innerHTML = `<div class="seg quiet"><button data-v="grid" class="${libView === "grid" ? "on" : ""}" title="Grid">${icon("layout-grid")}</button><button data-v="list" class="${libView === "list" ? "on" : ""}" title="List">${icon("layout-list")}</button></div>
    <label class="lib-zoom ${libView === "list" ? "off" : ""}" title="Card size (- and =, or pinch)"><input type="range" min="${ZMIN}" max="${ZMAX}" step="1" value="${libZoom}" aria-label="Card size"></label>`;
  box.querySelectorAll(".seg button").forEach((b) => (b.onclick = () => setLibView(b.dataset.v)));
  $("input", box).oninput = (e) => setZoom(+e.target.value);
}
// pinch on a trackpad (ctrl + wheel) over the Library zooms the grid; - and = do it from the keyboard
document.addEventListener("wheel", (e) => {
  if (!e.ctrlKey || route().view !== "scenes" || !e.target.closest?.("#main")) return;
  e.preventDefault();
  setZoom(libZoom - e.deltaY * 1.5);
}, { passive: false });
let zoomAcc = 0;
function renderScenes() {
  const main = $("#main");
  const list = sortScenes(SCENES.filter((s) => matches(s)));
  main.innerHTML = "";
  const nf = Object.values(ui.filters).reduce((a, x) => a + x.size, 0) + (ui.minSteal ? 1 : 0);
  const head = h(`<div class="view-head"><h1>Library</h1><span class="spacer"></span>
    <div class="seg quiet" id="media-seg" title="Video, images or GIFs"></div>
    <div class="seg quiet" id="collect"></div>
    <button class="icon-btn sm ${nf ? "on" : "ghost"}" id="filter-btn" title="Filter scenes (F)">${icon("sliders")}Filter${nf ? `<span class="cnt">${nf}</span>` : ""}</button>
    <div class="lib-view" id="lib-view"></div>
    <button class="icon-btn sm sq ghost" id="sort-btn" title="Sort: ${esc((SORTS.find((x) => x[0] === ui.sort) || SORTS[0])[1].toLowerCase())}" aria-label="Sort">${icon("arrow-up-down")}</button>
    <button class="icon-btn sm primary" id="add-ref" title="Paste links or drop files: films, images, GIFs and clips (or drop them anywhere)">${icon("plus")}<span>Add reference</span></button></div>`);
  main.append(head);
  paintCollect(); paintMedia();
  $("#filter-btn", head).onclick = openFpop;
  $("#add-ref", head).onclick = () => (window.Imports ? window.Imports.open() : pickFiles());
  window.Imports?.refresh?.();  // its running-jobs badge
  $("#sort-btn", head).onclick = (e) => menu(e.currentTarget, SORTS.map(([v, l]) => ({ value: v, html: `<span class="lbl">${l}</span>`, on: ui.sort === v })), (v) => { ui.sort = v; syncHash(); render(); });
  const act = h(`<div class="active-filters"></div>`);
  for (const [f, set] of Object.entries(ui.filters)) for (const v of set) {
    const c = h(`<button class="fchip" title="Remove this filter"><span class="f">${esc(facetLabel(f))}</span>${esc(v)}${icon("x")}</button>`); c.onclick = () => { toggleFilter(f, v); paintFpop(); }; act.append(c);
  }
  if (ui.minSteal) { const c = h(`<button class="fchip"><span class="f">Steal-worthy</span>${ui.minSteal === 3 ? "★★★" : "★★ and up"}${icon("x")}</button>`); c.onclick = () => { ui.minSteal = 0; syncHash(); render(); paintFpop(); }; act.append(c); }
  if (ui.q) { const c = h(`<button class="fchip"><span class="f">Search</span>${esc(ui.q)}${icon("x")}</button>`); c.onclick = () => { ui.q = ""; $("#q").value = ""; syncHash(); render(); }; act.append(c); }
  if (act.children.length > 1) { const c = h(`<button class="fclear">Clear all</button>`); c.onclick = () => { clearFilters(); paintFpop(); }; act.append(c); }
  if (act.children.length) main.append(act);
  if (!SCENES.length) {
    const e = h(`<div class="empty start"><b>Your library is empty</b><p>Start with one film whose look or motion you like. Paste its link: Spliced downloads it and cuts it into scenes you can browse, tag and borrow from.</p>
      <div><button class="icon-btn" data-a="add">${icon("plus")}Add a reference</button><button class="icon-btn" data-a="how">How Spliced works</button></div></div>`);
    $('[data-a="add"]', e).onclick = () => (window.Imports ? window.Imports.open() : pickFiles());
    $('[data-a="how"]', e).onclick = () => window.Welcome?.open();
    main.append(e); return;
  }
  if (!list.length) { main.append(h(`<div class="empty">No scene matches. <b>Clear a filter</b> or search for something broader.</div>`)); return; }
  viewOrder = list.map((x) => x.key);
  const grid = h(`<div class="grid lib ${libView === "list" ? "list" : ""}"></div>`);
  grid._cards = list.map((s) => { const c = { s, ar: aspectOf(s), el: null, real: false }; c.el = place(c); return c; });
  main.append(grid);
  libIO?.disconnect(); libIO = null;
  applyZoom(grid);          // lays the places out in columns, and makes the cards near the window
  libWindow(grid);
  paintLibView(grid);
}

/* ---------- detail ---------- */
let detailKey = null, video = null, videoFile = null, loopRange = [0, 0], rafId = 0, context = false, scrubbing = false, pendingStart = null, holdStart = false;
/* the logo: on hover the blocks sink and rise once, the brand's own motion (brand/splice-sink-white.svg, 3.6s, stair order) */
(async () => {
  const brand = $(".brand"), polys = [...(brand?.querySelectorAll(".lockup polygon") || [])].slice(0, 12);
  if (polys.length < 12 || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  let txt; try { txt = await (await fetch("brand/splice-sink-white.svg")).text(); } catch { return; }
  const anims = [...new DOMParser().parseFromString(txt, "image/svg+xml").querySelectorAll("polygon > animate")];
  if (anims.length !== 12) return;
  const els = anims.map((a, i) => {
    const n = document.createElementNS("http://www.w3.org/2000/svg", "animate");
    for (const at of a.attributes) n.setAttribute(at.name, at.value);
    n.setAttribute("begin", "indefinite"); n.setAttribute("repeatCount", "1"); n.setAttribute("fill", "remove");
    polys[i].append(n); return n;
  });
  let busy = false;
  brand.addEventListener("mouseenter", () => {
    if (busy) return; busy = true;
    els.forEach((n) => n.beginElement());
    setTimeout(() => (busy = false), 3600);
  });
})();
/* the sidebar folds away (⌘\, the button in its head, or ⌘K); a small button brings it back; remembered */
function setSidebar(open, save = true) {
  document.documentElement.classList.toggle("sb-off", !open);
  const fb = document.getElementById("sb-fold"); if (fb) { fb.innerHTML = icon("panel-left-close"); fb.title = "Hide the sidebar (⌘\\)"; }
  document.documentElement.classList.remove("sb-peek");
  if (save) localStorage.setItem("cr.sidebar", open ? "1" : "0");
}
/* folded away, it still opens as a drawer: hover the left edge and it slides over the page (which shifts a little),
   links work as usual, and it slides away when the pointer leaves. Click the sidebar itself (not a link) to keep it open. */
let sbPeekT = 0;
const folded = () => document.documentElement.classList.contains("sb-off");
function sbPeek(on) {
  clearTimeout(sbPeekT);
  if (!folded()) return;
  const fb = document.getElementById("sb-fold");
  if (fb) { fb.innerHTML = icon(on ? "panel-left" : "panel-left-close"); fb.title = on ? "Keep the sidebar open (⌘\\)" : "Hide the sidebar (⌘\\)"; }
  if (on) document.documentElement.classList.add("sb-peek");
  else sbPeekT = setTimeout(() => { if (document.activeElement?.id !== "q") document.documentElement.classList.remove("sb-peek"); }, 280);  // stays while typing in Search
}
setSidebar(localStorage.getItem("cr.sidebar") !== "0", false);
(() => {
  const opener = h(`<button class="sb-unfold" title="Show the sidebar (⌘\\)" aria-label="Show the sidebar">${icon("panel-left")}</button>`);
  opener.onclick = () => setSidebar(true); document.body.append(opener);
  const edge = h(`<div class="sb-edge" aria-hidden="true"></div>`); document.body.append(edge);
  const sb = $(".sidebar");
  for (const el of [edge, opener, sb]) { el.addEventListener("mouseenter", () => sbPeek(true)); el.addEventListener("mouseleave", (e) => { if (!sb.contains(e.relatedTarget) && e.relatedTarget !== opener && e.relatedTarget !== edge) sbPeek(false); }); }
  $("#q")?.addEventListener("blur", () => { if (!sb.matches(":hover")) sbPeek(false); });
  // a click on the drawer itself (not a link, button or field) keeps it open
  sb.addEventListener("click", (e) => { if (document.documentElement.classList.contains("sb-peek") && !e.target.closest("a, button, input, select, textarea, label")) setSidebar(true); });
  $("#sb-fold")?.addEventListener("click", (e) => { e.stopPropagation(); setSidebar(document.documentElement.classList.contains("sb-peek")); });
  document.addEventListener("keydown", (e) => { if (KB.is(e, "sidebar")) { e.preventDefault(); setSidebar(document.documentElement.classList.contains("sb-off")); } });
  window.CR?.command({ id: "app.sidebar", title: "Show or hide the sidebar", group: "App", keys: "⌘\\", run: () => setSidebar(document.documentElement.classList.contains("sb-off")) });
})();
/* the sidebar's width: drag its right edge (double-click resets); remembered in this browser */
(() => {
  const KEY = "cr.sidebarW";
  const set = (w, save) => {
    w = Math.round(Math.min(Math.max(200, w), 420));
    document.documentElement.style.setProperty("--sidebar-w", `${w}px`);
    if (save) localStorage.setItem(KEY, w);
  };
  if (+localStorage.getItem(KEY)) set(+localStorage.getItem(KEY), false);
  const grip = h(`<div class="sb-grip" title="Drag to resize · double-click to reset" role="separator" aria-orientation="vertical"></div>`);
  document.body.append(grip);
  grip.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault(); grip.setPointerCapture(e.pointerId); document.body.classList.add("resizing-sb");
    const move = (ev) => set(ev.clientX, false);
    const up = (ev) => { grip.removeEventListener("pointermove", move); grip.removeEventListener("pointerup", up); grip.removeEventListener("pointercancel", up);
      document.body.classList.remove("resizing-sb"); set(ev.clientX, true); };
    grip.addEventListener("pointermove", move); grip.addEventListener("pointerup", up); grip.addEventListener("pointercancel", up);
  });
  grip.addEventListener("dblclick", () => { localStorage.removeItem(KEY); document.documentElement.style.removeProperty("--sidebar-w"); });
})();
/* the scene panel's width: drag its left edge (double-click resets); remembered in this browser */
const DETAIL_W = "cr.detailW";
function setDetailW(w, save = true) {
  const sb = document.documentElement.classList.contains("sb-off") ? 0 : parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--sidebar-w")) || 252;
  w = Math.round(Math.min(Math.max(360, w), innerWidth - sb - 320));
  document.documentElement.style.setProperty("--detail", `${w}px`);
  if (save) localStorage.setItem(DETAIL_W, w);
}
if (+localStorage.getItem(DETAIL_W)) setDetailW(+localStorage.getItem(DETAIL_W), false);
addEventListener("resize", () => { const w = +localStorage.getItem(DETAIL_W); if (w) setDetailW(w, false); });
(() => {
  const grip = h(`<div class="detail-grip" title="Drag to resize · double-click to reset" role="separator" aria-orientation="vertical"></div>`);
  document.body.append(grip);
  grip.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault(); grip.setPointerCapture(e.pointerId); document.body.classList.add("resizing-detail");
    const move = (ev) => setDetailW(innerWidth - ev.clientX, false);
    const up = (ev) => { grip.removeEventListener("pointermove", move); grip.removeEventListener("pointerup", up); grip.removeEventListener("pointercancel", up);
      document.body.classList.remove("resizing-detail"); setDetailW(innerWidth - ev.clientX); };
    grip.addEventListener("pointermove", move); grip.addEventListener("pointerup", up); grip.addEventListener("pointercancel", up);
  });
  grip.addEventListener("dblclick", () => { localStorage.removeItem(DETAIL_W); document.documentElement.style.removeProperty("--detail"); });
})();
function openDetail(s) {
  detailKey = s.key;
  document.body.classList.add("detail-open");
  $("#detail").setAttribute("aria-hidden", "false");
  document.querySelectorAll(".card.sel, .card-ph.sel").forEach((c) => c.classList.remove("sel"));
  // (the scene's card, or its place in the Library when it is far from the window: scrolling there makes the card)
  document.querySelectorAll(`.card[data-key="${CSS.escape(s.key)}"], .card-ph[data-key="${CSS.escape(s.key)}"]`).forEach((c) => c.classList.add("sel"));
  revealSel(true);
  renderDetail(s);
}
function closeDetail(nav = true) {
  if (!detailKey) return;
  detailKey = null;
  document.body.classList.remove("detail-open");
  $("#detail").setAttribute("aria-hidden", "true");
  document.querySelectorAll(".card.sel, .card-ph.sel").forEach((c) => c.classList.remove("sel"));
  if (video) video.pause();
  if (nav) location.hash = ui.base;
}
function brief(s, withNote = true) {
  if (s.upload) {
    const x = s.upload, r = rev(s.key);
    return [`### ${s.key}: ${s.title}`, `An uploaded reference (${x.kind === "gif" ? "a GIF" : x.kind === "video" ? `a ${x.duration ? x.duration.toFixed(1) + "s " : ""}clip` : "an image"}${x.width ? `, ${x.width}x${x.height}` : ""}): ${x.file}. Look at it before building.`,
      x.source ? `Source: ${x.source}` : "", x.tags?.length ? `Tags: ${x.tags.join(", ")}` : "",
      x.analysis ? `Library tags: ${["world", "subject", "camera", "motion", "type_treatment", "pace", "energy", "production"].map((k) => [k, [].concat(x.analysis[k] || []).filter(Boolean)]).filter(([, v]) => v.length).map(([k, v]) => `${k.replace("_", " ")} ${v.map((t) => "`" + t + "`").join(" ")}`).join(" · ")}` : "",
      x.palette?.length ? `Palette: ${x.palette.join(" ")}` : "", x.analysis?.on_screen ? `On screen: ${x.analysis.on_screen}` : "",
      x.analysis?.how_it_moves ? `How it moves: ${x.analysis.how_it_moves}` : "", x.analysis?.recreate ? `Recreate: ${x.analysis.recreate}` : "",
      x.note ? `What to take from it: ${x.note}` : "", withNote && r.note ? `Our note: ${r.note}` : ""].filter(Boolean).join("\n");
  }
  const f = FILMS[s.film], r = rev(s.key);
  const tagline = [["role", s.role], ["world", s.world], ["camera", s.camera], ["motion", s.motion], ["transition in", s.transition_in], ["type", s.type_treatment], ["pace", s.pace], ["energy", s.energy], ["production", s.production]]
    .filter(([, v]) => [].concat(v).length).map(([k, v]) => `${k} ${[].concat(v).map((x) => "`" + x + "`").join(" ")}`).join(" · ");
  return [
    `### ${s.key}: ${s.title}`,
    `From "${f.title}" (${f.brand}), ${ts(s.start)} to ${ts(s.end)} (${(s.end - s.start).toFixed(1)}s). Breakdown: library/references/${s.film}/breakdown.md#${s.id}`,
    `Tags: ${tagline}`,
    s.palette?.length ? `Palette: ${s.palette.join(" ")}` : "",
    `On screen: ${s.on_screen}`,
    `How it moves: ${s.how_it_moves}`,
    `Recreate: ${s.recreate}`,
    withNote && r.note ? `Our note: ${r.note}` : "",
  ].filter(Boolean).join("\n");
}
function renderUploadDetail(s) {
  const x = s.upload, d = $("#detail"), f = FILMS.uploads, i = f.scenes.indexOf(s), prev = f.scenes[i - 1], next = f.scenes[i + 1];
  if (video) video.pause();
  video = null; videoFile = null; cancelAnimationFrame(rafId);
  d.innerHTML = "";
  d.append(h(`<div class="d-top"><button class="id" data-a="id" title="Copy the ID"><b>uploads</b>/${esc(x.id)}</button>
    <div class="review" id="review"></div>
    <button class="icon-btn sm primary" data-a="brief" title="Copy a brief to paste into ${SP.ai} (C)">${icon("copy")}Copy brief</button>
    <span class="d-nav"><button class="icon-btn sm sq ghost" data-a="prev" title="Previous (${esc(KB.get("prev").map(KB.label).join(" or "))})">${icon("chevron-up")}</button><button class="icon-btn sm sq ghost" data-a="next" title="Next (${esc(KB.get("next").map(KB.label).join(" or "))})">${icon("chevron-down")}</button></span>
    <button class="icon-btn sm sq ghost" data-a="close" title="Close (Esc)">${icon("x")}</button></div>`));
  $('#detail [data-a="prev"]').onclick = () => goScene(neighbour(s.key, -1));
  $('#detail [data-a="next"]').onclick = () => goScene(neighbour(s.key, 1));
  d.append(h(`<div class="player up-media">${x.kind === "video" ? `<video src="${fileUrl(x.file)}" controls autoplay muted loop playsinline></video>` : `<img alt="" src="${fileUrl(x.file)}">`}</div>`));
  const body = h(`<div class="d-body up-body">
    <input class="inl up-title" data-k="title" value="${esc(x.title)}" placeholder="Title" spellcheck="false">
    <div class="d-film">Uploaded${x.added ? ` ${esc(x.added.slice(0, 10))}` : ""}<span>·</span>${esc(x.kind === "gif" ? "GIF" : x.kind)}${x.width ? `<span>·</span>${x.width}x${x.height}` : ""}${x.duration ? `<span>·</span>${x.duration.toFixed(1)}s` : ""}</div>
    <div class="d-sec"><h5>What to take from it</h5><textarea class="inl" data-k="note" rows="2" placeholder="The move, the type, the colour, the pace: what we'd steal${esc(SP.forBrand())}">${esc(x.note || "")}</textarea></div>
    ${x.analysis ? `${x.palette?.length ? `<div class="d-sec"><h5>Palette</h5><div class="swatches">${x.palette.map((c) => `<span class="sw" data-c="${esc(c)}"><i style="background:${esc(c)}"></i>${esc(c)}</span>`).join("")}</div></div>` : ""}
      <div class="d-sec"><h5>On screen</h5><p class="lead">${esc(x.analysis.on_screen || "")}</p></div>
      ${x.analysis.how_it_moves ? `<div class="d-sec"><h5>${x.kind === "image" ? "How it could move" : "How it moves"}</h5><p>${esc(x.analysis.how_it_moves)}</p></div>` : ""}
      <div class="d-sec"><h5>Recreate${esc(SP.forBrand())}</h5><p>${esc(x.analysis.recreate || "")}</p></div>
      <div class="d-sec"><h5>Library tags</h5><div class="tagtable" id="up-tags"></div></div>`
      : `<div class="up-pending">${icon("loader")}<div><b>Being analysed</b><span>${SP.Ai} is reading it like a film scene: style, colours, motion and how we'd recreate it. It takes a minute or two.</span></div><button class="icon-btn sm ghost" data-a="analyse">Queue again</button></div>`}
    <div class="d-sec"><h5>Your tags</h5><input class="inl" data-k="tags" value="${esc((x.tags || []).join(", "))}" placeholder="e.g. kinetic type, grain, split screen" spellcheck="false"></div>
    <div class="d-sec"><h5>Source</h5><input class="inl" data-k="source" value="${esc(x.source || "")}" placeholder="Where it's from (a link or a name)" spellcheck="false">${/^https?:/.test(x.source || "") ? `<a class="up-src" href="${esc(x.source)}" target="_blank" rel="noopener">${icon("external-link")}Open</a>` : ""}</div>
    <div class="up-acts">${x.analysis ? `<button class="icon-btn sm ghost" data-a="reanalyse" title="Analyse it again">${icon("rotate-cw")}Analyse again</button>` : ""}<button class="icon-btn sm ghost" data-a="finder">${icon("folder-open")}Show in Finder</button><button class="icon-btn sm ghost danger" data-a="del">${icon("trash-2")}Delete</button></div>
    <div class="nav-row">${prev ? `<a href="#/scene/${prev.key}"><small>Previous <kbd>[</kbd></small>${esc(prev.title)}</a>` : "<span></span>"}${next ? `<a class="next" href="#/scene/${next.key}"><small><kbd>]</kbd> Next</small>${esc(next.title)}</a>` : "<span></span>"}</div></div>`);
  d.append(body);
  body.querySelectorAll("[data-k]").forEach((el) => {
    let t1; el.oninput = () => { clearTimeout(t1); t1 = setTimeout(() => saveUpload(x, { [el.dataset.k]: el.value }), 600); };
  });
  $('[data-a="close"]', d).onclick = () => closeDetail();
  $('[data-a="id"]', d).onclick = () => copy(s.key, `Copied ${s.key}`);
  $('[data-a="brief"]', d).onclick = () => copy(brief(s), `Brief copied: paste it into ${SP.ai}`);
  $('[data-a="finder"]', d).onclick = () => fetch("/api/reveal", { method: "POST", body: JSON.stringify({ path: x.file }) });
  const queue = async (ids) => { await fetch("/api/uploads/analyse", { method: "POST", body: JSON.stringify({ ids }) }); toast(`Queued: ${SP.ai} will analyse it`); };
  $('[data-a="analyse"]', d)?.addEventListener("click", () => queue([]));
  $('[data-a="reanalyse"]', d)?.addEventListener("click", () => queue([x.id]));
  d.querySelectorAll(".sw").forEach((sw) => (sw.onclick = () => copy(sw.dataset.c, `Copied ${sw.dataset.c}`)));
  const tt = $("#up-tags", d);
  if (tt) for (const [field, label] of [["role", "role"], ["world", "world"], ["subject", "subject"], ["camera", "camera"], ["motion", "motion"], ["type_treatment", "type"], ["pace", "pace"], ["energy", "energy"], ["production", "production"]]) {
    const vals = [].concat(s[field] ?? []).filter(Boolean); if (!vals.length) continue;
    const v = h(`<div class="v"></div>`);
    for (const t of vals) { const c = h(`<span class="chip" title="${esc(defn(field, t))}">${esc(t)}</span>`); c.onclick = () => { closeDetail(false); ui.filters = { [field]: new Set([t]) }; ui.q = ""; location.hash = "#/scenes?" + filtersToQuery(); }; v.append(c); }
    tt.append(h(`<div class="k">${label}</div>`), v);
  }
  $('[data-a="del"]', d).onclick = async () => {
    if (!confirm(`Delete "${x.title}"? The file goes too.${board().items.some((it) => it.id === s.key) ? " It's on a board: remove it there first." : ""}`)) return;
    const r = await fetch(`/api/uploads/${x.id}`, { method: "DELETE" });
    if (!r.ok) { toast("Couldn't delete it"); return; }
    await loadUploads(); closeDetail(); render(); toast("Deleted");
  };
  paintReview();
  d.scrollTop = 0;
}
async function saveUpload(x, patch) {
  try {
    const r = await fetch(`/api/uploads/${x.id}`, { method: "PATCH", body: JSON.stringify(patch) });
    const j = await r.json(); if (!r.ok) throw new Error(j.error);
    Object.assign(x, j); const s = BY_KEY[`uploads/${x.id}`]; if (s) Object.assign(s, uploadScene(x), { idx: s.idx });
    document.querySelectorAll(`.card[data-key="uploads/${CSS.escape(x.id)}"] .title`).forEach((t) => (t.textContent = x.title));
    toast("Saved");
  } catch (e) { toast(`Couldn't save: ${e.message}`); }
}
function renderDetail(s) {
  if (s.upload) return renderUploadDetail(s);
  const f = FILMS[s.film], d = $("#detail");
  const fps = f.fps || 30;
  const sameFile = video && videoFile === f.file && d.contains(video);
  const i = f.scenes.indexOf(s), prev = f.scenes[i - 1], next = f.scenes[i + 1];
  d.innerHTML = "";
  d.append(h(`<div class="d-top"><button class="id" data-a="id" title="Copy the scene ID"><b>${esc(s.film)}</b>/${s.id}</button>
    <div class="review" id="review"></div>
    <button class="icon-btn sm primary" data-a="brief" title="Copy a brief to paste into ${SP.ai} (C)">${icon("copy")}Copy brief</button>
    <span class="d-nav"><button class="icon-btn sm sq ghost" data-a="prev" title="Previous (${esc(KB.get("prev").map(KB.label).join(" or "))})">${icon("chevron-up")}</button><button class="icon-btn sm sq ghost" data-a="next" title="Next (${esc(KB.get("next").map(KB.label).join(" or "))})">${icon("chevron-down")}</button></span>
    <button class="icon-btn sm sq ghost" data-a="close" title="Close (Esc)">${icon("x")}</button></div>`));
  $('#detail [data-a="prev"]').onclick = () => goScene(neighbour(s.key, -1));
  $('#detail [data-a="next"]').onclick = () => goScene(neighbour(s.key, 1));
  const player = h(`<div class="player"></div>`);
  if (!sameFile) {
    video = document.createElement("video");
    video.muted = true; video.playsInline = true; video.preload = "auto";
    video.src = fileUrl(f.file); videoFile = f.file;
    video.onerror = () => { player.innerHTML = `<div class="nofile">Can't play ${esc(f.file)}.<br>Open the toolbox with <b>${SP.cmd("open")}</b> so videos can stream.</div>`; };
  }
  player.append(video);
  d.append(player);
  // the scene, zoomed: drag to scrub just this clip (the loop range, with ±1s of context when that's on)
  const strack = h(`<div class="strack" title="Drag to scrub the scene"><div class="strack-rail"><div class="strack-scene"></div><div class="strack-fill"></div></div><div class="strack-thumb"></div></div>`);
  const strackL = h(`<div class="strack-l"></div>`);
  d.append(strack, strackL);
  const tr = h(`<div class="transport">
    <button class="icon-btn sm sq" data-a="play" title="Play / pause (Space)">${icon("pause")}</button>
    <button class="icon-btn sm sq ghost" data-a="back" title="Back one frame (,)">${icon("step-back")}</button><button class="icon-btn sm sq ghost" data-a="fwd" title="Forward one frame (.)">${icon("step-forward")}</button>
    <span class="tc" id="tc"></span><span class="gap"></span>
    <button class="icon-btn sm ghost" data-a="speed" title="Playback speed (click to change)">${video.playbackRate || 1}×</button>
    <button class="icon-btn sm ${context ? "on" : "ghost"}" data-a="ctx" title="Play 1s either side of the scene">±1s</button>
    <button class="icon-btn sm sq ghost" data-a="mute" title="Sound">${icon(video.muted ? "volume-x" : "volume-2")}</button></div>`);
  d.append(tr);
  const bar = h(`<div class="filmbar" title="The whole film: click a scene, drag to scrub"></div>`);
  for (const x of f.scenes) bar.append(h(`<div class="seg-s ${x === s ? "cur" : ""}" style="left:${(x.start / f.duration) * 100}%;width:${((x.end - x.start) / f.duration) * 100}%"></div>`));
  const ph = h(`<div class="ph"></div>`); bar.append(ph);
  bar.dataset.film = f.slug;
  d.append(bar, h(`<div class="filmbar-l"><span>0:00</span><span>${esc(f.scenes.length)} scenes in the film</span><span>${ts(f.duration)}</span></div>`));

  const body = h(`<div class="d-body">
    <h2 class="d-title">${esc(s.title)}</h2>
    <div class="d-film"><a href="#/film/${s.film}">${esc(f.title)}</a><span>·</span>${esc(f.brand)}<span>·</span><span class="mono">${tcCopy(`${ts(s.start)} to ${ts(s.end)}`, stampRange(s.key, s.start, s.end))}</span><span>·</span><span class="stars" title="Steal-worthy">${stars(s.steal)}</span></div>
    <textarea class="inl d-note" id="note" rows="1" title="Your note on this scene. It is saved as you type and goes into the brief you copy" placeholder="Add a note: what to steal, what to change${esc(SP.forBrand())}"></textarea>
    ${(s.moves || []).length ? `<div class="d-sec"><h5>Signature move</h5><p class="lead">${s.moves.map(esc).join(" · ")}</p></div>` : ""}
    <div class="d-sec"><h5>On screen</h5><p class="lead">${esc(s.on_screen)}</p></div>
    <div class="d-sec"><h5>How it moves</h5><p>${esc(s.how_it_moves)}</p></div>
    <div class="d-sec"><h5>Recreate${esc(SP.forBrand())}</h5><p>${esc(s.recreate)}</p></div>
    ${s.palette?.length ? `<div class="d-sec"><h5>Palette</h5><div class="swatches">${s.palette.map((c) => `<span class="sw" data-c="${esc(c)}"><i style="background:${esc(c)}"></i>${esc(c)}</span>`).join("")}</div></div>` : ""}
    <details class="d-more"><summary>${icon("chevron-right")}Details<span>tags, camera, pace, energy</span></summary><div class="tagtable" id="tagtable"></div></details>
    <div class="nav-row">${prev ? `<a href="#/scene/${prev.key}"><small>Previous <kbd>[</kbd></small>${esc(prev.title)}</a>` : "<span></span>"}${next ? `<a class="next" href="#/scene/${next.key}"><small><kbd>]</kbd> Next</small>${esc(next.title)}</a>` : "<span></span>"}</div>
  </div>`);
  d.append(body);
  const tt = $("#tagtable", body);
  for (const [field, label] of [["role", "role"], ["world", "world"], ["subject", "subject"], ["camera", "camera"], ["motion", "motion"], ["transition_in", "transition in"], ["type_treatment", "type"], ["pace", "pace"], ["energy", "energy"], ["sound_sync", "sound sync"], ["production", "production"]]) {
    const vals = [].concat(s[field] ?? []); if (!vals.length) continue;
    const v = h(`<div class="v"></div>`);
    for (const x of vals) {
      const c = h(`<span class="chip" title="${esc(defn(field, x))}">${esc(x)}</span>`);
      c.onclick = () => { ui.filters = {}; ui.q = ""; (ui.filters[field] = new Set()).add(x); location.hash = "#/scenes?" + filtersToQuery(); };
      v.append(c);
    }
    tt.append(h(`<div class="k">${label}</div>`), v);
  }
  body.querySelectorAll(".sw").forEach((sw) => (sw.onclick = () => copy(sw.dataset.c, `Copied ${sw.dataset.c}`)));
  const note = $("#note", body); note.value = rev(s.key).note || "";
  let nt; note.oninput = () => { clearTimeout(nt); nt = setTimeout(() => setRev(s.key, { note: note.value.trim() }), 400); };
  paintReview();

  $('[data-a="close"]', d).onclick = () => closeDetail();
  $('[data-a="id"]', d).onclick = () => copy(s.key, `Copied ${s.key}`);
  $('[data-a="brief"]', d).onclick = () => copy(brief(s), `Brief copied: paste it into ${SP.ai}`);
  const playBtn = $('[data-a="play"]', tr);
  playBtn.onclick = () => (video.paused ? video.play() : video.pause());
  video.onplay = video.onpause = () => (playBtn.innerHTML = icon(video.paused ? "play" : "pause"));
  $('[data-a="back"]', tr).onclick = () => step(-1);
  $('[data-a="fwd"]', tr).onclick = () => step(1);
  $('[data-a="speed"]', tr).onclick = (e) => { const order = [1, 0.5, 0.25], r = order[(order.indexOf(video.playbackRate) + 1) % order.length] || 1; video.playbackRate = r; e.currentTarget.textContent = `${r}×`; e.currentTarget.classList.toggle("on", r !== 1); e.currentTarget.classList.toggle("ghost", r === 1); };
  $('[data-a="ctx"]', tr).onclick = () => { context = !context; renderDetail(s); };
  paintMomentPins();
  $('[data-a="mute"]', tr).onclick = (e) => { video.muted = !video.muted; e.currentTarget.innerHTML = icon(video.muted ? "volume-x" : "volume-2"); };

  loopRange = context ? [Math.max(0, s.start - 1), Math.min(f.duration, s.end + 1)] : [s.start, s.end];
  const L = () => loopRange[1] - loopRange[0];
  $(".strack-scene", strack).style.cssText = `left:${((s.start - loopRange[0]) / L()) * 100}%;width:${((s.end - s.start) / L()) * 100}%`;
  strackL.innerHTML = `${tcCopy(tsf(loopRange[0]), stampAt(s.key, loopRange[0], fps, s.start))}<span>${context ? "scene ±1s" : "scene"} · ${(s.end - s.start).toFixed(2)}s</span>${tcCopy(tsf(loopRange[1]), stampAt(s.key, loopRange[1], fps, s.start))}`;
  let wasPlaying = false;
  const grab = () => { scrubbing = true; wasPlaying = !video.paused; video.pause(); };
  const release = () => { scrubbing = false; if (wasPlaying) video.play().catch(() => {}); };
  scrubber(strack, {
    duration: L,
    seek: (k) => { try { video.currentTime = loopRange[0] + k; } catch {} },
    label: (k) => `${tsf(loopRange[0] + k)} · f${Math.round((loopRange[0] + k) * fps)}`,
    copyAt: (k) => stampAt(s.key, loopRange[0] + k, fps, s.start),
    onStart: grab, onEnd: release,
  });
  scrubber(bar, {
    duration: () => f.duration,
    seek: (t) => { try { video.currentTime = t; } catch {} },
    label: (t) => { const x = sceneAt(f, t), m = momentNear(f.slug, t, f.duration); return `${tsf(t)}${x ? ` · ${x.id} ${x.title}` : ""}${m ? ` · moment${m.note ? ": " + m.note : ""}` : ""}`; },
    copyAt: (t) => { const x = sceneAt(f, t) || s; return stampAt(x.key, t, fps, x.start); },
    onStart: grab,
    onEnd: (t, moved) => {
      scrubbing = false;
      const x = sceneAt(f, t);
      if (moved && x && x !== s && (t < loopRange[0] || t > loopRange[1])) { pendingStart = t; location.hash = `#/scene/${x.key}`; return; }
      if (moved) release();
    },
    onClick: (t) => {
      const x = sceneAt(f, t);
      if (x && x !== s) { location.hash = `#/scene/${x.key}`; return; }
      try { video.currentTime = t; } catch {} video.play().catch(() => {});
    },
  });
  const t0 = pendingStart != null && pendingStart >= loopRange[0] && pendingStart <= loopRange[1] ? pendingStart : loopRange[0] + 0.01;
  const hold = holdStart && pendingStart != null;
  pendingStart = null; holdStart = false;
  const start = () => { try { video.currentTime = t0; } catch {} if (hold) video.pause(); else video.play().catch(() => {}); };
  if (video.readyState >= 1) start(); else video.addEventListener("loadedmetadata", start, { once: true });
  cancelAnimationFrame(rafId);
  const tc = $("#tc", tr), fill = $(".strack-fill", strack), thumbEl = $(".strack-thumb", strack);
  tc.classList.add("tc-copy"); tc.title = "Click to copy the time with the scene ID (T)";
  const tick = () => {
    if (!scrubbing && (video.currentTime >= loopRange[1] - 0.03 || video.currentTime < loopRange[0] - 0.25)) { try { video.currentTime = loopRange[0]; } catch {} }
    const t = video.currentTime, k = clampN((t - loopRange[0]) / L(), 0, 1) * 100;
    tc.textContent = `${tsf(t)}  f${Math.round(t * fps)}`;
    const here = sceneAt(f, t) || s;
    tc.dataset.copy = stampAt(here.key, t, fps, here.start);
    ph.style.left = `${(t / f.duration) * 100}%`;
    fill.style.width = `${k}%`; thumbEl.style.left = `${k}%`;
    rafId = requestAnimationFrame(tick);
  };
  rafId = requestAnimationFrame(tick);
  function step(dir) { video.pause(); video.currentTime = Math.min(loopRange[1] - 0.001, Math.max(loopRange[0], video.currentTime + dir / fps)); }
  d.scrollTop = 0;
}
/* the scene's actions, as a quiet icon row in the sheet's top bar: favourite, save moment, board */
function paintReview() {
  const box = $("#review"); if (!box || !detailKey) return;
  const r = rev(detailKey), key = detailKey, s = BY_KEY[key], f = FILMS[s.film];
  const onBoard = board().items.some((i) => i.id === key);
  box.innerHTML = `<button class="icon-btn sm sq ghost ${r.fav ? "fav-on" : ""}" data-a="fav" title="${r.fav ? "Favourite: click to remove" : "Favourite"} (F)">${icon("heart")}</button>
    ${s.upload ? "" : `<button class="icon-btn sm sq ghost ${r.note ? "note-on" : ""}" data-a="note" title="${r.note ? "Your note: click to edit" : "Write a note on this scene"} (${esc(KB.get("sceneNote").map(KB.label).join(" or "))})">${icon(r.note ? "message-square" : "message-square-plus")}</button>
    <button class="icon-btn sm sq ghost" data-a="moment" title="Save the frame you're on as a moment (K)">${icon("bookmark-plus")}</button>`}
    <button class="icon-btn sm sq ghost ${onBoard ? "board-on" : ""}" data-a="board" title="${onBoard ? `On ${esc(current)}: click to remove` : `Add to ${esc(current)}`} (B)">${icon(onBoard ? "check" : "plus")}</button>`;
  $('[data-a="fav"]', box).onclick = () => setRev(key, { fav: !r.fav });
  if (!s.upload) $('[data-a="moment"]', box).onclick = (e) => saveMoment(f, video ? video.currentTime : s.start, e.currentTarget);
  if (!s.upload) $('[data-a="note"]', box).onclick = focusNote;
}
// the scene's own note (an upload's "What to take from it"): bring it into view and put the caret at its end
function focusNote() {
  const n = $("#detail #note") || $('#detail [data-k="note"]'); if (!n) return;
  n.scrollIntoView({ block: "nearest" }); n.focus(); n.setSelectionRange(n.value.length, n.value.length);
  $('[data-a="board"]', box).onclick = () => (onBoard ? removeFromBoard(key) : addToBoard(key));
}

/* ---------- boards ---------- */
// A board is a script: a brief (news, audience, aspect, target length, notes), a motion profile, and beats.
// Each beat borrows a scene (reference or system move) and carries its beat name, the on-screen copy or line,
// its length in seconds (which drives the running timecode) and a note.
const PROFILES = SPLICED.profiles;   // name -> one line: the project's own (spliced.json) and the kit's
const BRIEF = [["news", "The news, in one sentence"], ["audience", "Who it's for"], ["aspect", "16:9"], ["length", "Target seconds"], ["notes", "Anything else: tone, must-haves, must-nots"]];
function addToBoard(key) {
  const b = board();
  if (b.items.some((i) => i.id === key)) { toast(`Already on ${current}`); return; }
  const it = { uid: uid(), id: key, beat: "", copy: "", note: "" };
  b.items.push(it);
  send([{ op: "item.add", board: current, id: key, uid: it.uid }]);
  ui.flash.add(it.uid); setTimeout(() => ui.flash.delete(it.uid), 2200);
  renderTray(); refreshBadges(key); peekTray();
  toast(`Added to ${current} · beat ${b.items.length}`, 2600, [{ label: "Undo", run: () => removeFromBoard(it.uid) }, { label: "Open", run: () => (location.hash = `#/boards/${encodeURIComponent(current)}`) }]);
  boardsRefresh();
}
function removeFromBoard(keyOrUid) {
  const b = board();
  const it = b.items.find((i) => i.uid === keyOrUid) || b.items.find((i) => i.id === keyOrUid);
  if (!it) return;
  b.items = b.items.filter((i) => i !== it);
  send([{ op: "item.remove", board: current, uid: it.uid }]);
  renderTray(); refreshBadges(it.id);
  boardsRefresh();
}
function moveItem(uidv, to) {
  const b = board(), i = b.items.findIndex((x) => x.uid === uidv);
  if (i < 0 || to < 1 || to > b.items.length) return;
  b.items.splice(to - 1, 0, b.items.splice(i, 1)[0]);
  send([{ op: "item.move", board: current, uid: uidv, to }]);
  renderTray(); boardsRefresh();
}
const timers = {};
function debounced(key, fn, ms = 450) { clearTimeout(timers[key]); timers[key] = setTimeout(fn, ms); }
function updateItem(it, patch) {
  Object.assign(it, patch);
  const boardName = current;
  debounced(`item:${it.uid}:${Object.keys(patch).join()}`, () => send([{ op: "item.update", board: boardName, uid: it.uid, patch }]));
}
function setCurrent(name) {
  current = name; localStorage.setItem("cr.board", name);
  renderTray(); if (onBoardPage()) { history.replaceState(null, "", `#/boards/${encodeURIComponent(name)}`); renderBoards(); } else boardsRefresh();
  if (detailKey) paintReview();
  document.querySelectorAll(".card").forEach((el) => paintBadges(el, el.dataset.key));
}
function newBoard() {
  const name = prompt("Name the board (e.g. 'Areas launch v1')");
  if (!name) return;
  if (state.boards[name]) { toast("A board with that name exists"); return; }
  state.boards[name] = normalise({ boards: { x: { created: new Date().toISOString().slice(0, 10) } } }).boards.x;
  const folder = window.Folders && !["", "-"].includes(Folders.filter()) ? Folders.filter() : "";   // made while looking at a folder: it goes there
  if (folder) state.boards[name].folder = folder;
  send([{ op: "board.create", name, ...(folder ? { folder } : {}) }]); setCurrent(name);
}
const secs = (b) => b.items.reduce((a, it) => a + (+it.seconds || 0), 0);
const hasT = (it) => it.t != null && it.t !== "";
function boardMarkdown(name) {
  const b = state.boards[name], br = b.brief || {};
  const items = b.items.map((it) => ({ ...it, s: BY_KEY[it.id] })).filter((x) => x.s);
  let t = 0;
  const rows = items.map((x, i) => {
    const span = x.seconds ? `${ts(t)}–${ts(t + +x.seconds)}` : ts(t); t += +x.seconds || 0;
    return `| ${i + 1} | ${span} | ${x.beat || ""} | \`${x.id}\`${hasT(x) ? ` @ ${tsf(+x.t)}` : ""} ${x.s.title} | ${(x.copy || "").replace(/\n/g, " ")} | ${(x.vo || "").replace(/\n/g, " ")} | ${(x.note || "").replace(/\n/g, " ")} |`;
  });
  return [
    `# Board: ${name}`, "",
    `${items.length} beats · ${secs(b).toFixed(1)}s scripted${br.length ? ` of ${br.length}s` : ""}${br.aspect ? ` · ${br.aspect}` : ""} · motion profile \`${b.profile || SPLICED.default_profile}\``, "",
    ...BRIEF.filter(([k]) => br[k] && k !== "length" && k !== "aspect").map(([k]) => `**${k[0].toUpperCase() + k.slice(1)}:** ${br[k]}`), "",
    "| # | Time | Beat | Scene | On screen | Voice-over | Note |", "| --- | --- | --- | --- | --- | --- | --- |", ...rows,
    "", ...items.flatMap((x, i) => [`## ${i + 1}. ${x.beat || "Beat " + (i + 1)}`, "", hasT(x) ? `**Moment:** \`${stampAt(x.id, +x.t, FILMS[x.s.film].fps || 30, x.s.start)}\`: borrow this exact frame\n` : "", x.copy ? `**On screen:** ${x.copy}\n` : "", x.vo ? `**Voice-over:** ${x.vo}\n` : "", x.note ? `**Our note:** ${x.note}\n` : "", brief(x.s, true), ""]),
  ].join("\n");
}
function buildPrompt(name) {
  const b = state.boards[name];
  const profile = b.profile || SPLICED.default_profile;
  return [
    `/make-film Build a ${SPLICED.brand ? SPLICED.brand + " " : ""}video from the board "${name}" below, in remotion/.`,
    `Motion profile: \`${profile}\` (${PROFILES[profile]}). All motion goes through motion('${profile}') from remotion/src/lib/motion (remotion/docs/MOTION-SYSTEMS.md); run npm run check:motion before review.`,
    `The board is the script: use each beat's copy and length as written (lengths may be rounded to the beat grid). Keep one house style (${SPLICED.brand ? SPLICED.brand + "'s" : "the"} brand, one world, palette, type and motion language) and recreate each referenced scene's choreography inside it: borrow the move, not the brand. Scenes from system-moves are our own kit's moves: use the code in their Recreate field. Use ${SPLICED.brand ? "real " + SPLICED.brand : "the real"} UI rebuilt in code. Where a scene needs footage or photos, look for real footage first (${SP.cmd("stock")} search), then propose a generated clip or still for what real footage can't give.`,
    `The board lives in Spliced; read or edit it with: ${SP.cmd("board")} show "${name}"`,
    `Start the film with \`${SP.cmd("film")} new <slug> --board "${name}"\` unless it's already started (the Boards view's "start film" does the same): it writes remotion/src/films/<slug>/storyboard.json, the beat-by-beat plan that Spliced's Build view pairs with every render, and a cues.json seeded from these scenes. Keep each beat's status and notes there as you build (\`${SP.cmd("film")} mark\`).`,
    "Read each scene's section in its breakdown before building that beat. Where a beat names a moment (`film/sNN @ 0:42.51`), that exact frame is what the person means: look at it first.", "", boardMarkdown(name),
  ].join("\n");
}
/* A whole reference film as one prompt: recreate it as closely as possible, scene by scene, in its own look rather
   the project's (the make-film skill's "A study of one film"). The board and film it asks for pair every beat with
   its scene in Build. */
function filmBrief(slug) {
  const f = FILMS[slug], sig = f.style_signature || {}, board = `Study: ${f.title}`, film = `${slug}-study`;
  const tempo = f.tempo ? [[f.tempo.bpm && `${Math.round(f.tempo.bpm)} bpm`, f.tempo.avg_shot_s && `a cut every ${f.tempo.avg_shot_s}s on average`].filter(Boolean).join(", "), f.tempo.notes].filter(Boolean).join(". ") : "";
  return [
    `/make-film Recreate the reference film "${f.title}" (${f.brand}) as closely as you can, in remotion/.`,
    `Match it scene by scene: the same scenes in the same order, each the same length, with the same framing, layout, type, palette, copy, motion, cuts and pacing. This is a study of the film: don't move it into the project's house style, brand or motion profile, and don't add what it doesn't have. Follow "A study of one film" in the make-film skill.`,
    `Set it up so Spliced pairs every beat with its scene: ${SP.cmd("board")} new "${board}" --from-film ${slug}, then ${SP.cmd("film")} new ${film} --board "${board}" (skip whichever already exists). Build then plays each beat beside the scene it recreates; compare them with ${SP.cmd("film")} sheet ${film} --beat <id> and fix what differs before marking a beat review.`,
    `The reference: ${f.file}, ${ts(f.duration)}, ${f.format || ""}${f.fps ? `, ${f.fps} fps` : ""}. Its breakdown: library/references/${slug}/breakdown.md. Each scene's frames: library/references/${slug}/scenes/<id>.jpg. Look at a scene's frames before building it.`,
    "", `# Film: ${f.title}`, "",
    f.summary || "",
    "", sig.palette?.length ? `**Palette:** ${sig.palette.map((p) => `${p.hex}${p.name ? ` (${p.name})` : ""}`).join(", ")}` : "",
    ...Object.entries(sig).filter(([k]) => k !== "palette").map(([k, v]) => `**${k[0].toUpperCase() + k.slice(1).replace(/_/g, " ")}:** ${typeof v === "string" ? v : JSON.stringify(v)}`),
    tempo ? `**Tempo:** ${tempo}` : "", f.structure ? `**Structure:** ${f.structure}` : "",
    ...(f.signature_moves?.length ? ["", "## Signature moves", "", ...f.signature_moves.map((m) => `- **${m.name}** (${(m.scenes || []).join(", ")}): ${m.description}${m.recreate ? ` Recreate: ${m.recreate}` : ""}`)] : []),
    "", `## Scenes (${f.scenes.length})`, "", ...f.scenes.flatMap((s) => [brief(s, true), ""]),
  ].filter((x, i, a) => x !== "" || a[i - 1] !== "").join("\n");
}
async function startFilm(name) {
  if (!server) { toast(`Run ${SP.cmd("open")} to start a film`); return; }
  const b = state.boards[name];
  if (!b.items.length) { toast("The board is empty"); return; }
  const slug = prompt("Film slug: its folder in remotion/src/films/ (feature-what, e.g. search-launch)", name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""));
  if (!slug) return;
  try {
    const r = await fetch("/api/productions", { method: "POST", body: JSON.stringify({ slug, board: name, items: b.items, profile: b.profile || SPLICED.default_profile }) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error);
    toast(`Started ${j.dir}`); location.hash = `#/build/${j.slug}`;
  } catch (e) { toast(`Couldn't start it: ${e.message}`); }
}
function download(name, text, type = "text/markdown") {
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function dragList(container, itemSel, getItems) {
  let from = null;
  container.querySelectorAll(itemSel).forEach((el, i) => {
    el.draggable = true;
    el.ondragstart = (e) => { if (/input|textarea/i.test(e.target.tagName)) return; from = i; el.classList.add("drag"); e.dataTransfer.effectAllowed = "move"; };
    el.ondragend = () => { el.classList.remove("drag"); container.querySelectorAll(".over").forEach((x) => x.classList.remove("over")); };
    el.ondragover = (e) => { e.preventDefault(); el.classList.add("over"); };
    el.ondragleave = () => el.classList.remove("over");
    el.ondrop = (e) => { e.preventDefault(); if (from === null || from === i) return; const it = getItems()[from]; from = null; moveItem(it.uid, i + 1); };
  });
}
/* ---------- the tray: the current board, on demand ----------
   No permanent strip: a pill at the bottom of the sidebar names the current board; it opens the tray as a panel
   that slides up from the bottom (and peeks open for a moment after "Add to board"). */
function setTray(open) {
  ui.trayOpen = open; clearTimeout(peekT); peeking = false;
  document.body.classList.toggle("tray-open", open);
  $("#tray").setAttribute("aria-hidden", open ? "false" : "true");
  paintPill();
}
let peekT = 0, peeking = false;
function peekTray() {
  if (ui.trayOpen || document.body.classList.contains("no-tray")) return;
  setTray(true); peeking = true;
  const t = $("#tray");
  const later = () => { peekT = setTimeout(() => { if (peeking && !t.matches(":hover")) setTray(false); else if (peeking) later(); }, 2400); };
  later();
}
function paintPill() {
  const p = $("#board-pill"); if (!p) return;
  const b = board();
  p.innerHTML = `${icon("layout-list")}<span class="nm">${esc(current || "No board")}</span><span class="c">${b.items.length}</span>${icon(ui.trayOpen ? "chevron-down" : "chevron-right")}`;
  p.classList.toggle("on", ui.trayOpen);
  p.title = document.body.classList.contains("no-tray") ? `Open the board ${current}` : `${ui.trayOpen ? "Hide" : "Show"} the board ${current}`;
}
function renderTray() {
  const tray = $("#tray"); tray.innerHTML = "";
  paintPill();
  const names = Object.keys(state.boards);
  const b = board();
  const head = h(`<div class="tray-head">
    <button class="tray-name" title="Switch board">${esc(current)}${icon("chevrons-up-down")}</button><span class="meta">${b.items.length} beats · ${secs(b).toFixed(0)}s</span>
    <span class="gap"></span>
    <button class="icon-btn sm ghost" data-a="md" title="Copy the board as a plan">${icon("copy")}Copy plan</button>
    <a class="icon-btn sm ghost" href="#/boards/${encodeURIComponent(current)}">Open board</a>
    <button class="icon-btn sm sq ghost" data-a="x" title="Hide (Esc)">${icon("x")}</button></div>`);
  $(".tray-name", head).onclick = (e) => menu(e.currentTarget, [...names.map((n) => ({ value: n, html: `<span class="lbl">${esc(n)}</span><span class="c">${state.boards[n].items.length}</span>`, on: n === current })), { value: "__new", sep: true, html: `${icon("plus")}<span class="lbl">New board</span>` }], (v) => (v === "__new" ? newBoard() : setCurrent(v)));
  $('[data-a="md"]', head).onclick = () => copy(boardMarkdown(current), "Board plan copied");
  $('[data-a="x"]', head).onclick = () => setTray(false);
  $("a", head).onclick = () => setTray(false);
  const items = h(`<div class="tray-items"></div>`);
  if (!b.items.length) items.append(h(`<div class="tray-empty">Empty. Hover a scene and press <b>+</b>, press <kbd>B</kbd> while a scene is open, or ask ${SP.ai} to build the board.</div>`));
  b.items.forEach((it, i) => {
    const s = BY_KEY[it.id]; if (!s) return;
    const el = h(`<div class="t-item ${ui.flash.has(it.uid) ? "flash" : ""}" title="${esc(it.id + "  " + s.title)} (drag to reorder)"><span class="n">${i + 1}</span><button class="x" title="Remove">${icon("x")}</button><div class="beat">${esc(it.beat || s.title)}${it.seconds ? ` · ${it.seconds}s` : ""}</div></div>`);
    const th = thumb(s); el.insertBefore(th, $(".beat", el));
    th.onclick = () => (location.hash = `#/scene/${s.key}`);
    $(".x", el).onclick = () => removeFromBoard(it.uid);
    items.append(el);
  });
  dragList(items, ".t-item", () => board().items);
  tray.append(head, items);
  if (ui.flash.size) requestAnimationFrame(() => tray.querySelector(".t-item.flash")?.scrollIntoView({ inline: "nearest", block: "nearest" }));
}
/* A board that became a film shows the film's script (build.js), so there's one script, not two that drift apart.
   The board's own beats, as they were when the film started, fold away underneath. */
async function filmScript(f) {
  const main = $("#main"), sb = $(".sb", main);
  if (!sb || main.querySelector(".board-film")) return;
  const banner = h(`<div class="board-film">${icon("list-video")}<div>This board became the film <b>${esc(f.title)}</b> (${f.beats.length} beats). Its script lives in the film now: edits here save to the film. The board as it was is folded away below.</div><span class="spacer"></span><a class="icon-btn sm" href="#/build/${esc(f.slug)}/script">${icon("scroll-text")}Open in Build</a></div>`);
  const box = h(`<div class="board-script"></div>`);
  const was = h(`<details class="board-was"><summary>The board as it was: ${board().items.length} beats</summary></details>`);
  sb.before(banner, box, was); was.append(sb);
  await build.scriptFor(box, f.slug);
}
/* board actions, shared by the ⋯ menu and the command palette */
const boardActs = {
  plan: () => copy(boardMarkdown(current), "Board plan copied"),
  md: () => download(`board-${current.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.md`, boardMarkdown(current)),
  prompt: () => copy(buildPrompt(current), `Build prompt copied: paste it into ${SP.ai}`),
  film: () => (boardFilm ? (location.hash = `#/build/${boardFilm.slug}`) : startFilm(current)),
  rename: () => {
    const n = prompt("New name", current); if (!n || n === current) return;
    if (state.boards[n]) { toast("That name is taken"); return; }
    const old = current; state.boards[n] = state.boards[old]; delete state.boards[old];
    send([{ op: "board.rename", name: old, to: n }]); setCurrent(n);
  },
  del: () => {
    if (!confirm(`Delete the board "${current}"? Its scenes stay in the library.`)) return;
    const old = current; delete state.boards[old];
    send([{ op: "board.delete", name: old }]).then(() => { if (!Object.keys(state.boards).length) loadState().then(() => setCurrent(Object.keys(state.boards)[0])); });
    if (Object.keys(state.boards).length) setCurrent(latestBoard() || Object.keys(state.boards)[0]);
  },
  newb: () => newBoard(),
  exp: () => download("cutting-room-state.json", JSON.stringify(state, null, 1), "application/json"),
  imp: () => {
    const inp = h(`<input type="file" accept=".json">`);
    inp.onchange = async () => {
      try {
        const j = JSON.parse(await inp.files[0].text());
        const ops = Object.entries(j.reviews || {}).map(([key, patch]) => ({ op: "review.set", key, patch }));
        for (const [n, bd] of Object.entries(j.boards || {})) ops.push({ op: "board.create", name: state.boards[n] ? n + " (imported)" : n, profile: bd.profile, brief: bd.brief, items: bd.items });
        if (server) { await send(ops); await pull(); } else { Object.assign(state.reviews, j.reviews || {}); for (const op of ops) if (op.op === "board.create") state.boards[op.name] = normalise({ boards: { x: { ...op } } }).boards.x; send([]); render(); renderTray(); }
        toast("Imported");
      } catch { toast("That file isn't an export"); }
    };
    inp.click();
  },
};
let boardFilm = null; // the film this board became, if any (set when the productions list comes back)
function boardMenu(anchor) {
  menu(anchor, [
    { value: "plan", html: `${icon("copy")}<span class="lbl">Copy plan</span>` },
    { value: "md", html: `${icon("download")}<span class="lbl">Download as .md</span>` },
    { value: "film", html: `${icon("list-video")}<span class="lbl">${boardFilm ? `Open film: ${esc(boardFilm.slug)}` : "Start a film from this board"}</span>` },
    { value: "folder", html: `${icon("folder")}<span class="lbl">Move to folder…</span><span class="c">${esc(Folders.name(state.boards[current]?.folder))}</span>` },
    { value: "rename", sep: true, html: `${icon("pencil")}<span class="lbl">Rename</span>` },
    { value: "newb", html: `${icon("plus")}<span class="lbl">New board</span>` },
    { value: "exp", sep: true, html: `${icon("download")}<span class="lbl">Export all boards and reviews</span>` },
    { value: "imp", html: `${icon("upload")}<span class="lbl">Import from an export</span>` },
    { value: "del", sep: true, danger: true, html: `${icon("trash-2")}<span class="lbl">Delete board</span>` },
  ], (v) => (v === "folder" ? boardFolderMenu(anchor) : boardActs[v]()));
}
/* a board in one of the project's folders: Boards groups by it, and a film started from the board goes there too */
function boardFolderMenu(anchor) {
  const was = state.boards[current]?.folder || "";
  menu(anchor, Folders.items(was, icon), async (v) => {
    const to = await Folders.pick(v);
    if ((v === "+" && !to) || to === was || !state.boards[current]) return;
    if (to) state.boards[current].folder = to; else delete state.boards[current].folder;
    send([{ op: "board.set", name: current, folder: to }]);
    toast(to ? `${current} is in ${Folders.name(to)}` : `${current} is in no folder`);
    renderBoards();
  });
}
/* ---------- all boards: a grid to browse; a board opens into its script (renderBoards) ---------- */
const onBoardPage = () => $("#main").dataset.view === "boards" && /^#\/boards\/./.test(location.hash);
function boardsRefresh() { if ($("#main").dataset.view !== "boards") return; onBoardPage() ? renderBoards() : renderBoardGrid(); }
let boardFilms = null; // films started from boards (for their posters), fetched once per visit
function renderBoardGrid() {
  const main = $("#main"); main.innerHTML = "";
  const names = Object.keys(state.boards).sort((a, b) => String(state.boards[b].updated || "").localeCompare(String(state.boards[a].updated || "")));
  const head = h(`<div class="view-head"><h1>Boards</h1><span class="meta">${names.length} board${names.length === 1 ? "" : "s"}${server ? "" : " · saved in this browser"}</span><span class="spacer"></span>
    <button class="icon-btn sm primary" data-a="new">${icon("plus")}New board</button></div>`);
  main.append(head);
  $('[data-a="new"]', head).onclick = () => { const before = new Set(Object.keys(state.boards)); newBoard(); const n = Object.keys(state.boards).find((x) => !before.has(x)); if (n) location.hash = `#/boards/${encodeURIComponent(n)}`; };
  // with folders: a group per folder, the filter shared with Build and Assets
  const byFolder = window.Folders?.any(), folderOf = (n) => state.boards[n].folder || "";
  if (byFolder) main.append(Folders.chips(() => renderBoardGrid(), Folders.count(names, folderOf)));
  const sets = byFolder ? Folders.groups(names, folderOf).filter((g) => g.items.length || Folders.filter() !== "") : [{ items: names }];
  const grid = h(`<div class="bgrid"></div>`);   // (the first group's grid; each group gets its own below)
  const ago = (iso) => { if (!iso) return ""; const d = (Date.now() - new Date(iso).getTime()) / 1000; return d < 3600 ? `${Math.max(1, Math.floor(d / 60))}m ago` : d < 86400 ? `${Math.floor(d / 3600)}h ago` : `${Math.floor(d / 86400)}d ago`; };
  const grids = sets.map((g, gi) => {
    if (byFolder) main.append(h(`<h2 class="bx-group" title="${esc(g.folder ? `${g.folder}/` : "Boards in no folder")}">${esc(g.name)}<span>${g.items.length}</span></h2>`));
    const gr = gi ? h(`<div class="bgrid"></div>`) : grid;
    if (byFolder && !g.items.length) main.append(h(`<div class="empty">No board in ${esc(g.name)} yet. Press <b>New board</b> while this folder is picked, or move one here from its menu.</div>`));
    else main.append(gr);
    return [g, gr];
  });
  grids.forEach(([g, gr]) => g.items.forEach((n, i) => {
    const grid = gr;
    const b = state.boards[n], br = b.brief || {}, items = b.items.filter((it) => BY_KEY[it.id]);
    const el = h(`<a class="bcard" href="#/boards/${encodeURIComponent(n)}" data-name="${esc(n)}" style="animation-delay:${Math.min(i, 20) * 30}ms" data-search="${esc([n, br.news, br.audience, br.notes, b.profile, ...b.items.map((it) => `${it.id} ${it.beat} ${it.copy} ${it.vo} ${it.note} ${BY_KEY[it.id]?.title || ""}`)].join(" "))}">
      <div class="bcover ${items.length ? "" : "empty"}">${items.length ? "" : `<span>${icon("layout-list")}Empty board</span>`}</div>
      <div class="bbody"><div class="btitle"><b>${esc(n)}</b>${n === current ? `<span class="bcur" title="The board the tray adds to">current</span>` : ""}</div>
        ${br.news ? `<p>${esc(br.news)}</p>` : `<p class="dim">No brief yet</p>`}
        <div class="bmeta"><span>${b.items.length} beat${b.items.length === 1 ? "" : "s"}</span>${secs(b) ? `<span>${secs(b).toFixed(0)}s${br.length ? ` of ${br.length}s` : ""}</span>` : ""}<span>${esc(b.profile || SPLICED.default_profile)}</span><span class="bfilm"></span><span class="spacer"></span><span>${ago(b.updated)}</span></div></div></a>`);
    // the cover: the first beats' scenes as a mosaic (a film's poster once the board became a film)
    const cov = $(".bcover", el);
    items.slice(0, 4).forEach((it) => { const t = thumb(BY_KEY[it.id], { scrub: false }); cov.append(t); });
    cov.classList.add(`n${Math.min(4, items.length)}`);
    grid.append(el);
  }));
  ViewSearch.attach(head, "boards", { placeholder: "Search boards", cards: ".bgrid .bcard",
    count: (n, total, q) => ($(".meta", head).textContent = q ? `${n} of ${total} boards` : `${total} board${total === 1 ? "" : "s"}${server ? "" : " · saved in this browser"}`) });
  if (!names.length) main.append(h(`<div class="empty">No boards yet. A ${SP.term("board")} is your film's script: the ${SP.term("scene", "scenes")} you borrow, each with its words and its length. Press <b>New board</b>, or ask ${SP.ai} to put one together.</div>`));
  const paintFilms = (list) => {
    for (const f of list.filter((p) => p.board && p.latest)) {
      const card = main.querySelector(`.bcard[data-name="${CSS.escape(f.board)}"]`); if (!card) continue;
      const fl = $(".bfilm", card); fl.innerHTML = `${icon("list-video")}${esc(f.slug)}`; fl.title = `Became the film ${f.title}: open it in Build`;
      fl.onclick = (e) => { e.preventDefault(); e.stopPropagation(); location.hash = `#/build/${f.slug}`; };
      const t = f.full || f.latest, mid = (f.duration || 2) * 0.33;
      const cov = $(".bcover", card); cov.className = "bcover film";
      cov.innerHTML = `<img alt="" loading="lazy" src="/api/frame?file=${encodeURIComponent(t.file)}&t=${mid.toFixed(2)}&w=720&v=${Math.round(t.mtime || 0)}">`;
    }
  };
  if (boardFilms) paintFilms(boardFilms);
  if (server) fetch("/api/productions").then((r) => r.json()).then((list) => { boardFilms = list; if (!onBoardPage() && $("#main").dataset.view === "boards") paintFilms(list); }).catch(() => {});
}
function renderBoards(name) {
  if (name && state.boards[name] && name !== current) { current = name; localStorage.setItem("cr.board", name); renderTray(); }
  const main = $("#main"); main.innerHTML = "";
  const b = board(), br = b.brief || {};
  const total = secs(b), target = +br.length || 0;
  boardFilm = null;
  const head = h(`<div class="view-head"><h1><a class="crumb" href="#/boards" title="All boards">Boards</a><span class="sep">/</span><button class="board-switch" title="Switch board">${esc(current)}${icon("chevrons-up-down")}</button></h1><span class="meta">${b.items.length} beats · ${total.toFixed(1)}s${target ? ` of ${target}s` : ""}${b.folder ? ` · in ${esc(Folders.name(b.folder))}` : ""}${server ? "" : " · saved in this browser"}</span><span class="spacer"></span>
    <button class="icon-btn sm primary" data-a="prompt" title="A prompt that builds this board in Remotion">${icon("copy")}Copy build prompt</button>
    <button class="icon-btn sm sq ghost" data-a="more" title="More: plan, film, rename, export…">${icon("ellipsis")}</button></div>`);
  main.append(head);
  $('[data-a="prompt"]', head).onclick = boardActs.prompt;
  $('[data-a="more"]', head).onclick = (e) => boardMenu(e.currentTarget);
  $(".board-switch", head).onclick = (e) => menu(e.currentTarget, [...Object.keys(state.boards).map((n) => ({ value: n, html: `<span class="lbl">${esc(n)}</span><span class="c">${state.boards[n].items.length}</span>`, on: n === current })), { value: "__new", sep: true, html: `${icon("plus")}<span class="lbl">New board</span>` }], (v) => (v === "__new" ? newBoard() : setCurrent(v)));
  if (server) fetch("/api/productions").then((r) => r.json()).then((list) => {
    const f = list.find((p) => p.engine === "remotion" && p.board === current);
    if (f && $("#main").dataset.view === "boards") { boardFilm = f; filmScript(f); }
  }).catch(() => {});

  // The brief: a calm summary; "Edit brief" opens the form (open by default while the board has no news yet)
  const open = ui.briefOpen || !br.news;
  const prof = b.profile || SPLICED.default_profile;
  const bp = h(`<div class="brief-sum ${open ? "open" : ""}">
    <p class="news ${br.news ? "" : "dim"}">${esc(br.news || "No brief yet: what's the news, in one sentence?")}</p>
    ${br.audience ? `<p class="aud" title="Audience">${esc(br.audience)}</p>` : ""}
    <div class="facts">${[br.aspect && esc(br.aspect), target && `${target}s`, `profile <b>${esc(prof)}</b>`].filter(Boolean).map((x) => `<span>${x}</span>`).join("")}
      ${target ? `<span class="lenbar" title="${total.toFixed(1)}s scripted of ${target}s"><i style="width:${Math.min(100, (total / target) * 100)}%" class="${total > target * 1.05 ? "over" : ""}"></i></span>` : ""}
      <button class="icon-btn sm ghost" data-a="edit">${icon(open ? "chevron-down" : "pencil")}${open ? "Done" : "Edit brief"}</button></div>
    <div class="brief">
      <div class="brief-grid">${BRIEF.map(([k, ph]) => `<label class="${k}"><span>${k}</span>${k === "news" || k === "notes" ? `<textarea rows="2" data-k="${k}" placeholder="${esc(ph)}">${esc(br[k] ?? "")}</textarea>` : `<input data-k="${k}" ${k === "length" ? 'type="number" min="0" step="1"' : ""} placeholder="${esc(ph)}" value="${esc(br[k] ?? "")}">`}</label>`).join("")}</div>
      <div class="brief-side"><span class="meta">Motion profile</span>
        <div class="seg" id="profile">${Object.keys(PROFILES).map((p) => `<button data-v="${p}" class="${prof === p ? "on" : ""}" title="${esc(PROFILES[p])}">${p}</button>`).join("")}</div>
        <span class="meta">${esc(PROFILES[prof])}. Compare in <a href="#/film/system-moves">Systems</a> and remotion/docs/media/motion-profiles.mp4</span>
      </div></div></div>`);
  $('[data-a="edit"]', bp).onclick = () => { ui.briefOpen = !open; renderBoards(); };
  bp.querySelectorAll("[data-k]").forEach((el) => (el.oninput = () => {
    const k = el.dataset.k, v = k === "length" ? (el.value === "" ? "" : +el.value) : el.value;
    br[k] = v; b.brief = br;
    debounced(`brief:${k}`, () => send([{ op: "board.set", name: current, brief: { [k]: v } }]));
  }));
  bp.querySelectorAll("#profile button").forEach((btn) => (btn.onclick = () => { b.profile = btn.dataset.v; send([{ op: "board.set", name: current, profile: btn.dataset.v }]); renderBoards(); }));
  main.append(bp);

  if (!b.items.length) { main.append(h(`<div class="empty">No beats yet. Browse <a href="#/scenes"><b>Library</b></a> or <a href="#/film/system-moves"><b>Systems</b></a> and press <b>+</b> on a scene to borrow it as a ${SP.term("beat")}, or ask ${SP.ai} to put the board together.</div>`)); }
  const sb = h(`<div class="sb"></div>`);
  let t = 0;
  b.items.forEach((it, i) => {
    const s = BY_KEY[it.id];
    const t0 = t; t += +it.seconds || 0;
    if (!s) { sb.append(h(`<div class="sb-item"><span class="sb-n">${i + 1}</span><div class="sb-th"></div><div class="sb-main">Missing scene ${esc(it.id)}</div></div>`)); return; }
    const el = h(`<div class="sb-item ${ui.flash.has(it.uid) ? "flash" : ""}"><div class="sb-n" title="Drag to reorder">${i + 1}<small>${ts(t0)}</small></div><div class="sb-th"></div>
      <div class="sb-main">
        <div class="sb-row"><input class="inl beat" data-f="beat" placeholder="Beat name (hook, headline, use case 1, payoff)" value="${esc(it.beat)}"><input class="inl sec" data-f="seconds" type="number" min="0" step="0.25" placeholder="sec" value="${esc(it.seconds ?? "")}" title="Seconds"></div>
        <div class="id">${esc(s.title)} · <span class="k">${esc(it.id)}</span>${hasT(it) ? `<span class="sb-moment">${icon("bookmark")}${tcCopy(`@ ${tsf(+it.t)}`, stampAt(it.id, +it.t, FILMS[s.film].fps || 30, s.start), "The moment this beat borrows: click to copy")}<button data-a="clear-t" title="Clear the moment (keep the scene)">${icon("x")}</button></span>` : ""} · ${tcCopy(`${ts(s.start)} to ${ts(s.end)}`, stampRange(s.key, s.start, s.end))}</div>
        <label class="fl"><span>On screen</span><textarea class="inl" data-f="copy" rows="1" placeholder="The exact words shown in this beat">${esc(it.copy)}</textarea></label>
        <label class="fl vo"><span>Voice-over</span><textarea class="inl" data-f="vo" rows="1" placeholder="What's said over this beat">${esc(it.vo || "")}</textarea></label>
        <label class="fl"><span>Note</span><textarea class="inl" data-f="note" rows="1" placeholder="Our UI, what changes, what to keep">${esc(it.note)}</textarea></label>
        <details><summary>How it moves · recreate</summary><p>${esc(s.how_it_moves)}</p><p>${esc(s.recreate)}</p></details></div>
      <div class="sb-side"><button class="icon-btn sm sq ghost" data-a="up" title="Move up">${icon("arrow-up")}</button><button class="icon-btn sm sq ghost" data-a="down" title="Move down">${icon("arrow-down")}</button><button class="icon-btn sm sq ghost" data-a="brief" title="Copy the scene's brief">${icon("copy")}</button><button class="icon-btn sm sq ghost" data-a="rm" title="Remove from the board">${icon("x")}</button></div></div>`);
    const th = thumb(s); th.onclick = () => (location.hash = `#/scene/${s.key}${hasT(it) ? `?t=${it.t}` : ""}`); $(".sb-th", el).append(th);
    $('[data-a="clear-t"]', el)?.addEventListener("click", () => { delete it.t; send([{ op: "item.update", board: current, uid: it.uid, patch: { t: "" } }]); renderBoards(); });
    el.querySelectorAll("[data-f]").forEach((inp) => (inp.oninput = () => {
      const f = inp.dataset.f, v = f === "seconds" ? (inp.value === "" ? null : +inp.value) : inp.value;
      updateItem(it, { [f]: v });
      if (f === "seconds" || f === "beat") debounced("tray", renderTray, 500);
    }));
    $('[data-a="up"]', el).onclick = () => moveItem(it.uid, i);
    $('[data-a="down"]', el).onclick = () => moveItem(it.uid, i + 2);
    $('[data-a="brief"]', el).onclick = () => copy(brief(s), "Brief copied");
    $('[data-a="rm"]', el).onclick = () => removeFromBoard(it.uid);
    sb.append(el);
  });
  main.append(sb);
  dragList(sb, ".sb-item", () => board().items);

  const log = (state.log || []).slice(-8).reverse();
  if (log.length) main.append(h(`<details class="activity"><summary>Recent changes</summary>${log.map((l) => `<div><b class="${l.by}">${esc(SP.who(l.by))}</b> ${esc(l.summary)} <span>${esc((l.at || "").replace("T", " ").slice(5, 16))}</span></div>`).join("")}</details>`));
}

/* ---------- moves ---------- */
function renderMoves() {
  const main = $("#main"); main.innerHTML = "";
  const all = [];
  for (const f of L.films) for (const m of f.signature_moves || []) all.push({ ...m, f });
  const list = all;
  const head = h(`<div class="view-head"><h1>Signature moves</h1><span class="meta"></span></div>`);
  main.append(head);
  const box = h(`<div class="moves"></div>`);
  list.forEach((m, i) => {
    const el = h(`<div class="move" style="animation-delay:${Math.min(i, 20) * 20}ms"><h3>${esc(m.name)}</h3>
      <div class="from"><a href="#/film/${m.f.slug}">${esc(m.f.title)}</a> · ${esc(m.f.brand)}</div>
      <p>${esc(m.description)}</p><div class="scenes"></div>${m.recreate ? `<details class="rec"><summary>Recreate</summary><p>${esc(m.recreate)}</p></details>` : ""}</div>`);
    const sc = $(".scenes", el);
    for (const id of m.scenes || []) {
      const s = BY_KEY[`${m.f.slug}/${id}`]; if (!s) continue;
      const th = thumb(s); th.title = `${s.key}  ${s.title}`; th.onclick = () => (location.hash = `#/scene/${s.key}`); sc.append(th);
    }
    box.append(el);
  });
  main.append(box);
  ViewSearch.attach(head, "moves", { placeholder: "Search moves", cards: ".moves .move",
    count: (n, total, q) => ($(".meta", head).textContent = q ? `${n} of ${total} named techniques` : `${total} named techniques`) });
}

/* ---------- films ---------- */
/* A film card's media: a still from its best scene; on hover it plays a few seconds of each of its three best scenes,
   in film order, on a loop. The video only loads on hover. */
const PREVIEW_SECONDS = 2.4;
function stopPreviews() {
  document.querySelectorAll(".film-media video").forEach((v) => { v.pause(); v.removeAttribute("src"); v.load(); });
}
function filmPreview(f) {
  const picks = [...f.scenes].sort((a, b) => b.steal - a.steal || a.start - b.start).slice(0, 3).sort((a, b) => a.start - b.start);
  const segs = picks.map((s) => { const a = s.start + Math.min(0.15, (s.end - s.start) / 4); return { s, a, e: Math.min(s.end - 0.05, a + PREVIEW_SECONDS) }; });
  const box = h(`<div class="film-media"><div class="fm-bars">${segs.map(() => "<i><b></b></i>").join("")}</div><span class="fm-tag"></span><span class="fm-dur">${ts(f.duration)}</span></div>`);
  // poster: a clean frame from the middle of the best scene (cut by the toolbox server); the scene strip when opened from disk
  const best = [...f.scenes].sort((a, b) => b.steal - a.steal || a.start - b.start)[0];
  if (best) {
    const strip = () => box.prepend(thumb(best, { scrub: false }));
    if (server) {
      const img = h(`<img class="fm-poster" alt="" loading="lazy" src="/api/frame?file=${encodeURIComponent(f.file)}&t=${((best.start + best.end) / 2).toFixed(2)}&w=720">`);
      img.onerror = () => { img.remove(); strip(); };
      box.prepend(img);
    } else strip();
  }
  const tag = $(".fm-tag", box), bars = [...box.querySelectorAll(".fm-bars b")];
  let v = null, k = 0, raf = 0, hoverT = 0;
  const paint = () => {
    const g = segs[k]; if (!g || !v) return;
    tag.innerHTML = tcCopy(`${g.s.id} · ${ts(v.currentTime)}`, stampAt(g.s.key, v.currentTime, f.fps || 30, g.s.start), "Click to copy the time with the scene ID");
    tag.title = g.s.title;
    bars.forEach((b, j) => (b.style.width = j < k ? "100%" : j > k ? "0%" : `${clampN((v.currentTime - g.a) / (g.e - g.a), 0, 1) * 100}%`));
  };
  const go = (j) => { k = j % segs.length; try { v.currentTime = segs[k].a; } catch {} };
  const loop = () => {
    raf = requestAnimationFrame(loop);
    if (!v || v.readyState < 2) return;
    const g = segs[k];
    if (v.currentTime >= g.e || v.currentTime < g.a - 0.4) go(k + 1);
    paint();
  };
  const start = () => {
    if (!segs.length) return;
    if (!v) {
      v = document.createElement("video");
      v.muted = true; v.playsInline = true; v.preload = "auto"; v.disablePictureInPicture = true;
      v.addEventListener("playing", () => box.classList.add("live"));
      v.addEventListener("error", () => box.classList.add("nofile"));
      box.append(v);
    }
    if (!v.src) { v.src = fileUrl(f.file); box.classList.remove("live"); }
    box.classList.add("on");
    const begin = () => { go(0); v.play().catch(() => {}); };
    v.readyState >= 1 ? begin() : v.addEventListener("loadedmetadata", begin, { once: true });
    cancelAnimationFrame(raf); raf = requestAnimationFrame(loop);
  };
  const stop = () => {
    clearTimeout(hoverT); cancelAnimationFrame(raf);
    box.classList.remove("on", "live");
    bars.forEach((b) => (b.style.width = "0%"));
    if (v) v.pause();
  };
  box.addEventListener("mouseenter", () => { hoverT = setTimeout(start, 120); });
  box.addEventListener("mouseleave", stop);
  return box;
}
function renderFilms() {
  const main = $("#main"); main.innerHTML = "";
  const list = L.films.slice().sort((a, b) => a.category.localeCompare(b.category) || a.slug.localeCompare(b.slug));
  const head = h(`<div class="view-head"><h1>Films</h1><span class="meta"></span></div>`);
  main.append(head);
  const grid = h(`<div class="films"></div>`);
  list.forEach((f, i) => {
    const pal = (f.style_signature?.palette || []).slice(0, 6);
    const el = h(`<div class="film" style="animation-delay:${Math.min(i, 20) * 20}ms" title="${esc(f.summary)}" data-search="${esc([f.title, f.brand, f.slug, f.category, f.voice, (f.music_feel || []).join(" "), f.summary, (f.signature_moves || []).map((m) => m.name).join(" ")].join(" "))}">
      <h3>${esc(f.title)}</h3><div class="k"><span>${esc(f.brand)}</span><span>${esc(f.category.replace(/-/g, " "))}</span><span>${f.scenes.length} scenes</span></div>
      <div class="fpal">${pal.map((p) => `<i style="background:${esc(p.hex)}" title="${esc(p.hex + " " + (p.name || ""))}"></i>`).join("")}</div></div>`);
    el.prepend(filmPreview(f));
    el.onclick = () => (location.hash = `#/film/${f.slug}`);
    grid.append(el);
  });
  main.append(grid);
  ViewSearch.attach(head, "films", { placeholder: "Search films", cards: ".films .film",
    count: (n, total, q) => ($(".meta", head).textContent = q ? `${n} of ${total} films` : `${total} references · ${SCENES.length} scenes`) });
}
function renderFilm(slug) {
  const f = FILMS[slug], main = $("#main"); main.innerHTML = "";
  if (!f) {
    main.append(h(slug === "system-moves"
      ? `<div class="empty"><b>No film kit in this project yet</b><p>Systems shows a film kit's own moves, each as a scene you can borrow like any other. It appears once the project has a kit (<a href="#/setup">Setup</a>, Make films).</p></div>`
      : `<div class="empty">No film called ${esc(slug)}. <a href="#/films"><b>All films</b></a></div>`));
    return;
  }
  const sig = f.style_signature || {};
  const page = h(`<div class="film-page">
    <div class="view-head"><h1><a class="crumb" href="#/films">Films</a><span class="sep">/</span><span class="nm">${esc(f.title)}</span></h1><span class="meta">${esc(f.brand)} · ${ts(f.duration)} · ${f.scenes.length} scenes</span><span class="spacer"></span>
      <button class="icon-btn sm sq ghost" data-a="moment" title="Save the frame the film is on as a moment (K)">${icon("bookmark-plus")}</button>
      <button class="icon-btn sm ghost" data-a="filter">${icon("library-big")}Its scenes in Library</button>
      <button class="icon-btn sm primary" data-a="film-brief" title="Copy a prompt for ${esc(SP.ai)} to recreate this whole film as closely as it can, scene by scene">${icon("copy")}Copy build brief</button></div>
    <div class="hero"><video controls preload="metadata" src="${fileUrl(f.file)}"></video>
      <div><p class="summary">${esc(f.summary)}</p>
      ${sig.palette ? `<div class="swatches">${sig.palette.map((p) => `<span class="sw" data-c="${esc(p.hex)}" title="Copy ${esc(p.hex)}"><i style="background:${esc(p.hex)}"></i>${esc(p.name || p.hex)}</span>`).join("")}</div>` : ""}
      <details class="d-more"><summary>${icon("chevron-right")}Style signature<span>${esc(f.category)}, ${esc(f.voice)}${f.tempo?.bpm ? `, ${Math.round(f.tempo.bpm)} bpm` : ""}</span></summary>
      <dl class="sig">${Object.entries(sig).filter(([k]) => k !== "palette").map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
      ${f.structure ? `<p class="structure">${esc(f.structure)}</p>` : ""}</details></div></div>
    <div class="bigbar"></div><div class="grid"></div></div>`);
  main.append(page);
  page.querySelectorAll(".sw").forEach((sw) => (sw.onclick = () => copy(sw.dataset.c, `Copied ${sw.dataset.c}`)));
  $('[data-a="film-brief"]', page).onclick = () => copy(filmBrief(slug), `Copied: paste it to ${SP.ai} to recreate ${f.title}`);
  $('[data-a="filter"]', page).onclick = () => { ui.filters = { film: new Set([slug]) }; ui.q = ""; ui.sort = "film"; location.hash = "#/scenes?" + filtersToQuery(); };
  const bar = $(".bigbar", page), hero = $(".hero video", page);
  for (const s of f.scenes) bar.append(h(`<div class="seg-s" style="left:${(s.start / f.duration) * 100}%;width:${((s.end - s.start) / f.duration) * 100}%;background:${ROLE_COL[s.role] || "#777"}">${s.end - s.start > f.duration / 30 ? s.id : ""}</div>`));
  const bph = h(`<div class="ph"></div>`); bar.append(bph);
  bar.dataset.film = f.slug;
  filmHero = { f, video: hero };
  $('[data-a="moment"]', page).onclick = (e) => saveMoment(f, hero.currentTime || 0, e.currentTarget);
  paintMomentPins();
  const fps = f.fps || 30;
  const htc = h(`<div class="bigbar-l"><span class="tc-copy" title="Click to copy the time with the scene ID"></span><span>Drag to scrub · click a scene to open it · shift-click copies a time</span></div>`);
  bar.after(htc);
  const paint = () => {
    const t = hero.currentTime || 0, x = sceneAt(f, t) || f.scenes[0];
    bph.style.left = `${(t / f.duration) * 100}%`;
    const el = $(".tc-copy", htc); el.textContent = `${tsf(t)}  f${Math.round(t * fps)}  ${x ? x.id : ""}`;
    if (x) el.dataset.copy = stampAt(x.key, t, fps, x.start);
  };
  hero.addEventListener("timeupdate", paint); hero.addEventListener("seeked", paint); hero.addEventListener("loadedmetadata", paint);
  let heroWas = false;
  scrubber(bar, {
    duration: () => f.duration,
    seek: (t) => { try { hero.currentTime = t; } catch {} paint(); },
    label: (t) => { const x = sceneAt(f, t), m = momentNear(f.slug, t, f.duration); return `${tsf(t)}${x ? ` · ${x.id} ${x.role} · ${x.title}` : ""}${m ? ` · moment${m.note ? ": " + m.note : ""}` : ""}`; },
    copyAt: (t) => { const x = sceneAt(f, t) || f.scenes[0]; return stampAt(x.key, t, fps, x.start); },
    onStart: () => { heroWas = !hero.paused; hero.pause(); },
    onEnd: (t, moved) => { if (moved && heroWas) hero.play().catch(() => {}); },
    onClick: (t) => { const x = sceneAt(f, t); if (x) location.hash = `#/scene/${x.key}`; },
  });
  const grid = $(".grid", page);
  f.scenes.forEach((s) => grid.append(card(s)));
  const fmeta = $(".view-head .meta", page), fwas = fmeta.textContent;
  ViewSearch.attach($(".view-head", page), `film.${slug}`, { placeholder: slug === "system-moves" ? "Search the moves" : "Search this film's scenes", root: page, cards: ".grid > .card",
    text: (el) => { const s = BY_KEY[el.dataset.key]; return s ? `${s.key} ${s.text} ${[s.role, s.world, ...(s.motion || []), ...(s.camera || []), ...(s.subject || [])].join(" ")}` : ""; },
    count: (n, total, q) => (fmeta.textContent = q ? `${n} of ${total} scenes` : fwas) });
}

/* ---------- moments: the exact frames the person points at ("acme-launch/s12 @ 0:42.51") ---------- */
let filmHero = null;  // the film page's player, for K
const momentStamp = (m) => { const s = BY_KEY[m.key]; return s ? stampAt(m.key, m.t, FILMS[s.film].fps || 30, s.start) : `${m.key} @ ${tsf(m.t)}`; };
const momentNear = (film, t, dur) => state.moments.find((m) => m.key.split("/")[0] === film && Math.abs(m.t - t) < Math.max(0.12, dur / 300));
function saveMoment(f, t, anchor) {
  const s = sceneAt(f, t) || f.scenes[0];
  if (!s) return;
  if (video && f.file === videoFile && detailKey) video.pause();
  if (filmHero && filmHero.f === f) filmHero.video.pause();
  const m = { uid: uid(), key: s.key, t: Math.round(t * 100) / 100, note: "", at: new Date().toISOString().slice(0, 19), by: "browser" };
  state.moments.push(m);
  send([{ op: "moment.add", key: m.key, t: m.t, uid: m.uid }]);
  paintMomentPins();
  paintNavCounts();
  toast(`Moment saved: ${m.key} @ ${tsf(m.t)}`, 2400, [{ label: "Moments", run: () => (location.hash = "#/moments") }]);
  if (anchor) momentPopover(anchor, m);
}
/* a small popover under the button: type a note for the moment you just saved (Enter or click away saves it) */
let pop = null;
function closePop() { if (pop) { pop.remove(); pop = null; document.removeEventListener("mousedown", popOutside, true); } }
function popOutside(e) { if (pop && !pop.contains(e.target)) { pop._save(); closePop(); } }
function momentPopover(anchor, m) {
  closePop();
  pop = h(`<div class="mo-pop"><div class="mo-pop-t">${icon("bookmark")}<span class="mono">${esc(m.key)} @ ${tsf(m.t)}</span></div><input placeholder="Note (optional): what to take from this frame"><div class="mo-pop-k">Enter saves · Esc skips · <a href="#/moments">All moments</a></div></div>`);
  const inp = $("input", pop);
  pop._save = () => { const v = inp.value.trim(); if (v && v !== m.note) { m.note = v; send([{ op: "moment.update", uid: m.uid, patch: { note: v } }]); paintMomentPins(); } };
  inp.onkeydown = (e) => { e.stopPropagation(); if (e.key === "Enter") { pop._save(); closePop(); } else if (e.key === "Escape") closePop(); };
  const r = anchor.getBoundingClientRect();
  pop.style.top = `${Math.min(r.bottom + 8, innerHeight - 120)}px`; pop.style.left = `${Math.max(12, Math.min(r.right - 320, innerWidth - 332))}px`;
  document.body.append(pop); inp.focus();
  setTimeout(() => document.addEventListener("mousedown", popOutside, true));
}
/* markers on the film bars (scene detail, film page) where moments were saved */
function paintMomentPins() {
  document.querySelectorAll(".filmbar[data-film], .bigbar[data-film]").forEach((bar) => {
    bar.querySelectorAll(".mo-pin").forEach((x) => x.remove());
    const f = FILMS[bar.dataset.film]; if (!f) return;
    for (const m of state.moments) if (m.key.split("/")[0] === f.slug) bar.append(h(`<i class="mo-pin" style="left:${(m.t / f.duration) * 100}%"></i>`));
  });
}
function addMomentToBoard(m) {
  const b = board();
  if (b.items.some((i) => i.id === m.key && +i.t === m.t)) { toast(`Already on ${current}`); return; }
  const it = { uid: uid(), id: m.key, t: m.t, beat: "", copy: "", vo: "", note: m.note || "" };
  b.items.push(it);
  send([{ op: "item.add", board: current, id: m.key, uid: it.uid, t: m.t, ...(m.note ? { note: m.note } : {}) }]);
  renderTray(); toast(`Added ${m.key} @ ${tsf(m.t)} to ${current}`);
}
function renderMoments() {
  const main = $("#main"); main.innerHTML = "";
  const q = ui.q.toLowerCase();
  const all = [...state.moments].reverse();
  const list = all.filter((m) => !q || [m.key, m.note, BY_KEY[m.key]?.title].join(" ").toLowerCase().includes(q));
  main.append(h(`<div class="view-head"><h1>Moments</h1><span class="meta">${list.length}${list.length !== all.length ? ` of ${all.length}` : ""} saved frame${all.length === 1 ? "" : "s"}${q ? ` matching "${esc(ui.q)}"` : ""}</span><span class="spacer"></span><span class="meta hint">Press <kbd>K</kbd> in a scene or a film to save the frame you're on</span></div>`));
  if (!all.length) { main.append(h(`<div class="empty">No moments yet. Open a scene (or a film) and press <b>K</b>, or <b>Save moment</b>, at the frame you mean. It saves the scene and the exact time, so you can point at it, open it there, or put it on a board.</div>`)); return; }
  const grid = h(`<div class="mo-grid"></div>`);
  list.forEach((m, i) => {
    const s = BY_KEY[m.key], f = s && FILMS[s.film];
    const el = h(`<div class="mo-card ${ui.flash.has(m.uid) ? "flash" : ""}" style="animation-delay:${Math.min(i, 20) * 18}ms">
      <div class="mo-frame">${f ? (server ? `<img alt="" loading="lazy" src="/api/frame?file=${encodeURIComponent(f.file)}&t=${m.t.toFixed(2)}&w=480">` : "") : ""}<span class="mo-t">${tsf(m.t)}</span></div>
      <div class="mo-body"><div class="id">${tcCopy(`${esc(m.key)} @ ${tsf(m.t)}`, momentStamp(m))}${s ? ` · ${(m.t - s.start).toFixed(2)}s in` : ""}</div>
        <div class="t">${esc(s ? s.title : "Not in the library")}</div>${f ? `<div class="from">${esc(f.title)} · ${esc(f.brand)}</div>` : ""}
        <textarea class="inl" rows="1" placeholder="Add a note: what to take from this frame">${esc(m.note || "")}</textarea>
        <div class="btns"><a class="icon-btn sm ghost" href="#/scene/${esc(m.key)}?t=${m.t}" title="Open the scene at this frame">${icon("play")}Open</a>
          <button class="icon-btn sm ghost" data-a="board" title="Add it to ${esc(current)}, at this moment">${icon("plus")}Add to board</button>
          <span class="gap"></span><button class="icon-btn sm sq ghost" data-a="rm" title="Delete the moment">${icon("trash-2")}</button></div></div></div>`);
    const img = $(".mo-frame img", el);
    if (img) img.onerror = () => { img.remove(); if (s) $(".mo-frame", el).prepend(thumb(s, { scrub: false })); };
    else if (s) $(".mo-frame", el).prepend(thumb(s, { scrub: false }));
    $(".mo-frame", el).onclick = () => (location.hash = `#/scene/${m.key}?t=${m.t}`);
    const ta = $("textarea", el);
    ta.oninput = () => { m.note = ta.value; debounced(`moment:${m.uid}`, () => send([{ op: "moment.update", uid: m.uid, patch: { note: ta.value.trim() } }])); };
    $('[data-a="board"]', el).onclick = () => addMomentToBoard(m);
    $('[data-a="rm"]', el).onclick = () => { state.moments = state.moments.filter((x) => x !== m); send([{ op: "moment.remove", uid: m.uid }]); renderMoments(); paintNavCounts(); };
    grid.append(el);
  });
  main.append(grid);
}

/* ---------- settings (#/settings): this browser's preferences and keyboard shortcuts ---------- */
const PREFS = {
  cardDetails: ["cr.cardDetails", "hover"],   // "hover" (details on hover) or "always" (title and meta under each card)
  hoverPlay: ["cr.hoverPlay", "1"],
  grain: ["cr.grain", "1"],
  sounds: ["cr.uiSound", "0"],                // the clicks of Build's keys, switch and knobs (hardware.js): off unless turned on
};
const pref = (k) => localStorage.getItem(PREFS[k][0]) ?? PREFS[k][1];
function setPref(k, v) { localStorage.setItem(PREFS[k][0], v); applyPrefs(); }
function applyPrefs() {
  const r = document.documentElement;
  r.classList.toggle("cards-always", pref("cardDetails") === "always");
  r.classList.toggle("no-grain", pref("grain") === "0");
}
applyPrefs();
function renderSettings() {
  const main = $("#main"); main.innerHTML = "";
  main.append(h(`<div class="view-head"><h1>Settings</h1></div>`));
  const seg = (k, opts) => `<div class="seg" data-pref="${k}">${opts.map(([v, l]) => `<button data-v="${v}" class="${pref(k) === v ? "on" : ""}">${l}</button>`).join("")}</div>`;
  const theme = themeMode();
  const page = h(`<div class="set">
    <section><h2>Spliced</h2>
      <div class="set-row"><div><b>Version ${esc(window.Changelog?.version() || "")}</b><span>What changed, newest first</span></div><span class="set-new" hidden></span><button class="icon-btn sm" data-a="upd" title="${SP.native ? "Ask whether a newer Spliced is out, and put it in" : "Ask whether a newer Spliced is out, and how to get it"}">Check for updates</button><button class="icon-btn sm" data-a="whatsnew">What's new</button></div>
    </section>
    <section><h2>This machine</h2>
      <div class="set-row"><div><b>Setup</b><span>What Spliced can do here now, and the step that unlocks the next thing</span></div><a class="icon-btn sm" href="#/setup">Open Setup</a></div>
      <div class="set-row"><div><b>Welcome</b><span>How Spliced works, in three steps</span></div><button class="icon-btn sm" data-a="welcome">Show it</button></div>
      <div class="set-row"><div><b>Glossary</b><span>Beat, board, take, bed, stem and the rest, in plain terms</span></div><button class="icon-btn sm" data-a="glossary">Open it</button></div>
      <div class="set-row"><div><b>View explainers</b><span>The few lines under a view's heading the first time you open it</span></div><button class="icon-btn sm" data-a="explainers">Show them again</button></div>
    </section>
    <section><h2>Service keys</h2><p class="set-lead">Keys for the services Spliced calls itself. Each is saved in this project's .env, which git ignores and only you can read. Spliced never shows a key again, and your AI is told not to open the file. NASA and Openverse footage needs no key.</p><div class="set-apikeys"></div></section>
    <section><h2>Appearance</h2>
      <div class="set-row"><div><b>Theme</b><span>Spliced is dark by default</span></div><div class="seg" data-theme>${[["dark", "Dark"], ["light", "Light"], ["system", "System"]].map(([v, l]) => `<button data-v="${v}" class="${theme === v ? "on" : ""}">${l}</button>`).join("")}</div></div>
      <div class="set-row"><div><b>Film grain</b><span>A fine noise over the app's surfaces</span></div>${seg("grain", [["1", "On"], ["0", "Off"]])}</div>
      <div class="set-row"><div><b>Panel sizes</b><span>The sidebar and the scene panel are resized by dragging their edge</span></div><button class="icon-btn sm" data-a="reset-sizes">Reset sizes</button></div>
    </section>
    <section><h2>Library</h2>
      <div class="set-row"><div><b>Card details</b><span>Title, brand and time on hover, or always under the picture</span></div>${seg("cardDetails", [["hover", "On hover"], ["always", "Always"]])}</div>
      <div class="set-row"><div><b>Play clips on hover</b><span>A scene's clip loops while the pointer is on it</span></div>${seg("hoverPlay", [["1", "On"], ["0", "Off"]])}</div>
    </section>
    <section><h2>Build</h2>
      <div class="set-row"><div><b>Control sounds</b><span>Soft clicks when you press the keys, slide the switch or turn the knobs in the transport bar. Quiet while a film plays with its sound on</span></div>${seg("sounds", [["1", "On"], ["0", "Off"]])}</div>
    </section>
    <section><h2>Keyboard shortcuts</h2><p class="set-lead">Click a shortcut, then press the key you want. It replaces the current one for that action. Stored in this browser.</p><div class="set-keys"></div>
      <div class="set-foot"><button class="icon-btn sm" data-a="reset-keys">Reset all shortcuts</button></div></section>
  </div>`);
  main.append(page);
  $('[data-a="welcome"]', page).onclick = () => window.Welcome?.open();
  $('[data-a="whatsnew"]', page).onclick = () => window.Changelog?.open();
  const upd = $('[data-a="upd"]', page);
  if (upd && !SP.native) {   // a browser: the server asks, and says how this copy is updated
    upd.onclick = async () => {
      upd.disabled = true; upd.textContent = "Checking…";
      const u = await checkWebUpdate(true);
      upd.disabled = false; upd.textContent = "Check for updates";
      if (!u) toast("Couldn't ask: the server didn't answer");
      else if (u.newer) updateToast(u);
      else if (u.off) toast(u.kind === "checkout" ? "This copy is a git checkout: git pull updates it" : u.published === false ? "Spliced isn't published yet: update it from where you got it" : "Checking for updates is turned off for this project", 5000);
      else toast(u.latest ? "Spliced is up to date" : "Couldn't tell: offline, or no release to compare with yet", 4000);
    };
  } else if (upd) {
    const label = () => { upd.textContent = UPD?.state === "available" ? "Update app" : UPD?.state === "checking" ? "Checking…" : UPD?.state === "updating" ? "Updating…" : "Check for updates"; upd.disabled = UPD?.state === "updating" || UPD?.state === "checking"; };
    label(); updListeners.add(label);
    upd.onclick = async () => {
      if (UPD?.state === "available") return SP.native.ask("update", { action: "install" });
      await SP.native.ask("update", { action: "check" });
      const s = await new Promise((res) => { const t = setInterval(async () => { const x = await SP.native.ask("update", { action: "status" }); if (x.state !== "checking") { clearInterval(t); res(x); } }, 700); });
      SPUpdate.changed(s);
      toast(s.state === "available" ? `${s.version}: ready to update` : s.state === "failed" ? s.error : "Spliced is up to date");
    };
  }
  const news = () => window.Changelog?.unseen().then((n) => { const m = $(".set-new", page); if (m) { m.hidden = !n; m.textContent = !n ? "" : window.Changelog.first() ? "New" : `${n} new`; } });
  news(); document.addEventListener("spliced:changelog-seen", news, { once: true });
  $('[data-a="glossary"]', page).onclick = () => window.Tips?.glossary();
  $('[data-a="explainers"]', page).onclick = () => { window.Explain?.reset(); toast("Each view explains itself again, once"); };
  page.querySelectorAll("[data-pref]").forEach((g) => g.querySelectorAll("button").forEach((b) => (b.onclick = () => { setPref(g.dataset.pref, b.dataset.v); g.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); if (g.dataset.pref === "sounds" && b.dataset.v === "1") window.HW?.sound.play("clack"); })));   // turning the sounds on lets you hear one
  page.querySelectorAll(".seg[data-theme] button").forEach((b) => (b.onclick = () => { localStorage.setItem("cr.theme", b.dataset.v); applyTheme(); page.querySelectorAll(".seg[data-theme] button").forEach((x) => x.classList.toggle("on", x === b)); }));
  $('[data-a="reset-sizes"]', page).onclick = () => { ["cr.sidebarW", "cr.detailW"].forEach((k) => localStorage.removeItem(k)); document.documentElement.style.removeProperty("--sidebar-w"); document.documentElement.style.removeProperty("--detail"); toast("Panel sizes reset"); };
  $('[data-a="reset-keys"]', page).onclick = () => { KB.reset(); paintKeys(); toast("Shortcuts reset"); };
  const keys = $(".set-keys", page);
  function paintKeys() {
    keys.innerHTML = "";
    for (const g of [...new Set(KB.DEFS.map((d) => d[0]))]) {
      keys.append(h(`<h3>${esc(g)}</h3>`));
      for (const [, id, label] of KB.DEFS.filter((d) => d[0] === g)) {
        const cl = KB.clashes(id);
        const row = h(`<div class="set-key ${KB.custom(id) ? "custom" : ""}"><span class="l">${esc(label)}</span>${cl.length ? `<span class="clash" title="Also: ${esc(cl.join(", "))}">${icon("triangle-alert")}Shared with ${esc(cl[0])}${cl.length > 1 ? ` +${cl.length - 1}` : ""}</span>` : ""}
          <button class="caps" title="Click, then press a key">${KB.keycaps(id) || `<span class="dim">None</span>`}</button>${KB.custom(id) ? `<button class="icon-btn sm sq ghost" data-a="undo" title="Back to the default">${icon("rotate-cw")}</button>` : `<span class="sp"></span>`}</div>`);
        const caps = $(".caps", row);
        caps.onclick = () => {
          KB.recording = true; caps.classList.add("rec"); caps.innerHTML = "Press a key…";
          const done = () => { KB.recording = false; document.removeEventListener("keydown", onk, true); document.removeEventListener("mousedown", out, true); paintKeys(); };
          const onk = (e) => {
            e.preventDefault(); e.stopPropagation();
            if (e.key === "Escape") { done(); return; }
            const b = KB.of(e); if (!b) return;
            KB.set(id, [b]); done(); toast(`${label}: ${KB.label(b)}`);
          };
          const out = (e) => { if (!row.contains(e.target)) done(); };
          document.addEventListener("keydown", onk, true); setTimeout(() => document.addEventListener("mousedown", out, true));
        };
        $('[data-a="undo"]', row)?.addEventListener("click", () => { KB.reset(id); paintKeys(); });
        keys.append(row);
      }
    }
  }
  paintKeys();
  // service keys (apikeys.py): pasted here, saved in .env, never shown again
  const keyList = $(".set-apikeys", page);
  window.ApiKeys.list().then((keys) => {
    for (const k of keys) {
      const row = h(`<div class="set-row"><div><b>${esc(k.name)}</b><span>${esc(k.what)}</span></div></div>`);
      row.append(window.ApiKeys.control(k));
      keyList.append(row);
    }
  }).catch(() => keyList.append(h(`<p class="dim">Open Spliced with ${esc(SP.cmd("open"))} to manage keys.</p>`)));
}
CR.command?.({ id: "app.sounds", title: "Control sounds on / off", hint: "The clicks of the keys, switch and knobs in Build", group: "App", run: () => {
  const on = pref("sounds") !== "1"; setPref("sounds", on ? "1" : "0");
  document.querySelectorAll('[data-pref="sounds"] button').forEach((x) => x.classList.toggle("on", x.dataset.v === (on ? "1" : "0")));
  if (on) window.HW?.sound.play("clack");
  toast(on ? "Control sounds on" : "Control sounds off");
} });
CR.command?.({ id: "app.whatsnew", title: "What's new in Spliced", hint: "The version that is running, and what changed", group: "App", run: () => window.Changelog?.open() });
CR.command?.({ id: "app.explain", title: "About this view", hint: "What it is for, and what to try", group: "App", when: () => !!window.Explain?.has(), run: () => window.Explain?.show() });
CR.command?.({ id: "app.glossary", title: "Glossary: the words Spliced uses", hint: "Beat, board, take, bed, stem and the rest, in plain terms", group: "App", run: () => window.Tips?.glossary() });
CR.command?.({ id: "app.welcome", title: "Welcome: how Spliced works", hint: "The three steps: collect, connect your AI, make", group: "App", run: () => window.Welcome?.open() });
CR.command?.({ id: "app.settings", title: "Settings", hint: "Theme, Library, keyboard shortcuts, service keys (ElevenLabs, footage)", group: "App", run: () => (location.hash = "#/settings") });

/* ---------- styles ---------- */
function renderStyles() {
  const main = $("#main");
  if (window.StylesView) { window.StylesView.render(main); return; } // styles.js: the visual Styles view
  main.innerHTML = "";
  main.append(h(`<div class="prose">${L.styles_html}</div>`));
}

/* ---------- keys ---------- */
// the order next / previous walk through: the Library as it was last shown (filtered and sorted), or a film's scenes
let viewOrder = [];
function neighbour(key, dir) {
  const s = BY_KEY[key]; if (!s) return null;
  const i = viewOrder.indexOf(key);
  if (i >= 0) return BY_KEY[viewOrder[i + dir]] || null;
  const f = FILMS[s.film]; return f.scenes[f.scenes.indexOf(s) + dir] || null;
}
const goScene = (s) => s && (location.hash = `#/scene/${s.key}`);
/* Build's shortcuts work the transport's hardware the way a hand would: the key on screen goes down with its click
   on the press and comes up with its own on the release; L slides the switch with its clack (hardware.js sounds,
   which stay off unless Control sounds is on, and quiet while a film plays with its sound on). */
const HW_KEYS = [["bPlay", "play"], ["bFrameBack", "back"], ["bFrameFwd", "fwd"], ["sound", "mute"]];
function hwKey(e) {
  if (!document.querySelector(".bx-stage") || document.querySelector(".bx-compose, .imp-scrim")) return;
  const hit = HW_KEYS.find(([id]) => KB.is(e, id));
  if (hit) {
    const k = document.querySelector(`.bx-tr .hw-key[data-a="${hit[1]}"]`); if (!k || k.disabled) return;
    k.classList.add("is-active"); HW.sound.play("down");
    let t = 0;
    const up = (u) => { if (u && u.code !== e.code) return; removeEventListener("keyup", up, true); clearTimeout(t); k.classList.remove("is-active"); HW.sound.play("up"); };
    t = setTimeout(up, 700); addEventListener("keyup", up, true);
  } else if (KB.is(e, "loop") && document.querySelector(".bx-tr #bx-mode")) HW.sound.play("clack");
}
document.addEventListener("keydown", (e) => {
  const typing = /input|textarea|select/i.test(e.target.tagName);
  if (e.key === "Escape") { if (typing) e.target.blur(); else if (menuEl) closeMenu(); else if (fpop) closeFpop(); else if ($(".help")) $(".help").remove(); else if (detailKey) closeDetail(); else if (ui.trayOpen) setTray(false); return; }
  if (typing || KB.recording) return;
  if (KB.is(e, "search")) { e.preventDefault(); CR.openPalette?.(); return; }
  if (KB.is(e, "help")) { e.preventDefault(); toggleHelp(); return; }
  if (!detailKey) {
    const lib = route().view === "scenes";
    if (lib && KB.is(e, "filter")) { e.preventDefault(); openFpop(); return; }
    if (lib && KB.is(e, "zoomOut")) { e.preventDefault(); setZoom(libZoom - 40); return; }
    if (lib && KB.is(e, "zoomIn")) { e.preventDefault(); setZoom(libZoom + 40); return; }
    if (filmHero && KB.is(e, "moment")) { e.preventDefault(); saveMoment(filmHero.f, filmHero.video.currentTime || 0, $('[data-a="moment"]')); return; }
    if (route().view === "build" && window.HW && !e.metaKey && !e.ctrlKey && !e.repeat) hwKey(e);
    if (route().view === "assets" && !e.metaKey && !e.ctrlKey && window.AssetsView?.onKey?.(e)) return;
    if (!e.metaKey && !e.ctrlKey) build.onKey(e); return;
  }
  const s = BY_KEY[detailKey], f = FILMS[s.film];
  if (KB.is(e, "next")) { e.preventDefault(); goScene(neighbour(s.key, 1)); }
  else if (KB.is(e, "prev")) { e.preventDefault(); goScene(neighbour(s.key, -1)); }
  else if (KB.is(e, "fav")) setRev(s.key, { fav: !rev(s.key).fav });
  else if (KB.is(e, "board")) addToBoard(s.key);
  else if (KB.is(e, "brief")) copy(brief(s), `Brief copied: paste it into ${SP.ai}`);
  else if (KB.is(e, "sceneNote")) { e.preventDefault(); focusNote(); }
  else if (s.upload) { if (KB.is(e, "play")) { const v = $("#detail video"); if (v) { e.preventDefault(); v.paused ? v.play() : v.pause(); } } }
  else if (KB.is(e, "play")) { e.preventDefault(); video && (video.paused ? video.play() : video.pause()); }
  else if (KB.is(e, "frameBack") || KB.is(e, "frameFwd")) { const fps = f.fps || 30; video.pause(); video.currentTime = Math.min(loopRange[1] - 0.001, Math.max(loopRange[0], video.currentTime + (KB.is(e, "frameBack") ? -1 : 1) / fps)); }
  else if (KB.is(e, "moment")) { e.preventDefault(); saveMoment(f, video.currentTime, $('#review [data-a="moment"]')); }
  else if (KB.is(e, "time")) $("#tc")?.click();
  else if (KB.is(e, "seekBack") || KB.is(e, "seekFwd")) { e.preventDefault(); video.currentTime = clampN(video.currentTime + (KB.is(e, "seekBack") ? -1 : 1) * (e.shiftKey ? 0.1 : 1), loopRange[0], loopRange[1] - 0.001); }
});
// the shortcuts sheet (?) shows the bindings as they are now
function toggleHelp() {
  const x = $(".help"); if (x) { x.remove(); return; }
  const groups = [...new Set(KB.DEFS.map((d) => d[0]))];
  const el = h(`<div class="help">${groups.map((g) => `<h3>${esc(g)}</h3><dl>${KB.DEFS.filter((d) => d[0] === g).map((d) => `<dt>${KB.keycaps(d[1])}</dt><dd>${esc(d[2])}</dd>`).join("")}</dl>`).join("")}<p class="help-foot"><a href="#/settings">Change them in Settings</a></p></div>`);
  $("a", el).onclick = () => el.remove();
  document.body.append(el);
}

/* ---------- build view (build.js) ---------- */
// setBoard(name): the Build view makes the film's board the current one (no navigation), so Scenes adds to the right board
const setBoard = (name) => { if (name && state.boards[name] && name !== current) setCurrent(name); };
const build = window.BuildView({ h, esc, $, ts, tsf, toast, copy: (t, m) => copy(t, m), thumb, BY_KEY, FILMS, fileUrl, scrubber, stampAt, stampRange, tcCopy, setBoard });

/* ---------- the command palette (palette.js): every action and every place ---------- */
function paintNavCounts() { const n = $("#nav-moments"); if (n) n.textContent = state.moments.length || ""; }
const view = () => route().view;
const inDetail = () => !!detailKey;
const GO = [["scenes", "Library", "#/scenes"], ["films", "Films", "#/films"], ["moves", "Moves", "#/moves"], ["systems", "Systems", "#/film/system-moves"], ["styles", "Styles", "#/styles"], ["moments", "Moments", "#/moments"], ["boards", "Boards", "#/boards"], ["setup", "Setup", "#/setup"], ["build", "Build", "#/build"], ["assets", "Assets", "#/assets"]];
for (const [id, title, hash] of GO) CR.command({ id: `lib.go.${id}`, title: `Go to ${title}`, group: "Go to", run: () => (location.hash = hash) });
const scenesOnly = () => view() === "scenes";
for (const c of [
  { id: "lib.filter", title: "Filter scenes…", group: "Library", keys: "F", when: scenesOnly, run: () => openFpop() },
  { id: "lib.clear", title: "Clear all filters", group: "Library", when: () => scenesOnly() && activeCount() > 0, run: () => clearFilters() },
  { id: "lib.favs", title: "Show favourites", group: "Library", run: () => { ui.fav = true; ui.notes = false; location.hash = "#/scenes?" + filtersToQuery(); } },
  { id: "lib.noted", title: "Show scenes with notes", group: "Library", run: () => { ui.notes = true; ui.fav = false; location.hash = "#/scenes?" + filtersToQuery(); } },
  ...SORTS.map(([v, l]) => ({ id: `lib.sort.${v}`, title: `Sort scenes: ${l.toLowerCase()}`, group: "Library", when: scenesOnly, run: () => { ui.sort = v; syncHash(); render(); } })),
  { id: "lib.brief", title: "Copy the scene's brief", group: "Scene", keys: "C", when: inDetail, run: () => copy(brief(BY_KEY[detailKey]), `Brief copied: paste it into ${SP.ai}`) },
  { id: "lib.id", title: "Copy the scene ID", group: "Scene", when: inDetail, run: () => copy(detailKey, `Copied ${detailKey}`) },
  { id: "lib.fav", title: "Favourite the scene", group: "Scene", keys: "F", when: inDetail, run: () => setRev(detailKey, { fav: !rev(detailKey).fav }) },
  { id: "lib.moment", title: "Save this frame as a moment", group: "Scene", keys: "K", when: () => inDetail() || !!filmHero, run: () => { if (detailKey) { const s = BY_KEY[detailKey]; saveMoment(FILMS[s.film], video.currentTime, $('#review [data-a="moment"]')); } else saveMoment(filmHero.f, filmHero.video.currentTime || 0, $('[data-a="moment"]')); } },
  { id: "lib.add", title: "Add the scene to the board", group: "Scene", keys: "B", when: inDetail, run: () => addToBoard(detailKey) },
  { id: "lib.ctx", title: "Play 1s either side of the scene", group: "Scene", when: inDetail, run: () => $('#detail [data-a="ctx"]')?.click() },
  { id: "lib.filmscenes", title: "Show this film's scenes in Library", group: "Film", when: () => view() === "film", run: () => $('[data-a="filter"]')?.click() },
  { id: "lib.tray", title: "Show or hide the board tray", group: "Board", run: () => (document.body.classList.contains("no-tray") ? (location.hash = `#/boards/${encodeURIComponent(current)}`) : setTray(!ui.trayOpen)) },
  { id: "lib.prompt", title: "Copy the board's build prompt", group: "Board", run: () => boardActs.prompt() },
  { id: "lib.plan", title: "Copy the board as a plan", group: "Board", run: () => boardActs.plan() },
  { id: "lib.md", title: "Download the board as .md", group: "Board", run: () => boardActs.md() },
  { id: "lib.film", title: "Start a film from the board (or open it)", group: "Board", when: () => view() === "boards", run: () => boardActs.film() },
  { id: "lib.editbrief", title: "Edit the board's brief", group: "Board", when: () => view() === "boards", run: () => { ui.briefOpen = true; renderBoards(); } },
  { id: "lib.rename", title: "Rename the board", group: "Board", when: () => view() === "boards", run: () => boardActs.rename() },
  { id: "lib.delete", title: "Delete the board", group: "Board", when: () => view() === "boards", run: () => boardActs.del() },
  { id: "lib.new", title: "New board", group: "Board", run: () => boardActs.newb() },
  { id: "lib.export", title: "Export all boards and reviews", group: "Board", run: () => boardActs.exp() },
  { id: "lib.import", title: "Import boards from an export", group: "Board", run: () => boardActs.imp() },
  { id: "lib.theme", title: "Change theme (system, light, dark)", group: "App", run: () => cycleTheme() },
  { id: "lib.help", title: "Keyboard shortcuts", group: "App", keys: "?", run: () => toggleHelp() },
  { id: "lib.follow", title: `Follow ${SP.ai} on or off`, group: "App", when: () => server, run: () => $('#status [data-a="follow"]')?.click() },
]) CR.command(c);
// what the global search finds, each with a picture (palette.js draws scenes, films, boards and moments as tiles)
const frameThumb = (file, t, w = 360) => `/api/frame?file=${encodeURIComponent(file)}&t=${(+t || 0).toFixed(2)}&w=${w}`;
const sceneThumb = (x) => x.upload ? (x.upload.kind === "video" ? frameThumb(x.upload.file, 0.4) : fileUrl(x.upload.file)) : FILMS[x.film]?.file ? frameThumb(FILMS[x.film].file, (x.start + x.end) / 2) : "";
// What the global search can land on beyond scenes, films and boards: a line on a board, a named move, a look
// or structure from Styles, a film word. Each opens the place it lives, with that view's own search set to it.
CR.sources.push(() => [
  ...Object.keys(state.boards).flatMap((n) => state.boards[n].items.map((it, i) => ({ id: `lib.bb.${n}.${it.uid}`, title: it.copy || it.vo || it.beat || BY_KEY[it.id]?.title || it.id,
    sub: `${n} · beat ${i + 1}${it.beat ? " · " + it.beat : ""}`, text: `${it.copy} ${it.vo} ${it.note} ${it.beat} ${it.id} ${n}`, group: "Board beats", hash: `#/boards/${encodeURIComponent(n)}` }))),
  ...L.films.flatMap((f) => (f.signature_moves || []).map((m) => ({ id: `lib.mv.${f.slug}.${m.name}`, title: m.name, sub: `${f.title} · ${m.description || ""}`.slice(0, 110),
    text: `${m.name} ${m.description || ""} ${f.title} ${f.brand}`, group: "Moves", hash: `#/moves?q=${encodeURIComponent(m.name)}` }))),
  ...(L.styles?.sections || []).flatMap((sec) => (sec.kind === "looks" ? sec.items.map((it) => it.title) : sec.kind === "table" ? sec.rows.map((r) => r.plain?.[0]) : []).filter(Boolean)
    .map((t) => ({ id: `lib.st.${sec.id}.${t}`, title: t, sub: sec.title, text: `${t} ${sec.title}`, group: "Styles", hash: `#/styles?q=${encodeURIComponent(t)}` }))),
  ...Object.entries(window.Tips?.TERMS || {}).map(([k, [name, means]]) => ({ id: `word.${k}`, title: name, sub: means, text: `${name} ${means} glossary word meaning`, group: "Words", run: () => window.Tips.glossary() })),
]);
CR.sources.push(() => [
  ...Object.keys(state.boards).map((n) => { const b = state.boards[n], first = b.items.map((it) => BY_KEY[it.id]).filter(Boolean).slice(0, 4);
    return { id: `lib.b.${n}`, title: n, sub: `${b.items.length} beats${b.brief?.news ? " · " + b.brief.news : ""}`, text: [n, b.brief?.news, ...b.items.map((it) => `${it.beat} ${it.copy} ${it.vo}`)].join(" "), group: "Boards", hash: `#/boards/${encodeURIComponent(n)}`, thumbs: first.map(sceneThumb) }; }),
  ...state.moments.map((m) => { const x = BY_KEY[m.key]; return { id: `lib.m.${m.uid}`, title: m.note || x?.title || m.key, sub: `${m.key} @ ${tsf(m.t)}`, group: "Moments", hash: `#/scene/${m.key}?t=${m.t}`, thumb: x && FILMS[x.film]?.file ? frameThumb(FILMS[x.film].file, m.t) : "" }; }),
  ...L.films.map((f) => { const best = [...f.scenes].sort((a, b) => b.steal - a.steal)[0];
    return { id: `lib.f.${f.slug}`, title: f.title, sub: `${f.brand} · ${f.scenes.length} scenes`, text: `${f.title} ${f.brand} ${f.category} ${f.summary || ""}`, group: "Films", hash: `#/film/${f.slug}`, thumb: best ? frameThumb(f.file, (best.start + best.end) / 2) : "" }; }),
  ...SCENES.map((x) => ({ id: `lib.s.${x.key}`, title: x.title, sub: x.upload ? `Uploaded · ${x.upload.kind}` : `${FILMS[x.film]?.brand || ""} · ${tsf(x.start)}`, text: `${x.key} ${x.text}`, group: x.upload ? "Uploads" : "Scenes", hash: `#/scene/${x.key}`, thumb: sceneThumb(x), video: !x.upload || x.upload.kind === "video" })),
]);
// typing in search can also filter the Library itself
window.CR.filterLibrary = (q) => { ui.q = q.trim(); $("#q").value = ui.q; closeDetail(false); location.hash = "#/scenes" + (filtersToQuery() ? "?" + filtersToQuery() : ""); };

/* ---------- tabs (like Linear): several places open at once, each keeping its own route and scroll ----------
   A tab is a route (the hash) plus, for a scene, the view under it. Clicking in the app moves the tab you're in;
   ⌘-click or middle-click a card or link to open it in a new tab. Shortcuts in Settings (Alt+T, Alt+W, Alt+←/→, Alt+1–9).
   Kept in this browser: localStorage cr.tabs. */
const TABS_KEY = "cr.tabs";
let tabs = (() => { try { const t = JSON.parse(localStorage.getItem(TABS_KEY)); if (t && t.list?.length) return t; } catch {} return null; })();
let tabSwitching = false, prodTitles = {};
const saveTabs = () => localStorage.setItem(TABS_KEY, JSON.stringify(tabs));
const curTab = () => tabs.list.find((t) => t.id === tabs.active) || tabs.list[0];
const VIEW_TAB = { setup: ["Setup", "check"], scenes: ["Library", "library-big"], films: ["Films", "film"], moves: ["Moves", "sparkles"], styles: ["Styles", "swatch-book"], moments: ["Moments", "bookmark"], boards: ["Boards", "layout-list"], build: ["Build", "list-video"], assets: ["Assets", "image"], settings: ["Settings", "settings"] };
function tabInfo(hash) {
  const [path] = (hash || "#/scenes").replace(/^#\/?/, "").split("?");
  const p = path.split("/").filter(Boolean).map(decodeURIComponent), v = p[0] || "scenes";
  if (v === "scene") { const x = BY_KEY[`${p[1]}/${p[2]}`]; return [x ? x.title : `${p[1]}/${p[2]}`, x?.upload ? "image" : "film"]; }
  if (v === "film") return p[1] === "system-moves" ? ["Systems", "cpu"] : [FILMS[p[1]]?.title || p[1], "film"];
  if (v === "boards" && p[1]) return [p[1], "layout-list"];
  if (v === "build" && p[1]) return [prodTitles[p[1]] || p[1], "list-video"];
  if (v === "scenes" && hash.includes("?")) { const q = new URLSearchParams(hash.split("?")[1]); const bits = [q.get("q"), ...[...q.keys()].filter((k) => !["q", "sort"].includes(k)).map((k) => q.get(k))].filter(Boolean); if (bits.length) return [`Library: ${bits.join(", ")}`.slice(0, 60), "library-big"]; }
  return VIEW_TAB[v] || ["Spliced", "library-big"];
}
function tabId() { return Math.random().toString(36).slice(2, 8); }
function openTab(hash, { background = false } = {}) {
  const t = { id: tabId(), hash, base: hash.startsWith("#/scene/") ? (curTab()?.base || ui.base || "#/scenes") : null, scroll: 0 };
  // like a browser: a background tab goes after the ones already opened from this tab, a new tab right after this one
  const i = tabs.list.findIndex((x) => x.id === tabs.active);
  let at = i + 1;
  if (background) { const from = tabs.active; while (at < tabs.list.length && tabs.list[at].from === from) at++; t.from = from; }
  tabs.list.splice(at, 0, t); saveTabs();
  if (background) { paintTabs(); toast(`Opened in a new tab: ${tabInfo(hash)[0]}`); }
  else switchTab(t.id);
}
function switchTab(id) {
  const t = tabs.list.find((x) => x.id === id); if (!t) return;
  const was = curTab(); if (was) was.scroll = $("#main").scrollTop;
  tabs.active = id; saveTabs(); paintTabs();
  if (t.hash === location.hash) return;
  tabSwitching = true;
  if (t.hash.startsWith("#/scene/")) { ui.base = t.base || "#/scenes"; if (route().view === "scene" || location.hash.split("?")[0] !== ui.base.split("?")[0]) { closeDetail(false); history.replaceState(null, "", ui.base); onHash(); } }
  location.hash = t.hash;
  setTimeout(() => { tabSwitching = false; const m = $("#main"); if (m && t.scroll) m.scrollTop = t.scroll; }, 250);
}
function closeTab(id) {
  if (tabs.list.length === 1) { const t = tabs.list[0]; if (t.hash !== "#/scenes") { t.hash = "#/scenes"; saveTabs(); location.hash = "#/scenes"; } return; }
  const i = tabs.list.findIndex((x) => x.id === id); if (i < 0) return;
  tabs.list.splice(i, 1);
  if (tabs.active === id) switchTab(tabs.list[Math.min(i, tabs.list.length - 1)].id); else { saveTabs(); paintTabs(); }
}
function stepTab(d) { const i = tabs.list.findIndex((x) => x.id === tabs.active); switchTab(tabs.list[(i + d + tabs.list.length) % tabs.list.length].id); }
let dragTab = null;
function paintTabs() {
  const bar = $("#tabs"); if (!bar || !tabs) return;
  bar.innerHTML = "";
  bar.append(navCluster());
  for (const t of tabs.list) {
    const [title, ic] = tabInfo(t.hash);
    const el = h(`<div class="tab ${t.id === tabs.active ? "on" : ""}" draggable="true" title="${esc(title)}" data-id="${t.id}">${icon(ic)}<span>${esc(title)}</span><button class="tab-x" title="Close tab (${esc(KB.get("closeTab").map(KB.label).join(" or "))})" aria-label="Close tab">${icon("x")}</button></div>`);
    el.onclick = (e) => { if (!e.target.closest(".tab-x")) switchTab(t.id); };
    el.onauxclick = (e) => { if (e.button === 1) { e.preventDefault(); closeTab(t.id); } };
    $(".tab-x", el).onclick = (e) => { e.stopPropagation(); closeTab(t.id); };
    el.ondragstart = () => { dragTab = t.id; el.classList.add("drag"); };
    el.ondragend = () => { dragTab = null; el.classList.remove("drag"); };
    el.ondragover = (e) => { if (dragTab) e.preventDefault(); };
    el.ondrop = (e) => { e.preventDefault(); if (!dragTab || dragTab === t.id) return; const from = tabs.list.findIndex((x) => x.id === dragTab), to = tabs.list.findIndex((x) => x.id === t.id); tabs.list.splice(to, 0, tabs.list.splice(from, 1)[0]); saveTabs(); paintTabs(); };
    bar.append(el);
  }
  const add = h(`<button class="tab-add" title="New tab (${esc(KB.get("newTab").map(KB.label).join(" or "))})" aria-label="New tab">${icon("plus")}</button>`);
  add.onclick = () => openTab("#/scenes");
  bar.append(add);
  const up = updatePill(); if (up) bar.append(up);
  bar.querySelector(".tab.on")?.scrollIntoView({ inline: "nearest", block: "nearest" });
}
function initTabs() {
  if (!tabs) tabs = { list: [{ id: tabId(), hash: location.hash || "#/scenes", base: null, scroll: 0 }] };
  if (!tabs.list.some((t) => t.id === tabs.active)) tabs.active = tabs.list[0].id;
  const t = curTab();
  if (location.hash && location.hash !== t.hash) t.hash = location.hash; else if (!location.hash) history.replaceState(null, "", t.hash);
  saveTabs(); paintTabs();
  fetch("/api/productions").then((r) => r.json()).then((l) => { for (const p of l) prodTitles[p.slug] = p.title; paintTabs(); }).catch(() => {});
}
// the tab you're in follows where you go, and remembers where it has been: back and forward are each tab's own
window.addEventListener("hashchange", () => {
  if (!tabs) return;
  const t = curTab(); if (!t) return;
  const traversed = navTraversed(); navStamp();
  if (!tabSwitching && t.hash && t.hash !== location.hash) noteStep(t, t.hash, location.hash, traversed);
  navStepping = null;
  if (location.hash.startsWith("#/scene/")) t.base = t.base && !tabSwitching ? (route().view === "scene" ? ui.base : t.base) : ui.base;
  t.hash = location.hash; saveTabs(); paintTabs();
});
// ⌘-click or middle-click a card or an in-app link: open it in a new tab, staying where you are
function tabTarget(e) {
  const a = e.target.closest?.('a[href^="#/"]'); if (a) return a.getAttribute("href");
  const c = e.target.closest?.(".card[data-key], .pal-tile, .as-tile"); if (c?.dataset.key) return `#/scene/${c.dataset.key}`;
  return null;
}
document.addEventListener("click", (e) => { if (!(e.metaKey || e.ctrlKey) || !tabs) return; const t = tabTarget(e); if (!t) return; e.preventDefault(); e.stopPropagation(); openTab(t, { background: true }); }, true);
document.addEventListener("auxclick", (e) => { if (e.button !== 1 || !tabs || e.target.closest(".tab")) return; const t = tabTarget(e); if (!t) return; e.preventDefault(); e.stopPropagation(); openTab(t, { background: true }); }, true);
document.addEventListener("keydown", (e) => {
  if (!tabs || /input|textarea|select/i.test(e.target.tagName) || KB.recording) return;
  if (KB.is(e, "newTab")) { e.preventDefault(); openTab("#/scenes"); }
  else if (KB.is(e, "closeTab")) { e.preventDefault(); closeTab(tabs.active); }
  else if (KB.is(e, "nextTab")) { e.preventDefault(); stepTab(1); }
  else if (KB.is(e, "prevTab")) { e.preventDefault(); stepTab(-1); }
  else if (e.altKey && !e.metaKey && !e.ctrlKey && /^Digit[1-9]$/.test(e.code)) { const t = tabs.list[+e.code.slice(5) - 1]; if (t) { e.preventDefault(); switchTab(t.id); } }
}, true);
CR.command?.({ id: "tab.new", title: "New tab", group: "Tabs", run: () => openTab("#/scenes") });
CR.command?.({ id: "tab.dup", title: "Duplicate this tab", group: "Tabs", run: () => openTab(location.hash) });
CR.command?.({ id: "tab.close", title: "Close this tab", group: "Tabs", run: () => closeTab(tabs.active) });
CR.command?.({ id: "tab.others", title: "Close other tabs", group: "Tabs", run: () => { tabs.list = [curTab()]; saveTabs(); paintTabs(); } });

/* ---------- in the Mac app: back, forward and recently viewed, at the start of the tab strip ----------
   A browser has its own back and forward; the app's window doesn't, so the page draws them there (SP.native only).
   The app tells the page when going back or forward becomes possible (SPNav.state). Recently viewed is every place
   opened in this project, newest first, one entry per place (kept in this browser: cr.recent). */
const RECENT_KEY = "cr.recent", NAV_MAX = 50;
/* Each tab keeps the places it came from (t.back, newest last) and the ones it stepped back from (t.fwd), like a
   browser tab. A step the page makes itself (the buttons, ⌘[ ⌘]) is marked by navStepping. A move through the
   window's own history (a two-finger swipe) brings back an entry the page stamped earlier (history.state.spNav):
   it is taken as back or forward when it lands where the tab's history says, and as a new place otherwise. */
let navStepping = null, navCount = 0;
{ const rs = history.replaceState.bind(history);   // the app's own replaceState calls keep the stamp
  history.replaceState = (st, title, url) => rs(st ?? history.state, title, url); }
function navTraversed() { return history.state?.spNav != null; }
function navStamp() { history.replaceState({ ...(history.state || {}), spNav: ++navCount }, ""); }
navStamp();
function noteStep(t, from, to, traversed) {
  t.back = t.back || []; t.fwd = t.fwd || [];
  const top = (a) => a[a.length - 1];
  const way = navStepping || (traversed ? (top(t.back) === to ? "back" : top(t.fwd) === to ? "fwd" : null) : null);
  if (way === "back" && top(t.back) === to) { t.back.pop(); t.fwd.push(from); }
  else if (way === "fwd" && top(t.fwd) === to) { t.fwd.pop(); t.back.push(from); }
  else { t.back.push(from); t.fwd = []; }
  if (t.back.length > NAV_MAX) t.back.splice(0, t.back.length - NAV_MAX);
  if (t.fwd.length > NAV_MAX) t.fwd.splice(0, t.fwd.length - NAV_MAX);
}
function navCan() { const t = tabs && curTab(); return { back: !!t?.back?.length, fwd: !!t?.fwd?.length }; }
function navStep(way) {
  const t = tabs && curTab(), list = way === "back" ? t?.back : t?.fwd;
  if (!list?.length) return;
  const to = list[list.length - 1];
  if (to === location.hash) { list.pop(); saveTabs(); paintTabs(); return; }   // nothing to move to: drop it
  navStepping = way;
  location.hash = to;
  setTimeout(() => (navStepping = null), 600);
}
const recentList = () => { try { return JSON.parse(localStorage.getItem(RECENT_KEY)) || []; } catch { return []; } };
function noteRecent(hash) {
  if (!hash || !hash.startsWith("#/")) return;
  const place = hash.split("?")[0];
  const list = recentList().filter((r) => r.hash.split("?")[0] !== place);
  list.unshift({ hash, at: Date.now() });
  localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, 40)));
}
window.addEventListener("hashchange", () => noteRecent(location.hash));
setTimeout(() => noteRecent(location.hash || "#/scenes"), 0);
function recentKind(hash) {
  const p = hash.replace(/^#\/?/, "").split("?")[0].split("/").filter(Boolean), v = p[0] || "scenes";
  if (v === "scene") return p[1] === "uploads" ? "Upload" : "Scene";
  if (v === "film") return p[1] === "system-moves" ? "View" : "Film";
  if (v === "boards" && p[1]) return "Board";
  if (v === "build" && p[1]) return "In production";
  if (v === "scenes" && hash.includes("?")) return "Search";
  return "View";
}
function navCluster() {
  const can = navCan(), t = tabs && curTab();
  const name = (list) => (list?.length ? `: ${tabInfo(list[list.length - 1])[0]}` : "");
  // the shortcuts are the Mac app's menu's: in a browser those keys are the browser's own, so the buttons stand alone
  const key = (k) => (SP.native ? ` (${k})` : "");
  const el = h(`<div class="tab-nav">
    <button data-a="recent" title="Recently viewed${key("⌘Y")}" aria-label="Recently viewed">${icon("history")}</button>
    <button data-a="back" title="${esc("Back" + name(t?.back) + key("⌘["))}" aria-label="Back" ${can.back ? "" : "disabled"}>${icon("chevron-left")}</button>
    <button data-a="fwd" title="${esc("Forward" + name(t?.fwd) + key("⌘]"))}" aria-label="Forward" ${can.fwd ? "" : "disabled"}>${icon("chevron-right")}</button></div>`);
  $('[data-a="recent"]', el).onclick = (e) => { e.stopPropagation(); $(".rv-pop") ? closeRecent() : openRecent(); };
  $('[data-a="back"]', el).onclick = () => navStep("back");
  $('[data-a="fwd"]', el).onclick = () => navStep("fwd");
  SP.native?.ask("navState", can);   // the View menu's Back and Forward follow the page
  return el;
}
function closeRecent() { const p = $(".rv-pop"); if (!p) return; p.remove(); $('.tab-nav [data-a="recent"]')?.classList.remove("on"); }
function openRecent() {
  closeRecent();
  const btn = $('.tab-nav [data-a="recent"]'), here = location.hash.split("?")[0];
  const list = recentList().filter((r) => r.hash.split("?")[0] !== here).slice(0, 20);
  const pop = h(`<div class="rv-pop" role="menu" aria-label="Recently viewed"><div class="rv-h">Recently viewed</div>
    ${list.length ? list.map((r) => { const [t, ic] = tabInfo(r.hash); return `<button class="rv-row" role="menuitem" data-h="${esc(r.hash)}"><span class="rv-k">${esc(recentKind(r.hash))}</span>${icon(ic)}<span class="rv-t">${esc(t)}</span></button>`; }).join("")
      : `<div class="rv-empty">Places you open show up here.</div>`}</div>`);
  document.body.append(pop);
  const r = btn?.getBoundingClientRect();
  pop.style.left = `${Math.max(8, r ? r.left : 8)}px`; pop.style.top = `${(r ? r.bottom : 40) + 6}px`;
  btn?.classList.add("on");
  const rows = [...pop.querySelectorAll(".rv-row")];
  rows.forEach((b) => (b.onclick = (e) => { closeRecent(); if (e.metaKey || e.ctrlKey) openTab(b.dataset.h, { background: true }); else location.hash = b.dataset.h; }));
  (rows[0] || pop).focus?.();
  pop.addEventListener("keydown", (e) => {
    const i = rows.indexOf(document.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); rows[(i + (e.key === "ArrowDown" ? 1 : -1) + rows.length) % rows.length]?.focus(); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeRecent(); btn?.focus(); }
  });
  setTimeout(() => document.addEventListener("mousedown", function off(e) { if (!e.target.closest(".rv-pop, .tab-nav")) { closeRecent(); document.removeEventListener("mousedown", off); } }), 0);
}
/* ---------- in the Mac app: a newer Spliced, and the button that puts it in ----------
   The app checks (a release on GitHub, or new commits for a copy built from a checkout) and tells the page
   (SPUpdate.changed); Update app asks it to update, which closes and reopens Spliced with the same projects. */
let UPD = null;
const updListeners = new Set();
function updatePill() {
  if (!SP.native) return webUpdatePill();
  if (!UPD) return null;
  const why = "Spliced closes, updates and opens again with your projects";
  const b = UPD.state === "available" ? h(`<button class="upd-pill" title="${esc(`${UPD.version}${UPD.detail ? ": " + UPD.detail : ""}. ${why}.`)}">${icon("download")}Update app</button>`)
    : UPD.state === "updating" ? h(`<button class="upd-pill busy" disabled title="${esc(UPD.step || "Updating")}">${icon("loader")}${esc(UPD.step || "Updating")}…</button>`)
    : UPD.state === "failed" ? h(`<button class="upd-pill fail" title="${esc(UPD.error || "The update didn't finish")}">${icon("triangle-alert")}Update failed</button>`)
    : null;
  if (!b) return null;
  b.onclick = () => {
    if (UPD.state === "available") SP.native.ask("update", { action: "install" });
    else if (UPD.state === "failed") toast(UPD.error || "The update didn't finish", 8000, [{ label: "Try again", run: () => SP.native.ask("update", { action: "check" }) }]);
  };
  return b;
}
window.SPUpdate = {
  changed(s) {
    UPD = s;
    const bar = $("#tabs"); $(".upd-pill", bar || document)?.remove();
    const p = updatePill(); if (p && bar) bar.append(p);
    updListeners.forEach((f) => { try { f(); } catch {} });
  },
};
if (SP.native) setTimeout(() => SP.native.ask("update", { action: "status" }).then((s) => s && SPUpdate.changed(s)).catch(() => {}), 0);
/* In a browser there is no app to do the updating. The server asks, at most once a day, whether a newer Spliced is out
   (/api/update, updates.py); the same place in the tab strip then says so, with the command that gets it. */
let WEBUPD = null;
const updateWords = (u) => `Spliced ${u.latest} is out (this is ${u.current}). ${u.command ? `Run: ${u.command}. ` : ""}${u.how}. Afterwards, ${SP.cmd("setup")} brings this project's skills and film kit up to date.`;
const updateToast = (u) => toast(updateWords(u), 15000, u.command ? [{ label: "Copy the command", run: () => navigator.clipboard?.writeText(u.command) }] : null);
function webUpdatePill() {
  if (!WEBUPD?.newer) return null;
  const b = h(`<button class="upd-pill" title="${esc(`Spliced ${WEBUPD.latest} is out. Click for how to get it.`)}">${icon("download")}Update</button>`);
  b.onclick = () => updateToast(WEBUPD);
  return b;
}
async function checkWebUpdate(fresh) {
  const u = await fetch("/api/update" + (fresh ? "?fresh=1" : ""), { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (!u) return null;
  WEBUPD = u;
  const bar = $("#tabs"); $(".upd-pill", bar || document)?.remove();
  const p = webUpdatePill(); if (p && bar) bar.append(p);
  return u;
}
if (!SP.native) setTimeout(() => checkWebUpdate(false), 4000);

window.SPNav = {
  back: () => navStep("back"),
  forward: () => navStep("fwd"),
  can: () => navCan(),
  state() {},   // older app builds report the window's history here; the page keeps its own now
  recent: () => ($(".rv-pop") ? closeRecent() : openRecent()),
};
CR.command?.({ id: "nav.recent", title: "Recently viewed", group: "Tabs", ...(SP.native ? { keys: "⌘Y" } : {}), run: () => openRecent() });

// The app's window has no title bar: the top row (the tab strip, and the sidebar's strip above its header) moves
// the window when dragged where it is empty. The page says where that is; the app does the dragging.
if (SP.native) {
  let queued = false;
  const box = (r) => [r.left, r.top, r.width, r.height];
  const report = () => {
    queued = false;
    const bar = $("#tabs"), side = $(".sidebar"), drag = [], holes = [];
    if (bar) { drag.push(box(bar.getBoundingClientRect())); bar.querySelectorAll(".tab, button").forEach((x) => holes.push(box(x.getBoundingClientRect()))); }
    const tabsH = bar ? bar.getBoundingClientRect().height : 40;
    if (side) { const s = side.getBoundingClientRect(); if (s.right > 0) drag.push([s.left, 0, s.width, tabsH]); }
    document.querySelectorAll(".sb-unfold").forEach((x) => holes.push(box(x.getBoundingClientRect())));
    SP.native.ask("dragRegions", { drag, holes });
  };
  const queue = () => { if (!queued) { queued = true; requestAnimationFrame(report); } };
  window.addEventListener("resize", queue);
  window.addEventListener("load", queue);
  new MutationObserver(queue).observe(document.documentElement, { attributes: true, attributeFilter: ["class", "style"] });
  document.addEventListener("transitionend", queue);
  const watch = () => { const bar = $("#tabs"); if (!bar) return setTimeout(watch, 200); new MutationObserver(queue).observe(bar, { childList: true, subtree: true }); bar.addEventListener("scroll", queue); queue(); };
  watch();
}

// The app's window holds one project, so the sidebar names it, quietly, at the bottom above the toolbar: most people
// have one project, and sort their work into folders inside it. Clicking it opens the app's menu of projects: switch
// this window to a recent one, open or make another in its place, or close it (a browser tab is one project's server,
// so only the app draws this).
if (SP.native) {
  const name = SPLICED.project || "This project";
  const btn = h(`<button class="sb-proj" id="sb-proj" aria-haspopup="menu" title="${esc(name)}: switch to another project, open one or make a new one">
    ${icon("folder-open")}<span class="sb-proj-n">${esc(name)}</span>${icon("chevrons-up-down")}</button>`);
  $("#status")?.before(btn);
  const menu = async () => {
    const r = btn.getBoundingClientRect();
    btn.classList.add("on");
    await SP.native.ask("projects", r.width ? { at: [r.left, r.bottom + 4], above: r.top - 4 } : {});
    btn.classList.remove("on");
  };
  btn.onclick = menu;
  CR.command?.({ id: "app.projects", title: "Switch project", hint: "Open another project in this window, or make a new one", group: "App", run: menu });
}
// In a browser the page draws the same name and its own menu: the projects this person has opened (the server keeps
// the list, /api/projects), newest first. Choosing one starts its app if it isn't running and takes this tab there.
// Each project has its own address, so its tabs and what the page remembers stay with it.
if (!SP.native) {
  const name = SPLICED.project || "This project";
  const btn = h(`<button class="sb-proj" id="sb-proj" aria-haspopup="menu" title="${esc(name)}: switch to another project you have opened">
    ${icon("folder-open")}<span class="sb-proj-n">${esc(name)}</span>${icon("chevrons-up-down")}</button>`);
  $("#status")?.before(btn);
  const close = () => { $(".pj-pop")?.remove(); btn.classList.remove("on"); };
  const go = async (row, p) => {
    row.disabled = true; $(".rv-k", row).textContent = "Opening…";
    try {
      const r = await fetch("/api/projects/open", { method: "POST", body: JSON.stringify({ root: p.root }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.url) throw new Error(j.error || "it didn't start");
      location.href = j.url;
    } catch (e) { close(); toast(`Couldn't open ${p.name}: ${e.message}`, 6000); }
  };
  const menu = async () => {
    if ($(".pj-pop")) return close();
    const list = await fetch("/api/projects", { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).then((j) => j?.projects || []).catch(() => []);
    const others = list.filter((p) => !p.here), make = SP.cmd("setup", "<folder>");
    const pop = h(`<div class="rv-pop pj-pop" role="menu" aria-label="Projects"><div class="rv-h">Projects you have opened</div>
      <button class="rv-row" role="menuitem" disabled><span class="rv-k">This one</span>${icon("check")}<span class="rv-t">${esc(name)}</span></button>
      ${others.map((p, i) => `<button class="rv-row" role="menuitem" data-i="${i}" title="${esc(p.root)}"><span class="rv-k">${p.url ? "Running" : "Open"}</span>${icon("folder-open")}<span class="rv-t">${esc(p.name)}</span></button>`).join("")}
      ${others.length ? "" : `<div class="rv-empty">No other project has been opened on this machine yet.</div>`}
      <button class="rv-row" role="menuitem" data-a="new" title="${esc(`Choose a new or empty folder: Spliced makes it a project and opens it. From a terminal: ${make}`)}"><span class="rv-k">New</span>${icon("plus")}<span class="rv-t">New project…</span></button></div>`);
    document.body.append(pop);
    const r = btn.getBoundingClientRect();
    pop.style.width = "min(420px, calc(100vw - 24px))";
    pop.style.left = `${Math.max(8, r.left)}px`; pop.style.top = `${Math.max(8, r.top - pop.offsetHeight - 6)}px`;
    btn.classList.add("on");
    pop.querySelectorAll("[data-i]").forEach((row) => (row.onclick = () => go(row, others[+row.dataset.i])));
    $('[data-a="new"]', pop).onclick = async (e) => {
      const row = e.currentTarget, say = $(".rv-k", row);
      row.disabled = true; say.textContent = "Choose…";
      // the system's folder picker (the server opens it); where there is none, the path in words
      const picked = await fetch("/api/pick-folder", { method: "POST", body: JSON.stringify({ for: "project" }) }).then((x) => (x.ok ? x.json() : { none: true })).catch(() => ({ none: true }));
      const folder = picked.none ? prompt("A new or empty folder for the project, with its whole path:", "~/films/") : picked.path;
      if (!folder) { row.disabled = false; say.textContent = "New"; return; }
      say.textContent = "Making…";
      try {
        const res = await fetch("/api/projects/new", { method: "POST", body: JSON.stringify({ folder }) });
        const j = await res.json().catch(() => ({}));
        if (!res.ok || !j.url) throw new Error(j.error || "it wasn't made");
        location.href = j.url;
      } catch (err) { close(); toast(`Couldn't make the project: ${err.message}`, 7000); }
    };
    (pop.querySelector("[data-i]") || pop).focus?.();
    pop.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); btn.focus(); } });
    setTimeout(() => document.addEventListener("mousedown", function off(e) { if (!e.target.closest(".pj-pop, #sb-proj")) { close(); document.removeEventListener("mousedown", off); } }), 0);
  };
  btn.onclick = menu;
  CR.command?.({ id: "app.projects", title: "Switch project", hint: "Go to another project you have opened", group: "App", run: menu });
}

/* ---------- @ references in notes: type @ in any note to pick scenes or uploads to draw from ----------
   The note keeps "@film/sNN" (or "@uploads/<id>"), shown as a chip with the picture wherever the note is shown, and
   every prompt copied for Claude lists the referenced scenes with their breakdowns. */
const MENTION_RE = /@([a-z0-9][\w-]*\/(?:s\d+|[a-f0-9]{6}))\b/gi;
const mentionKeys = (text) => [...new Set([...String(text || "").matchAll(MENTION_RE)].map((m) => m[1]).filter((k) => BY_KEY[k]))];
let mpop = null; // {ta, at, items, sel, el}
function closeMention() { mpop?.el.remove(); mpop = null; }
function mentionResults(q) {
  q = q.toLowerCase();
  const words = q.split(/\s+/).filter(Boolean);
  const pool = q ? SCENES.filter((x) => words.every((w) => x.key.toLowerCase().includes(w) || x.text.includes(w))) : [
    ...SCENES.filter((x) => rev(x.key).fav),           // nothing typed yet: favourites first, then the best
    ...SCENES.filter((x) => !rev(x.key).fav && x.steal >= 3),
  ];
  const score = (x) => (x.key.toLowerCase().startsWith(words[0] || "") ? 3 : 0) + (words.every((w) => x.title.toLowerCase().includes(w)) ? 2 : 0) + (rev(x.key).fav ? 1 : 0) + x.steal / 10;
  return (q ? pool.sort((a, b) => score(b) - score(a)) : pool).slice(0, 8);
}
// the picker's second line: where it comes from, in words
const mentionFrom = (x) => x.upload ? `Upload · ${x.upload.kind === "video" ? "clip" : x.upload.kind || "image"}` : `${FILMS[x.film]?.title || x.film} · ${x.id}`;
function paintMention() {
  const { ta, items } = mpop;
  const r = ta.getBoundingClientRect();
  mpop.el.innerHTML = items.length ? items.map((x, i) => `<button class="mn-it ${i === mpop.sel ? "on" : ""}" data-i="${i}"><img loading="lazy" alt="" src="${esc(sceneThumb(x))}"><span class="t">${esc(mlabel(x))}</span><span class="k">${esc(mentionFrom(x))}</span></button>`).join("")
    : `<div class="mn-empty">No scene or upload matches</div>`;
  mpop.el.querySelectorAll(".mn-it").forEach((b) => { b.onmousedown = (e) => { e.preventDefault(); pickMention(+b.dataset.i); }; b.onmousemove = () => { if (mpop.sel !== +b.dataset.i) { mpop.sel = +b.dataset.i; paintMention(); } }; });
  const below = r.bottom + 6, h0 = mpop.el.offsetHeight || 320;
  mpop.el.style.left = `${Math.min(r.left, innerWidth - 380)}px`;
  mpop.el.style.top = `${below + h0 > innerHeight - 8 ? Math.max(8, r.top - h0 - 6) : below}px`;
}

/* In the box: the note's value keeps "@film/sNN" / "@uploads/<id>" (every save path reads ta.value and gets keys),
   but the box itself shows "@<name>", and a mirror laid over it draws each one as a badge with its picture.
   Done per textarea by shadowing its value property, so no view's own note code has to change. */
const NV = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value");
const nget = (ta) => NV.get.call(ta), nset = (ta, v) => NV.set.call(ta, v);
const mlabel = (x) => String(x.title || x.key).replace(/\s+/g, " ").replace(/@/g, "").trim();
function mranges(ta, text = nget(ta)) {
  const map = ta._mn?.map; if (!map?.size) return [];
  const labels = [...map.keys()].sort((a, b) => b.length - a.length), out = [];
  for (let i = text.indexOf("@"); i >= 0; i = text.indexOf("@", i + 1)) {
    if (i > 0 && !/[\s(\["'“‘]/.test(text[i - 1])) continue;
    const l = labels.find((l) => text.startsWith(l, i + 1) && !/\w/.test(text[i + 1 + l.length] || ""));
    if (l) { out.push({ start: i, end: i + 1 + l.length, key: map.get(l), label: l }); i += l.length; }
  }
  return out;
}
function toKeys(ta, text) { let out = "", last = 0; for (const r of mranges(ta, text)) { out += text.slice(last, r.start) + "@" + r.key; last = r.end; } return out + text.slice(last); }
function toLabels(ta, v) {
  return String(v ?? "").replace(MENTION_RE, (all, k) => { const x = BY_KEY[k]; if (!x) return all; const l = mlabel(x); ta._mn.map.set(l, k); return "@" + l; });
}
function richTa(ta) {
  if (ta._mn) return;
  ta._mn = { map: new Map() };
  Object.defineProperty(ta, "value", { configurable: true, get() { return toKeys(ta, nget(ta)); }, set(v) { nset(ta, toLabels(ta, v)); paintRich(ta); } });
  const cur = nget(ta), shown = toLabels(ta, cur);
  if (shown !== cur) nset(ta, shown);
  paintRich(ta);
}
const MIRROR = ["fontFamily", "fontSize", "fontWeight", "fontStyle", "lineHeight", "letterSpacing", "wordSpacing", "textIndent", "textTransform", "tabSize", "textAlign", "direction", "boxSizing",
  "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth"];
const rich = new Set();
function paintRich(ta) {
  const rs = mranges(ta); let ov = ta._mnOv;
  if (!rs.length) { if (ov) { ov.remove(); ta._mnOv = null; rich.delete(ta); } ta.classList.remove("mn-rich"); return; }
  if (!ov || !ov.isConnected || ov.previousElementSibling !== ta) { ov?.remove(); ov = ta._mnOv = h(`<div class="mn-mirror" aria-hidden="true"></div>`); ta.after(ov); }
  const text = nget(ta); let last = 0; ov.textContent = "";
  for (const r of rs) {
    const x = BY_KEY[r.key];
    ov.append(text.slice(last, r.start));
    const tok = document.createElement("span"), at = document.createElement("span");
    tok.className = "mn-tok"; at.className = "mn-at"; at.textContent = "@"; at.style.backgroundImage = `url(${JSON.stringify(sceneThumb(x))})`;
    tok.append(at, r.label); ov.append(tok); last = r.end;
  }
  ov.append(text.slice(last) + "​");   // so a trailing newline still takes its line
  ta.classList.add("mn-rich"); styleRich(ta); rich.add(ta); loopRich();
}
function styleRich(ta) {
  const ov = ta._mnOv; if (!ov) return;
  const cs = getComputedStyle(ta);
  for (const p of MIRROR) ov.style[p] = cs[p];
  const sb = ta.offsetWidth - ta.clientWidth - parseFloat(cs.borderLeftWidth) - parseFloat(cs.borderRightWidth);   // its scrollbar
  ov.style.paddingRight = `${parseFloat(cs.paddingRight) + Math.max(0, sb)}px`;
  ov.style.color = cs.color; ov.style.zIndex = cs.zIndex === "auto" ? "" : cs.zIndex;
  placeRich(ta);
}
function placeRich(ta) {
  const ov = ta._mnOv, s = ov.style, v = [`${ta.offsetLeft}px`, `${ta.offsetTop}px`, `${ta.offsetWidth}px`, `${ta.offsetHeight}px`];
  if (s.left !== v[0]) s.left = v[0]; if (s.top !== v[1]) s.top = v[1];
  if (s.width !== v[2]) { s.width = v[2]; } if (s.height !== v[3]) s.height = v[3];
  if (ov.scrollTop !== ta.scrollTop) ov.scrollTop = ta.scrollTop;
}
let richRaf = 0;
function loopRich() {   // follows the box while it moves (layout shifts, resizing, scrolling inside it)
  if (richRaf) return;
  const tick = () => {
    for (const ta of rich) { if (!ta.isConnected || !ta._mnOv) { ta._mnOv?.remove(); rich.delete(ta); continue; } placeRich(ta); }
    richRaf = rich.size ? requestAnimationFrame(tick) : 0;
  };
  richRaf = requestAnimationFrame(tick);
}
const richAll = (root) => { if (root instanceof HTMLTextAreaElement) richTa(root); else root.querySelectorAll?.("textarea").forEach(richTa); };
new MutationObserver((muts) => { for (const m of muts) for (const n of m.addedNodes) if (n.nodeType === 1) richAll(n); })
  .observe(document.body, { childList: true, subtree: true });
addEventListener("resize", () => rich.forEach(styleRich));
document.addEventListener("focusin", (e) => { if (e.target instanceof HTMLTextAreaElement) { richTa(e.target); if (e.target._mnOv) styleRich(e.target); } });

function pickMention(i) {
  const x = mpop?.items[i]; if (!x) return;
  const { ta, at } = mpop, end = ta.selectionStart, l = mlabel(x), v = nget(ta);
  richTa(ta); ta._mn.map.set(l, x.key);
  nset(ta, v.slice(0, at) + `@${l} ` + v.slice(end));
  const pos = at + l.length + 2; ta.setSelectionRange(pos, pos);
  closeMention();
  ta.dispatchEvent(new Event("input", { bubbles: true }));  // the note's own save runs as if typed
}
document.addEventListener("input", (e) => {
  const ta = e.target;
  if (!(ta instanceof HTMLTextAreaElement)) return;
  richTa(ta); paintRich(ta);
  // the query can run to a few words ("@acme la"); it ends when nothing matches any more
  const before = nget(ta).slice(0, ta.selectionStart), m = before.match(/(?:^|\s)@([^@\n]{0,40})$/);
  const q = m ? m[1] : "", at = m ? before.length - m[1].length - 1 : -1;
  const done = m && mranges(ta).some((r) => r.start === at);   // a picked reference, then more typing
  if (!m || done || q.trim().split(/\s+/).length > 3 || (/\s/.test(q) && !mentionResults(q.trim()).length)) { if (mpop?.ta === ta) closeMention(); return; }
  if (!mpop || mpop.ta !== ta) { closeMention(); mpop = { ta, el: h(`<div class="mn-pop" role="listbox"></div>`), sel: 0 }; document.body.append(mpop.el); }
  mpop.at = at; mpop.items = mentionResults(m[1].trim()); mpop.sel = Math.min(mpop.sel, Math.max(0, mpop.items.length - 1));
  paintMention();
}, true);
// a badge is one thing: Backspace after it (or Delete before it) takes the whole reference
document.addEventListener("keydown", (e) => {
  const ta = e.target;
  if (!(ta instanceof HTMLTextAreaElement) || !ta._mnOv || (e.key !== "Backspace" && e.key !== "Delete") || ta.selectionStart !== ta.selectionEnd || mpop?.ta === ta) return;
  const p = ta.selectionStart, r = mranges(ta).find((r) => e.key === "Backspace" ? p > r.start && p <= r.end : p >= r.start && p < r.end);
  if (!r) return;
  e.preventDefault(); e.stopImmediatePropagation();
  const v = nget(ta); nset(ta, v.slice(0, r.start) + v.slice(r.end)); ta.setSelectionRange(r.start, r.start);
  ta.dispatchEvent(new Event("input", { bubbles: true }));
}, true);
document.addEventListener("keydown", (e) => {
  if (!mpop || e.target !== mpop.ta) return;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); e.stopImmediatePropagation(); mpop.sel = (mpop.sel + (e.key === "ArrowDown" ? 1 : -1) + mpop.items.length) % Math.max(1, mpop.items.length); paintMention(); }
  else if ((e.key === "Enter" || e.key === "Tab") && mpop.items.length) { e.preventDefault(); e.stopImmediatePropagation(); pickMention(mpop.sel); }
  else if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); closeMention(); }
}, true);
document.addEventListener("focusout", (e) => { if (mpop && e.target === mpop.ta) setTimeout(() => { if (mpop && document.activeElement !== mpop.ta) closeMention(); }, 120); });
addEventListener("scroll", () => mpop && paintMention(), true);
// shown notes: @keys become chips with the picture; click opens the scene
function decorateMentions(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: (n) => n.parentElement?.closest("textarea, .mn-chip, .mn-mirror, script, style") || !/@[\w-]+\//.test(n.nodeValue) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
  const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const n of nodes) {
    const t = n.nodeValue; let last = 0, frag = document.createDocumentFragment(), hit = false;
    for (const m of t.matchAll(MENTION_RE)) {
      const x = BY_KEY[m[1]]; if (!x) continue; hit = true;
      frag.append(t.slice(last, m.index));
      const c = h(`<a class="mn-chip" href="#/scene/${esc(x.key)}" title="${esc(`${x.key}: ${x.title}`)}"><img alt="" src="${esc(sceneThumb(x))}"><span>${esc(mlabel(x))}</span></a>`);
      c.onclick = (ev) => ev.stopPropagation();
      frag.append(c); last = m.index + m[0].length;
    }
    if (hit) { frag.append(t.slice(last)); n.replaceWith(frag); }
  }
}
new MutationObserver((muts) => { for (const m of muts) for (const n of m.addedNodes) if (n.nodeType === 1 && !n.closest?.(".mn-pop")) decorateMentions(n); })
  .observe(document.getElementById("main"), { childList: true, subtree: true });
// prompts copied for Claude: list every referenced scene with where to read it
const _copy = copy;
copy = async (text, msg) => {
  const keys = mentionKeys(text);
  if (keys.length && !String(text).includes("References named with @")) {
    text += "\n\nReferences named with @ in the notes (look at each before changing anything):\n" + keys.map((k) => { const x = BY_KEY[k];
      return x.upload ? `- \`@${k}\` ${x.title}: the uploaded file ${x.upload.file}${x.upload.analysis?.recreate ? `. Recreate: ${x.upload.analysis.recreate}` : ""}`
        : `- \`@${k}\` ${x.title} (library/references/${x.film}/breakdown.md#${x.id}, ${ts(x.start)} to ${ts(x.end)})`; }).join("\n");
  }
  return _copy(text, msg);
};

/* ---------- boot ---------- */
let qT;
// the sidebar's search field opens the global search (palette.js); the Library's own text filter is one of its actions
$("#q").readOnly = true;
$("#q").addEventListener("focus", (e) => { e.target.blur(); CR.openPalette?.(); });
$("#q").addEventListener("mousedown", (e) => { e.preventDefault(); CR.openPalette?.(); });
$("#q").addEventListener("input", (e) => {
  clearTimeout(qT);
  qT = setTimeout(() => {
    ui.q = e.target.value.trim();
    const v = route().view;
    if (v === "scene" || v === "scenes") { if (v === "scene") closeDetail(false); location.hash = "#/scenes" + (filtersToQuery() ? "?" + filtersToQuery() : ""); }
    else render();
  }, 160);
});
(async () => {
  await loadState();
  if (server) await loadUploads();
  paintStatus();
  renderTray(); paintNavCounts();
  $("#board-pill").onclick = () => (document.body.classList.contains("no-tray") ? (location.hash = `#/boards/${encodeURIComponent(current)}`) : setTray(!ui.trayOpen));
  window.addEventListener("hashchange", onHash);
  initTabs();
  if (!location.hash) history.replaceState(null, "", "#/scenes");
  onHash();
  connectLive();
  window.Imports && window.Imports.mount();
  window.Welcome?.maybe({ boards: () => state.boards });
})();
})();
