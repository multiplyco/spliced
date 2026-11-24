/* The asset library (#/assets): every still, clip and sound the films are made of, across films: Higgsfield
   generations, ElevenLabs music, voice and effects, design exports. Two parts: Visuals (stills and clips as a grid,
   clips play on hover) and Sound (a track list with a player docked at the bottom, like a music app: arrows step
   through, it plays on to the next). Every sound gets a small cover drawn in code from its data (see cover()).
   Data: /api/assets (film.py library_assets). */
window.AssetsView = (() => {
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const icon = (n) => window.icon(n);
const fileUrl = SP.fileUrl;
const SOURCES = { upload: "Uploaded", higgsfield: "Higgsfield", elevenlabs: "ElevenLabs", pexels: "Pexels", pixabay: "Pixabay", unsplash: "Unsplash", nasa: "NASA", openverse: "Openverse", stock: "Stock", code: "Made in code", blender: "Blender", design: "Design", placeholder: "Placeholder", reference: "Reference still", other: "Other" };
const VKINDS = [["all", "All"], ["still", "Stills"], ["clip", "Clips"]];
const SKINDS = [["all", "All"], ["music", "Music"], ["voice", "Voice"], ["effect", "Effects"]];
const SOUND = new Set(["music", "voice", "effect"]);
const ago = (s) => { const d = Date.now() / 1000 - s; return d < 3600 ? `${Math.max(1, Math.floor(d / 60))}m ago` : d < 86400 ? `${Math.floor(d / 3600)}h ago` : `${Math.floor(d / 86400)}d ago`; };
const size = (b) => b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.round(b / 1e3)} KB`;
let data = null, raf = 0;
const f = { view: "visuals", kind: "all", source: "all", film: "", q: "", extras: false, stack: "" };   // source: all assets unless picked; stack: the one that is open

function readHash() {
  const p = new URLSearchParams(location.hash.split("?")[1] || "");
  f.kind = p.get("kind") || "all"; f.view = p.get("view") === "sound" || SOUND.has(f.kind) ? "sound" : "visuals"; f.source = p.get("source") || "all"; f.film = p.get("film") || ""; f.q = p.get("q") || ""; f.extras = p.get("extras") === "1"; f.stack = p.get("stack") || "";
}
function writeHash() {
  const p = new URLSearchParams();
  if (f.view === "sound") p.set("view", "sound"); if (f.kind !== "all") p.set("kind", f.kind); if (f.source !== "all") p.set("source", f.source);
  if (f.film) p.set("film", f.film); if (f.q) p.set("q", f.q); if (f.extras) p.set("extras", "1"); if (f.stack) p.set("stack", f.stack);
  history.replaceState(null, "", "#/assets" + (p.toString() ? "?" + p : ""));
}
const role = (a) => a.type === "audio" ? a.role : a.type === "video" ? "clip" : "still";
// whose it is: its film, or for a file put straight into one of the project's folders (or the shared assets/), that folder
const whose = (a) => a.film || (window.Folders ? Folders.name(a.folder) : "");
const byFolder = () => window.Folders?.any();
function match(a, ignore) {
  if (ignore !== "view" && (a.type === "audio") !== (f.view === "sound")) return false;
  if (ignore !== "kind" && ignore !== "view" && f.kind !== "all" && role(a) !== f.kind) return false;
  // made for the films: generated, rendered in Blender, or a sound made in code (the films' own effects)
  if (ignore !== "source" && f.source === "generated" && !(a.generated || a.source === "blender" || (a.type === "audio" && a.source === "code"))) return false;
  if (ignore !== "source" && f.source === "stock" && !a.stock) return false;
  if (ignore !== "source" && !["generated", "all", "stock"].includes(f.source) && a.source !== f.source) return false;
  if (f.film && a.film !== f.film) return false;
  if (ignore !== "folder" && byFolder() && !Folders.matches(a.folder)) return false;
  if (!f.extras && (a.raw || a.source === "placeholder")) return false;
  if (f.q) { const t = `${a.name} ${a.label || ""} ${a.file} ${a.prompt || ""} ${a.note || ""}`.toLowerCase(); for (const w of f.q.toLowerCase().split(/\s+/).filter(Boolean)) if (!t.includes(w)) return false; }
  return true;
}

async function render(main) {
  stop(); readHash();
  main.innerHTML = `<div class="view-head"><h1>Assets</h1><span class="meta">Loading…</span></div>`;
  try { data = await (await fetch("/api/assets")).json(); } catch { main.innerHTML = `<div class="empty">Spliced's server isn't answering. Start it with <b>${SP.cmd("open")}</b>.</div>`; return; }
  if (!location.hash.startsWith("#/assets")) return;
  draw(main);
}
/* ---------- stacks: the frames of one render shown as one card ----------
   The server marks every frame with its stack (film.py stack_assets) and still lists each one. Here a stack is one
   tile: its middle frame, the count, and the frames running under the pointer. Opening it shows every frame, each
   still its own asset with its own path. */
const stackOf = (id) => (data.stacks || []).find((s) => s.id === id);
const framesOf = (id) => data.assets.filter((a) => a.stack === id).sort((a, b) => a.frame - b.frame);
/** The filtered list with each stack folded into one entry, where it first appears: assets and {stack, frames}. */
function folded(list) {
  const out = [], at = new Map();
  for (const a of list) {
    const s = a.stack && stackOf(a.stack);
    if (!s) { out.push(a); continue; }
    if (at.has(s.id)) at.get(s.id).frames.push(a); else { const e = { stack: s, frames: [a] }; at.set(s.id, e); out.push(e); }
  }
  return out.map((e) => (e.stack && e.frames.length === 1 ? e.frames[0] : e));   // a search that finds one frame shows that frame
}
function stackTile(e, i, main) {
  const s = e.stack, frames = e.frames.slice().sort((a, b) => a.frame - b.frame), cover = frames[Math.floor(frames.length / 2)];
  const part = frames.length < s.count ? `${frames.length} of ${s.count}` : `${s.count}`;
  const el = h(`<button class="as-tile stack ${s.used === false ? "unused" : ""}" style="animation-delay:${Math.min(i, 30) * 14}ms" title="${esc(`${s.pattern}\nA stack: ${s.count} frames, ${s.first} to ${s.last}. Move across it to run through them; click to open every frame.`)}">
    <div class="th"><img loading="lazy" alt="" src="${fileUrl(cover.file)}"><span class="stk">${icon("layout-list")}${part} frames</span><i class="run"></i></div>
    <div class="cap"><span class="nm">${esc(s.label || s.name)}</span><span class="sub">${esc(whose(s))} · ${esc(SOURCES[s.source] || s.source)}${s.used === false ? " · not used" : ""}</span></div></button>`);
  // moving across the tile runs through the frames: a dozen of them, evenly spread, so a long render doesn't load whole
  const pick = Array.from({ length: Math.min(12, frames.length) }, (_, k) => frames[Math.round((k * (frames.length - 1)) / Math.max(1, Math.min(12, frames.length) - 1))]);
  const th = $(".th", el), img = $("img", el), run = $(".run", el);
  th.onmousemove = (ev) => { const r = th.getBoundingClientRect(), x = Math.max(0, Math.min(0.999, (ev.clientX - r.left) / r.width)), a = pick[Math.floor(x * pick.length)]; const u = fileUrl(a.file); if (img.getAttribute("src") !== u) img.src = u; run.style.width = `${x * 100}%`; };
  th.onmouseleave = () => { img.src = fileUrl(cover.file); run.style.width = "0"; };
  el.onclick = () => { f.stack = s.id; writeHash(); draw(main); main.scrollTop = 0; };
  return el;
}
function drawStack(main) {
  const s = stackOf(f.stack), frames = framesOf(f.stack);
  main.innerHTML = "";
  const back = () => { f.stack = ""; writeHash(); draw(main); };
  if (!s) { main.append(h(`<div class="view-head"><h1><a class="crumb" href="#/assets">Assets</a></h1></div>`), h(`<div class="empty">That stack is gone: its frames were removed or renamed.</div>`)); return; }
  const w = s.pattern.split("#").length - 1, num = (n) => String(n).padStart(w, "0");
  const head = h(`<div class="view-head"><h1><a class="crumb" href="#/assets" data-a="back">Assets</a><span class="sep">/</span><span class="nm">${esc(s.label || s.name)}</span></h1>
    <span class="meta">${s.count} frames, ${num(s.first)} to ${num(s.last)} · ${esc(whose(s))} · ${esc(SOURCES[s.source] || s.source)} · ${size(s.size)}</span><span class="spacer"></span>
    <button class="icon-btn sm" data-a="pattern" title="Copy the frames' path, with # for the number: what to hand to your AI or to code that plays the sequence">${icon("copy")}Copy the path</button></div>`);
  $('[data-a="back"]', head).onclick = (ev) => { ev.preventDefault(); back(); };
  $('[data-a="pattern"]', head).onclick = () => navigator.clipboard?.writeText(s.pattern).then(() => window.crToast?.(`Copied: ${s.pattern}`));
  main.append(head);
  const grid = h(`<div class="as-grid frames"></div>`);
  frames.forEach((a, i) => { const t = tile(a, i, frames); $(".nm", t).textContent = `Frame ${num(a.frame)}`; $(".sub", t).textContent = a.name; grid.append(t); });
  main.append(grid);
  main.append(h(`<p class="as-foot">Each frame is its own file and can be used on its own. The stack is only how they are shown.</p>`));
}

function draw(main) {
  document.body.dataset.dropFilm = upTargetSafe();
  if (f.stack && f.view === "visuals") return drawStack(main);
  const all = data.assets, list = all.filter((a) => match(a));
  const gen = all.filter((a) => a.generated);
  main.innerHTML = "";
  const nv = all.filter((a) => a.type !== "audio" && match(a, "view")).length, ns = all.filter((a) => a.type === "audio" && match(a, "view")).length;
  const head = h(`<div class="view-head"><h1>Assets</h1><div class="seg as-view" id="as-view"><button data-v="visuals" class="${f.view === "visuals" ? "on" : ""}">${icon("image")}Visuals<span class="c">${nv}</span></button><button data-v="sound" class="${f.view === "sound" ? "on" : ""}">${icon("audio-lines")}Sound<span class="c">${ns}</span></button></div><span class="spacer"></span>
    <label class="as-search" title="${f.view === "sound" ? "Names, prompts and notes of the films' sounds" : "Your films' stills and clips, and below them photos and clips from free libraries (Pexels, Pixabay, Unsplash, NASA, Openverse) to add to a film"}">${icon("search")}<input placeholder="${f.view === "sound" ? "Search sounds" : "Search assets and free libraries"}" value="${esc(f.q)}" spellcheck="false"></label>
    <button class="icon-btn sm solid" data-a="upload" title="Add your own files to a film from this computer (or drop them anywhere here)">${icon("upload")}Upload</button></div>`);
  $('[data-a="upload"]', head).onclick = (e) => uploadPop(e.currentTarget, main);
  head.querySelectorAll("#as-view button").forEach((b) => (b.onclick = () => { if (f.view === b.dataset.v) return; f.view = b.dataset.v; f.kind = "all"; writeHash(); if (f.view !== "sound") stop(); draw(main); }));
  main.append(head);
  if (byFolder()) main.append(Folders.chips(() => draw(main), Folders.count(all.filter((a) => match(a, "folder")), (a) => a.folder)));
  const KINDS = f.view === "sound" ? SKINDS : VKINDS;
  const counts = Object.fromEntries(KINDS.map(([k]) => [k, all.filter((a) => match({ ...a }, "kind") && (k === "all" || role(a) === k)).length]));
  const glyph = (k) => f.view === "sound" && k !== "all" ? `<span class="as-glyph">${cover({ role: k, file: k, name: k, source: "elevenlabs" }, true)}</span>` : "";
  const bar = h(`<div class="as-bar"><div class="seg" id="as-kind">${KINDS.map(([k, l]) => `<button data-v="${k}" class="${f.kind === k ? "on" : ""}">${glyph(k)}${l}<span class="c">${counts[k]}</span></button>`).join("")}</div>
    <span class="spacer"></span>
    <select id="as-source" title="What made it"><option value="all">All assets</option><option value="generated">Made for the films</option><option value="stock">Stock footage</option>${Object.entries(SOURCES).map(([k, l]) => `<option value="${k}">${l}</option>`).join("")}</select>
    <select id="as-film" title="Film"><option value="">All films</option>${data.films.filter((x) => !byFolder() || Folders.matches(x.folder) || x.slug === f.film).map((x) => `<option value="${esc(x.slug)}">${esc(x.slug)}${x.engine === "beds" ? " (beds)" : ""}</option>`).join("")}</select>
    <label class="as-chk" title="Placeholders and raw takes"><input type="checkbox" ${f.extras ? "checked" : ""}> Drafts</label></div>`);
  main.append(bar);
  $("#as-source", bar).value = f.source; $("#as-film", bar).value = f.film;
  bar.querySelectorAll("#as-kind button").forEach((b) => (b.onclick = () => { f.kind = b.dataset.v; writeHash(); draw(main); }));
  $("#as-source", bar).onchange = (e) => { f.source = e.target.value; writeHash(); draw(main); };
  $("#as-film", bar).onchange = (e) => { f.film = e.target.value; writeHash(); draw(main); };
  $(".as-chk input", bar).onchange = (e) => { f.extras = e.target.checked; writeHash(); draw(main); };
  $(".as-search input", head).onkeydown = (e) => { if (e.key === "Enter") { clearTimeout(extT); f.q = e.target.value.trim(); writeHash(); draw(main); searchExt(main, true); } };
  let qT; $(".as-search input", head).oninput = (e) => { clearTimeout(qT); qT = setTimeout(() => { f.q = e.target.value.trim(); writeHash(); const pos = e.target.selectionStart; draw(main); const inp = $(".as-search input", main); inp.focus(); inp.setSelectionRange(pos, pos); clearTimeout(extT); extT = setTimeout(() => searchExt(main), 450); }, 200); };

  const ext = f.view === "visuals" && f.q.length >= 2;   // a search in Visuals reaches the free libraries too
  if (!list.length) {
    main.append(h(`<div class="empty${ext ? " sm" : ""}">${ext ? `Nothing in the films' assets matches “${esc(f.q)}”.` : `Nothing here with these filters.${f.source === "generated" ? " Made for the films means Higgsfield, ElevenLabs, Blender and sounds made in code; pick <b>All assets</b> to see everything." : ""}`}</div>`));
    if (ext) extSection(main); else if (f.view === "sound") main.append(playerBar());
    return;
  }
  if (f.view === "visuals") {
    if (ext) main.append(h(`<h2 class="as-h">In the films <span>${list.length}</span></h2>`));
    // with folders and none picked: a group per folder, so a client's or a kind of video's files sit together
    const sets = byFolder() && !Folders.filter() && !f.film ? Folders.groups(list, (a) => a.folder).filter((g) => g.items.length) : [{ items: list }];
    let left = 400;
    for (const g of sets) {
      if (sets.length > 1 || (byFolder() && !Folders.filter() && !f.film)) main.append(h(`<h2 class="as-h" title="${esc(g.folder ? `${g.folder}/ and its films` : "Files in no folder: shared by every one")}">${esc(g.name)} <span>${g.items.length}</span></h2>`));
      const grid = h(`<div class="as-grid"></div>`);
      folded(g.items).slice(0, left).forEach((x, i) => grid.append(x.stack ? stackTile(x, i, main) : tile(x, i)));
      left -= grid.children.length;
      main.append(grid);
      if (left <= 0) break;
    }
    if (ext) extSection(main);
  } else soundList(main, list);
  main.append(h(`<p class="as-foot">Prompts, models and credits show when the film's <code>assets.json</code> records them. Files come from <code>remotion/public/films/</code>, <code>videos/*/assets/</code>${byFolder() ? `, the project's folders (${Folders.list().map((x) => `<code>${esc(x.folder)}/</code>`).join(", ")})` : ""} and <code>music/</code>.</p>`));
  if (f.view === "sound") main.append(playerBar());
}
function tile(a, i, among) {   // among: the frames of the stack this one is shown in, so the viewer can step through them
  const src = a.type === "video" ? `/api/frame?file=${encodeURIComponent(a.file)}&t=0.6&w=480&v=${Math.round(a.mtime)}` : fileUrl(a.file);
  const el = h(`<button class="as-tile ${a.used === false ? "unused" : ""}" style="animation-delay:${Math.min(i, 30) * 14}ms" title="${esc(a.file)}">
    <div class="th"><img loading="lazy" alt="" src="${src}">${a.type === "video" ? `<span class="vid">${icon("play")}</span>` : ""}</div>
    <div class="cap"><span class="nm">${esc(a.label || a.name)}</span><span class="sub">${esc(whose(a))} · ${esc(SOURCES[a.source] || a.source)}${a.used === false ? " · not used" : ""}</span></div></button>`);
  if (a.type === "video") {
    const th = $(".th", el);
    el.onmouseenter = () => { if (th.querySelector("video")) return; const v = document.createElement("video"); v.muted = true; v.loop = true; v.playsInline = true; v.src = fileUrl(a.file); th.append(v); v.play().catch(() => {}); };
    el.onmouseleave = () => th.querySelector("video")?.remove();
  }
  el.onclick = () => preview(a, among);
  return el;
}
/* ---------- Sound: covers drawn from the data ----------
   One system, so a sound reads before it's heard:
   - the kind is the symbol and the hue: music is rings (a record), voice is speech bars, effects a mark that follows
     the name (whoosh: swept arcs, click/pin/type: a grid of points, hit/boom: a burst, riser: steps, glitch: a zigzag,
     anything else: nested diamonds). Hues come from the brand kit's state colours, never volt (volt is the playhead):
     music amber, voice blue, effects mint, each on the kit's ink.
   - the source is the ground: made in code gets a dot grid, ElevenLabs a clean ground, other files fine hatching.
   - the file name seeds the rest (ring gaps, bar heights, rotation), so every sound has its own cover and keeps it. */
