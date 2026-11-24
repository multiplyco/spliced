/* Studio hardware: how the tactile controls of the Build view behave (the look is hardware.css).
   HW.knob(el, opts) turns an empty element into a knob; HW.slide(el) wires a slide switch whose options are plain
   buttons carrying .on. Both set their own ARIA, take the keyboard only while they have focus, and never take focus
   from a click, so the view's own shortcuts (arrows seek, Space plays) keep working after the mouse has been used.
   HW.sound is the sound of the parts moving: off unless the person turns it on (Settings, or ⌘K), made in code. */
window.HW = (() => {
"use strict";
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));

/* ---------- sounds: small mechanical clicks, synthesised (no files) ----------
   Off by default; on is localStorage cr.uiSound = "1" (this browser). Nothing is made, not even the audio context,
   until a sound is asked for with the setting on. A sound belongs to operating a control by hand: pressing a key,
   sliding the switch, turning a knob, on screen or with its keyboard shortcut (app.js hwKey presses the key on screen
   with its sound, as the person asked: it should feel like a studio). A control the app moves by itself stays silent.
   Each sound is one or two short parts: a burst of filtered noise (the contact) and a low sine that drops (the body).
   Every hit varies a little in pitch and level, so a row of clicks doesn't sound stamped out.
   sound.hush, when the view sets it, says when to stay quiet (Build: while a film plays with its sound on). */
