// Spliced, the app, rebuilt in code (app space 2000 x 1180, the size of the reference captures in .context/splice-shots).
// Values come from Spliced's web/style.css (the Spliced brand section) and splice-tokens.css. Every view is a pure
// function of its props: the scenes compute the state from film time and pass it in.
import React from 'react';
import {Img, staticFile} from 'remotion';
import {Bookmark, Check, Copy, Cpu, Ellipsis, Film, Heart, Image as ImageIcon, LayoutGrid, LayoutList, LibraryBig, List, ListVideo,
  MessageSquare, MessageSquarePlus, Moon, Play, Plus, Search, Settings, SlidersHorizontal, Sparkles, StepBack, StepForward, SwatchBook,
  Upload, X, CircleHelp, ArrowUpDown, ChevronsUpDown, Pencil, GitCompare, Maximize, VolumeX, Repeat, ChevronRight} from 'lucide-react';
import {LOCKUP_W, Lockup, MONO, SpliceMark, T, UI, display, label, mono} from './brand';

export const APP_W = 2000, APP_H = 1180, SIDEBAR = 252;
const ico = {size: 16, strokeWidth: 1.75};

export type View = 'library' | 'boards' | 'build';

/** A frame from the library (the content inside the app). */
export const Frame: React.FC<{src: string; style?: React.CSSProperties; fit?: 'cover' | 'contain'}> = ({src, style, fit = 'cover'}) => (
  <Img src={staticFile(src)} style={{width: '100%', height: '100%', objectFit: fit, display: 'block', ...style}} />
);

// ---------------------------------------------------------------- sidebar
const NAV: [string, React.FC<typeof ico>, View | null, string?][] = [
  ['Library', LibraryBig, 'library'], ['Films', Film, null], ['Moves', Sparkles, null], ['Systems', Cpu, null], ['Styles', SwatchBook, null], ['Moments', Bookmark, null, '1'],
];
const MAKE: [string, React.FC<typeof ico>, View | null][] = [['Boards', LayoutList, 'boards'], ['Build', ListVideo, 'build'], ['Assets', ImageIcon, null]];

