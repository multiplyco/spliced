// The nine beats of the Spliced explainer. Every component takes film time `t`; every time comes from cues.json;
// every move is a role of the film's profile (motion('splice')).
import React from 'react';
import {AbsoluteFill} from 'remotion';
import {motion} from '../../lib/motion';
import {LOCKUP_W, Lockup, RISE_ORDER, T, UI, display, label, mono} from './brand';
import {AddSheet, APP_H, APP_W, BoardsView, BuildView, Cursor, Frame, gridSlot, LibraryView, NoteCompose, rowThumb, Sidebar, Toast,
  type Beat, type Card, type CardPose, type RowState, type Step, type View} from './ui';
import cues from './cues.json';
import frames from './frames.json';

export const m = motion('splice');
const C = cues;
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
/** A click: 0 → 1 → 0 over 0.2s (the squash of a press). */
const press = (t: number, at: number) => Math.sin(Math.PI * clamp01((t - at) / 0.2));
/** Characters typed by time t (keystroke timing, one per 1/cps). */
const typed = (s: string, t: number, at: number, cps: number) => s.slice(0, Math.max(0, Math.min(s.length, Math.floor((t - at) * cps) + (t >= at ? 1 : 0))));
const fmt = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toFixed(2).padStart(5, '0')}`;

// ---------------------------------------------------------------- shared pieces
export const Ground: React.FC = () => (
  <AbsoluteFill style={{background: `radial-gradient(ellipse 80% 60% at 50% 0%, ${T.g900} 0%, ${T.ink} 70%)`}} />
);

/** The film's headline: Anybody wide, words sharpen in on the profile, then blur out. */
export const Headline: React.FC<{t: number; lines: string[]; at: number; out: number; size?: number; top?: number}> = ({t, lines, at, out, size = 60, top = 64}) => {
  if (t < at - 0.01) return null;
  const x = m.exit(t, out);
  if (x >= 1) return null;
  let i = 0;
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top, textAlign: 'center', ...display(size), opacity: 1 - x, filter: `blur(${10 * x}px)`, transform: `translateY(${-8 * x}px)`}}>
      {lines.map((ln, li) => (
        <div key={li}>{ln.split(' ').map((w) => <span key={w + i} style={{...m.word(t, at, i++, T.chalk), margin: '0 0.14em'}}>{w}</span>)}</div>
      ))}
    </div>
  );
};

/** The app window on the stage: app space (2000 x 1180) at 0.8, top-left at (160, 200), bleeding off the bottom. */
export const WIN = {x: 160, y: 200, s: 0.8};
export const appToScreen = (ax: number, ay: number) => ({x: WIN.x + WIN.s * ax, y: WIN.y + WIN.s * ay});
type Cam = {x: number; y: number; s: number};
const REST: Cam = {x: 960, y: 540, s: 1};
const cam = (a: number[]) => ({x: a[0], y: a[1], s: a[2]});
/** Blend two cameras (scale in log space, so a zoom feels even). */
const camLerp = (a: Cam, b: Cam, k: number): Cam => ({x: lerp(a.x, b.x, k), y: lerp(a.y, b.y, k), s: Math.exp(lerp(Math.log(a.s), Math.log(b.s), k))});
const camCss = (c: Cam) => `translate(${960 - c.x * c.s}px, ${540 - c.y * c.s}px) scale(${c.s})`;

const AppWindow: React.FC<{children: React.ReactNode; cam?: Cam; enter?: number; exit?: number; overlay?: React.ReactNode}> = ({children, cam = REST, enter = 1, exit = 0, overlay}) => (
  <AbsoluteFill style={{transform: camCss(cam), transformOrigin: '0 0', opacity: Math.min(1, enter * 1.4) * (1 - exit), filter: exit > 0 ? `blur(${12 * exit}px)` : undefined}}>
    <div style={{position: 'absolute', left: WIN.x, top: WIN.y + 420 * (1 - enter), width: APP_W, height: APP_H, transform: `scale(${WIN.s})`, transformOrigin: '0 0',
      borderRadius: 22, overflow: 'hidden', background: T.ink, boxShadow: `0 0 0 1px ${T.g700}, 0 40px 120px rgba(0,0,0,0.6)`}}>
      {children}
    </div>
    {overlay}
  </AbsoluteFill>
);
/** Fades the window's top edge under the headline, so a pushed-in camera never puts UI behind the words. */
const TopShade: React.FC = () => <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 210, background: `linear-gradient(${T.ink} 55%, rgba(11,11,12,0))`}} />;

// ---------------------------------------------------------------- 1. open: a caret
export const Open: React.FC<{t: number}> = ({t}) => {
  const c = C.open;
  const x = m.exit(t, c.exit);
  const last = c.lines.length - 1;
  const doneAt = c.typeAt[last] + c.lines[last].length / c.cps;
  const typing = t >= c.typeAt[0] && t < doneAt;
  const blink = typing ? 1 : 0.2 + 0.8 * (0.5 + 0.5 * Math.cos(2 * Math.PI * Math.max(0, t - (t < c.typeAt[0] ? 0 : doneAt))));
  const cur = c.lines.findIndex((ln, i) => t < c.typeAt[i] + ln.length / c.cps) ;
  const caretLine = cur === -1 ? last : t < c.typeAt[cur] && cur > 0 ? cur - 1 : cur;
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
      <Ground />
      <div style={{position: 'relative', ...display(108), lineHeight: 1.12, opacity: 1 - x, filter: `blur(${12 * x}px)`}}>
        {c.lines.map((ln, li) => {
          const shown = typed(ln, t, c.typeAt[li], c.cps);
          return (
            <div key={li} style={{whiteSpace: 'pre'}}>
              <span>{shown}</span>
              {li === caretLine && <span style={{display: 'inline-block', width: 10, height: '0.78em', marginLeft: 6, background: T.volt, opacity: blink, verticalAlign: '-0.02em'}} />}
              <span style={{opacity: 0}}>{ln.slice(shown.length)}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 2. paste a link
export const Paste: React.FC<{t: number}> = ({t}) => {
  const c = C.paste;
  const p = m.move(t, c.whip);
  const x = m.exit(t, c.exit);
  const focus = m.ui(t, c.focus);
  const link = t >= c.paste ? c.link : '';
  const job = m.ui(t, c.job);
  const steps: Step[] = [t < c.steps[0] ? 'cur' : 'done', t < c.steps[0] ? 'todo' : t < c.steps[1] ? 'cur' : 'done', t < c.steps[1] ? 'todo' : 'cur', 'todo'];
  const ck = m.move(t, c.cursor[0], c.cursor[1] - c.cursor[0]);
  const cur = {x: lerp(1600, 1376, ck), y: lerp(1000, 610, ck)};
  return (
    <AbsoluteFill>
      <Ground />
      <Headline t={t} lines={[c.head[0] as string]} at={c.head[1] as number} out={c.head[2] as number} />
      <div style={{position: 'absolute', left: 0, right: 0, top: c.sheet.top, display: 'flex', justifyContent: 'center', perspective: 1400}}>
        <div style={{transform: `translateX(${900 * (1 - p)}px) scale(${c.sheet.scale * (1 + 1.4 * (1 - p))}) rotateY(${-28 * (1 - p)}deg)`, transformOrigin: '50% 0',
          filter: `blur(${14 * (1 - p) + 12 * x}px)`, opacity: Math.min(1, p * 3) * (1 - x)}}>
          <AddSheet link={link} focus={focus} press={press(t, c.click)} job={job} steps={steps} loaderT={t} />
        </div>
      </div>
      <Cursor x={cur.x} y={cur.y} press={press(t, c.click)} o={t < c.cursor[0] ? 0 : Math.min(1, (t - c.cursor[0]) * 5) * (1 - x)} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 3. cut into scenes
type Strip = {t: number; scene: string; src: string};
const STRIP = frames.strip as Strip[];
const SCENES = frames.strip_scenes;
const FW = 116, FH = 78, GAP = 22, STRIP_Y = 560;
const groupsOf = () => SCENES.map((s) => STRIP.map((f, i) => ({f, i})).filter(({f}) => f.scene === s.id));
const GROUPS = groupsOf();
const CUTS = GROUPS.slice(1).map((g) => g[0].i); // frame index where each new scene starts
const CARD = {w: 272, h: 153, gap: 22, y: 452};
const cardRect = (g: number) => ({x: (1920 - (6 * CARD.w + 5 * CARD.gap)) / 2 + g * (CARD.w + CARD.gap), y: CARD.y, w: CARD.w, h: CARD.h});

const cutTimes = () => {
  const [a, b] = C.cut.scan;
  return {at: (i: number) => a + (b - a) * (i / STRIP.length), a, b};
};

/** Where each scene segment sits on the strip at time t (gaps open as the playhead passes a cut). */
const stripLayout = (t: number) => {
  const ct = cutTimes();
  const gapK = CUTS.map((ci) => m.ui(t, ct.at(ci)));
  const width = STRIP.length * FW + gapK.reduce((a, k) => a + k * GAP, 0);
  const x0 = 960 - width / 2;
  const segs = GROUPS.map((g, gi) => {
    const before = gapK.slice(0, gi).reduce((a, k) => a + k * GAP, 0);
    return {x: x0 + g[0].i * FW + before, y: STRIP_Y - FH / 2, w: g.length * FW, h: FH};
  });
  return {segs, x0, width, ct};
};

const Segment: React.FC<{g: {f: Strip; i: number}[]; r: {x: number; y: number; w: number; h: number}; k: number; scanned: (i: number) => number}> = ({g, r, k, scanned}) => {
  const mid = g[Math.floor(g.length / 2)].f;
  return (
    <div style={{position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, borderRadius: 4 + 8 * k, overflow: 'hidden', background: T.g900, boxShadow: `0 0 0 1px ${T.g700}`}}>
      <div style={{position: 'absolute', inset: 0, display: 'flex', opacity: 1 - k}}>
        {g.map(({f, i}) => {
          const s = scanned(i);
          return <div key={i} style={{flex: 1, height: '100%', borderRight: `1px solid ${T.ink}`}}><Frame src={f.src} style={{filter: `grayscale(${1 - s}) brightness(${0.42 + 0.58 * s})`}} /></div>;
        })}
      </div>
      {k > 0 && <div style={{position: 'absolute', inset: 0, opacity: k}}><Frame src={mid.src} /></div>}
    </div>
  );
};

const cardLabel = (gi: number) => `${SCENES[gi].id} · ${fmt(SCENES[gi].start)}`;

export const Cut: React.FC<{t: number}> = ({t}) => {
  const c = C.cut;
  const e = m.enter(t, c.enter);
  const {segs, ct} = stripLayout(t);
  const [a, b] = c.scan;
  const play = clamp01((t - a) / (b - a)); // playback runs at a constant speed
  const L = stripLayout(b);
  const phX = L.x0 + play * L.width;
  const scanned = (i: number) => m.ui(t, ct.at(i + 0.5));
  const phO = t < a ? e : 1 - m.exit(t, b + 0.05);
  return (
    <AbsoluteFill>
      <Ground />
      <Headline t={t} lines={[c.head[0] as string]} at={c.head[1] as number} out={c.head[2] as number} />
      <div style={{position: 'absolute', inset: 0, opacity: e, transform: `translateX(${160 * (1 - e)}px)`}}>
        {GROUPS.map((g, gi) => {
          const k = m.move(t, c.cards + gi * 0.05);
          const s = segs[gi], d = cardRect(gi);
          const r = {x: lerp(s.x, d.x, k), y: lerp(s.y, d.y, k), w: lerp(s.w, d.w, k), h: lerp(s.h, d.h, k)};
          const lab = m.ui(t, ct.at(g[0].i)) * (1 - k);
          const under = m.textReveal(t, c.labels, gi);
          return (
            <React.Fragment key={gi}>
              <Segment g={g} r={r} k={k} scanned={scanned} />
              {lab > 0.01 && <div style={{position: 'absolute', left: s.x, top: s.y - 30, ...label(13, T.s300), opacity: lab, whiteSpace: 'nowrap'}}>{SCENES[gi].id}</div>}
              {under > 0 && (
                <div style={{position: 'absolute', left: d.x, top: d.y + d.h + 16, width: d.w, opacity: Math.min(1, under), transform: `translateY(${10 * (1 - under)}px)`, filter: `blur(${6 * (1 - Math.min(1, under))}px)`}}>
                  <div style={mono(14, T.s400)}>{cardLabel(gi)}</div>
                  <div style={{marginTop: 6, fontFamily: UI, fontSize: 16, lineHeight: 1.35, color: T.chalk, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden'}}>{SCENES[gi].title}</div>
                </div>
              )}
            </React.Fragment>
          );
        })}
        {phO > 0 && (
          <div style={{position: 'absolute', left: phX - 1, top: STRIP_Y - FH / 2 - 44, width: 2, height: FH + 70, background: T.volt, opacity: phO, boxShadow: '0 0 18px rgba(223,255,26,0.45)'}}>
            <div style={{position: 'absolute', top: -6, left: -6, width: 14, height: 8, borderRadius: '4px 4px 1px 1px', background: T.volt}} />
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 4. name every move
const BIG = {x: 580, y: 214, w: 760, h: 427.5};
const chipW = (s: string) => s.length * 13.4 + 36;
const Chip: React.FC<{children: React.ReactNode; on?: number; w?: number; style?: React.CSSProperties}> = ({children, on = 0, w, style}) => (
  <div style={{position: 'absolute', height: 48, width: w, padding: w ? 0 : '0 18px', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
    fontFamily: UI, fontWeight: 500, fontSize: 24, whiteSpace: 'nowrap', color: on > 0.5 ? T.ink : T.s300,
    background: on > 0 ? `rgba(244,244,241,${on})` : T.ink, boxShadow: `inset 0 0 0 2px ${on > 0.5 ? T.chalk : T.g700}`, ...style}}>{children}</div>
);

export const Name: React.FC<{t: number}> = ({t}) => {
  const c = C.name;
  const x = m.exit(t, c.exit);
  const carry = m.move(t, c.carry);
  const g0 = GROUPS[c.hero], mid = g0[Math.floor(g0.length / 2)].f;
  const from = cardRect(c.hero);
  const r = {x: lerp(from.x, BIG.x, carry), y: lerp(from.y, BIG.y, carry), w: lerp(from.w, BIG.w, carry), h: lerp(from.h, BIG.h, carry)};
  // the reel: ease-sink spins it fast through the middle and lands it slowly on the last tag
  const reelK = m.emphasis(t, c.reel);
  const pos = reelK * (c.reelTags.length - 1);
  const speed = (m.emphasis(t + 1 / 30, c.reel) - reelK) * (c.reelTags.length - 1) * 30;
  const landed = m.ui(t, c.land);
  const reelIn = m.enter(t, c.reel - 0.15);
  const lastW = chipW(c.reelTags[c.reelTags.length - 1]);
  const w0 = lerp(360, lastW, landed);
  const sibW = c.siblings.map(chipW);
  const rowW = lastW + sibW.reduce((a, w) => a + w + 14, 0);
  const rowX = 960 - rowW / 2;
  const reelX = lerp(960 - w0 / 2, rowX, landed);
  const meta = m.textReveal(t, c.meta);
  return (
    <AbsoluteFill>
      <Ground />
      <Headline t={t} lines={[c.head[0] as string]} at={c.head[1] as number} out={c.head[2] as number} />
      <div style={{position: 'absolute', inset: 0, opacity: 1 - x, filter: x > 0 ? `blur(${12 * x}px)` : undefined}}>
        {GROUPS.map((g, i) => {
          if (i === c.hero) return null;
          const d = cardRect(i), o = 1 - m.exit(t, c.carry + i * 0.03);
          return o > 0 && <div key={i} style={{position: 'absolute', left: d.x, top: d.y + 30 * (1 - o), width: d.w, height: d.h, borderRadius: 12, overflow: 'hidden', opacity: o, filter: `blur(${8 * (1 - o)}px)`}}><Frame src={g[Math.floor(g.length / 2)].f.src} /></div>;
        })}
        <div style={{position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, borderRadius: 12 + 4 * carry, overflow: 'hidden', boxShadow: `0 0 0 1px ${T.g700}, 0 30px 80px rgba(0,0,0,0.5)`}}><Frame src={mid.src} /></div>
        {meta > 0 && <>
          <div style={{position: 'absolute', left: BIG.x, top: BIG.y - 30, ...mono(15, T.s300), opacity: Math.min(1, meta)}}>acme-plan-it-together/{SCENES[c.hero].id}</div>
          <div style={{position: 'absolute', left: BIG.x + BIG.w - 240, width: 240, textAlign: 'right', top: BIG.y - 30, ...mono(15, T.s400), opacity: Math.min(1, meta)}}>{fmt(SCENES[c.hero].start)} to {fmt(SCENES[c.hero].end)}</div>
        </>}
        {reelIn > 0 && (
          <Chip w={w0} on={landed} style={{left: reelX, top: 688, opacity: Math.min(1, reelIn)}}>
            <div style={{position: 'absolute', left: 0, right: 0, top: 0, transform: `translateY(${-pos * 48}px)`, filter: `blur(${Math.min(4, Math.abs(speed) * 0.25)}px)`}}>
              {c.reelTags.map((tag) => <div key={tag} style={{height: 48, lineHeight: '48px', textAlign: 'center'}}>{tag}</div>)}
            </div>
          </Chip>
        )}
        {c.siblings.map((s, i) => {
          const k = m.textReveal(t, c.tags, i);
          const left = rowX + lastW + 14 + sibW.slice(0, i).reduce((a, w) => a + w + 14, 0);
          return k > 0 && <Chip key={s} style={{left, top: 688, opacity: Math.min(1, k), transform: `translateY(${12 * (1 - Math.min(1, k))}px)`, filter: `blur(${6 * (1 - Math.min(1, k))}px)`,
            color: s.startsWith('★') ? T.warning : T.s300}}>{s}</Chip>;
        })}
        <div style={{position: 'absolute', left: 0, right: 0, top: 770, textAlign: 'center', fontFamily: UI, fontSize: 22, color: T.s400, opacity: Math.min(1, m.textReveal(t, c.tags, 5))}}>
          {SCENES[c.hero].title}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 5. find it
const GRID_CARDS: Card[] = frames.grid.map((g) => ({key: g.key, src: g.src, dur: g.dur, tags: g.tags.filter(Boolean) as string[]}));
const MATCH = GRID_CARDS.map((c) => c.tags.includes(C.find.query));
const MATCH_SLOT = MATCH.map((ok, i) => (ok ? MATCH.slice(0, i).filter(Boolean).length : -1));
const N_MATCH = MATCH.filter(Boolean).length;
const SEARCH_APP = {x: 126, y: 78};

const libraryPoses = (t: number): CardPose[] => {
  const f = C.find;
  return GRID_CARDS.map((_, i) => {
    const from = gridSlot(i);
    if (MATCH[i]) {
      const k = m.move(t, f.sort + MATCH_SLOT[i] * 0.04);
      const to = gridSlot(MATCH_SLOT[i]);
      return {x: lerp(from.x, to.x, k), y: lerp(from.y, to.y, k), w: from.w, h: from.h, o: 1, sel: MATCH_SLOT[i] === 0 ? m.ui(t, f.pickClick) : 0};
    }
    const out = m.exit(t, f.sort - 0.05 + (i % 5) * 0.015);
    return {x: from.x + from.w * 0.04 * out, y: from.y + 14 * out, w: from.w * (1 - 0.08 * out), h: from.h * (1 - 0.08 * out), o: 1 - out};
  });
};
const libraryCount = (t: number) => (t < C.find.sort ? 'Video 572' : `${N_MATCH} scenes`);
const LibraryAt: React.FC<{t: number}> = ({t}) => {
  const f = C.find;
  const q = typed(f.query, t, f.type, f.cps);
  return <><Sidebar view="library" search={q} searchFocus={m.ui(t, f.click)} caret={t >= f.click && t < f.sort + 1.2} /><LibraryView cards={GRID_CARDS} poses={libraryPoses(t)} count={libraryCount(t)} /></>;
};

export const Find: React.FC<{t: number}> = ({t}) => {
  const f = C.find;
  const enter = m.enter(t, f.window);
  const camNow = camLerp(cam(f.cams[0]), cam(f.cams[1]), m.camera(t, f.push));
  const a = m.move(t, f.cursor[0], f.cursor[1] - f.cursor[0]);
  const b = m.move(t, f.pick[0], f.pick[1] - f.pick[0]);
  const s0 = appToScreen(SEARCH_APP.x - 40, SEARCH_APP.y + 4);
  const slot0 = gridSlot(0), s1 = appToScreen(slot0.x + slot0.w * 0.55, slot0.y + slot0.h * 0.6);
  const cx = t < f.pick[0] ? lerp(1500, s0.x, a) : lerp(s0.x, s1.x, b);
  const cy = t < f.pick[0] ? lerp(1020, s0.y, a) : lerp(s0.y, s1.y, b);
  const pr = Math.max(press(t, f.click), press(t, f.pickClick));
  return (
    <AbsoluteFill>
      <Ground />
      <AppWindow cam={camNow} enter={enter} overlay={<Cursor x={cx} y={cy} press={pr} o={t < f.cursor[0] ? 0 : Math.min(1, (t - f.cursor[0]) * 5)} />}>
        <LibraryAt t={t} />
      </AppWindow>
      <TopShade />
      <Headline t={t} lines={[f.head[0] as string]} at={f.head[1] as number} out={f.head[2] as number} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 6. board it
const BOARD_BEATS: Beat[] = (() => {
  const names = ['Open: a caret', 'Paste a link', 'Cut into scenes', 'Name every move', 'Find it', 'Board it', 'With Claude', 'Build view', 'End card'];
  const copy = ['Films you love. / Frame by frame.', 'Paste a link.', 'Cut into scenes.', 'Every move named', 'Find it in seconds.', 'Borrow the move. / Write the script.', 'Claude works with you.', 'Every beat, / beside its reference.', 'Spliced / Study it. Name it. Make it.'];
  const secs = Object.values(C.scenes).map(([a, b]) => b - a);
  let acc = 0;
  return frames.board.map((b, i) => {
    const r = {n: i + 1, tc: fmt(acc).padStart(7, '0'), name: names[i], scene: b.key, title: b.title, copy: copy[i], secs: secs[i], src: b.src};
    acc += secs[i];
    return r;
  });
})();
const PILE = [{x: 900, y: 560, r: -8}, {x: 1180, y: 520, r: 6}, {x: 1020, y: 700, r: -3}, {x: 1300, y: 690, r: 9}];
const PILE_W = 380, PILE_H = 213.75;

const boardState = (t: number) => {
  const c = C.boardIt;
  const rows: RowState[] = BOARD_BEATS.map((_, i) => {
    if (i >= PILE.length) return {o: 0, text: 0};
    const text = m.textReveal(t, c.rowsText, i);
    const row: RowState = {o: t >= c.snap ? 1 : 0, text: Math.min(1, text)};
    if (i === c.typed) {
      row.copyShown = typed(BOARD_BEATS[i].copy, t, c.type, c.cps);
      row.focus = m.ui(t, c.focus) * (1 - m.ui(t, c.type + BOARD_BEATS[i].copy.length / c.cps + 0.4));
      row.caret = t >= c.focus && row.focus > 0.3;
    }
    return row;
  });
  const done = PILE.filter((_, i) => t >= c.snap + i * 0.035).length;
  const beats = t < c.snap ? 0 : Math.min(PILE.length, Math.max(1, Math.round(done)));
  const secs = BOARD_BEATS.slice(0, beats).reduce((a, b) => a + b.secs, 0);
  return {rows, meta: `${beats} beats · ${secs.toFixed(1)}s of 40s`};
};

const PileCards: React.FC<{t: number}> = ({t}) => {
  const c = C.boardIt;
  return <>{PILE.map((p, i) => {
    const e = m.enter(t, c.pile + i * c.pileGap);
    if (e <= 0) return null;
    const k = m.move(t, c.snap + i * 0.035);
    const to = rowThumb(i);
    const w = lerp(PILE_W, to.w, k), h = lerp(PILE_H, to.h, k);
    const cx = lerp(p.x, to.x + to.w / 2, k), cy = lerp(p.y + 220 * (1 - e), to.y + to.h / 2, k);
    return (
      <div key={i} style={{position: 'absolute', left: cx - w / 2 - 252, top: cy - h / 2, width: w, height: h, borderRadius: lerp(14, 8, k), overflow: 'hidden', opacity: Math.min(1, e * 2),
        transform: `rotate(${p.r * (1 - k)}deg) scale(${1 + 0.12 * (1 - e)})`, boxShadow: `0 0 0 1px ${T.g700}, 0 ${24 * (1 - k)}px ${60 * (1 - k)}px rgba(0,0,0,0.55)`}}>
        <Frame src={BOARD_BEATS[i].src} />
      </div>
    );
  })}</>;
};

const BoardAt: React.FC<{t: number}> = ({t}) => {
  const s = boardState(t);
  return <BoardsView beats={BOARD_BEATS} rows={s.rows} meta={s.meta} showThumbs={false}><PileCards t={t} /></BoardsView>;
};

export const Board: React.FC<{t: number}> = ({t}) => {
  const c = C.boardIt;
  const from = C.find;
  return (
    <AbsoluteFill>
      <Ground />
      <AppWindow cam={camLerp(camLerp(cam(c.cams[0]), cam(c.cams[1]), m.camera(t, C.design['board-it'][0])), cam(c.cams[2]), m.camera(t, c.push))}>
        <Sidebar view={t < c.pile - 0.2 ? 'library' : 'boards'} />
        <m.ViewChange t={t} start={C.design['board-it'][0]} style={{position: 'absolute', left: 0, top: 0, width: APP_W, height: APP_H}}
          from={<LibraryView cards={GRID_CARDS} poses={libraryPoses(from.pickClick + 1)} count={libraryCount(from.pickClick + 1)} />}
          to={<BoardAt t={t} />} />
      </AppWindow>
      <TopShade />
      {c.head.map((h, i) => <Headline key={i} t={t} lines={[h[0] as string]} at={h[1] as number} out={h[2] as number} />)}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 7. with claude
const claudeState = (t: number) => {
  const c = C.claude, b = C.boardIt;
  const base = boardState(b.type + 5);
  const rows: RowState[] = BOARD_BEATS.map((_, i) => {
    if (i < PILE.length) {
      const r = {...base.rows[i]};
      if (i === c.editRow) {
        r.copyShown = t < c.edit ? c.editFrom : c.editTo;
        r.flash = t >= c.edit ? 1 - m.exit(t, c.edit + 0.5, 1.0) : 0;
      }
      return r;
    }
    const at = c.add[i - PILE.length];
    if (at === undefined) return {o: 0, text: 0};
    const g = m.ui(t, at);
    return {o: g > 0 ? 1 : 0, grow: g, text: Math.min(1, m.textReveal(t, at + 0.15)), flash: g > 0 ? 1 - m.exit(t, at + 0.5, 1.0) : 0};
  });
  const n = PILE.length + c.add.filter((a) => t >= a).length;
  const secs = BOARD_BEATS.slice(0, n).reduce((a, b2) => a + b2.secs, 0);
  return {rows, meta: `${n} beats · ${secs.toFixed(1)}s of 40s`};
};

export const Claude: React.FC<{t: number}> = ({t}) => {
  const c = C.claude;
  const sc = m.camera(t, c.scroll) * c.scrollBy;
  const s = claudeState(t);
  const t1 = m.ui(t, c.toast1) * (1 - m.exit(t, c.toast2 - 0.1));
  const t2 = m.ui(t, c.toast2);
  return (
    <AbsoluteFill>
      <Ground />
      <AppWindow cam={cam(c.cam)}>
        <Sidebar view="boards" />
        <BoardsView beats={BOARD_BEATS} rows={s.rows} meta={s.meta} scroll={sc} showThumbs />
        <Toast k={t1} text={<>Claude: added <b style={{fontWeight: 600}}>Find it</b> and <b style={{fontWeight: 600}}>Board it</b></>} style={{right: 60, top: 940}} />
        <Toast k={t2} text={<>Claude: tightened the copy on beat 4</>} style={{right: 60, top: 940}} />
      </AppWindow>
      <TopShade />
      <Headline t={t} lines={[c.head[0] as string]} at={c.head[1] as number} out={c.head[2] as number} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 8. build view
const BAR = BOARD_BEATS.map((b) => ({n: b.n, name: b.name, dur: b.secs}));
export const Build: React.FC<{t: number}> = ({t}) => {
  const c = C.build;
  const [endA] = C.design['end-card'];
  const ft = endA + Math.max(0, t - c.plays); // the render plays the end card beat
  const total = C.designDuration;
  const camNow = camLerp(camLerp(cam(c.cams[0]), cam(c.cams[1]), m.camera(t, C.design['build-view'][0])), cam(c.cams[2]), m.camera(t, c.push));
  const x = m.exit(t, c.exit);
  const ck = m.move(t, c.cursor[0], c.cursor[1] - c.cursor[0]);
  const target = appToScreen(560, 560);
  const cur = {x: lerp(1500, target.x, ck), y: lerp(1000, target.y, ck)};
  const note = typed(c.note, t, c.type, c.cps);
  const pinAt = (endA + Math.max(0, c.pin - c.plays)) / total;
  const prevEnd = claudeState(C.claude.edit + 3);
  const scale = 810 / 1920;
  return (
    <AbsoluteFill>
      <Ground />
      <AppWindow cam={camNow} exit={x} overlay={<Cursor x={cur.x} y={cur.y} press={press(t, c.click)} o={t < c.cursor[0] ? 0 : Math.min(1, (t - c.cursor[0]) * 5) * (1 - m.exit(t, c.compose))} />}>
        <Sidebar view={t < C.design['build-view'][0] + 0.2 ? 'boards' : 'build'} />
        <m.ViewChange t={t} start={C.design['build-view'][0]} style={{position: 'absolute', left: 0, top: 0, width: APP_W, height: APP_H}}
          from={<BoardsView beats={BOARD_BEATS} rows={prevEnd.rows} meta={prevEnd.meta} scroll={C.claude.scrollBy} showThumbs />}
          to={<>
            <BuildView bar={BAR} selBeat={8} playhead={ft / total} tc={`${fmt(ft)}  f${Math.floor((ft % 1) * 30)}`} thumbs={BOARD_BEATS.map((b) => b.src)}
              refLabel={`${BOARD_BEATS[8].scene}  1:04.95`} pins={[{at: pinAt, k: m.ui(t, c.pin)}]}
              render={<div style={{width: 1920, height: 1080, transform: `scale(${scale})`, transformOrigin: '0 0', position: 'relative'}}><End t={ft} /></div>}
              reference={<Frame src={BOARD_BEATS[8].src} />} />
            <NoteCompose k={m.ui(t, c.compose)} text={note} caret={t >= c.type - 0.2} tc={fmt((endA + c.pin - c.plays))} style={{left: 336, top: 256}} />
          </>} />
      </AppWindow>
      <TopShade />
      <Headline t={t} lines={c.head[0] as string[]} at={c.head[1] as number} out={c.head[2] as number} size={50} top={52} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 9. end card
export const End: React.FC<{t: number}> = ({t}) => {
  const c = C.end;
  const W = 1000 * LOCKUP_W / 930, s = W / LOCKUP_W; // same word size as before, wider lockup
  const rise = [0, 0, 0, 0];
  RISE_ORDER.forEach((b, j) => { rise[b] = m.emphasis(t, c.rise + j * c.riseGap); });
  // once built: sink tallest first, rise back lowest first (the brand's hover move)
  const sinkOrder = [...RISE_ORDER].reverse();
  sinkOrder.forEach((b, j) => {
    const down = m.emphasis(t, c.sink + j * 0.06, 0.45), up = m.emphasis(t, c.rise2 + (3 - j) * 0.06, 0.5);
    rise[b] = rise[b] * (1 - 0.6 * down * (1 - up));
  });
  const slide = m.move(t, c.slide);
  const markOnly = (W / 2 - (277.1 * 0.72176 * s) / 2); // shift that puts the mark alone at the centre
  const word = m.enter(t, c.word);
  const o = m.enter(t, c.in);
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
      <Ground />
      <div style={{position: 'absolute', left: 960 - W / 2 + markOnly * (1 - slide), top: 470 - (145.8 * s) / 2, opacity: Math.min(1, o * 2)}}>
        <Lockup width={W} rise={rise} word={word} wordShift={-40 * (1 - word)} />
      </div>
      <div style={{position: 'absolute', top: 640, left: 0, right: 0, textAlign: 'center', fontFamily: UI, fontWeight: 500, fontSize: 34, color: T.s300}}>
        {c.tagline_words.map((w, i) => <span key={w} style={{...m.word(t, c.tagline, i, T.s300), margin: '0 0.3em'}}>{w}</span>)}
      </div>
    </AbsoluteFill>
  );
};

export const SCENE_OF: Record<string, React.FC<{t: number}>> = {
  'open-a-caret': Open, 'paste-a-link': Paste, 'cut-into-scenes': Cut, 'name-every-move': Name, 'find-it': Find,
  'board-it': Board, 'with-claude': Claude, 'build-view': Build, 'end-card': End,
};
export type {View};
