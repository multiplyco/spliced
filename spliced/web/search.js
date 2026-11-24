/* A search bar for a view: type, and the cards on screen that don't match step aside.

   One bar, the same in every view that lists things (Films, Moves, Boards, a film's scenes, Styles, Build). It
   filters what the view has already drawn, so a view only says which elements are its cards:

     ViewSearch.attach(head, "films", { placeholder: "Search films", cards: ".films .film" })

   What a card is matched on: its data-search if it has one, else opts.text(el), else the words on it. Every word
   typed has to be in there. The bar keeps what was typed while the view draws itself again, empties when you go
   somewhere else, and takes its start from the address (#/moves?q=whip), which is how the global search hands over. */
window.ViewSearch = (() => {
"use strict";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const typed = {};      // view key -> what is in its bar
const fromHash = {};   // view key -> the last ?q= taken from the address (so going back to typing isn't overridden)
let focusKey = null;   // the bar being typed in, so a view that redraws gives it the caret back

// Leaving a view empties its bar: coming back to a list that is quietly still filtered hides what is new there.
// (A view drawing itself again, because something changed, is not leaving: the address is the same.)
const place = () => location.hash.split("?")[0];
let at = place();
addEventListener("hashchange", () => { if (place() !== at) { at = place(); for (const k in typed) delete typed[k]; for (const k in fromHash) delete fromHash[k]; focusKey = null; } });

const hashQ = () => { const m = location.hash.split("?")[1]; return m ? new URLSearchParams(m).get("q") : null; };
const words = (q) => q.toLowerCase().split(/\s+/).filter(Boolean);

/**
 * head: the view's .view-head. key: a name for the view. opts:
 *   placeholder   what the bar says when empty
 *   cards         selector (inside root) of the things to filter
 *   root          where to look for them (default: the head's parent)
 *   text(el)      what a card is matched on, when it has no data-search
 *   sections      selector of groups to hide when none of their cards is left
 *   count(shown, total, q)   tell the view how many are left (to update its "34 films")
 *   after(root, q)           anything else the view wants done once the cards are filtered
 */
function attach(head, key, opts) {
  const root = opts.root || head.parentNode;
  const hq = hashQ();
  if (hq != null && hq !== fromHash[key]) { fromHash[key] = hq; typed[key] = hq; }
  const bar = h(`<label class="vsearch">${window.icon("search")}<input type="search" spellcheck="false" autocomplete="off" placeholder="${esc(opts.placeholder || "Search")}" aria-label="${esc(opts.placeholder || "Search")}">
    <button type="button" class="vs-x" title="Clear the search (Esc)" hidden>${window.icon("x")}</button></label>`);
  const inp = bar.querySelector("input"), x = bar.querySelector(".vs-x");
  inp.value = typed[key] || "";
  const spacer = head.querySelector(".spacer");
  if (spacer) spacer.after(bar); else { head.append(h(`<span class="spacer"></span>`), bar); }

  const textOf = (el) => (el._vs ??= (el.dataset.search || opts.text?.(el) || el.textContent || "").toLowerCase());
  function apply() {
    const q = (typed[key] || "").trim(), ws = words(q);
    const cards = [...root.querySelectorAll(opts.cards)];
    let shown = 0;
    for (const el of cards) {
      const ok = !ws.length || ws.every((w) => textOf(el).includes(w));
      el.classList.toggle("vs-hide", !ok);
      if (ok) shown++;
    }
    if (opts.sections) for (const sec of root.querySelectorAll(opts.sections)) sec.classList.toggle("vs-hide", !!ws.length && ![...sec.querySelectorAll(opts.cards)].some((c) => !c.classList.contains("vs-hide")));
    x.hidden = !q;
    bar.classList.toggle("on", !!q);
    root.querySelector(":scope > .vs-none")?.remove();
    if (q && cards.length && !shown) {
      const none = h(`<div class="empty vs-none">Nothing here matches “${esc(q)}”. <button class="vs-clear">Clear the search</button></div>`);
      none.querySelector("button").onclick = () => set("");
      root.append(none);
    }
    opts.count?.(shown, cards.length, q);
    opts.after?.(root, q);
  }
  function set(v) { typed[key] = v; inp.value = v; apply(); }
  let t;
  inp.addEventListener("input", () => { typed[key] = inp.value; clearTimeout(t); t = setTimeout(apply, 60); });
  inp.addEventListener("focus", () => (focusKey = key));
  inp.addEventListener("blur", () => { if (focusKey === key) focusKey = null; });
  inp.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.stopPropagation(); if (inp.value) set(""); else inp.blur(); }
    else if (!e.metaKey && !e.ctrlKey) e.stopPropagation();   // typing here is typing, not the app's single-key shortcuts
  });
  x.onclick = () => { set(""); inp.focus(); };
  if (focusKey === key) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
  apply();
  return { apply, set, input: inp };
}

return { attach, value: (key) => typed[key] || "" };
})();
