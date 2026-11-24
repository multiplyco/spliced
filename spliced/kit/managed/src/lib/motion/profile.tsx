// Motion profiles: the semantic layer between film code and the motion systems.
//
// Film code asks for a ROLE (enter, exit, move, ui, emphasis, camera, textReveal, viewChange, idle),
// never a raw curve. A profile maps every role to a token from one system, so a film has one
// motion language and switching it is one line:
//
//   const m = motion('soft');
//   const k = m.enter(t, start);                 // 0..1 progress (springs may overshoot 1)
//   const words = m.textReveal(t, start, i);     // i-th word, staggered by the profile
//   <m.ViewChange t={t} start={cue} from={<A/>} to={<B/>} />
//   m.seconds('enter')                            // how long a role takes, for laying out cues
//
// The built-in profiles are below; a project adds its own in src/profiles.ts (its file, never replaced by
// `spliced kit update`). `npm run check:motion` flags hand-written easing in film code, so motion stays on the profile.
import React from 'react';
import {M3_EASING, m3Spring, type M3Easing} from './material3';
import {KIT_CURVES, sp, tw, type Profile, type ViewChangeKind, type Role, type MotionSpec} from './spec';
import {PROJECT_PROFILES} from '../../profiles';
import {appleSpec} from './apple';
import {clamp01, settleTime, springStep} from './spring';
import {FadeThrough, SharedAxis} from './M3Transitions';

export const BUILT_IN_PROFILES = {
  /** Calm and precise on a white stage: things arrive fast and land soft, the camera is slow, nothing bounces. */
  soft: {
    name: 'soft', feel: 'Calm and precise: arrive fast, land soft, slow camera, never a bounce.',
    roles: {
      enter: tw('land', 0.6, 'kit land (arrive 20%/frame)'),
      exit: tw('emphasizedAccelerate', 0.3, 'M3 emphasized accelerate'),
      move: tw('land', 0.75, 'kit land'),
      ui: tw('land', 0.45, 'kit land'),
      emphasis: tw('land', 0.5, 'kit land'),
      camera: tw('glide', 1.0, 'kit glide (0.32, 0, 0.12, 1)'),
      textReveal: tw('land', 0.5, 'kit land, word sharpen'),
    },
    stagger: 0.1, viewChange: {kind: 'cut', seconds: 0}, idle: 1,
  },
  /** Material 3: emphasized curves, expressive springs, shared-axis view changes. */
  material: {
    name: 'material', feel: 'Precise and editorial: emphasized curves, view changes along an axis.',
    roles: {
      enter: tw('emphasizedDecelerate', 0.8, 'M3 emphasized decelerate · medium4 x2'),
      exit: tw('emphasizedAccelerate', 0.4, 'M3 emphasized accelerate · short4 x2'),
      move: tw('emphasized', 1.0, 'M3 emphasized · long2 x2'),
      ui: sp(m3Spring('defaultSpatial', 'expressive'), 'M3 expressive default spatial (film-slowed)'),
      emphasis: sp(m3Spring('fastSpatial', 'expressive'), 'M3 expressive fast spatial (film-slowed)'),
      camera: tw('emphasized', 1.4, 'M3 emphasized · extraLong1 x2'),
      textReveal: tw('emphasizedDecelerate', 0.6, 'M3 emphasized decelerate · medium2 x2'),
    },
    stagger: 0.05, viewChange: {kind: 'sharedAxisZ', seconds: 0.6}, idle: 0,
  },
  /** Apple-style: springs everywhere, a little bounce on UI, smooth camera. */
  apple: {
    name: 'apple', feel: 'Physical and friendly: springs everywhere, a small bounce on UI.',
    roles: {
      enter: sp(appleSpec({duration: 0.6, bounce: 0}), 'Apple smooth 0.6s'),
      exit: tw('standardAccelerate', 0.3, 'accelerate 0.3s'),
      move: sp(appleSpec({duration: 0.7, bounce: 0}), 'Apple smooth 0.7s'),
      ui: sp(appleSpec({duration: 0.5, bounce: 0.15}), 'Apple snappy'),
      emphasis: sp(appleSpec({duration: 0.6, bounce: 0.3}), 'Apple bouncy 0.6s'),
      camera: sp(appleSpec({duration: 1.1, bounce: 0}), 'Apple smooth 1.1s'),
      textReveal: sp(appleSpec({duration: 0.5, bounce: 0}), 'Apple smooth 0.5s'),
    },
    stagger: 0.06, viewChange: {kind: 'sharedAxisX', seconds: 0.6}, idle: 0.6,
  },
  /**
   * Spliced, the app (Spliced's web/splice-tokens.css): the brand's own curves, film-slowed. Things arrive on
   * ease-out (fast, then a long settle), UI on ease-ui, and anything that rises or sinks (the logo's blocks, the
   * camera) on ease-sink. Words sharpen in. No bounce: the brand's only physical move is the blocks sinking and rising.
   */
  splice: {
    name: 'splice', feel: 'Spliced brand: crisp ease-out arrivals, ease-sink camera and blocks, sharpened words, no bounce.',
    roles: {
      enter: tw('spliceOut', 0.75, 'Spliced ease-out (0.16, 1, 0.3, 1) 0.75s'),
      exit: tw('emphasizedAccelerate', 0.3, 'M3 emphasized accelerate 0.3s'),
      move: tw('spliceOut', 0.85, 'Spliced ease-out 0.85s'),
      ui: tw('spliceUi', 0.4, 'Spliced ease-ui (0.3, 0, 0.2, 1) 0.4s (dur-panel 240ms, film-slowed)'),
      emphasis: tw('spliceSink', 0.9, 'Spliced ease-sink (0.7, 0, 0.2, 1) 0.9s'),
      camera: tw('spliceSink', 1.0, 'Spliced ease-sink 1.0s'),
      textReveal: tw('spliceOut', 0.55, 'Spliced ease-out 0.55s, word sharpen'),
    },
    stagger: 0.07, viewChange: {kind: 'blurThrough', seconds: 0.5}, idle: 0.3,
  },
} satisfies Record<string, Profile>;
/** Every profile a film can name: the built-in ones and this project's own (src/profiles.ts), which win on a clash. */
export const PROFILES = {...BUILT_IN_PROFILES, ...PROJECT_PROFILES};
export type ProfileName = keyof typeof PROFILES;