export const Sidebar: React.FC<{view: View; search?: string; searchFocus?: number; caret?: boolean; board?: string; beats?: number}> = ({view, search = '', searchFocus = 0, caret, board = 'Spliced: how it works', beats = 9}) => {
  const item = (name: string, I: React.FC<typeof ico>, v: View | null, n?: string) => {
    const on = v === view;
    return (
      <div key={name} style={{display: 'flex', alignItems: 'center', gap: 10, height: 32, padding: '0 10px', borderRadius: 7, fontSize: 13.5, fontWeight: 500,
        color: on ? T.chalk : T.s300, background: on ? T.g800 : 'transparent'}}>
        <span style={{color: on ? T.chalk : T.s400, display: 'flex'}}><I {...ico} /></span>{name}
        {n && <span style={{marginLeft: 'auto', ...mono(11, T.s400)}}>{n}</span>}
      </div>
    );
  };
  return (
    <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: SIDEBAR, background: T.g900, borderRight: `1px solid ${T.g700}`, display: 'flex', flexDirection: 'column', fontFamily: UI}}>
      <div style={{padding: '18px 14px 14px 22px'}}><Lockup width={116 * LOCKUP_W / 930} /></div>
      <div style={{margin: '0 14px 10px', display: 'flex', alignItems: 'center', gap: 8, height: 34, padding: '0 8px 0 10px', borderRadius: 12, background: T.ink,
        boxShadow: searchFocus > 0 ? `inset 0 0 0 1px ${T.volt}, 0 0 0 3px rgba(223,255,26,${0.14 * searchFocus})` : `inset 0 0 0 1px ${T.g700}`, color: T.s300}}>
        <Search {...ico} />
        <span style={{flex: 1, fontSize: 13, color: search ? T.chalk : T.s300, whiteSpace: 'nowrap'}}>{search || 'Search'}{caret && <span style={{display: 'inline-block', width: 1.5, height: 15, background: T.volt, marginLeft: 1, verticalAlign: -2}} />}</span>
        <span style={{...mono(11, T.s300), padding: '2px 5px', borderRadius: 5, background: T.g800, boxShadow: `inset 0 0 0 1px ${T.g600}`}}>/</span>
      </div>
      <div style={{display: 'flex', flexDirection: 'column', gap: 1, padding: '4px 10px 10px'}}>
        <div style={{margin: '4px 10px 4px', ...label(11)}}>Reference</div>
        {NAV.map(([n, I, v, c]) => item(n, I, v, c))}
        <div style={{margin: '14px 10px 4px', ...label(11)}}>Make</div>
        {MAKE.map(([n, I, v]) => item(n, I, v))}
      </div>
      <div style={{flex: 1}} />
      <div style={{margin: '0 10px 8px', display: 'flex', alignItems: 'center', gap: 10, height: 34, padding: '0 12px', borderRadius: 12, background: T.g800, boxShadow: `0 0 0 1px ${T.g700}`, fontSize: 13, fontWeight: 500, color: T.chalk}}>
        <LayoutList {...ico} size={14} /><span style={{flex: 1}}>{board}</span><span style={mono(11, T.s400)}>{beats}</span><ChevronRight {...ico} size={14} color={T.s400} />
      </div>
      <div style={{display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px 12px 18px', fontSize: 12, color: T.s300}}>
        <span style={{display: 'inline-flex', alignItems: 'center', gap: 7, flex: 1}}><span style={{width: 7, height: 7, borderRadius: 4, background: T.success, boxShadow: '0 0 0 3px rgba(61,220,151,0.18)'}} />Live</span>
        {[MessageSquare, Settings, CircleHelp, Moon].map((I, i) => <span key={i} style={{width: 28, height: 28, display: 'grid', placeItems: 'center', color: T.s300}}><I {...ico} size={15} /></span>)}
      </div>
    </div>
  );
};

/** The page title: Anybody wide uppercase, an optional crumb and a name in Inter. */
const Head: React.FC<{crumb?: string; name?: string; meta?: string; right?: React.ReactNode}> = ({crumb, name, meta, right}) => (
  <div style={{display: 'flex', alignItems: 'center', gap: 12, height: 36, marginBottom: 28}}>
    <div style={{display: 'flex', alignItems: 'center', ...display(22, crumb ? T.s400 : T.chalk)}}>
      {crumb ?? name}
      {crumb && name && <><span style={{color: T.s500, margin: '0 10px', fontWeight: 400}}>/</span><span style={{fontFamily: UI, fontStretch: '100%', fontVariationSettings: 'normal', textTransform: 'none', fontWeight: 600, fontSize: 20, letterSpacing: '-0.01em', color: T.chalk}}>{name}</span></>}
    </div>
    {meta && <span style={{fontSize: 13, color: T.s300}}>{meta}</span>}
    <span style={{flex: 1}} />{right}
  </div>
);

export const PrimaryButton: React.FC<{children: React.ReactNode; press?: number; style?: React.CSSProperties}> = ({children, press = 0, style}) => (
  <div style={{display: 'inline-flex', alignItems: 'center', gap: 6, height: 28, padding: '0 12px', borderRadius: 8, background: press > 0.5 ? T.voltPress : T.volt, color: T.ink,
    fontSize: 13, fontWeight: 600, transform: `scale(${1 - 0.04 * Math.sin(Math.PI * Math.min(1, press))})`, ...style}}>{children}</div>
);

