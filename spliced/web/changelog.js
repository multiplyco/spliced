/* What's new: the version of Spliced that is running, and the list of what changed, newest first.

   The list is web/changelog.md, written for the person using the app: a `## ` title, the date on the next line,
   one line in *italics*, then paragraphs and at most a picture. This file reads it, shows it in a sheet that
   scrolls, and remembers the newest entry seen in this browser, so the Settings icon can say "there is news". */
window.Changelog = (() => {
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const SEEN = "cr.changelogSeen";
let entries = null, sheet = null;

const inline = (s) => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");

/** changelog.md -> [{title, date, lead, body: [html], image: {src, alt}?, key}], newest first as written. */
const MARK = /^<!-- release (\d+\.\d+\.\d+) (\d{4}-\d{2}-\d{2}) -->\s*$/m;
function parse(md) {
  const out = [], parts = md.split(/^## /m);
  // A release is marked above the entries it contains (scripts/release.py). Entries above the first mark are in
  // this build but in no release yet: their version is "".
  let version = parts[0].match(MARK)?.[1] || "";
  for (const raw of parts.slice(1)) {
    const next = raw.match(MARK)?.[1], part = raw.replace(MARK, "");
    const lines = part.split("\n");
    const e = { title: lines[0].trim(), date: "", lead: "", body: [], image: null, version };
    if (next) version = next;
    const blocks = lines.slice(1).join("\n").split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
    for (const b of blocks) {
      const first = b.split("\n");
      if (!e.date && /^\d{4}-\d{2}-\d{2}/.test(first[0])) {   // the date line, with the one-line summary right under it
        e.date = first[0].slice(0, 10);
        const lead = first.slice(1).join(" ").trim().match(/^\*(.+)\*$/);
        if (lead) e.lead = lead[1];
        continue;
      }
      const img = b.match(/^!\[([^\]]*)\]\(([\w./-]+)\)$/);
      if (img) { e.image = { alt: img[1], src: img[2] }; continue; }
      const lead = b.replace(/\n/g, " ").match(/^\*([^*].*)\*$/);
      if (lead && !e.lead && !e.body.length) { e.lead = lead[1]; continue; }
      e.body.push(inline(b.replace(/\n/g, " ")));
    }
    e.key = `${e.date} ${e.title}`;
    out.push(e);
  }
  return out;
}

async function load() {
  if (entries) return entries;
  try {
    const r = await fetch("changelog.md", { cache: "no-store" });
    entries = r.ok ? parse(await r.text()) : [];
  } catch { entries = []; }
  return entries;
}

/** How many entries are newer than the one last seen in this browser (all of them, the first time). */
async function unseen() {
  const list = await load(), seen = localStorage.getItem(SEEN);
  const i = list.findIndex((e) => e.key === seen);
  return i < 0 ? list.length : i;
}

const pretty = (d) => { const t = new Date(d + "T12:00:00"); return isNaN(t) ? d : t.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }); };
/** The version as Settings shows it: "0.3.0", and the build when the app runs from a checkout. */
const version = () => (window.SPLICED?.version || "") + (window.SPLICED?.build ? ` · build ${window.SPLICED.build}` : "");

async function open() {
  if (sheet) return;
  // "New" marks what arrived since you last looked. The first time there is no "last", so nothing is marked.
  const list = await load(), fresh = localStorage.getItem(SEEN) ? await unseen() : 0;
  const released = list.some((e) => e.version);   // before the first release there are no versions to show
  sheet = h(`<div class="imp-scrim cl"><div class="imp-sheet cl-sheet" role="dialog" aria-label="What's new in Spliced">
    <div class="imp-head cl-head"><h2>What's new</h2><span class="cl-ver">Spliced ${esc(version())}</span><button class="icon-btn ghost sm sq" data-a="x" title="Close (Esc)">${window.icon("x")}</button></div>
    <div class="cl-list">${list.length ? list.map((e, i) => `<article class="cl-entry">
      <header><h3>${esc(e.title)}${i < fresh ? `<span class="cl-new">New</span>` : ""}</h3>${released ? `<span class="cl-v" title="${e.version ? `Arrived in Spliced ${esc(e.version)}` : "In this build, and in the next release"}">${e.version ? esc(e.version) : "Next release"}</span>` : ""}<time datetime="${esc(e.date)}">${esc(pretty(e.date))}</time></header>
      ${e.lead ? `<p class="cl-lead">${inline(e.lead)}</p>` : ""}${e.body.map((p) => `<p>${p}</p>`).join("")}
      ${e.image ? `<figure><img loading="lazy" alt="${esc(e.image.alt)}" src="${esc(e.image.src)}"></figure>` : ""}</article>`).join("")
      : `<p class="cl-lead">The list of changes couldn't be read.</p>`}</div></div></div>`);
  document.body.append(sheet);
  requestAnimationFrame(() => sheet?.classList.add("in"));
  const close = () => { const s = sheet; sheet = null; s.classList.remove("in"); setTimeout(() => s.remove(), 180); };
  $('[data-a="x"]', sheet).onclick = close;
  sheet.addEventListener("mousedown", (e) => { if (e.target === sheet) close(); });
  sheet.tabIndex = -1;
  sheet.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } });
  sheet.focus();
  if (list.length) localStorage.setItem(SEEN, list[0].key);   // opening it is seeing it
  document.dispatchEvent(new CustomEvent("spliced:changelog-seen"));
}

return { open, unseen, version, parse, first: () => !localStorage.getItem(SEEN) };
})();
