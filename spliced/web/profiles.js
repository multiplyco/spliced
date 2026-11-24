/* Profiles (#/profiles): the looks the project's films are made in. A house look (a company's own brand, type and
   product) or a look to explore; each with its motion profile, palette, type, its own words (PROFILE.md) and the rules
   learned while making films. One is the default. Every copy of a brief can choose another, or none: then the
   reference is recreated as it is, in its own look.

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
let list = [], def = "", motion = {};
const listeners = new Set();

async function load() {
  try {
    const j = await (await fetch("/api/profiles", { cache: "no-store" })).json();
    list = j.profiles || []; def = j.default || ""; motion = j.motion || {};
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
  return `Profile: ${p.name}. Make it in this profile: read \`${SP.cmd("profile", "show", r)}\` first. Its look, its rules and its motion profile (\`${p.motion}\`) win over the kit's defaults${p.kind === "house" ? "; its real UI and logo are rebuilt from its own sources" : ""}. Recreate the referenced ${many ? "scenes'" : "scene's"} choreography inside it: borrow the move, not the reference's look.`;
}

const remembered = (ctx, fallback) => localStorage.getItem(`cr.profileFor.${ctx}`) ?? fallback;
const remember = (ctx, v) => localStorage.setItem(`cr.profileFor.${ctx}`, v);

/** A menu of the choices: every profile, then none; the current one ticked. */
function pick(anchor, current, onPick) {
  const r = resolve(current);
  CR.menu(anchor, [
    ...list.map((p) => ({ value: p.slug, on: r === p.slug, html: `<span class="lbl">${esc(p.name)}</span><span class="c">${p.slug === def ? "default" : p.kind === "house" ? "house" : "exploration"}</span>` })),
    { value: NONE, sep: list.length > 0, on: r === NONE, html: `<span class="lbl">No profile</span><span class="c">as the reference</span>` },
    { value: "__manage", sep: true, html: `${icon("palette")}<span class="lbl">${list.length ? "Manage profiles" : "Make a profile"}</span>` },
  ], (v) => { if (v === "__manage") location.hash = "#/profiles"; else onPick(v); });
}

/** A copy button with the profile it copies for beside it: the first part copies, the second picks another profile.
    make(choice) gives the text; ctx remembers the choice per kind of brief; fallback is the first choice ("" = default). */
function splitCopy({ ctx, fallback = "", text, title, make, msg }) {
  const el = h(`<span class="pf-split"><button class="icon-btn sm primary" data-a="copy" title="${esc(title)}">${icon("copy")}${esc(text)}</button><button class="pf-for" data-a="for"></button></span>`);
  const paint = () => { const v = remembered(ctx, fallback), b = el.querySelector('[data-a="for"]'); b.innerHTML = `${esc(name(v))}${icon("chevron-down")}`; b.title = `Copied for: ${name(v)}. Choose another profile, or none to recreate it as it is`; };
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
      return `<button class="pf-chip ${on ? "on" : ""}" data-p="${esc(p.slug)}" title="${on ? `Take it out of ${esc(p.name)}` : `Pin it to ${esc(p.name)}: a scene that shows the look, which ${esc(SP.ai)} reads before building in it`}">${on ? icon("check") : icon("plus")}${esc(p.name)}</button>`; }).join("");
    el.querySelectorAll(".pf-chip").forEach((b) => (b.onclick = async () => {
      const p = get(b.dataset.p), on = p.scenes.includes(key);
      try { await post({ op: on ? "unpin" : "pin", profile: p.slug, scene: key }); toast(on ? `Taken out of ${p.name}` : `Pinned to ${p.name}`); paint(); } catch (e) { toast(e.message); }
    }));
  };
  ready.then(paint);
  return el;
}

/* ---------- the view ---------- */
const swatches = (pal) => (pal || []).map((c) => `<span class="sw" title="${esc(c.hex)}"><i style="background:${esc(c.hex)}"></i>${esc(c.name || c.hex)}</span>`).join("");
const thumbs = (keys, n) => keys.slice(0, n).map((k) => { const s = CR.scene(k); return s ? `<img alt="" loading="lazy" src="${esc(CR.sceneThumb(s))}">` : ""; }).join("");

