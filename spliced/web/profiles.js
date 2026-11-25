/* Profiles (#/profiles): the looks the project's films are made in. Each keeps a palette, a typeface, a motion (a base
   motion profile and what this look changes about it), the scenes that show it, its own words (PROFILE.md) and the
   rules learned while making films. One can be the default: briefs start in it. Every brief can choose another, or
   none: then the reference is recreated as it is, in its own look.

   The data is the server's (/api/profiles, profiles.py, the same as `spliced profile`); this shows it and edits it.
   Other views use: Profiles.pick (a menu of choices), Profiles.line (what a prompt says about the choice),
   Profiles.splitCopy (a copy button with its profile beside it), Profiles.pinRow (a scene's "shows the look of"). */
window.Profiles = (() => {
"use strict";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const icon = (n) => window.icon(n);
const toast = (m, ms) => window.crToast?.(m, ms);
const NONE = "none";
let list = [], def = "", motion = {}, knobs = {}, kit = {}, starts = [], fonts = null;
const listeners = new Set();

async function load() {
  try {
    const j = await (await fetch("/api/profiles", { cache: "no-store" })).json();
    list = j.profiles || []; def = j.default || ""; motion = j.motion || {}; knobs = j.knobs || {}; kit = j.kit || {}; starts = j.motions || [];
  } catch {}
  listeners.forEach((fn) => fn());
  return list;
}
const ready = load();
async function post(body) {
  const r = await fetch("/api/profiles", { method: "POST", body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Couldn't save it");
  list = j.profiles || list; def = j.default ?? def; starts = j.motions || starts;
  listeners.forEach((fn) => fn());
  return j;
}
const get = (slug) => list.find((p) => p.slug === slug);
/** A stored choice ("" = the project's default) as a profile's slug, or "none". */
const resolve = (v) => (v === NONE ? NONE : v && get(v) ? v : def || NONE);
const name = (v) => { const r = resolve(v); return r === NONE ? "No profile" : get(r).name; };

/** What a prompt says about the profile it is made in. many: a board (several references) rather than one film or scene. */
function line(v, { many = false } = {}) {
  const r = resolve(v);
  if (r === NONE) return `Profile: none. Recreate what ${many ? "each referenced scene" : "the reference"} shows, in its own look: its framing, palette, type, copy and motion as they are. Don't move it into a profile or house style; follow "A study of one film" in the make-film skill${many ? ", beat by beat" : ""}.`;
  const p = get(r);
  return `Profile: ${p.name}. Make it in this profile: read \`${SP.cmd("profile", "show", r)}\` first. Its look, its motion (built on \`${p.motion.base}\`) and its rules win over the kit's defaults. Recreate the referenced ${many ? "scenes'" : "scene's"} choreography inside it: borrow the move, not the reference's look.`;
}

const remembered = (ctx, fallback) => localStorage.getItem(`cr.profileFor.${ctx}`) ?? fallback;
const remember = (ctx, v) => localStorage.setItem(`cr.profileFor.${ctx}`, v);

/** A menu of the choices: every profile, then none; the current one ticked. */
function pick(anchor, current, onPick) {
  const r = resolve(current);
  CR.menu(anchor, [
    ...list.map((p) => ({ value: p.slug, on: r === p.slug, html: `<span class="pf-dots">${dots(p.palette, 3)}</span><span class="lbl">${esc(p.name)}</span><span class="c">${p.slug === def ? "default" : ""}</span>` })),
    { value: NONE, sep: list.length > 0, on: r === NONE, html: `<span class="pf-dots"><i class="none"></i></span><span class="lbl">No profile</span><span class="c">copy it as it is</span>` },
    { value: "__manage", sep: true, html: `${icon("palette")}<span class="lbl">${list.length ? "Manage profiles" : "Make a profile"}</span>` },
  ], (v) => { if (v === "__manage") location.hash = "#/profiles"; else onPick(v); });
}

/** A copy button with the profile it copies for beside it: the first part copies, the second picks another profile.
    make(choice) gives the text; ctx remembers the choice per kind of brief; fallback is the first choice ("" = default). */
function splitCopy({ ctx, fallback = "", text, title, make, msg }) {
  const el = h(`<span class="pf-split"><button class="icon-btn sm primary" data-a="copy" title="${esc(title)}">${icon("copy")}${esc(text)}</button><button class="pf-for" data-a="for"></button></span>`);
  const paint = () => { const v = remembered(ctx, fallback), r = resolve(v), b = el.querySelector('[data-a="for"]');
    b.innerHTML = `<span class="pf-dots">${r === NONE ? `<i class="none"></i>` : dots(get(r).palette, 3)}</span>${esc(name(v))}${icon("chevron-down")}`;
    b.title = `Copied for: ${name(v)}. Choose another profile, or No profile to copy the reference as it is`; };
  el.querySelector('[data-a="copy"]').onclick = () => CR.copy(make(remembered(ctx, fallback)), msg);
  el.querySelector('[data-a="for"]').onclick = (e) => pick(e.currentTarget, remembered(ctx, fallback), (v) => { remember(ctx, v); paint(); CR.copy(make(v), msg); });
  paint(); ready.then(paint);
  return el;
}
const briefFor = (ctx, fallback, make) => make(remembered(ctx, fallback));

/** A scene's row of profiles it shows the look of: click one to pin the scene to it, or take it out. */
function pinRow(key) {
  const el = h(`<div class="d-sec pf-pins" hidden><h5>Shows the look of</h5><div class="pf-chips"></div></div>`);
  const paint = () => {
    el.hidden = !list.length;
    el.querySelector(".pf-chips").innerHTML = list.map((p) => { const on = p.scenes.includes(key);
      return `<button class="pf-chip ${on ? "on" : ""}" data-p="${esc(p.slug)}" title="${on ? `Take it out of ${esc(p.name)}` : `Add it to ${esc(p.name)}'s scenes: ${esc(SP.ai)} looks at them before building in it`}">${on ? icon("check") : icon("plus")}${esc(p.name)}</button>`; }).join("");
    el.querySelectorAll(".pf-chip").forEach((b) => (b.onclick = async () => {
      const p = get(b.dataset.p), on = p.scenes.includes(key);
      try { await post({ op: on ? "unpin" : "pin", profile: p.slug, scene: key }); toast(on ? `Taken out of ${p.name}` : `Added to ${p.name}`); paint(); } catch (e) { toast(e.message); }
    }));
  };
  ready.then(paint);
  return el;
}

/* ---------- colour ---------- */
const rgb = (hx) => { let s = String(hx).replace("#", ""); if (s.length === 3) s = [...s].map((c) => c + c).join(""); const n = parseInt(s.slice(0, 6), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const lum = (hx) => { const [r, g, b] = rgb(hx).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
const sat = (hx) => { const [r, g, b] = rgb(hx); const mx = Math.max(r, g, b), mn = Math.min(r, g, b); return mx ? (mx - mn) / mx : 0; };
const dist = (a, b) => { const [x, y] = [rgb(a), rgb(b)]; return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]); };
const toHex = (c) => "#" + c.map((v) => Math.round(v).toString(16).padStart(2, "0")).join("").toUpperCase();
const dots = (pal, n) => (pal || []).slice(0, n).map((c) => `<i style="background:${esc(c.hex)}"></i>`).join("") || `<i class="none"></i>`;
/** The roles a palette plays on a stage: background (the first colour), ink (most contrast with it), accent (most colourful of the rest). */
function roles(pal) {
  const hx = (pal || []).map((c) => c.hex);
  const bg = hx[0] || "#151517";
  const ink = [...hx.slice(1), "#FFFFFF", "#111111"].sort((a, b) => contrast(b, bg) - contrast(a, bg))[0];
  const rest = hx.filter((x) => x !== bg && x !== ink);
  const accent = rest.sort((a, b) => sat(b) - sat(a))[0] || (lum(bg) > 0.5 ? "#2A2A2E" : "#DFDFE3");
  return { bg, ink, accent, second: rest.find((x) => x !== accent) || accent };
}
/** A palette from scenes' own palettes: their colours clustered, the most common first. */
function paletteFrom(keys) {
  const all = keys.flatMap((k) => { const s = CR.scene(k); return (s?.palette || s?.upload?.palette || []); }).filter((x) => /^#[0-9a-f]{3,8}$/i.test(x));
  const groups = [];
  for (const c of all) { const g = groups.find((x) => dist(x.c, c) < 48); if (g) { g.n++; g.sum = g.sum.map((v, i) => v + rgb(c)[i]); g.c = toHex(g.sum.map((v) => v / g.n)); } else groups.push({ c, n: 1, sum: rgb(c) }); }
  return groups.sort((a, b) => b.n - a.n).slice(0, 6).map((g) => ({ hex: g.c }));
}
/** How close a scene's palette is to the profile's: the mean distance from each of its colours to the nearest of ours. */
function closeness(s, pal) {
  const sp = s.palette || s.upload?.palette || [];
  if (!sp.length || !pal.length) return 999;
  return sp.reduce((t, c) => t + Math.min(...pal.map((p) => dist(c, p.hex))), 0) / sp.length;
}

/* ---------- motion ---------- */
const KNOB = {
  pace: { label: "Pace", min: 0.5, max: 2, step: 0.05, show: (v) => v === 1 ? "as the base" : `${v.toFixed(2)}x ${v > 1 ? "slower" : "brisker"}`, tip: "How long every move takes, against the base. Right is slower" },
  bounce: { label: "Bounce", min: 0, max: 0.5, step: 0.01, show: (v) => v === 0 ? "none" : v < 0.12 ? "a touch" : v < 0.25 ? "a little" : "playful", tip: "Overshoot when UI and emphasis land" },
  stagger: { label: "Stagger", min: 0, max: 0.3, step: 0.01, show: (v) => `${Math.round(v * 1000)} ms`, tip: "Time between grouped items: words, cards, rows" },
  idle: { label: "Float", min: 0, max: 1, step: 0.05, show: (v) => v === 0 ? "still" : v < 0.4 ? "a little" : "drifting", tip: "How much things float while they are held on screen" },
};
const CHOICE = {
  transition: { label: "Scene change", opts: [["cut", "Cut"], ["blurThrough", "Blur"], ["fadeThrough", "Fade"], ["sharedAxisX", "Slide"], ["sharedAxisZ", "Push"]], tip: "How one scene becomes the next" },
  text: { label: "Words", opts: [["sharpen", "Sharpen"], ["greyToInk", "Grey to ink"]], tip: "How words arrive: sharpen in from a blur, or land grey and darken" },
};
const baseOf = (m) => kit[m.base] || kit.soft || { pace: 1, bounce: 0, stagger: 0.1, transition: "cut", text: "sharpen", idle: 0.5, curve: [0.2, 0.8, 0.2, 1], enter: 0.6 };
const val = (m, k) => (k in m ? m[k] : baseOf(m)[k]);

/** A small stage that plays the look: its palette and typeface, a card arriving with its motion, words, a scene change. Loops. */
function stage(p, { big = false } = {}) {
  const el = h(`<div class="pf-stage ${big ? "big" : ""}"><div class="pf-fr a"><div class="pf-st-card"></div><div class="pf-words"></div></div><div class="pf-fr b"><div class="pf-big"></div></div>
    ${big ? `<button class="pf-replay" title="Play the motion again">${icon("rotate-cw")}</button>` : ""}</div>`);
  let timer = 0, cur = p;
  const paint = () => {
    const r = roles(cur.palette), font = cur.font ? `"${cur.font.replace(/"/g, "")}", ` : "";
    if (cur.font_source === "google") googleFace(cur.font);
    el.style.setProperty("--bg", r.bg); el.style.setProperty("--ink", r.ink); el.style.setProperty("--ac", r.accent); el.style.setProperty("--ac2", r.second);
    el.style.setProperty("--font", `${font}Inter, system-ui, sans-serif`);
    const words = (cur.about && cur.about.split(/\s+/).length <= 6 ? cur.about : cur.name).split(/\s+/).slice(0, 5);
    el.querySelector(".pf-words").innerHTML = words.map((w) => `<span>${esc(w)}</span>`).join(" ");
    el.querySelector(".pf-big").textContent = cur.name;
  };
  const play = () => {
    clearTimeout(timer);
    if (!el.isConnected && timer) return;
    const m = cur.motion, b = baseOf(m), pace = val(m, "pace"), bounce = val(m, "bounce"), stg = val(m, "stagger"), idle = val(m, "idle");
    const enter = b.enter * pace * 1000, ease = bounce > 0.01 ? `cubic-bezier(0.34, ${(1 + bounce * 2.4).toFixed(2)}, 0.64, 1)` : `cubic-bezier(${b.curve.join(",")})`;
    const [A, B] = el.querySelectorAll(".pf-fr"), card = el.querySelector(".pf-st-card"), words = [...el.querySelectorAll(".pf-words span")], big = el.querySelector(".pf-big");
    el.getAnimations({ subtree: true }).forEach((a) => a.cancel());
    A.style.opacity = 1; B.style.opacity = 0;
    card.animate([{ transform: "translateY(26%) scale(0.92)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: enter, easing: ease, fill: "both", delay: 150 });
    if (idle > 0.01) card.animate([{ transform: "translateY(0)" }, { transform: `translateY(${-3 * idle}%)` }, { transform: "translateY(0)" }], { duration: 2200, iterations: Infinity, delay: 150 + enter, composite: "add", easing: "ease-in-out" });
    const grey = val(m, "text") === "greyToInk";
    words.forEach((w, i) => w.animate(grey ? [{ opacity: 0, color: "color-mix(in srgb, var(--ink) 35%, var(--bg))" }, { opacity: 1, color: "color-mix(in srgb, var(--ink) 35%, var(--bg))", offset: 0.35 }, { opacity: 1, color: "var(--ink)" }]
      : [{ opacity: 0, filter: "blur(6px)", transform: "translateY(30%)" }, { opacity: 1, filter: "blur(0)", transform: "none" }],
      { duration: (grey ? 1.6 : 1) * 520 * pace, delay: 150 + enter * 0.5 + i * stg * 1000, easing: `cubic-bezier(${b.curve.join(",")})`, fill: "both" }));
    const at = 150 + enter + words.length * stg * 1000 + 1300 * pace, dur = 520 * pace, tr = val(m, "transition");
    const out = { cut: [[{ opacity: 1 }, { opacity: 0 }], 1], blurThrough: [[{ filter: "blur(0)", opacity: 1 }, { filter: "blur(14px)", opacity: 0 }]], fadeThrough: [[{ opacity: 1 }, { opacity: 0 }]],
      sharedAxisX: [[{ transform: "none", opacity: 1 }, { transform: "translateX(-18%)", opacity: 0 }]], sharedAxisZ: [[{ transform: "none", opacity: 1 }, { transform: "scale(1.12)", opacity: 0 }]] }[tr];
    const inn = { cut: [[{ opacity: 0 }, { opacity: 1 }], 1], blurThrough: [[{ filter: "blur(14px)", opacity: 0 }, { filter: "blur(0)", opacity: 1 }]], fadeThrough: [[{ opacity: 0 }, { opacity: 1 }]],
      sharedAxisX: [[{ transform: "translateX(18%)", opacity: 0 }, { transform: "none", opacity: 1 }]], sharedAxisZ: [[{ transform: "scale(0.9)", opacity: 0 }, { transform: "none", opacity: 1 }]] }[tr];
    const d = (x) => (x[1] ? 1 : dur);
    A.animate(out[0], { duration: d(out), delay: at, fill: "forwards", easing: "cubic-bezier(0.4,0,1,1)" });
    B.animate(inn[0], { duration: d(inn), delay: at + (tr === "fadeThrough" || tr === "blurThrough" ? dur * 0.45 : 0), fill: "forwards", easing: `cubic-bezier(${b.curve.join(",")})` });
    big.animate([{ letterSpacing: "0.04em" }, { letterSpacing: "-0.02em" }], { duration: enter * 1.4, delay: at, fill: "both", easing: `cubic-bezier(${b.curve.join(",")})` });
    timer = setTimeout(() => { if (el.isConnected) play(); }, at + dur + 1500 * pace);
  };
  el.querySelector(".pf-replay")?.addEventListener("click", play);
  paint(); requestAnimationFrame(play);
  el.update = (q) => { cur = q; paint(); play(); };
  return el;
}

/* ---------- typefaces ---------- */
/* Google Fonts: the names ship with Spliced (google-fonts.json); a face is fetched from Google only when it is shown,
   in the picker's Google tab or for a profile that uses one. spliced.json "google_fonts": false turns all of it off. */
let gfList = null;
const gfLoaded = new Set();
const googleOK = () => fonts?.google !== false && SPLICED.google_fonts !== false;
function googleFace(family, text) {
  if (!family || !googleOK()) return;
  const key = family + (text ? "|t" : "");
  if (gfLoaded.has(key) || gfLoaded.has(family)) return;
  gfLoaded.add(key);
  const l = document.createElement("link");
  l.rel = "stylesheet";
  l.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(family).replace(/%20/g, "+")}${text ? `&text=${encodeURIComponent(text)}` : ":wght@400;600;700"}&display=swap`;
  document.head.append(l);
}
async function fontLists() {
  if (!fonts) { try { fonts = await (await fetch("/api/fonts")).json(); } catch { fonts = { installed: [], google: false }; } }
  if (!gfList && googleOK()) { try { gfList = (await (await fetch("google-fonts.json")).json()).families; } catch { gfList = []; } }
  return { installed: fonts.installed || [], google: googleOK() ? gfList || [] : null };
}
const faceCss = (family, source) => family ? `"${family.replace(/"/g, "")}", Inter, system-ui, sans-serif` : "";

/* The typeface sheet: this Mac's families (what Font Book has) or Google Fonts, each shown in its own face. */
async function fontPicker({ title, current, source, sample, allowSame, onPick }) {
  const L = await fontLists();
  const CATS = [["", "All"], ["sans", "Sans"], ["serif", "Serif"], ["display", "Display"], ["hand", "Handwriting"], ["mono", "Mono"]];
  let tab = source === "google" && L.google ? "google" : "local", cat = "";
  const scrim = h(`<div class="pf-scrim"><div class="pf-sheet pf-fonts" role="dialog" aria-label="${esc(title)}">
    <div class="pf-sheet-h"><b>${esc(title)}</b><input type="search" placeholder="Search typefaces" aria-label="Search typefaces" title="Search by name">
      <input class="pf-sample" value="${esc(sample)}" aria-label="Sample text" title="The words each typeface shows"><button class="icon-btn sm" data-a="close" title="Close (Esc)">Close</button></div>
    <div class="pf-font-bar"><div class="seg" data-tab>
      <button data-v="local" title="The typefaces installed on this Mac, as Font Book lists them">On this Mac <span class="c">${L.installed.length}</span></button>
      ${L.google ? `<button data-v="google" title="Free typefaces from Google Fonts. Your AI loads the one you choose when it renders">Google Fonts <span class="c">${L.google.length}</span></button>` : ""}</div>
      <div class="seg pf-cats" data-cat hidden>${CATS.map(([v, t]) => `<button data-v="${v}" title="${t} typefaces">${t}</button>`).join("")}</div>
      ${allowSame ? `<button class="pf-link" data-a="same" title="Use the headline typeface for text too">Same as headlines</button>` : ""}
      <span class="pf-gf-note" hidden>Previews load from Google Fonts while this tab is open.</span></div>
    <div class="pf-font-list" role="listbox"></div></div></div>`);
  document.body.append(scrim);
  const box = scrim.querySelector(".pf-font-list"), q = scrim.querySelector('input[type="search"]'), sm = scrim.querySelector(".pf-sample");
  let shown = 0, items = [];
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting && e.target.dataset.g) { googleFace(e.target.dataset.f, sm.value || e.target.dataset.f); io.unobserve(e.target); } }), { root: box, rootMargin: "200px" });
  const row = (f, g) => `<button class="pf-font ${f === current && (g ? "google" : "local") === (source || "local") ? "on" : ""}" role="option" data-f="${esc(f)}" ${g ? 'data-g="1"' : ""} title="${esc(f)}">
      <span class="pf-font-n">${esc(f)}${g ? `<small>${esc({ sans: "Sans", serif: "Serif", display: "Display", hand: "Handwriting", mono: "Mono" }[g[1]] || "")}</small>` : ""}</span>
      <span class="pf-font-s" style="font-family:${esc(faceCss(f))}">${esc(sm.value || f)}</span></button>`;
  const more = () => {
    const next = items.slice(shown, shown + 80);
    box.insertAdjacentHTML("beforeend", next.map(([f, g]) => row(f, g)).join(""));
    [...box.children].slice(shown).forEach((el) => { if (el.dataset.g) io.observe(el); });
    shown += next.length;
  };
  const paint = () => {
    scrim.querySelector("[data-cat]").hidden = tab !== "google";
    scrim.querySelector(".pf-gf-note").hidden = tab !== "google";
    scrim.querySelectorAll("[data-tab] button").forEach((b) => b.classList.toggle("on", b.dataset.v === tab));
    scrim.querySelectorAll("[data-cat] button").forEach((b) => b.classList.toggle("on", b.dataset.v === cat));
    const w = q.value.toLowerCase().trim();
    items = tab === "google" ? L.google.filter((g) => (!cat || g[1] === cat) && (!w || g[0].toLowerCase().includes(w))).map((g) => [g[0], g])
      : L.installed.filter((f) => !w || f.toLowerCase().includes(w)).map((f) => [f, null]);
    box.innerHTML = items.length ? "" : `<p class="meta pf-font-none">${tab === "local" && !L.installed.length ? "Spliced couldn't list this Mac's typefaces." : "No typeface matches."}</p>`;
    shown = 0; box.scrollTop = 0; more();
  };
  box.addEventListener("scroll", () => { if (box.scrollTop + box.clientHeight > box.scrollHeight - 400 && shown < items.length) more(); });
  box.addEventListener("click", (e) => { const b = e.target.closest(".pf-font"); if (!b) return; onPick(b.dataset.f, b.dataset.g ? "google" : "local"); close(); });
  scrim.querySelectorAll("[data-tab] button").forEach((b) => (b.onclick = () => { tab = b.dataset.v; paint(); }));
  scrim.querySelectorAll("[data-cat] button").forEach((b) => (b.onclick = () => { cat = b.dataset.v; paint(); }));
  scrim.querySelector('[data-a="same"]')?.addEventListener("click", () => { onPick("", ""); close(); });
  sm.oninput = () => box.querySelectorAll(".pf-font-s").forEach((el) => (el.textContent = sm.value || el.closest(".pf-font").dataset.f));
  const close = () => { io.disconnect(); scrim.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  scrim.addEventListener("mousedown", (e) => { if (e.target === scrim) close(); });
  scrim.querySelector('[data-a="close"]').onclick = close;
  q.oninput = paint; paint(); q.focus();
}

/* ---------- drafting from what the person drops ---------- */
const DROP_OK = /\.(pdf|png|jpe?g|webp|gif|svg|mp4|mov|m4v|webm|txt|md|key|pptx)$/i;
async function sendSources(slug, files, onEach) {
  let n = 0;
  for (const f of files) {
    if (!DROP_OK.test(f.name)) { toast(`${f.name}: Spliced reads PDFs, images, films, decks and text`); continue; }
    onEach?.(f.name, n, files.length);
    const r = await fetch(`/api/profiles/${slug}/sources`, { method: "POST", headers: { "X-Filename": encodeURIComponent(f.name) }, body: f });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { toast(`${f.name}: ${j.error || "couldn't add it"}`); continue; }
    n++;
  }
  return n;
}
/* An in-app dialog in place of the browser's: a title, a line, an optional field. Resolves to the field's text (or
   true), or null when it is cancelled. */
function ask({ title, text = "", input = null, ok = "OK", danger = false }) {
  return new Promise((res) => {
    const scrim = h(`<div class="pf-scrim"><form class="pf-dialog" role="dialog" aria-label="${esc(title)}"><b>${esc(title)}</b>${text ? `<p>${esc(text)}</p>` : ""}
      ${input !== null ? `<input value="${esc(input)}" aria-label="${esc(title)}" title="${esc(title)}" spellcheck="false">` : ""}
      <div class="pf-dialog-a"><button type="button" class="icon-btn sm ghost" data-a="no" title="Cancel (Esc)">Cancel</button><button class="icon-btn sm ${danger ? "pf-danger" : "primary"}" title="${esc(ok)}">${esc(ok)}</button></div></form></div>`);
    const done = (v) => { scrim.remove(); document.removeEventListener("keydown", key, true); res(v); };
    const key = (e) => { if (e.key === "Escape") { e.stopPropagation(); done(null); } };
    document.addEventListener("keydown", key, true);
    scrim.addEventListener("mousedown", (e) => { if (e.target === scrim) done(null); });
    scrim.querySelector('[data-a="no"]').onclick = () => done(null);
    const inp = scrim.querySelector("input");
    scrim.querySelector("form").onsubmit = (e) => { e.preventDefault(); if (inp && !inp.value.trim()) return inp.focus(); done(inp ? inp.value.trim() : true); };
    document.body.append(scrim);
    (inp || scrim.querySelector("button.primary, button.pf-danger")).focus(); inp?.select();
  });
}

/* New profile: three ways in, each a click or a drop. Files a person drops are read by their AI, which fills the
   profile in; a film from the library gives its palette, type and moves; blank is for setting it up by hand. */
function newSheet({ film = null, files = null } = {}) {
  const films = CR.films();
  let how = files ? "files" : film ? "film" : "files", chosen = files ? [...files] : [], pick = film?.slug || "";
  const scrim = h(`<div class="pf-scrim"><div class="pf-sheet pf-new" role="dialog" aria-label="New profile">
    <div class="pf-sheet-h"><b>New profile</b><span class="spacer"></span><button class="icon-btn sm ghost" data-a="close" title="Close (Esc)">${icon("x")}</button></div>
    <div class="pf-new-body">
      <label class="pf-new-name"><span>Name</span><input placeholder="Your company, or the look you want" aria-label="Name" title="What the app and ${esc(SP.ai)} call it"></label>
      <div class="pf-new-ways">
        <button data-how="files" title="${esc(SP.Ai)} reads a brand book, logo, screenshots or a film and fills the profile in">${icon("upload")}<b>From files</b><small>A brand book, logo, screenshots or a film. ${esc(SP.Ai)} fills it in.</small></button>
        <button data-how="film" title="Take a film's palette, type and moves from your library" ${films.length ? "" : "disabled"}>${icon("film")}<b>From a film</b><small>${films.length ? "Its palette, type and moves, from your library." : "Add a reference film first."}</small></button>
        <button data-how="blank" title="Set the colours, typefaces and motion yourself">${icon("plus")}<b>Blank</b><small>Choose everything yourself, or ask ${esc(SP.ai)} later.</small></button>
      </div>
      <div class="pf-new-pane"></div>
    </div>
    <div class="pf-new-foot"><span class="meta pf-new-hint"></span><button class="icon-btn primary" data-a="go" title="Make the profile">Create</button></div></div></div>`);
  document.body.append(scrim);
  const nameEl = scrim.querySelector(".pf-new-name input"), pane = scrim.querySelector(".pf-new-pane"), go = scrim.querySelector('[data-a="go"]'), hint = scrim.querySelector(".pf-new-hint");
  const guess = (f) => f.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").replace(/\b(brand ?book|guidelines?|brand|final|v\d+)\b/gi, "").trim();
  const paint = () => {
    scrim.querySelectorAll("[data-how]").forEach((b) => b.classList.toggle("on", b.dataset.how === how));
    if (how === "files") {
      pane.innerHTML = "";
      const dz = dropZone(chosen.length ? `${chosen.length} file${chosen.length > 1 ? "s" : ""}: ${chosen.map((f) => f.name).join(", ")}` : "Drop files here, or click to choose");
      wireDrop(dz, (fs) => { chosen = [...chosen, ...[...fs].filter((f) => DROP_OK.test(f.name))]; if (!nameEl.value && chosen[0]) nameEl.value = guess(chosen[0]); paint(); });
      pane.append(dz);
      go.textContent = "Create and draft"; go.disabled = !chosen.length;
      hint.textContent = chosen.length ? `${SP.Ai} reads ${chosen.length > 1 ? "them" : "it"} and fills in the palette, typefaces, motion and rules. You can change everything after.` : "";
    } else if (how === "film") {
      pane.innerHTML = `<div class="pf-new-films">${films.map((f) => `<button class="pf-new-film ${f.slug === pick ? "on" : ""}" data-f="${esc(f.slug)}" title="${esc(f.title)}">${f.thumb ? `<img alt="" loading="lazy" src="${esc(f.thumb)}">` : "<span></span>"}<small>${esc(f.title)}</small></button>`).join("")}</div>`;
      pane.querySelectorAll("[data-f]").forEach((b) => (b.onclick = () => { const was = films.find((f) => f.slug === pick); pick = b.dataset.f; if (!nameEl.value || (was && nameEl.value === `${was.title} look`)) nameEl.value = `${films.find((f) => f.slug === pick).title} look`; paint(); }));
      go.textContent = "Create from this film"; go.disabled = !pick;
      hint.textContent = pick ? "Its palette, type and signature scenes come with it. You can change everything after." : "";
    } else {
      pane.innerHTML = `<p class="meta pf-new-blank">An empty profile. Choose its colours, typefaces and motion on its page, or tell ${esc(SP.ai)} what it should be.</p>`;
      go.textContent = "Create"; go.disabled = false; hint.textContent = "";
    }
  };
  scrim.querySelectorAll("[data-how]").forEach((b) => (b.onclick = () => { how = b.dataset.how; paint(); }));
  const close = () => { scrim.remove(); document.removeEventListener("keydown", key, true); };
  const key = (e) => { if (e.key === "Escape" && !document.querySelector(".pf-dialog")) { e.stopPropagation(); close(); } };
  document.addEventListener("keydown", key, true);
  scrim.addEventListener("mousedown", (e) => { if (e.target === scrim) close(); });
  scrim.querySelector('[data-a="close"]').onclick = close;
  go.onclick = async () => {
    const f = films.find((x) => x.slug === pick);
    const n = nameEl.value.trim() || (how === "film" && f ? `${f.title} look` : how === "files" && chosen[0] ? guess(chosen[0]) : "");
    if (!n) { nameEl.focus(); nameEl.placeholder = "Give it a name first"; return; }
    go.disabled = true;
    try {
      const j = await post({ op: "new", name: n, from_film: how === "film" ? pick : undefined });
      if (how === "files") { go.textContent = "Adding files…"; if (await sendSources(j.profile, chosen)) await post({ op: "draft", profile: j.profile }); window.Imports?.refresh?.(); }
      close(); toast(`Made the profile ${n}`); location.hash = `#/profiles/${j.profile}`;
    } catch (e) { toast(e.message); go.disabled = false; }
  };
  paint(); nameEl.focus();
}
const draftNew = (files) => newSheet({ files });
let dropTarget = null;   // the profile page open, if any: drops add to its sources
function drop(files) { if (dropTarget) dropTarget(files); else draftNew(files); }
async function jobFor(slug) {
  try { const r = await (await fetch("/api/imports")).json(); return (r.jobs || []).filter((j) => j.type === "profile" && j.slug === slug).pop() || null; } catch { return null; }
}

/* ---------- the list ---------- */
const thumbs = (keys, n) => keys.slice(0, n).map((k) => { const s = CR.scene(k); return s ? `<img alt="" loading="lazy" src="${esc(CR.sceneThumb(s))}">` : ""; }).join("");

const create = (film) => newSheet({ film });
const dropZone = (label) => h(`<label class="pf-drop" title="Drop a brand book, a logo, screenshots or a film, or click to choose files. ${esc(SP.Ai)} reads them and fills the profile in">
  ${icon("upload")}<span><b>${label}</b><small>A brand book (PDF), a logo, screenshots, a film or a deck. ${esc(SP.Ai)} reads them and fills in the palette, typefaces, motion and rules.</small></span>
  <input type="file" multiple hidden accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.svg,.mp4,.mov,.m4v,.webm,.txt,.md,.key,.pptx"></label>`);
function wireDrop(el, onFiles) {
  el.querySelector("input").onchange = (e) => { onFiles(e.target.files); e.target.value = ""; };
  el.addEventListener("dragover", (e) => { e.preventDefault(); e.stopPropagation(); el.classList.add("over"); });
  el.addEventListener("dragleave", () => el.classList.remove("over"));
  el.addEventListener("drop", (e) => { e.preventDefault(); e.stopPropagation(); el.classList.remove("over"); onFiles(e.dataTransfer.files); });
}

async function render(main, slug) {
  main.innerHTML = `<div class="empty">Loading profiles…</div>`;
  await load();
  dropTarget = null;
  document.body.dataset.dropProfile = "a new profile";
  if (slug) return detail(main, slug);
  main.innerHTML = "";
  const head = h(`<div class="view-head"><h1>Profiles</h1><span class="meta">${list.length ? `${list.length} profile${list.length > 1 ? "s" : ""}` : ""}</span><span class="spacer"></span>
    <button class="icon-btn sm primary" data-a="new" title="A new profile: a look your films can be made in">${icon("plus")}New profile</button></div>`);
  head.querySelector('[data-a="new"]').onclick = () => newSheet();
  main.append(head);
  const dz = dropZone("Drop a brand book or a film to draft a profile");
  wireDrop(dz, draftNew);
  if (!list.length) {
    const e = h(`<div class="empty pf-empty"><b>No profiles yet</b><p>A profile is a look your films are made in: your company's own, or one you want to try. It keeps a palette, typefaces, its motion and your rules, and ${esc(SP.ai)} adds what it learns on every film.</p><p>Without one, a brief copies its reference as it is.</p>
      <div class="pf-empty-acts">${SPLICED.brand ? `<button class="icon-btn sm primary" data-a="house" title="Make ${esc(SPLICED.brand)}'s profile from the project's brand and house rules">${icon("palette")}Make ${esc(SPLICED.brand)}'s profile</button>` : ""}<button class="icon-btn sm" data-a="new2" title="A new profile">${icon("plus")}New profile</button></div></div>`);
    e.querySelector('[data-a="new2"]').onclick = () => newSheet();
    const hb = e.querySelector('[data-a="house"]');
    if (hb) hb.onclick = async () => { try { const j = await post({ op: "house" }); location.hash = `#/profiles/${j.profile}`; } catch (err) { toast(err.message); } };
    main.append(e, dz);
    return;
  }
  const grid = h(`<div class="pf-grid"></div>`);
  for (const p of list) {
    const c = h(`<a class="pf-card" href="#/profiles/${esc(p.slug)}" title="Open ${esc(p.name)}">
      <div class="pf-cover"></div>
      <div class="pf-body"><div class="pf-t"><b>${esc(p.name)}</b>${p.slug === def ? `<span class="pf-badge on" title="Briefs start in this profile">${icon("check")}Default</span>` : ""}</div>
      ${p.about ? `<p>${esc(p.about)}</p>` : ""}
      <div class="pf-meta"><span class="pf-dots">${dots(p.palette, 6)}</span>${p.font ? `<span style="font-family:${esc(faceCss(p.font))}">${esc(p.font)}</span>` : ""}<span>${p.scenes.length} scene${p.scenes.length === 1 ? "" : "s"}</span><span>${p.rules.length} rule${p.rules.length === 1 ? "" : "s"}</span></div></div></a>`);
    if (p.font_source === "google") googleFace(p.font);
    const cover = c.querySelector(".pf-cover");
    if (p.scenes.length >= 3) { cover.classList.add("scenes"); cover.innerHTML = thumbs(p.scenes, 3); }
    else cover.append(stage(p));
    grid.append(c);
  }
  main.append(grid, dz);
  main.append(h(`<p class="pf-foot">Every brief you copy can choose a profile, or <b>No profile</b> to copy the reference as it is. Briefs start in the default.</p>`));
}

/* ---------- motion, seen ---------- */
const curveOf = (m) => `cubic-bezier(${baseOf(m).curve.join(",")})`;
const easeOf = (m) => { const b = val(m, "bounce"); return b > 0.01 ? `cubic-bezier(0.34, ${(1 + b * 2.4).toFixed(2)}, 0.64, 1)` : curveOf(m); };
/* A small picture of one setting, playing the value it has: pace races a dot against the base's, bounce lands a block,
   stagger brings in a row one by one, float bobs, scene change swaps two frames, words arrive their way. */
function knobView(k) {
  const el = h(`<span class="pf-kv" data-k="${k}" aria-hidden="true"></span>`);
  el.innerHTML = {
    pace: `<i class="ghost"></i><i class="dot"></i><b class="rail"></b>`,
    bounce: `<b class="floor"></b><i class="blk"></i>`,
    stagger: `<i></i><i></i><i></i><i></i>`,
    idle: `<i class="blk"></i>`,
    transition: `<i class="fa"></i><i class="fb"></i>`,
    text: `<em>Aa</em>`,
  }[k] || "";
  let t = 0, cur = null;
  el.play = (m) => {
    cur = m; clearTimeout(t);
    el.getAnimations({ subtree: true }).forEach((a) => a.cancel());
    const b = baseOf(m), pace = val(m, "pace"), dur = b.enter * 1000;
    const loop = (ms) => { t = setTimeout(() => el.isConnected && el.play(cur), ms); };
    if (k === "pace") {
      el.querySelector(".ghost").animate([{ transform: "translateX(0)" }, { transform: "translateX(46px)" }], { duration: dur, easing: curveOf(m), fill: "both" });
      el.querySelector(".dot").animate([{ transform: "translateX(0)" }, { transform: "translateX(46px)" }], { duration: dur * pace, easing: curveOf(m), fill: "both" });
      loop(dur * Math.max(1, pace) + 900);
    } else if (k === "bounce") {
      el.querySelector(".blk").animate([{ transform: "translateY(-16px)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: dur * pace, easing: easeOf(m), fill: "both" });
      loop(dur * pace + 1000);
    } else if (k === "stagger") {
      const st = val(m, "stagger") * 1000;
      [...el.children].forEach((c, i) => c.animate([{ transform: "translateY(8px)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 380 * pace, delay: i * st, easing: curveOf(m), fill: "both" }));
      loop(3 * st + 380 * pace + 900);
    } else if (k === "idle") {
      const a = val(m, "idle");
      el.querySelector(".blk").animate([{ transform: "translateY(0)" }, { transform: `translateY(${-7 * a}px)` }, { transform: "translateY(0)" }], { duration: 1800, iterations: Infinity, easing: "ease-in-out" });
    } else if (k === "transition") {
      const tr = val(m, "transition"), d = tr === "cut" ? 1 : 450 * pace, A = el.querySelector(".fa"), B = el.querySelector(".fb");
      const out = { cut: [{ opacity: 1 }, { opacity: 0 }], blurThrough: [{ filter: "blur(0)", opacity: 1 }, { filter: "blur(4px)", opacity: 0 }], fadeThrough: [{ opacity: 1 }, { opacity: 0 }],
        sharedAxisX: [{ transform: "none", opacity: 1 }, { transform: "translateX(-14px)", opacity: 0 }], sharedAxisZ: [{ transform: "none", opacity: 1 }, { transform: "scale(1.2)", opacity: 0 }] }[tr];
      const inn = { cut: [{ opacity: 0 }, { opacity: 1 }], blurThrough: [{ filter: "blur(4px)", opacity: 0 }, { filter: "blur(0)", opacity: 1 }], fadeThrough: [{ opacity: 0 }, { opacity: 1 }],
        sharedAxisX: [{ transform: "translateX(14px)", opacity: 0 }, { transform: "none", opacity: 1 }], sharedAxisZ: [{ transform: "scale(0.8)", opacity: 0 }, { transform: "none", opacity: 1 }] }[tr];
      A.animate(out, { duration: d, delay: 600, fill: "both" });
      B.animate(inn, { duration: d, delay: 600 + (tr.endsWith("Through") ? d * 0.4 : 0), fill: "both", easing: curveOf(m) });
      loop(600 + d * 1.4 + 1100);
    } else if (k === "text") {
      const e = el.querySelector("em"), grey = val(m, "text") === "greyToInk";
      e.animate(grey ? [{ opacity: 0, color: "var(--subtle-foreground)" }, { opacity: 1, color: "var(--subtle-foreground)", offset: 0.4 }, { opacity: 1, color: "var(--foreground)" }]
        : [{ opacity: 0, filter: "blur(4px)", transform: "translateY(5px)" }, { opacity: 1, filter: "blur(0)", transform: "none" }], { duration: (grey ? 1200 : 600) * pace, easing: curveOf(m), fill: "both" });
      loop((grey ? 1200 : 600) * pace + 1100);
    }
  };
  return el;
}

/* ---------- one profile ---------- */
function detail(main, slug) {
  let p = get(slug);
  main.innerHTML = "";
  if (!p) { main.append(h(`<div class="empty">No profile called ${esc(slug)}. <a href="#/profiles">All profiles</a></div>`)); return; }
  const timers = {};
  const later = (k, fn, ms = 450) => { clearTimeout(timers[k]); timers[k] = setTimeout(fn, ms); };
  const save = (patch, msg) => post({ op: "set", profile: slug, ...patch }).then(() => { p = get(slug); msg && toast(msg); }).catch((e) => toast(e.message));
  const isDef = p.slug === def;
  const head = h(`<div class="view-head"><h1><a class="crumb" href="#/profiles" title="All profiles">Profiles</a><span class="sep">/</span><span class="nm">${esc(p.name)}</span></h1><span class="spacer"></span>
    <label class="pf-switch" title="Briefs start in the default profile. Turn it off and briefs start with No profile, copying the reference as it is">
      <span>Default profile</span><button role="switch" aria-checked="${isDef}" aria-label="Default profile" class="${isDef ? "on" : ""}"><i></i></button></label>
    <button class="icon-btn sm" data-a="show" title="Copy the line that tells ${esc(SP.ai)} to read this profile">${icon("copy")}Copy for ${esc(SP.ai)}</button>
    <button class="icon-btn sm sq ghost" data-a="more" title="More: remove">${icon("ellipsis")}</button></div>`);
  main.append(head);
  const sw = head.querySelector('[role="switch"]');
  sw.onclick = async () => {
    const on = sw.getAttribute("aria-checked") !== "true";
    try { await post({ op: "default", profile: on ? slug : NONE }); sw.setAttribute("aria-checked", on); sw.classList.toggle("on", on); toast(on ? `Briefs start in ${p.name}` : "No default: briefs start with No profile"); } catch (e) { toast(e.message); }
  };
  head.querySelector('[data-a="show"]').onclick = () => CR.copy(`Read this profile before building a film in it: ${SP.cmd("profile", "show", slug)}`, `Copied: paste it to ${SP.ai}`);
  head.querySelector('[data-a="more"]').onclick = (e) => CR.menu(e.currentTarget, [{ value: "rm", danger: true, html: `${icon("trash-2")}<span class="lbl">Remove profile</span>` }], async () => {
    if (!(await ask({ title: `Remove ${p.name}?`, text: "Briefs can't use it any more. Its folder is kept in .cache/profiles-removed/, so nothing is lost.", ok: "Remove", danger: true }))) return;
    try { await post({ op: "remove", profile: slug }); toast(`Removed ${p.name}`); location.hash = "#/profiles"; } catch (e2) { toast(e2.message); }
  });

  const page = h(`<div class="pf-page">
    <div class="pf-drafting" hidden></div>
    <section class="pf-hero"><div class="pf-hero-stage"></div>
      <div class="pf-hero-side">
        <input class="pf-name" data-k="name" value="${esc(p.name)}" title="The profile's name" aria-label="Name">
        <input class="pf-about" data-k="about" value="${esc(p.about)}" placeholder="One line: what this look is" title="One line about this look" aria-label="About">
        <div class="pf-block"><div class="pf-lab"><span>Palette</span><span class="pf-acts"></span></div><div class="pf-found-pal"></div><div class="pf-pal"></div></div>
        <div class="pf-block"><div class="pf-lab"><span>Typefaces</span></div><div class="pf-faces"></div><div class="pf-found-type"></div></div>
      </div></section>
    <form class="pf-askbar" title="Tell ${esc(SP.ai)} what to change in this profile, in your own words">${icon("message-square")}
      <input placeholder="Tell ${esc(SP.ai)} what to change: warmer colours, calmer motion, the logo never on white…" aria-label="Tell ${esc(SP.ai)} what to change">
      <button class="icon-btn sm primary" title="${esc(SP.Ai)} makes the change in this profile">Ask ${esc(SP.ai)}</button></form>
    <section class="pf-sec"><div class="pf-sec-h"><h3>Scenes that show the look</h3><button class="icon-btn sm" data-a="add-scenes" title="Choose scenes from the library that show this look">${icon("plus")}Add scenes</button></div>
      <p class="meta">A mood board ${esc(SP.ai)} looks at before building. Add from here, or from a scene's page (Shows the look of).</p><div class="pf-mood"></div></section>
    <section class="pf-sec"><div class="pf-sec-h"><h3>Motion</h3><span class="pf-mhead"></span></div>
      <p class="meta">Pick a motion, then change what this look does differently. The preview at the top plays it.</p>
      <div class="pf-starts"></div><div class="pf-motion"></div></section>
    <section class="pf-sec"><h3>In its own words</h3><p class="meta">The voice, the stage, what its films always do and never do. ${esc(SP.Ai)} reads this first. Saved as you type, in profiles/${esc(slug)}/PROFILE.md.</p>
      <textarea class="pf-md" data-k="md" rows="9" placeholder="Write it like a brief to a designer: what this look is, and what it never does" title="The profile in your own words" aria-label="In its own words">${esc(p.md)}</textarea></section>
    <section class="pf-sec"><h3>Rules learned</h3><p class="meta">What came up while making films: ${esc(SP.ai)} offers to keep a lasting preference here, and you can add your own.</p>
      <ol class="pf-rules"></ol>
      <div class="pf-add"><input placeholder="A rule, in a sentence: never bounce the logo" title="Add a rule to this profile" aria-label="New rule"><button class="icon-btn sm" data-a="learn" title="Keep this rule in the profile">Add rule</button></div></section>
    <section class="pf-sec"><div class="pf-sec-h"><h3>Drafted from</h3><button class="icon-btn sm" data-a="redraft" hidden title="Have ${esc(SP.ai)} read the sources again and fill the profile in">${icon("rotate-cw")}Draft again</button></div>
      <p class="meta">Drop a brand book, a logo, screenshots or a film here, or anywhere on this page. ${esc(SP.Ai)} reads them and fills the profile in.</p>
      <div class="pf-sources"></div></section>
  </div>`);
  main.append(page);
  const st = stage(p, { big: true });
  page.querySelector(".pf-hero-stage").append(st);
  const live = () => st.update(p);

  page.querySelectorAll("input[data-k], textarea[data-k]").forEach((el) => (el.oninput = () => {
    const k = el.dataset.k; p = { ...p, [k]: el.value };
    if (k === "name") head.querySelector(".nm").textContent = el.value || slug;
    if (["name", "about"].includes(k)) later("live", live, 250);
    later(k, () => save({ [k]: el.value }));
  }));

  // palette
  const pal = page.querySelector(".pf-pal"), palActs = page.querySelector(".pf-acts");
  const savePal = (next) => { p = { ...p, palette: next }; paintPal(); live(); later("palette", () => save({ palette: next })); };
  const paintPal = () => {
    pal.innerHTML = p.palette.map((c, i) => `<span class="pf-sw" style="--c:${esc(c.hex)}"><label title="Change this colour"><input type="color" value="${esc(c.hex.length === 4 ? "#" + [...c.hex.slice(1)].map((x) => x + x).join("") : c.hex.slice(0, 7))}" data-i="${i}" aria-label="Colour ${i + 1}"></label>
      <input class="pf-sw-n" data-n="${i}" value="${esc(c.name || "")}" placeholder="${esc(c.hex)}" title="This colour's name, ${esc(c.hex)}" aria-label="Name of colour ${i + 1}"><button data-x="${i}" title="Take this colour out">${icon("x")}</button></span>`).join("")
      + `<button class="pf-sw-add" title="Add a colour">${icon("plus")}</button>`;
    pal.querySelectorAll("input[type=color]").forEach((inp) => (inp.oninput = () => { const next = p.palette.map((c, i) => (i === +inp.dataset.i ? { ...c, hex: inp.value.toUpperCase() } : c)); p = { ...p, palette: next }; inp.closest(".pf-sw").style.setProperty("--c", inp.value); live(); later("palette", () => save({ palette: next })); }));
    pal.querySelectorAll("[data-n]").forEach((inp) => (inp.oninput = () => { const next = p.palette.map((c, i) => (i === +inp.dataset.n ? { ...c, name: inp.value } : c)); p = { ...p, palette: next }; later("palette", () => save({ palette: next })); }));
    pal.querySelectorAll("[data-x]").forEach((b) => (b.onclick = () => savePal(p.palette.filter((_, i) => i !== +b.dataset.x))));
    pal.querySelector(".pf-sw-add").onclick = () => savePal([...p.palette, { hex: p.palette.length ? roles(p.palette).accent : "#151517" }]);
    palActs.innerHTML = p.scenes.length ? `<button class="pf-link" data-a="from" title="Take the colours from this profile's scenes">From its scenes</button>` : "";
    const fb = palActs.querySelector('[data-a="from"]');
    if (fb) fb.onclick = () => { const next = paletteFrom(p.scenes); if (!next.length) return toast("Its scenes carry no colours yet"); savePal(next); toast("Palette taken from its scenes"); };
  };
  paintPal();

  // typefaces: headlines and text, each chosen from this Mac or Google Fonts
  const faces = page.querySelector(".pf-faces");
  const paintFaces = () => {
    const slot = (role, label, f, src) => `<button class="pf-face" data-role="${role}" title="Choose the ${label.toLowerCase()} typeface, from this Mac or Google Fonts">
      <span class="pf-aa" style="${f ? `font-family:${esc(faceCss(f))}` : ""}">Aa</span>
      <span class="pf-face-t"><small>${label}</small><b style="${f ? `font-family:${esc(faceCss(f))}` : ""}">${esc(f || (role === "text" ? "As headlines" : "Choose one"))}</b>
      <small>${f ? (src === "google" ? "Google Fonts" : "On this Mac") : ""}</small></span>${icon("chevron-down")}</button>`;
    faces.innerHTML = slot("font", "Headlines", p.font, p.font_source) + slot("text", "Text", p.text_font, p.text_font_source);
    [[p.font, p.font_source], [p.text_font, p.text_font_source]].forEach(([f, s]) => s === "google" && googleFace(f));
    faces.querySelectorAll(".pf-face").forEach((b) => (b.onclick = () => {
      const text = b.dataset.role === "text";
      fontPicker({ title: text ? "Typeface for text" : "Typeface for headlines", current: text ? p.text_font : p.font, source: text ? p.text_font_source : p.font_source,
        sample: text ? "The quick brown fox jumps over the lazy dog" : p.name, allowSame: text,
        onPick: (f, src) => {
          const patch = text ? { text_font: f, text_font_source: src } : { font: f, font_source: src };
          p = { ...p, ...patch }; paintFaces(); live(); save(patch, f ? `${text ? "Text" : "Headlines"} in ${f}` : "Text in the headline typeface");
        } });
    }));
  };
  paintFaces();

  // what its words already say: colours and typefaces, offered in one click while the profile has none
  const foundPal = page.querySelector(".pf-found-pal"), foundType = page.querySelector(".pf-found-type");
  const paintFound = async () => {
    const cols = (p.found?.palette || []).filter((c) => !p.palette.some((x) => x.hex === c.hex));
    const fresh = !p.palette.length || p.palette.every((c) => !c.name);   // an empty palette, or one with only unnamed swatches: replace it
    foundPal.innerHTML = cols.length ? `<div class="pf-suggest">${icon("sparkles")}<span>Its words name ${cols.length} colour${cols.length > 1 ? "s" : ""}${p.palette.length ? " not in the palette" : ""}</span><span class="pf-dots">${dots(cols, 8)}</span>
      <button class="icon-btn sm" data-a="use-pal" title="${fresh ? "Make these colours the palette" : "Add these colours to the palette"}">${fresh ? "Use them" : "Add them"}</button><button class="icon-btn sm sq ghost" data-a="no-pal" title="Not now">${icon("x")}</button></div>` : "";
    foundPal.querySelector('[data-a="use-pal"]')?.addEventListener("click", () => { savePal(fresh ? cols : [...p.palette, ...cols]); foundPal.innerHTML = ""; toast("Colours taken from its words"); });
    foundPal.querySelector('[data-a="no-pal"]')?.addEventListener("click", () => { foundPal.innerHTML = ""; });
    foundType.innerHTML = "";
    if (p.font || !p.md.trim()) return;
    const L = await fontLists(), names = new Map();
    for (const g of L.google || []) if (g[0].length > 3) names.set(g[0], "google");
    for (const f of L.installed) if (f.length > 3 && !names.has(f)) names.set(f, "local");
    const hits = [...names.keys()].map((n) => [n, p.md.search(new RegExp(`(^|[^\\w])${n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^\\w]|$)`))]).filter(([, i]) => i >= 0).sort((a, b) => a[1] - b[1]).map(([n]) => n).slice(0, 2);
    if (!hits.length || p.font) return;
    foundType.innerHTML = `<div class="pf-suggest">${icon("sparkles")}<span>Its words name ${hits.map(esc).join(" and ")}</span><button class="icon-btn sm" data-a="use-type" title="${hits.length > 1 ? `${esc(hits[0])} for headlines, ${esc(hits[1])} for text` : `${esc(hits[0])} for headlines`}">Use ${hits.length > 1 ? "them" : "it"}</button></div>`;
    foundType.querySelector('[data-a="use-type"]').onclick = () => {
      const patch = { font: hits[0], font_source: names.get(hits[0]), ...(hits[1] ? { text_font: hits[1], text_font_source: names.get(hits[1]) } : {}) };
      p = { ...p, ...patch }; paintFaces(); live(); save(patch, "Typefaces taken from its words"); foundType.innerHTML = "";
    };
  };
  paintFound();

  // the mood board
  const mood = page.querySelector(".pf-mood");
  function openPicker() { scenePicker(p, async (key, on) => { await post({ op: on ? "pin" : "unpin", profile: slug, scene: key }); p = get(slug); paintMood(); paintPal(); return p; }); }
  const paintMood = () => {
    mood.innerHTML = p.scenes.map((k) => { const s = CR.scene(k); return `<span class="pf-scene"><a href="#/scene/${esc(k)}" title="${esc(s?.title || k)}">${s ? `<img alt="" loading="lazy" src="${esc(CR.sceneThumb(s))}">` : `<span class="pf-gone">Not in the library</span>`}<small>${esc(s?.title || k)}</small></a><button class="icon-btn sm sq ghost" data-k="${esc(k)}" title="Take it out of this profile">${icon("x")}</button></span>`; }).join("")
      || `<button class="pf-mood-empty" title="Choose scenes from the library">${icon("plus")}<span>Add the scenes that show this look</span></button>`;
    mood.querySelectorAll(".pf-scene [data-k]").forEach((b) => (b.onclick = () => post({ op: "unpin", profile: slug, scene: b.dataset.k }).then(() => { p = get(slug); paintMood(); paintPal(); })));
    mood.querySelector(".pf-mood-empty")?.addEventListener("click", openPicker);
  };
  paintMood();
  page.querySelector('[data-a="add-scenes"]').onclick = openPicker;

  // motion: where it starts, what it changes, and a way back
  const startsEl = page.querySelector(".pf-starts"), mot = page.querySelector(".pf-motion"), mhead = page.querySelector(".pf-mhead");
  const own = (m) => Object.keys(KNOB).concat(Object.keys(CHOICE)).filter((k) => k in m);
  const startOf = (m) => starts.find((x) => x.slug === (m.from || m.base)) || { slug: m.base, name: m.base, base: m.base, kind: "kit" };
  const edited = (m) => { const s = startOf(m); return [...Object.keys(KNOB), ...Object.keys(CHOICE)].some((k) => (k in m ? m[k] : undefined) !== (k in s ? s[k] : undefined)) || s.base !== m.base; };
  const views = [];
  const playAll = () => views.forEach((v) => v.play(p.motion));
  const commit = (patch) => later("motion", () => save({ motion: patch }).then(paintHead), 350);
  const startFrom = (slugM) => { p = { ...p, motion: { ...(starts.find((x) => x.slug === slugM) || { base: slugM }), from: slugM } }; delete p.motion.name; delete p.motion.slug; delete p.motion.kind; delete p.motion.about;
    live(); save({ motion: { from: slugM } }).then(() => { paintStarts(); paintMotion(); paintHead(); }); };
  const paintHead = () => {
    const m = p.motion, s = startOf(m), ed = edited(m);
    mhead.innerHTML = ed ? `<span class="pf-edited">Changed from ${esc(s.name)}</span>
      ${s.kind === "saved" ? `<button class="icon-btn sm" data-a="keep" title="Keep these changes in the motion ${esc(s.name)}, for every profile that starts from it next">Save to ${esc(s.name)}</button>` : ""}
      <button class="icon-btn sm ghost" data-a="reset" title="Undo every change and go back to ${esc(s.name)}">${icon("rotate-cw")}Reset</button>` : "";
    mhead.querySelector('[data-a="reset"]')?.addEventListener("click", () => startFrom(s.slug));
    mhead.querySelector('[data-a="keep"]')?.addEventListener("click", async () => {
      try { await post({ op: "motion-save", profile: slug, name: s.name }); toast(`Saved to ${s.name}`); startFrom(s.slug); } catch (e) { toast(e.message); }
    });
  };
  const newMotion = async () => {
    const n = await ask({ title: "New motion", text: `It starts as this profile's motion as it is now. Tune it with the settings below, and any profile can use it.`, input: `${p.name} motion`, ok: "Create" });
    if (!n) return;
    try { await post({ op: "motion-save", profile: slug, name: n }); const key = starts.find((x) => x.name === n)?.slug; toast(`Made the motion ${n}`); if (key) startFrom(key); else paintStarts(); } catch (e) { toast(e.message); }
  };
  const paintStarts = () => {
    const cur = startOf(p.motion).slug;
    startsEl.innerHTML = starts.map((s) => `<button class="pf-sb ${s.slug === cur ? "on" : ""}" data-s="${esc(s.slug)}" title="${esc(s.about || `${s.name}: a motion of your own, on ${s.base}`)}">${esc(s.name)}${s.kind === "saved" ? `<span class="pf-sb-x" data-x="${esc(s.slug)}" title="Delete the motion ${esc(s.name)}">${icon("x")}</span>` : ""}</button>`).join("")
      + `<button class="pf-sb pf-sb-new" data-a="new-motion" title="Make a motion of your own, starting from this one">${icon("plus")}New</button>`;
    startsEl.querySelector('[data-a="new-motion"]').onclick = newMotion;
    startsEl.querySelectorAll("[data-s]").forEach((b) => (b.onclick = async (e) => {
      const s = starts.find((x) => x.slug === b.dataset.s);
      if (e.target.closest("[data-x]")) {
        if (await ask({ title: `Delete the motion ${s.name}?`, text: "Profiles that use it keep their motion as it is.", ok: "Delete", danger: true })) post({ op: "motion-remove", motion: s.slug }).then(paintStarts).catch((er) => toast(er.message));
        return;
      }
      if (s.slug === cur && !edited(p.motion)) return;
      if (edited(p.motion) && !(await ask({ title: `Switch to ${s.name}?`, text: "This profile's changes to its motion go.", ok: "Switch" }))) return;
      startFrom(s.slug);
    }));
  };
  const paintMotion = () => {
    const m = p.motion, b = baseOf(m);
    views.length = 0;
    mot.innerHTML = "";
    const rows = [...Object.entries(KNOB).map(([k, d]) => [k, d, "range"]), ...Object.entries(CHOICE).map(([k, d]) => [k, d, "choice"])];
    for (const [k, d, kind] of rows) {
      const v = val(m, k), mine = k in m;
      const row = h(`<div class="pf-mrow"><span class="pf-ml"><span class="pf-kv-slot"></span><span><b>${d.label}</b><small>${esc(d.tip)}</small></span></span>
        ${kind === "range" ? `<input type="range" data-knob="${k}" min="${d.min}" max="${d.max}" step="${d.step}" value="${v}" title="${esc(d.tip)}" aria-label="${d.label}" class="${mine ? "own" : ""}">`
          : `<div class="seg" data-choice="${k}">${d.opts.map(([o, t]) => `<button data-v="${o}" class="${v === o ? "on" : ""}" title="${o === b[k] ? "What the base does" : esc(d.tip)}">${t}</button>`).join("")}</div>`}
        <span class="pf-mv"><span class="pf-mv-t">${kind === "range" ? esc(d.show(+v)) : mine ? "changed" : "as the base"}</span>${mine ? `<button class="pf-reset" data-reset="${k}" title="Back to what the base does">reset</button>` : ""}</span></div>`);
      const kv = knobView(k); row.querySelector(".pf-kv-slot").append(kv); views.push(kv);
      row.addEventListener("mouseenter", () => kv.play(p.motion));
      mot.append(row);
    }
    mot.querySelectorAll("[data-knob]").forEach((r) => (r.oninput = () => {
      const k = r.dataset.knob; r.classList.add("own"); r.closest(".pf-mrow").querySelector(".pf-mv-t").textContent = KNOB[k].show(+r.value);
      p = { ...p, motion: { ...p.motion, [k]: +r.value } }; live(); views.find((v) => v.dataset.k === k)?.play(p.motion); commit({ [k]: +r.value });
    }));
    mot.querySelectorAll("[data-choice] button").forEach((x) => (x.onclick = () => {
      const k = x.parentElement.dataset.choice; x.parentElement.querySelectorAll("button").forEach((y) => y.classList.toggle("on", y === x));
      p = { ...p, motion: { ...p.motion, [k]: x.dataset.v } }; live(); views.find((v) => v.dataset.k === k)?.play(p.motion); commit({ [k]: x.dataset.v });
    }));
    mot.querySelectorAll("[data-reset]").forEach((x) => (x.onclick = () => {
      const k = x.dataset.reset, m2 = { ...p.motion }; delete m2[k]; p = { ...p, motion: m2 }; live();
      save({ motion: { [k]: "base" } }).then(() => { paintMotion(); paintHead(); });
    }));
    requestAnimationFrame(playAll);
  };
  paintStarts(); paintMotion(); paintHead();

  // rules
  const rules = page.querySelector(".pf-rules");
  const paintRules = () => {
    rules.innerHTML = p.rules.map((r, i) => `<li><span>${esc(r.text)}${r.from ? `<small>from ${esc(r.from)}</small>` : ""}</span><button class="icon-btn sm sq ghost" data-n="${i + 1}" title="Forget this rule">${icon("x")}</button></li>`).join("") || `<li class="pf-none">None yet.</li>`;
    rules.querySelectorAll("[data-n]").forEach((b) => (b.onclick = () => post({ op: "forget", profile: slug, n: +b.dataset.n }).then(() => { p = get(slug); paintRules(); }).catch((e) => toast(e.message))));
  };
  paintRules();
  const add = page.querySelector(".pf-add input"), learn = () => { const v = add.value.trim(); if (!v) return add.focus(); post({ op: "learn", profile: slug, text: v, from: "the person" }).then(() => { p = get(slug); add.value = ""; paintRules(); }).catch((e) => toast(e.message)); };
  page.querySelector('[data-a="learn"]').onclick = learn;
  add.onkeydown = (e) => { if (e.key === "Enter") learn(); };

  // drafted from: the sources, and the reading of them by the person's AI
  const srcEl = page.querySelector(".pf-sources"), banner = page.querySelector(".pf-drafting"), redraft = page.querySelector('[data-a="redraft"]');
  const kindIcon = { video: "film", image: "image", document: "file-text" };
  const paintSources = () => {
    srcEl.innerHTML = `<div class="pf-src-list">${p.sources.map((x) => `<span class="pf-src">${x.kind === "image" && !/\.svg$/i.test(x.name) ? `<img alt="" src="${esc(SP.fileUrl(x.file))}">` : `<span class="pf-src-i">${icon(kindIcon[x.kind] || "file-text")}</span>`}<small title="${esc(x.file)}">${esc(x.name)}</small></span>`).join("")}</div>`;
    const dz = dropZone(p.sources.length ? "Add more" : "Drop files to draft this profile"); dz.classList.add("small");
    wireDrop(dz, addFiles); srcEl.append(dz);
    redraft.hidden = !p.sources.length;
  };
  const addFiles = async (files) => {
    files = [...files]; if (!files.length) return;
    toast(`Adding ${files.length} file${files.length > 1 ? "s" : ""}…`);
    const n = await sendSources(slug, files);
    if (!n) return;
    await post({ op: "draft", profile: slug }).catch((e) => toast(e.message));
    await load(); p = get(slug); paintSources(); watch();
    window.Imports?.refresh?.();
  };
  redraft.onclick = async () => { try { await post({ op: "draft", profile: slug }); toast(`${SP.Ai} will read the sources again`); watch(); window.Imports?.refresh?.(); } catch (e) { toast(e.message); } };
  dropTarget = addFiles;
  document.body.dataset.dropProfile = p.name;
  let watchT = 0;
  const watch = async () => {
    clearTimeout(watchT);
    if (!page.isConnected) return;
    const j = await jobFor(slug);
    const run = j && ["queued", "running"].includes(j.status), wait = j && j.status === "waiting";
    banner.hidden = !(run || wait);
    if (run) banner.innerHTML = `<span class="dk-load"><img class="on-dark" src="brand/splice-loader-white.svg" alt=""><img class="on-light" src="brand/splice-loader-black.svg" alt=""></span><span><b>${esc(SP.Ai)} is ${j.request ? "changing" : "drafting"} this profile</b><small>${esc(j.request ? `“${j.request.split("\n").pop()}”` : j.activity || "Reading the sources")}</small></span>`;
    else if (wait) { banner.innerHTML = `${icon("info")}<span><b>${j.request ? "Your request is" : "The sources are"} waiting for ${esc(SP.ai)}</b><small>${j.request ? `“${esc(j.request.split("\n").pop())}”. ` : ""}Paste the line to ${esc(SP.ai)} and it picks it up.</small></span><button class="icon-btn sm" data-a="pickup" title="Copy the line that tells ${esc(SP.ai)} to draft this profile">${icon("copy")}Copy for ${esc(SP.ai)}</button>`;
      banner.querySelector('[data-a="pickup"]').onclick = () => CR.copy(`Run \`${SP.cmd("imports", "next")}\` and do what it prints.`, `Copied: paste it to ${SP.ai}`); }
    if (run || wait) watchT = setTimeout(watch, run ? 3000 : 15000);
    else if (j && j.status === "done" && banner.dataset.was === "run") { await load(); detail(main, slug); toast(`${p.name} is updated`); return; }
    banner.dataset.was = run ? "run" : wait ? "wait" : "";
  };
  const askbar = page.querySelector(".pf-askbar");
  askbar.onsubmit = async (e) => {
    e.preventDefault();
    const inp = askbar.querySelector("input"), v = inp.value.trim();
    if (!v) return inp.focus();
    try { await post({ op: "draft", profile: slug, request: v }); inp.value = ""; toast(`Sent to ${SP.ai}`); watch(); window.Imports?.refresh?.(); } catch (er) { toast(er.message); }
  };
  paintSources(); watch();
}

/* A sheet of library scenes to add to a profile: search, closest to its palette first, click to add or take out. */
function scenePicker(p, toggle) {
  const scrim = h(`<div class="pf-scrim"><div class="pf-sheet" role="dialog" aria-label="Add scenes to ${esc(p.name)}">
    <div class="pf-sheet-h"><b>Scenes that show ${esc(p.name)}</b><input type="search" placeholder="Search the library" aria-label="Search the library" title="Search titles, films and how scenes move"><button class="icon-btn sm primary" data-a="done" title="Done (Esc)">Done</button></div>
    <p class="meta">${p.palette.length ? "Closest to its palette first." : "Add a palette and the closest scenes come first."} Click a scene to add it; click again to take it out.</p>
    <div class="pf-pick-grid"></div></div></div>`);
  document.body.append(scrim);
  const grid = scrim.querySelector(".pf-pick-grid"), q = scrim.querySelector("input");
  const order = CR.scenes().map((s) => [s, closeness(s, p.palette)]).sort((a, b) => a[1] - b[1]).map(([s]) => s);
  const paint = () => {
    const words = q.value.toLowerCase().split(/\s+/).filter(Boolean);
    const hits = order.filter((s) => words.every((w) => (s.text || s.title.toLowerCase()).includes(w))).slice(0, 80);
    grid.innerHTML = hits.map((s) => `<button class="pf-pick ${p.scenes.includes(s.key) ? "on" : ""}" data-k="${esc(s.key)}" title="${esc(s.title)}"><img alt="" loading="lazy" src="${esc(CR.sceneThumb(s))}"><small>${esc(s.title)}</small><i>${icon("check")}</i></button>`).join("") || `<p class="meta">Nothing matches.</p>`;
    grid.querySelectorAll(".pf-pick").forEach((b) => (b.onclick = async () => { const on = !b.classList.contains("on"); b.classList.toggle("on", on); try { p = await toggle(b.dataset.k, on); } catch (e) { b.classList.toggle("on", !on); toast(e.message); } }));
  };
  const close = () => { scrim.remove(); document.removeEventListener("keydown", esc_); };
  const esc_ = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", esc_);
  scrim.addEventListener("mousedown", (e) => { if (e.target === scrim) close(); });
  scrim.querySelector('[data-a="done"]').onclick = close;
  q.oninput = paint; paint(); q.focus();
}

return { ready, load, get, resolve, name, line, pick, splitCopy, briefFor, pinRow, render, create, drop, googleFace, remembered, remember, NONE, all: () => list, default: () => def, onChange: (fn) => listeners.add(fn) };
})();
