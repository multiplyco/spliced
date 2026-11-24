// Specimen reel for the motion systems: every curve, spring, transition pattern, symbol effect
// and the Liquid Glass material, side by side. Composition "Specimen-MotionSystems" (17s, 30fps).
// It is the visual reference for docs/MOTION-SYSTEMS.md, not a film.
import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {Bell, Check, CircleCheck, Heart, Loader, Sparkles, Star, Wand2} from 'lucide-react';
import {display, ui} from './type';
import {
  M3_EASING, m3Seconds, m3SpringAt, appleSpringAt, symbolFX, SharedAxis, FadeThrough, ContainerTransform, LiquidGlass,
  lerp, clamp01,
} from '../lib/motion';

const INK = '#0B152B', MUTED = 'rgba(11,21,43,0.45)', LINE = 'rgba(11,21,43,0.10)', ACCENT = '#5B47E0', BG = '#F5F3EF';
export const SPECIMEN = {fps: 30, duration: 17};

const Kicker: React.FC<{children: React.ReactNode; t: number; at: number}> = ({children, t, at}) => (
  <div style={{position: 'absolute', left: 120, top: 84, font: `500 22px ${ui}`, letterSpacing: '0.14em', textTransform: 'uppercase', color: MUTED,
    opacity: clamp01((t - at) / 0.3)}}>{children}</div>
);
const Title: React.FC<{children: React.ReactNode; t: number; at: number}> = ({children, t, at}) => {
  const k = M3_EASING.emphasizedDecelerate(clamp01((t - at) / 0.6));
  return <div style={{position: 'absolute', left: 120, top: 120, font: `500 76px ${display}`, letterSpacing: '-0.035em', color: INK, opacity: k, transform: `translateY(${(1 - k) * 24}px)`}}>{children}</div>;
};