const sound = (() => {
  const KEY = "cr.uiSound", LEVEL = 0.5;
  let ctx = null, out = null, noise = null, lastTick = 0;
  const on = () => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } };
  const set = (x) => { try { localStorage.setItem(KEY, x ? "1" : "0"); } catch {} };
  const vary = (x, by) => x * (1 + (Math.random() - 0.5) * by);
  function noiseBuf(c) {
    const b = c.createBuffer(1, Math.round(c.sampleRate * 0.5), c.sampleRate), d = b.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    return b;
  }
  // the way out: one level for every sound, and the top rolled off so nothing is sharp
  function chain(c) {
    const g = c.createGain(); g.gain.value = LEVEL;
    const lp = c.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 9000; lp.Q.value = 0.5;
    g.connect(lp); lp.connect(c.destination);
    return g;
  }
  // the parts a sound is built from, placed in time with at()
  function parts(c, dest, nb, t0) {
    let t = t0;
    return {
      at(dt) { t = t0 + dt; },
      hit({ f, q = 1.5, d, g, a = 0.0006 }) {   // filtered noise: f centre, q width, a attack, d decay, g level
        const src = c.createBufferSource(); src.buffer = nb;
        const bp = c.createBiquadFilter(); bp.type = "bandpass"; bp.frequency.value = vary(f, 0.06); bp.Q.value = q;
        const e = c.createGain(); e.gain.setValueAtTime(0.0001, t); e.gain.exponentialRampToValueAtTime(vary(g, 0.16), t + a); e.gain.exponentialRampToValueAtTime(0.0001, t + a + d * 3);
        src.connect(bp); bp.connect(e); e.connect(dest);
        src.start(t, Math.random() * 0.3, a + d * 3 + 0.01);
      },
      body({ f, to, d, g }) {   // a sine falling from f to `to` over d
        const o = c.createOscillator(); o.frequency.setValueAtTime(vary(f, 0.04), t); o.frequency.exponentialRampToValueAtTime(to, t + d);
        const e = c.createGain(); e.gain.setValueAtTime(0.0001, t); e.gain.exponentialRampToValueAtTime(vary(g, 0.16), t + 0.002); e.gain.exponentialRampToValueAtTime(0.0001, t + d);
        o.connect(e); e.connect(dest); o.start(t); o.stop(t + d + 0.01);
      },
    };
  }
  const VOICES = {
    // a key going down: a soft, low thock
    down: (p) => { p.hit({ f: 2300, q: 1.1, d: 0.004, g: 0.5 }); p.body({ f: 165, to: 105, d: 0.045, g: 0.5 }); },
    // and coming back up: lighter and higher
    up: (p) => { p.hit({ f: 3300, q: 1.4, d: 0.003, g: 0.26 }); p.body({ f: 250, to: 185, d: 0.028, g: 0.16 }); },
    // the slide switch: the cap travels (a breath of friction), lands in its seat, and the spring settles
    clack: (p) => {
      p.hit({ f: 900, q: 0.7, d: 0.009, g: 0.05, a: 0.012 });
      p.at(0.034); p.hit({ f: 2000, q: 1.2, d: 0.004, g: 0.5 }); p.body({ f: 205, to: 135, d: 0.04, g: 0.4 });
      p.at(0.052); p.hit({ f: 3900, q: 2, d: 0.002, g: 0.13 });
    },
    // a knob falling into a stop: small, hard, plastic
    detent: (p) => { p.hit({ f: 3600, q: 2.5, d: 0.002, g: 0.4 }); p.body({ f: 520, to: 430, d: 0.014, g: 0.12 }); },
    // a smooth knob passing a mark: barely there, a touch higher as the level goes up (o.v, 0 to 1)
    tick: (p, o) => p.hit({ f: 4600 + 1500 * (o.v ?? 0.5), q: 3, d: 0.0012, g: 0.2 }),
    // a knob reaching the end of its travel: a dull bump
    stop: (p) => { p.hit({ f: 700, q: 0.9, d: 0.005, g: 0.2 }); p.body({ f: 120, to: 78, d: 0.05, g: 0.35 }); },
  };
  function play(name, o = {}) {
    if (!VOICES[name] || !on() || (sound.hush && sound.hush())) return false;
    const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return false;
    const now = performance.now();
    if (name === "tick") { if (now - lastTick < 24) return false; lastTick = now; }   // a fast turn doesn't become a buzz
    try {
      if (!ctx) { ctx = new AC({ latencyHint: "interactive" }); out = chain(ctx); noise = noiseBuf(ctx); }
      if (ctx.state === "suspended") ctx.resume().catch(() => {});
      VOICES[name](parts(ctx, out, noise, ctx.currentTime + 0.004), o);
    } catch { return false; }
    return true;
  }
  // a sound as samples (48 kHz, mono, 200 ms), without playing it: for measuring it on the specimen sheet
  async function render(name, o = {}) {
    const c = new OfflineAudioContext(1, 9600, 48000);
    VOICES[name](parts(c, chain(c), noiseBuf(c), 0.005), o);
    return (await c.startRendering()).getChannelData(0);
  }
  return { on, set, play, render, names: Object.keys(VOICES), live: () => !!ctx, hush: null };
})();

// keys: down on the press, up on the release, wherever a .hw-key is
let heldKey = null;
document.addEventListener("pointerdown", (e) => {
  if (e.button) return;
  const k = e.target.closest && e.target.closest(".hw-key");
  if (!k || k.disabled) return;
  heldKey = k; sound.play("down");
}, true);
const liftKey = () => { if (heldKey) { heldKey = null; sound.play("up"); } };
document.addEventListener("pointerup", liftKey, true);
document.addEventListener("pointercancel", liftKey, true);

/* A knob. Drag up or right to turn it (Shift: fine), arrow keys when focused, Home / End for the ends.
   opts: value; onInput(value); label (for screen readers); format(value) -> text;
         continuous: min, max, step (keys), reset (double-click), sweep (degrees, 270);
         detents: stops [values] (a click steps to the next one, the pips show which), readout (print the value beside it). */
