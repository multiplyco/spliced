/* Command palette (⌘K / Ctrl+K), Linear-style: every action and every place in one searchable list, so the
   screens can stay quiet. Views register what they can do:
     CR.command({ id, title, group, hint?, keys?, when?, run })   when() true = applies to the view on screen
     CR.uncommand(prefix)                                         drop every command whose id starts with prefix
   Places (scenes, films, boards, films in Build, moments) come from CR.sources: functions returning items. */
window.CR = window.CR || {};
CR.commands = CR.commands || new Map();
CR.sources = CR.sources || [];
CR.command = (c) => { CR.commands.set(c.id, c); };
CR.uncommand = (prefix) => { for (const id of [...CR.commands.keys()]) if (id.startsWith(prefix)) CR.commands.delete(id); };

/* ---------- the palette ---------- */
(() => {
"use strict";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const URL_RE = /^https?:\/\/\S+$/i;
const RECENT = "cr.paletteRecent";
let box = null, items = [], sel = 0, before = null;

// fuzzy score: every query word must appear in order-ish; earlier, word-start and shorter matches score higher
function score(text, q) {
  const t = text.toLowerCase(); let s = 0;
  for (const w of q.toLowerCase().split(/\s+/).filter(Boolean)) {
    const i = t.indexOf(w);
    if (i < 0) {
      // Letters in order but apart ("stg" for Settings) count only when they sit close together in something short,
      // a command or a name. Across a whole line any few letters turn up in order somewhere, and everything matches.
      if (t.length > 80) return -1;
      let best = Infinity;
      for (let from = t.indexOf(w[0]); from >= 0 && best > w.length; from = t.indexOf(w[0], from + 1)) {
        let k = 1, j = from + 1;
        for (; j < t.length && k < w.length; j++) if (t[j] === w[k]) k++;
        if (k === w.length) best = Math.min(best, j - from);
      }
      if (best > w.length * 2 + 2) return -1;
      s += 1;
    } else s += 10 + (i === 0 || /[\s/:·-]/.test(t[i - 1]) ? 8 : 0) - Math.min(5, i / 20);
  }
  return s - text.length / 200;
}
// films in production and every generated asset come from the server; fetched when search opens, kept a minute
let extra = [], extraAt = 0;
async function loadExtra() {
  if (Date.now() - extraAt < 60000) return;
  extraAt = Date.now();
  const out = [];
  const fu = SP.fileUrl;
  const fr = (file, t, w = 360) => `/api/frame?file=${encodeURIComponent(file)}&t=${(+t || 0).toFixed(2)}&w=${w}`;
  try {
    for (const p of await (await fetch("/api/productions")).json()) {
      const r = p.full || p.latest;
      for (const b of p.beats)   // each beat of a film in production: found by its name or by the note left on it
        out.push({ id: `build.${p.slug}.${b.id}`, title: b.title || b.id, sub: `${p.title} · beat ${b.n} · ${b.status}${b.review ? " · note: " + b.review : ""}`.slice(0, 120),
          text: `${b.title} ${b.id} ${b.review || ""} ${p.title} ${p.slug}`, group: "Beats in production", hash: `#/build/${p.slug}?beat=${encodeURIComponent(b.id)}` });
      out.push({ id: `build.${p.slug}`, title: p.title, sub: `${p.beats.length} beats${p.latest ? "" : " · not rendered yet"}`, text: `${p.title} ${p.slug} ${p.message || ""} ${p.beats.map((b) => b.title).join(" ")}`, group: "In production", hash: `#/build/${p.slug}`, thumb: r ? fr(r.file, (p.duration || 2) * 0.33) : "" });
    }
  } catch {}
  try {
    const a = await (await fetch("/api/assets")).json();
    for (const s of a.stacks || [])   // a render's frames are found as one thing; opening it shows every frame
      out.push({ id: `stack.${s.id}`, title: `${s.label || s.name} · ${s.count} frames`, sub: `${s.film} · ${s.source}`, text: `${s.label || ""} ${s.name} ${s.film} ${s.source} ${s.pattern} frames stack`, group: "Assets", hash: `#/assets?stack=${encodeURIComponent(s.id)}`, thumb: fu(s.cover) });
    for (const x of a.assets.filter((x) => x.type !== "audio" && !x.raw && x.source !== "placeholder" && !x.stack).slice(0, 600))
      out.push({ id: `asset.${x.file}`, title: x.label || x.name, sub: `${x.film} · ${x.source}`, text: `${x.label || ""} ${x.name} ${x.film} ${x.source} ${x.prompt || ""}`, group: "Assets", hash: `#/assets?film=${encodeURIComponent(x.film)}&q=${encodeURIComponent(x.name)}`, thumb: x.type === "video" ? fr(x.file, 0.6) : fu(x.file) });
    for (const x of a.assets.filter((x) => x.type === "audio" && !x.raw).slice(0, 400))
      out.push({ id: `asset.${x.file}`, title: x.label || x.name, sub: `${x.role} · ${x.film} · ${x.source}`, text: `${x.label || ""} ${x.name} ${x.film} ${x.role} ${x.source}`, group: "Sounds", hash: `#/assets?film=${encodeURIComponent(x.film)}&q=${encodeURIComponent(x.name)}&kind=${x.role}`, sound: true });
  } catch {}
  extra = out;
  if (box) paint(box.querySelector("input").value);
}
function all() {
  const cmds = [...CR.commands.values()].filter((c) => !c.when || c.when()).map((c) => ({ ...c, kind: "cmd", text: `${c.title} ${c.hint || ""} ${c.group || ""}` }));
  const places = [...CR.sources.flatMap((fn) => { try { return fn() || []; } catch { return []; } }), ...extra].map((p) => ({ ...p, kind: "place", text: p.text ? `${p.title} ${p.text}` : `${p.title} ${p.sub || ""} ${p.group || ""}` }));
  return { cmds, places };
}
// visual groups (tiles) in this order, then rows (commands, views, sounds)
const VISUAL = [["Scenes", 8], ["Your films", 8], ["Uploads", 8], ["Films", 4], ["Boards", 4], ["In production", 4], ["Moments", 4], ["Assets", 8]];
function results(q) {
  const { cmds, places } = all();
  const qq = q.trim();
  if (URL_RE.test(qq) && window.Imports) return { tiles: [], rows: [{ kind: "cmd", id: "imp.paste", title: `Add: ${qq}`, hint: "Import the film, or upload the image or clip", group: "Add", run: () => window.Imports.open(qq) }] };
  if (!qq) {
    const rec = JSON.parse(localStorage.getItem(RECENT) || "[]");
    const recent = rec.map((id) => cmds.find((c) => c.id === id) || places.find((p) => p.id === id)).filter(Boolean).map((x) => ({ ...x, group: "Recent" }));
    const boards = places.filter((p) => p.group === "Boards").slice(0, 4), builds = places.filter((p) => p.group === "In production").slice(0, 4);
    return { tiles: [["Boards", boards], ["In production", builds]].filter(([, l]) => l.length),
      rows: [...recent.slice(0, 5), ...places.filter((p) => p.group === "Views"), ...cmds.filter((c) => c.group !== "Go to").slice(0, 8)] };
  }
  const rank = (list) => list.map((x) => ({ x, s: score(x.text, qq) })).filter((r) => r.s >= 0).sort((a, b) => b.s - a.s).map((r) => r.x);
  const tiles = [];
  for (const [g, n] of VISUAL) { const hits = rank(places.filter((p) => p.group === g)); if (hits.length) tiles.push([g, hits.slice(0, n), hits.length]); }
  const rows = [
    ...(window.CR.filterLibrary ? [{ kind: "cmd", id: "", title: `Filter the Library by “${qq}”`, hint: "Every scene and upload whose text matches", group: "Library", run: () => window.CR.filterLibrary(qq) }] : []),
    ...rank(places.filter((p) => p.group === "Views")),
    ...["Beats in production", "Board beats", "Moves", "Styles", "Words"].flatMap((g) => rank(places.filter((p) => p.group === g)).slice(0, 5)),
    ...rank(cmds).slice(0, 8),
    ...rank(places.filter((p) => p.group === "Sounds")).slice(0, 6),
  ];
  return { tiles, rows };
}
function open() {
  if (box) { close(); return; }
  before = document.activeElement;
  box = h(`<div class="pal-scrim"><div class="cmdk wide" role="dialog" aria-label="Search">
    <div class="pal-in">${window.icon("search")}<input placeholder="Search everything: scenes, films, boards and their beats, films in production, moves, styles, assets, commands" spellcheck="false" autocomplete="off"><kbd>esc</kbd></div>
    <div class="pal-list" role="listbox"></div>
    <div class="pal-foot"><span><kbd>↑</kbd><kbd>↓</kbd><kbd>←</kbd><kbd>→</kbd> move</span><span><kbd>↵</kbd> open</span><span>paste a link to add it</span></div></div></div>`);
  document.body.append(box);
  requestAnimationFrame(() => box && box.classList.add("in"));
  const inp = box.querySelector("input");
  let t1; inp.oninput = () => { clearTimeout(t1); t1 = setTimeout(() => { sel = 0; paint(inp.value); }, 60); };
  inp.onkeydown = (e) => {
    const cur = items[sel], tileStep = cur && cur.tile ? 1 : 0;
    if (e.key === "ArrowDown" || (e.key === "n" && e.ctrlKey)) { e.preventDefault(); sel = nextRow(1); mark(); }
    else if (e.key === "ArrowUp" || (e.key === "p" && e.ctrlKey)) { e.preventDefault(); sel = nextRow(-1); mark(); }
    else if (e.key === "ArrowRight" && tileStep && inp.selectionStart === inp.value.length) { e.preventDefault(); sel = Math.min(items.length - 1, sel + 1); mark(); }
    else if (e.key === "ArrowLeft" && tileStep && inp.selectionStart === inp.value.length && sel > 0) { e.preventDefault(); sel = sel - 1; mark(); }
    else if (e.key === "Enter") { e.preventDefault(); run(items[sel]); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
    e.stopPropagation();
  };
  box.addEventListener("mousedown", (e) => { if (e.target === box) close(); });
  paint(""); inp.focus(); loadExtra();
}
// up and down jump between rows of tiles (a group) and list rows; left and right move inside a group
function nextRow(dir) {
  const cur = items[sel]; if (!cur) return 0;
  let i = sel + dir;
  if (cur.tile) { while (i >= 0 && i < items.length && items[i].tile && items[i].group === cur.group) i += dir; if (dir < 0 && i >= 0 && items[i]?.tile) { const g = items[i].group; while (i > 0 && items[i - 1].tile && items[i - 1].group === g) i--; } }
  return Math.max(0, Math.min(items.length - 1, i));
}
function close() { if (!box) return; const b = box; box = null; b.classList.remove("in"); setTimeout(() => b.remove(), 140); before?.focus?.(); }
function paint(q) {
  if (!box) return;
  const { tiles, rows } = results(q);
  items = [];
  const list = box.querySelector(".pal-list"); list.innerHTML = "";
  if (!tiles.length && !rows.length) { list.append(h(`<div class="pal-empty">Nothing matches “${esc(q)}”</div>`)); return; }
  for (const [g, hits, total] of tiles) {
    const more = total > hits.length && g === "Scenes" && window.CR.filterLibrary;
    const sec = h(`<div class="pal-sec"><div class="pal-g">${esc(g)}<span>${total || hits.length}</span>${more ? `<button class="pal-more">Show all ${total} in the Library</button>` : ""}</div><div class="pal-tiles ${g === "Boards" ? "boards" : ""}"></div></div>`);
    if (more) sec.querySelector(".pal-more").onclick = () => { close(); window.CR.filterLibrary(q); };
    const grid = sec.querySelector(".pal-tiles");
    for (const x of hits) {
      const i = items.length; items.push({ ...x, tile: true });
      const pic = x.thumbs ? `<div class="pal-mosaic n${Math.min(4, x.thumbs.length)}">${x.thumbs.map((u) => `<img loading="lazy" alt="" src="${esc(u)}">`).join("")}</div>` : x.thumb ? `<img loading="lazy" alt="" src="${esc(x.thumb)}">` : `<span class="pal-noimg">${window.icon("image")}</span>`;
      const el = h(`<button class="pal-tile" data-i="${i}"><div class="pic">${pic}</div><span class="t">${esc(x.title)}</span><span class="s">${esc(x.sub || "")}</span></button>`);
      el.onmousemove = () => { if (sel !== i) { sel = i; mark(false); } };
      el.onclick = () => run(x);
      grid.append(el);
    }
    list.append(sec);
  }
  let g = null;
  for (const x of rows) {
    if (x.group !== g) { g = x.group; list.append(h(`<div class="pal-g">${esc(g || "")}</div>`)); }
    const i = items.length; items.push(x);
    const el = h(`<button class="pal-it" role="option" data-i="${i}">${x.sound ? window.icon("audio-lines") : ""}<span class="t">${esc(x.title)}</span>${x.sub || x.hint ? `<span class="s">${esc(x.sub || x.hint)}</span>` : ""}${x.keys ? `<kbd>${esc(x.keys)}</kbd>` : ""}</button>`);
    el.onmousemove = () => { if (sel !== i) { sel = i; mark(false); } };
    el.onclick = () => run(x);
    list.append(el);
  }
  sel = Math.min(sel, items.length - 1);
  mark();
}
function mark(scroll = true) {
  box.querySelectorAll(".pal-it, .pal-tile").forEach((el) => el.classList.toggle("on", +el.dataset.i === sel));
  if (scroll) box.querySelector(`[data-i="${sel}"]`)?.scrollIntoView({ block: "nearest" });
}
function run(x) {
  if (!x) return;
  if (x.id) { const rec = JSON.parse(localStorage.getItem(RECENT) || "[]").filter((id) => id !== x.id); localStorage.setItem(RECENT, JSON.stringify([x.id, ...rec].slice(0, 8))); }
  close();
  setTimeout(() => { if (x.kind === "place" && x.hash) location.hash = x.hash; else x.run?.(); }, 0);
}
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === "k") { e.preventDefault(); e.stopPropagation(); open(); }
}, true);
CR.openPalette = open;
// the views every app has
CR.sources.push(() => [["Library", "#/scenes"], ["Moments", "#/moments"], ["Films", "#/films"], ["Moves", "#/moves"], ["Systems", "#/film/system-moves"], ["Styles", "#/styles"], ["Boards", "#/boards"], ["Build", "#/build"], ["Assets", "#/assets"], ["Setup", "#/setup"], ["Settings", "#/settings"]]
  .map(([t, hash]) => ({ id: `view.${t}`, title: t, group: "Views", hash })));
CR.command({ id: "app.theme", title: "Change theme (system, light, dark)", group: "App", run: () => document.querySelector('#status [data-a="theme"]')?.click() });
CR.command({ id: "app.help", title: "Keyboard shortcuts", group: "App", keys: "?", run: () => document.dispatchEvent(new KeyboardEvent("keydown", { key: "?" })) });
})();