// ---------------------------------------------------------------- library
export type Card = {key: string; src: string; dur: number; tags: string[]};
export type CardPose = {x: number; y: number; w: number; h: number; o: number; sel?: number};
/** The library grid: content area x 308..1944. Five columns of 16:9 cards. */
export const GRID = {x0: 308, y0: 104, w: 316, h: 178, gap: 14, cols: 5};
export const gridSlot = (i: number) => ({x: GRID.x0 + (i % GRID.cols) * (GRID.w + GRID.gap), y: GRID.y0 + Math.floor(i / GRID.cols) * (GRID.h + GRID.gap), w: GRID.w, h: GRID.h});

export const LibraryView: React.FC<{cards: Card[]; poses: CardPose[]; count: string}> = ({cards, poses, count}) => (
  <div style={{position: 'absolute', left: SIDEBAR, top: 0, right: 0, bottom: 0, padding: '40px 56px', fontFamily: UI, color: T.chalk}}>
    <Head name="Library" right={
      <div style={{display: 'flex', alignItems: 'center', gap: 22, fontSize: 13, fontWeight: 500, color: T.s300}}>
        <span>{count}</span><span>Images <span style={mono(11, T.s400)}>53</span></span>
        <span style={{display: 'flex', gap: 2, background: T.g800, borderRadius: 12, padding: 3}}>
          <span style={{padding: '4px 10px', borderRadius: 8, background: T.g700, color: T.chalk}}>All</span><span style={{padding: '4px 10px'}}>Favourites <span style={mono(11, T.s400)}>46</span></span>
        </span>
        <span style={{display: 'flex', alignItems: 'center', gap: 6}}><SlidersHorizontal {...ico} size={14} />Filter</span>
        <span style={{display: 'flex', gap: 8, color: T.s400}}><LayoutGrid {...ico} color={T.chalk} /><List {...ico} /></span>
        <ArrowUpDown {...ico} />
        <PrimaryButton><Plus size={14} strokeWidth={2.2} />Add reference</PrimaryButton>
      </div>} />
    {cards.map((c, i) => {
      const p = poses[i];
      if (p.o <= 0.001) return null;
      return (
        <div key={c.key} style={{position: 'absolute', left: p.x - SIDEBAR, top: p.y, width: p.w, height: p.h, opacity: p.o, borderRadius: 12, overflow: 'hidden', background: T.g900,
          boxShadow: p.sel ? `0 0 0 ${1.5 + 1.5 * p.sel}px ${T.volt}` : `0 0 0 1px ${T.g700}`}}>
          <Frame src={c.src} />
          {(p.sel ?? 0) > 0 && <div style={{position: 'absolute', inset: 0, background: T.voltTint, opacity: p.sel}} />}
          <span style={{position: 'absolute', left: 6, top: 6, padding: '1px 5px', borderRadius: 4, background: 'rgba(0,0,0,0.62)', ...mono(10.5, T.chalk)}}>{c.dur.toFixed(2)}s</span>
          <span style={{position: 'absolute', right: 8, top: 8, width: 22, height: 22, borderRadius: 6, background: 'rgba(0,0,0,0.45)', display: 'grid', placeItems: 'center'}}>
            <Heart size={12} strokeWidth={2} color={T.chalk} fill={(p.sel ?? 0) > 0.5 ? T.chalk : 'none'} /></span>
        </div>
      );
    })}
  </div>
);

// ---------------------------------------------------------------- boards
export type Beat = {n: number; tc: string; name: string; scene: string; title: string; copy: string; secs: number; src: string};
export type RowState = {o: number; text: number; copyShown?: string; caret?: boolean; focus?: number; flash?: number; grow?: number};
export const ROW = {x: 308, y0: 372, h: 168, thumbX: 364, thumbW: 200, thumbH: 112.5, textX: 588};
export const rowThumb = (i: number) => ({x: ROW.thumbX, y: ROW.y0 + i * ROW.h + 20, w: ROW.thumbW, h: ROW.thumbH});