async function create(from) {
  const n = prompt(from ? "Name the profile (a look to explore, started from this film)" : "Name the new profile, for example your company, or a look you want to try", from ? `${from.title} look` : "");
  if (!n || !n.trim()) return;
  try {
    const j = await post({ op: "new", name: n.trim(), kind: from ? "exploration" : "exploration", from_film: from?.slug });
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
    const e = h(`<div class="empty pf-empty"><b>No profiles yet</b><p>A profile is a look your films are made in: your company's own, or one you want to explore. It keeps its palette, type, motion and your rules, and ${esc(SP.ai)} adds what it learns on every film.</p><p>Without one, a film recreates its references as they are.</p>
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
      <div class="pf-thumbs">${thumbs(p.scenes, 3) || `<span class="pf-noscene">${(p.palette || []).slice(0, 5).map((x) => `<i style="background:${esc(x.hex)}"></i>`).join("")}</span>`}</div>
      <div class="pf-body"><div class="pf-t"><b>${esc(p.name)}</b>${p.slug === def ? `<span class="pf-badge on">Default</span>` : ""}<span class="pf-badge">${p.kind === "house" ? "House" : "Exploration"}</span></div>
      ${p.about ? `<p>${esc(p.about)}</p>` : ""}
      <div class="pf-meta"><span>motion ${esc(p.motion)}</span><span>${p.rules.length} rule${p.rules.length === 1 ? "" : "s"}</span><span>${p.scenes.length} scene${p.scenes.length === 1 ? "" : "s"}</span></div></div></a>`);
    grid.append(c);
  }
  main.append(grid);
  main.append(h(`<p class="pf-foot">Every brief you copy can choose a profile, or <b>No profile</b> to recreate the reference as it is. The default is used when you don't choose.</p>`));
}

