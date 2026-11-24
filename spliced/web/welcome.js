/* The welcome: what Spliced is, in three steps, shown once to someone new and whenever they ask for it again
   (⌘K, "Welcome"; Settings). Each step is a real place in the app and knows whether it is already done here,
   so on a project that is under way it reads as a map, not a tutorial.

   The film: when the app ships an introduction (spliced/web/intro.mp4, announced by the server as SPLICED.intro),
   it plays at the top. Until then the three steps stand alone. */
window.Welcome = (() => {
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const icon = (n) => window.icon(n);
const SEEN = "cr.welcomed";
let sheet = null, boards = () => ({});

// The library's own films: the kit's "system-moves" is a specimen, not something the person collected.
const films = () => (window.LIBRARY?.films || []).filter((f) => f.slug !== "system-moves").length;
const beats = () => Object.values(boards() || {}).reduce((n, b) => n + (b.items?.length || 0), 0);

function steps(doc) {
  const ai = doc?.levels?.find((l) => l.id === "analyse");
  const next = doc?.items?.find((i) => i.id === doc.next);
  const nf = films(), nb = beats();
  return [
    { n: 1, title: "Collect films you love", done: nf > 0, state: nf ? `${nf} film${nf === 1 ? "" : "s"} in the library` : "",
      html: `Paste a link to a film whose look or motion you like. Spliced downloads it and cuts it into ${SP.term("scene", "scenes")} you can browse, ${SP.term("tag")} and borrow from.`,
      act: "Add a reference", go: () => window.Imports?.open() },
    { n: 2, title: "Connect your AI", done: !!ai?.ready, state: ai?.ready ? "Ready on this machine" : next ? `Next: ${next.label}` : "",
      html: `Spliced does no AI work itself. Your own AI (Claude Code, Codex or another) reads each film, builds ${SP.term("board", "boards")} with you and makes your film. Setup shows what is ready on this machine.`,
      act: "Open Setup", go: () => (location.hash = "#/setup") },
    { n: 3, title: "Make your own", done: nb > 0, state: nb ? `${nb} beat${nb === 1 ? "" : "s"} on your boards` : "",
      html: `Put scenes on a ${SP.term("board")} to write your film's script: one ${SP.term("beat")} per scene, with its words and its length. Then build it beat by beat, your ${SP.term("render")} beside the scene it borrows from.`,
      act: "Open Boards", go: () => (location.hash = "#/boards") },
  ];
}

function paint(doc) {
  if (!sheet) return;
  const list = steps(doc), first = list.find((s) => !s.done);
  const box = $(".wl-steps", sheet);
  box.innerHTML = "";
  for (const s of list) {
    const row = h(`<div class="wl-step ${s.done ? "done" : ""}"><span class="wl-n">${s.done ? icon("check") : s.n}</span>
      <div><b>${esc(s.title)}</b>${s.state ? `<span class="wl-state">${esc(s.state)}</span>` : ""}<p>${s.html}</p></div>
      <button class="icon-btn sm ${s === first ? "primary" : ""}">${esc(s.act)}</button></div>`);
    $("button", row).onclick = () => { close(); s.go(); };
    box.append(row);
  }
  const done = $('[data-a="done"]', sheet);
  done.classList.toggle("primary", !first);   // one primary button on the sheet: the next step, or Start when all are done
}

function open() {
  if (sheet) return;
  const intro = window.SPLICED?.intro, poster = window.SPLICED?.intro_poster;
  const first = !localStorage.getItem(SEEN);   // someone new: the film starts by itself, without sound, as the way in
  sheet = h(`<div class="imp-scrim wl"><div class="imp-sheet wl-sheet" role="dialog" aria-label="Welcome to Spliced">
    <div class="imp-head"><h2>Welcome to Spliced</h2><button class="icon-btn ghost sm sq" data-a="x" title="Close (Esc)">${icon("x")}</button></div>
    <div class="wl-body ${intro ? "with-film" : ""}">
      <div class="wl-intro">
      <p class="wl-lead">Study the films you love scene by scene, name their moves, and build your own from them, with your AI doing the work beside you.</p>
      ${intro ? `<figure class="wl-filmbox"><video class="wl-film" controls playsinline preload="${first ? "auto" : "metadata"}" ${first ? "autoplay muted" : ""} ${poster ? `poster="${esc(poster)}"` : ""} src="${esc(intro)}"></video>
        <figcaption>How Spliced works, in under a minute${first ? ". It plays without sound until you turn it on." : ""}</figcaption></figure>` : ""}
      </div>
      <div class="wl-steps"></div>
    </div>
    <div class="wl-foot"><span>Open this again any time: <kbd>⌘K</kbd>, Welcome. <a href="#" data-a="words">The words Spliced uses</a></span><button class="icon-btn sm" data-a="done">Start browsing</button></div>
  </div></div>`);
  document.body.append(sheet);
  requestAnimationFrame(() => sheet?.classList.add("in"));
  $('[data-a="x"]', sheet).onclick = close;
  $('[data-a="done"]', sheet).onclick = close;
  $('[data-a="words"]', sheet).onclick = (e) => { e.preventDefault(); close(); window.Tips?.glossary(); };
  sheet.addEventListener("mousedown", (e) => { if (e.target === sheet) close(); });
  sheet.tabIndex = -1;
  sheet.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } });
  sheet.focus();
  paint(null);
  // what is set up on this machine arrives a moment later (the server asks each program for its version)
  fetch("/api/doctor", { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).then((d) => d && paint(d)).catch(() => {});
}

function close() {
  if (!sheet) return;
  localStorage.setItem(SEEN, "1");
  const s = sheet; sheet = null;
  $("video", s)?.pause();
  s.classList.remove("in");
  setTimeout(() => s.remove(), 180);
}

/** Called once the app has loaded: shows the welcome to someone who has not seen it in this browser. */
function maybe(opts = {}) {
  if (opts.boards) boards = opts.boards;
  if (!localStorage.getItem(SEEN)) open();
}

return { open, close, maybe, seen: () => !!localStorage.getItem(SEEN) };
})();
