// The vocabulary a motion profile is written in: the roles, the curves, and tw()/sp() to name a tween or a spring.
// Its own file so a project's profiles (src/profiles.ts) can use it without importing the profiles themselves.
import {Easing} from 'remotion';
import {type M3Easing} from './material3';
import {type SpringSpec} from './spring';

export type Role = 'enter' | 'exit' | 'move' | 'ui' | 'emphasis' | 'camera' | 'textReveal';
export type ViewChangeKind = 'sharedAxisX' | 'sharedAxisY' | 'sharedAxisZ' | 'fadeThrough' | 'blurThrough' | 'cut';

/** Our own curves: glide for camera moves (eases off the mark, long soft landing); land = arrive fast, land soft. */
const glide = Easing.bezier(0.32, 0, 0.12, 1);
const land = (rate: number) => (x: number) => (x <= 0 ? 0 : x >= 1 ? 1 : (1 - Math.pow(1 - rate, x * 30)) / (1 - Math.pow(1 - rate, 30)));
/** Spliced's own curves (Spliced's web/splice-tokens.css): ease-out, ease-in-out, ease-ui and ease-sink (the logo's blocks). */
const SPLICE_CURVES = {
  spliceOut: Easing.bezier(0.16, 1, 0.3, 1),
  spliceInOut: Easing.bezier(0.45, 0, 0.55, 1),
  spliceUi: Easing.bezier(0.3, 0, 0.2, 1),
  spliceSink: Easing.bezier(0.7, 0, 0.2, 1),
};
export const KIT_CURVES = {glide, land: land(0.2), ...SPLICE_CURVES};

export type MotionSpec =
  | {kind: 'tween'; curve: M3Easing | keyof typeof KIT_CURVES; seconds: number; source: string}
  | {kind: 'spring'; spring: SpringSpec; source: string};

export type Profile = {
  name: string;
  feel: string;
  roles: Record<Role, MotionSpec>;
  /** Seconds between grouped items (words, cards, rows). */
  stagger: number;
  viewChange: {kind: ViewChangeKind; seconds: number};
  /** Amplitude of the never-still idle float (0 = none). */
  idle: number;
  /** How words arrive (m.word): 'sharpen' = blur to sharp and rise (kit); 'greyToInk' = land light grey, then darken. */
  text?: {style: 'sharpen' | 'greyToInk'; grey?: string};
};

export type CurveName = M3Easing | keyof typeof KIT_CURVES;
export const tw = (curve: CurveName, seconds: number, source: string): MotionSpec => ({kind: 'tween', curve, seconds, source});
export const sp = (spring: SpringSpec, source: string): MotionSpec => ({kind: 'spring', spring, source});