const HUE = { music: "#FFB020", voice: "#6EA8FF", effect: "#3DDC97" };
const INK = "#131314", CHALK = "#F4F4F1", GREY = "#55555A", MID = "#85858B";
const hash = (str) => { let x = 2166136261; for (const c of String(str)) x = Math.imul(x ^ c.charCodeAt(0), 16777619); return x >>> 0; };
const rng = (seed) => () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const FX = [["whoosh", /whoosh|swoosh|swish|sweep|swipe|woosh|pass|fly|wind|air/], ["point", /click|tap|pin|pop|blip|tick|key|type|word|note|beep|ping|ding|drop-?let|button|ui/],
  ["burst", /hit|boom|impact|thud|slam|punch|bass|kick|stomp|crash|bang|land|drop/], ["rise", /rise|riser|build|swell|up|lift|grow|charge/],
  ["zig", /glitch|zap|static|noise|digital|buzz|err|shock|spark/]];
const fxShape = (a) => { const n = `${a.name} ${a.label || ""} ${a.dir || ""}`.toLowerCase(); return (FX.find(([, re]) => re.test(n)) || ["diamond"])[0]; };
const r2 = (x) => Math.round(x * 100) / 100;
function cover(a, glyphOnly) {
  const k = HUE[a.role] ? a.role : "effect", hue = HUE[k], R = rng(hash(a.file)), id = `g${hash(a.file + k).toString(36)}`;
  let art = "";
  if (k === "music") {
    const n = 3 + Math.floor(R() * 3), cx = 20 + (R() - 0.5) * 4, cy = 20 + (R() - 0.5) * 4;
    for (let i = 0; i < n; i++) {
      const r = 6 + (i * 11) / Math.max(1, n - 1), c = 2 * Math.PI * r, gap = c * (0.12 + R() * 0.3), rot = Math.round(R() * 360);
      art += `<circle cx="${r2(cx)}" cy="${r2(cy)}" r="${r2(r)}" fill="none" stroke="${i === n - 1 || R() < 0.35 ? hue : i % 2 ? MID : CHALK}" stroke-width="${i === n - 1 ? 2.2 : 1.3}" stroke-dasharray="${r2(c - gap)} ${r2(gap)}" stroke-linecap="round" transform="rotate(${rot} ${r2(cx)} ${r2(cy)})"/>`;
    }
    art += `<circle cx="${r2(cx)}" cy="${r2(cy)}" r="2.6" fill="${hue}"/>`;
  } else if (k === "voice") {
    const n = 7, w = 2.8, gap = 1.9, x0 = 20 - (n * w + (n - 1) * gap) / 2, line = +(String(a.name).match(/(\d+)/)?.[1] || 0), hot = line ? line % n : Math.floor(R() * n);
    for (let i = 0; i < n; i++) {
      const env = Math.sin(((i + 0.5) / n) * Math.PI), hgt = 5 + env * (12 + R() * 12);
      art += `<rect x="${r2(x0 + i * (w + gap))}" y="${r2(20 - hgt / 2)}" width="${w}" height="${r2(hgt)}" rx="1.4" fill="${i === hot ? CHALK : hue}" opacity="${i === hot ? 1 : r2(0.55 + env * 0.45)}"/>`;
    }
  } else {
    const sh = fxShape(a), rot = Math.round(R() * 90);
    if (sh === "whoosh") for (let i = 0; i < 3; i++) { const r = 8 + i * 5; art += `<path d="M ${r2(8)} ${r2(30 - i * 2)} A ${r} ${r} 0 0 1 ${r2(10 + r * 1.1)} ${r2(12 - i * 2 + R() * 2)}" fill="none" stroke="${i === 1 ? hue : i ? MID : CHALK}" stroke-width="${i === 1 ? 2.4 : 1.5}" stroke-linecap="round"/>`; }
    else if (sh === "point") for (let y = 0; y < 3; y++) for (let x = 0; x < 3; x++) { const on = R() < 0.45 || (x === 1 && y === 1); art += `<circle cx="${12 + x * 8}" cy="${12 + y * 8}" r="${on ? 2.6 : 1.4}" fill="${on ? hue : GREY}"/>`; }
    else if (sh === "burst") { const n = 8 + Math.floor(R() * 5); for (let i = 0; i < n; i++) { const t = (i / n) * Math.PI * 2 + rot / 57, l = 9 + R() * 7; art += `<line x1="${r2(20 + Math.cos(t) * 5)}" y1="${r2(20 + Math.sin(t) * 5)}" x2="${r2(20 + Math.cos(t) * l)}" y2="${r2(20 + Math.sin(t) * l)}" stroke="${i % 3 ? hue : CHALK}" stroke-width="1.6" stroke-linecap="round"/>`; } art += `<circle cx="20" cy="20" r="2.8" fill="${CHALK}"/>`; }
    else if (sh === "rise") for (let i = 0; i < 5; i++) { const hgt = 4 + i * 5 + R() * 2; art += `<rect x="${9 + i * 4.8}" y="${r2(31 - hgt)}" width="3.2" height="${r2(hgt)}" rx="1" fill="${i === 4 ? CHALK : hue}" opacity="${r2(0.5 + i * 0.12)}"/>`; }
    else if (sh === "zig") { let d = "M 8 20", up = R() < 0.5; for (let i = 1; i <= 6; i++) { d += ` L ${8 + i * 4} ${r2(20 + (up ? -1 : 1) * (4 + R() * 7))}`; up = !up; } art += `<path d="${d}" fill="none" stroke="${hue}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/><circle cx="32" cy="20" r="2" fill="${CHALK}"/>`; }
    else for (let i = 0; i < 3; i++) { const s0 = 16 - i * 4.5; art += `<rect x="${r2(20 - s0 / 2)}" y="${r2(20 - s0 / 2)}" width="${r2(s0)}" height="${r2(s0)}" rx="${i === 2 ? 1 : 2}" fill="${i === 2 ? hue : "none"}" stroke="${i === 2 ? "none" : i ? hue : MID}" stroke-width="1.4" transform="rotate(${45 + rot * (i - 1) / 3} 20 20)"/>`; }
  }
  if (glyphOnly) return `<svg viewBox="4 4 32 32" aria-hidden="true">${art}</svg>`;
  const ground = a.source === "code" ? `<pattern id="${id}" width="5" height="5" patternUnits="userSpaceOnUse"><circle cx="2.5" cy="2.5" r="0.55" fill="${CHALK}" opacity="0.16"/></pattern><rect width="40" height="40" fill="url(#${id})"/>`
    : a.source === "elevenlabs" ? "" : `<pattern id="${id}" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="4" stroke="${CHALK}" stroke-width="0.5" opacity="0.1"/></pattern><rect width="40" height="40" fill="url(#${id})"/>`;
  return `<svg viewBox="0 0 40 40" aria-hidden="true"><rect width="40" height="40" fill="${INK}"/><rect width="40" height="40" fill="${hue}" opacity="0.07"/>${ground}${art}</svg>`;
}