function knob(el, o = {}) {
  const stops = o.stops && o.stops.length > 1 ? o.stops : null;
  const min = stops ? 0 : o.min ?? 0, max = stops ? stops.length - 1 : o.max ?? 1;
  const sweep = o.sweep ?? (stops ? 45 * (stops.length - 1) : 270), step = o.step ?? (max - min) / 20;
  const fmt = o.format || ((v) => String(v));
  const angle = (p) => -sweep / 2 + ((p - min) / (max - min)) * sweep;
  let p = min;   // position: the value itself, or the index of the stop
  el.classList.add("hw-knob"); el.classList.toggle("detent", !!stops);
  el.innerHTML = `<span class="hw-dial"><i class="hw-ring"></i>${stops ? stops.map((_, i) => `<i class="hw-stop" style="--sa:${angle(i)}deg"></i>`).join("") : ""}<i class="hw-cap"></i><i class="hw-ptr"></i></span>${o.readout ? `<span class="hw-read"></span>` : ""}`;
  el.tabIndex = 0; el.setAttribute("role", "slider");
  if (o.label) el.setAttribute("aria-label", o.label);
  const value = () => (stops ? stops[p] : p);
  function paint() {
    const f = (p - min) / (max - min);
    el.style.setProperty("--a", `${angle(p).toFixed(2)}deg`); el.style.setProperty("--v", f.toFixed(4));
    el.setAttribute("aria-valuemin", stops ? stops[0] : min); el.setAttribute("aria-valuemax", stops ? stops[stops.length - 1] : max);
    el.setAttribute("aria-valuenow", +(+value()).toFixed(3)); el.setAttribute("aria-valuetext", fmt(value()));
    el.querySelectorAll(".hw-stop").forEach((s, i) => s.classList.toggle("on", i === p));
    const r = el.querySelector(".hw-read"); if (r) r.textContent = fmt(value());
  }
  // move to a position; tells the owner unless silent (the owner calling set() to show its own state)
  function to(np, silent) {
    np = stops ? clamp(Math.round(np), min, max) : clamp(np, min, max);
    if (np === p) return;
    const mark = (x) => Math.floor(((x - min) / (max - min)) * 20 + 1e-9), was = p;   // twenty marks round a smooth knob
    p = np; paint();
    if (silent) return;
    if (stops) sound.play("detent");
    else if (p === min || p === max) sound.play("stop");
    else if (mark(p) !== mark(was)) sound.play("tick", { v: (p - min) / (max - min) });
    if (o.onInput) o.onInput(value());
  }
  function set(v, silent = true) {
    if (stops) { let best = 0; stops.forEach((s, i) => { if (Math.abs(s - v) < Math.abs(stops[best] - v)) best = i; }); to(best, silent); }
    else to(+v, silent);
  }

  let drag = null;
  el.addEventListener("mousedown", (e) => e.preventDefault());   // a click turns the knob without taking focus
  el.addEventListener("pointerdown", (e) => {
    if (e.button || el.getAttribute("aria-disabled") === "true") return;
    try { el.setPointerCapture(e.pointerId); } catch {}
    drag = { x: e.clientX, y: e.clientY, f: (p - min) / (max - min), moved: 0 };
  });
  el.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const d = (drag.y - e.clientY) + (e.clientX - drag.x);
    drag.x = e.clientX; drag.y = e.clientY; drag.moved += Math.abs(d);
    if (drag.moved < 3) return;
    el.classList.add("turning");
    const travel = stops ? 34 * (stops.length - 1) : 150;   // pixels from one end to the other
    drag.f = clamp(drag.f + d / travel / (e.shiftKey ? 4 : 1), 0, 1);
    to(min + drag.f * (max - min));
  });
  const end = (e) => {
    if (!drag) return;
    const clicked = drag.moved < 3 && e.type === "pointerup";
    drag = null; el.classList.remove("turning");
    if (clicked && stops) to(p >= max ? min : p + 1);   // a click on a detent knob steps to the next stop, round again
  };
  el.addEventListener("pointerup", end); el.addEventListener("pointercancel", end);
  if (!stops && o.reset != null) el.addEventListener("dblclick", () => to(o.reset));
  el.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key, unit = stops ? 1 : step * (e.shiftKey ? 0.2 : 1);
    if (k === "ArrowUp" || k === "ArrowRight") to(p + unit);
    else if (k === "ArrowDown" || k === "ArrowLeft") to(p - unit);
    else if (k === "PageUp") to(p + unit * 4);
    else if (k === "PageDown") to(p - unit * 4);
    else if (k === "Home") to(min);
    else if (k === "End") to(max);
    else return;
    e.preventDefault(); e.stopPropagation();
  });

  if (o.value != null) set(o.value);
  paint();
  return { el, set, get: value };
}

