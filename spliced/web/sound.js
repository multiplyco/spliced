/* Sound panel for the Build view: the film's sound taken apart into lanes (music, voice, sound effects) on the music's
   beat grid, under the same time axis as the beat bar. Data: /api/sound/<slug> (sound.py). Plays the stems
   with Web Audio in sync with the render, with mute and solo per lane, so one sound can be heard on its own.
   Drag on a lane to select a range (snaps to beats, Alt for free), click a section, a join or an effect to select it,
   then loop it, copy it or leave a note for the agent (saved with the film's beat notes). */
window.SoundPanel = (api) => {
"use strict";
const { h, esc, $, tsf, toast, copy, fileUrl, scrubber, tcCopy } = api;
const icon = window.icon;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const maps = {};              // slug -> sound map (cached for the session)

/* ---------- Web Audio engine ---------- */
let ctx = null, master = null;
let level = 1;                // the monitor level (the Build transport's volume knob), as a gain
const buffers = new Map();    // file -> Promise<AudioBuffer>
function audio() {
  if (!ctx) { ctx = new (window.AudioContext || window.webkitAudioContext)(); master = ctx.createGain(); master.connect(ctx.destination); }
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  return ctx;
}
let soundVersion = "";        // the sound map's fingerprint: changes whenever any track's file changes, so a file
                              // re-rendered under the same name is fetched fresh instead of from the browser's cache
function buffer(file) {
  const key = `${file}?${soundVersion}`;
  if (!buffers.has(key)) buffers.set(key, fetch(`${fileUrl(file)}?v=${soundVersion}`).then((r) => { if (!r.ok) throw new Error(file); return r.arrayBuffer(); }).then((b) => audio().decodeAudioData(b)).catch(() => null));
  return buffers.get(key);
}

function mount(container, player, slug) {
  let S = null, on = false, mode = "render", sel = null, playing = [], laneGain = {}, muted = new Set(), solo = new Set(), sched = null, dead = false;
  let T = null, aud = null, audLoop = false; const openTk = new Set();   // takes (takes.json) and the take being auditioned: {track, take}
  const el = h(`<section class="snd"><div class="snd-head"><h2>Sound</h2><span class="meta" id="snd-meta">Taking the sound apart…</span><span class="spacer"></span></div><div class="snd-aud" id="snd-aud" hidden></div><div class="snd-body"><div class="snd-loading">${icon("loader")} Reading the tracks and finding the beat…</div></div><div class="snd-takes" id="snd-takes"></div></section>`);
  container.append(el);

  const load = async (q = "") => {
    try {
      const r = await fetch(`/api/sound/${encodeURIComponent(slug)}${q}`);
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || r.statusText);
      const was = maps[slug];
      maps[slug] = j; soundVersion = j.fingerprint || "";
      if (!q && was && was.fingerprint === j.fingerprint) return;   // nothing changed since the copy we drew from
      if (was) buffers.clear();                               // a clip may have been replaced under the same name
      if (!dead) { S = j; draw(); }
    } catch (e) { if (!dead) $(".snd-body", el).innerHTML = `<div class="empty">Couldn't analyse the sound: ${esc(e.message)}</div>`; }
  };
  // Draw the last copy at once, but always ask again: sound.json changes between renders (new voice lines, retimed effects).
  if (maps[slug]) { S = maps[slug]; soundVersion = S.fingerprint || ""; queueMicrotask(draw); }
  load();

  /* ----- time <-> x, over the visible window: the timeline's own window (Film: the whole film until the timeline is
     zoomed in, which the beat bar shares), or (Beat zoom) the selected beat or loop ±0.5s ----- */
  let lanesEl = null, ro = null;
  let zoom = localStorage.getItem("cr.sndZoom") === "beat" ? "beat" : "film", V = [0, 1];
  const D = () => (S && S.duration) || player.duration();
  const view = () => {
    if (zoom !== "beat") { const w = player.zoomed && player.zoomed() ? player.window() : null; return w ? [w[0], Math.min(w[1], D())] : [0, D()]; }
    const r = player.loop() || (player.view && player.view());
    return r && r[1] > r[0] ? [Math.max(0, r[0] - 0.5), Math.min(D(), r[1] + 0.5)] : [0, D()];
  };
  const span = () => Math.max(0.001, V[1] - V[0]);
  const xOf = (t) => ((t - V[0]) / span()) * 100;
  const wOf = (d) => (d / span()) * 100;
  const vis = (a, e) => e >= V[0] && a <= V[1];
  const detail = () => zoom === "beat" || span() <= 24;   // close enough to name each effect
  const tAt = (x) => { const r = lanesEl.getBoundingClientRect(); return V[0] + clamp((x - r.left) / r.width, 0, 1) * span(); };
  const beats = () => (S.tempo && S.tempo.beats) || [];
  const snap = (t) => { const b = beats(); if (!b.length) return t; let best = b[0]; for (const x of b) if (Math.abs(x - t) < Math.abs(best - t)) best = x; return best; };
  const gridAt = (t) => {
    const g = S.tempo; if (!g) return null;
    const b = g.beats; let i = 0; for (let j = 0; j < b.length; j++) if (Math.abs(b[j] - t) < Math.abs(b[i] - t)) i = j;
    let bar = 0; for (const x of g.bars) if (x <= b[i] + 1e-3) bar++;
    return { bar, beat: ((i - g.phase) % 4 + 4) % 4 + 1, offset: t - b[i] };
  };
  const barsLabel = (a, e) => { const g1 = gridAt(a), g2 = gridAt(Math.max(a, e - 0.02)); return g1 && g2 ? (g1.bar === g2.bar ? `bar ${g1.bar}` : `bars ${g1.bar}-${g2.bar}`) : ""; };
  const placeLabel = (t) => { const g = gridAt(t); if (!g) return ""; const ms = Math.round(g.offset * 1000); return `bar ${g.bar} beat ${g.beat}${Math.abs(ms) > 8 ? ` ${ms > 0 ? "+" : ""}${ms}ms` : ""}`; };

  /* ----- draw ----- */
  function draw() {
    if (!S) return;
    // the first time: what this panel is, above its lanes (web/explain.js)
    if (!$(".explain", el)) { const ex = window.Explain?.inline("sound", "build-film"); if (ex) $(".snd-head", el).after(ex); }
    V = view();
    const g = S.tempo;
    const playable = S.lanes.some((l) => l.clips && l.clips.length);
    mode = playable ? mode : "render";
    $("#snd-meta", el).textContent = [S.source, g ? `${g.bpm} bpm · ${g.bars.length} bars` : "no steady beat", S.separated ? "voice and music separated with Demucs" : ""].filter(Boolean).join(" · ");
    const head = $(".snd-head", el);
    head.querySelectorAll(".snd-ctl").forEach((x) => x.remove());
    const ctl = h(`<div class="snd-ctl">
      <div class="seg" id="snd-zoom" title="Film: the same stretch as the timeline above (pinch or ⌘-scroll on the lanes to zoom, scroll sideways to move along). Beat: the selected beat, or the looped range"><button data-z="film">Film</button><button data-z="beat">Beat</button></div>
      ${playable ? `<div class="seg" id="snd-mode" title="What you hear"><button data-v="stems">Stems</button><button data-v="render">Render</button></div>` : ""}
      <button class="icon-btn sm sq ghost" data-a="smore" title="Analyse again${S.can_separate && !S.separated ? ", separate voice and music" : ""}">${icon("ellipsis")}</button></div>`);
    head.append(ctl);
    ctl.querySelectorAll("#snd-mode button").forEach((b) => (b.onclick = () => { setMode(b.dataset.v); }));
    ctl.querySelectorAll("#snd-zoom button").forEach((b) => {
      b.classList.toggle("on", b.dataset.z === zoom);
      b.onclick = () => { zoom = b.dataset.z; localStorage.setItem("cr.sndZoom", zoom); draw(); };
    });
    paintMode();
    const separate = () => { $("#snd-meta", el).textContent = "Separating voice and music with Demucs (about a minute the first time)…"; load("?separate=1"); };
    const redo = () => { $("#snd-meta", el).textContent = "Analysing…"; load(`?force=1${S.separated ? "&separate=1" : ""}`); };
    $('[data-a="smore"]', ctl).onclick = (e) => {
      const items = [{ value: "redo", html: `${icon("rotate-cw")}<span class="lbl">Analyse the sound again</span>` },
        ...(S.can_separate && !S.separated ? [{ value: "sep", html: `${icon("sparkles")}<span class="lbl">Separate voice and music (Demucs, about a minute)</span>` }] : [])];
      const pick = (v) => (v === "sep" ? separate() : redo());
      if (player.menu) player.menu(e.currentTarget, items, pick); else redo();
    };

    const body = $(".snd-body", el); body.innerHTML = "";
    for (const n of S.notes || []) body.append(h(`<div class="bx-warn">${icon("circle-help")}<div>${esc(n)}</div></div>`));
    if (!S.lanes.length) { lanesEl = null; return; }
    lanesEl = h(`<div class="snd-lanes"><div class="snd-grid"></div><div class="snd-sel"></div><div class="snd-ph"></div></div>`);
    // ruler: bars, beats, picture cuts
    const ruler = h(`<div class="snd-ruler" title="Drag to scrub"><div class="snd-time tl-ticks"></div></div>`);
    if (g) {
      g.bars.forEach((t, i) => { if (t <= D() && vis(t, t)) ruler.append(h(`<span class="bar" style="left:${xOf(t)}%">${i + 1}</span>`)); });
    }
    for (const c of player.cuts()) {
      if (!vis(c.t, c.t)) continue;
      const p = g ? gridAt(c.t) : null, ms = p ? Math.round(p.offset * 1000) : null;
      const on = p && Math.abs(ms) <= 35;
      const m = h(`<i class="cut ${on ? "on" : "off"}" style="left:${xOf(c.t)}%" title="${esc(`Cut into beat ${c.n} "${c.title}" at ${tsf(c.t)}${p ? `: ${on ? "on" : ms > 0 ? `${ms}ms after` : `${-ms}ms before`} bar ${p.bar} beat ${p.beat}` : ""}`)}"></i>`);
      ruler.append(m);
    }
    lanesEl.prepend(ruler);
    // the ruler scrubs the visible window (k = seconds into it)
    scrubber(ruler, {
      duration: span, seek: (k) => player.seek(V[0] + k),
      label: (k) => `${tsf(V[0] + k)}${g ? ` · ${placeLabel(V[0] + k)}` : ""}`,
      copyAt: (k) => `${slug} @ ${tsf(V[0] + k)}${g ? ` (${placeLabel(V[0] + k)})` : ""}`,
      onStart: () => player.grab(), onEnd: (k, moved) => player.release(moved),
    });
    // grid lines
    const grid = $(".snd-grid", lanesEl);
    if (g) {
      const barSet = new Set(g.bars.map((x) => x.toFixed(3)));
      for (const t of g.beats) if (t <= D() && vis(t, t)) grid.append(h(`<i class="${barSet.has(t.toFixed(3)) ? "bar" : ""}" style="left:${xOf(t)}%"></i>`));
    }
    for (const c of player.cuts()) if (vis(c.t, c.t)) grid.append(h(`<i class="cut" style="left:${xOf(c.t)}%"></i>`));
    // lanes
    for (const ln of S.lanes) lanesEl.append(lane(ln));
    body.append(lanesEl);
    const zoomed = V[0] > 0.001 || V[1] < D() - 0.001;
    body.append(h(`<div class="filmbar-l"><span>${tsf(V[0])}</span><span>${zoomed ? `${(V[1] - V[0]).toFixed(1)}s ${zoom !== "beat" ? "in view" : `around ${player.loop() ? "the loop" : "the selected beat"}`} · ` : ""}Drag on a lane to select bars · click a section, join or effect · Alt to skip beat snapping · Shift-click the ruler to copy a time</span><span>${tsf(V[1])}</span></div>`));
    body.append(h(`<div class="snd-insp" id="snd-insp"></div>`), h(`<div class="snd-notes" id="snd-notes"></div>`));
    gains();
    paintSel(); paintNotes();
    if (sel) insp();
    if (ro) ro.disconnect();
    const times = () => lanesEl && player.ruler && player.ruler($(".snd-time", lanesEl), V[0], V[1], lanesEl.clientWidth || el.clientWidth || 1000);
    times();
    ro = new ResizeObserver(() => { if (!lanesEl) return; lanesEl.querySelectorAll("canvas").forEach((c) => c._paint && c._paint()); times(); });
    ro.observe(lanesEl);
    bindSelect();
    // the timeline's zoom from here too: pinch or ⌘-scroll at the pointer, a sideways scroll to move. From Beat, zooming carries on from the beat's window
    const own = () => { if (zoom === "beat") { player.setWindow(V[0], V[1]); zoom = "film"; localStorage.setItem("cr.sndZoom", zoom); } };
    if (player.wheel) lanesEl.addEventListener("wheel", (e) => { if (e.ctrlKey || e.metaKey) own(); if (zoom !== "beat") player.wheel(e, lanesEl, V[0], V[1]); }, { passive: false });
    if (player.pinch) { lanesEl.addEventListener("gesturestart", own); player.pinch(lanesEl, () => V); }
  }
  // Beat zoom follows the Build view's selected beat (and a loop): redraw when the window moves
  function follow() {
    if (!S || !lanesEl) return;
    const n = view();
    if (Math.abs(n[0] - V[0]) > 1e-3 || Math.abs(n[1] - V[1]) > 1e-3) draw();
  }

  function lane(ln) {
    const rows = ln.kind === "music" ? "music" : ln.kind;
    const L = h(`<div class="snd-lane k-${rows}" data-lane="${esc(ln.id)}">
      <div class="snd-lh"><b>${esc(ln.label)}</b>${ln.guess ? `<span title="Loud hits off the beat grid in the separated music: probably effects">guess</span>` : ""}
        ${ln.clips && ln.clips.length ? `<button data-a="m" title="Mute">M</button><button data-a="s" title="Solo">S</button>` : ""}</div></div>`);
    if (ln.peaks && ln.peaks.length) {
      const c = document.createElement("canvas"); c.className = "wave"; L.append(c);
      c._paint = () => wave(c, ln.peaks, S.peak_rate);
      requestAnimationFrame(c._paint);
    }
    if (ln.kind === "music") {
      const strip = h(`<div class="snd-secs"></div>`);
      (S.sections || []).forEach((s, i) => {
        if (!vis(s.start, s.end)) return;
        const a0 = Math.max(s.start, V[0]), e0 = Math.min(s.end, V[1]);   // the part in view, so its name stays in sight when zoomed in
        const b = h(`<button class="sec h${s.label.charCodeAt(0) % 6}" style="left:${xOf(a0)}%;width:${wOf(e0 - a0)}%" title="${esc(`Section ${s.label}${s.tag ? ` (${s.tag})` : ""}: ${tsf(s.start)} to ${tsf(s.end)}, bars ${s.bars ? s.bars.join("-") : "?"}, ${s.energy_db} dB`)}"><span>${esc(s.label)}${s.tag ? ` · ${esc(s.tag)}` : ""}</span></button>`);
        b.onclick = (e) => { e.stopPropagation(); select({ kind: "music", lane: ln.id, start: s.start, end: s.end, label: `section ${s.label}${s.tag ? ` (${s.tag})` : ""}, ${s.bars ? `bars ${s.bars.join("-")}` : ""}` }); };
        strip.append(b);
      });
      L.append(strip);
      const pl = S.plan;
      if (pl) {
        for (const [a, e2, gdb] of pl.lift || []) if (vis(a, e2)) L.append(h(`<i class="snd-fx lift" style="left:${xOf(a)}%;width:${wOf(e2 - a)}%" title="${esc(`Lift +${gdb} dB, ${tsf(a)} to ${tsf(e2)} (bed plan)`)}"></i>`));
        for (const [a, e2] of pl.dips || []) if (vis(a, e2)) L.append(h(`<i class="snd-fx dip" style="left:${xOf(a)}%;width:${wOf(e2 - a)}%" title="${esc(`Low-pass dip, ${tsf(a)} to ${tsf(e2)} (bed plan)`)}"></i>`));
        for (const j of pl.joins || []) {
          if (!vis(j.t, j.t)) continue;
          const jb = h(`<button class="join ${j.seamless ? "seamless" : ""}" style="left:${xOf(j.t)}%" title="${esc(j.seamless ? `Piece boundary at ${tsf(j.t)} (seamless: same source time)` : `Join at ${tsf(j.t)}: the bed jumps from ${tsf(j.from)} to ${tsf(j.to)} in ${pl.source}`)}"></button>`);
          jb.onclick = (e) => { e.stopPropagation(); const p = (S.tempo && S.tempo.period * 4) || 2; select({ kind: "music", lane: ln.id, start: Math.max(0, j.t - p), end: Math.min(D(), j.t + p), label: `join at ${tsf(j.t)}${j.seamless ? " (seamless)" : `, source ${tsf(j.from)} to ${tsf(j.to)}`}` }); };
          L.append(jb);
        }
      }
    }
    if (ln.events) {
      const near = detail();
      if (near) L.classList.add("zoomed");
      const evs = h(`<div class="snd-evs ${near ? "zoomed" : ""}"></div>`);
      // stack overlapping chips on up to three rows (five when zoomed, where each chip gets room for its name)
      const rowsEnd = near ? [-1, -1, -1, -1, -1] : [-1, -1, -1];
      const pxT = span() / Math.max(300, (lanesEl && lanesEl.clientWidth) || el.clientWidth || 1000);   // seconds per pixel
      ln.events.forEach((ev) => {
        const w = Math.max(ev.dur || 0.2, 0.25);
        if (!vis(ev.t, ev.t + w)) return;
        const room = near ? (String(ev.name).length * 6.6 + 20) * pxT : span() * 0.035, t0 = Math.max(ev.t, V[0]);
        let r = rowsEnd.findIndex((x) => x <= t0); if (r < 0) r = rowsEnd.indexOf(Math.min(...rowsEnd));
        rowsEnd[r] = t0 + Math.max(ev.t + w - t0, room);
        const where = ev.grid ? ev.grid.where : "";
        const chip = h(`<button class="ev ${where === "on the beat" ? "on" : where.startsWith("on") ? "sub" : "offg"}" data-id="${esc(ev.id)}" style="left:${xOf(Math.max(ev.t, V[0]))}%;width:${wOf(Math.max(near ? room : 0, ev.t + w - Math.max(ev.t, V[0])))}%;top:${4 + r * 17}px" title="${esc(`${ev.name} at ${tsf(ev.t)}${ev.grid ? `: bar ${ev.grid.bar} beat ${ev.grid.beat_in_bar} ${Math.round(ev.grid.offset * 1000)}ms, ${where}` : ""}`)}"><span>${esc(ev.name)}</span></button>`);
        chip.onclick = (e) => { e.stopPropagation(); select({ kind: "sfx", lane: ln.id, start: ev.t, end: ev.t + (ev.dur || 0.25), ev, label: `${ev.name} (${ev.id})` }); if (ev.file) preview(ev); };
        evs.append(chip);
      });
      L.append(evs);
    }
    L.querySelectorAll(".snd-lh button").forEach((b) => (b.onclick = (e) => {
      e.stopPropagation();
      const set = b.dataset.a === "m" ? muted : solo;
      set.has(ln.id) ? set.delete(ln.id) : set.add(ln.id);
      if (b.dataset.a === "s" && solo.size) { setMode("stems"); player.soundOn(true); }
      gains();
    }));
    return L;
  }

  function wave(c, pk, rate) {
    const r = c.getBoundingClientRect(), dpr = devicePixelRatio || 1;
    c.width = Math.max(1, r.width * dpr); c.height = Math.max(1, r.height * dpr);
    const g = c.getContext("2d"), W = c.width, H = c.height, n = pk.length, k = (span() * rate) / W, p0 = V[0] * rate; // peaks per pixel, from the window's start
    g.clearRect(0, 0, W, H);
    g.fillStyle = getComputedStyle(c).color;
    for (let x = 0; x < W; x++) {
      const a = Math.floor(p0 + x * k), b = Math.max(a + 1, Math.ceil(p0 + (x + 1) * k));
      let m = 0; for (let i = a; i < b && i < n; i++) m = Math.max(m, pk[i]);
      const hgt = (m / 100) * H * 0.92;
      g.fillRect(x, (H - hgt) / 2, 1, Math.max(1, hgt));
    }
  }

  /* ----- selection ----- */
  function bindSelect() {
    let down = null;
    lanesEl.addEventListener("pointerdown", (e) => {
      if (e.button || e.target.closest("button, .snd-ruler")) return;
      const ln = e.target.closest(".snd-lane"); if (!ln) return;
      e.preventDefault(); lanesEl.setPointerCapture(e.pointerId);
      down = { x: e.clientX, t: tAt(e.clientX), lane: ln.dataset.lane, alt: e.altKey };
    });
    lanesEl.addEventListener("pointermove", (e) => {
      if (!down || Math.abs(e.clientX - down.x) < 4) return;
      const t = tAt(e.clientX), sn = (x) => (down.alt || e.altKey ? x : snap(x));
      const a = sn(Math.min(down.t, t)), b = sn(Math.max(down.t, t));
      sel = { kind: laneKind(down.lane), lane: down.lane, start: a, end: Math.max(b, a + 0.05), drag: true };
      paintSel();
    });
    const up = (e) => {
      if (!down) return;
      const moved = Math.abs(e.clientX - down.x) >= 4, t = tAt(e.clientX);
      down = null;
      if (!moved) { player.seek(t); return; }
      sel.drag = false; sel.label = barsLabel(sel.start, sel.end) || `${tsf(sel.start)} to ${tsf(sel.end)}`;
      select(sel);
    };
    lanesEl.addEventListener("pointerup", up); lanesEl.addEventListener("pointercancel", up);
  }
  const laneKind = (id) => (S.lanes.find((l) => l.id === id) || {}).kind || "music";
  const noteId = (s) => s.ev ? `sfx-${s.ev.id}` : `${s.kind}-${Math.round(s.start * 1000)}-${Math.round(s.end * 1000)}`;
  const stampOf = (s) => s.ev
    ? `${slug} ${s.ev.id} ${s.ev.name}${s.ev.file ? ` (${s.ev.file})` : ""} @ ${tsf(s.ev.t)}${s.ev.grid ? ` (bar ${s.ev.grid.bar} beat ${s.ev.grid.beat_in_bar}, ${Math.round(s.ev.grid.offset * 1000)}ms, ${s.ev.grid.where})` : ""}`
    : `${slug} ${s.kind} ${s.label ? s.label + ", " : ""}${tsf(s.start)} to ${tsf(s.end)}`;

  function select(s) {
    sel = s; paintSel();
    lanesEl.querySelectorAll(".ev.sel, .sec.sel").forEach((x) => x.classList.remove("sel"));
    if (s.ev) lanesEl.querySelector(`.ev[data-id="${CSS.escape(s.ev.id)}"]`)?.classList.add("sel");
    insp();
  }
  function paintSel() {
    const box = lanesEl && $(".snd-sel", lanesEl); if (!box) return;
    if (!sel) { box.style.display = "none"; return; }
    box.style.display = "block"; box.style.left = `${xOf(sel.start)}%`; box.style.width = `${Math.max(0.2, wOf(sel.end - sel.start))}%`;
  }
  function insp() {
    const box = $("#snd-insp", el); if (!box) return;
    if (!sel) { box.innerHTML = ""; player.setLoop(null); return; }
    const id = noteId(sel), n = (player.notes()[id] || {});
    const ev = sel.ev;
    box.innerHTML = "";
    const card = h(`<div class="snd-card">
      <div class="top"><span class="kind k-${esc(sel.kind)}">${esc(sel.kind)}</span><b>${esc(sel.label || "")}</b>
        ${tcCopy(`${tsf(sel.start)} to ${tsf(sel.end)}`, stampOf(sel))}<span class="dim">${(sel.end - sel.start).toFixed(2)}s</span><span class="spacer"></span>
        ${ev && ev.file ? `<button class="icon-btn sm" data-a="hear" title="Play this effect alone">${icon("volume-2")}Hear it</button>` : ""}
        <button class="icon-btn sm ${player.loop() ? "on" : ""}" data-a="loop" title="Loop this range in the render">${icon("repeat")}${player.loop() ? "Looping" : "Loop"}</button>
        <button class="icon-btn sm sq ghost" data-a="x" title="Clear the selection">${icon("x")}</button></div>
      ${ev ? `<div class="dim">${esc(ev.file || "")}${ev.gain != null ? ` · volume ${ev.gain}` : ""}${ev.grid ? ` · ${esc(placeLabel(ev.t))}, ${esc(ev.grid.where)}` : ""}${ev.guess ? " · a guess from the separated music" : ""}</div>` : ""}
      <textarea class="note" rows="2" placeholder="Note for the agent: what to change here (e.g. cut a bar, softer, move it onto the beat, swap the sound)">${esc(n.note || "")}</textarea>
      <div class="bx-btns"><button class="icon-btn sm primary" data-a="save">${icon("message-square")}Save note</button><button class="icon-btn sm" data-a="copy">${icon("copy")}Copy</button></div></div>`);
    box.append(card);
    $('[data-a="x"]', card).onclick = () => { sel = null; paintSel(); insp(); lanesEl.querySelectorAll(".sel").forEach((x) => x.classList.remove("sel")); follow(); };
    $('[data-a="loop"]', card).onclick = () => { player.setLoop(player.loop() ? null : [sel.start, sel.end]); if (player.loop()) { player.seek(sel.start); player.play(); } insp(); follow(); };
    $('[data-a="hear"]', card)?.addEventListener("click", () => preview(ev, true));
    $('[data-a="copy"]', card).onclick = () => copy(stampOf(sel), `Copied ${stampOf(sel)}`);
    $('[data-a="save"]', card).onclick = () => saveNote(id, { kind: sel.kind, label: sel.label || "", start: +sel.start.toFixed(3), end: +sel.end.toFixed(3), ref: ev ? ev.id : sel.lane, note: $("textarea", card).value.trim() });
    if (player.loop()) player.setLoop([sel.start, sel.end]);
  }
  async function saveNote(id, body) {
    try {
      const r = await fetch(`/api/productions/${encodeURIComponent(slug)}/sound/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(body) });
      const j = await r.json(); if (!r.ok) throw new Error(j.error);
      player.setNotes(j); paintNotes(); toast(body.note || body.done ? "Saved to the film's notes" : "Note removed");
    } catch (e) { toast(`Couldn't save: ${e.message}`); }
  }
  function paintNotes() {
    const box = $("#snd-notes", el); if (!box) return;
    const all = Object.entries(player.notes()).filter(([, v]) => v.note).sort((a, b) => (a[1].start || 0) - (b[1].start || 0));
    lanesEl.querySelectorAll(".snd-pin").forEach((x) => x.remove());
    for (const [, v] of all) if (v.start != null) lanesEl.append(h(`<i class="snd-pin" style="left:${xOf(v.start)}%" title="${esc(v.note)}"></i>`));
    if (!all.length) { box.innerHTML = ""; return; }
    box.innerHTML = `<h3>Sound notes <span>${all.length}</span></h3>`;
    for (const [id, v] of all) {
      const r = h(`<div class="snd-note"><span class="kind k-${esc(v.kind || "")}">${esc(v.kind || "")}</span>
        <div class="txt"><div class="lbl">${esc(v.label || id)} · ${tcCopy(`${tsf(v.start)} to ${tsf(v.end)}`, `${slug} ${v.kind} ${v.label ? v.label + ", " : ""}${tsf(v.start)} to ${tsf(v.end)}`)}</div><div>${esc(v.note)}</div></div>
        <button class="icon-btn sm ghost" data-a="go" title="Select and loop it">${icon("repeat")}</button>
        <button class="icon-btn sm ghost" data-a="prompt" title="Copy a fix prompt for this note">${icon("copy")}</button>
        <button class="icon-btn sm ghost" data-a="done" title="Mark it done (files it in the note's log)">${icon("check")}</button></div>`);
      $('[data-a="go"]', r).onclick = () => {
        const lane = S.lanes.find((l) => l.events && l.events.some((e) => `sfx-${e.id}` === id));
        const ev = lane && lane.events.find((e) => `sfx-${e.id}` === id);
        select({ kind: v.kind, lane: v.ref, start: v.start, end: v.end, label: v.label, ev });
        player.setLoop([v.start, v.end]); player.seek(v.start); player.play(); insp(); follow();
      };
      $('[data-a="prompt"]', r).onclick = () => copy(player.prompt([[id, v]]), "Fix prompt copied");
      $('[data-a="done"]', r).onclick = () => { const d = prompt("What changed? (filed with the note)", "Fixed in review"); if (d != null) saveNote(id, { done: d || "done" }); };
      box.append(r);
    }
  }

  /* ----- takes: alternatives for a track (takes.json), auditioned in the stems under the picture, then used ----- */
  // An auditioned take replaces its track's clip in the stems: same start and gain, the take's own file, offset and length.
  function swap(c, ln) {
    if (!aud || aud.track !== c.id) return c;
    const t = aud.take, off = +t.offset || 0;
    let dur = (+t.dur || 0) - off;
    if (ln.kind === "music" && dur > 0) dur = Math.min(dur, D() - c.start);
    return { ...c, file: t.file, offset: off, dur: dur > 0 ? dur : null, name: t.name };
  }
  const clipOf = (track) => { for (const ln of (S && S.lanes) || []) for (const c of ln.clips || []) if (c.id === track) return { c, ln }; return null; };
  async function loadTakes() {
    try { const r = await fetch(`/api/productions/${encodeURIComponent(slug)}/takes`); if (!r.ok) throw 0; T = await r.json(); }
    catch { T = null; }
    if (!dead) paintTakes();
  }
  function audition(track, take) {
    const tr = T.tracks[track], hit = clipOf(track);
    if (!hit) { toast(`${tr.label || track} isn't in the stems, so it can't be heard here`); return; }
    if (audLoop && hit.ln.kind !== "voice") { player.setLoop(null); audLoop = false; follow(); }
    aud = { track, take };
    setMode("stems"); player.soundOn(true);
    if (hit.ln.kind === "voice") {   // a line: loop it, with a little air either side
      const a = Math.max(0, hit.c.start - 0.4), e = Math.min(D(), hit.c.start + Math.max(+take.dur || hit.c.dur || 2, hit.c.dur || 0) + 0.4);
      player.setLoop([a, e]); audLoop = true; player.seek(a); follow();
    }
    if (!player.playing()) player.play(); else schedule();
    paintTakes();
  }
  function stopAudition(quiet) {
    if (!aud) return;
    aud = null;
    if (audLoop) { player.setLoop(null); audLoop = false; follow(); }
    schedule(); if (!quiet) paintTakes();
  }
  async function useTake(track, take) {
    try {
      const r = await fetch(`/api/productions/${encodeURIComponent(slug)}/takes/${encodeURIComponent(track)}`, { method: "PATCH", body: JSON.stringify({ take: take.id }) });
      const j = await r.json(); if (!r.ok) throw new Error(j.error);
      T = j; stopAudition(true);
      toast(j.applied ? `${j.tracks[track].label || track} now plays ${take.name}: render the film to hear it in the render` : `Chosen ${take.name}: put it in the mix by hand`, 4200);
      paintTakes();
      if (j.applied) { delete maps[slug]; $("#snd-meta", el).textContent = `Reading the mix with ${take.name}…`; load(); }
    } catch (e) { toast(`Couldn't use it: ${e.message}`); }
  }
  function paintTakes() {
    const box = $("#snd-takes", el), bar = $("#snd-aud", el); if (!box) return;
    const tracks = Object.entries((T && T.tracks) || {});
    if (aud && T) {
      const tr = T.tracks[aud.track] || {};
      bar.hidden = false;
      bar.innerHTML = `<span class="dot"></span><span>Auditioning <b>${esc(aud.take.name)}</b> on ${esc(tr.label || aud.track)}${aud.take.note ? ` <span class="dim">· ${esc(aud.take.note)}</span>` : ""}</span><span class="spacer"></span>
        ${aud.take.id === tr.chosen ? `<span class="dim">This is the take the film plays</span>` : `<button class="icon-btn sm primary" data-a="use">${icon("check")}Use this take</button>`}
        <button class="icon-btn sm" data-a="stop">${icon("x")}Stop</button>`;
      $('[data-a="stop"]', bar).onclick = () => stopAudition();
      $('[data-a="use"]', bar)?.addEventListener("click", () => useTake(aud.track, aud.take));
    } else { bar.hidden = true; bar.innerHTML = ""; }
    if (!tracks.length) { box.innerHTML = ""; return; }
    box.innerHTML = `<h3>${SP.term("take", "Takes")} <span>other versions of a track: hear one under the picture, then use it</span></h3>`;
    for (const [id, tr] of tracks) {
      const cur = tr.takes.find((t) => t.id === tr.chosen);
      const hearingHere = aud && aud.track === id;
      const g = h(`<details class="tk-track" ${hearingHere || openTk.has(id) ? "open" : ""}><summary class="tk-h"><b>${esc(tr.label || id)}</b><span class="tk-cur">${esc(cur ? cur.name : (tr.current || "").split("/").pop() || "nothing")}</span><span class="dim">${esc(tr.lane || "")}${tr.start != null ? ` · from ${tsf(tr.start)}` : ""}${tr.in_mix ? "" : " · not in sound.json"}</span><span class="spacer"></span><span class="tk-change">${tr.takes.length} takes ${icon("chevron-down")}</span></summary><div class="tk-list"></div></details>`);
      g.ontoggle = () => (g.open ? openTk.add(id) : openTk.delete(id));
      const list = $(".tk-list", g);
      for (const t of tr.takes) {
        const hearing = aud && aud.track === id && aud.take.id === t.id, chosen = t.id === tr.chosen;
        const b = h(`<div class="tk ${hearing ? "on" : ""} ${chosen ? "chosen" : ""}" title="${esc(`${t.file}\nPlays in the stems, synced to the render (no ducking under the voice in the stems).`)}">
          <button class="tk-play" ${t.exists && tr.in_mix ? "" : "disabled"} title="${hearing ? "Stop" : "Hear it under the picture"}">${icon(hearing ? "pause" : "play")}</button>
          <span class="tk-n">${esc(t.name)}</span><span class="tk-d">${(+t.dur || 0).toFixed(1)}s</span><span class="tk-note">${esc(t.note || "")}</span>
          ${chosen ? `<span class="tk-on">${icon("check")}In the film</span>` : `<button class="icon-btn sm ghost tk-use" ${t.exists && tr.in_mix ? "" : "disabled"}>Use</button>`}</div>`);
        $(".tk-play", b).onclick = () => (hearing ? stopAudition() : audition(id, t));
        $(".tk-use", b)?.addEventListener("click", () => useTake(id, t));
        list.append(b);
      }
      box.append(g);
    }
  }
  loadTakes();

  /* ----- playback ----- */
  function gains() {
    if (!S) return;
    for (const ln of S.lanes) {
      if (!laneGain[ln.id] && ctx) { laneGain[ln.id] = ctx.createGain(); laneGain[ln.id].connect(master); }
      const v = solo.size ? (solo.has(ln.id) ? 1 : 0) : (muted.has(ln.id) ? 0 : 1);
      if (laneGain[ln.id]) laneGain[ln.id].gain.value = v;
      const L = lanesEl && lanesEl.querySelector(`.snd-lane[data-lane="${CSS.escape(ln.id)}"]`);
      if (L) {
        L.classList.toggle("muted", !v);
        L.querySelector('[data-a="m"]')?.classList.toggle("on", muted.has(ln.id));
        L.querySelector('[data-a="s"]')?.classList.toggle("on", solo.has(ln.id));
      }
    }
    if (master) master.gain.value = on && mode === "stems" ? level : 0;
  }
  function stopAll() { for (const s of playing) { try { s.stop(); } catch {} } playing = []; sched = null; }
  async function schedule() {
    stopAll();
    if (!S || !on || mode !== "stems" || !player.playing()) return;
    audio(); gains();
    const t0 = player.t(), rate = player.rate(), my = {};
    sched = my;
    const jobs = [];
    for (const ln of S.lanes) for (const c0 of ln.clips || []) {
      const c = swap(c0, ln);
      if ((c.dur != null && c.start + c.dur <= t0) || !c.file) continue;
      jobs.push(buffer(c.file).then((buf) => ({ buf, c, ln })));
    }
    const ready = await Promise.all(jobs);
    if (sched !== my || !player.playing()) return;
    const now = ctx.currentTime + 0.03, tNow = player.t() + 0.03 * rate;
    for (const { buf, c, ln } of ready) {
      if (!buf) continue;
      const into = Math.max(0, tNow - c.start), dur = (c.dur || buf.duration - (c.offset || 0)) - into;
      if (dur <= 0) continue;
      const src = ctx.createBufferSource(); src.buffer = buf; src.playbackRate.value = rate;
      const g = ctx.createGain(); g.gain.value = c.gain ?? 1;
      src.connect(g); g.connect(laneGain[ln.id] || master);
      src.start(now + Math.max(0, (c.start - tNow) / rate), (c.offset || 0) + into, dur);
      playing.push(src);
    }
    my.ctx0 = now; my.t0 = tNow; my.rate = rate;
  }
  async function preview(ev, force) {
    if (!ev.file || (!force && !on)) return;
    audio(); const buf = await buffer(ev.file); if (!buf) return;
    const src = ctx.createBufferSource(); src.buffer = buf; const g = ctx.createGain(); g.gain.value = Math.max(0.3, ev.gain || 1) * level;   // not through master (that is silent with the stems off), so the level is applied here
    src.connect(g); g.connect(ctx.destination); src.start();
  }
  function setMode(m) { mode = m; paintMode(); player.applySound(); schedule(); }
  function paintMode() { el.querySelectorAll("#snd-mode button").forEach((b) => b.classList.toggle("on", b.dataset.v === mode)); }

  // follow the render
  const v = player.video();
  const re = () => schedule();
  if (v) { ["play", "seeked", "ratechange"].forEach((n) => v.addEventListener(n, re)); ["pause", "seeking", "waiting"].forEach((n) => v.addEventListener(n, stopAll)); }

  return {
    reload: () => load(),   // the film's sound changed on disk (build.js polls sound_stamp): read the map again
    tick(t) {
      if (!lanesEl) return;
      const ph = $(".snd-ph", lanesEl); if (ph) ph.style.left = `${xOf(t)}%`;
      if (sched && sched.ctx0 && ctx && player.playing()) {   // drift check
        const want = sched.t0 + (ctx.currentTime - sched.ctx0) * sched.rate;
        if (ctx.currentTime > sched.ctx0 + 0.3 && Math.abs(want - t) > 0.09) schedule();
      }
    },
    setOn(x) { on = x; if (on) audio(); gains(); schedule(); },
    setVolume(g) { level = g; gains(); },
    follow,
    mode: () => (S && S.lanes.some((l) => l.clips && l.clips.length) ? mode : "render"),
    refreshNotes: paintNotes,
    destroy() { dead = true; if (aud) stopAudition(); stopAll(); if (v) { ["play", "seeked", "ratechange"].forEach((n) => v.removeEventListener(n, re)); ["pause", "seeking", "waiting"].forEach((n) => v.removeEventListener(n, stopAll)); } },
  };
}
return { mount };
};