const curveOf = (c: string) => (c in KIT_CURVES ? KIT_CURVES[c as keyof typeof KIT_CURVES] : M3_EASING[c as M3Easing]);

const hex = (c: string) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
/** Mix two #rrggbb colours (k = 0 gives a, 1 gives b). */
export const mixHex = (a: string, b: string, k: number) => {
  const A = hex(a), B = hex(b), q = Math.max(0, Math.min(1, k));
  return '#' + A.map((v, i) => Math.round(v + (B[i] - v) * q).toString(16).padStart(2, '0')).join('');
};

/** Evaluate a spec: progress of a motion started at `start` (0 before it). */
export const evalSpec = (spec: MotionSpec, t: number, start: number, seconds?: number) =>
  spec.kind === 'spring' ? springStep(t - start, spec.spring) : curveOf(spec.curve)(clamp01((t - start) / (seconds ?? spec.seconds)));

const BlurThrough: React.FC<{t: number; start: number; seconds: number; from: React.ReactNode; to: React.ReactNode; style?: React.CSSProperties}> = ({t, start, seconds, from, to, style}) => {
  const p = clamp01((t - start) / seconds);
  const a = clamp01(p / 0.5), b = M3_EASING.emphasizedDecelerate(clamp01((p - 0.35) / 0.65));
  return (
    <div style={{position: 'relative', overflow: 'hidden', ...style}}>
      {a < 1 && <div style={{position: 'absolute', inset: 0, opacity: 1 - a, filter: `blur(${16 * a}px)`, transform: `translateY(${-12 * a}px)`}}>{from}</div>}
      {b > 0 && <div style={{position: 'absolute', inset: 0, opacity: b, filter: `blur(${16 * (1 - b)}px)`, transform: `translateY(${12 * (1 - b)}px)`}}>{to}</div>}
    </div>
  );
};

