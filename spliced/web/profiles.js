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
let list = [], def = "", motion = {}, knobs = {}, kit = {};
const listeners = new Set();

async function load() {
  try {
    const j = await (await fetch("/api/profiles", { cache: "no-store" })).json();
    list = j.profiles || []; def = j.default || ""; motion = j.motion || {}; knobs = j.knobs || {}; kit = j.kit || {};
  } catch {}
  listeners.forEach((fn) => fn());
  return list;
}
const ready = load();
async function post(body) {
  const r = await fetch("/api/profiles", { method: "POST", body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Couldn't save it");
  list = j.profiles || list; def = j.default ?? def;
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

/* ---------- the list ---------- */
const thumbs = (keys, n) => keys.slice(0, n).map((k) => { const s = CR.scene(k); return s ? `<img alt="" loading="lazy" src="${esc(CR.sceneThumb(s))}">` : ""; }).join("");

async function create(from) {
  const n = prompt(from ? "Name the profile (a look to explore, started from this film)" : "Name the new profile: your company, or a look you want to try", from ? `${from.title} look` : "");
  if (!n || !n.trim()) return;
  try {
    const j = await post({ op: "new", name: n.trim(), from_film: from?.slug });
    toast(`Made the profile ${n.trim()}`); location.hash = `#/profiles/${j.profile}`;
  } catch (e) { toast(e.message); }
}

async function render(main, slug) {
  main.innerHTML = `<div class="empty">Loading profiles…</div>`;
  await load();
  if (slug) return detail(main, slug);
  main.innerHTML = "";
  const head = h(`<div class="view-head"><h1>Profiles</h1><span class="meta">${list.length ? `${list.length} profile${list.length > 1 ? "s" : ""}` : ""}</span><span class="spacer"></span>
    <button class="icon-btn sm primary" data-a="new" title="A new profile: a look your films can be made in">${icon("plus")}New profile</button></div>`);
  head.querySelector('[data-a="new"]').onclick = () => create();
  main.append(head);
  if (!list.length) {
    const e = h(`<div class="empty pf-empty"><b>No profiles yet</b><p>A profile is a look your films are made in: your company's own, or one you want to try. It keeps a palette, a typeface, its motion and your rules, and ${esc(SP.ai)} adds what it learns on every film.</p><p>Without one, a brief copies its reference as it is.</p>
      <div class="pf-empty-acts">${SPLICED.brand ? `<button class="icon-btn sm primary" data-a="house" title="Make ${esc(SPLICED.brand)}'s profile from the project's brand and house rules">${icon("palette")}Make ${esc(SPLICED.brand)}'s profile</button>` : ""}<button class="icon-btn sm" data-a="new2" title="A new profile">${icon("plus")}New profile</button></div></div>`);
    e.querySelector('[data-a="new2"]').onclick = () => create();
    const hb = e.querySelector('[data-a="house"]');
    if (hb) hb.onclick = async () => { try { const j = await post({ op: "house" }); location.hash = `#/profiles/${j.profile}`; } catch (err) { toast(err.message); } };
    main.append(e);
    return;
  }
  const grid = h(`<div class="pf-grid"></div>`);
  for (const p of list) {
    const c = h(`<a class="pf-card" href="#/profiles/${esc(p.slug)}" title="Open ${esc(p.name)}">
      <div class="pf-cover"></div>
      <div class="pf-body"><div class="pf-t"><b>${esc(p.name)}</b>${p.slug === def ? `<span class="pf-badge on" title="Briefs start in this profile">${icon("check")}Default</span>` : ""}</div>
      ${p.about ? `<p>${esc(p.about)}</p>` : ""}
      <div class="pf-meta"><span class="pf-dots">${dots(p.palette, 6)}</span><span>${esc(p.motion.base)}</span><span>${p.scenes.length} scene${p.scenes.length === 1 ? "" : "s"}</span><span>${p.rules.length} rule${p.rules.length === 1 ? "" : "s"}</span></div></div></a>`);
    const cover = c.querySelector(".pf-cover");
    if (p.scenes.length >= 3) { cover.classList.add("scenes"); cover.innerHTML = thumbs(p.scenes, 3); }
    else cover.append(stage(p));
    grid.append(c);
  }
  main.append(grid);
  main.append(h(`<p class="pf-foot">Every brief you copy can choose a profile, or <b>No profile</b> to copy the reference as it is. Briefs start in the default.</p>`));
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
    if (!confirm(`Remove the profile ${p.name}? Its folder is kept in .cache/profiles-removed/.`)) return;
    try { await post({ op: "remove", profile: slug }); toast(`Removed ${p.name}`); location.hash = "#/profiles"; } catch (e2) { toast(e2.message); }
  });

  const page = h(`<div class="pf-page">
    <section class="pf-hero"><div class="pf-hero-stage"></div>
      <div class="pf-hero-side">
        <input class="pf-name" data-k="name" value="${esc(p.name)}" title="The profile's name" aria-label="Name">
        <input class="pf-about" data-k="about" value="${esc(p.about)}" placeholder="One line: what this look is" title="One line about this look" aria-label="About">
        <div class="pf-block"><div class="pf-lab"><span>Palette</span><span class="pf-acts"></span></div><div class="pf-pal"></div></div>
        <div class="pf-block"><div class="pf-lab"><span>Typeface</span></div>
          <div class="pf-type"><span class="pf-aa">Aa</span><div><input data-k="font" value="${esc(p.font)}" placeholder="A typeface, e.g. Inter" title="The typeface's name. The preview uses it when it is installed on this Mac" aria-label="Typeface">
          <input data-k="type" value="${esc(p.type)}" placeholder="How it is set: weights, size, case, tracking" title="How the type is set" aria-label="How the type is set"></div></div></div>
      </div></section>
    <section class="pf-sec"><div class="pf-sec-h"><h3>Scenes that show the look</h3><button class="icon-btn sm" data-a="add-scenes" title="Choose scenes from the library that show this look">${icon("plus")}Add scenes</button></div>
      <p class="meta">A mood board ${esc(SP.ai)} looks at before building. Add from here, or from a scene's page (Shows the look of).</p><div class="pf-mood"></div></section>
    <section class="pf-sec"><div class="pf-sec-h"><h3>Motion</h3></div>
      <p class="meta">A base ${SP.term("motion profile")}, and what this look changes about it. The preview above plays it. Anything left alone follows the base.</p><div class="pf-motion"></div></section>
    <section class="pf-sec"><h3>In its own words</h3><p class="meta">The voice, the stage, what its films always do and never do. ${esc(SP.Ai)} reads this first. Saved as you type, in profiles/${esc(slug)}/PROFILE.md.</p>
      <textarea class="pf-md" data-k="md" rows="9" placeholder="Write it like a brief to a designer: what this look is, and what it never does" title="The profile in your own words" aria-label="In its own words">${esc(p.md)}</textarea></section>
    <section class="pf-sec"><h3>Rules learned</h3><p class="meta">What came up while making films: ${esc(SP.ai)} offers to keep a lasting preference here, and you can add your own.</p>
      <ol class="pf-rules"></ol>
      <div class="pf-add"><input placeholder="A rule, in a sentence: never bounce the logo" title="Add a rule to this profile" aria-label="New rule"><button class="icon-btn sm" data-a="learn" title="Keep this rule in the profile">Add rule</button></div></section>
  </div>`);
  main.append(page);
  const st = stage(p, { big: true });
  page.querySelector(".pf-hero-stage").append(st);
  const live = () => st.update(p);

  // text fields: saved as typed; the name, about and typeface also change the preview
  page.querySelectorAll("input[data-k], textarea[data-k]").forEach((el) => (el.oninput = () => {
    const k = el.dataset.k; p = { ...p, [k]: el.value };
    if (k === "name") head.querySelector(".nm").textContent = el.value || slug;
    if (k === "font") page.querySelector(".pf-aa").style.fontFamily = el.value ? `"${el.value}", Inter` : "";
    if (["name", "about", "font"].includes(k)) later("live", live, 250);
    later(k, () => save({ [k]: el.value }));
  }));
  page.querySelector(".pf-aa").style.fontFamily = p.font ? `"${p.font}", Inter` : "";

  // palette: swatches to click and change, add, take out, or take from the scenes
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

  // motion
  const mot = page.querySelector(".pf-motion");
  const setMotion = (k, v) => { const m = { ...p.motion }; if (v === null) delete m[k]; else m[k] = v; p = { ...p, motion: m }; live(); later(`motion.${k}`, () => save({ motion: { [k]: v === null ? "base" : v } }), 350); };
  const paintMotion = () => {
    const m = p.motion, b = baseOf(m);
    mot.innerHTML = `<div class="pf-mrow"><span class="pf-ml" title="The motion profile this look starts from">Base</span><div class="seg" data-base>${Object.keys(motion).map((x) => `<button data-v="${esc(x)}" class="${m.base === x ? "on" : ""}" title="${esc(motion[x])}">${esc(x)}</button>`).join("")}</div><span class="pf-mv">${esc(motion[m.base] || "")}</span></div>`
      + Object.entries(KNOB).map(([k, d]) => { const v = val(m, k), own = k in m;
        return `<div class="pf-mrow"><span class="pf-ml" title="${esc(d.tip)}">${d.label}</span><input type="range" data-knob="${k}" min="${d.min}" max="${d.max}" step="${d.step}" value="${v}" title="${esc(d.tip)}" aria-label="${d.label}" class="${own ? "own" : ""}">
          <span class="pf-mv">${esc(d.show(+v))}${own ? `<button class="pf-reset" data-reset="${k}" title="Back to the base's own (${esc(d.show(+b[k]))})">reset</button>` : ""}</span></div>`; }).join("")
      + Object.entries(CHOICE).map(([k, d]) => { const v = val(m, k), own = k in m;
        return `<div class="pf-mrow"><span class="pf-ml" title="${esc(d.tip)}">${d.label}</span><div class="seg" data-choice="${k}">${d.opts.map(([o, t]) => `<button data-v="${o}" class="${v === o ? "on" : ""}" title="${o === b[k] ? "The base's own" : esc(d.tip)}">${t}</button>`).join("")}</div>
          <span class="pf-mv">${own ? `<button class="pf-reset" data-reset="${k}" title="Back to the base's own">reset</button>` : "as the base"}</span></div>`; }).join("");
    mot.querySelectorAll("[data-base] button").forEach((x) => (x.onclick = () => { p = { ...p, motion: { ...p.motion, base: x.dataset.v } }; live(); save({ motion: { base: x.dataset.v } }).then(paintMotion); }));
    mot.querySelectorAll("[data-knob]").forEach((r) => (r.oninput = () => { const k = r.dataset.knob; r.classList.add("own"); r.parentElement.querySelector(".pf-mv").firstChild.textContent = KNOB[k].show(+r.value); setMotion(k, +r.value); }));
    mot.querySelectorAll("[data-choice] button").forEach((x) => (x.onclick = () => { const k = x.parentElement.dataset.choice; setMotion(k, x.dataset.v); x.parentElement.querySelectorAll("button").forEach((y) => y.classList.toggle("on", y === x)); }));
    mot.querySelectorAll("[data-reset]").forEach((x) => (x.onclick = () => { setMotion(x.dataset.reset, null); paintMotion(); }));
  };
  paintMotion();

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

return { ready, load, get, resolve, name, line, pick, splitCopy, briefFor, pinRow, render, create, remembered, remember, NONE, all: () => list, default: () => def, onChange: (fn) => listeners.add(fn) };
})();