export const BoardsView: React.FC<{beats: Beat[]; rows: RowState[]; meta: string; showThumbs?: boolean; scroll?: number; children?: React.ReactNode}> = ({beats, rows, meta, showThumbs = true, scroll = 0, children}) => (
  <div style={{position: 'absolute', left: SIDEBAR, top: 0, right: 0, height: 2400, padding: '40px 56px', fontFamily: UI, color: T.chalk, transform: `translateY(${-scroll}px)`}}>
    <Head crumb="Boards" name="Spliced: how it works" meta={meta} right={<><PrimaryButton><Copy size={13} strokeWidth={2.2} />Copy build prompt</PrimaryButton><Ellipsis {...ico} color={T.s300} style={{marginLeft: 18}} /></>} />
    <div style={{fontSize: 22, fontWeight: 500, lineHeight: 1.32, maxWidth: 940, letterSpacing: '-0.01em'}}>Spliced turns the films we love into named, reusable moves, and builds new films from them.</div>
    <div style={{fontSize: 13.5, color: T.s300, marginTop: 12}}>People new to Spliced</div>
    <div style={{display: 'flex', alignItems: 'center', gap: 10, fontSize: 13.5, color: T.s300, marginTop: 20}}>
      16:9<span>·</span>40s<span>·</span>profile <b style={{color: T.chalk, fontWeight: 600}}>splice</b>
      <span style={{width: 72, height: 4, borderRadius: 2, background: T.chalk, marginLeft: 8}} /><span style={{display: 'flex', alignItems: 'center', gap: 6, marginLeft: 20, color: T.chalk}}><Pencil size={14} strokeWidth={1.75} />Edit brief</span>
    </div>
    <div style={{position: 'absolute', left: ROW.x - SIDEBAR, right: 56, top: ROW.y0 - 1, height: 1, background: T.g700}} />
    {beats.map((b, i) => {
      const r = rows[i];
      if (!r || r.o <= 0.001) return null;
      const g = r.grow ?? 1;
      const flash = r.flash ?? 0;
      return (
        <div key={b.n} style={{position: 'absolute', left: ROW.x - SIDEBAR, right: 56, top: ROW.y0 + i * ROW.h, height: ROW.h * g, overflow: 'hidden', opacity: r.o,
          borderBottom: `1px solid ${T.g700}`, borderRadius: flash ? 10 : 0,
          boxShadow: flash ? `0 0 0 2px rgba(255,176,32,${flash}), 0 0 30px rgba(255,176,32,${0.35 * flash})` : 'none'}}>
          <div style={{position: 'absolute', left: 0, top: 22, width: 34, textAlign: 'center', ...mono(13, T.s300), opacity: r.text}}>{b.n}<div style={{...mono(11, T.s400), marginTop: 4}}>{b.tc}</div></div>
          {showThumbs && <div style={{position: 'absolute', left: ROW.thumbX - ROW.x, top: 20, width: ROW.thumbW, height: ROW.thumbH, borderRadius: 8, overflow: 'hidden', boxShadow: `0 0 0 1px ${T.g700}`}}><Frame src={b.src} /></div>}
          <div style={{position: 'absolute', left: ROW.textX - ROW.x, right: 80, top: 18, opacity: r.text, transform: `translateY(${8 * (1 - r.text)}px)`}}>
            <div style={{fontSize: 16, fontWeight: 600, letterSpacing: '-0.012em'}}>{b.name}</div>
            <div style={{fontSize: 13, color: T.s300, marginTop: 6, whiteSpace: 'nowrap', overflow: 'hidden'}}>{b.title} <span style={mono(12, T.s400)}>· {b.scene}</span></div>
            <div style={{display: 'grid', gridTemplateColumns: '96px 1fr', marginTop: 16, alignItems: 'baseline', fontSize: 14}}>
              <span style={{fontSize: 12.5, color: T.s400}}>On screen</span>
              <span style={{position: 'relative', padding: '5px 10px', marginLeft: -10, borderRadius: 8, boxShadow: r.focus ? `inset 0 0 0 1px rgba(223,255,26,${r.focus}), 0 0 0 3px rgba(223,255,26,${0.14 * r.focus})` : 'none'}}>
                {r.copyShown ?? b.copy}{r.caret && <span style={{display: 'inline-block', width: 1.5, height: 17, background: T.volt, marginLeft: 1, verticalAlign: -3}} />}
              </span>
            </div>
          </div>
          <div style={{position: 'absolute', right: 0, top: 22, ...mono(13, T.s300), opacity: r.text}}>{b.secs.toFixed(1)}s</div>
        </div>
      );
    })}
    {children}
  </div>
);