// ---------- A: curves and springs ----------
const CURVES: {label: string; sub: string; f: (t: number, s: number) => number}[] = [
  {label: 'M3 standard', sub: 'cubic-bezier(0.2, 0, 0, 1)', f: (t, s) => M3_EASING.standard(clamp01((t - s) / m3Seconds('long2')))},
  {label: 'M3 emphasized', sub: 'two-segment path', f: (t, s) => M3_EASING.emphasized(clamp01((t - s) / m3Seconds('long2')))},
  {label: 'M3 emphasized decelerate', sub: '(0.05, 0.7, 0.1, 1)', f: (t, s) => M3_EASING.emphasizedDecelerate(clamp01((t - s) / m3Seconds('long2')))},
  {label: 'M3 expressive spring', sub: 'default spatial · ζ 0.8 · k 380', f: (t, s) => m3SpringAt(t, s, 'defaultSpatial', 'expressive')},
  {label: 'M3 expressive spring', sub: 'fast spatial · ζ 0.6 · k 800', f: (t, s) => m3SpringAt(t, s, 'fastSpatial', 'expressive')},
  {label: 'Apple smooth', sub: 'duration 0.5 · bounce 0', f: (t, s) => appleSpringAt(t, s, 'smooth')},
  {label: 'Apple snappy', sub: 'duration 0.5 · bounce 0.15', f: (t, s) => appleSpringAt(t, s, 'snappy')},
  {label: 'Apple bouncy', sub: 'duration 0.5 · bounce 0.3', f: (t, s) => appleSpringAt(t, s, 'bouncy')},
];
const Curves: React.FC<{t: number}> = ({t}) => {
  const go = 0.9, back = 2.5;
  return (
    <AbsoluteFill>
      <Kicker t={t} at={0}>Material 3 · Apple</Kicker>
      <Title t={t} at={0.1}>Curves and springs</Title>
      {CURVES.map((c, i) => {
        const y = 300 + i * 88;
        const p = t < back ? c.f(t, go) : 1 - c.f(t, back);
        const x0 = 760, x1 = 1760;
        return (
          <div key={i} style={{opacity: clamp01((t - 0.2 - i * 0.04) / 0.3)}}>
            <div style={{position: 'absolute', left: 120, top: y - 22, font: `500 28px ${ui}`, color: INK}}>{c.label}</div>
            <div style={{position: 'absolute', left: 120, top: y + 14, font: `400 19px ${ui}`, color: MUTED}}>{c.sub}</div>
            <div style={{position: 'absolute', left: x0, top: y, width: x1 - x0, height: 2, background: LINE}} />
            <div style={{position: 'absolute', left: x1, top: y - 10, width: 2, height: 22, background: LINE}} />
            <div style={{position: 'absolute', left: lerp(x0, x1, p) - 14, top: y - 13, width: 28, height: 28, borderRadius: 14, background: i < 3 ? INK : i < 5 ? ACCENT : '#E8613C'}} />
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------- B: M3 transition patterns ----------
export const Screen: React.FC<{hue: string; title: string; rows?: number}> = ({hue, title, rows = 4}) => (
  <div style={{position: 'absolute', inset: 0, background: '#fff', padding: 24, fontFamily: ui}}>
    <div style={{display: 'flex', alignItems: 'center', gap: 12}}>
      <div style={{width: 40, height: 40, borderRadius: 12, background: hue}} />
      <div style={{font: `600 22px ${ui}`, color: INK}}>{title}</div>
    </div>
    {Array.from({length: rows}).map((_, i) => (
      <div key={i} style={{marginTop: 18, height: 16, width: `${90 - i * 14}%`, borderRadius: 8, background: i === 0 ? hue : 'rgba(11,21,43,0.08)', opacity: i === 0 ? 0.35 : 1}} />
    ))}
  </div>
);
const Tile: React.FC<{x: number; label: string; sub: string; t: number; children: React.ReactNode}> = ({x, label, sub, t, children}) => (
  <div style={{opacity: clamp01((t - 4.2) / 0.4)}}>
    <div style={{position: 'absolute', left: x, top: 330, width: 380, height: 460, borderRadius: 28, background: '#ECE9E3', overflow: 'hidden'}}>{children}</div>
    <div style={{position: 'absolute', left: x, top: 810, font: `500 26px ${ui}`, color: INK}}>{label}</div>
    <div style={{position: 'absolute', left: x, top: 846, font: `400 19px ${ui}`, color: MUTED}}>{sub}</div>
  </div>
);
const Transitions: React.FC<{t: number}> = ({t}) => {
  const a = 5.0, b = 6.9; // forward at a, back at b
  const pane = {position: 'absolute' as const, left: 30, top: 30, width: 320, height: 400, borderRadius: 20, overflow: 'hidden' as const};
  const S1 = <Screen hue="#5B47E0" title="Workspace" />, S2 = <Screen hue="#E8613C" title="Brief" rows={3} />;
  const fwd = t < b;
  return (
    <AbsoluteFill>
      <Kicker t={t} at={4.0}>Material 3 · transition patterns</Kicker>
      <Title t={t} at={4.1}>Four ways to change view</Title>
      <Tile x={120} t={t} label="Container transform" sub="a card becomes the next screen">
        <div style={{position: 'absolute', inset: 0}}>
          <ContainerTransform t={t} start={fwd ? a : b} from={fwd ? <Chip /> : <Screen hue="#E8613C" title="Brief" rows={3} />} to={fwd ? <Screen hue="#E8613C" title="Brief" rows={3} /> : <Chip />}
            fromBox={fwd ? {x: 60, y: 330, w: 260, h: 72, r: 36} : {x: 30, y: 30, w: 320, h: 400, r: 20}}
            toBox={fwd ? {x: 30, y: 30, w: 320, h: 400, r: 20} : {x: 60, y: 330, w: 260, h: 72, r: 36}}
            fromSize={fwd ? {w: 260, h: 72} : {w: 320, h: 400}} toSize={fwd ? {w: 320, h: 400} : {w: 260, h: 72}} />
        </div>
      </Tile>
      <Tile x={555} t={t} label="Shared axis · X" sub="next / previous step">
        <SharedAxis t={t} start={fwd ? a : b} axis="x" back={!fwd} from={fwd ? S1 : S2} to={fwd ? S2 : S1} style={pane} />
      </Tile>
      <Tile x={990} t={t} label="Shared axis · Z" sub="into / out of a level">
        <SharedAxis t={t} start={fwd ? a : b} axis="z" back={!fwd} from={fwd ? S1 : S2} to={fwd ? S2 : S1} style={pane} />
      </Tile>
      <Tile x={1425} t={t} label="Fade through" sub="unrelated views">
        <FadeThrough t={t} start={fwd ? a : b} from={fwd ? S1 : S2} to={fwd ? S2 : S1} style={pane} />
      </Tile>
    </AbsoluteFill>
  );
};
export const Chip: React.FC = () => (
  <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', gap: 12, padding: '0 22px', background: '#fff', font: `600 22px ${ui}`, color: INK}}>
    <div style={{width: 34, height: 34, borderRadius: 17, background: '#E8613C'}} />Open brief
  </div>
);

// ---------- C: symbol effects ----------
const Effects: React.FC<{t: number}> = ({t}) => {
  const base = 9.0;
  const rep = (period: number, off = 0) => base + off + Math.floor(Math.max(0, t - base - off) / period) * period;
  const items: {label: string; icon: React.ReactNode; fx: ReturnType<typeof symbolFX.bounce>; extra?: React.ReactNode}[] = [
    {label: 'bounce', icon: <Bell size={72} />, fx: symbolFX.bounce(t, rep(1.1, 0.3))},
    {label: 'pulse', icon: <Loader size={72} />, fx: symbolFX.pulse(t, base)},
    {label: 'breathe', icon: <Heart size={72} />, fx: symbolFX.breathe(t, base)},
    {label: 'wiggle', icon: <Sparkles size={72} />, fx: symbolFX.wiggle(t, rep(1.1, 0.5))},
    {label: 'rotate', icon: <Loader size={72} />, fx: symbolFX.rotate(t, base)},
    {label: 'appear', icon: <Star size={72} />, fx: symbolFX.appear(t, rep(1.1, 0.2))},
  ];
  const rs = rep(1.4, 0.4), phase = Math.floor(Math.max(0, t - base - 0.4) / 1.4) % 2;
  return (
    <AbsoluteFill>
      <Kicker t={t} at={8.6}>Apple-style · symbol effects (on our own icons)</Kicker>
      <Title t={t} at={8.7}>Icons that react</Title>
      {[...items, {label: 'replace', icon: null, fx: symbolFX.bounce(-1, 0)}].map((it, i) => {
        const x = 150 + i * 240;
        return (
          <div key={i} style={{opacity: clamp01((t - 8.8 - i * 0.05) / 0.3)}}>
            <div style={{position: 'absolute', left: x, top: 420, width: 180, height: 180, borderRadius: 40, background: '#fff', display: 'grid', placeItems: 'center', color: INK}}>
              {it.icon ? <div style={{...it.fx, display: 'grid'}}>{it.icon}</div> : (
                <div style={{position: 'relative', width: 72, height: 72}}>
                  <div style={{position: 'absolute', inset: 0, ...symbolFX.replace(t, rs, 'out')}}>{phase ? <CircleCheck size={72} /> : <Wand2 size={72} />}</div>
                  <div style={{position: 'absolute', inset: 0, ...symbolFX.replace(t, rs, 'in'), color: phase ? INK : '#1F8A4C'}}>{phase ? <Wand2 size={72} /> : <CircleCheck size={72} />}</div>
                </div>
              )}
            </div>
            <div style={{position: 'absolute', left: x, top: 630, width: 180, textAlign: 'center', font: `500 26px ${ui}`, color: INK}}>{it.label}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------- D: Liquid Glass ----------
export const GlassBackdrop: React.FC<{t: number}> = ({t}) => (
  <div style={{position: 'absolute', inset: 0, background: '#EDEAF6', overflow: 'hidden'}}>
    {[['#7B61FF', 380, 300, 0], ['#FF7A45', 1500, 260, 1.7], ['#22B8A7', 1150, 860, 3.1], ['#FFC94D', 420, 900, 4.4]].map(([c, x, y, k], i) => (
      <div key={i} style={{position: 'absolute', left: (x as number) - 380 + Math.sin(t * 0.5 + (k as number)) * 120, top: (y as number) - 380 + Math.cos(t * 0.4 + (k as number)) * 90,
        width: 760, height: 760, borderRadius: '50%', background: c as string, filter: 'blur(90px)', opacity: 0.75}} />
    ))}
    {[0, 1, 2, 3].map((r) => (
      <div key={r} style={{position: 'absolute', left: -400 - ((t * (90 + r * 25)) % 900), top: 120 + r * 230, whiteSpace: 'nowrap', font: `600 150px ${display}`, letterSpacing: '-0.04em',
        color: r % 2 ? 'rgba(11,21,43,0.85)' : '#fff'}}>
        {'Notes · Plans · Drafts · Reviews · Launches · '.repeat(3)}
      </div>
    ))}
  </div>
);
const Glass: React.FC<{t: number}> = ({t}) => {
  const s = t - 11.0;
  const grow = appleSpringAt(s, 0.2, {duration: 0.7, bounce: 0.25});
  const split = appleSpringAt(s, 1.5, {duration: 0.9, bounce: 0.2});
  const card = M3_EASING.emphasized(clamp01((s - 3.0) / 1.2));
  const rejoin = appleSpringAt(s, 3.0, {duration: 1.0, bounce: 0.15});
  const pill = {cx: 960, cy: lerp(820, 560, card), w: lerp(560, 760, card) * Math.max(0.05, grow), h: lerp(124, 380, card) * Math.max(0.05, grow), r: lerp(62, 56, card)};
  const bx = pill.cx + pill.w / 2 - 70 + lerp(0, 260, split) * (1 - rejoin);
  const bubble = {cx: bx, cy: pill.cy + lerp(0, -40, split) * (1 - rejoin), w: 140 * grow, h: 140 * grow, r: 70};
  const shapes = s < 1.5 ? [pill] : [pill, bubble];
  const label = clamp01((s - 4.3) / 0.5);
  return (
    <AbsoluteFill>
      <GlassBackdrop t={t} />
      <LiquidGlass shapes={shapes} backdrop={() => <GlassBackdrop t={t} />} blend={70} refraction={42} bevel={40} frost={6} />
      <div style={{position: 'absolute', left: 960 - 300, top: 520, width: 600, textAlign: 'center', font: `500 44px ${display}`, color: INK, opacity: label, letterSpacing: '-0.02em'}}>
        <Check size={40} style={{verticalAlign: '-6px', marginRight: 10}} />Brief ready
      </div>
      <div style={{position: 'absolute', left: 120, top: 84, padding: '10px 20px', borderRadius: 999, background: 'rgba(255,255,255,0.7)', font: `500 22px ${ui}`, letterSpacing: '0.14em', textTransform: 'uppercase', color: INK}}>
        Liquid-Glass-style material · pill, split, merge, morph
      </div>
    </AbsoluteFill>
  );
};

/** For tuning the glass alone (composition "Specimen-Glass"). */
export const GlassSpecimen: React.FC = () => {
  const f = useCurrentFrame(), {fps} = useVideoConfig();
  return <Glass t={11 + f / fps} />;
};

export const MotionSystems: React.FC = () => {
  const f = useCurrentFrame(), {fps} = useVideoConfig();
  const t = f / fps;
  const fadeTo = (a: number, b: number) => clamp01((t - a) / 0.35) * (1 - clamp01((t - b) / 0.35));
  return (
    <AbsoluteFill style={{background: BG}}>
      {t < 4.3 && <AbsoluteFill style={{opacity: fadeTo(-1, 3.9)}}><Curves t={t} /></AbsoluteFill>}
      {t > 3.9 && t < 8.9 && <AbsoluteFill style={{opacity: fadeTo(3.9, 8.5)}}><Transitions t={t} /></AbsoluteFill>}
      {t > 8.5 && t < 11.3 && <AbsoluteFill style={{opacity: fadeTo(8.5, 10.9)}}><Effects t={t} /></AbsoluteFill>}
      {t > 10.9 && <AbsoluteFill style={{opacity: fadeTo(10.9, 99)}}><Glass t={t} /></AbsoluteFill>}
    </AbsoluteFill>
  );
};