type ViewChangeProps = {t: number; start: number; from: React.ReactNode; to: React.ReactNode; back?: boolean; kind?: ViewChangeKind; style?: React.CSSProperties};
// One stable component per profile, so React doesn't remount the view change on every frame.
const VIEW_CHANGE = new Map<Profile, React.FC<ViewChangeProps>>();
const viewChangeFor = (p: Profile) => {
  if (!VIEW_CHANGE.has(p)) VIEW_CHANGE.set(p, makeViewChange(p));
  return VIEW_CHANGE.get(p)!;
};
const makeViewChange = (p: Profile) => {
  const ViewChange: React.FC<ViewChangeProps> = ({t, start, from, to, back, kind, style}) => {
    const k = kind ?? p.viewChange.kind, s = p.viewChange.seconds || 0.6;
    const ms = (s * 1000) / 2; // the M3 components stretch by FILM_STRETCH (2)
    if (k === 'cut') return <div style={{position: 'relative', overflow: 'hidden', ...style}}><div style={{position: 'absolute', inset: 0}}>{t < start ? from : to}</div></div>;
    if (k === 'fadeThrough') return <FadeThrough t={t} start={start} duration={ms} from={from} to={to} style={style} />;
    if (k === 'blurThrough') return <BlurThrough t={t} start={start} seconds={s} from={from} to={to} style={style} />;
    return <SharedAxis t={t} start={start} duration={ms} axis={k === 'sharedAxisX' ? 'x' : k === 'sharedAxisY' ? 'y' : 'z'} back={back} from={from} to={to} style={style} />;
  };
  ViewChange.displayName = `ViewChange(${p.name})`;
  return ViewChange;
};

/** The motion API for one film. */
export const motion = (name: ProfileName | Profile = 'soft') => {
  const p: Profile = typeof name === 'string' ? PROFILES[name] : name;
  const role = (r: Role) => (t: number, start: number, seconds?: number) => evalSpec(p.roles[r], t, start, seconds);
  return {
    profile: p,
    enter: role('enter'), exit: role('exit'), move: role('move'), ui: role('ui'), emphasis: role('emphasis'), camera: role('camera'),
    /** i-th item of a group (word, card, row), staggered by the profile. */
    textReveal: (t: number, start: number, i = 0) => evalSpec(p.roles.textReveal, t, start + i * p.stagger),
    /**
     * Style for the i-th word of a line, in the profile's text style. Spread it on a span:
     * <span style={m.word(t, cue, i, ink)}>{w}</span>. Keep unsaid words in the layout (opacity 0), so lines never shift.
     */
    word: (t: number, start: number, i = 0, ink = '#0B152B'): React.CSSProperties => {
      const k = evalSpec(p.roles.textReveal, t, start + i * p.stagger);
      if (p.text?.style === 'greyToInk') {
        const a = Math.min(1, k / 0.35), c = Math.max(0, (k - 0.3) / 0.7);
        return {display: 'inline-block', opacity: a, color: mixHex(p.text.grey ?? '#C9C9CE', ink, c), transform: `translateY(${6 * (1 - a)}px)`};
      }
      return {display: 'inline-block', opacity: Math.min(1, k), color: ink, filter: `blur(${10 * Math.max(0, 1 - k)}px)`, transform: `translateY(${18 * (1 - k)}px)`};
    },
    stagger: (i: number) => i * p.stagger,
    /** Seconds a role takes (tweens: their duration; springs: until settled within 0.1%). */
    seconds: (r: Role) => {
      const s = p.roles[r];
      return s.kind === 'tween' ? s.seconds : settleTime(s.spring);
    },
    /** Never-still float for holds, scaled by the profile (0 = off). */
    idle: (t: number, k: number) => ({
      x: (Math.sin(t * 0.63 + k * 2.1) * 1.2 + Math.sin(t * 1.07 + k) * 0.6) * p.idle,
      y: (Math.sin(t * 0.91 + k * 1.3) * 2.4 + Math.sin(t * 0.47 + k * 0.7) * 1.2) * p.idle,
    }),
    ViewChange: viewChangeFor(p),
  };
};
export type Motion = ReturnType<typeof motion>;