export const Toast: React.FC<{text: React.ReactNode; k: number; style?: React.CSSProperties}> = ({text, k, style}) => k <= 0 ? null : (
  <div style={{position: 'absolute', display: 'flex', alignItems: 'center', gap: 12, padding: '16px 22px', borderRadius: 16, background: T.g700, color: T.chalk,
    boxShadow: `${T.pop}, 0 0 0 1px ${T.g600}`, fontFamily: UI, fontSize: 17, fontWeight: 500, opacity: Math.min(1, k), transform: `translateY(${12 * (1 - Math.min(1, k))}px)`, ...style}}>
    <span style={{width: 8, height: 8, borderRadius: 4, background: T.success}} />{text}
  </div>
);

// ---------------------------------------------------------------- build
export type BarBeat = {n: number; name: string; dur: number};
/** The Build view. `render` and `reference` are the two players' contents (16:9 boxes). */
export const BUILD = {px: 308, top: 236, gap: 16, w: 810, h: 456};
export const BuildView: React.FC<{render: React.ReactNode; reference: React.ReactNode; bar: BarBeat[]; playhead: number; selBeat: number; tc: string; refLabel: string;
  pins?: {at: number; k: number}[]; thumbs: string[]}> = ({render, reference, bar, playhead, selBeat, tc, refLabel, pins = [], thumbs}) => {
  const total = bar.reduce((a, b) => a + b.dur, 0);
  const barW = 1636, gap = 6;
  let acc = 0;
  return (
    <div style={{position: 'absolute', left: SIDEBAR, top: 0, right: 0, bottom: 0, padding: '34px 56px', fontFamily: UI, color: T.chalk}}>
      <Head crumb="Build" name="Spliced: how it works" right={<span style={{display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: T.s400}}><MessageSquarePlus {...ico} size={14} />Copy notes prompt</span>} />
      <div style={{marginTop: -16, fontSize: 13.5, color: T.s300}}><b style={{color: T.chalk, fontWeight: 600}}>v1</b> · just now · First full cut: nine beats on the splice profile</div>
      <div style={{position: 'absolute', left: BUILD.px - SIDEBAR, top: BUILD.top - 24, ...label(11)}}>Render <span style={{color: T.s300, marginLeft: 4}}>v1</span></div>
      <div style={{position: 'absolute', left: BUILD.px - SIDEBAR + BUILD.w + BUILD.gap, top: BUILD.top - 24, ...label(11), whiteSpace: 'nowrap'}}>Reference <span style={{...mono(11, T.chalk), textTransform: 'none', letterSpacing: 0, marginLeft: 6}}>{refLabel}</span></div>
      {[render, reference].map((c, i) => (
        <div key={i} style={{position: 'absolute', left: BUILD.px - SIDEBAR + i * (BUILD.w + BUILD.gap), top: BUILD.top, width: BUILD.w, height: BUILD.h, borderRadius: 12, overflow: 'hidden', background: T.ink, boxShadow: `0 0 0 1px ${T.g700}`}}>{c}</div>
      ))}
      <div style={{position: 'absolute', left: BUILD.px - SIDEBAR, width: barW, top: BUILD.top + BUILD.h + 14, height: 32, display: 'flex', alignItems: 'center', gap: 14, fontSize: 13, color: T.s300}}>
        <Play {...ico} color={T.chalk} /><StepBack {...ico} /><StepForward {...ico} />
        <span style={mono(13, T.chalk)}>{tc}</span>
        <span style={{...mono(13, T.s300), marginLeft: 30}}>beat {selBeat + 1} · {bar[selBeat]?.name.toLowerCase()}</span>
        <span style={{flex: 1}} />
        <span style={{padding: '4px 10px', borderRadius: 8, background: T.g800, color: T.chalk}}>Loop beat</span><span>Play through</span>
        <span style={{display: 'flex', alignItems: 'center', gap: 6, marginLeft: 8}}><Repeat {...ico} size={14} />Ref synced</span>
        <span style={{display: 'flex', alignItems: 'center', gap: 6, marginLeft: 8}}><MessageSquarePlus {...ico} size={14} />Note</span>
        <span style={{display: 'flex', alignItems: 'center', gap: 6}}><GitCompare {...ico} size={14} />Compare</span>
        <VolumeX {...ico} size={14} /><Maximize {...ico} size={14} />
      </div>
      <div style={{position: 'absolute', left: BUILD.px - SIDEBAR, width: barW, top: BUILD.top + BUILD.h + 70, height: 34}}>
        {bar.map((b, i) => {
          const x = (acc / total) * barW, w = (b.dur / total) * barW - gap;
          acc += b.dur;
          const sel = i === selBeat;
          return (
            <div key={b.n} style={{position: 'absolute', left: x, width: w, top: 0, height: 34, borderRadius: 6, background: sel ? T.voltTint : T.g800,
              boxShadow: sel ? `inset 0 0 0 1.5px ${T.volt}` : 'none', ...mono(12, sel ? T.chalk : T.s300), display: 'flex', alignItems: 'center', paddingLeft: 8, whiteSpace: 'nowrap', overflow: 'hidden'}}>
              {b.n}<span style={{fontFamily: UI, marginLeft: 6, color: sel ? T.chalk : T.s400}}>{b.name.toLowerCase()}</span>
            </div>
          );
        })}
        {pins.map((p, i) => p.k > 0 && (
          <svg key={i} width={18} height={22} viewBox="0 0 18 22" style={{position: 'absolute', left: p.at * barW - 9, top: -26 - 8 * (1 - p.k), opacity: Math.min(1, p.k * 1.5)}}>
            <path d="M9 21c-1-2-7-7-7-12a7 7 0 0 1 14 0c0 5-6 10-7 12z" fill="none" stroke={T.danger} strokeWidth={2} />
          </svg>
        ))}
        <div style={{position: 'absolute', left: playhead * barW - 1, top: -6, width: 2, height: 46, background: T.volt}}>
          <div style={{position: 'absolute', top: -4, left: -4, width: 10, height: 6, borderRadius: '3px 3px 1px 1px', background: T.volt}} />
        </div>
        <div style={{position: 'absolute', left: 0, top: 44, ...mono(11, T.s400)}}>0:00</div>
        <div style={{position: 'absolute', right: 0, top: 44, ...mono(11, T.s400)}}>0:{total.toFixed(2).padStart(5, '0')}</div>
      </div>
      <div style={{position: 'absolute', left: BUILD.px - SIDEBAR, top: BUILD.top + BUILD.h + 148, display: 'flex', gap: 12}}>
        {thumbs.map((s, i) => (
          <div key={i} style={{width: 168, borderRadius: 10, padding: 5, background: T.g900, boxShadow: i === selBeat ? `0 0 0 1.5px ${T.volt}` : `0 0 0 1px ${T.g700}`}}>
            <div style={{height: 88, borderRadius: 6, overflow: 'hidden'}}><Frame src={s} /></div>
            <div style={{display: 'flex', alignItems: 'center', gap: 6, padding: '7px 3px 2px', fontSize: 12, color: T.chalk, whiteSpace: 'nowrap', overflow: 'hidden'}}>
              <span style={{width: 8, height: 8, borderRadius: 4, border: `2px solid ${i === selBeat ? T.warning : T.success}`}} />{i + 1} {bar[i]?.name.toLowerCase()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/** A note being written on a frame (the Build view's compose box). */
export const NoteCompose: React.FC<{k: number; text: string; caret: boolean; tc: string; style?: React.CSSProperties}> = ({k, text, caret, tc, style}) => k <= 0 ? null : (
  <div style={{position: 'absolute', width: 380, padding: '14px 16px', borderRadius: 16, background: T.g700, boxShadow: `${T.pop}, 0 0 0 1px ${T.g700}`, fontFamily: UI, color: T.chalk,
    opacity: Math.min(1, k), transform: `translateY(${10 * (1 - Math.min(1, k))}px) scale(${0.98 + 0.02 * Math.min(1, k)})`, transformOrigin: 'bottom left', ...style}}>
    <div style={{display: 'flex', alignItems: 'center', gap: 8, ...label(11)}}><span style={{width: 8, height: 8, borderRadius: 4, background: T.danger}} />Note at <span style={{...mono(11, T.chalk), letterSpacing: 0}}>{tc}</span></div>
    <div style={{marginTop: 10, fontSize: 15, lineHeight: 1.45, minHeight: 22}}>{text}{caret && <span style={{display: 'inline-block', width: 1.5, height: 17, background: T.volt, marginLeft: 1, verticalAlign: -3}} />}</div>
    <div style={{display: 'flex', justifyContent: 'flex-end', marginTop: 12}}><PrimaryButton>Save note</PrimaryButton></div>
  </div>
);

// ---------------------------------------------------------------- add references
export type Step = 'todo' | 'cur' | 'done';
export const AddSheet: React.FC<{link: string; focus: number; press: number; job: number; steps: Step[]; loaderT: number; selectAll?: number}> = ({link, focus, press, job, steps, loaderT}) => (
  <div style={{width: 760, borderRadius: 16, background: T.g700, boxShadow: `${T.pop}, 0 0 0 1px ${T.g600}`, fontFamily: UI, color: T.chalk, padding: '22px 24px 20px'}}>
    <div style={{display: 'flex', alignItems: 'center'}}><div style={{fontSize: 18, fontWeight: 600, flex: 1}}>Add references</div><X {...ico} color={T.s300} /></div>
    <div style={{marginTop: 8, fontSize: 13.5, lineHeight: 1.5, color: T.s300}}>Paste links or drop files. A film link (YouTube, Vimeo, X) is downloaded and broken down scene by scene; images, GIFs and clips are added as they are and analysed. Everything lands in the Library.</div>
    <div style={{marginTop: 16, borderRadius: 12, background: T.ink, overflow: 'hidden',
      boxShadow: focus > 0 ? `inset 0 0 0 1px ${T.volt}, 0 0 0 3px rgba(223,255,26,${0.14 * focus})` : `inset 0 0 0 1px ${T.g600}`}}>
      <div style={{padding: '12px 14px', height: 78, fontSize: 15, color: link ? T.chalk : T.s400, fontFamily: link ? MONO : UI}}>{link || 'Paste links, one per line'}{focus > 0.5 && <span style={{display: 'inline-block', width: 1.5, height: 17, background: T.volt, marginLeft: 1, verticalAlign: -3}} />}</div>
      <div style={{display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px 10px 14px', borderTop: `1px dashed ${T.g600}`, fontSize: 13, color: T.s300}}><Upload {...ico} size={15} />Drop images, GIFs or clips here, or<span style={{flex: 1}} />
        <span style={{padding: '5px 12px', borderRadius: 8, border: `1px solid ${T.g600}`, color: T.chalk, fontWeight: 500}}>Choose files</span></div>
    </div>
    <div style={{display: 'flex', alignItems: 'center', gap: 12, marginTop: 14, fontSize: 13.5, color: T.chalk}}>
      <span style={{color: T.s300}}>Name</span>
      <span style={{flex: 1, height: 32, display: 'flex', alignItems: 'center', padding: '0 11px', borderRadius: 8, background: T.ink, boxShadow: `inset 0 0 0 1px ${T.g600}`, color: T.s400, fontSize: 13}}>brand-what, e.g. acme-launch-2026 (optional)</span>
      <span style={{width: 16, height: 16, borderRadius: 4, background: T.volt, display: 'grid', placeItems: 'center', marginLeft: 8}}><Check size={12} strokeWidth={3} color={T.ink} /></span>Break it down with Claude
    </div>
    <div style={{display: 'flex', alignItems: 'center', marginTop: 16}}>
      <span style={{flex: 1, fontSize: 12.5, color: T.s400}}>Runs in the background, about 10 to 15 minutes a film. You can close this.</span>
      <PrimaryButton press={press} style={{height: 34, padding: '0 16px', fontSize: 14}}><Plus size={15} strokeWidth={2.2} />Add</PrimaryButton>
    </div>
    {job > 0 && (
      <div style={{marginTop: 18, paddingTop: 16 * Math.min(1, job), borderTop: `1px solid ${T.g600}`, opacity: Math.min(1, job), height: 92 * Math.min(1, job), overflow: 'hidden'}}>
        <div style={{display: 'flex', alignItems: 'baseline', gap: 10}}>
          <b style={{fontSize: 14, fontWeight: 600}}>Plan it together</b><span style={mono(12, T.s400)}>acme-plan-it-together</span>
          <span style={{flex: 1}} /><span style={mono(12, T.s300)}>{steps.every((s) => s === 'done') ? 'done' : 'running'}</span>
        </div>
        <div style={{display: 'flex', gap: 22, marginTop: 14, fontSize: 13}}>
          {['Download', 'Analyse', 'Break down', 'Add to library'].map((l, i) => (
            <span key={l} style={{display: 'flex', alignItems: 'center', gap: 8, color: steps[i] === 'todo' ? T.s400 : T.chalk}}>
              {steps[i] === 'done' ? <span style={{width: 16, height: 16, borderRadius: 8, background: T.success, display: 'grid', placeItems: 'center'}}><Check size={11} strokeWidth={3} color={T.ink} /></span>
                : steps[i] === 'cur' ? <Loader t={loaderT} width={20} /> : <span style={{width: 14, height: 14, borderRadius: 7, border: `1.5px solid ${T.s500}`}} />}
              {l}
            </span>
          ))}
        </div>
      </div>
    )}
  </div>
);

/** The brand loader: the four blocks sink and rise in a staggered wave (splice-loader-*.svg, 2.4s, ease-in-out). */
export const Loader: React.FC<{t: number; width: number}> = ({t, width}) => {
  const rise = [0, 1, 2, 3].map((i) => {
    const ph = (((t + [0.6, 0, 1.2, 1.8][i]) / 2.4) % 1 + 1) % 1; // each block's phase in the wave
    return 0.0714 + 0.9286 * (0.5 + 0.5 * Math.cos(ph * 2 * Math.PI)); // sinks to 3 of 42 units, like the svg
  });
  return <SpliceMark width={width} rise={rise} />;
};

/** macOS arrow cursor in screen space, with a click squash. */
export const Cursor: React.FC<{x: number; y: number; press?: number; o?: number}> = ({x, y, press = 0, o = 1}) => o <= 0 ? null : (
  <svg width={34} height={40} viewBox="0 0 17 20" style={{position: 'absolute', left: x - 3, top: y - 2, opacity: o, transform: `scale(${1 - 0.12 * press})`, transformOrigin: '3px 2px', filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.5))'}}>
    <path d="M1.5 1.5v14.2l3.6-3.4 2.3 5.3 2.4-1-2.3-5.2h5z" fill="#111" stroke="#fff" strokeWidth={1.2} strokeLinejoin="round" />
  </svg>
);

export {Play};