/* A slide switch over two or more buttons. The buttons keep their own click handlers and the owner keeps toggling
   .on on them: the cap follows, and ARIA with it. The cap can also be dragged across; letting go picks the nearest. */
function slide(el, o = {}) {
  const btns = [...el.querySelectorAll(":scope > button")];
  let thumb = el.querySelector(":scope > .hw-thumb");
  if (!thumb) { thumb = document.createElement("i"); thumb.className = "hw-thumb"; el.prepend(thumb); }
  el.classList.add("hw-slide"); el.style.setProperty("--n", btns.length);
  el.setAttribute("role", "radiogroup"); if (o.label) el.setAttribute("aria-label", o.label);
  btns.forEach((b) => b.setAttribute("role", "radio"));
  const at = () => Math.max(0, btns.findIndex((b) => b.classList.contains("on")));
  let cur = null, byHand = false;   // the option the cap is on, and whether the change under way was made on the switch itself
  function sync() {
    const i = at();
    if (i !== cur) { if (cur != null && byHand) sound.play("clack"); cur = i; }
    el.style.setProperty("--i", i);
    btns.forEach((b, j) => { b.setAttribute("aria-checked", j === i ? "true" : "false"); b.tabIndex = j === i ? 0 : -1; });
  }
  new MutationObserver(sync).observe(el, { attributes: true, attributeFilter: ["class"], subtree: true });
  sync();

  // arrows move between the options while one has focus (a radio group), instead of seeking the film
  el.addEventListener("keydown", (e) => {
    const d = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!d || e.metaKey || e.ctrlKey || e.altKey) return;
    e.preventDefault(); e.stopPropagation();
    const n = btns[clamp(at() + d, 0, btns.length - 1)];
    if (!n.classList.contains("on")) n.click();
    n.focus();
  });

  // drag the cap
  let drag = null, swallow = false;
  el.addEventListener("mousedown", (e) => e.preventDefault());
  el.addEventListener("pointerdown", (e) => {
    if (e.button) return;
    drag = { x: e.clientX, from: at(), w: thumb.offsetWidth, on: false, pos: 0 };
    const move = (ev) => {
      const dx = ev.clientX - drag.x;
      if (!drag.on && Math.abs(dx) < 4) return;
      drag.on = true; el.classList.add("dragging");
      drag.pos = clamp(drag.from * drag.w + dx, 0, drag.w * (btns.length - 1));
      thumb.style.transform = `translateX(${drag.pos}px)`;
    };
    const up = () => {
      window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); window.removeEventListener("pointercancel", up);
      const d = drag; drag = null;
      if (!d.on) return;
      el.classList.remove("dragging"); thumb.style.transform = "";
      const to = clamp(Math.round(d.pos / d.w), 0, btns.length - 1);
      swallow = true; setTimeout(() => (swallow = false), 0);   // the click that follows this pointerup is the drag's, not a choice
      if (to !== d.from) btns[to].click();
    };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up); window.addEventListener("pointercancel", up);
  });
  el.addEventListener("click", (e) => {
    if (swallow && e.isTrusted) { e.stopPropagation(); e.preventDefault(); return; }
    if (e.target.closest("button")) { byHand = true; setTimeout(() => (byHand = false), 0); }   // a choice made on the switch (a click, a drag, its own arrow keys): true until sync() has seen it
  }, true);
  return { el, sync };
}

return { knob, slide, sound };
})();
