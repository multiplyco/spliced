/* Tooltips and the glossary: how the app explains itself.

   Tooltips. Every `title="..."` in the app is shown by one tooltip of our own, with no change where it is
   written: when the pointer or the keyboard reaches an element with a title, the title moves to data-tip (so
   the browser's slow grey one never shows) and ours appears. The first one waits a moment; while you move
   from control to control the next ones are instant. An icon-only control keeps its title as its accessible name.

   The glossary. Film-making has its own words (beat, take, bed, stem). SP.term("beat") marks one in the app's
   copy: it gets a dotted underline and its plain meaning on hover or focus. Tips.glossary() lists them all. */
window.Tips = (() => {
"use strict";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };

// Written for someone who has never edited a film. Keep each to a sentence or two, with no other jargon in it.
const TERMS = {
  reference: ["Reference", "A film you like, added to the library to study and borrow from."],
  scene: ["Scene", "One idea in a film, from one change to the next. Scenes are what you browse, tag and borrow. Written as film/s05: the fifth scene of that film."],
  breakdown: ["Breakdown", "What your AI writes about a film: each scene, what is on screen, how it moves, and how to recreate it."],
  tag: ["Tag", "A word from the project's own fixed list that describes a scene, so scenes from different films can be found together."],
  move: ["Move", "A named piece of motion a film is known for, like a whip between scenes or words sharpening into focus."],
  moment: ["Moment", "One exact frame you saved, so you can point at it later or put it on a board."],
  board: ["Board", "Your film's script: the scenes you borrow, in order, each with its words and its length."],
  beat: ["Beat", "One step of your film, and one line on a board. It borrows a scene, says what is on screen, and lasts a few seconds."],
  "motion profile": ["Motion profile", "How everything in one film moves: how fast things arrive, whether they bounce. One per film, so it feels made by one hand."],
  storyboard: ["Storyboard", "A film's plan, beat by beat, once you start building it from a board."],
  render: ["Render", "A video file made from the film as it stands. Each new one gets a version number, so you can compare."],
  cue: ["Cue", "A time in the film where something happens, written down once so picture and sound agree."],
  take: ["Take", "One of several versions of a sound: a voice line read again, or another try at the music. You choose which one plays."],
  bed: ["Bed", "The music that runs under a film."],
  stem: ["Stem", "One part of the music on its own, such as the drums or the bass, so each can be heard and cut separately."],
  strip: ["Strip", "A scene's frames side by side, so you can see what happens in it without playing it."],
};

let tip = null, timer = 0, target = null, lastHide = 0;
const COLD = 450, WARM = 400;   // ms before the first tooltip; how long after one closes the next is instant

/** The element under the pointer that has something to say, with its native title taken over. */
function owner(node) {
  const el = node?.closest?.("[title], [data-tip], [data-term]");
  if (!el || el.closest(".tip")) return null;
  const t = el.getAttribute("title");
  if (t) {   // take the browser's tooltip over (again, if the app has since set a new title)
    el.dataset.tip = t;
    el.removeAttribute("title");
    if (!el.getAttribute("aria-label") && !el.textContent.trim()) el.setAttribute("aria-label", t);
  }
  return el.dataset.tip || el.dataset.term ? el : null;
}

function content(el) {
  const term = TERMS[el.dataset.term];
  if (term) return `<b>${esc(term[0])}</b>${esc(term[1])}`;
  return esc(el.dataset.tip || "").replace(/\n/g, "<br>");
}

function show(el) {
  if (!el.isConnected) return;
  const html = content(el);
  if (!html) return;
  if (!tip) { tip = h(`<div class="tip" role="tooltip"></div>`); document.body.append(tip); }
  tip.className = "tip" + (el.dataset.term ? " tip-term" : "");
  tip.innerHTML = html;
  tip.style.left = tip.style.top = "0px";
  tip.classList.add("on");
  // under the element, centred; above it when there is no room below; never off the window's edge
  const r = el.getBoundingClientRect(), t = tip.getBoundingClientRect(), gap = 8, pad = 8;
  // (a film word's meaning goes above it when it can: you are reading on, downwards)
  const above = r.top - gap - t.height, roomAbove = above > pad;
  let top = el.dataset.term && roomAbove ? above : r.bottom + gap;
  if (top + t.height > innerHeight - pad && roomAbove) top = above;
  const left = Math.max(pad, Math.min(innerWidth - t.width - pad, r.left + r.width / 2 - t.width / 2));
  tip.style.left = `${Math.round(left)}px`;
  tip.style.top = `${Math.round(Math.max(pad, top))}px`;
}

function hide() {
  clearTimeout(timer);
  if (tip?.classList.contains("on")) { tip.classList.remove("on"); lastHide = performance.now(); }
  target = null;
}

function aim(el, now) {
  if (el === target) return;
  hide();
  if (!el) return;
  target = el;
  const wait = now || performance.now() - lastHide < WARM ? 0 : COLD;
  timer = setTimeout(() => target === el && show(el), wait);
}

const touch = () => matchMedia("(hover: none)").matches;
document.addEventListener("mouseover", (e) => { if (!touch()) aim(owner(e.target)); }, true);
document.addEventListener("mouseout", (e) => { if (target && !target.contains(e.relatedTarget)) hide(); }, true);
document.addEventListener("focusin", (e) => { const el = owner(e.target); if (el && e.target.matches?.(":focus-visible")) aim(el, true); }, true);
document.addEventListener("focusout", hide, true);
for (const ev of ["mousedown", "keydown", "wheel"]) document.addEventListener(ev, hide, true);
addEventListener("scroll", hide, true);
addEventListener("blur", hide);

/** A film word in the app's copy, with its meaning one hover away: SP.term("beat"), or SP.term("beat", "beats"). */
const term = (key, text) => (TERMS[key] ? `<span class="term" data-term="${esc(key)}" tabindex="0">${esc(text || key)}</span>` : esc(text || key));

let sheet = null;
function glossary() {
  if (sheet) return;
  sheet = h(`<div class="imp-scrim gl"><div class="imp-sheet gl-sheet" role="dialog" aria-label="Glossary">
    <div class="imp-head"><h2>The words Spliced uses</h2><button class="icon-btn ghost sm sq" data-a="x" title="Close (Esc)">${window.icon("x")}</button></div>
    <p class="wl-lead">Film-making has its own words. These are the ones you will meet here, in plain terms.</p>
    <dl class="gl-list">${Object.values(TERMS).map(([name, means]) => `<div><dt>${esc(name)}</dt><dd>${esc(means)}</dd></div>`).join("")}</dl></div></div>`);
  document.body.append(sheet);
  requestAnimationFrame(() => sheet?.classList.add("in"));
  const close = () => { const s = sheet; sheet = null; s.classList.remove("in"); setTimeout(() => s.remove(), 180); };
  sheet.querySelector('[data-a="x"]').onclick = close;
  sheet.addEventListener("mousedown", (e) => { if (e.target === sheet) close(); });
  sheet.tabIndex = -1;
  sheet.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } });
  sheet.focus();
}

if (window.SP) window.SP.term = term;
return { TERMS, term, glossary, hide };
})();
