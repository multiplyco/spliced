/* Keyboard shortcuts: one registry the views read from, so Settings can rebind any of them. A binding is the key as
   the browser reports it (e.key), with modifiers first: "ArrowDown", "Shift+ArrowLeft", "Meta+\\", "k", " " (space).
   Each action can have several bindings; the person's own choice (Settings) replaces the defaults for that action.
   Stored in this browser: localStorage cr.keys = {id: ["binding", ...]}. */
window.KB = (() => {
"use strict";
const DEFS = [
  // group, id, label, default bindings
  ["Everywhere", "search", "Search", ["/"]],
  ["Everywhere", "help", "Keyboard shortcuts", ["?"]],
  ["Everywhere", "sidebar", "Hide or show the sidebar", ["Meta+\\"]],
  ["Tabs", "newTab", "New tab", ["Alt+t"]],
  ["Tabs", "closeTab", "Close the tab", ["Alt+w"]],
  ["Tabs", "nextTab", "Next tab", ["Alt+ArrowRight"]],
  ["Tabs", "prevTab", "Previous tab", ["Alt+ArrowLeft"]],
  ["Library", "filter", "Filter", ["f"]],
  ["Library", "zoomOut", "Smaller cards", ["-"]],
  ["Library", "zoomIn", "Bigger cards", ["=", "+"]],
  ["Viewer", "next", "Next item", ["ArrowDown", "]"]],
  ["Viewer", "prev", "Previous item", ["ArrowUp", "["]],
  ["Viewer", "play", "Play / pause", [" "]],
  ["Viewer", "frameBack", "Back one frame", [","]],
  ["Viewer", "frameFwd", "Forward one frame", ["."]],
  ["Viewer", "seekBack", "Back 1 second (Shift: 0.1s)", ["ArrowLeft"]],
  ["Viewer", "seekFwd", "Forward 1 second (Shift: 0.1s)", ["ArrowRight"]],
  ["Viewer", "fav", "Favourite", ["f"]],
  ["Viewer", "sceneNote", "Write a note on the scene", ["n"]],
  ["Viewer", "moment", "Save the frame as a moment", ["k"]],
  ["Viewer", "board", "Add to the current board", ["b"]],
  ["Viewer", "brief", "Copy the brief", ["c"]],
  ["Viewer", "time", "Copy the time with the ID", ["t"]],
  ["Build", "beatNext", "Next beat", ["ArrowDown", "]"]],
  ["Build", "beatPrev", "Previous beat", ["ArrowUp", "["]],
  ["Build", "bPlay", "Play / pause", [" "]],
  ["Build", "bFrameBack", "Back one frame", [","]],
  ["Build", "bFrameFwd", "Forward one frame", ["."]],
  ["Build", "bSeekBack", "Back 1 second (Shift: 0.1s)", ["ArrowLeft"]],
  ["Build", "bSeekFwd", "Forward 1 second (Shift: 0.1s)", ["ArrowRight"]],
  ["Build", "note", "Pin a note to the frame", ["n"]],
  ["Build", "compare", "Compare with another render", ["x"]],
  ["Build", "refPane", "Show or hide the reference beside the render", ["h"]],
  ["Build", "swap", "Swap the compared renders", ["v"]],
  ["Build", "loop", "Loop the beat / play through", ["l"]],
  ["Build", "sync", "Reference timed to the beat", ["s"]],
  ["Build", "tlIn", "Zoom in on the timeline", ["=", "+"]],
  ["Build", "tlOut", "Zoom out on the timeline", ["-"]],
  ["Build", "tlFit", "Show the whole film on the timeline", ["0"]],
  ["Build", "full", "Full screen", ["f"]],
  ["Build", "sound", "Sound on / off", ["m"]],
  ["Build", "reload", "Reload the plan and renders", ["r"]],
  ["Build", "bTime", "Copy the time with the beat", ["t"]],
  ["Sounds", "sPlay", "Play / pause", [" "]],
  ["Sounds", "sNext", "Next sound", ["ArrowDown", "]"]],
  ["Sounds", "sPrev", "Previous sound", ["ArrowUp", "["]],
  ["Sounds", "sBack", "Back 5 seconds (Shift: 1s)", ["ArrowLeft"]],
  ["Sounds", "sFwd", "Forward 5 seconds (Shift: 1s)", ["ArrowRight"]],
  ["Sounds", "sLoop", "Loop the sound / play through the list", ["l"]],
];
const own = () => { try { return JSON.parse(localStorage.getItem("cr.keys") || "{}"); } catch { return {}; } };
const def = (id) => DEFS.find((d) => d[1] === id);
const get = (id) => own()[id] || def(id)?.[3] || [];
// a keydown as a binding string: modifiers, then the key (letters lower case; Shift is implied for "?", "+" and the like)
function of(e) {
  let k = e.key;
  if (e.altKey && /^Key[A-Z]$/.test(e.code)) k = e.code.slice(3);
  else if (e.altKey && /^Digit\d$/.test(e.code)) k = e.code.slice(5);
  if (k.length === 1) k = k.toLowerCase();
  if (k === "Dead" || ["Shift", "Meta", "Control", "Alt"].includes(k)) return "";
  const mods = [e.metaKey && "Meta", e.ctrlKey && "Ctrl", e.altKey && "Alt", e.shiftKey && k.length > 1 && "Shift"].filter(Boolean);
  return [...mods, k].join("+");
}
// does this keydown trigger the action? Shift on arrows counts as the same action (the fine step)
function is(e, id) {
  const b = of(e); if (!b) return false;
  const plain = b.replace(/^Shift\+(?=Arrow)/, "");
  return get(id).some((x) => x === b || x === plain);
}
const NAMES = { " ": "Space", ArrowDown: "↓", ArrowUp: "↑", ArrowLeft: "←", ArrowRight: "→", Escape: "Esc", Meta: "⌘", Ctrl: "Ctrl", Alt: "⌥", Shift: "⇧", Enter: "↵" };
const parts = (b) => b === "+" ? ["+"] : b.endsWith("++") ? [...b.slice(0, -2).split("+"), "+"] : b.split("+");
const label = (b) => parts(b).map((p) => NAMES[p] || (p.length === 1 ? p.toUpperCase() : p)).join(" ");
const keycaps = (id) => get(id).map((b) => `<kbd>${label(b).replace(/&/g, "&amp;").replace(/</g, "&lt;")}</kbd>`).join(" ");
function set(id, bindings) { const o = own(); o[id] = bindings; localStorage.setItem("cr.keys", JSON.stringify(o)); }
function reset(id) { const o = own(); if (id) delete o[id]; else for (const k of Object.keys(o)) delete o[k]; localStorage.setItem("cr.keys", JSON.stringify(o)); }
const custom = (id) => !!own()[id];
// actions in the same group (or Everywhere) that share a binding
function clashes(id) {
  const g = def(id)[0], mine = get(id);
  return DEFS.filter((d) => d[1] !== id && (d[0] === g || d[0] === "Everywhere" || g === "Everywhere") && get(d[1]).some((b) => mine.includes(b))).map((d) => d[2]);
}
return { DEFS, of, is, get, set, reset, custom, label, keycaps, clashes };
})();
