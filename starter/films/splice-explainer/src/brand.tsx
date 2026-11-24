// Spliced brand for the film: tokens (Spliced's web/splice-tokens.css), fonts, and the four-block mark drawn in code
// so each block's height can be driven by film time (the brand's build-in and sink-and-rise, through the profile).
import React from 'react';
import {Img, staticFile} from 'remotion';
import {loadFont as loadAnybody} from '@remotion/google-fonts/Anybody';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {loadFont as loadMono} from '@remotion/google-fonts/JetBrainsMono';

export const DISPLAY = loadAnybody('normal', {weights: ['700'], subsets: ['latin']}).fontFamily;
export const UI = loadInter('normal', {weights: ['400', '500', '600'], subsets: ['latin']}).fontFamily;
export const MONO = loadMono('normal', {weights: ['400', '500'], subsets: ['latin']}).fontFamily;

export const T = {
  volt: '#DFFF1A', voltHover: '#E8FF4D', voltPress: '#A8C400', voltDeep: '#6F8400', voltTint: 'rgba(223, 255, 26, 0.14)',
  ink: '#0B0B0C', g900: '#131314', g800: '#1A1A1C', g700: '#242426', g600: '#323235',
  s500: '#55555A', s400: '#85858B', s300: '#B1B1B6', m200: '#D9D9DC', m100: '#EDEDEF', chalk: '#F4F4F1',
  danger: '#FF5C4D', warning: '#FFB020', success: '#3DDC97', info: '#6EA8FF',
  hover: 'rgba(255, 255, 255, 0.06)',
  pop: '0 12px 32px rgba(0, 0, 0, 0.5)',
};

/** Page-title type: Anybody, wide (wdth 130), bold, uppercase. */
export const display = (size: number, color = T.chalk): React.CSSProperties => ({
  fontFamily: DISPLAY, fontWeight: 700, fontSize: size, lineHeight: 1.06, textTransform: 'uppercase', letterSpacing: 0,
  fontStretch: '130%', fontVariationSettings: '"wdth" 130', color,
});
/** Labels: JetBrains Mono, small, uppercase, tracked. */
export const label = (size = 11, color = T.s400): React.CSSProperties => ({
  fontFamily: MONO, fontWeight: 500, fontSize: size, letterSpacing: '0.08em', textTransform: 'uppercase', color,
});
export const mono = (size = 13, color = T.s300): React.CSSProperties => ({fontFamily: MONO, fontSize: size, color, fontVariantNumeric: 'tabular-nums'});

// The mark: four isometric blocks in a pinwheel, each taller than the last (splice-mark-*.svg, viewBox 277.1 x 202).
// Each block is its top rhombus at full height and the height of its sides; the faces hang from the top down to a fixed floor.
type P = [number, number];
const BLOCKS: {top: [P, P, P, P]; h: number}[] = [
  {top: [[138.6, 0], [221.7, 48], [173.2, 76], [90.1, 28]], h: 42},
  {top: [[83.1, 48], [131.6, 76], [48.5, 124], [0, 96]], h: 26},
  {top: [[228.6, 36], [277.1, 64], [194.0, 112], [145.5, 84]], h: 58},
  {top: [[103.9, 116], [187.1, 164], [138.6, 192], [55.4, 144]], h: 10},
];
/** Block indices from lowest to tallest: the order the build-in raises them. */
export const RISE_ORDER = [3, 1, 0, 2];
const TONES = {
  volt: {top: T.volt, left: T.voltPress, right: T.voltDeep},
  white: {top: '#F4F4F1', left: '#B9B9B3', right: '#7C7C77'},
};

/** The mark. `rise[i]` is block i's height as a share of full (0 = flat, 1 = full); default all full. */
export const SpliceMark: React.FC<{width: number; tone?: keyof typeof TONES; rise?: number[]; style?: React.CSSProperties}> = ({width, tone = 'white', rise, style}) => {
  const c = TONES[tone];
  const pts = (ps: P[]) => ps.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
  return (
    <svg viewBox="0 0 277.1 202" width={width} height={(width * 202) / 277.1} style={{overflow: 'visible', ...style}}>
      {BLOCKS.map((b, i) => {
        const k = rise ? rise[i] : 1;
        const d = b.h * (1 - k); // how far the top has sunk
        const [tp, rt, bt, lf] = b.top.map(([x, y]) => [x, y + d] as P);
        const floor = (p: P): P => [p[0], p[1] - d + b.h];
        return (
          <g key={i}>
            <polygon fill={c.left} points={pts([lf, bt, floor(bt), floor(lf)])} />
            <polygon fill={c.right} points={pts([rt, bt, floor(bt), floor(rt)])} />
            <polygon fill={c.top} points={pts([tp, rt, bt, lf])} />
          </g>
        );
      })}
    </svg>
  );
};

/**
 * The horizontal lockup (splice-lockup-horizontal-*.svg, LOCKUP_W x 145.8, made by Spliced's brand_wordmark.py): the mark at 0.72176 scale and the outlined
 * wordmark (never retyped) at (266.67, 22.9). `word` reveals the wordmark (0..1) with a left-to-right wipe.
 */
/** Widths of the outlined SPLICED wordmark and the horizontal lockup (Spliced's brand_wordmark.py). */
export const WORD_W = 799.54, LOCKUP_W = 266.67 + WORD_W;
export const Lockup: React.FC<{width: number; rise?: number[]; word?: number; wordShift?: number}> = ({width, rise, word = 1, wordShift = 0}) => {
  const s = width / LOCKUP_W;
  return (
    <div style={{position: 'relative', width, height: 145.8 * s}}>
      <SpliceMark width={277.1 * 0.72176 * s} rise={rise} style={{position: 'absolute', left: 0, top: 0}} />
      <div style={{position: 'absolute', left: 266.67 * s, top: 22.9 * s, width: WORD_W * s, height: 100 * s,
        clipPath: `inset(0 ${(1 - word) * 100}% 0 0)`, transform: `translateX(${wordShift * s}px)`}}>
        <Img src={staticFile('films/splice-explainer/brand/splice-wordmark-white.svg')} style={{width: '100%', height: '100%', display: 'block'}} />
      </div>
    </div>
  );
};
