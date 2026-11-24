/* A view's explainer: the first time someone opens a view, a few lines under its heading say what it is for and
   the two or three things to try. "Got it" puts that one away for good; "Hide all of these" puts them all away
   (someone who knows the app shouldn't have to dismiss each). Settings and ⌘K bring them back.

   The words are written for someone who has never edited a film: no jargon that isn't in the glossary, and a
   film word is marked with SP.term so its meaning is one hover away.

   A short loop can sit beside the words: when the app ships web/explainers/<key>.mp4 the server names it in
   SPLICED.explainers and it plays, silent and looping. None ships yet.

   Views don't call this. It watches the main area and places the explainer under whatever heading the view drew,
   so a view that draws itself again gets it back, and a new view needs only an entry in VIEWS. */
window.Explain = (() => {
"use strict";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const SEEN = "cr.explained", OFF = "cr.explainOff";
const T = (k, text) => (window.SP?.term ? SP.term(k, text) : esc(text || k));
const K = (k) => `<kbd>${esc(k)}</kbd>`;

// key -> [title, the lines]. Lines are functions so the film words and the AI's name are filled in when shown.
const VIEWS = {
  scenes: ["This is your library", () => [
    `Every ${T("scene")} from the films you have added, and the pictures and clips you uploaded.`,
    `Move the pointer across a card to run through it. Click one to open it: it plays just that scene, and says what is on screen, how it moves and how to recreate it.`,
    `Press <b>+</b> on a card to borrow it for your ${T("board")}, the heart to keep it as a favourite, and <b>Filter</b> to narrow by any ${T("tag")}. In an open scene, ${K("N")} writes your own note on it, and the note goes into the brief you copy.`]],
  boards: ["Boards are your films' scripts", () => [
    `A ${T("board")} is one film, written down: the scenes it borrows, in order, each with its words and its length.`,
    `Start one with <b>New board</b>, or ask ${esc(SP.ai)} to put one together from a sentence about what the film should say.`]],
  board: ["This board is a script", () => [
    `Each row is a ${T("beat")}: the scene it borrows, the words on screen, the line that is spoken, and how many seconds it lasts. The running time adds them up.`,
    `Drag a row to reorder. Type straight into any field; ${esc(SP.ai)} can edit the same board while you watch.`,
    `<b>Copy build prompt</b> hands the script to ${esc(SP.ai)} to build. <b>Start film</b> turns it into a film in production, which you then follow in Build.`]],
  build: ["Films in production", () => [
    `Each film here started from a ${T("board")}. Open one to see it next to what it borrows from, ${T("beat")} by beat.`]],
  "build-film": ["Your film, beside what it borrows from", () => [
    `On the left is your latest ${T("render")}; on the right, the scene the current ${T("beat")} borrows, playing alongside so you can compare.`,
    `Pause on a frame and press ${K("N")} to leave a note right there. ${esc(SP.Ai)} picks the notes up, fixes them and renders again.`,
    `Every beat has a status. It becomes <b>to review</b> when there is something new to look at; you set <b>approved</b> or ask for changes.`]],
  assets: ["Everything your films are made of", () => [
    `Every still, clip and sound across your films, with what made each one and whether it is used.`,
    `The search also looks in free footage libraries. <b>Add</b> pulls a clip or photo into a film and writes down its author and licence.`]],
  profiles: ["The looks your films are made in", () => [
    `A ${T("profile")} is a look: your company's own, or one you want to explore. It keeps a palette, type, a ${T("motion profile")} and your own words, and ${esc(SP.ai)} adds the rules it learns on every film.`,
    `One can be the default. Each brief you copy can choose another, or <b>No profile</b> to recreate the reference as it is.`,
    `Start one with <b>New profile</b>, or from a film you like: its page has <b>Start a profile</b>.`]],
  sound: ["The film's sound, taken apart", () => [
    `Music, voice and effects, each on its own line, laid over the music's own pulse so you can see what lands on it.`,
    `Turn the sound on to hear the parts in step with the picture; mute or solo any line. Drag across a stretch to loop it or leave a note about it.`,
    `A ${T("take")} is another version of a sound. Hear one under the picture, then use it. A ${T("stem")} is one part of the music on its own.`]],
};

const read = () => { try { return new Set(JSON.parse(localStorage.getItem(SEEN) || "[]")); } catch { return new Set(); } };
const off = () => localStorage.getItem(OFF) === "1";
const wanted = (key) => !!VIEWS[key] && !off() && !read().has(key);

function build(key) {
  const [title, lines] = VIEWS[key], loop = window.SPLICED?.explainers?.[key];
  const el = h(`<aside class="explain ${loop ? "with-loop" : ""}" data-key="${esc(key)}" aria-label="About this view">
    ${loop ? `<video class="ex-loop" autoplay muted loop playsinline preload="metadata" src="${esc(loop)}"></video>` : ""}
    <div class="ex-text"><b>${esc(title)}</b>${lines().map((l) => `<p>${l}</p>`).join("")}</div>
    <div class="ex-acts"><button class="icon-btn sm" data-a="ok">Got it</button><button class="ex-all" data-a="all" title="Stop showing these in every view. Settings brings them back.">Hide all of these</button></div></aside>`);
  el.querySelector('[data-a="ok"]').onclick = () => { const s = read(); s.add(key); localStorage.setItem(SEEN, JSON.stringify([...s])); el.remove(); };
  el.querySelector('[data-a="all"]').onclick = () => { localStorage.setItem(OFF, "1"); document.querySelectorAll(".explain").forEach((x) => x.remove()); window.crToast?.("Hidden everywhere. Settings brings them back."); };
  return el;
}

/** The explainer for a part of a view that draws itself (the Sound panel): an element to put in, or null.
    One thing at a time: while the view around it (`after`) still has its own to show, the part waits its turn. */
const inline = (key, after) => (wanted(key) && !(after && wanted(after)) ? build(key) : null);

// which explainer the address asks for; null while a scene is open over a view (leave what is there alone)
function keyOf() {
  const parts = location.hash.replace(/^#\/?/, "").split("?")[0].split("/").filter(Boolean), v = parts[0] || "scenes";
  if (v === "scene") return null;
  if (v === "boards") return parts[1] ? "board" : "boards";
  if (v === "build") return parts[1] ? "build-film" : "build";
  if (v === "profiles") return parts[1] ? null : "profiles";
  return v;
}

let forced = null;   // "About this view" shows one even after it was put away
function place() {
  const main = document.getElementById("main"), key = keyOf();
  if (!main || key === null) return;
  const have = main.querySelector(":scope > .explain, .film-page > .explain");
  const want = VIEWS[key] && (forced === key || wanted(key));
  if (have && (!want || have.dataset.key !== key)) have.remove();
  if (!want || (have && have.dataset.key === key)) return;
  const head = main.querySelector(".view-head");
  if (head) head.after(build(key));
}

function start() {
  const main = document.getElementById("main");
  if (!main) return;
  new MutationObserver(place).observe(main, { childList: true });
  addEventListener("hashchange", () => { forced = null; place(); });
  place();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();

/** Show this view's explainer again (⌘K, "About this view"). */
function show() { const key = keyOf(); if (!VIEWS[key]) return false; forced = key; document.querySelector("#main .explain")?.remove(); place(); document.querySelector("#main .explain")?.scrollIntoView({ block: "nearest" }); return true; }
/** Bring every explainer back (Settings). */
function reset() { localStorage.removeItem(SEEN); localStorage.removeItem(OFF); forced = null; place(); }

return { inline, show, reset, has: () => !!VIEWS[keyOf()], hidden: () => off() || read().size > 0, VIEWS };
})();
