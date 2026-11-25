/* Build view: films in production, each storyboard beat paired with its slice of the render and its reference scenes.
   Data comes live from film.py through toolbox.py (/api/productions). Review notes and statuses save into
   the film's own storyboard.json (Remotion) or review.json (HyperFrames), which is where the agents building it read them. */
window.BuildView = (api) => {
"use strict";
const { h, esc, $, tsf, toast, copy, thumb, BY_KEY, FILMS, fileUrl, scrubber, stampAt, stampRange, tcCopy } = api;
const icon = window.icon;
const dot = (s) => `<span class="st-dot st-${s}"></span>`;
const cap = (x) => x.charAt(0).toUpperCase() + x.slice(1);
const statusBtn = (s) => `${dot(s)}<span>${cap(STATUS[s] || s)}</span>${icon("chevron-down")}`;

/* ---------- a small popover menu (status picker) ---------- */
let menu = null;
function closeMenu() { if (menu) { menu.remove(); menu = null; document.removeEventListener("mousedown", outside, true); document.removeEventListener("keydown", menuKey, true); } }
function menuKey(e) { if (menu && e.key === "Escape") { e.stopPropagation(); e.preventDefault(); closeMenu(); } }
function outside(e) { if (menu && !menu.contains(e.target)) closeMenu(); }
function openMenu(anchor, items, onPick) {
  closeMenu();
  menu = h(`<div class="menu" role="menu">${items.map((it) => it.sep ? `<hr class="menu-sep">` : it.value === "" && !it.on && /class="lbl dim"/.test(it.html) ? `<div class="menu-info">${it.html}</div>` : `<button role="menuitem" data-v="${esc(it.value)}" class="${it.on ? "on" : ""}">${it.html}${it.on ? icon("check") : ""}</button>`).join("")}</div>`);
  const r = anchor.getBoundingClientRect();
  menu.style.top = `${Math.min(r.bottom + 6, innerHeight - 220)}px`; menu.style.left = `${Math.min(r.left, innerWidth - 220)}px`;
  menu.querySelectorAll("button").forEach((b) => (b.onclick = () => { closeMenu(); onPick(b.dataset.v); }));
  document.body.append(menu);
  const mh = menu.offsetHeight; if (r.bottom + 6 + mh > innerHeight - 8) menu.style.top = `${Math.max(8, innerHeight - mh - 8)}px`;
  const mw = menu.offsetWidth; if (r.left + mw > innerWidth - 8) menu.style.left = `${Math.max(8, Math.min(r.right, innerWidth - 8) - mw)}px`;
  setTimeout(() => { document.addEventListener("mousedown", outside, true); document.addEventListener("keydown", menuKey, true); });
}

const STATUS = { todo: "not built", wip: "building", review: "to review", changes: "changes asked", approved: "approved" };
const ORDER = Object.keys(STATUS);
const ago = (s) => { const d = Date.now() / 1000 - s; return d < 60 ? "just now" : d < 3600 ? `${Math.floor(d / 60)}m ago` : d < 86400 ? `${Math.floor(d / 3600)}h ago` : `${Math.floor(d / 86400)}d ago`; };
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
async function call(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
const patchBeat = (slug, id, body) => call(`/api/productions/${slug}/beats/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(body) });

let P = null;          // the film on screen
let snd = null;        // the sound panel (sound.js) for the film on screen
let soundOn = false;   // the transport's sound key
let volume = (() => { const v = parseFloat(localStorage.getItem("cr.vol")); return Number.isFinite(v) ? clamp(v, 0, 1) : 1; })();   // the monitor level knob (this browser)
let speedKnob = null, volKnob = null;   // the transport's knobs (hardware.js), made anew with each draw
// the controls' own sounds (Settings: Control sounds) never play over a film that is being listened to
window.HW.sound.hush = () => soundOn && !!vid && !vid.paused && !!document.querySelector(".bx-stage");
let loopRange = null;  // a range looped from the sound panel (overrides the beat loop)
let TL = { z: 1, v0: 0 };   // the timeline's zoom: z times the film's width, starting at v0 seconds. The beat bar and the sound lanes share it
let tlHold = 0, tlPrevT = -1;   // when the person last moved the window by hand; the playhead's last time (the window follows it when it moves)
const TL_MIN = 1;         // the closest zoom shows this many seconds
const Sound = window.SoundPanel(api);
const openSoundNotes = () => Object.entries(P.sound_notes || {}).filter(([, v]) => v.note);
let R = null;          // the render being shown
let sel = 0;           // selected beat
let mode = "play";     // "play" (the default): play through, the storyboard follows the playhead · "loop": loop the selected beat
let sync = true;       // stretch the reference so it starts and ends with the beat
let speed = 1;
let refKey = null;     // reference scene in the right pane
let vid = null, rvid = null, raf = 0, nowIdx = -1, gen = 0, scrubbing = false;
const memo = {};       // per film: selected beat, render, mode
let C = null;          // a second render to compare with (shown in the right pane instead of the reference)
let cvid = null;       // its video
let tab = "beats";     // what's under the player: beats · script · assets
const openPins = () => (P.pins || []).filter((x) => x.status !== "done");
const pinsOf = (b) => openPins().filter((x) => x.beat === b.id);
const short = (r) => r ? r.name.replace(new RegExp(`^${P.slug}-`), "").replace(/\.(mp4|mov|webm|m4v)$/i, "") : "";
const BY = { person: "you", chat: "from the chat", claude: "Claude", agent: SP.Ai };
// when a note was written, answered or closed: the date and time as this person's machine writes them ("23 Nov, 14:02"),
// with the year when it isn't this one. A date with no time (notes closed before the time was kept) stays a date.
const whenAt = (iso, long = false) => {
  if (!iso) return "";
  const timed = iso.includes("T"), d = new Date(timed ? iso : `${iso}T00:00:00`);
  if (isNaN(d)) return "";
  const o = long ? { weekday: "long", day: "numeric", month: "long", year: "numeric" } : { day: "numeric", month: "short", ...(d.getFullYear() === new Date().getFullYear() ? {} : { year: "numeric" }) };
  return d.toLocaleString(undefined, timed ? { ...o, hour: "numeric", minute: "2-digit" } : o);
};
// done notes on the beat bar: there until the person hides them (kept in this browser)
const donePinsHidden = () => localStorage.getItem("cr.donePins") === "0";
function toggleDonePins(show = donePinsHidden()) { try { localStorage.setItem("cr.donePins", show ? "1" : "0"); } catch {} paintPins(); }
// the script as the film has it now: the plan's words, else what's in the film, else what the board planned
const spokenText = (b) => (b.spoken || []).map((x) => x.text).join(" / ");
const scriptCopy = (b) => b.copy || b.in_film || b.board?.copy || "";
const scriptVo = (b) => b.vo || spokenText(b) || b.board?.vo || "";
const norm = (s) => String(s || "").toLowerCase().replace(/[’']/g, "'").replace(/[^a-z0-9']+/g, " ").trim();
const copyChanged = (b) => !!b.copy && !!b.in_film && norm(b.copy) !== norm(b.in_film);
const voChanged = (b) => !!b.vo && norm(b.vo) !== norm(spokenText(b));
// acts: runs of beats that share a section name (film.py works them out from the beat titles, or a beat's own `act`)
function actsOf() {
  const out = [];
  P.beats.forEach((b, i) => { const a = b.act || ""; if (!out.length || out[out.length - 1].name !== a) out.push({ name: a, from: i, to: i }); else out[out.length - 1].to = i; });
  return out.length > 1 ? out : [];
}

function stop() { stopListPreviews(); unwatch(); closeMenu(); closeComposer(); cancelAnimationFrame(raf); raf = 0; if (vid) vid.pause(); if (rvid) rvid.pause(); if (cvid) cvid.pause(); if (snd) { snd.destroy(); snd = null; } }

/* ---------- beat windows in the render being shown ---------- */
const win = (b) => (R && R.beats && R.beats[b.id]) || [b.start, b.end];
const span = () => (R && R.span) || [0, Infinity];
function covered(b) {
  if (!R || b.start == null) return false;
  const [a, e] = win(b), [s0, s1] = span();
  return a >= s0 - 0.01 && e <= s1 + 0.01;
}
function beatAt(t) {
  for (let i = P.beats.length - 1; i >= 0; i--) { const [a] = win(P.beats[i]); if (a != null && t >= a - 0.001) return i; }
  return -1;
}
function beatStamp(t) {
  const b = P.beats[beatAt(t)];
  const id = b ? `${P.slug}/${b.id}` : P.slug;
  return stampAt(id, t, P.fps || 30, b ? win(b)[0] : null, "beat") + (R ? ` in ${R.name}` : "");
}
const filmT = () => (vid && R ? vid.currentTime + (R.offset || 0) : 0);
function seekFilm(t) { if (vid && R) try { vid.currentTime = Math.max(0, t - (R.offset || 0) + 0.001); } catch {} }
const frameUrl = (t, w = 320) => `/api/frame?file=${encodeURIComponent(R.file)}&t=${(t - (R.offset || 0)).toFixed(3)}&w=${w}&v=${Math.round(R.mtime)}`;

/* ---------- list of films ---------- */
function strip(p) {
  const total = p.duration || p.beats.reduce((a, b) => Math.max(a, b.end || 0), 0) || 1;
  return `<div class="bx-strip">${p.beats.map((b) => `<i class="st-${b.status}" style="flex:${Math.max(0.2, (b.end ?? 0) - (b.start ?? 0)) / total}" title="${esc(`${b.n}. ${b.title}: ${STATUS[b.status] || b.status}`)}"></i>`).join("")}</div>`;
}
/* A film card's picture, like the Films view: a frame of its newest full render; on hover the render plays a few
   seconds of three beats (the first, one from the middle, the last one built), muted, with the beat as the tag. */
const PREVIEW_S = 2.4;
function filmCardMedia(p) {
  const f = p.full, dur = p.duration || 0;
  const box = h(`<div class="film-media bx-media"><div class="fm-bars"></div><span class="fm-tag"></span>${dur ? `<span class="fm-dur">${tsf(dur).replace(/\.\d+$/, "")}</span>` : ""}</div>`);
  if (!f) {
    const s = BY_KEY[p.beats.find((b) => b.ref && BY_KEY[b.ref])?.ref];
    box.classList.add("bx-media-none");
    if (s) box.prepend(thumb(s, { scrub: false }));
    box.append(h(`<span class="bx-media-msg">Not rendered yet</span>`));
    return box;
  }
  const wins = (b) => (f.beats && f.beats[b.id]) || (b.start != null ? [b.start, b.end] : null);
  const timed = p.beats.filter((b) => wins(b));
  const built = timed.filter((b) => b.status !== "todo");
  const picks = [...new Set([timed[0], timed[Math.floor(timed.length / 2)], built[built.length - 1] || timed[timed.length - 1]].filter(Boolean))].sort((a, b) => wins(a)[0] - wins(b)[0]);
  const off = f.offset || 0;
  const segs = picks.map((b) => { const [a0, e0] = wins(b), a = a0 + Math.min(0.15, (e0 - a0) / 4); return { b, a: a - off, e: Math.min(e0 - 0.05, a + PREVIEW_S) - off }; });
  const mid = (timed.length ? wins(timed[Math.floor(timed.length / 2)]) : [dur / 2, dur / 2]);
  const img = h(`<img class="fm-poster" alt="" loading="lazy" src="/api/frame?file=${encodeURIComponent(f.file)}&t=${Math.max(0, (mid[0] + mid[1]) / 2 - off).toFixed(2)}&w=720&v=${Math.round(f.mtime)}">`);
  img.onerror = () => img.remove();
  box.prepend(img);
  const bars = $(".fm-bars", box); bars.innerHTML = segs.map(() => "<i><b></b></i>").join("");
  const tag = $(".fm-tag", box), bb = [...bars.querySelectorAll("b")];
  let v = null, k = 0, raf = 0, hoverT = 0;
  const go = (j) => { k = j % segs.length; try { v.currentTime = segs[k].a; } catch {} };
  const loop = () => {
    raf = requestAnimationFrame(loop);
    if (!v || v.readyState < 2) return;
    const g = segs[k];
    if (v.currentTime >= g.e || v.currentTime < g.a - 0.4) go(k + 1);
    tag.textContent = `${g.b.n} · ${g.b.title}`;
    bb.forEach((x, j) => (x.style.width = j < k ? "100%" : j > k ? "0%" : `${clamp((v.currentTime - g.a) / Math.max(0.1, g.e - g.a), 0, 1) * 100}%`));
  };
  const start = () => {
    if (!segs.length) return;
    if (!v) {
      v = document.createElement("video"); v.muted = true; v.playsInline = true; v.preload = "auto"; v.disablePictureInPicture = true;
      v.addEventListener("playing", () => box.classList.add("live")); v.addEventListener("error", () => box.classList.add("nofile"));
      box.append(v);
    }
    if (!v.src) v.src = fileUrl(f.file);
    box.classList.add("on");
    const begin = () => { go(0); v.play().catch(() => {}); };
    v.readyState >= 1 ? begin() : v.addEventListener("loadedmetadata", begin, { once: true });
    cancelAnimationFrame(raf); raf = requestAnimationFrame(loop);
  };
  const stopIt = () => { clearTimeout(hoverT); cancelAnimationFrame(raf); box.classList.remove("on", "live"); bb.forEach((x) => (x.style.width = "0%")); if (v) v.pause(); };
  box.addEventListener("mouseenter", () => { hoverT = setTimeout(start, 120); });
  box.addEventListener("mouseleave", stopIt);
  return box;
}
function stopListPreviews() { document.querySelectorAll(".bx-media video").forEach((v) => { v.pause(); v.removeAttribute("src"); v.load(); }); }
async function renderList(main) {
  stop(); const my = ++gen;
  main.innerHTML = "";
  const head = h(`<div class="view-head"><h1>Build</h1><span class="meta">Films in production</span></div>`);
  main.append(head);
  let list;
  try { list = await call("/api/productions"); }
  catch { main.append(h(`<div class="empty">Spliced's server isn't answering. Start it with <b>${SP.cmd("open")}</b>.</div>`)); return; }
  if (my !== gen) return;
  // films that so far exist only in another git worktree (a Conductor workspace): shown last, with the renders that came here
  const away = list.filter((p) => p.workspace);
  list = list.filter((p) => !p.workspace);
  // With folders, a group per folder (the renderer is a tag on each film); without, one per renderer, as before.
  const byFolder = window.Folders?.any();
  if (byFolder) main.append(Folders.chips(() => renderList(main), Folders.count(list, (p) => p.folder)));
  const ENGINES = { remotion: "Remotion", hyperframes: "HyperFrames" };
  const sets = byFolder
    ? Folders.groups(list, (p) => p.folder).map((g) => [g.name, g.folder ? `${g.folder}/: renders go to ${g.folder}/renders/` : "Films in no folder", g.items, g.folder])
    : [["remotion", "remotion/src/films"], ["hyperframes", "videos"]].map(([eng, dir]) => [ENGINES[eng], `${dir}/`, list.filter((p) => p.engine === eng), null]);
  for (const [label, tip, all, folder] of sets) {
    const items = all.slice().sort((a, b) => b.updated - a.updated);
    if (byFolder && !items.length && Folders.filter() === "") continue;   // (an empty folder shows when it's the one asked for)
    main.append(h(`<h2 class="bx-group" title="${esc(tip)}">${esc(label)}<span>${items.length}</span>${byFolder && folder ? `<button class="bx-gfinder" title="Show ${esc(folder)}/ in Finder">${icon("folder-open")}</button>` : ""}</h2>`));
    main.lastElementChild.querySelector(".bx-gfinder")?.addEventListener("click", () => reveal(folder, "open"));
    if (!items.length) {
      main.append(h(byFolder ? `<div class="empty">No film in ${esc(label)} yet. Open a film and choose <b>Move to folder</b> in its menu, or start one from a board that is in this folder.</div>`
        : `<div class="empty">No film in production yet. This is where you build one: your ${SP.term("render")} on one side, the scene it borrows from on the other, ${SP.term("beat")} by beat. Start from a board: open <a href="#/boards"><b>Boards</b></a> and press <b>Start film</b>.</div>`));
      continue;
    }
    const grid = h(`<div class="bx-films"></div>`);
    items.forEach((p, i) => {
      const notes = p.beats.filter((b) => b.review).length + (p.pins || 0);
      const l = p.latest;
      const el = h(`<a class="bx-film" href="#/build/${esc(p.slug)}" style="animation-delay:${Math.min(i, 20) * 22}ms" data-search="${esc([p.title, p.slug, p.message, p.board, p.profile, p.engine, ...p.beats.map((b) => `${b.id} ${b.title} ${b.review || ""} ${b.status}`)].join(" "))}">
        <div class="top"><h3>${esc(p.title)}</h3>${byFolder ? `<span class="bx-eng" title="Made with ${ENGINES[p.engine] || p.engine}">${ENGINES[p.engine] || p.engine}</span>` : ""}</div>
        ${strip(p)}
        <div class="k foot"><span>${p.beats.length} beats</span>${notes ? `<span class="bx-fnotes">${icon("message-square")}${notes}</span>` : ""}<span class="spacer"></span>${l ? `<span title="Latest render: ${esc(l.file)}">${l.stale ? `<span class="warn">times changed · </span>` : ""}rendered ${ago(l.mtime)}</span><button class="bx-ffinder" title="Show ${esc(l.file)} in Finder">${icon("folder-open")}</button>` : "<span>not rendered yet</span>"}</div>
      </a>`);
      el.prepend(filmCardMedia(p));
      $(".bx-ffinder", el)?.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); reveal(l.file); });
      grid.append(el);
    });
    main.append(grid);
  }
  const awayShown = away.filter((p) => !window.Folders?.any() || Folders.matches(p.folder)).sort((a, b) => b.updated - a.updated);
  if (awayShown.length) {
    main.append(h(`<h2 class="bx-group" title="Films that are only in another copy of this project so far (a git worktree, such as a Conductor workspace). Their renders come here; the film itself arrives when its branch is merged.">In other workspaces<span>${awayShown.length}</span></h2>`));
    const grid = h(`<div class="bx-films"></div>`);
    awayShown.forEach((p, i) => {
      const l = p.latest, ws = p.workspace;
      const el = h(`<div class="bx-film bx-away" role="button" tabindex="0" title="${esc(l ? `Play ${l.name} (it is in ${l.file.replace(/^@main\//, "")})` : "Not rendered yet")}" style="animation-delay:${Math.min(i, 20) * 22}ms" data-search="${esc([p.title, p.slug, p.message, ws.branch, ws.name].join(" "))}">
        <div class="top"><h3>${esc(p.title)}</h3><span class="bx-eng" title="Being made in the workspace ${esc(ws.name)}, on the branch ${esc(ws.branch)}">${esc(ws.name)}</span></div>
        ${strip(p)}
        <div class="k foot"><span>${esc(ws.branch)}</span><span class="spacer"></span>${l ? `<span title="Latest render: ${esc(l.file)}">rendered ${ago(l.mtime)}</span><button class="bx-ffinder" title="Show ${esc(l.file)} in Finder">${icon("folder-open")}</button>` : "<span>not rendered yet</span>"}</div>
      </div>`);
      el.prepend(filmCardMedia(p));
      const play = () => (l ? reveal(l.file, "open") : toast(`${p.title} has no render yet`));
      el.addEventListener("click", (e) => { if (!e.target.closest(".bx-ffinder")) play(); });
      el.addEventListener("keydown", (e) => { if (e.key === "Enter") play(); });
      $(".bx-ffinder", el)?.addEventListener("click", (e) => { e.stopPropagation(); reveal(l.file); });
      grid.append(el);
    });
    main.append(grid);
  }
  if (list.length || awayShown.length) ViewSearch.attach(head, "build", { placeholder: "Search films in production", cards: ".bx-films .bx-film",
    count: (n, total, q) => (head.querySelector(".meta").textContent = q ? `${n} of ${total} films in production` : "Films in production"),
    // a group whose films are all filtered out goes with them (its heading is the grid's own neighbour)
    after: (root, q) => root.querySelectorAll(".bx-films").forEach((g) => g.previousElementSibling?.classList.toggle("vs-hide", !!q && !g.querySelector(".bx-film:not(.vs-hide)"))) });
}

/* ---------- one film ---------- */
async function renderFilm(main, slug) {
  stop(); const my = ++gen;
  if (!P || P.slug !== slug) main.innerHTML = `<div class="empty">Loading ${esc(slug)}…</div>`;
  try { P = await call(`/api/productions/${encodeURIComponent(slug)}`); }
  catch (e) { if (my === gen) main.innerHTML = `<div class="empty">${esc(e.message)}. <a href="#/build"><b>All films</b></a></div>`; return; }
  if (my !== gen) return;
  const m = (memo[slug] ||= { sel: 0, render: P.renders[0]?.file, mode: "play" });
  R = P.renders.find((r) => r.file === m.render) || P.renders[0] || null;
  C = (m.compare && P.renders.find((r) => r.file === m.compare && r !== R)) || null;
  sel = clamp(m.sel, 0, Math.max(0, P.beats.length - 1)); mode = m.mode; refKey = null; nowIdx = -1;
  TL = { z: m.z || 1, v0: m.v0 || 0 };
  const wantBeat = new URLSearchParams(location.hash.split("?")[1] || "").get("beat");
  if (wantBeat) { const bi = P.beats.findIndex((b) => b.id === wantBeat); if (bi >= 0) { sel = bi; m.sel = bi; } }
  const want = location.hash.split("?")[0].split("/")[3];
  const saved = localStorage.getItem(`cr.tab.${slug}`);
  tab = TABS.some((x) => x[0] === want) ? want : TABS.some((x) => x[0] === saved) ? saved : "beats";
  if (P.board) api.setBoard?.(P.board); // the tray and "Add to board" follow the film being built
  draw(main);
}
const remember = () => { if (P) Object.assign(memo[P.slug], { sel, render: R?.file, mode, compare: C?.file, z: TL.z, v0: TL.v0 }); };

/* ---------- the timeline's zoom: one window on the film (TL) for the beat bar, its ruler and the sound lanes ---------- */
const tlWin = () => { const D = P.duration || 1; return [TL.v0, TL.v0 + D / TL.z]; };
function setTl(z, v0, byHand) {
  const D = P.duration || 1;
  TL.z = clamp(z, 1, Math.max(1, D / TL_MIN));
  if (TL.z < 1.002) TL.z = 1;
  TL.v0 = clamp(v0, 0, D - D / TL.z);
  if (byHand) tlHold = performance.now();
  remember(); applyTl();
}
// zoom by a factor, keeping one film time where it is on screen: `at`, else the playhead when it is in view, else the middle
function zoomTl(f, at) {
  const D = P.duration || 1, [a, b] = tlWin(), now = filmT();
  const t = at ?? (now >= a && now <= b ? now : (a + b) / 2), k = (t - a) / (b - a);
  const z = clamp(TL.z * f, 1, Math.max(1, D / TL_MIN));
  setTl(z, t - k * (D / z), true);
}
// pinch or ⌘-scroll zooms at the pointer; a sideways scroll (or Shift-scroll) moves along the film. `box` shows the window a..b
function tlWheel(e, box, a, b) {
  const r = box.getBoundingClientRect(), side = Math.abs(e.deltaX) > Math.abs(e.deltaY);
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault();
    zoomTl(Math.exp(-clamp(e.deltaY, -30, 30) * 0.012), a + clamp((e.clientX - r.left) / r.width, 0, 1) * (b - a));
  } else if (TL.z > 1 && (side || e.shiftKey)) {
    e.preventDefault();
    setTl(TL.z, TL.v0 + ((side ? e.deltaX : e.deltaY) / r.width) * (b - a), true);
  }
}
// Safari and the Mac app report a pinch as gesture events, not as a wheel
function tlPinch(box, win) {
  let z0 = 1, t0 = 0;
  box.addEventListener("gesturestart", (e) => { e.preventDefault(); const r = box.getBoundingClientRect(), [a, b] = win(); z0 = TL.z; t0 = a + clamp((e.clientX - r.left) / r.width, 0, 1) * (b - a); });
  box.addEventListener("gesturechange", (e) => { e.preventDefault(); zoomTl((z0 * e.scale) / TL.z, t0); });
}
// time ticks for a ruler that shows a..b seconds over px pixels: a labelled tick every 70 to 110 pixels, finer ones
// between, down to single frames. pos(t) is a tick's place in percent of the ruler
function paintRuler(el, a, b, px, pos) {
  if (!el) return;
  const fps = P.fps || 30, pps = px / Math.max(0.001, b - a);
  const steps = [...new Set([1 / fps, 2 / fps, 5 / fps, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600])].sort((x, y) => x - y);
  const major = steps.find((x) => x * pps >= (x >= 1 ? 64 : x >= 0.5 ? 76 : 112)) || steps[steps.length - 1];
  const minor = steps.find((x) => x < major && x * pps >= 6 && Math.abs(major / x - Math.round(major / x)) < 1e-6) || major;
  const k = Math.round(major / minor);
  const whole = (t) => `${Math.floor((t + 1e-6) / 60)}:${String(Math.floor((t + 1e-6) % 60)).padStart(2, "0")}`;
  const lab = (t) => major >= 1 ? whole(t) : major >= 0.5 ? `${whole(t)}${Math.abs(t - Math.round(t)) < 1e-6 ? "" : ".5"}` : `${tsf(t)} f${Math.round(t * fps)}`;
  let out = "";
  for (let i = Math.ceil((a - 1e-6) / minor), n = Math.floor((b + 1e-6) / minor); i <= n; i++) {
    const t = i * minor, M = i % k === 0;
    out += `<i class="${M ? "M" : ""}" style="left:${pos(t).toFixed(4)}%">${M ? `<span>${lab(t)}</span>` : ""}</i>`;
  }
  el.innerHTML = out;
  el.dataset.step = major < 0.5 ? "frames" : String(major);
}
// lay the beat bar out for the window: its width and place, the labels that fit, the ruler, the readouts
function applyTl() {
  const box = document.getElementById("bx-tl"), inn = document.getElementById("bx-tl-in"); if (!box || !inn || !P) return;
  const D = P.duration || 1, W = box.clientWidth || 1, [a, b] = tlWin(), off = Math.round((TL.v0 / D) * TL.z * W);
  inn.style.width = `${TL.z * 100}%`; inn.style.transform = off ? `translateX(${-off}px)` : "";
  box.classList.toggle("zoomed", TL.z > 1);
  // a beat's label fits its width on screen, and stays in sight when the beat starts to the left of the window
  inn.querySelectorAll(".bx-seg").forEach((el) => {
    const bt = P.beats[+el.dataset.i]; if (!bt) return;
    const [s0, s1] = win(bt), fr = ((s1 - s0) / D) * TL.z, sp = el.firstElementChild;
    el.classList.toggle("nar", fr < 0.034);
    sp.textContent = `${fr < 0.012 ? "" : bt.n}${fr > 0.075 ? " " + bt.title.replace(/^[\w ]{2,24}:\s+/, "") : ""}`;
    const hid = off - (s0 / D) * TL.z * W;
    sp.style.left = hid > 0 && fr >= 0.034 ? `${Math.round(hid) + 8}px` : "";
  });
  inn.querySelectorAll(".bx-acts button").forEach((el) => {
    const hid = off - (parseFloat(el.style.left) / 100) * TL.z * W;
    el.firstElementChild.style.marginLeft = hid > 0 ? `${Math.round(hid)}px` : "";
  });
  paintRuler(document.getElementById("bx-ruler"), a, b, W, (t) => (t / D) * 100);
  const set = (id, v) => { const x = document.getElementById(id); if (x) x.textContent = v; };
  set("bx-tl-a", TL.z > 1 ? tsf(a) : "0:00"); set("bx-tl-b", tsf(Math.min(b, D)));
  const zb = document.getElementById("bx-zoom");
  if (zb) {
    $('[data-a="zout"]', zb).disabled = TL.z <= 1; $('[data-a="zin"]', zb).disabled = TL.z >= Math.max(1, D / TL_MIN) - 1e-6;
    const fit = $('[data-a="zfit"]', zb); fit.textContent = `${TL.z >= 10 ? Math.round(TL.z) : +TL.z.toFixed(1)}×`; fit.disabled = TL.z <= 1;
  }
  const ov = document.getElementById("bx-tlov");
  if (ov) { ov.hidden = TL.z <= 1; ov.firstElementChild.style.cssText = `left:${(TL.v0 / D) * 100}%;width:${100 / TL.z}%`; }
  if (snd && snd.follow) snd.follow();
}

function renderLabel(r) {
  return `${r.name} · ${ago(r.mtime)}${r.beat ? ` · ${/^\d+-\d+$/.test(r.beat) ? "beats" : "beat"} ${r.beat}` : ""}${r.stale ? " · times changed since" : ""}${r.note ? ` · ${r.note.length > 70 ? r.note.slice(0, 68) + "…" : r.note}` : ""}`;
}
/* ---------- new renders: watch the film's renders and offer the new one once it's finished writing ---------- */
let watchT = 0, seen = null, sizes = {};
function unwatch() { clearTimeout(watchT); watchT = 0; }
function watch(slug) {
  unwatch();
  seen = Object.fromEntries(P.renders.map((r) => [r.file, r.mtime]));
  sizes = {};
  const poll = async () => {
    watchT = setTimeout(poll, 4000);
    if (document.hidden || !P || P.slug !== slug || !document.getElementById("bx-upd")) return;
    let np; try { np = await call(`/api/productions/${encodeURIComponent(slug)}`); } catch { return; }
    if (!P || P.slug !== slug) return;
    livePins(np);
    if (JSON.stringify(np.sound_notes || {}) !== JSON.stringify(P.sound_notes || {})) { P.sound_notes = np.sound_notes; paintPins(); }   // sound notes filed elsewhere
    if (np.notes_mode !== P.notes_mode || JSON.stringify(np.watcher) !== JSON.stringify(P.watcher)) { P.notes_mode = np.notes_mode; P.watcher = np.watcher; paintMode(); }
    // the sound changed (soundkit, a new take, retimed effects): the Sound panel reads it again, so Stems play the new mix
    if (np.sound_stamp !== P.sound_stamp) { P.sound_stamp = np.sound_stamp; if (snd && snd.reload) snd.reload(); }
    const fresh = np.renders.filter((r) => !(r.file in seen) || r.mtime > seen[r.file] + 0.5);
    const writing = [], ready = [];
    for (const r of fresh) {
      const was = sizes[r.file]; sizes[r.file] = r.size;
      // finished = its size held still between two checks and it hasn't been touched for a couple of seconds
      (was === r.size && r.size > 0 && Date.now() / 1000 - r.mtime > 2 ? ready : writing).push(r);
    }
    paintUpd(writing, ready);
  };
  watchT = setTimeout(poll, 4000);
}
/* notes added elsewhere (Claude filing the chat's feedback with spliced film note, another tab) appear without a reload */
function livePins(np) {
  const key = (l) => JSON.stringify((l || []).map((x) => [x.id, x.status, x.note, x.t, (x.replies || []).length]));
  if (key(np.pins) === key(P.pins)) return;
  const before = new Set((P.pins || []).map((x) => x.id));
  const added = (np.pins || []).filter((x) => !before.has(x.id));
  const wasOpen = new Set((P.pins || []).filter((x) => x.status !== "done").map((x) => x.id));
  const closed = (np.pins || []).filter((x) => x.status === "done" && wasOpen.has(x.id));
  P.pins = np.pins || [];
  for (const b of P.beats) { const nb = np.beats.find((x) => x.id === b.id); if (nb) Object.assign(b, { status: nb.status, review: nb.review }); }
  paintPins();
  if (closed.length && !added.length) toast(closed.length === 1 ? `Done in ${(closed[0].done_in || "").replace(/\.(mp4|mov|webm|m4v)$/i, "")}: ${closed[0].done}` : `${closed.length} notes marked done`, 4200);
  if (added.length) toast(added.length === 1 ? `New note at ${tsf(added[0].t)}${added[0].by !== "person" ? ` (${BY[added[0].by] || added[0].by})` : ""}: ${added[0].note}` : `${added.length} new notes`, 3600);
}
function paintUpd(writing, ready) {
  const el = document.getElementById("bx-upd"); if (!el) return;
  const short = (r) => r.name.replace(new RegExp(`^${P.slug}-`), "").replace(/\.(mp4|mov|webm|m4v)$/i, "");
  const best = ready.sort((a, b) => b.mtime - a.mtime)[0];
  if (best) {
    const same = R && best.file === R.file;
    el.className = "bx-upd ready";
    el.innerHTML = `<span class="dot"></span><span>${same ? `${esc(short(best))} was re-rendered` : `New render ready: <b>${esc(short(best))}</b>${best.beat ? ` · beat ${esc(best.beat)}` : ""}`}</span><button class="icon-btn sm primary" data-a="load">${same ? "Reload" : "Load"}</button>`;
    el.title = `${best.file} · ${(best.size / 1e6).toFixed(1)} MB${best.note ? ` · ${best.note}` : ""}`;
    $('[data-a="load"]', el).onclick = () => { memo[P.slug].render = best.file; renderFilm($("#main"), P.slug); };
  } else if (writing.length) {
    const w = writing.sort((a, b) => b.mtime - a.mtime)[0];
    el.className = "bx-upd writing";
    el.innerHTML = `${icon("loader")}<span>Rendering ${esc(short(w))}…</span>`;
    el.title = `${w.file} is still being written (${(w.size / 1e6).toFixed(1)} MB so far)`;
  } else { el.hidden = true; return; }
  el.hidden = false;
}

/* ---------- who picks up the notes: Auto (a chat working on the film fixes them as they come in; spliced film watch wakes it)
   or Manual (they wait until you copy them into a prompt). Per film, kept with the pins (spliced film mode). ---------- */
const listenPrompt = () => `/make-film Work through my notes on "${P.title}" (${P.dir}/) as I add them in the Build view. Notes are in auto mode: fix the open ones now (\`${SP.cmd("film")} status ${P.slug}\`), then run \`${SP.cmd("film")} watch ${P.slug}\` in the background and pick up the next notes each time it returns.`;
function paintMode() {
  const el = document.getElementById("bx-nmode"); if (!el || !P) return;
  const auto = (P.notes_mode || "auto") === "auto", w = P.watcher;
  const mins = w ? Math.max(0, Math.round((Date.now() / 1000 - w.at) / 60)) : 0;
  const st = !auto ? "" : w?.state === "waiting" ? `<span class="bx-listen on" title="A chat with ${SP.ai} is waiting for your next note: add one and it starts within seconds"><span class="dot"></span><span class="lbl">${SP.Ai} is listening</span></span>`
    : w?.state === "working" ? `<span class="bx-listen busy" title="${esc(`Picked up ${mins ? mins + " min ago" : "just now"}: ${(w.notes || []).join(", ")}`)}"><span class="dot"></span><span class="lbl">${SP.Ai} is on ${w.notes?.length || ""} note${w.notes?.length === 1 ? "" : "s"}</span></span>`
    : `<button class="bx-listen off" data-a="listen" title="No chat is listening to this film's notes. Click to copy a prompt that starts one; paste it into ${SP.ai}"><span class="dot"></span><span class="lbl">No chat listening</span></button>`;
  el.innerHTML = `${st}<div class="seg sm" role="radiogroup" aria-label="Who picks up notes">
    <button class="${auto ? "on" : ""}" data-m="auto" title="Auto: a chat with ${SP.ai} working on this film picks up your notes as you add them">Auto</button>
    <button class="${auto ? "" : "on"}" data-m="manual" title="Manual: notes wait until you copy them with Copy notes prompt and paste them into ${SP.ai}">Manual</button></div>`;
  el.querySelectorAll("[data-m]").forEach((b) => (b.onclick = () => setNotesMode(b.dataset.m)));
  $('[data-a="listen"]', el)?.addEventListener("click", () => copy(listenPrompt(), `Prompt copied: paste it into a chat with ${SP.ai} and it picks up your notes as they come`));
  const nb = document.querySelector('[data-a="notes"]');
  if (nb) nb.title = auto ? "Auto mode picks notes up by itself; this copies every open note as one prompt anyway" : `Every open note as one prompt for ${SP.ai}`;
}
async function setNotesMode(m) {
  if (!P || (P.notes_mode || "auto") === m) return;
  try { Object.assign(P, await call(`/api/productions/${P.slug}`, { method: "PATCH", body: JSON.stringify({ notes_mode: m }) })); paintMode();
    toast(m === "auto" ? "Auto: a chat working on this film picks up notes as you add them" : "Manual: notes wait for Copy notes prompt"); }
  catch (e) { toast(`Couldn't switch: ${e.message}`); }
}

const scriptEdits = () => P.beats.filter((b) => copyChanged(b) || voChanged(b));
const noteCount = () => P.beats.filter((b) => b.review).length + openSoundNotes().length + openPins().length + scriptEdits().length;
function paintNotesBtn() {
  if (!P) return;
  const k = noteCount(), nb = document.querySelector('[data-a="notes"]');
  if (nb) { nb.disabled = !k; nb.classList.toggle("primary", !!k); nb.classList.toggle("ghost", !k); nb.innerHTML = `${icon("message-square")}Copy notes prompt${k ? ` (${k})` : ""}`; }
  const bd = document.getElementById("bx-nbadge"); if (bd) { bd.textContent = k || ""; bd.hidden = !k; }
}
function draw(main) {
  if (snd) { snd.destroy(); snd = null; }
  loopRange = null;
  main.innerHTML = "";
  const notes = noteCount();
  // header: the film's name, the render on screen as a quiet picker, one primary action; the rest in ⋯ and ⌘K
  const warns = [...P.warnings];
  if (R?.stale) warns.push(`${short(R)} was rendered with different beat times than cues.json has now: render again to see the current cut`);
  else if (R?.code_newer) warns.push(`The film's code changed after ${short(R)} was rendered`);
  const head = h(`<div class="view-head bx-head"><div class="bx-title">
      <h1><a href="#/build" class="crumb" title="All films">Build</a><span class="sep">/</span><span class="nm">${esc(P.title)}</span></h1>
      <div class="bx-sub">${P.renders.length ? `<button class="bx-rpick" data-a="render" title="The render on screen: pick another">${esc(R ? short(R) : "no render")}<span>${R ? ` · ${esc(ago(R.mtime))}${R.note ? ` · ${esc(R.note)}` : ""}` : ""}</span>${icon("chevron-down")}</button>` : `<span class="dim">Not rendered yet</span>`}
        ${R ? `<button class="icon-btn sm ghost bx-finder" data-a="finder" title="Show ${esc(R.file)} in Finder">${icon("folder-open")}Show in Finder</button>` : ""}
        <span class="bx-upd" id="bx-upd" hidden></span>
        ${warns.length ? `<span class="bx-stale" title="${esc(warns.join("\n"))}">${icon("triangle-alert")}${esc(warns[0])}${warns.length > 1 ? ` (+${warns.length - 1})` : ""}</span>` : ""}</div></div>
    <span class="spacer"></span>
    <div class="bx-nmode" id="bx-nmode"></div>
    <button class="icon-btn sm sq ghost" data-a="more" title="More: film info, reload, the board">${icon("ellipsis")}</button>
    <button class="icon-btn sm ${notes ? "primary" : "ghost"}" data-a="notes" ${notes ? "" : "disabled"} title="Every open note as one prompt for ${SP.ai}">${icon("message-square")}Copy notes prompt${notes ? ` (${notes})` : ""}</button></div>`);
  main.append(head);
  if (P.message) main.append(h(`<p class="bx-msg">${esc(P.message)}</p>`));
  $('[data-a="render"]', head)?.addEventListener("click", (e) => pickRender(e.currentTarget));
  $('[data-a="notes"]', head).onclick = () => copy(notesPrompt(), `Notes prompt copied: paste it into ${SP.ai}`);
  $('[data-a="more"]', head).onclick = (e) => filmMenu(e.currentTarget);
  paintMode();
  $('[data-a="finder"]', head)?.addEventListener("click", () => reveal(R.file));
  watch(P.slug);

  const stage = h(`<div class="bx-stage ${refHidden() ? "solo" : ""}">
    <div class="bx-pane"><div class="bx-label"><b>Render</b><span id="bx-rl"></span><button class="bx-showref" data-a="showref" title="Show the reference beside the render (H)">${icon("columns-2")}Reference</button></div><div class="bx-screen" id="bx-rs"></div></div>
    <div class="bx-pane"><div class="bx-label"><b id="bx-sh">Storyboard</b><span id="bx-sl"></span><span class="bx-tabs" id="bx-tabs"></span><button class="bx-hideref" data-a="hideref" title="Hide the reference: the render takes the width (H)">${icon("x")}Hide</button></div><div class="bx-screen" id="bx-ref"></div></div>
  </div>`);
  // the player: render, reference, transport and beat bar in one block, so the block can go full screen
  $('[data-a="hideref"]', stage).onclick = () => toggleRefPane(false);
  $('[data-a="showref"]', stage).onclick = () => toggleRefPane(true);
  const player = h(`<div class="bx-player ${localStorage.getItem("cr.fsRef") === "1" ? "with-ref" : ""}"></div>`);
  main.append(player);
  player.append(stage);
  const rs = $("#bx-rs", stage);
  if (R) {
    vid = document.createElement("video");
    vid.muted = true; vid.playsInline = true; vid.preload = "auto"; vid.src = fileUrl(R.file);
    vid.onerror = () => { rs.innerHTML = `<div class="nofile">Can't play ${esc(R.file)}.</div>`; };
    rs.append(vid);
    $("#bx-rl", stage).textContent = short(R);
    $("#bx-rl", stage).title = R.name + (R.note ? ` · ${R.note}` : "");
  } else {
    vid = null;
    rs.append(h(`<div class="nofile">Not rendered yet.<br>${P.engine === "remotion" ? `<code>${SP.cmd("film")} render ${esc(P.slug)}</code> (or <code>--beat &lt;id&gt;</code> for one beat)` : "Render it as the project's AGENTS.md says."}</div>`));
  }

  // transport: what you use every second on the left; the occasional controls in ⋯ (and ⌘K, and their keys)
  // The studio controls (play, frame step, loop switch, speed and level knobs, sound) are hardware: hardware.css / hardware.js.
  const tr = h(`<div class="transport bx-tr">
    <span class="hw-bay round"><button class="hw-key" data-a="play" title="Play / pause (Space)" aria-label="Play / pause">${icon("play")}</button></span>
    <span class="hw-bay"><button class="hw-key" data-a="back" title="Back one frame (,)" aria-label="Back one frame">${icon("step-back")}</button><button class="hw-key" data-a="fwd" title="Forward one frame (.)" aria-label="Forward one frame">${icon("step-forward")}</button></span>
    <span class="tc tc-copy" id="bx-tc" title="Click to copy the time with the beat ID (T)"></span><span class="bx-now" id="bx-now"></span><span class="gap"></span>
    <div class="hw-slide" id="bx-mode"><i class="hw-thumb"></i><button data-v="loop" class="${mode === "loop" ? "on" : ""}" title="Loop the selected beat (L)">Loop beat</button><button data-v="play" class="${mode === "play" ? "on" : ""}" title="Play the film through; the beats follow the playhead (L)">Play through</button></div>
    <div class="hw-knob detent" id="bx-speed" title="Speed: click for the next one, or drag"></div>
    <button class="icon-btn sm ghost" data-a="sync" title="Stretch the reference so it starts and ends with the beat (S)">${icon("repeat")}<span></span></button>
    <span class="bx-trsep"></span>
    <button class="icon-btn sm ghost" data-a="pin" title="Pin a note to this frame (N)">${icon("message-square-plus")}Note</button>
    <button class="icon-btn sm ${C ? "on" : "ghost"}" data-a="cmp" title="Compare with another render, side by side (X; V swaps them)">${icon("git-compare")}${C ? `vs ${esc(short(C))}` : "Compare"}</button>
    <span class="bx-mon"><span class="hw-bay"><button class="hw-key ${soundOn ? "on" : ""}" data-a="mute" title="Sound on / off (M)" aria-label="Sound" aria-pressed="${soundOn}"><span>${icon(soundOn ? "volume-2" : "volume-x")}</span><i class="hw-led"></i></button></span>
    <div class="hw-knob ${soundOn ? "" : "idle"}" id="bx-vol" title="Volume: drag up or down (Shift for fine), double-click for full"></div>
    <button class="icon-btn sm sq ghost" data-a="fsref" title="Show the reference beside the render in full screen">${icon("columns-2")}</button>
    <button class="icon-btn sm sq ghost" data-a="fs" title="Full screen (F)">${icon("maximize")}</button></span></div>`);
  player.append(tr);
  $('[data-a="pin"]', tr).onclick = () => compose();
  $('[data-a="cmp"]', tr).onclick = (e) => pickCompare(e.currentTarget);
  tr.querySelectorAll("#bx-mode button").forEach((b) => (b.onclick = () => { setMode(b.dataset.v); paintTrState(); }));
  window.HW.slide($("#bx-mode", tr), { label: "Playback" });
  speedKnob = window.HW.knob($("#bx-speed", tr), { stops: [0.25, 0.5, 1], value: speed, readout: true, label: "Speed", format: (v) => `${v}×`, onInput: setSpeed });
  volKnob = window.HW.knob($("#bx-vol", tr), { value: volume, reset: 1, label: "Volume", format: (v) => `${Math.round(v * 100)}%`, onInput: setVolume });
  $('[data-a="sync"]', tr).onclick = toggleSync;
  $('[data-a="fsref"]', tr).onclick = toggleFsRef;
  $('[data-a="fs"]', tr).onclick = toggleFull;
  $("#bx-rs", stage).addEventListener("dblclick", toggleFull);
  paintFull(); paintTrState();
  const playBtn = $('[data-a="play"]', tr);
  playBtn.onclick = togglePlay;
  $('[data-a="back"]', tr).onclick = () => step(-1);
  $('[data-a="fwd"]', tr).onclick = () => step(1);
  $('[data-a="mute"]', tr).onclick = () => setSound(!soundOn);
  // the play key stays down while the film plays
  if (vid) { vid.playbackRate = speed; vid.onplay = vid.onpause = () => { playBtn.innerHTML = icon(vid.paused ? "play" : "pause"); playBtn.classList.toggle("on", !vid.paused); }; }

  const bar = h(`<div class="bx-bar" title="Click a beat to play it, drag to scrub, shift-click to copy a time"></div>`);
  const D = P.duration || 1;
  // the acts, the beat bar and its ruler sit in one strip that is as wide as the zoom makes it; the box shows a window of it
  const tlBox = h(`<div class="bx-tl" id="bx-tl"><div class="bx-tl-in" id="bx-tl-in"></div></div>`), tlIn = tlBox.firstChild;
  player.append(tlBox);
  if (R?.span) {
    const [s0, s1] = R.span;
    if (s0 > 0) bar.append(h(`<div class="bx-out" style="left:0;width:${(s0 / D) * 100}%"></div>`));
    if (s1 < D) bar.append(h(`<div class="bx-out" style="left:${(s1 / D) * 100}%;right:0"></div>`));
  }
  P.beats.forEach((b, i) => {
    if (b.start == null) return;
    const [a, e] = win(b);
    // the label fits the segment: number and name when it's wide, the number alone when it's narrow, nothing when tiny
    // (the act is written above the bar, so "bridge: that's why" reads as "that's why")
    const fr = (e - a) / D, name = b.title.replace(/^[\w ]{2,24}:\s+/, "");
    bar.append(h(`<div class="bx-seg st-${b.status} ${fr < 0.034 ? "nar" : ""}" data-i="${i}" style="left:${(a / D) * 100}%;width:${fr * 100}%" title="${esc(`${b.n}. ${b.title} · ${tsf(a)} to ${tsf(e)}`)}"><span>${fr < 0.012 ? "" : b.n}${fr > 0.075 ? " " + esc(name) : ""}</span>${b.review ? "<i></i>" : ""}</div>`));
  });
  bar.append(h(`<div class="ph" id="bx-ph"></div>`), h(`<div class="bx-pins" id="bx-pins"></div>`));
  const acts = actsOf();
  if (acts.length) {
    const row = h(`<div class="bx-acts"></div>`);
    for (const a of acts) {
      const b0 = P.beats[a.from], b1 = P.beats[a.to]; if (b0.start == null || b1.start == null) continue;
      const x0 = win(b0)[0], x1 = win(b1)[1];
      const el = h(`<button style="left:${(x0 / D) * 100}%;width:${((x1 - x0) / D) * 100}%" title="${esc(`${a.name}: beats ${b0.n} to ${b1.n}, ${tsf(x0)} to ${tsf(x1)}`)}"><span>${esc(a.name)}</span></button>`);
      el.onclick = () => select(a.from, { seek: true, play: !!vid && !vid.paused, scroll: true, center: true });
      row.append(el);
    }
    tlIn.append(row);
  }
  const fps = P.fps || 30;
  const inSpan = (t) => { const [s0, s1] = span(); return clamp(t, s0, Math.min(s1, D) - 0.001); };
  let wasPlaying = false;
  scrubber(bar, {
    duration: () => D, clip: () => tlBox,
    seek: (t) => {
      const i = beatAt(t);
      if (i >= 0 && i !== sel) select(i, { seek: false, scroll: false });
      if (vid) seekFilm(inSpan(t));
    },
    label: (t) => { const b = P.beats[beatAt(t)]; return `${tsf(t)} · f${Math.round(t * fps)}${b ? ` · ${b.n} ${b.title} · ${STATUS[b.status] || b.status}` : ""}`; },
    copyAt: (t) => beatStamp(t),
    onStart: () => { scrubbing = true; wasPlaying = vid && !vid.paused; if (vid) vid.pause(); },
    onEnd: (t, moved) => { scrubbing = false; if (moved && wasPlaying) vid.play().catch(() => {}); },
    onClick: (t) => {
      const i = beatAt(t); if (i < 0) return;
      tbClick = performance.now();
      if (!vid || !covered(P.beats[i])) { select(i, { seek: true, play: true }); return; }
      select(i, { seek: false }); seekFilm(inSpan(t)); vid.play().catch(() => {});
    },
  });
  tlIn.append(bar, h(`<div class="bx-ruler tl-ticks" id="bx-ruler"></div>`));
  // when zoomed: where the window is in the whole film; drag it to move along
  const ov = h(`<div class="bx-tlov" id="bx-tlov" title="Where you are in the film: drag to move along it" hidden><i></i></div>`);
  player.append(ov, h(`<div class="filmbar-l bx-bar-l"><span id="bx-tl-a">0:00</span><span>${R ? (R.span && R.beat ? `this render covers ${tsf(R.span[0])} to ${tsf(R.span[1])}` : "") : "no render"}</span><span class="r"><button class="bx-donepins" id="bx-donepins" hidden></button>
    <span class="bx-zoom" id="bx-zoom"><button class="icon-btn sm sq ghost" data-a="zout" title="Zoom out on the timeline (${esc(window.KB.get("tlOut").map(window.KB.label).join(" or "))})" aria-label="Zoom out on the timeline">${icon("zoom-out")}</button><button class="bx-zfit" data-a="zfit" title="How far the timeline is zoomed in. Click to show the whole film (${esc(window.KB.get("tlFit").map(window.KB.label).join(" or "))})">1×</button><button class="icon-btn sm sq ghost" data-a="zin" title="Zoom in on the timeline for finer times (${esc(window.KB.get("tlIn").map(window.KB.label).join(" or "))}). Pinch or ⌘-scroll on it zooms at the pointer; scroll sideways to move along" aria-label="Zoom in on the timeline">${icon("zoom-in")}</button></span>
    <span id="bx-tl-b">${tsf(D)}</span></span></div>`));
  $("#bx-donepins", player).onclick = () => toggleDonePins();
  $('#bx-zoom [data-a="zout"]', player).onclick = () => zoomTl(0.5);
  $('#bx-zoom [data-a="zin"]', player).onclick = () => zoomTl(2);
  $('#bx-zoom [data-a="zfit"]', player).onclick = () => setTl(1, 0, true);
  tlBox.addEventListener("wheel", (e) => tlWheel(e, tlBox, ...tlWin()), { passive: false });
  tlPinch(tlBox, tlWin);
  {
    let grab = null;
    const at = (e) => { const r = ov.getBoundingClientRect(); return ((e.clientX - r.left) / r.width) * D; };
    ov.addEventListener("pointerdown", (e) => {
      if (e.button) return;
      e.preventDefault(); ov.setPointerCapture(e.pointerId);
      const t = at(e), [a, b] = tlWin();
      grab = t >= a && t <= b ? t - a : (b - a) / 2;     // on the window: keep the grip; beside it: bring its middle here
      setTl(TL.z, t - grab, true);
    });
    ov.addEventListener("pointermove", (e) => { if (grab != null) setTl(TL.z, at(e) - grab, true); });
    const drop = () => { grab = null; };
    ov.addEventListener("pointerup", drop); ov.addEventListener("pointercancel", drop);
  }
  new ResizeObserver(() => applyTl()).observe(tlBox);
  // the beat strip under the beat bar; it docks to the top with a small live picture once the player scrolls away
  main.append(toolbar());

  // under the player: one tab bar
  const tabs = h(`<div class="bx-viewtabs"><div class="bx-tabbar" id="bx-tab" role="tablist">
      ${TABS.map(([v, l, ic, tip]) => `<button role="tab" data-v="${v}" title="${esc(tip)}">${icon(ic)}<span>${l}</span>${v === "notes" ? `<i class="bx-badge" id="bx-nbadge"></i>` : ""}</button>`).join("")}</div>
    <span class="meta" id="bx-tabmeta"></span><span class="spacer"></span><span id="bx-tabbtns"></span></div>`);
  main.append(tabs, h(`<div id="bx-body"></div>`));
  // the sound panel is mounted once and kept (hidden on other tabs), so its stems keep playing with the render
  const sndBox = h(`<div id="bx-sound" hidden></div>`);
  main.append(sndBox);
  snd = Sound.mount(sndBox, {
    video: () => vid, t: filmT, duration: () => P.duration || 1, playing: () => !!vid && !vid.paused, rate: () => (vid ? vid.playbackRate : 1),
    seek: (t) => { if (vid) seekFilm(clamp(t, span()[0], Math.min(span()[1], P.duration || 1) - 0.001)); },
    play: () => vid && vid.play().catch(() => {}),
    grab: () => { scrubbing = true; scrubWas = vid && !vid.paused; if (vid) vid.pause(); },
    release: (moved) => { scrubbing = false; if (moved && scrubWas && vid) vid.play().catch(() => {}); },
    cuts: () => P.beats.filter((b) => b.start != null && b.n > 1).map((b) => ({ n: b.n, title: b.title, t: win(b)[0] })),
    setLoop: (r) => { loopRange = r; },
    loop: () => loopRange,
    soundOn: (x) => setSound(x),
    applySound: () => applySound(),
    notes: () => P.sound_notes || {},
    setNotes: (n) => { P.sound_notes = n; paintPins(); },   // paintPins repaints the Notes tab and the notes button
    prompt: (list) => soundPrompt(list),
    view: () => { const b = P.beats[sel]; return b && b.start != null ? win(b) : null; },
    // the timeline's zoom, shared with the beat bar
    window: () => tlWin(), zoomed: () => TL.z > 1,
    setWindow: (a, b) => setTl((P.duration || 1) / Math.max(0.001, b - a), a, true),
    wheel: (e, box, a, b) => tlWheel(e, box, a, b),
    pinch: (box, w) => tlPinch(box, w),
    ruler: (el, a, b, px) => paintRuler(el, a, b, px, (t) => ((t - a) / Math.max(0.001, b - a)) * 100),
    menu: (anchor, items, onPick) => openMenu(anchor, items, onPick),
  }, P.slug);
  applySound();
  tabs.querySelectorAll("#bx-tab button").forEach((b) => (b.onclick = () => setTab(b.dataset.v)));
  setTab(tab, false);
  paintPins();
  commands();
  applyTl();

  rvid = null;
  select(sel, { seek: true, play: false, scroll: false });
  cancelAnimationFrame(raf); raf = requestAnimationFrame(tick);
}
const TABS = [
  ["beats", "Beats", "list-video", "Each beat: plan, references, frames of the render, history"],
  ["notes", "Notes", "message-square", "Notes pinned to frames of the film (N on a frame)"],
  ["script", "Script", "scroll-text", "The script on one page: picture, on-screen words, voice-over"],
  ["sound", "Sound", "audio-lines", "Music, voice and effects on the beat grid; takes"],
  ["assets", "Assets", "image", "Every still and clip the film uses, where, and what made it"],
];

/* ---------- menus: the render picker, the film's ⋯, the transport's ⋯ ---------- */
function pickRender(anchor) {
  openMenu(anchor, P.renders.slice(0, 60).map((r) => ({ value: r.file, on: r === R, html: `<span class="lbl"><b>${esc(short(r))}</b> <span class="dim">${esc(ago(r.mtime))}${r.beat ? ` · ${/^\d+-\d+$/.test(r.beat) ? "beats" : "beat"} ${esc(r.beat)}` : ""}${r.stale ? " · times changed since" : ""}</span>${r.note ? ` · ${esc(r.note)}` : ""}</span>` })), (v) => {
    const r = P.renders.find((x) => x.file === v); if (!r || r === R) return;
    if (C === r) C = null;
    R = r;
    // A render of one beat (or a span) can't show the beat you're on: go to the first beat it covers, so picking it
    // doesn't bounce straight back to a render that does.
    if (!covered(P.beats[sel])) { const i = P.beats.findIndex((b) => covered(b)); if (i >= 0) sel = i; }
    remember(); draw($("#main"));
  });
}
/* Finder: the render on screen, the folder of renders, the film's own folder */
async function reveal(path, how = "reveal") {
  try {
    const r = await fetch("/api/reveal", { method: "POST", body: JSON.stringify({ path, how }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || r.statusText);
    toast(how === "open" ? `Opening ${path.split("/").pop()}` : `Showing ${j.path} in Finder`);
  } catch (e) { toast(`Couldn't open it: ${e.message}`); }
}
function filmMenu(anchor) {
  const items = [
    { value: "", html: `<span class="lbl dim">${esc([P.engine, P.dir, P.duration ? tsf(P.duration) : "", `${P.beats.length} beats`, P.style ? (P.style === "none" ? "no profile" : `profile ${window.Profiles?.get(P.style)?.name || P.style}`) : "", P.profile ? `motion ${P.profile}` : ""].filter(Boolean).join(" · "))}</span>` },
    { value: "folder", html: `${icon("folder")}<span class="lbl">Move to folder…</span><span class="c">${esc(window.Folders ? Folders.name(P.folder) : "")}</span>` },
    { value: "reload", html: `${icon("rotate-cw")}<span class="lbl">Reload the plan and renders</span><kbd>R</kbd>` },
    { value: "script", html: `${icon("copy")}<span class="lbl">Copy the script as a table</span>` },
    ...(P.board ? [{ value: "board", html: `${icon("layout-list")}<span class="lbl">Open the board: ${esc(P.board)}</span>` }] : []),
    ...(R ? [{ value: "finder", html: `${icon("folder-open")}<span class="lbl">Show ${esc(short(R))} in Finder</span>` },
      { value: "play", html: `${icon("play")}<span class="lbl">Open ${esc(short(R))} in QuickTime</span>` }] : []),
    { value: "code", html: `${icon("folder-open")}<span class="lbl">Open the film's folder (${esc(P.dir)})</span>` },
    { value: "storyboard", html: `${icon("file-text")}<span class="lbl">Copy the plan's path</span>` },
  ];
  openMenu(anchor, items, (v) => {
    if (v === "folder") folderMenu(anchor);
    else if (v === "reload") renderFilm($("#main"), P.slug);
    else if (v === "script") copy(scriptMarkdown(), "Script copied as a table");
    else if (v === "board") location.hash = `#/boards/${encodeURIComponent(P.board)}`;
    else if (v === "storyboard") copy(P.storyboard, `Copied ${P.storyboard}`);
    else if (v === "finder") reveal(R.file);
    else if (v === "play") reveal(R.file, "open");
    else if (v === "code") reveal(P.dir, "open");
  });
}
/* Move the film to one of the project's folders: a Remotion film's renders go with it, a HyperFrames film's whole folder moves */
function folderMenu(anchor) {
  openMenu(anchor, Folders.items(P.folder || "", icon, true), async (v) => {
    const to = await Folders.pick(v);
    if (v === "+" && !to) return;
    if ((to || "") === (P.folder || "")) return;
    try {
      P = await call(`/api/productions/${encodeURIComponent(P.slug)}/folder`, { method: "POST", body: JSON.stringify({ folder: to }) });
      R = P.renders.find((r) => r.name === R?.name) || P.renders[0] || null; C = null; remember();
      toast(to ? `Moved to ${Folders.name(to)}: renders go to ${P.renders_dir}/` : `Moved out of its folder: renders go to ${P.renders_dir}/`);
      draw($("#main"));
    } catch (e) { toast(`Couldn't move it: ${e.message}`); }
  });
}
const fsRef = () => document.querySelector(".bx-player")?.classList.contains("with-ref");
function playMenu(anchor) {
  const items = [
    ...[0.25, 0.5, 1].map((v) => ({ value: `speed:${v}`, on: speed === v, html: `<span class="lbl">${v === 1 ? "Normal speed" : `${v}× speed`}</span>` })),
    { sep: true },
    { value: "mode:loop", on: mode === "loop", html: `<span class="lbl">Loop the beat</span><kbd>L</kbd>` },
    { value: "mode:play", on: mode === "play", html: `<span class="lbl">Play the film through</span><kbd>L</kbd>` },
    { sep: true },
    { value: "sync", on: sync, html: `<span class="lbl">Reference timed to the beat</span><kbd>S</kbd>` },
    { value: "fsref", on: fsRef(), html: `<span class="lbl">Reference beside the render in full screen</span>` },
    { value: "full", html: `<span class="lbl">${document.fullscreenElement ? "Exit full screen" : "Full screen"}</span><kbd>F</kbd>` },
  ];
  openMenu(anchor, items, (v) => {
    if (v.startsWith("speed:")) setSpeed(+v.slice(6));
    else if (v.startsWith("mode:")) { setMode(v.slice(5)); paintTrState(); }
    else if (v === "sync") toggleSync();
    else if (v === "fsref") toggleFsRef();
    else if (v === "full") toggleFull();
  });
}
function setSpeed(v) { speed = v; if (vid) vid.playbackRate = speed; paintTrState(); }
function toggleSync() { sync = !sync; if (rvid) rvid.playbackRate = speed; lastLabel = 0; refLabel(); paintTrState(); toast(sync ? "Reference timed to the beat" : "Reference at its own pace"); }
/* the reference (or storyboard, or compared render) beside the render: hide it to give the render the width; kept in this browser */
const refHidden = () => localStorage.getItem("cr.refHidden") === "1";
function toggleRefPane(show) {
  const st = document.querySelector(".bx-stage"); if (!st) return;
  const solo = show === undefined ? !st.classList.contains("solo") : !show;
  st.classList.toggle("solo", solo); localStorage.setItem("cr.refHidden", solo ? "1" : "0");
  if (solo && rvid && !rvid.paused) rvid.pause();
}
function toggleFsRef() { const pl = document.querySelector(".bx-player"); if (!pl) return; const on = pl.classList.toggle("with-ref"); localStorage.setItem("cr.fsRef", on ? "1" : "0"); paintFull(); }
// the transport's toggles show their state: loop or play through, the speed, the reference timing
function paintTrState() {
  document.querySelectorAll("#bx-mode button").forEach((b) => b.classList.toggle("on", b.dataset.v === mode));   // the switch's cap follows .on
  if (speedKnob) speedKnob.set(speed);
  const sb = document.querySelector('.bx-tr [data-a="sync"]');
  if (sb) { sb.classList.toggle("on", sync); sb.classList.toggle("ghost", !sync); $("span", sb).textContent = sync ? "Ref synced" : "Ref own pace"; }
}
/* ---------- ⌘K: every action that isn't on the screen ---------- */
function commands() {
  if (!window.CR?.command) return;
  CR.uncommand("build.");
  const on = () => !!P && location.hash.startsWith(`#/build/${P.slug}`);
  const cmd = (id, title, run, extra = {}) => CR.command({ id: `build.${id}`, title, group: "Film", when: on, run, ...extra });
  cmd("notes", "Copy notes prompt", () => copy(notesPrompt(), `Notes prompt copied: paste it into ${SP.ai}`), { when: () => on() && noteCount() > 0 });
  cmd("nmode-auto", "Notes: Auto (a chat picks them up as you add them)", () => setNotesMode("auto"), { when: () => on() && P.notes_mode === "manual" });
  cmd("nmode-manual", "Notes: Manual (they wait for Copy notes prompt)", () => setNotesMode("manual"), { when: () => on() && (P.notes_mode || "auto") === "auto" });
  cmd("listen", "Copy a prompt that has a chat pick up notes as they come", () => copy(listenPrompt(), `Prompt copied: paste it into a chat with ${SP.ai}`), { when: () => on() });
  cmd("pin", "Pin a note to this frame", () => compose(), { keys: "N" });
  cmd("done-pins", "Done notes on the beat bar: hide / show", () => toggleDonePins(), { when: () => on() && (P.pins || []).some((x) => x.status === "done") });
  cmd("render", "Show another render…", () => { const b = document.querySelector('[data-a="render"]'); if (b) pickRender(b); });
  cmd("compare", "Compare with another render…", () => { const b = document.querySelector('.bx-tr [data-a="cmp"]'); if (b) pickCompare(b); }, { keys: "X" });
  cmd("compare-off", "Stop comparing", () => setCompare(null), { when: () => on() && !!C });
  cmd("swap", "Swap the two renders", () => swapCompare(), { keys: "V", when: () => on() && !!C });
  cmd("loop", "Loop the beat / play through", () => { setMode(mode === "loop" ? "play" : "loop"); paintTrState(); }, { keys: "L" });
  for (const v of [0.25, 0.5, 1]) cmd(`speed-${v}`, v === 1 ? "Normal speed" : `Play at ${v}× speed`, () => setSpeed(v));
  cmd("sync", "Reference timed to the beat / own pace", () => toggleSync(), { keys: "S" });
  cmd("sound", "Sound on / off", () => setSound(!soundOn), { keys: "M" });
  cmd("full", "Full screen", () => toggleFull(), { keys: "F" });
  cmd("fsref", "Reference beside the render in full screen", () => toggleFsRef());
  cmd("refpane", "Show or hide the reference beside the render", () => toggleRefPane(), { keys: "H" });
  cmd("tl-in", "Zoom in on the timeline", () => zoomTl(2), { keys: "=" });
  cmd("tl-out", "Zoom out on the timeline", () => zoomTl(0.5), { keys: "-", when: () => on() && TL.z > 1 });
  cmd("tl-fit", "Show the whole film on the timeline", () => setTl(1, 0, true), { keys: "0", when: () => on() && TL.z > 1 });
  cmd("tl-beat", "Zoom the timeline to the selected beat", () => { const b = P.beats[sel]; if (b && b.start != null) { const [a, e] = win(b), pad = (e - a) * 0.08; setTl((P.duration || 1) / (e - a + 2 * pad), a - pad, true); } });
  cmd("reload", "Reload the plan and renders", () => renderFilm($("#main"), P.slug), { keys: "R" });
  cmd("finder", "Show the render in Finder", () => R && reveal(R.file));
  cmd("quicktime", "Open the render in QuickTime", () => R && reveal(R.file, "open"));
  cmd("folder", "Open the film's folder", () => reveal(P.dir, "open"));
  cmd("script-copy", "Copy the script as a table", () => copy(scriptMarkdown(), "Script copied as a table"));
  for (const [v, l] of TABS) cmd(`tab-${v}`, `Show ${l.toLowerCase()}`, () => setTab(v));
  if (P.board) cmd("board", `Open the board: ${P.board}`, () => (location.hash = `#/boards/${encodeURIComponent(P.board)}`));
}

/* ---------- the beat strip: one small card per beat, following the playhead. It shows only once the player has
   scrolled out of view (at rest the beat bar does the job), docked to the top with a small live picture. ---------- */
/* The toolbar docks to the top of the page once the render scrolls out of view: it grows a small live picture of the
   render, play/pause and the timecode, so the film keeps playing in sight while the rows are read. */
function toolbar() {
  const dock = h(`<div class="bx-dock">
    <button class="bx-mini" title="Back to the player"><canvas width="256" height="144"></canvas></button>
    <div class="bx-dctl"><button class="icon-btn sm sq" data-a="dplay" title="Play / pause (Space)">${icon("play")}</button>
      <span class="tc tc-copy" id="bx-dtc" title="Click to copy the time with the beat ID"></span><span class="bx-dnow" id="bx-dnow"></span></div>
    <div class="bx-tb" title="Click a beat to go there · swipe sideways or Shift + scroll to move along the film"><div class="bx-tb-track"></div></div></div>`);
  const tb = $(".bx-tb", dock);
  const track = $(".bx-tb-track", tb);
  P.beats.forEach((b, i) => {
    const [a, e] = b.start == null ? [null, null] : win(b);
    const card = h(`<button class="bx-tb-card st-${b.status}" data-i="${i}" title="${esc(`${b.n}. ${b.title}${a == null ? "" : ` · ${tsf(a)} to ${tsf(e)}`} · ${STATUS[b.status] || b.status}${b.review ? ` · note: ${b.review}` : ""}`)}">
      <div class="th"></div><div class="meta"><span class="n">${dot(b.status)}${b.n}</span><span class="t">${esc(b.title)}</span></div><i class="prog"></i>${b.review ? `<i class="note"></i>` : ""}</button>`);
    const th = $(".th", card);
    if (covered(b)) th.append(h(`<img alt="" loading="lazy" src="${frameUrl(a + (e - a) * 0.5, 240)}">`));
    else { const s = BY_KEY[b.refs[0]]; if (s) { const t = thumb(s, { scrub: false }); th.append(t); th.classList.add("ref"); } else th.append(h(`<span>${a == null ? "no time" : "not rendered"}</span>`)); }
    // highlight the beat and play it in the render, but leave the page and the strip where they are
    card.addEventListener("mousedown", (e) => e.preventDefault()); // no focus, so no scroll-into-view
    card.onclick = () => (tbClick = performance.now(), select(i, { seek: true, play: !!vid && (!vid.paused || mode === "loop"), scroll: false, center: false }));
    const act = actsOf().find((x) => x.from === i);
    if (act) track.append(h(`<span class="bx-tb-act" title="${esc(act.name)}: beats ${act.from + 1} to ${act.to + 1}">${esc(act.name)}</span>`));
    track.append(card);
  });
  // the page wheel always scrolls the page; swipe sideways (or Shift + wheel) to move along the strip
  $('[data-a="dplay"]', dock).onclick = togglePlay;
  $(".bx-mini", dock).onclick = () => $("#main").scrollTo({ top: 0, behavior: "smooth" });
  // dock when the player has scrolled out of view
  requestAnimationFrame(() => {
    const stage = document.querySelector(".bx-stage"); if (!stage) return;
    const io = new IntersectionObserver(([en]) => { dock.classList.toggle("docked", en.intersectionRatio < 0.35 && en.boundingClientRect.top < 0); }, { root: $("#main"), threshold: [0, 0.35, 0.7, 1] });
    io.observe(stage);
  });
  // the strip sits under the beat bar, and sticks to the top with a small live picture once the player scrolls away
  return dock;
}
function paintDock(t) {
  const dock = document.querySelector(".bx-dock.docked"); if (!dock) return;
  const c = $(".bx-mini canvas", dock);
  if (vid && vid.readyState >= 2) { try { const g = c.getContext("2d"); g.drawImage(vid, 0, 0, c.width, c.height); } catch {} }
  const tc = $("#bx-dtc", dock); tc.textContent = `${tsf(t)}  f${Math.round(t * (P.fps || 30))}`; tc.dataset.copy = beatStamp(t);
  const nb = P.beats[nowIdx]; $("#bx-dnow", dock).textContent = nb ? `${nb.n} · ${nb.title}` : "";
  const pb = $('[data-a="dplay"]', dock), want = vid && !vid.paused ? "pause" : "play";
  if (pb.dataset.ic !== want) { pb.dataset.ic = want; pb.innerHTML = icon(want); }
}
let tbClick = 0; // the person clicked a card: let the strip stay put while that beat starts playing
let tbUser = 0; // the person scrolled the toolbar: don't pull it back for a moment
function centerCard(i) {
  const tb = document.querySelector(".bx-tb"), c = tb && tb.querySelector(`.bx-tb-card[data-i="${i}"]`);
  if (!c || performance.now() - tbUser < 2500) return;
  tb.scrollTo({ left: c.offsetLeft - tb.clientWidth / 2 + c.offsetWidth / 2, behavior: "smooth" });
}
document.addEventListener("wheel", (e) => { if (e.target.closest?.(".bx-tb")) tbUser = performance.now(); }, { passive: true });

/* ---------- a row per beat: storyboard · references · render · review ---------- */
function row(b, i) {
  const [a, e] = b.start == null ? [null, null] : win(b);
  const el = h(`<div class="bx-row st-${b.status}" data-i="${i}">
    <div class="bx-n" title="${esc(STATUS[b.status] || b.status)}">${dot(b.status)}${b.n}</div>
    <div class="bx-sb">
      <div class="id">${esc(b.id)} · ${a == null ? "no window in cues.json" : `${tcCopy(`${tsf(a)} to ${tsf(e)}`, stampRange(`${P.slug}/${b.id}`, a, e))} · ${(e - a).toFixed(1)}s`}</div>
      <div class="t">${esc(b.title)}</div>
      ${b.on_screen ? `<p class="plan">${esc(b.on_screen)}</p>${b.on_screen.length > 200 ? `<button class="bx-more">more</button>` : ""}` : `<p class="dim">${P.engine === "remotion" ? "What's on screen isn't written yet (storyboard.json, on_screen)." : ""}</p>`}
      ${b.copy ? `<p class="copy">${esc(b.copy)}</p>` : ""}
      <div class="bx-chips">${(b.roles || []).map((r) => `<span class="chip">${esc(r)}</span>`).join("")}${b.transition_in ? `<span class="chip" title="transition in">in: ${esc(b.transition_in)}</span>` : ""}</div>
      ${b.notes || b.sound || b.blueprint ? `<details><summary>plan notes</summary>${b.blueprint ? `<p><b>blueprint</b> ${esc(b.blueprint)}</p>` : ""}${b.sound ? `<p><b>sound</b> ${esc(b.sound)}</p>` : ""}${b.notes ? `<p class="pre">${esc(b.notes)}</p>` : ""}</details>` : ""}
    </div>
    <div class="bx-refs"></div>
    <div class="bx-frames"></div>
    <div class="bx-rev">
      <button class="icon-btn sm ghost bx-status" title="Status">${statusBtn(b.status)}</button>
      <textarea class="note bx-inline" rows="2" placeholder="A note on the whole beat">${esc(b.review)}</textarea>
      <div class="bx-bpins"></div>
      ${b.log?.length ? `<details class="bx-log"><summary>${b.log.length} earlier note${b.log.length > 1 ? "s" : ""}</summary>${b.log.slice().reverse().map((l) => `<p><span>${esc(l.at || "")} ${esc(l.render || "")}</span>${esc(l.note || "")}<br><b>done:</b> ${esc(l.done || "")}</p>`).join("")}</details>` : ""}
      <div class="bx-btns"><button class="icon-btn sm ghost" data-a="prompt">${icon("copy")}${b.review ? "Fix prompt" : "Build prompt"}</button>${P.engine === "remotion" ? `<button class="icon-btn sm sq ghost" data-a="sheet" title="Copy the command that makes this beat's pairing sheet (storyboard | reference | render)">${icon("file-text")}</button>` : ""}</div>
    </div>
  </div>`);

  const refs = $(".bx-refs", el);
  const scenes = b.refs.map((k) => BY_KEY[k]).filter(Boolean);
  for (const s of scenes) {
    const w = h(`<div class="bx-ref" title="${esc(s.key + "  " + s.title)}"></div>`);
    const th = thumb(s); th.onclick = (ev) => { ev.stopPropagation(); select(i, { seek: sel !== i, ref: s.key }); };
    w.append(th, h(`<div class="cap"><span class="t">${esc(s.title)}</span><a href="#/scene/${esc(s.key)}" title="Open ${esc(s.key)}">${esc(s.key)}</a></div>`));
    refs.append(w);
  }
  for (const k of b.missing_refs || []) refs.append(h(`<div class="dim">${esc(k)}: not in the library</div>`));
  if (!b.refs.length) refs.append(h(`<div class="dim">${P.engine === "remotion" ? "No reference scene." : "No library reference."}</div>`));

  const fr = $(".bx-frames", el);
  if (P.renders.length > 1 && b.start != null) {
    const hd = h(`<details class="bx-hist"><summary>${icon("history")}History</summary><div></div></details>`);
    hd.ontoggle = () => { if (hd.open) beatHistory(b, $("div", hd)); };
    hd.onclick = (ev) => ev.stopPropagation();
    queueMicrotask(() => fr.after(hd));
  }
  if (covered(b)) {
    for (const k of [0.12, 0.5, 0.88]) {
      const t = a + (e - a) * k;
      const im = h(`<img loading="lazy" alt="" src="${frameUrl(t)}" title="${tsf(t)}: click to go there">`);
      im.onclick = (ev) => { ev.stopPropagation(); select(i, { seek: false }); if (vid) { vid.pause(); seekFilm(t); } };
      fr.append(im);
    }
  } else fr.append(h(`<div class="dim">${!R ? "Not rendered yet." : b.start == null ? "No window in cues.json." : `Not in ${esc(R.name)}.`}</div>`));

  $(".bx-more", el)?.addEventListener("click", (ev) => { ev.stopPropagation(); const o = $(".bx-sb", el).classList.toggle("open"); ev.currentTarget.textContent = o ? "less" : "more"; });
  el.onclick = (ev) => { if (ev.target.closest("textarea, button, a, details, .seg")) return; tbClick = performance.now(); select(i, { seek: true, play: true }); };
  $(".bx-status", el).onclick = (ev) => openMenu(ev.currentTarget, ORDER.map((s) => ({ value: s, on: s === b.status, html: `${dot(s)}<span class="lbl">${cap(STATUS[s])}</span>` })), (v) => saveBeat(b, { status: v }));
  const ta = $("textarea", el);
  let t1; ta.oninput = () => {
    clearTimeout(t1);
    t1 = setTimeout(() => {
      const review = ta.value.trim(), body = { review };
      if (review && ["review", "approved"].includes(b.status)) body.status = "changes"; // a note on a rendered beat asks for a change
      saveBeat(b, body, false);
    }, 600);
  };
  $('[data-a="prompt"]', el).onclick = () => copy(beatPrompt(b), b.review ? "Fix prompt copied" : "Build prompt copied");
  $('[data-a="sheet"]', el)?.addEventListener("click", () => copy(`${SP.cmd("film")} sheet ${P.slug} --beat ${b.id}`, "Command copied"));
  return el;
}
async function saveBeat(b, body, repaint = true) {
  try {
    const np = await patchBeat(P.slug, b.id, body);
    const nb = np.beats.find((x) => x.id === b.id);
    Object.assign(b, { status: nb.status, review: nb.review, log: nb.log });
    // keep the textarea being typed in: repaint classes, buttons and the bar only
    const el = document.querySelector(`.bx-row[data-i="${b.n - 1}"]`);
    if (el) {
      el.className = el.className.replace(/st-\w+/, `st-${b.status}`);
      const sb = $(".bx-status", el); if (sb) sb.innerHTML = statusBtn(b.status);
      const pb = $('[data-a="prompt"]', el); if (pb) pb.innerHTML = icon("copy") + (b.review ? "Fix prompt" : "Build prompt");
      const nd = $(".bx-n .st-dot", el); if (nd) nd.className = `st-dot st-${b.status}`;
    }
    const seg = document.querySelector(`.bx-seg[data-i="${b.n - 1}"]`);
    if (seg) { seg.className = seg.className.replace(/st-\w+/, `st-${b.status}`); if (b.review && !$("i", seg)) seg.append(document.createElement("i")); if (!b.review) $("i", seg)?.remove(); }
    const nbtn = document.querySelector('[data-a="notes"]');
    if (nbtn) paintNotesBtn();
    toast(repaint ? `Beat ${b.n}: ${STATUS[b.status]}` : `Saved to ${P.engine === "remotion" ? "storyboard.json" : "review.json"}`);
  } catch (e) { toast(`Couldn't save: ${e.message}`); }
}

/* ---------- selection, playback, the reference pane ---------- */
function setMode(m) { mode = m; remember(); if (mode === "play" && vid && vid.paused) vid.play().catch(() => {}); }
// Picking a beat never moves the page or the strip on its own: only playback (center) and [ ] (scroll + center) do.
function select(i, { seek = true, play = false, scroll = false, center = false, ref = null } = {}) {
  if (!P || !P.beats[i]) return;
  const b = P.beats[i], changed = i !== sel || !rvid;
  sel = i; remember();
  document.querySelectorAll(".bx-row, .bx-srow").forEach((r) => r.classList.toggle("sel", +r.dataset.i === i));
  document.querySelectorAll(".bx-seg, .bx-tb-card").forEach((r) => r.classList.toggle("sel", +r.dataset.i === i));
  // the page follows the selection to its row, except while playing through (then only the toolbar follows, so the render stays in view)
  const playingThrough = mode === "play" && vid && !vid.paused;
  if (scroll && !playingThrough) document.querySelector(`.bx-row[data-i="${i}"], .bx-srow[data-i="${i}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  if (center) centerCard(i);
  if (vid && R && !covered(b) && b.start != null) {
    const other = P.renders.find((r) => { const keep = R; R = r; const ok = covered(b); R = keep; return ok; });
    if (other && seek) { R = other; remember(); toast(`Switched to ${other.name}: it covers beat ${b.n}`); draw($("#main")); return; }
  }
  if (ref || changed || C) paneFor(b, ref);
  if (snd && snd.follow) snd.follow();
  if (seek && vid && covered(b)) { seekFilm(win(b)[0]); if (play) vid.play().catch(() => {}); }
}
function paneFor(b, ref, force) {
  const box = $("#bx-ref"); if (!box) return;
  if (C) {
    if (rvid) rvid.pause();
    $("#bx-sh").textContent = "Compare"; $("#bx-tabs").innerHTML = "";
    $("#bx-sl").innerHTML = `<b>${esc(short(C))}</b> ${esc(ago(C.mtime))}${C.note ? ` · ${esc(C.note)}` : ""} <button class="icon-btn sm ghost" id="bx-swap" title="Swap the two (V)">${icon("arrow-left-right")}Swap</button>`;
    $("#bx-swap").onclick = swapCompare;
    if (!cvid || cvid.dataset.file !== C.file || !box.contains(cvid)) {
      box.innerHTML = "";
      cvid = document.createElement("video");
      cvid.muted = true; cvid.playsInline = true; cvid.preload = "auto"; cvid.src = fileUrl(C.file); cvid.dataset.file = C.file;
      cvid.onerror = () => { box.innerHTML = `<div class="nofile">Can't play ${esc(C.file)}.</div>`; };
      box.append(cvid);
    }
    if (b && b.start != null && !C.beats?.[b.id]) $("#bx-sl").insertAdjacentHTML("beforeend", ` <span class="warn">this beat isn't in ${esc(short(C))}: same film time</span>`);
    return;
  }
  if (cvid && box.contains(cvid)) { cvid.pause(); box.innerHTML = ""; cvid = null; rvid = null; }
  const scenes = b.refs.map((k) => BY_KEY[k]).filter(Boolean);
  const s = scenes.find((x) => x.key === ref) || scenes.find((x) => x.key === refKey) || scenes[0];
  $("#bx-sh").textContent = s ? "Reference" : "Storyboard";
  if (s && s.upload) {  // an uploaded image, GIF or clip: show it as it is
    if (rvid) rvid.pause(); rvid = null; refKey = null;
    $("#bx-tabs").innerHTML = scenes.length > 1 ? scenes.map((x) => `<button class="${x === s ? "on" : ""}" data-k="${esc(x.key)}">${esc(x.key.split("/")[1])}</button>`).join("") : "";
    document.querySelectorAll("#bx-tabs button").forEach((t) => (t.onclick = () => paneFor(b, t.dataset.k)));
    const x = s.upload;
    box.innerHTML = x.kind === "video" ? `<video src="${fileUrl(x.file)}" muted loop autoplay playsinline></video>` : `<img class="bx-upimg" alt="" src="${fileUrl(x.file)}">`;
    $("#bx-sl").innerHTML = `<a href="#/scene/${esc(s.key)}">${esc(s.key)}</a> ${esc(s.title)}`;
    return;
  }
  $("#bx-tabs").innerHTML = scenes.length > 1 ? scenes.map((x) => `<button class="${x === s ? "on" : ""}" data-k="${esc(x.key)}">${esc(x.key.split("/")[1])}</button>`).join("") : "";
  document.querySelectorAll("#bx-tabs button").forEach((t) => (t.onclick = () => paneFor(b, t.dataset.k)));
  if (!s) {
    refKey = null; if (rvid) rvid.pause();
    box.innerHTML = "";
    box.append(h(`<div class="bx-card"><div class="n">${b.n}</div><div class="t">${esc(b.title)}</div>${b.on_screen ? `<p>${esc(b.on_screen)}</p>` : ""}${b.copy ? `<p class="copy">${esc(b.copy)}</p>` : ""}</div>`));
    $("#bx-sl").textContent = `beat ${b.n}`;
    return;
  }
  refKey = s.key;
  const file = FILMS[s.film].file;
  if (!rvid || rvid.dataset.file !== file || !box.contains(rvid)) {
    box.innerHTML = "";
    rvid = document.createElement("video");
    rvid.muted = true; rvid.playsInline = true; rvid.preload = "auto"; rvid.src = fileUrl(file); rvid.dataset.file = file;
    rvid.onerror = () => { box.innerHTML = `<div class="nofile">Can't play ${esc(file)}.</div>`; };
    box.append(rvid);
  }
  const go = () => { try { rvid.currentTime = s.start + 0.01; } catch {} };
  rvid.readyState >= 1 ? go() : rvid.addEventListener("loadedmetadata", go, { once: true });
  refLabel();
}
function refLabel() {
  if (C) return;
  const s = BY_KEY[refKey], b = P.beats[sel]; if (!s || !b) return;
  const rd = s.end - s.start, [a, e] = b.start == null ? [0, rd] : win(b);
  const html = `<a href="#/scene/${esc(s.key)}">${esc(s.key)}</a> <span class="tc-copy" id="bx-rtc" title="Click to copy the reference time with its scene ID"></span> ${esc(s.title)} · ${rd.toFixed(1)}s${sync && b.start != null ? ` · beat ${(e - a).toFixed(1)}s, plays at ${(rd / (e - a)).toFixed(2)}×` : ""}`;
  const el = $("#bx-sl");
  if (el.dataset.html !== html) { el.innerHTML = html; el.dataset.html = html; } // don't swap the timecode out from under the pointer
}
function driveRef(t) {
  const s = BY_KEY[refKey], b = P.beats[sel];
  if (!rvid || !s || !b || rvid.readyState < 1) return;
  const playing = vid && !vid.paused;
  if (sync && vid && b.start != null) {
    const [a, e] = win(b), rd = s.end - s.start, rate = rd / Math.max(0.05, e - a);
    const target = s.start + clamp(t - a, 0, e - a) * rate;
    const base = clamp(rate * speed, 0.0625, 16), drift = target - rvid.currentTime;
    // While the film plays, the reference catches up by running a little faster or slower, not by seeking: a seek makes
    // WebKit decode a fresh burst of frames, and seeking every half second starved the film's own sound (crackles near
    // cuts). It only jumps for a real gap (a new beat, a scrub) and never while a jump is still under way.
    if (!playing) { rvid.playbackRate = base; if (Math.abs(drift) > 0.02 && !rvid.seeking) try { rvid.currentTime = target; } catch {} }
    else if (Math.abs(drift) > 0.75) { rvid.playbackRate = base; if (!rvid.seeking) try { rvid.currentTime = target; } catch {} }
    else {
      const want = clamp(base * (1 + Math.round(clamp(drift, -0.4, 0.4) * 10) / 10), 0.0625, 16);   // steps of 10%: no change every frame
      if (Math.abs(rvid.playbackRate - want) > 1e-3) rvid.playbackRate = want;
    }
  } else {
    rvid.playbackRate = speed;
    if (rvid.currentTime >= s.end - 0.03 || rvid.currentTime < s.start - 0.25) try { rvid.currentTime = s.start; } catch {}
  }
  if (playing && rvid.paused) rvid.play().catch(() => {});
  else if (!playing && !rvid.paused && vid) rvid.pause();
  else if (!vid && rvid.paused) rvid.play().catch(() => {});
}
let scrubWas = false;
function applySound() {
  // A render with its own mix (a music test, an older score) plays its own sound: the stems are the current film's.
  const stems = snd && snd.mode() === "stems" && !(R && (R.own_sound || /-draft-music-/.test(R.name)));
  if (vid) vid.muted = stems || !soundOn;
  if (snd) snd.setOn(soundOn && stems);
  applyVolume();
}
function setSound(x) {
  soundOn = x;
  // Sound on with the level knob all the way down would still be silence (the knob is remembered per window, so it
  // can sit at zero from another day): turning the sound on brings the level back to full.
  if (soundOn && volume < 0.02) { setVolume(1); volKnob?.set(1); }
  applySound();
  const b = document.querySelector('.bx-tr [data-a="mute"]');
  if (b) { $("span", b).innerHTML = icon(soundOn ? "volume-2" : "volume-x"); b.classList.toggle("on", soundOn); b.setAttribute("aria-pressed", soundOn); }
  document.querySelector("#bx-vol")?.classList.toggle("idle", !soundOn);   // the level knob goes quiet with the sound off
}
// The monitor level: how loud the film plays here (the render's own sound, the stems, a voice line). It never touches
// the film's mix. The knob's travel is tapered (the gain is its square), so the lower half is as useful as the upper.
const monitorGain = () => volume * volume;
function applyVolume() {
  if (vid) vid.volume = monitorGain();
  if (snd && snd.setVolume) snd.setVolume(monitorGain());
  if (vo) vo.volume = monitorGain();
}
function setVolume(v) {
  volume = clamp(+v || 0, 0, 1);
  try { localStorage.setItem("cr.vol", volume.toFixed(3)); } catch {}
  applyVolume();
}
let lastLabel = 0;
// A timecode is written only when it changes: rewriting the same text every frame made WebKit repaint the transport
// (its knobs are drawn with gradients) sixty times a second while nothing played, and the Mac app lagged.
function setTc(el, text, copy) {
  if (!el) return;
  if (el.textContent !== text) el.textContent = text;
  if (el.dataset.copy !== copy) el.dataset.copy = copy;
}
function tick() {
  raf = requestAnimationFrame(tick);
  if (!P || !document.querySelector(".bx-stage")) return;
  const t = filmT();
  if (vid && R) {
    const b = P.beats[sel];
    if (!scrubbing && loopRange && !vid.paused) {
      if (t >= loopRange[1] - 0.02 || t < loopRange[0] - 0.25) seekFilm(loopRange[0]);
    } else if (!scrubbing && mode === "loop" && b && covered(b) && !vid.paused) {
      const [a, e] = win(b);
      if (t >= e - 0.02 || t < a - 0.25) seekFilm(a);
    }
    if (vid.ended && mode === "play") { seekFilm(0); vid.play().catch(() => {}); }
    const i = beatAt(t);
    if (i !== nowIdx) {
      nowIdx = i;
      document.querySelectorAll(".bx-seg").forEach((r) => r.classList.toggle("now", +r.dataset.i === i));
      document.querySelectorAll(".bx-row, .bx-tb-card").forEach((r) => r.classList.toggle("now", +r.dataset.i === i));
      document.querySelectorAll(".bx-tb-card .prog").forEach((p) => (p.style.width = ""));
      if (i >= 0 && performance.now() - tbClick > 4000) centerCard(i);
      const nb = P.beats[i];
      $("#bx-now").textContent = nb ? `beat ${nb.n} · ${nb.title}` : "";
      if (mode === "play" && !scrubbing && i >= 0 && i !== sel) select(i, { seek: false, center: performance.now() - tbClick > 4000 });
    }
    setTc($("#bx-tc"), `${tsf(t)}  f${Math.round(t * (P.fps || 30))}`, beatStamp(t));
    const cur = P.beats[nowIdx], pc = cur && document.querySelector(`.bx-tb-card[data-i="${nowIdx}"] .prog`);
    if (pc && cur.start != null) { const [a, e] = win(cur); pc.style.width = `${clamp((t - a) / (e - a), 0, 1) * 100}%`; }
    paintDock(t);
    $("#bx-ph").style.left = `${(t / (P.duration || 1)) * 100}%`;
    // zoomed in: when the playhead moves out of the window, the window goes with it (not while you are moving the window yourself)
    if (TL.z > 1 && !scrubbing && Math.abs(t - tlPrevT) > 1e-4 && performance.now() - tlHold > 1500) {
      const [a, b] = tlWin();
      if (t < a || t > b) setTl(TL.z, vid.paused ? t - (b - a) / 2 : t - (b - a) * 0.06);
    }
    tlPrevT = t;
  }
  if (C) driveCompare(t); else driveRef(t);
  if (snd) snd.tick(t);
  const rtc = document.getElementById("bx-rtc"), rs = BY_KEY[refKey];
  if (rtc && rvid && rs) { const rt = rvid.currentTime; setTc(rtc, tsf(rt), stampAt(rs.key, rt, FILMS[rs.film].fps || 30, rs.start)); }
  if (sync && performance.now() - lastLabel > 500) { lastLabel = performance.now(); refLabel(); }
}
function togglePlay() { if (!vid) return; vid.paused ? vid.play().catch(() => {}) : vid.pause(); }
function step(dir) { if (!vid) return; vid.pause(); seekFilm(filmT() + dir / (P.fps || 30)); }

/* ---------- under the player: beats · script · assets ---------- */
function setTab(t, save = true) {
  tab = t;
  document.querySelectorAll("#bx-tab button").forEach((b) => { b.classList.toggle("on", b.dataset.v === t); b.setAttribute("aria-selected", b.dataset.v === t); });
  if (save) {
    localStorage.setItem(`cr.tab.${P.slug}`, t);
    history.replaceState(null, "", `#/build/${P.slug}${t === "notes" ? "" : "/" + t}`);
  }
  const body = $("#bx-body"); if (!body) return;
  body.innerHTML = ""; $("#bx-tabmeta").textContent = ""; $("#bx-tabbtns").innerHTML = "";
  const sb = document.getElementById("bx-sound"); if (sb) sb.hidden = t !== "sound";
  body.hidden = t === "sound";
  if (t === "script") renderScript(body);
  else if (t === "assets") renderAssets(body);
  else if (t === "notes") { body.append(h(`<section class="bx-notes" id="bx-notes"></section>`)); paintPins(); }
  else if (t === "beats") { const rows = h(`<div class="bx-rows"></div>`); P.beats.forEach((b, i) => { actHead(rows, i); rows.append(row(b, i)); }); body.append(rows); paintPins(); }
  else if (t === "sound") { $("#bx-tabmeta").textContent = "Music, voice and effects on the beat grid"; snd?.follow?.(); window.dispatchEvent(new Event("resize")); }
  document.querySelectorAll(".bx-row, .bx-srow").forEach((r) => r.classList.toggle("sel", +r.dataset.i === sel));
  paintNotesBtn();
}
function actHead(box, i) {
  const a = actsOf().find((x) => x.from === i); if (!a) return;
  const b0 = P.beats[a.from], b1 = P.beats[a.to];
  box.append(h(`<h3 class="bx-act"><span>${esc(a.name)}</span><small>beats ${b0.n}${a.to > a.from ? ` to ${b1.n}` : ""}${b0.start != null && b1.start != null ? ` · ${tsf(win(b0)[0])} to ${tsf(win(b1)[1])}` : ""}</small></h3>`));
}

/* ---------- the script: picture · on screen · voice-over, the whole film on one page ----------
   Each beat's words as the film has them (its storyboard copy / vo, else what's in the film, else the board's plan).
   Editing writes the plan (storyboard.json copy / vo); where the plan and the film differ the row says so, and
   "Copy notes prompt" asks the agent to make the film match. */
let vo = null; // a voice line being played on its own
function renderScript(box, opts = {}) {
  const slug = P.slug;
  const edits = scriptEdits().length;
  if (!opts.embedded) {
    $("#bx-tabmeta").textContent = `${P.beats.length} beats · ${P.beats.filter((b) => scriptCopy(b)).length} with words on screen · ${P.beats.filter((b) => (b.spoken || []).length).length} with voice${edits ? ` · ${edits} changed, not in the film yet` : ""}`;
    const cp = h(`<button class="icon-btn sm">${icon("copy")}Copy script</button>`);
    cp.onclick = () => copy(scriptMarkdown(), "Script copied as a table"); $("#bx-tabbtns").append(cp);
  }
  const tbl = h(`<div class="bx-script"><div class="bx-shead"><span>#</span><span>Picture</span><span>On screen</span><span>Voice-over</span></div></div>`);
  P.beats.forEach((b, i) => {
    actHead(tbl, i);
    const [a, e] = b.start == null ? [null, null] : win(b);
    const sp = b.spoken || [];
    const el = h(`<div class="bx-srow st-${b.status}" data-i="${i}">
      <div class="n">${dot(b.status)}${b.n}<small>${a == null ? "" : tcCopy(tsf(a), stampRange(`${P.slug}/${b.id}`, a, e))}</small><small>${a == null ? "" : `${(e - a).toFixed(1)}s`}</small></div>
      <div class="pic"><div class="fr"></div><div class="t">${esc(b.title)}</div></div>
      <div class="col"><textarea data-f="copy" rows="2" placeholder="No words on screen">${esc(scriptCopy(b))}</textarea>
        ${copyChanged(b) ? `<div class="diff" title="The plan says one thing, the film shows another">${icon("circle-help")}In the film: ${esc(b.in_film)}</div>` : !b.copy && !b.in_film && b.board?.copy ? `<div class="from">from the board</div>` : ""}</div>
      <div class="col"><textarea data-f="vo" rows="2" placeholder="No voice-over">${esc(scriptVo(b))}</textarea>
        <div class="lines">${sp.map((x, k) => `<button class="vo-line" data-k="${k}" title="Hear this line (${esc(x.file)})">${icon("play")}<span>${tsf(x.start)}</span>${esc(x.text)}</button>`).join("")}</div>
        ${voChanged(b) ? `<div class="diff">${icon("circle-help")}${sp.length ? "Recorded: " + esc(spokenText(b)) : "Not recorded yet"}</div>` : !b.vo && !sp.length && b.board?.vo ? `<div class="from">from the board, not recorded</div>` : ""}</div>
    </div>`);
    const fr = $(".fr", el);
    if (covered(b)) fr.append(h(`<img loading="lazy" alt="" src="${frameUrl(a + (e - a) * 0.5)}">`));
    else { const s = BY_KEY[b.refs[0]]; if (s) { fr.append(thumb(s, { scrub: false })); fr.classList.add("ref"); } else fr.append(h(`<span>${a == null ? "no time" : "not rendered"}</span>`)); }
    const pins = pinsOf(b);
    if (pins.length) $(".pic", el).append(h(`<div class="pinc" title="${esc(pins.map((x) => `${tsf(x.t)} ${x.note}`).join("\n"))}">${icon("message-square")}${pins.length} note${pins.length > 1 ? "s" : ""}</div>`));
    $(".pic", el).onclick = () => { if (opts.embedded) { location.hash = `#/build/${P.slug}/script`; return; } select(i, { seek: true, play: true }); };
    el.querySelectorAll(".vo-line").forEach((btn) => (btn.onclick = (ev) => { ev.stopPropagation(); hear(sp[+btn.dataset.k], btn); }));
    el.querySelectorAll("textarea").forEach((ta) => {
      let t1; ta.oninput = () => {
        clearTimeout(t1);
        t1 = setTimeout(() => {
          const f = ta.dataset.f, v = ta.value.trim();
          // saving the film's own words unchanged is not an edit: keep the plan empty so the row follows the film
          const same = f === "copy" ? norm(v) === norm(b.in_film || b.board?.copy) : norm(v) === norm(spokenText(b) || b.board?.vo);
          saveScript(b, { [f]: same && !b[f] ? "" : v }, slug);
        }, 700);
      };
    });
    tbl.append(el);
  });
  box.append(tbl);
}
async function saveScript(b, body, slug) {
  try {
    const np = await patchBeat(slug, b.id, body);
    const nb = np.beats.find((x) => x.id === b.id); Object.assign(b, { copy: nb.copy, vo: nb.vo });
    paintNotesBtn();
    const el = document.querySelector(`.bx-srow[data-i="${b.n - 1}"]`);
    if (el) {
      for (const [f, changed, msg] of [["copy", copyChanged(b), `In the film: ${esc(b.in_film || "")}`], ["vo", voChanged(b), (b.spoken || []).length ? "Recorded: " + esc(spokenText(b)) : "Not recorded yet"]]) {
        const col = el.querySelector(`textarea[data-f="${f}"]`).parentElement;
        col.querySelector(".diff")?.remove(); col.querySelector(".from")?.remove();
        if (changed) col.append(h(`<div class="diff">${icon("circle-help")}${msg}</div>`));
      }
    }
    toast(`Saved to storyboard.json: Copy notes prompt asks ${SP.ai} to match the film`);
  } catch (e) { toast(`Couldn't save: ${e.message}`); }
}
function hear(line, btn) {
  if (vo) { vo.pause(); document.querySelectorAll(".vo-line.on").forEach((x) => x.classList.remove("on")); if (vo._line === line) { vo = null; return; } }
  vo = new Audio(fileUrl(line.file)); vo._line = line; vo.volume = monitorGain(); btn.classList.add("on");
  vo.onended = () => { btn.classList.remove("on"); vo = null; };
  vo.play().catch(() => toast(`Can't play ${line.file}`));
}
function scriptMarkdown() {
  const rows = P.beats.map((b) => `| ${b.n} | ${b.start == null ? "" : tsf(win(b)[0])} | ${b.act || ""} | ${b.title} | ${scriptCopy(b).replace(/\n/g, " ")} | ${scriptVo(b).replace(/\n/g, " ")} |`);
  return [`# ${P.title}: the script`, "", "| # | Time | Section | Picture | On screen | Voice-over |", "| --- | --- | --- | --- | --- | --- |", ...rows].join("\n");
}
// the Boards view shows a board that became a film as the film's script
async function scriptFor(box, slug) {
  let p; try { p = await call(`/api/productions/${encodeURIComponent(slug)}`); } catch { return false; }
  const keep = { P, R }; P = p; R = p.renders[0] || null;
  try { renderScript(box, { embedded: true }); } finally { if (keep.P) { P = keep.P; R = keep.R; } }
  return p;
}

/* ---------- assets: every still and clip the film uses ---------- */
async function renderAssets(box) {
  box.append(h(`<div class="empty">Listing the film's stills and clips…</div>`));
  let A; try { A = await call(`/api/productions/${encodeURIComponent(P.slug)}/assets`); } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  if (tab !== "assets") return;
  box.innerHTML = "";
  if (A.note) { box.append(h(`<div class="empty">${esc(A.note)}</div>`)); return; }
  const list = A.assets, used = list.filter((a) => a.uses.length);
  const gen = used.filter((a) => a.kind === "generated");
  const genBeats = new Set(gen.flatMap((a) => a.uses.flatMap((u) => u.beats)));
  $("#bx-tabmeta").textContent = `${list.length} files in ${A.dir}/ · ${used.length} used · ${gen.length} generated in use (${gen.filter((a) => a.type === "video").length} clips, ${gen.filter((a) => a.type === "image").length} stills) across ${genBeats.size} of ${P.beats.length} beats`;
  const gb = h(`<div class="bx-genbeats"><span>Generated footage by beat</span>${P.beats.map((b) => `<i class="${genBeats.has(b.n) ? "on" : ""}" title="${esc(`${b.n}. ${b.title}${genBeats.has(b.n) ? ": uses generated stills or clips" : ""}`)}">${b.n}</i>`).join("")}<small>Prompts, models and credits come from ${esc(A.meta)} when it has them.</small></div>`);
  box.append(gb);
  const groups = {};
  for (const a of list) (groups[a.dir] ||= []).push(a);
  for (const [dir, items] of Object.entries(groups)) {
    const unusedN = items.filter((a) => !a.uses.length).length;
    const sec = h(`<details class="bx-adir" ${unusedN === items.length ? "" : "open"}><summary><b>${esc(dir === "." ? "(top)" : dir)}</b><span>${items.length} file${items.length > 1 ? "s" : ""}${unusedN ? ` · ${unusedN} not used` : ""}</span></summary><div class="bx-agrid"></div></details>`);
    const grid = $(".bx-agrid", sec);
    // a render's frames are one card (a stack: film.py stack_assets); Assets opens it to every frame
    const shown = [], seen = new Set();
    for (const a of items) {
      const st = a.stack && (A.stacks || []).find((s) => s.id === a.stack);
      if (!st) { shown.push(a); continue; }
      if (seen.has(st.id)) continue;
      seen.add(st.id);
      const frames = items.filter((x) => x.stack === st.id), cover = frames[Math.floor(frames.length / 2)];
      const uses = [...new Map(frames.flatMap((x) => x.uses).map((u) => [`${u.file} ${u.where}`, u])).values()];
      shown.push({ ...cover, name: `${st.name} · ${st.count} frames`, path: st.pattern.replace(/^remotion\/public\//, ""), uses, _stack: st });
    }
    for (const a of shown) {
      const src = a.type === "video" ? `/api/frame?file=${encodeURIComponent(a.file)}&t=0.5&w=320&v=${Math.round(a.mtime)}` : fileUrl(a.file);
      const beats = [...new Set(a.uses.flatMap((u) => u.beats))];
      const el = h(`<div class="bx-asset ${a.uses.length ? "" : "unused"} ${a._stack ? "stack" : ""}">
        <div class="th"><img loading="lazy" alt="" src="${src}">${a.type === "video" ? `<span class="vid">${icon("play")}clip</span>` : ""}${a._stack ? `<span class="stk">${icon("layout-list")}${a._stack.count} frames</span>` : ""}<span class="kind k-${esc(a.kind)}">${esc(a.kind)}</span></div>
        <div class="nm tc-copy" data-copy="${esc(a.path)}" title="${a._stack ? "Click to copy the frames' path, with # for the number" : "Click to copy the path staticFile() takes"}">${esc(a.name)}</div>
        ${a._stack ? `<a class="frames-link" href="#/assets?stack=${encodeURIComponent(a._stack.id)}">See every frame</a>` : ""}
        <div class="use">${beats.length ? beats.map((n) => `<button data-n="${n}" title="${esc(P.beats[n - 1]?.title || "")}">beat ${n}</button>`).join("") : ""}${a.uses.map((u) => `<span title="${esc(u.label || "")}">${esc(u.file)}${u.where ? " " + esc(u.where) : ""}</span>`).join("") || `<span class="dim">not used</span>`}</div>
        ${a.prompt || a.model || a.credits != null ? `<div class="meta">${a.model ? `<b>${esc(a.model)}</b> ` : ""}${a.credits != null ? `${esc(a.credits)} credits · ` : ""}${esc(a.prompt || "")}</div>` : ""}
      </div>`);
      if (a.type === "video") {
        const th = $(".th", el);
        th.onmouseenter = () => { if (th.querySelector("video")) return; const v = document.createElement("video"); v.muted = true; v.loop = true; v.playsInline = true; v.src = fileUrl(a.file); th.append(v); v.play().catch(() => {}); };
        th.onmouseleave = () => th.querySelector("video")?.remove();
      }
      el.querySelectorAll("[data-n]").forEach((btn) => (btn.onclick = () => { setTab("beats"); select(+btn.dataset.n - 1, { seek: true, play: true, scroll: true, center: true }); }));
      grid.append(el);
    }
    box.append(sec);
  }
}

/* ---------- notes at a moment: press N on a frame, write, Enter ---------- */
let composer = null;
function closeComposer() { if (composer) { composer.remove(); composer = null; } }
function compose(t = filmT(), pin = null) {
  if (!P) return;
  if (!pin && !R) { toast("Render the film first: notes are pinned to a frame of a render"); return; }
  closeComposer();
  if (vid && !vid.paused) vid.pause();
  const b = P.beats[beatAt(t)];
  const bar = document.querySelector(".bx-bar"); if (!bar) return;
  composer = h(`<div class="bx-compose" role="dialog">
    <div class="hd">${icon("message-square-plus")}<b>${pin ? "Edit note" : "Note"} at ${tsf(t)}</b><span>${b ? `beat ${b.n} · ${esc(b.title)}` : ""}${R ? ` · ${esc(short(pin ? { name: pin.render || R.name } : R))}` : ""}</span></div>
    <textarea rows="3" placeholder="What should change here? (Enter saves, Shift+Enter for a new line, Esc cancels)">${esc(pin?.note || "")}</textarea>
    <div class="ft"><span class="dim">Saved to the film's plan, where ${SP.ai} reads it</span><span class="spacer"></span><button class="icon-btn sm ghost" data-a="x">Cancel</button><button class="icon-btn sm primary" data-a="ok">${icon("check")}Save note</button></div></div>`);
  const host = document.querySelector(".bx-player");
  host.append(composer);
  const pr = host.getBoundingClientRect(), br = bar.getBoundingClientRect(), D = P.duration || 1;
  const x = br.left - pr.left + (t / D) * br.width;
  composer.style.left = `${clamp(x - 180, 8, pr.width - 380)}px`;
  composer.style.top = `${br.top - pr.top - composer.offsetHeight - 10}px`;
  const ta = $("textarea", composer); ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length);
  const save = async () => {
    const note = ta.value.trim();
    if (!note) { closeComposer(); return; }
    try {
      P.pins = pin
        ? await call(`/api/productions/${P.slug}/pins/${pin.id}`, { method: "PATCH", body: JSON.stringify({ note }) })
        : await call(`/api/productions/${P.slug}/pins`, { method: "POST", body: JSON.stringify({ t: +t.toFixed(3), note, render: R?.name, by: "person" }) });
      const np = await call(`/api/productions/${encodeURIComponent(P.slug)}`);
      for (const x of P.beats) { const nb = np.beats.find((y) => y.id === x.id); if (nb) x.status = nb.status; }
      closeComposer(); paintPins(); toast(pin ? "Note saved" : `Note pinned at ${tsf(t)}`);
    } catch (e) { toast(`Couldn't save: ${e.message}`); }
  };
  ta.onkeydown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); save(); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeComposer(); }
    e.stopPropagation();
  };
  $('[data-a="ok"]', composer).onclick = save;
  $('[data-a="x"]', composer).onclick = closeComposer;
}
async function pinAction(x, action) {
  try {
    if (action === "delete") { if (!confirm(`Delete the note "${x.note}"?`)) return; P.pins = await call(`/api/productions/${P.slug}/pins/${x.id}`, { method: "DELETE" }); }
    else if (action === "done") { const d = prompt("What changed? (filed with the note)", "Fixed"); if (d == null) return; P.pins = await call(`/api/productions/${P.slug}/pins/${x.id}`, { method: "PATCH", body: JSON.stringify({ done: d || "done" }) }); }
    else if (action === "reopen") P.pins = await call(`/api/productions/${P.slug}/pins/${x.id}`, { method: "PATCH", body: JSON.stringify({ status: "open" }) });
    paintPins();
  } catch (e) { toast(`Couldn't save: ${e.message}`); }
}
function goPin(x) {
  const i = P.beats.findIndex((b) => b.id === x.beat);
  if (i >= 0 && i !== sel) select(i, { seek: false, scroll: false });
  if (vid) { vid.pause(); seekFilm(x.t); }
  document.querySelectorAll(".bx-note").forEach((el) => el.classList.toggle("sel", el.dataset.id === x.id));
}
/* a sound note in the Notes tab: the same row as a frame note, with its kind (sfx, music, voice, mix) up front */
const SOUND_KIND = { sfx: "SFX", music: "Music", voice: "Voice", mix: "Mix" };
const doneSoundNotes = () => Object.entries(P.sound_notes || {}).filter(([, v]) => !v.note && v.log && v.log.length);
function soundNoteItem(id, v, isDone = false) {
  const last = isDone ? v.log[v.log.length - 1] : null, text = isDone ? last.note : v.note, t = v.start ?? 0;
  const b = P.beats[beatAt(t)], kind = v.kind || "mix";
  const el = h(`<div class="bx-note snd ${isDone ? "done" : ""}" data-id="${esc(id)}">
    <button class="tm" title="Go to this moment">${icon("play")}${tsf(t)}</button>
    <div class="txt"><div class="lbl"><span class="kind k-${esc(kind)}" title="A note on the sound">${esc(SOUND_KIND[kind] || kind)}</span> ${esc(v.label || id)}${v.end != null ? ` · ${tsf(t)} to ${tsf(v.end)}` : ""}${b ? ` · beat ${b.n} · ${esc(b.title)}` : ""}${v.at ? ` · <span class="at" title="${esc(`Added ${whenAt(v.at, true)}`)}">added ${esc(whenAt(v.at))}</span>` : ""} ${tcCopy(icon("copy"), `${P.slug} ${kind} ${v.label ? v.label + ", " : ""}${tsf(t)}${v.end != null ? ` to ${tsf(v.end)}` : ""}: ${text}`, "Copy the note with its time")}</div>
      <div class="body">${esc(text || "")}</div>${isDone ? `<div class="dn">${icon("check")}Done${last.at ? ` ${esc(whenAt(last.at))}` : ""}: ${esc(last.done || "")}</div>` : ""}</div>
    <div class="acts">${isDone ? "" : `<button class="icon-btn sm sq ghost" data-a="sound" title="Open it in the Sound panel">${icon("audio-lines")}</button><button class="icon-btn sm sq ghost" data-a="done" title="Mark it done">${icon("check")}</button><button class="icon-btn sm sq ghost" data-a="delete" title="Delete">${icon("trash-2")}</button>`}</div></div>`);
  $(".tm", el).onclick = () => { const i = beatAt(t); if (i >= 0 && i !== sel) select(i, { seek: false, scroll: false }); if (vid) { vid.pause(); seekFilm(t); } document.querySelectorAll(".bx-note").forEach((n) => n.classList.toggle("sel", n === el)); };
  $('[data-a="sound"]', el)?.addEventListener("click", () => setTab("sound"));
  $('[data-a="done"]', el)?.addEventListener("click", () => soundNoteAction(id, "done"));
  $('[data-a="delete"]', el)?.addEventListener("click", () => soundNoteAction(id, "delete", v.note));
  return { sound: true, id, t, el };
}
async function soundNoteAction(id, action, note) {
  let body;
  if (action === "done") { const d = prompt("What changed? (filed with the note)", "Fixed"); if (d == null) return; body = { done: d || "done" }; }
  else { if (!confirm(`Delete the note "${note}"?`)) return; body = { note: "" }; }
  try { P.sound_notes = await call(`/api/productions/${P.slug}/sound/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(body) }); paintPins(); }
  catch (e) { toast(`Couldn't save: ${e.message}`); }
}
/* markers on the beat bar, the list of notes under the player, and each beat's own notes */
function paintPins() {
  if (!P) return;
  const D = P.duration || 1, all = P.pins || [], open = openPins();
  const lay = document.getElementById("bx-pins");
  if (lay) {
    lay.innerHTML = "";
    const hide = donePinsHidden(), nd = all.length - open.length, tg = document.getElementById("bx-donepins");
    if (tg) {
      tg.hidden = !nd; tg.setAttribute("aria-pressed", String(!hide));
      tg.innerHTML = `${icon(hide ? "eye-off" : "eye")}${hide ? "Show" : "Hide"} ${nd} done note${nd === 1 ? "" : "s"}`;
      tg.title = hide ? "Done notes are hidden on the beat bar: show them again" : "Take the done notes off the beat bar; they stay in the Notes tab";
    }
    for (const x of hide ? open : all) {
      const m = h(`<button class="bx-pin ${x.status === "done" ? "done" : ""}" style="left:${(x.t / D) * 100}%" title="${esc(`${tsf(x.t)} · ${x.note}${x.at ? ` · added ${whenAt(x.at)}` : ""}${x.status === "done" ? ` (done${x.done_at ? ` ${whenAt(x.done_at)}` : ""} in ${x.done_in || "?"}: ${x.done})` : ""}`)}"></button>`);
      m.onpointerdown = (e) => e.stopPropagation();
      m.onclick = (e) => { e.stopPropagation(); goPin(x); document.querySelector(`.bx-note[data-id="${x.id}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }); };
      lay.append(m);
    }
  }
  const box = document.getElementById("bx-notes");
  if (box) {
    box.innerHTML = "";
    const done = all.filter((x) => x.status === "done");
    // sound notes (on an effect, the music, the voice, the mix) are listed here too, by time, marked with their kind
    const sOpen = openSoundNotes().map(([id, v]) => soundNoteItem(id, v)), sDone = doneSoundNotes().map(([id, v]) => soundNoteItem(id, v, true));
    const nOpen = open.length + sOpen.length, nDone = done.length + sDone.length;
    if (tab === "notes") $("#bx-tabmeta").textContent = nOpen ? `${nOpen} open${nDone ? ` · ${nDone} done` : ""}` : "";
    // the other open notes (on beats, script changes) live in their tabs: point there
    const other = [[P.beats.filter((b) => b.review).length, "beat note", "beats"], [scriptEdits().length, "script change", "script"]].filter(([n]) => n);
    if (!nOpen) box.append(h(`<div class="bx-nempty">${icon("message-square-plus")}<b>${nDone ? "Every note is done" : "No notes yet"}</b><span>Pause on a frame and press <kbd>N</kbd> to pin a note to it. Feedback you give ${SP.ai} in the chat lands here too.</span></div>`));
    if (other.length) {
      const ln = h(`<div class="bx-nother">Also open: ${other.map(([n, l, t]) => `<button data-t="${t}">${n} ${l}${n > 1 ? "s" : ""}</button>`).join(", ")}</div>`);
      ln.querySelectorAll("button").forEach((b) => (b.onclick = () => setTab(b.dataset.t)));
      box.append(ln);
    }
    const item = (x) => {
      const b = P.beats.find((y) => y.id === x.beat);
      const el = h(`<div class="bx-note ${x.status === "done" ? "done" : x.replies?.length ? "wip" : ""}" data-id="${esc(x.id)}">
        <button class="tm" title="Go to this frame">${icon("play")}${tsf(x.t)}</button>
        <div class="txt"><div class="lbl">${b ? `beat ${b.n} · ${esc(b.title)}` : "?"}${x.render ? ` · seen in ${esc(x.render.replace(/\.(mp4|mov|webm|m4v)$/i, ""))}` : ""}${x.by && x.by !== "person" ? ` · ${esc(BY[x.by] || x.by)}` : ""}${x.at ? ` · <span class="at" title="${esc(`Added ${whenAt(x.at, true)}`)}">added ${esc(whenAt(x.at))}</span>` : ""} ${tcCopy(icon("copy"), `${P.slug}/${x.beat || ""} @ ${tsf(x.t)}${x.render ? ` in ${x.render}` : ""}: ${x.note}`, "Copy the note with its time")}</div>
          <div class="body">${esc(x.note)}</div>${(x.replies || []).map((r) => `<div class="rp">${icon("message-square")}<b>${esc(BY[r.by] || r.by)}</b> ${esc(r.text)}<span title="${esc(whenAt(r.at, true))}">${esc(whenAt(r.at))}</span></div>`).join("")}${x.status === "done" ? `<div class="dn"${x.done_at ? ` title="${esc(`Done ${whenAt(x.done_at, true)}`)}"` : ""}>${icon("check")}Done${x.done_at ? ` ${esc(whenAt(x.done_at))}` : ""}${x.done_in ? ` in ${esc(x.done_in.replace(/\.(mp4|mov|webm|m4v)$/i, ""))}` : ""}: ${esc(x.done || "")}</div>` : ""}</div>
        <div class="acts">${x.status === "done" ? `<button class="icon-btn sm ghost" data-a="reopen" title="Open it again">${icon("rotate-cw")}</button>` : `<button class="icon-btn sm sq ghost" data-a="edit" title="Edit">${icon("pencil")}</button><button class="icon-btn sm sq ghost" data-a="done" title="Mark it done">${icon("check")}</button>`}<button class="icon-btn sm sq ghost" data-a="delete" title="Delete">${icon("trash-2")}</button></div></div>`);
      $(".tm", el).onclick = () => goPin(x);
      $('[data-a="edit"]', el)?.addEventListener("click", () => { goPin(x); compose(x.t, x); });
      for (const a of ["done", "reopen", "delete"]) $(`[data-a="${a}"]`, el)?.addEventListener("click", () => pinAction(x, a));
      return el;
    };
    const any = (x) => (x.sound ? x.el : item(x));
    const byT = (a, b) => (a.t ?? 0) - (b.t ?? 0);
    if (nOpen) { const l = h(`<div class="bx-nlist"></div>`); [...open, ...sOpen].sort(byT).forEach((x) => l.append(any(x))); box.append(l); }
    if (nDone) { const d = h(`<details class="bx-ndone"><summary>${nDone} done</summary><div class="bx-nlist"></div></details>`); [...done, ...sDone].sort(byT).reverse().forEach((x) => $(".bx-nlist", d).append(any(x))); box.append(d); }
  }
  // the beat rows' own notes and the toolbar's note dots
  document.querySelectorAll(".bx-row").forEach((el) => {
    const b = P.beats[+el.dataset.i]; if (!b) return;
    const ps = pinsOf(b), box2 = $(".bx-bpins", el); if (!box2) return;
    box2.innerHTML = ps.map((x) => `<button data-id="${esc(x.id)}" title="Go to ${tsf(x.t)}">${icon("message-square")}<span>${tsf(x.t)}</span>${esc(x.note)}</button>`).join("");
    box2.querySelectorAll("button").forEach((btn) => (btn.onclick = (e) => { e.stopPropagation(); goPin(ps.find((x) => x.id === btn.dataset.id)); }));
    el.className = el.className.replace(/st-\w+/, `st-${b.status}`);
  });
  document.querySelectorAll(".bx-tb-card").forEach((c) => { const b = P.beats[+c.dataset.i]; if (b) c.classList.toggle("pinned", pinsOf(b).length > 0); });
  paintNotesBtn();
}

/* ---------- compare: a second render in the right pane, in step with the first ---------- */
function pickCompare(anchor) {
  const others = P.renders.filter((r) => r !== R);
  if (!others.length) { toast("There's only one render"); return; }
  openMenu(anchor, [{ value: "", on: !C, html: `<span class="lbl">Off: show the reference</span>` }, ...others.slice(0, 40).map((r) => ({ value: r.file, on: C === r, html: `<span class="lbl"><b>${esc(short(r))}</b> ${esc(ago(r.mtime))}${r.note ? ` · ${esc(r.note.slice(0, 60))}` : ""}</span>` }))], (v) => setCompare(v ? P.renders.find((r) => r.file === v) : null));
}
function setCompare(r) {
  C = r && r !== R ? r : null; remember();
  const b = document.querySelector('.bx-tr [data-a="cmp"]');
  if (b) { b.innerHTML = icon("git-compare") + (C ? `vs ${esc(short(C))}` : "Compare"); b.classList.toggle("on", !!C); b.classList.toggle("ghost", !C); }
  if (C) { document.querySelector(".bx-player")?.classList.add("with-ref"); toggleRefPane(true); }   // the compared render plays in that pane
  paneFor(P.beats[sel], null, true);
}
function swapCompare() {
  if (!C) { toast("Pick a render to compare with first (X)"); return; }
  const a = R; R = C; C = a; remember();
  const t = filmT(); draw($("#main")); if (vid) { const go = () => seekFilm(t); vid.readyState >= 1 ? go() : vid.addEventListener("loadedmetadata", go, { once: true }); }
  toast(`Now playing ${short(R)}, compared with ${short(C)}`);
}
// a film time in the render on screen -> the same moment in the compared render: the same point of the same beat
function cmpTime(t) {
  const b = P.beats[beatAt(t)];
  const w1 = b && R?.beats?.[b.id], w2 = b && C?.beats?.[b.id];
  if (w1 && w2 && w1[1] > w1[0]) return w2[0] + ((t - w1[0]) / (w1[1] - w1[0])) * (w2[1] - w2[0]);
  return t;
}
function driveCompare(t) {
  if (!cvid || !C || cvid.readyState < 1) return;
  const playing = vid && !vid.paused, want = cmpTime(t) - (C.offset || 0);
  cvid.playbackRate = speed;
  if (Math.abs(cvid.currentTime - want) > (playing ? 0.12 : 0.02)) try { cvid.currentTime = Math.max(0, want); } catch {}
  if (playing && cvid.paused) cvid.play().catch(() => {}); else if (!playing && !cvid.paused) cvid.pause();
}
/* ---------- a beat's history: the same moment in every render that has it ---------- */
function beatHistory(b, box) {
  const vs = P.renders.filter((r) => { const w = r.beats?.[b.id], sp = r.span || [0, Infinity]; return w && w[0] >= sp[0] - 0.01 && w[1] <= sp[1] + 0.01; }).slice(0, 18);
  box.innerHTML = "";
  if (!vs.length) { box.append(h(`<div class="dim">No render has this beat yet.</div>`)); return; }
  const grid = h(`<div class="bx-hist-grid"></div>`);
  for (const r of vs) {
    const [a, e] = r.beats[b.id], t = a + (e - a) * 0.5;
    const log = (b.log || []).filter((l) => l.render === r.name);
    const el = h(`<button class="bx-hv ${r === R ? "cur" : ""} ${r === C ? "cmp" : ""}" title="${esc(`${r.name}${r.note ? `: ${r.note}` : ""}${log.length ? `\nFixed: ${log.map((l) => l.done).join("; ")}` : ""}\nClick to compare with ${R ? short(R) : "it"}`)}">
      <img loading="lazy" alt="" src="/api/frame?file=${encodeURIComponent(r.file)}&t=${(t - (r.offset || 0)).toFixed(3)}&w=240&v=${Math.round(r.mtime)}">
      <span class="v"><b>${esc(short(r))}</b>${r === R ? " · on screen" : ""}</span><span class="nt">${esc(r.note || "")}</span></button>`);
    el.onclick = (ev) => { ev.stopPropagation(); if (r === R) return; setCompare(r); select(P.beats.indexOf(b), { seek: true, play: false }); document.querySelector(".bx-stage")?.scrollIntoView({ behavior: "smooth", block: "start" }); };
    grid.append(el);
  }
  box.append(grid);
}

/* ---------- prompts for the agent ---------- */
const where = (b) => P.engine === "remotion"
  ? `${P.dir}/ (beat \`${b.id}\` in storyboard.json; its times are cues.json scenes.${Array.isArray(b.cue) ? b.cue.join(" + ") : b.cue})`
  : `${P.dir}/ (Frame ${b.n} in STORYBOARD.md, ${b.src})`;
const refLines = (b) => b.refs.map((k) => { const s = BY_KEY[k]; return s ? `- \`${k}\` ${s.title} (library/references/${s.film}/breakdown.md#${s.id})` : `- \`${k}\` (not in the library)`; });
function loopLine(b, fixing) {
  const mark = `${SP.cmd("film")} mark ${P.slug} ${b.id} review${fixing ? ' --done "<what you changed>"' : ""}`;
  return P.engine === "remotion"
    ? `Work loop: \`${SP.cmd("film")} mark ${P.slug} ${b.id} wip\`, build it, \`${SP.cmd("film")} render ${P.slug} --beat ${b.id}\`, then \`${SP.cmd("film")} sheet ${P.slug} --beat ${b.id}\` and look at the sheet (storyboard, reference and render side by side). When the beat matches its plan: \`${mark}\`.`
    : `Render as the project's AGENTS.md says, check it with \`${SP.cmd("film")} sheet ${P.slug} --beat ${b.id}\` (storyboard and render side by side), then \`${mark}\`.`;
}
/* The profile the film is made in (storyboard.json "style"), as its prompts say it: read it first, and keep what lasts. */
function styleLine() {
  if (!P.style) return "";
  if (P.style === "none") return "Made in no profile: each beat recreates its reference as it is (the make-film skill's \"A study of one film\").";
  return `Made in the profile ${window.Profiles?.get(P.style)?.name || P.style}: read \`${SP.cmd("profile", "show", P.style)}\` first. If a note states a lasting preference rather than a fix for one frame, offer to keep it: \`${SP.cmd("profile", "learn", P.style, `"<the rule>"`)} --from "${P.slug} note <id>"\`.`;
}
function beatPrompt(b) {
  const prev = P.beats[b.n - 2], next = P.beats[b.n];
  const when = b.start == null ? "" : `, film time ${tsf(b.start)} to ${tsf(b.end)}`;
  return [
    b.review || pinsOf(b).length
      ? `/make-film Notes on beat ${b.n} of ${P.beats.length}, "${b.title}", in ${where(b)}${when}${R ? `, seen in ${R.name}` : ""}:\n\n${b.review || "(the notes pinned to its frames, below)"}`
      : `/make-film Build beat ${b.n} of ${P.beats.length}, "${b.title}", in ${where(b)}${when}.`,
    styleLine(),
    `Read the whole plan first (${P.storyboard}) so this beat picks up from ${prev ? `beat ${prev.n} "${prev.title}"` : "the opening frame"} and hands off into ${next ? `beat ${next.n} "${next.title}"` : "the end"}. Leave the other beats as they are.`,
    b.on_screen && `On screen: ${b.on_screen}`,
    b.copy && `Copy: ${b.copy}`,
    b.roles?.length && `Motion roles: ${b.roles.join(", ")}`,
    b.sound && `Sound: ${b.sound}`,
    b.refs.length && `References (read each one's breakdown section before building):\n${refLines(b).join("\n")}`,
    pinsOf(b).length && `Notes pinned to frames of this beat:\n${pinsOf(b).map(pinLine).join("\n")}\nWhen a render fixes a note, close it in the same step: \`${SP.cmd("film")} render ${P.slug} --beat <id> --fixes <note ids> --note "<what you changed>"\`, or afterwards \`${SP.cmd("film")} done ${P.slug} <ids> --done "<what you changed>"\`. If a note is only partly done (say the copy changed but the voice is pending), leave it open and reply with what's left: \`${SP.cmd("film")} note-reply ${P.slug} <id> "..."\`. Never leave a fixed note open.`,
    scriptLines([b]).length && `Script changes:\n${scriptLines([b]).join("\n")}`,
    b.log?.length && `Earlier notes on this beat:\n${b.log.map((l) => `- ${l.at}${l.render ? ` (${l.render})` : ""}: "${l.note}" -> ${l.done}`).join("\n")}`,
    loopLine(b, !!b.review),
  ].filter(Boolean).join("\n\n");
}
function soundLines(list) {
  return list.map(([id, v]) => `- [${id}] ${v.kind}${v.label ? ` ${v.label}` : ""} (${tsf(v.start)} to ${tsf(v.end)}${v.ref ? `, ${v.ref}` : ""}): ${v.note}`);
}
const soundHow = () => `Sound: \`spliced sound show ${P.slug}\` prints the beat grid, the music sections, the bed plan's joins and every effect with its bar, beat and offset${P.engine === "hyperframes" ? " (effects are the <audio> elements in index.html; the bed is cut by build_bed.py from its plan-*.json)" : ""}. If the project has its own sound rules (remotion/docs/SOUND.md), read them first. When a note is fixed: \`${SP.cmd("film")} sound-done ${P.slug} <id> --done "<what you changed>"\`.`;
function soundPrompt(list) {
  return [`/make-film Sound notes on "${P.title}" (${P.dir}/)${R ? `, from ${R.name}` : ""}. Leave everything else as it is.`, "", ...soundLines(list), "", soundHow()].join("\n");
}
const pinLine = (x) => { const b = P.beats.find((y) => y.id === x.beat); return `- [${x.id}] ${tsf(x.t)}${b ? `, beat ${b.n} \`${b.id}\`` : ""}${x.render ? `, seen in ${x.render}` : ""}: ${x.note}`; };
const scriptLines = (list) => list.flatMap((b) => [
  copyChanged(b) && `- beat ${b.n} \`${b.id}\` on screen: "${b.copy}" (the film shows "${b.in_film}")`,
  voChanged(b) && `- beat ${b.n} \`${b.id}\` voice-over: "${b.vo}" (${(b.spoken || []).length ? `recorded: "${spokenText(b)}"` : "not recorded yet"})`,
].filter(Boolean));
function notesPrompt() {
  const open = P.beats.filter((b) => b.review), so = openSoundNotes(), pins = openPins(), se = scriptEdits();
  return [
    `/make-film Notes on "${P.title}" (${P.dir}/)${R ? `, from ${R.name}` : ""}: ${[pins.length ? `${pins.length} note${pins.length === 1 ? "" : "s"} at a moment` : "", open.length ? `${open.length} beat note${open.length === 1 ? "" : "s"}` : "", se.length ? `${se.length} script change${se.length > 1 ? "s" : ""}` : "", so.length ? `${so.length} sound note${so.length > 1 ? "s" : ""}` : ""].filter(Boolean).join(", ")} to work through. Leave the rest as it is.`, "",
    ...(pins.length ? ["Notes pinned to a frame (film time in the render named):", ...pins.map(pinLine), `When a render fixes a note, close it in the same step: \`${SP.cmd("film")} render ${P.slug} --beat <id> --fixes <note ids> --note "<what you changed>"\`, or afterwards \`${SP.cmd("film")} done ${P.slug} <ids> --done "<what you changed>"\`. If a note is only partly done (say the copy changed but the voice is pending), leave it open and reply with what's left: \`${SP.cmd("film")} note-reply ${P.slug} <id> "..."\`. Never leave a fixed note open.`, ""] : []),
    ...(se.length ? ["Script changes (storyboard.json copy / vo; the film doesn't match yet; new voice lines need recording in the film's voice):", ...scriptLines(se), ""] : []),
    ...open.map((b) => `${b.n}. \`${b.id}\` "${b.title}"${b.start == null ? "" : ` (${tsf(b.start)} to ${tsf(b.end)})`}: ${b.review}`),
    ...(so.length ? [...(open.length ? [""] : []), "Sound:", ...soundLines(so), "", soundHow()] : []), "",
    `The plan is ${P.storyboard}; \`${SP.cmd("film")} status ${P.slug}\` prints it beat by beat with the open notes.`,
    ...(styleLine() ? [styleLine()] : []),
    P.engine === "remotion"
      ? `For each beat: fix it, \`${SP.cmd("film")} render ${P.slug} --beat <id>\`, check \`${SP.cmd("film")} sheet ${P.slug} --beat <id>\`, then \`${SP.cmd("film")} mark ${P.slug} <id> review --done "<what you changed>"\`. Finish with a full render: \`${SP.cmd("film")} render ${P.slug}\`.`
      : `For each beat: fix it, re-render the film as the project's AGENTS.md says, check \`${SP.cmd("film")} sheet ${P.slug}\`, then \`${SP.cmd("film")} mark ${P.slug} <id> review --done "<what you changed>"\`.`,
  ].join("\n");
}

/* ---------- keys (only while a film is open) ---------- */
/* ---------- full screen: the player block fills the screen, the beat bar stays along the bottom ---------- */
function toggleFull() {
  const pl = document.querySelector(".bx-player"); if (!pl) return;
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  else (pl.requestFullscreen ? pl.requestFullscreen() : Promise.reject()).catch(() => toast("Full screen isn't available in this browser"));
}
function paintFull() {
  const on = !!document.fullscreenElement, pl = document.querySelector(".bx-player");
  const b = document.querySelector('.bx-tr [data-a="fs"]');
  if (b) { b.innerHTML = icon(on ? "minimize" : "maximize"); b.title = on ? "Exit full screen (F or Esc)" : "Full screen (F)"; }
  const r = document.querySelector('.bx-tr [data-a="fsref"]');
  if (r && pl) { const w = pl.classList.contains("with-ref"); r.classList.toggle("on", w); r.classList.toggle("ghost", !w); }
}
document.addEventListener("fullscreenchange", () => {
  // the toast (copied timecodes etc.) has to live inside the full screen element to be seen
  const t = document.getElementById("toast"); if (t) (document.fullscreenElement || document.body).append(t);
  paintFull();
  if (!document.fullscreenElement) centerCard(sel);
});

function onKey(e) {
  if (!P || !document.querySelector(".bx-stage")) return false;
  if (composer) return false;
  const K = window.KB;
  if (K.is(e, "bPlay")) { e.preventDefault(); togglePlay(); }
  else if (K.is(e, "bFrameBack") || K.is(e, "bFrameFwd")) step(K.is(e, "bFrameBack") ? -1 : 1);
  else if (K.is(e, "beatNext") || K.is(e, "beatPrev")) { e.preventDefault(); select(clamp(sel + (K.is(e, "beatPrev") ? -1 : 1), 0, P.beats.length - 1), { seek: true, play: vid && !vid.paused, scroll: true, center: true }); }
  else if (K.is(e, "full")) toggleFull();
  else if (K.is(e, "loop")) { setMode(mode === "loop" ? "play" : "loop"); paintTrState(); toast(mode === "loop" ? "Looping the beat" : "Playing the film through"); }
  else if (K.is(e, "sync")) toggleSync();
  else if (K.is(e, "reload")) renderFilm($("#main"), P.slug);
  else if (K.is(e, "bTime")) $("#bx-tc")?.click();
  else if (K.is(e, "sound")) setSound(!soundOn);
  else if (K.is(e, "note")) { e.preventDefault(); compose(); }
  else if (K.is(e, "compare")) $('.bx-tr [data-a="cmp"]')?.click();
  else if (K.is(e, "swap")) swapCompare();
  else if (K.is(e, "refPane")) toggleRefPane();
  else if (K.is(e, "tlIn")) zoomTl(2);
  else if (K.is(e, "tlOut")) zoomTl(0.5);
  else if (K.is(e, "tlFit")) setTl(1, 0, true);
  else if (K.is(e, "bSeekBack") || K.is(e, "bSeekFwd")) { e.preventDefault(); if (vid) { vid.pause(); seekFilm(filmT() + (K.is(e, "bSeekBack") ? -1 : 1) * (e.shiftKey ? 0.1 : 1)); } }
  else return false;
  return true;
}

return { renderList, renderFilm, stop, onKey, scriptFor };
};
