/* Styles (#/styles): library/STYLES.md shown, not just told. Each look gets a mood board (its scenes playing on
   hover, the palette, the motion and type tags, the pace); each move, transition and ending a card that plays the
   scene that shows it; structures as their shape; pace tiers as the films in them. STYLES.md stays the source:
   build_library.py parses it into LIBRARY.styles; "Text" shows it as written (LIBRARY.styles_html). */
window.StylesView = (() => {
"use strict";
const L = window.LIBRARY;
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const icon = (n) => window.icon(n);
const fileUrl = SP.fileUrl;
// one timecode format everywhere: m:ss.cc (frames are added where they matter)
const ts = (t) => `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, "0")}`;
const FILMS = Object.fromEntries(L.films.map((f) => [f.slug, f]));
const SC = {};
for (const f of L.films) for (const s of f.scenes) SC[`${f.slug}/${s.id}`] = { ...s, film: f.slug, key: `${f.slug}/${s.id}` };
let toastT = 0;
const toast = (msg, ms = 1800) => {
  if (typeof window.crToast === "function") return window.crToast(msg, ms);
  const t = document.getElementById("toast"); if (!t) return;
  t.textContent = msg; t.classList.add("show"); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("show"), ms);
};
async function copyText(text, msg) {
  try { await navigator.clipboard.writeText(text); } catch { const a = document.createElement("textarea"); a.value = text; document.body.append(a); a.select(); document.execCommand("copy"); a.remove(); }
  toast(msg);
}

/* ---------- from references to things to show ---------- */
const best = (f, n = 2) => [...f.scenes].sort((a, b) => b.steal - a.steal || a.start - b.start).slice(0, n).map((s) => SC[`${f.slug}/${s.id}`]);
function scenesOf(refs, perFilm = 2, max = 8) {
  const out = [];
  for (const r of refs) {
    if (r.scene && SC[`${r.film}/${r.scene}`]) out.push(SC[`${r.film}/${r.scene}`]);
    else if (!r.scene && FILMS[r.film]) out.push(...best(FILMS[r.film], perFilm));
  }
  return [...new Map(out.map((s) => [s.key, s])).values()].slice(0, max);
}
function paletteOf(refs, scenes, max = 8) {
  const seen = new Map();
  const add = (hex, name) => { const k = String(hex).toUpperCase(); if (/^#[0-9A-F]{6}$/.test(k) && !seen.has(k)) seen.set(k, name || ""); };
  for (const r of refs) if (!r.scene && FILMS[r.film]) for (const p of FILMS[r.film].style_signature?.palette || []) add(p.hex, p.name);
  for (const s of scenes) for (const c of s.palette || []) add(c, "");
  return [...seen].slice(0, max);
}
function tagsOf(scenes, fields = ["motion", "type_treatment", "transition_in"], max = 6) {
  const n = {};
  for (const s of scenes) for (const f of fields) for (const v of [].concat(s[f] ?? [])) if (v && v !== "none") n[v] = (n[v] || 0) + 1;
  return Object.entries(n).sort((a, b) => b[1] - a[1]).slice(0, max).map(([v]) => v);
}
function paceOf(refs) {
  const fs = [...new Set(refs.map((r) => r.film))].map((f) => FILMS[f]).filter((f) => f && f.tempo);
  const shots = fs.map((f) => f.tempo.avg_shot_s).filter(Boolean), bpm = fs.map((f) => f.tempo.bpm).filter(Boolean);
  if (!shots.length) return "";
  const r = (a) => (Math.min(...a) === Math.max(...a) ? `${+Math.min(...a).toFixed(1)}` : `${+Math.min(...a).toFixed(1)} to ${+Math.max(...a).toFixed(1)}`);
  return `shots ${r(shots)}s${bpm.length ? ` · ${r(bpm.map(Math.round))} bpm` : ""}`;
}

/* ---------- a scene that plays on hover ---------- */
let live = null;
function stopLive() { if (live) { cancelAnimationFrame(live.raf); live.v.remove(); live.el.classList.remove("on"); live = null; } }
function preview(s, { label = true, cls = "" } = {}) {
  const f = FILMS[s.film];
  const el = h(`<div class="st-pv ${cls}" tabindex="0" title="${esc(`${s.key}  ${s.title}`)}">
    <img loading="lazy" alt="" class="strip" src="${esc(SP.stripUrl(s.film, s.id))}">
    <span class="st-dur">${(s.end - s.start).toFixed(1)}s</span>
    <button class="st-add" title="Add to the current board" aria-label="Add to board">${icon("plus")}</button>
    ${label ? `<div class="st-cap"><b>${esc(s.key)}</b><span>${esc(s.title)}</span></div>` : ""}</div>`);
  // the poster: the middle frame of the scene's strip (library/references/<film>/scenes/sNN.jpg, n frames 6px apart)
  const img = $("img", el), d = s.end - s.start, n = d <= 2.5 ? 3 : d <= 5 ? 4 : 5;
  img.onload = () => {
    // cover the tile with frame k of the strip, whatever the tile's shape (percentages, so it holds on resize)
    const W = img.naturalWidth, H = img.naturalHeight, fw = (W - 6 * (n - 1)) / n, k = Math.floor(n / 2);
    const cw = el.clientWidth || 320, ch = el.clientHeight || 180, sc = Math.max(cw / fw, ch / H);
    Object.assign(img.style, { width: `${(W * sc / cw) * 100}%`, height: `${(H * sc / ch) * 100}%`,
      left: `${((-k * (fw + 6) * sc + (cw - fw * sc) / 2) / cw) * 100}%`, top: `${(((ch - H * sc) / 2) / ch) * 100}%` });
  };
  // then swap in a clean frame (the strip's frames carry a time label) from the same moment, once the server has cut it
  const pad = Math.min(0.08, d * 0.1), tk = s.start + pad + Math.floor(n / 2) * (d - 2 * pad) / Math.max(1, n - 1);
  const clean = `/api/frame?file=${encodeURIComponent(f.file)}&t=${tk.toFixed(3)}&w=640`;
  const swap = () => { const im = new Image(); im.onload = () => { img.onload = null; img.classList.remove("strip"); img.removeAttribute("style"); img.src = clean; }; im.src = clean; };
  img.addEventListener("load", swap, { once: true });
  img.onerror = () => { img.onerror = null; img.classList.remove("strip"); img.src = clean; };
  const start = () => {
    if (live?.el === el) return;
    stopLive();
    const v = document.createElement("video");
    v.muted = true; v.playsInline = true; v.preload = "auto"; v.src = fileUrl(f.file);
    el.append(v);
    live = { el, v, raf: 0 };
    const a = s.start + 0.02, e = Math.max(a + 0.3, s.end - 0.04);
    const go = () => { try { v.currentTime = a; } catch {} v.play().catch(() => {}); };
    v.readyState >= 1 ? go() : v.addEventListener("loadedmetadata", go, { once: true });
    v.addEventListener("playing", () => el.classList.add("on"), { once: true });
    const loop = () => { if (!live || live.v !== v) return; if (v.currentTime >= e || v.currentTime < a - 0.5) try { v.currentTime = a; } catch {} live.raf = requestAnimationFrame(loop); };
    live.raf = requestAnimationFrame(loop);
  };
  el.addEventListener("mouseenter", start); el.addEventListener("focus", start);
  el.addEventListener("mouseleave", () => { if (live?.el === el) stopLive(); });
  el.addEventListener("blur", () => { if (live?.el === el) stopLive(); });
  el.onclick = (e) => { if (e.target.closest(".st-add")) return; location.hash = `#/scene/${s.key}`; };
  el.onkeydown = (e) => { if (e.key === "Enter") location.hash = `#/scene/${s.key}`; };
  $(".st-add", el).onclick = (e) => { e.stopPropagation(); addToBoard(s.key); };
  return el;
}
async function addToBoard(key) {
  const board = localStorage.getItem("cr.board");
  if (!board) { toast("Open a board first (Boards)"); return; }
  try {
    const r = await fetch("/api/ops", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ by: "browser", ops: [{ op: "item.add", board, id: key }] }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || r.statusText);
    toast(`Added ${key} to ${board}`);
  } catch (e) { toast(`Couldn't add it: ${e.message}`); }
}
// hex codes in the prose get a swatch, and copy on click
const hexes = (html) => String(html || "").replace(/<code>(#[0-9A-Fa-f]{6})<\/code>/g, '<code class="st-hex" data-c="$1" title="Click to copy"><i style="background:$1"></i>$1</code>');
const swatches = (pal) => pal.length ? `<div class="st-pal">${pal.map(([hex, name]) => `<button class="st-sw" data-c="${esc(hex)}" title="${esc(`${hex}${name ? "  " + name : ""} (click to copy)`)}" style="--c:${esc(hex)}"></button>`).join("")}</div>` : "";
const chips = (tags) => tags.length ? `<div class="st-tags">${tags.map((t) => `<a class="st-tag" href="#/scenes?motion=${encodeURIComponent(t)}" data-t="${esc(t)}">${esc(t)}</a>`).join("")}</div>` : "";
const refLinks = (refs, skip = new Set()) => refs.filter((r) => !skip.has(r.scene ? `${r.film}/${r.scene}` : r.film))
  .map((r) => `<a class="st-ref" href="${r.scene ? `#/scene/${esc(r.film)}/${esc(r.scene)}` : `#/film/${esc(r.film)}`}" title="${esc(r.note || "")}">${esc(r.scene ? `${r.film}/${r.scene}` : (FILMS[r.film]?.title || r.film))}${r.note ? `<small>${esc(r.note)}</small>` : ""}</a>`).join("");
function wire(box) {
  box.querySelectorAll(".st-hex").forEach((b) => (b.onclick = (e) => { e.stopPropagation(); copyText(b.dataset.c, `Copied ${b.dataset.c}`); }));
  box.querySelectorAll(".st-sw").forEach((b) => (b.onclick = (e) => { e.stopPropagation(); copyText(b.dataset.c, `Copied ${b.dataset.c}`); }));
  // a tag chip filters Scenes by the field the tag belongs to
  box.querySelectorAll(".st-tag").forEach((a) => {
    const t = a.dataset.t, field = ["motion", "type_treatment", "transition_in", "world"].find((f) => L.tags[f] && t in L.tags[f]) || "motion";
    a.href = `#/scenes?${field}=${encodeURIComponent(t)}`;
    a.title = (L.tags[field] || {})[t] || "";
  });
}

/* ---------- sections ---------- */
function look(it) {
  const scenes = scenesOf(it.refs, 2, 6), pal = paletteOf(it.refs, scenes), pace = paceOf(it.refs);
  const det = it.details.filter((d) => d.label.toLowerCase() !== "films");
  const films = it.details.find((d) => d.label.toLowerCase() === "films");
  const el = h(`<article class="st-look">
    <div class="st-mood"></div>
    <div class="st-body">
      <div class="st-l"><h3>${esc(it.title)}</h3><p>${hexes(it.html)}</p>${films ? `<div class="st-films">${refLinks(films.refs)}</div>` : ""}</div>
      <div class="st-r">${swatches(pal)}${chips(tagsOf(scenes))}${pace ? `<div class="st-pace">${icon("film")}${esc(pace)}</div>` : ""}
        ${det.length ? `<details class="st-more"><summary>Numbers and how to build it</summary>${det.map((d) => `<p><b>${esc(d.label)}</b> ${hexes(d.html)}</p>`).join("")}</details>` : ""}</div>
    </div></article>`);
  const mood = $(".st-mood", el);
  scenes.slice(0, 5).forEach((s, i) => mood.append(preview(s, { label: false, cls: i === 0 ? "big" : "" })));
  if (!scenes.length) mood.remove();
  wire(el);
  return el;
}
function moveCard(row, cols) {
  const scenes = scenesOf(row.refs, 1, 4), first = scenes[0];
  const title = row.plain[0], desc = cols.length > 2 ? row.cells[1] : "";
  const el = h(`<article class="st-move"><div class="st-mv-pv"></div>
    <div class="st-mv-t"><h4>${esc(title)}</h4>${desc ? `<p>${desc}</p>` : ""}${chips(tagsOf(scenes, ["motion", "type_treatment", "transition_in"], 3))}
      <div class="st-refs">${refLinks(row.refs, new Set(first ? [first.key] : []))}</div></div></article>`);
  const pv = $(".st-mv-pv", el);
  if (first) pv.append(preview(first)); else pv.remove();
  wire(el);
  return el;
}
function structure(row) {
  const [name, len, shape] = row.plain;
  const steps = shape.split(/\s*→\s*/).filter(Boolean);
  const el = h(`<article class="st-struct">
    <div class="st-st-head"><h4>${esc(name)}</h4><span class="st-len">${esc(len)}</span></div>
    <div class="st-flow">${steps.map((s, i) => `<span class="st-step">${esc(s)}</span>${i < steps.length - 1 ? `<i>${icon("chevron-right")}</i>` : ""}`).join("")}</div>
    <div class="st-ex"></div></article>`);
  const ex = $(".st-ex", el);
  for (const r of row.refs) {
    const f = FILMS[r.film]; if (!f) continue;
    const s = best(f, 1)[0];
    const w = h(`<div class="st-exf"><a href="#/film/${esc(f.slug)}">${esc(f.title)}</a></div>`);
    if (s) w.prepend(preview(s, { label: false }));
    ex.append(w);
  }
  return el;
}
function paceTier(row) {
  const [tier, shot] = row.plain;
  const el = h(`<div class="st-tier"><div class="st-tier-h"><b>${esc(tier)}</b><span>${esc(shot)}</span></div><div class="st-tier-f"></div></div>`);
  const box = $(".st-tier-f", el);
  const brands = row.refs.map((r) => FILMS[r.film]?.brand), twice = (b) => brands.filter((x) => x === b).length > 1;
  for (const r of row.refs) {
    const f = FILMS[r.film]; if (!f) continue;
    const s = best(f, 1)[0];
    const w = h(`<div class="st-pf"><div class="st-pf-l"><a href="#/film/${esc(f.slug)}" title="${esc(f.title)}">${esc(!f.brand || twice(f.brand) ? f.title : f.brand)}</a><span>${esc(r.note || (f.tempo?.avg_shot_s ? `${f.tempo.avg_shot_s}s` : ""))}</span></div></div>`);
    if (s) w.prepend(preview(s, { label: false }));
    box.append(w);
  }
  return el;
}
function section(sec) {
  const el = h(`<section class="st-sec" id="st-${esc(sec.id)}" data-id="${esc(sec.id)}">
    <div class="st-sec-h"><span class="st-n">${sec.n ?? ""}</span><h2>${esc(sec.title)}</h2>
      <span class="st-count">${sec.kind === "looks" ? `${sec.items.length} looks` : sec.kind === "table" ? `${sec.rows.length}` : ""}</span></div>
    ${sec.intro ? `<p class="st-intro">${sec.intro}</p>` : ""}</div>`);
  if (sec.kind === "looks") { const box = h(`<div class="st-looks"></div>`); sec.items.forEach((it) => box.append(look(it))); el.append(box); }
  else if (sec.kind === "table") {
    const c0 = (sec.cols[0] || "").toLowerCase();
    if (c0 === "structure") { const box = h(`<div class="st-structs"></div>`); sec.rows.forEach((r) => box.append(structure(r))); el.append(box); }
    else if (c0 === "tier") { const box = h(`<div class="st-tiers"></div>`); sec.rows.forEach((r) => box.append(paceTier(r))); el.append(box); }
    else { const box = h(`<div class="st-moves"></div>`); sec.rows.forEach((r) => box.append(moveCard(r, sec.cols))); el.append(box); }
    if (sec.outro) el.append(h(`<div class="st-outro">${sec.outro}</div>`));
  } else {
    const scenes = scenesOf(sec.refs || [], 1, 5).filter(Boolean);
    if (scenes.length) { const strip = h(`<div class="st-strip"></div>`); scenes.forEach((s) => strip.append(preview(s))); el.append(strip); }
    el.append(h(`<div class="st-prose prose">${hexes(sec.html)}</div>`)); wire(el);
  }
  return el;
}

/* ---------- the page ---------- */
let io = null, unscroll = null;
function render(main) {
  stop();
  const mode = localStorage.getItem("cr.stylesMode") || "visual";
  const st = L.styles;
  main.innerHTML = "";
  const head = h(`<div class="view-head"><h1>Styles</h1><span class="meta">The looks, moves and structures across the library, with the scenes that show them</span><span class="spacer"></span>
    <div class="seg" id="st-mode"><button data-v="visual">Visual</button><button data-v="text">Text</button></div></div>`);
  main.append(head);
  head.querySelectorAll("#st-mode button").forEach((b) => { b.classList.toggle("on", b.dataset.v === mode); b.onclick = () => { localStorage.setItem("cr.stylesMode", b.dataset.v); render(main); }; });
  if (mode === "text" || !st) { main.append(h(`<div class="prose">${L.styles_html}</div>`)); return; }
  const nav = h(`<nav class="st-index">${st.sections.map((s) => `<button data-id="${esc(s.id)}">${esc(s.title)}</button>`).join("")}</nav>`);
  main.append(nav);
  nav.querySelectorAll("button").forEach((b) => (b.onclick = () => go(b.dataset.id)));
  for (const sec of st.sections) main.append(section(sec));
  const smeta = head.querySelector(".meta"), swas = smeta.textContent;
  ViewSearch.attach(head, "styles", { placeholder: "Search styles", cards: ".st-look, .st-move, .st-struct, .st-tier", sections: ".st-sec",
    count: (n, total, q) => (smeta.textContent = q ? `${n} of ${total} looks, moves and structures` : swas) });
  main.append(h(`<p class="st-foot">From <code>library/STYLES.md</code>: edit it there and run <code>${SP.cmd("library")}</code>. Hover a scene to play it, click to open it, + to add it to the current board.</p>`));
  // the index casts a line only once it's stuck to the top
  const navTop = nav.offsetTop;
  const onScroll = () => nav.classList.toggle("stuck", main.scrollTop > navTop - 30);
  main.addEventListener("scroll", onScroll, { passive: true }); onScroll();
  unscroll = () => main.removeEventListener("scroll", onScroll);
  // the index follows the scroll
  io = new IntersectionObserver((ents) => {
    for (const en of ents) if (en.isIntersecting) nav.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.id === en.target.dataset.id));
  }, { root: main, rootMargin: "-20% 0px -70% 0px" });
  main.querySelectorAll(".st-sec").forEach((s) => io.observe(s));
  const want = new URLSearchParams(location.hash.split("?")[1] || "").get("s");
  if (want) requestAnimationFrame(() => go(want, false));
}
function go(id, smooth = true) {
  const sec = document.getElementById(`st-${id}`), main = document.getElementById("main"); if (!sec || !main) return;
  const nav = $(".st-index", main);
  main.scrollTo({ top: sec.offsetTop - (nav ? nav.offsetHeight + 16 : 0) - main.offsetTop, behavior: smooth ? "smooth" : "auto" });
  history.replaceState(null, "", `#/styles?s=${id}`);
}
function stop() { stopLive(); if (io) { io.disconnect(); io = null; } if (unscroll) { unscroll(); unscroll = null; } }
for (const s of (L.styles?.sections || [])) window.CR?.command({ id: `st.${s.id}`, title: `Styles: ${s.title}`, group: "Go to", run: () => { location.hash = `#/styles?s=${s.id}`; } });
return { render, stop };
})();
