/* The project's folders (spliced.json "folders", `spliced folders`): how its films, boards and assets are sorted,
   say one folder per kind of video, or one per client. Build, Boards and Assets group by folder and share one filter
   (cr.folder): everything, one folder, or Shared (what is in no folder). The Library is never filtered: every
   folder borrows from all of it. A project with no folders sees none of this. */
(() => {
  const KEY = "cr.folder";   // "" everything · "-" in no folder (Shared) · a folder's path
  const list = () => window.SPLICED?.folders || [];
  const name = (f) => (f ? list().find((x) => x.folder === f)?.name || f : "Shared");
  const filter = () => { const v = localStorage.getItem(KEY) || ""; return v === "-" || !v || list().some((x) => x.folder === v) ? v : ""; };
  const matches = (f) => { const v = filter(); return !v || (v === "-" ? !f : f === v); };

  async function refresh() {
    try { const r = await fetch("/api/folders"); if (r.ok) SPLICED.folders = (await r.json()).folders || []; } catch {}
    return list();
  }

  /** Ask for a name and make the folder. Resolves with its path, or "" if nothing was made. */
  async function create() {
    const n = (prompt("A name for the new folder (say Branding videos, or a client's name). Spliced makes it inside the project.") || "").trim();
    if (!n) return "";
    try {
      const r = await fetch("/api/folders", { method: "POST", body: JSON.stringify({ name: n }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || r.statusText);
      SPLICED.folders = j.folders || list();
      window.crToast?.(`Made ${j.folder.folder}/`);
      return j.folder.folder;
    } catch (e) { window.crToast?.(`Couldn't make the folder: ${e.message}`); return ""; }
  }

  /** Menu items to put something in a folder: [{value, html, on}], with "In no folder" and "New folder…".
      Hand the picked value to pick(): it makes the folder first when that was asked for. `sepAlone`: the menu takes
      a separator as an item of its own (Build's), not as a line drawn before an item (the Boards' menu). */
  const items = (current, icon, sepAlone = false) => [
    ...list().map((x) => ({ value: x.folder, on: current === x.folder, html: `${icon("folder")}<span class="lbl">${esc(x.name)}</span><span class="c">${esc(x.folder)}/</span>` })),
    { value: "-", on: !current, html: `${icon("folder-open")}<span class="lbl">In no folder (Shared)</span>` },
    ...(sepAlone ? [{ sep: true }] : []),
    { value: "+", sep: !sepAlone, html: `${icon("folder-plus")}<span class="lbl">New folder…</span>` },
  ];
  async function pick(v) { return v === "+" ? create() : v === "-" ? "" : v; }

  /** [{folder, name, items}] in spliced.json's order, Shared last; only the groups the filter lets through. */
  function groups(things, folderOf) {
    const out = [...list(), { folder: "", name: "Shared" }].map((x) => ({ ...x, items: things.filter((t) => (folderOf(t) || "") === x.folder) }));
    const known = new Set(list().map((x) => x.folder));
    out[out.length - 1].items.push(...things.filter((t) => folderOf(t) && !known.has(folderOf(t))));   // a folder since taken off the list
    return out.filter((g) => matches(g.folder));
  }

  /** The filter as a row of chips: All · each folder · Shared · +. Calls onChange after the filter changes. */
  function chips(onChange, counts = {}) {
    const el = document.createElement("div");
    el.className = "fold-chips";
    el.setAttribute("role", "radiogroup");
    el.setAttribute("aria-label", "Show one folder");
    const v = filter();
    const chip = (val, label, title, n) => `<button role="radio" aria-checked="${v === val}" class="${v === val ? "on" : ""}" data-v="${esc(val)}" title="${esc(title)}">${esc(label)}${n != null ? `<span class="c">${n}</span>` : ""}</button>`;
    el.innerHTML = chip("", "All", "Everything, folder by folder", counts.all)
      + list().map((x) => chip(x.folder, x.name, `Only what is in ${x.folder}/`, counts[x.folder] ?? 0)).join("")
      + chip("-", "Shared", "Only what is in no folder: shared by all of them", counts[""] ?? 0)
      + `<button class="fold-new" data-v="+" title="Make a new folder to sort films, boards and assets into">+</button>`;
    el.querySelectorAll("button").forEach((b) => (b.onclick = async () => {
      let val = b.dataset.v;
      if (val === "+") { val = await create(); if (!val) return; }
      localStorage.setItem(KEY, val);
      onChange?.(val);
    }));
    return el;
  }

  /** How many things each folder holds, for the chips: {all, "": n, folder: n}. */
  function count(things, folderOf) {
    const c = { all: things.length, "": 0 };
    const known = new Set(list().map((x) => x.folder));
    for (const t of things) { const f = folderOf(t) || ""; const k = known.has(f) ? f : ""; c[k] = (c[k] || 0) + 1; }
    return c;
  }

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  window.Folders = { list, any: () => list().length > 0, name, filter, matches, refresh, create, items, pick, groups, chips, count };
})();