function detail(main, slug) {
  const p = get(slug);
  main.innerHTML = "";
  if (!p) { main.append(h(`<div class="empty">No profile called ${esc(slug)}. <a href="#/profiles">All profiles</a></div>`)); return; }
  const save = (patch, msg) => post({ op: "set", profile: slug, ...patch }).then(() => msg && toast(msg)).catch((e) => toast(e.message));
  let timers = {};
  const later = (k, fn) => { clearTimeout(timers[k]); timers[k] = setTimeout(fn, 500); };
  const head = h(`<div class="view-head"><h1><a class="crumb" href="#/profiles" title="All profiles">Profiles</a><span class="sep">/</span><span class="nm">${esc(p.name)}</span></h1>
    <span class="meta">${p.slug === def ? "The default" : ""}</span><span class="spacer"></span>
    ${p.slug === def ? `<button class="icon-btn sm ghost" data-a="undef" title="Have no default: a brief that names no profile recreates its reference as it is">Not the default</button>` : `<button class="icon-btn sm" data-a="def" title="Make it the default: a brief that names no profile is made in it">Make default</button>`}
    <button class="icon-btn sm" data-a="show" title="Copy the command ${esc(SP.ai)} runs to read this profile">${icon("copy")}Copy for ${esc(SP.ai)}</button>
    <button class="icon-btn sm sq ghost" data-a="more" title="More: remove">${icon("ellipsis")}</button></div>`);
  main.append(head);
  const d = head.querySelector('[data-a="def"]'), u = head.querySelector('[data-a="undef"]');
  if (d) d.onclick = () => post({ op: "default", profile: slug }).then(() => { toast(`${p.name} is the default`); detail(main, slug); });
  if (u) u.onclick = () => post({ op: "default", profile: NONE }).then(() => { toast("No default profile"); detail(main, slug); });
  head.querySelector('[data-a="show"]').onclick = () => CR.copy(`Read this profile before building a film in it: ${SP.cmd("profile", "show", slug)}`, `Copied: paste it to ${SP.ai}`);
  head.querySelector('[data-a="more"]').onclick = (e) => CR.menu(e.currentTarget, [{ value: "rm", danger: true, html: `${icon("trash-2")}<span class="lbl">Remove profile</span>` }], async () => {
    if (!confirm(`Remove the profile ${p.name}? Its folder is kept in .cache/profiles-removed/.`)) return;
    try { await post({ op: "remove", profile: slug }); toast(`Removed ${p.name}`); location.hash = "#/profiles"; } catch (e2) { toast(e2.message); }
  });

  const pal = p.palette.map((c) => `${c.hex}${c.name ? " " + c.name : ""}`).join(", ");
  const page = h(`<div class="pf-page">
    <div class="pf-fields">
      <label><span>Name</span><input data-k="name" value="${esc(p.name)}" title="What the app and ${esc(SP.ai)} call it"></label>
      <label><span>Kind</span><div class="seg" data-k="kind">${[["house", "House", "A company's own look: its real logo, UI and product"], ["exploration", "Exploration", "A look to try, with no company behind it"]].map(([v, t, tip]) => `<button data-v="${v}" class="${p.kind === v ? "on" : ""}" title="${esc(tip)}">${t}</button>`).join("")}</div></label>
      <label><span>${SP.term("motion profile", "Motion")}</span><div class="seg" data-k="motion">${Object.keys(motion).map((m) => `<button data-v="${esc(m)}" class="${p.motion === m ? "on" : ""}" title="${esc(motion[m])}">${esc(m)}</button>`).join("")}</div></label>
      <label class="wide"><span>About</span><input data-k="about" value="${esc(p.about)}" placeholder="One line: what this look is" title="One line about this look"></label>
      <label class="wide"><span>Palette</span><input data-k="palette" value="${esc(pal)}" placeholder="#0E3B43 deep teal, #FFB703 amber" title="Its colours: a hex code and a name, separated by commas"><div class="swatches">${swatches(p.palette)}</div></label>
      <label class="wide"><span>Type</span><input data-k="type" value="${esc(p.type)}" placeholder="Its typefaces and how they are set" title="Its typefaces and how they are set"></label>
    </div>
    <div class="pf-sec"><h3>In its own words</h3><p class="meta">The voice, the stage, the type, what its films always do and never do. ${esc(SP.Ai)} reads this first. Saved as you type, in profiles/${esc(slug)}/PROFILE.md.</p>
      <textarea class="pf-md" data-k="md" rows="10" placeholder="Write it like a brief to a designer: what this look is, and what it never does" title="The profile in your own words">${esc(p.md)}</textarea></div>
    <div class="pf-sec"><h3>Rules learned</h3><p class="meta">What came up while making films: ${esc(SP.ai)} offers to keep a lasting preference here, and you can add your own.</p>
      <ol class="pf-rules">${p.rules.map((r, i) => `<li><span>${esc(r.text)}${r.from ? `<small>from ${esc(r.from)}</small>` : ""}</span><button class="icon-btn sm sq ghost" data-n="${i + 1}" title="Forget this rule">${icon("x")}</button></li>`).join("")}</ol>
      <div class="pf-add"><input placeholder="A rule, in a sentence: never bounce the logo" title="Add a rule to this profile"><button class="icon-btn sm" data-a="learn" title="Keep this rule in the profile">Add rule</button></div></div>
    <div class="pf-sec"><h3>Scenes that show the look</h3><p class="meta">Pin a scene from its page in the Library (Shows the look of). ${esc(SP.Ai)} looks at these before building.</p>
      <div class="pf-scenes">${p.scenes.map((k) => { const s = CR.scene(k); return `<span class="pf-scene"><a href="#/scene/${esc(k)}" title="${esc(s?.title || k)}">${s ? `<img alt="" loading="lazy" src="${esc(CR.sceneThumb(s))}">` : ""}<small>${esc(s?.title || k)}</small></a><button class="icon-btn sm sq ghost" data-k="${esc(k)}" title="Take it out of this profile">${icon("x")}</button></span>`; }).join("") || `<span class="meta">None yet.</span>`}</div></div>
  </div>`);
  main.append(page);
  page.querySelectorAll("input[data-k], textarea[data-k]").forEach((el) => (el.oninput = () => later(el.dataset.k, () => save({ [el.dataset.k]: el.value }))));
  page.querySelector('input[data-k="palette"]').onchange = () => setTimeout(() => detail(main, slug), 600);
  page.querySelectorAll(".seg[data-k] button").forEach((b) => (b.onclick = () => { const k = b.parentElement.dataset.k; save({ [k]: b.dataset.v }).then(() => detail(main, slug)); }));
  page.querySelectorAll(".pf-rules [data-n]").forEach((b) => (b.onclick = () => post({ op: "forget", profile: slug, n: +b.dataset.n }).then(() => detail(main, slug)).catch((e) => toast(e.message))));
  const add = page.querySelector(".pf-add input"), learn = () => { const v = add.value.trim(); if (!v) return add.focus(); post({ op: "learn", profile: slug, text: v, from: "the person" }).then(() => detail(main, slug)).catch((e) => toast(e.message)); };
  page.querySelector('[data-a="learn"]').onclick = learn;
  add.onkeydown = (e) => { if (e.key === "Enter") learn(); };
  page.querySelectorAll(".pf-scene [data-k]").forEach((b) => (b.onclick = () => post({ op: "unpin", profile: slug, scene: b.dataset.k }).then(() => detail(main, slug))));
}

return { ready, load, get, resolve, name, line, pick, splitCopy, briefFor, pinRow, render, create, remembered, remember, NONE, all: () => list, default: () => def, onChange: (fn) => listeners.add(fn) };
})();