/* ---------- Sound: the list and the player ---------- */
const title = (a) => a.label || String(a.name).replace(/\.[a-z0-9]+$/i, "").replace(/[-_]+/g, " ").replace(/^\w/, (c) => c.toUpperCase());
const KIND = { music: "Music", voice: "Voice", effect: "Effect" };
const mmss = (t) => !isFinite(t) || t == null ? "" : `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const len = (t) => !isFinite(t) || t == null ? "" : t < 10 ? `${t.toFixed(1)}s` : mmss(t);   // effects are short: tenths count
const durs = new Map(), peaks = new Map();
// when a sound ends: play through the list, or loop it to hear it again and again (short effects); kept in this browser
let queue = [], cur = -1, now = null, audio = null, smode = localStorage.getItem("cr.sndMode") === "loop" ? "loop" : "through", durObs = null;
function soundList(main, list) {
  queue = list.slice(0, 600);
  cur = now ? queue.findIndex((a) => a.file === now.file) : -1;   // the sound playing keeps playing when the filters change
  const box = h(`<div class="sp-list"><div class="sp-hd"><span>#</span><span></span><span>Title</span><span>Film</span><span>Made with</span><span class="r">${icon("history")}</span><span></span></div></div>`);
  durObs?.disconnect();
  durObs = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { durObs.unobserve(e.target); measure(queue[+e.target.dataset.i], e.target); } }), { rootMargin: "200px" });
  queue.forEach((a, i) => {
    const el = h(`<div class="sp-row ${a.used === false ? "unused" : ""}" data-i="${i}" title="${esc(a.file)}">
      <span class="n"><span class="num">${i + 1}</span><span class="pl">${icon("play")}</span></span>
      <span class="sp-art">${cover(a)}</span>
      <div class="t"><span class="nm">${esc(title(a))}</span><span class="sub">${KIND[a.role] || a.role}${a.dir && a.dir !== "." ? ` · ${esc(a.dir)}` : ""}${a.used === false ? " · not used" : ""}</span></div>
      <span class="film">${esc(whose(a))}</span><span class="src">${esc(SOURCES[a.source] || a.source)}</span>
      <span class="dur r">${len(durs.get(a.file))}</span>
      <button class="icon-btn sm sq ghost tc-copy" data-copy="${esc(a.file)}" title="Copy the path">${icon("copy")}</button></div>`);
    el.onclick = (e) => { if (e.target.closest(".tc-copy")) return; i === cur && audio ? toggle() : playAt(i); };
    box.append(el); if (!durs.has(a.file)) durObs.observe(el);
  });
  main.append(box);
  paintRows();
}
let measuring = 0; const waitQ = [];
function measure(a, el) {   // a sound's length from its metadata, a few at a time
  if (!a) return;
  if (measuring >= 4) { waitQ.push([a, el]); return; }
  measuring++;
  const x = new Audio(); x.preload = "metadata";
  const done = () => { measuring--; x.src = ""; const nx = waitQ.shift(); if (nx) measure(...nx); };
  x.onloadedmetadata = () => { durs.set(a.file, x.duration); const d = el.querySelector(".dur"); if (d) d.textContent = len(x.duration); done(); };
  x.onerror = done; x.src = fileUrl(a.file);
}
function playerBar() {
  const el = h(`<div class="sp-player" id="sp-player">
    <div class="sp-now"><span class="sp-art lg"></span><div class="t"><span class="nm"></span><span class="sub"></span></div></div>
    <div class="sp-mid"><div class="sp-ctl">
        <button class="icon-btn sm sq ghost" data-a="prev" title="Previous (${KB.label(KB.get("sPrev")[0] || "ArrowUp")})">${icon("step-back")}</button>
        <button class="sp-pp" data-a="pp" title="Play / pause (Space)">${icon("play")}</button>
        <button class="icon-btn sm sq ghost" data-a="next" title="Next (${KB.label(KB.get("sNext")[0] || "ArrowDown")})">${icon("step-forward")}</button></div>
      <div class="sp-scrub"><span class="tm" id="sp-t">0:00</span><canvas id="sp-wave"></canvas><span class="tm" id="sp-d">0:00</span></div></div>
    <div class="sp-side"><div class="seg sm" id="sp-mode" role="radiogroup" aria-label="When a sound ends">
        <button data-v="through" title="Play through the list: the next sound starts when this one ends (L switches)">${icon("list-end")}Play through</button>
        <button data-v="loop" title="Loop this sound, to hear it again and again (L switches)">${icon("repeat-1")}Loop</button></div>
      <button class="icon-btn sm sq ghost" data-a="copy" title="Copy the path">${icon("copy")}</button></div></div>`);
  $('[data-a="prev"]', el).onclick = () => step(-1, true);
  $('[data-a="next"]', el).onclick = () => step(1);
  $('[data-a="pp"]', el).onclick = () => toggle();
  el.querySelectorAll("#sp-mode button").forEach((b) => (b.onclick = () => setSMode(b.dataset.v)));
  $('[data-a="copy"]', el).onclick = () => now && navigator.clipboard?.writeText(now.file).then(() => window.crToast?.("Path copied"));
  const cv = $("#sp-wave", el);
  let drag = false;
  const seekAt = (e) => { if (!audio || !audio.duration) return; const r = cv.getBoundingClientRect(); audio.currentTime = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * audio.duration; drawWave(); };
  cv.onpointerdown = (e) => { drag = true; cv.setPointerCapture(e.pointerId); seekAt(e); };
  cv.onpointermove = (e) => drag && seekAt(e);
  cv.onpointerup = () => (drag = false);
  requestAnimationFrame(() => { paintPlayer(); drawWave(); });
  return el;
}
function playAt(i) {
  const a = queue[i]; if (!a) return;
  if (audio) { audio.onended = null; audio.pause(); }
  cur = i; now = a; audio = new Audio(fileUrl(a.file));
  audio.loop = smode === "loop";
  audio.onended = () => { if (smode === "through" && cur >= 0 && cur < queue.length - 1) playAt(cur + 1); else { paintRows(); paintPlayer(); drawWave(); } };
  audio.onloadedmetadata = () => { durs.set(a.file, audio.duration); paintPlayer(); };
  audio.play().catch(() => {});
  loadPeaks(a);
  paintRows(); paintPlayer();
  document.querySelector(`.sp-row[data-i="${i}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  cancelAnimationFrame(raf);
  const tick = () => { raf = requestAnimationFrame(tick); drawWave(); const t = document.getElementById("sp-t"); if (t && audio) t.textContent = mmss(audio.currentTime); };
  tick();
}
function toggle() {
  if (!audio) { playAt(cur >= 0 ? cur : 0); return; }
  if (cur < 0 && audio.paused && audio.ended) { playAt(0); return; }
  if (audio.paused) audio.play().catch(() => {}); else audio.pause();
  paintRows(); paintPlayer();
}
function step(d, button) {   // the back button works like a music app's: a few seconds in, it restarts the sound first
  if (!queue.length) return;
  if (button && d < 0 && audio && audio.currentTime > 3) { audio.currentTime = 0; if (audio.paused) toggle(); return; }
  playAt(Math.max(0, Math.min(queue.length - 1, (cur < 0 ? (d > 0 ? -1 : 0) : cur) + d)));
}
function setSMode(m, viaKey) {
  smode = m; localStorage.setItem("cr.sndMode", m);
  if (audio) audio.loop = m === "loop";
  paintPlayer();
  if (viaKey) window.crToast?.(m === "loop" ? "Looping this sound" : "Playing through the list");
}
function paintRows() {
  const on = audio && !audio.paused;
  document.querySelectorAll(".sp-row").forEach((r) => {
    const me = +r.dataset.i === cur; r.classList.toggle("cur", me); r.classList.toggle("on", me && on);
    $(".pl", r).innerHTML = icon(me && on ? "pause" : "play");
  });
}
function paintPlayer() {
  const el = document.getElementById("sp-player"); if (!el) return;
  const a = now, on = audio && !audio.paused;
  el.classList.toggle("idle", !a);
  $(".sp-now .sp-art", el).innerHTML = a ? cover(a) : "";
  $(".sp-now .nm", el).textContent = a ? title(a) : "Nothing playing";
  $(".sp-now .sub", el).textContent = a ? `${KIND[a.role] || a.role} · ${whose(a)} · ${SOURCES[a.source] || a.source}` : "Pick a sound, or press ↓ to start";
  $('[data-a="pp"]', el).innerHTML = icon(on ? "pause" : "play");
  el.querySelectorAll("#sp-mode button").forEach((b) => b.classList.toggle("on", b.dataset.v === smode));
  $("#sp-d", el).textContent = a ? mmss(audio?.duration || durs.get(a.file)) : "0:00";
  if (!audio) $("#sp-t", el).textContent = "0:00";
}
let actx = null;
async function loadPeaks(a) {   // the waveform of the sound playing, for the scrubber
  if (peaks.has(a.file)) return;
  peaks.set(a.file, null);
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    const buf = await actx.decodeAudioData(await (await fetch(fileUrl(a.file))).arrayBuffer());
    const ch = buf.getChannelData(0), n = 160, step = Math.floor(ch.length / n) || 1, out = [];
    for (let i = 0; i < n; i++) { let m = 0; for (let j = i * step, e = Math.min(ch.length, j + step); j < e; j += 8) m = Math.max(m, Math.abs(ch[j])); out.push(m); }
    const top = Math.max(...out, 0.01); peaks.set(a.file, out.map((v) => v / top));
  } catch { peaks.delete(a.file); }
}
function drawWave() {
  const cv = document.getElementById("sp-wave"); if (!cv) return;
  const dpr = devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
  const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  const a = now, pk = a && peaks.get(a.file), p = audio && audio.duration ? audio.currentTime / audio.duration : 0;
  const cs = getComputedStyle(cv), played = cs.getPropertyValue("--wave-on").trim() || CHALK, rest = cs.getPropertyValue("--wave-off").trim() || GREY, head = cs.getPropertyValue("--wave-head").trim() || "#DFFF1A";
  if (pk) {
    const n = pk.length, bw = W / n;
    for (let i = 0; i < n; i++) { const hh = Math.max(1.5, pk[i] * (H - 4)); g.fillStyle = (i + 0.5) / n <= p ? played : rest; g.fillRect(i * bw + 0.5, (H - hh) / 2, Math.max(1, bw - 1.2), hh); }
  } else { g.fillStyle = rest; g.fillRect(0, H / 2 - 1, W, 2); g.fillStyle = played; g.fillRect(0, H / 2 - 1, W * p, 2); }
  if (a) { g.fillStyle = head; g.fillRect(Math.round(W * p) - 1, 1, 2, H - 2); }   // the playhead: volt, as the brand allows
}
function onKey(e) {
  if (f.view !== "sound" || !document.getElementById("sp-player")) return false;
  const K = window.KB;
  if (K.is(e, "sPlay")) { e.preventDefault(); toggle(); }
  else if (K.is(e, "sNext")) { e.preventDefault(); step(1); }
  else if (K.is(e, "sPrev")) { e.preventDefault(); step(-1); }
  else if (K.is(e, "sLoop")) { e.preventDefault(); setSMode(smode === "loop" ? "through" : "loop", true); }
  else if (K.is(e, "sBack") || K.is(e, "sFwd")) { e.preventDefault(); if (audio && audio.duration) audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + (K.is(e, "sFwd") ? 1 : -1) * (e.shiftKey ? 1 : 5))); }
  else return false;
  return true;
}
function preview(a, among) {
  const at = among ? among.indexOf(a) : -1, st = a.stack && stackOf(a.stack);
  const box = h(`<div class="imp-scrim as-lb"><div class="as-lb-in">
    <div class="as-lb-media">${a.type === "video" ? `<video src="${fileUrl(a.file)}" controls autoplay muted loop playsinline></video>` : `<img src="${fileUrl(a.file)}" alt="">`}</div>
    <div class="as-lb-side"><div class="imp-head"><h2>${esc(a.label || a.name)}</h2><button class="icon-btn sm sq ghost" data-a="x" title="Close (Esc)">${icon("x")}</button></div>
      ${st ? `<div class="as-step"><button class="icon-btn sm sq" data-a="prev" title="The frame before (←)" ${at > 0 ? "" : "disabled"}>${icon("chevron-left")}</button><span>${at >= 0 ? `Frame ${at + 1} of ${among.length}` : `Frame ${a.frame}`} in <a href="#/assets?stack=${encodeURIComponent(st.id)}" data-a="stack">${esc(st.label || st.name)}</a></span><button class="icon-btn sm sq" data-a="next" title="The frame after (→)" ${at >= 0 && at < among.length - 1 ? "" : "disabled"}>${icon("chevron-right")}</button></div>` : ""}
      <dl><dt>${a.film ? "Film" : "Folder"}</dt><dd>${esc(whose(a))}</dd>${a.film && a.folder ? `<dt>Folder</dt><dd>${esc(Folders.name(a.folder))}</dd>` : ""}<dt>Made with</dt><dd>${esc(SOURCES[a.source] || a.source)}${a.model ? ` · ${esc(a.model)}` : ""}</dd>
      ${a.credits != null ? `<dt>Credits</dt><dd>${esc(a.credits)}</dd>` : ""}
      ${a.author ? `<dt>By</dt><dd>${a.author_url ? `<a href="${esc(a.author_url)}" target="_blank" rel="noopener">${esc(a.author)}</a>` : esc(a.author)}</dd>` : ""}
      ${a.license ? `<dt>Licence</dt><dd>${a.license_url ? `<a href="${esc(a.license_url)}" target="_blank" rel="noopener">${esc(a.license)}</a>` : esc(a.license)}${a.credit ? `<br><span class="dim">${esc(a.credit)}</span>` : ""}</dd>` : ""}
      ${a.page ? `<dt>Source</dt><dd><a href="${esc(a.page)}" target="_blank" rel="noopener">Open the original</a></dd>` : ""}<dt>Used</dt><dd>${a.used == null ? "unknown" : a.used ? "in the film" : "not used"}</dd>
      <dt>File</dt><dd class="mono tc-copy" data-copy="${esc(a.file)}" title="Copy the path">${esc(a.file)}</dd><dt>Size</dt><dd>${size(a.size)} · ${ago(a.mtime)}</dd></dl>
      ${a.prompt ? `<h5>Prompt</h5><p class="as-prompt tc-copy" data-copy="${esc(a.prompt)}" title="Copy the prompt">${esc(a.prompt)}</p>` : `<p class="dim">No prompt recorded for this file.</p>`}
      ${a.engine === "remotion" ? `<a class="icon-btn sm" href="#/build/${esc(a.film)}/assets">${icon("list-video")}Open in Build</a>` : ""}</div></div></div>`);
  document.body.append(box); requestAnimationFrame(() => box.classList.add("in"));
  const close = () => { box.classList.remove("in"); setTimeout(() => box.remove(), 180); document.removeEventListener("keydown", key, true); };
  const step = (d) => { if (at < 0 || !among[at + d]) return; box.remove(); document.removeEventListener("keydown", key, true); preview(among[at + d], among); document.querySelector(".as-lb")?.classList.add("in"); };
  const key = (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } else if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); step(-1); } else if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); step(1); } };
  $('[data-a="prev"]', box)?.addEventListener("click", () => step(-1)); $('[data-a="next"]', box)?.addEventListener("click", () => step(1));
  $('[data-a="stack"]', box)?.addEventListener("click", () => close());
  document.addEventListener("keydown", key, true);
  $('[data-a="x"]', box).onclick = close; box.onmousedown = (e) => { if (e.target === box) close(); };
  $("a", box)?.addEventListener("click", close);
}
/* ---------- the same search in the free libraries (stock.py): photos and clips to add to a film ----------
   Under the films' own results, for the same words; the kind filter picks photos (Stills), clips (Clips) or both.
   Added files go into the film's stock/ folder with author and licence, and show above from then on. */
const KEY_HELP = { pexels: ["PEXELS_API_KEY", "https://www.pexels.com/api/"], pixabay: ["PIXABAY_API_KEY", "https://pixabay.com/api/docs/"], unsplash: ["UNSPLASH_ACCESS_KEY", "https://unsplash.com/developers"] };
const extCache = new Map();   // "q|kind" -> {loading, results, errors, missing}
let extT = 0, srcs = null, target = localStorage.getItem("cr.stockFilm") || "";
const extKinds = () => f.kind === "still" ? ["photo"] : f.kind === "clip" ? ["video"] : ["video", "photo"];
const extKey = () => `${f.q.toLowerCase()}|${extKinds().join(",")}`;
async function searchExt(main, now) {
  if (f.view !== "visuals" || f.q.length < 2) return;
  const key = extKey(); if (extCache.has(key) && !now) return paintExt();
  const q = f.q, kinds = extKinds();
  if (!srcs) { extCache.set(key, { loading: true }); paintExt(); try { srcs = (await (await fetch("/api/stock/sources")).json()).sources; } catch { srcs = []; } }
  // each library on its own, so the quick ones show while a slow one (Openverse can take 15 s) is still answering
  const ready = srcs.filter((x) => x.ready).map((x) => x.id);
  const st = { byReq: {}, errors: {}, waiting: new Set(ready), missing: srcs.filter((x) => !x.ready).map((x) => x.id) };
  extCache.set(key, st); paintExt();
  const per = Math.max(4, Math.round(24 / Math.max(1, ready.length * kinds.length)) + 2);
  await Promise.all(ready.flatMap((src) => kinds.map(async (k) => {
    try { const r = await (await fetch(`/api/stock/search?q=${encodeURIComponent(q)}&kind=${k}&source=${src}&n=${per}`)).json(); st.byReq[`${src}|${k}`] = r.results || []; Object.assign(st.errors, r.errors || {}); }
    catch (e) { st.errors[src] = e.message; }
    if (kinds.every((kk) => `${src}|${kk}` in st.byReq || st.errors[src])) st.waiting.delete(src);
    if (extKey() === key) paintExt();
  })));
}
// every library's results woven together: the first of each, then the second of each…
function extResults(st) {
  const lists = Object.values(st.byReq || {}), out = [];
  for (let i = 0; lists.some((l) => l[i]); i++) for (const l of lists) if (l[i]) out.push(l[i]);
  return out;
}
function extSection(main) {
  const films = data.films.filter((x) => x.engine === "remotion").map((x) => x.slug);
  if (f.film && films.includes(f.film)) target = f.film;
  if (!films.includes(target)) target = films[0] || "";
  const sec = h(`<section class="as-ext" id="as-ext"><h2 class="as-h">From free libraries <span>Pexels, Pixabay, Unsplash, NASA, Openverse</span><span class="spacer"></span>
      <label class="as-to">Add to <select title="The film added files go into">${films.map((x) => `<option ${x === target ? "selected" : ""}>${esc(x)}</option>`).join("")}</select></label></h2>
    <div class="as-ext-body"></div></section>`);
  $("select", sec).onchange = (e) => { target = e.target.value; localStorage.setItem("cr.stockFilm", target); };
  main.append(sec);
  if (!extCache.has(extKey())) { clearTimeout(extT); extT = setTimeout(() => searchExt(main), 450); }
  paintExt();
}
function paintExt() {
  const body = document.querySelector("#as-ext .as-ext-body"); if (!body) return;
  const r = extCache.get(extKey());
  const res = r ? extResults(r) : [], waiting = r?.waiting ? [...r.waiting] : [];
  if (!r || r.loading || (!res.length && waiting.length)) { body.innerHTML = `<div class="st-empty">${icon("loader")} Searching the free libraries for “${esc(f.q)}”…</div>`; return; }
  body.innerHTML = "";
  if (waiting.length) body.append(h(`<div class="as-ext-wait">${icon("loader")} Still asking ${esc(waiting.map((x) => SOURCES[x] || x).join(", "))}</div>`));
  const errs = Object.entries(r.errors || {}).filter(([k]) => !waiting.includes(k)).map(([k, v]) => `${SOURCES[k] || k}: ${/timeout|timed out|504/i.test(v) ? "didn't answer in time" : v}`);
  if (errs.length) body.append(h(`<div class="st-err">${esc(errs.join(" · "))}</div>`));
  if (!res.length) body.append(h(`<div class="st-empty">Nothing in the free libraries for “${esc(f.q)}”.</div>`));
  else {
    const grid = h(`<div class="as-grid"></div>`);
    res.forEach((x, i) => grid.append(extTile(x, i)));
    body.append(grid);
  }
  const off = (srcs || []).filter((x) => !x.ready);
  if (off.length) {
    const ln = h(`<p class="as-ext-keys">Also searchable with a free key: ${off.map((x) => `<span>${esc(SOURCES[x.id] || x.id)} <a href="${esc(KEY_HELP[x.id]?.[1] || "#")}" target="_blank" rel="noopener">get a key</a> · <button data-src="${esc(x.id)}">paste key</button></span>`).join(", ")}</p>`);
    ln.querySelectorAll("button").forEach((b) => (b.onclick = () => addKey(b.dataset.src)));
    body.append(ln);
  }
}
async function addKey(src) {
  const label = SOURCES[src] || src;
  const v = prompt(`Paste your ${label} API key${src === "unsplash" ? " (the Access Key, not the Secret key)" : ""}. It's saved in .env at the repo root, which git ignores.`);
  if (!v) return;
  try {
    const r = await fetch("/api/stock/key", { method: "POST", body: JSON.stringify({ source: src, value: v.trim() }) });
    const j = await r.json(); if (!r.ok) throw new Error(j.error);
    srcs = null; extCache.clear(); searchExt($("#main"), true);
  } catch (e) { alert(`Couldn't save the key: ${e.message}`); }
}
function extTile(x, i) {
  const el = h(`<div class="as-tile ext" style="animation-delay:${Math.min(i, 30) * 14}ms" title="${esc(x.title || "")}">
    <div class="th">${x.thumb ? `<img loading="lazy" alt="" src="${esc(x.thumb)}">` : ""}${x.kind === "video" ? `<span class="vid">${icon("play")}</span>` : ""}${x.duration ? `<span class="dur">${esc(x.duration)}s</span>` : ""}
      <button class="icon-btn sm primary st-add" title="Download into ${esc(target)}/stock, with its author and licence">${icon("plus")}Add</button></div>
    <div class="cap"><span class="nm">${esc(x.title || "(untitled)")}</span><span class="sub">${esc(SOURCES[x.source] || x.source)}${x.author ? ` · ${esc(x.author)}` : ""}${x.license ? ` · ${esc(x.license)}` : ""}</span></div></div>`);
  const th = $(".th", el);
  if (x.preview) {
    th.onmouseenter = () => { if (th.querySelector("video")) return; const v = document.createElement("video"); v.muted = true; v.loop = true; v.playsInline = true; v.src = x.preview; th.append(v); v.play().catch(() => {}); };
    th.onmouseleave = () => th.querySelector("video")?.remove();
  }
  $(".st-add", el).onclick = async (e) => {
    const b = e.currentTarget; b.disabled = true; b.innerHTML = `${icon("loader")}Adding`;
    try {
      const rr = await fetch("/api/stock/get", { method: "POST", body: JSON.stringify({ id: x.id, film: target, name: f.q }) });
      const j = await rr.json(); if (!rr.ok) throw new Error(j.error);
      b.innerHTML = `${icon("check")}Added`; b.classList.remove("primary");
      window.crToast?.(`Added to ${target}: ${j.path}`);
      // it's one of the films' assets now (stock): it shows under All assets and Stock footage
      try { data = await (await fetch("/api/assets")).json(); } catch {}
      if (!["all", "stock"].includes(f.source)) window.crToast?.(`Added to ${target}. Pick “All assets” or “Stock footage” to see it with the films' assets`, 4200);
    } catch (err) { b.disabled = false; b.innerHTML = `${icon("plus")}Add`; alert(`Couldn't add it: ${err.message}`); }
  };
  return el;
}
/* ---------- Upload: the person's own files into a film (stock.py add_file) ----------
   From this computer only (the file picker, or drop files anywhere on Assets). They land in
   remotion/public/films/<film>/uploads/ and in the film's assets.json as source "upload". Links (YouTube, a page)
   belong to the Library's Add reference, which downloads, analyses and breaks them down. */
let upPop = null;
const filmsForUpload = () => data.films.filter((x) => x.engine === "remotion").map((x) => x.slug);
function upTargetSafe() { try { return upTarget(); } catch { return ""; } }
function upTarget() { const fl = filmsForUpload(); if (f.film && fl.includes(f.film)) target = f.film; if (!fl.includes(target)) target = fl[0] || ""; return target; }
function closeUpPop() { if (!upPop) return; upPop.remove(); upPop = null; document.removeEventListener("pointerdown", upOutside, true); document.removeEventListener("keydown", upEsc, true); }
const upOutside = (e) => { if (upPop && !upPop.contains(e.target) && !e.target.closest('[data-a="upload"]')) closeUpPop(); };
const upEsc = (e) => { if (e.key === "Escape") { e.stopPropagation(); closeUpPop(); } };
function uploadPop(anchor, main) {
  if (upPop) return closeUpPop();
  const fl = filmsForUpload(); upTarget();
  upPop = h(`<div class="as-up" role="dialog" aria-label="Upload">
    <div class="as-up-hd"><b>Upload</b><button class="icon-btn sm sq ghost" data-a="x" title="Close (Esc)">${icon("x")}</button></div>
    <label class="as-up-to">Into <select>${fl.map((x) => `<option ${x === target ? "selected" : ""}>${esc(x)}</option>`).join("")}</select></label>
    <button class="as-up-file" data-a="pick">${icon("folder-open")}<span><b>From this computer…</b><small>Images, clips and sounds, up to 95 MB</small></span></button>
    <p class="as-up-hint">Or drop files anywhere on Assets. Links go in the Library, with Add reference.</p></div>`);
  document.body.append(upPop);
  const r = anchor.getBoundingClientRect();
  upPop.style.top = `${r.bottom + 8}px`; upPop.style.left = `${Math.max(12, r.right - upPop.offsetWidth)}px`;
  $("select", upPop).onchange = (e) => { target = e.target.value; localStorage.setItem("cr.stockFilm", target); document.body.dataset.dropFilm = target; };
  $('[data-a="x"]', upPop).onclick = closeUpPop;
  $('[data-a="pick"]', upPop).onclick = () => {
    const inp = document.createElement("input"); inp.type = "file"; inp.multiple = true; inp.accept = "image/*,video/*,audio/*,.gif"; inp.hidden = true;
    document.body.append(inp);   // attached, so every browser sends its change
    inp.onchange = () => { const fs = [...inp.files]; inp.remove(); closeUpPop(); uploadAssets(fs, main); }; inp.click();
  };
  $('[data-a="pick"]', upPop).focus();
  document.addEventListener("pointerdown", upOutside, true); document.addEventListener("keydown", upEsc, true);
}
function sendAsset(file, film, onProgress, onXhr) {
  return new Promise((res, rej) => {
    const x = new XMLHttpRequest(); onXhr?.(x);
    x.onabort = () => rej(new Error("cancelled"));
    x.open("POST", "/api/assets/upload"); x.setRequestHeader("X-Filename", encodeURIComponent(file.name)); x.setRequestHeader("X-Film", encodeURIComponent(film));
    x.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    x.onload = () => { let j = {}; try { j = JSON.parse(x.responseText); } catch {} x.status < 300 ? res(j) : rej(new Error(j.error || x.statusText)); };
    x.onerror = () => rej(new Error("the toolbox didn't answer")); x.send(file);
  });
}
async function uploadAssets(files, main) {
  files = [...files]; if (!files.length) return;
  const film = upTarget(), dock = window.Imports?.upload;
  let ok = 0, xhr = null, stop = false;
  dock?.start(files, { after: `In ${film}'s assets (uploads/)`, open: `#/assets?film=${film}`, cancel: () => { stop = true; xhr?.abort(); } });
  for (const [i, file] of files.entries()) {
    if (stop) break;
    dock?.file(i, file.name);
    try { await sendAsset(file, film, (p) => dock?.progress(p), (x) => (xhr = x)); ok++; dock?.done(true); }
    catch (e) { if (stop) break; dock?.done(false); window.crToast?.(`Couldn't upload ${file.name}: ${e.message}`, 4200); }
  }
  dock?.end({ cancelled: stop });
  if (ok) await reload(main);
}
async function reload(main) {
  try { data = await (await fetch("/api/assets")).json(); } catch { return; }
  if (location.hash.startsWith("#/assets")) draw(main);
}
// files dropped on Assets go into a film, not the Library (app.js asks first)
function drop(files) { uploadAssets(files, $("#main")); return true; }
window.CR?.command({ id: "as.up", title: "Upload into a film's assets…", group: "App", run: () => { location.hash = "#/assets"; setTimeout(() => { const b = $('[data-a="upload"]'); if (b) uploadPop(b, $("#main")); }, 500); } });
window.CR?.command({ id: "as.stock", title: "Search assets and free libraries…", group: "App", run: () => { location.hash = "#/assets"; setTimeout(() => $(".as-search input")?.focus(), 500); } });
function stop() { closeUpPop(); delete document.body.dataset.dropFilm; if (audio) { audio.onended = null; audio.pause(); audio = null; } cur = -1; now = null; cancelAnimationFrame(raf); durObs?.disconnect(); }
window.CR?.command({ id: "as.go", title: "Go to Assets", group: "Go to", run: () => (location.hash = "#/assets") });
window.CR?.command({ id: "as.hf", title: "Assets: Higgsfield generations", group: "Go to", run: () => (location.hash = "#/assets?source=higgsfield") });
window.CR?.command({ id: "as.el", title: "Assets: ElevenLabs sounds", group: "Go to", run: () => (location.hash = "#/assets?source=elevenlabs") });
window.CR?.command({ id: "as.snd", title: "Assets: Sound (music, voice, effects)", group: "Go to", run: () => (location.hash = "#/assets?view=sound") });
return { render, stop, onKey, drop };
})();
