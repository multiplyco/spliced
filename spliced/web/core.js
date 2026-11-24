/* Loaded first. Where the app gets things from: the one place that builds a URL for a file of the project.

   The server (toolbox.py) serves three kinds of URL:
     /app/...            this app's own files
     /project/<path>     a picture, clip or sound of the project, by its project-relative path
     /api/...            data and actions
   Files are written down everywhere (breakdowns, storyboards, uploads.json, assets) as project-relative paths
   like "reference/Film [id].mp4"; SP.fileUrl turns one into a URL. Nothing else in the app should build one. */
// The project, as the server describes it (/api/boot.js): its name, whose films these are, its motion profiles.
window.SPLICED = Object.assign({ project: "", brand: "", profiles: {}, default_profile: "soft", cli: "spliced" }, window.SPLICED);

// What the project calls its AI: its own name for it, "Claude" when it has Claude read its imports, otherwise
// "your AI". SP.ai in the middle of a sentence, SP.Ai at the start of one.
const AI = String(window.SPLICED.ai || "").trim();

// The Mac app (mac/ in the repo) runs this same page in its own window and offers a few things a browser can't: a
// real folder picker, Finder. SP.native is null in a browser; in the app, SP.native.ask("pickFolder") resolves with
// the native side's answer (the app calls SP.native.answer(id, value) back).
const NATIVE = window.webkit?.messageHandlers?.spliced ? (() => {
  let n = 0; const waiting = new Map();
  return {
    app: "mac",
    ask: (type, body = {}) => new Promise((resolve) => { const id = ++n; waiting.set(id, resolve); window.webkit.messageHandlers.spliced.postMessage({ id, type, ...body }); }),
    answer: (id, value) => { const r = waiting.get(id); waiting.delete(id); if (r) r(value); },
  };
})() : null;

window.SP = {
  /** The Mac app's bridge, or null in a browser. */
  native: NATIVE,
  ai: AI || "your AI",
  Ai: AI || "Your AI",
  /** Who made a change, as shown beside it: a change is signed "claude", "agent" (over MCP), "browser" or a name. */
  who: (by) => (by === "claude" ? "Claude" : by === "agent" ? AI || "Your AI" : by),
  /** " for Acme" when the project names its brand, "" when it doesn't: for copy that reads fine either way. */
  forBrand: () => (SPLICED.brand ? ` for ${SPLICED.brand}` : ""),
  /** A Spliced command as the person or their AI would type it: SP.cmd("film", "status", slug) -> "spliced film status <slug>".
      Every command the app shows or copies goes through here, so the day the tool is installed on its own they all change at once. */
  cmd: (...a) => [SPLICED.cli, ...a].join(" "),
  /** A project file's URL: "reference/a b.mp4" -> "/project/reference/a%20b.mp4". */
  fileUrl: (f) => "/project/" + String(f || "").split("/").map(encodeURIComponent).join("/"),
  /** A scene's strip of frames (library/references/<film>/scenes/<id>.jpg, cut by the library build). */
  stripUrl: (film, id) => SP.fileUrl(`library/references/${film}/scenes/${id}.jpg`),
  /** One frame of a video, cut by the server and cached: v is anything that changes when the file does (its mtime). */
  frameUrl: (file, t, w = 320, v) => `/api/frame?file=${encodeURIComponent(file)}&t=${(+t || 0).toFixed(3)}&w=${w}${v ? `&v=${Math.round(v)}` : ""}`,
};

// Spliced runs through its server. Opened as a file there is no library, no boards and no media to show: say so.
if (location.protocol === "file:") {
  document.addEventListener("DOMContentLoaded", () => {
    document.body.innerHTML = `<div style="position:fixed;inset:0;display:grid;place-items:center;font:500 15px/1.6 Inter,system-ui,sans-serif;text-align:center;padding:24px">
      <div><p style="font-size:18px;font-weight:600;margin:0 0 8px">Spliced runs through its server</p>
      <p style="margin:0;opacity:.7">Start it with <code>spliced open</code>, then open the address it prints.</p></div></div>`;
  });
}
