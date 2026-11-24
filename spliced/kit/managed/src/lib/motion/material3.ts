// Material Design 3 motion for Remotion: easing curves, duration tokens and springs, as functions
// of film time in seconds (like the rest of the kit). Transition patterns are in M3Transitions.tsx.
//
// Sources (fetched 2026-11-16; m3.material.io itself is a JS app, so values come from the code):
// - Easing and durations: material-web tokens v0_192 (_md-sys-motion.scss) and Jetpack Compose
//   MotionTokens.kt agree on every value. The emphasized curve is the path from
//   material-components-android docs/theming/Motion.md; the web tokens approximate it with
//   standard's cubic-bezier(0.2, 0, 0, 1), which loses its signature slow start.
// - Expressive springs: Compose ExpressiveMotionTokens.kt (v0_14_0), confirmed.
// - Standard springs: material-components-android Motion.md (MaterialSpring). Compose's
//   StandardMotionTokens.kt could not be read to cross-check.
import {Easing} from 'remotion';
import {fromStiffness, springStep, type SpringSpec} from './spring';

type Curve = (x: number) => number;
const bz = (x1: number, y1: number, x2: number, y2: number): Curve => Easing.bezier(x1, y1, x2, y2);

/** Evaluate a path of cubic segments [p0, c1, c2, p3] given as x,y pairs (for M3 emphasized). */
const pathCurve = (segs: number[][]): Curve => {
  const cub = (a: number, b: number, c: number, d: number, s: number) => {
    const u = 1 - s;
    return u * u * u * a + 3 * u * u * s * b + 3 * u * s * s * c + s * s * s * d;
  };
  return (x: number) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    const seg = segs.find((g) => x <= g[6]) ?? segs[segs.length - 1];
    const [x0, y0, x1, y1, x2, y2, x3, y3] = seg;
    let lo = 0, hi = 1;
    for (let i = 0; i < 40; i++) {
      const mid = (lo + hi) / 2;
      if (cub(x0, x1, x2, x3, mid) < x) lo = mid; else hi = mid;
    }
    return cub(y0, y1, y2, y3, (lo + hi) / 2);
  };
};

/** The curves, as cubic-bezier control points (emphasized as its true two-segment path). */
export const M3_EASING_SPEC = {
  standard: [0.2, 0, 0, 1],
  standardAccelerate: [0.3, 0, 1, 1],
  standardDecelerate: [0, 0, 0, 1],
  emphasized: 'path: M 0,0 C 0.05,0 0.133333,0.06 0.166666,0.4 C 0.208333,0.82 0.25,1 1,1',
  emphasizedAccelerate: [0.3, 0, 0.8, 0.15],
  emphasizedDecelerate: [0.05, 0.7, 0.1, 1],
  legacy: [0.4, 0, 0.2, 1],
  legacyAccelerate: [0.4, 0, 1, 1],
  legacyDecelerate: [0, 0, 0.2, 1],
  linear: [0, 0, 1, 1],
} as const;

export const M3_EASING = {
  standard: bz(0.2, 0, 0, 1),
  standardAccelerate: bz(0.3, 0, 1, 1),
  standardDecelerate: bz(0, 0, 0, 1),
  emphasized: pathCurve([
    [0, 0, 0.05, 0, 0.133333, 0.06, 0.166666, 0.4],
    [0.166666, 0.4, 0.208333, 0.82, 0.25, 1, 1, 1],
  ]),
  emphasizedAccelerate: bz(0.3, 0, 0.8, 0.15),
  emphasizedDecelerate: bz(0.05, 0.7, 0.1, 1),
  legacy: bz(0.4, 0, 0.2, 1),
  legacyAccelerate: bz(0.4, 0, 1, 1),
  legacyDecelerate: bz(0, 0, 0.2, 1),
  linear: (x: number) => Math.max(0, Math.min(1, x)),
} satisfies Record<keyof typeof M3_EASING_SPEC, Curve>;
export type M3Easing = keyof typeof M3_EASING;

/** Duration tokens in milliseconds. */
export const M3_DURATION = {
  short1: 50, short2: 100, short3: 150, short4: 200,
  medium1: 250, medium2: 300, medium3: 350, medium4: 400,
  long1: 450, long2: 500, long3: 550, long4: 600,
  extraLong1: 700, extraLong2: 800, extraLong3: 900, extraLong4: 1000,
} as const;
export type M3Duration = keyof typeof M3_DURATION;

/**
 * Film timing: M3 durations are tuned for someone using an app. A viewer watching a film needs
 * longer (camera moves under about 0.9s read as rushed: there's no time to read), so the kit's
 * default stretches UI durations by this factor. Pass `film: 1` to get the literal token.
 */
export const FILM_STRETCH = 2;

/** Seconds for a token, stretched for film unless `film` says otherwise. */
export const m3Seconds = (d: M3Duration | number, film = FILM_STRETCH) => ((typeof d === 'number' ? d : M3_DURATION[d]) / 1000) * film;

/** Progress 0..1 of a tween that starts at film time `start`. */
export const m3Tween = (t: number, start: number, duration: M3Duration | number = 'medium2', easing: M3Easing = 'emphasized', film = FILM_STRETCH) => {
  const d = m3Seconds(duration, film);
  return M3_EASING[easing](Math.max(0, Math.min(1, (t - start) / d)));
};

/** Springs: damping ratio + stiffness (mass 1). Spatial = position/size, effects = opacity/colour (never overshoot). */
const sp = (dampingRatio: number, stiffness: number) => ({dampingRatio, stiffness});
export const M3_SPRING_TOKENS = {
  expressive: {
    fastSpatial: sp(0.6, 800), defaultSpatial: sp(0.8, 380), slowSpatial: sp(0.8, 200),
    fastEffects: sp(1, 3800), defaultEffects: sp(1, 1600), slowEffects: sp(1, 800),
  },
  standard: {
    fastSpatial: sp(0.9, 1400), defaultSpatial: sp(0.9, 700), slowSpatial: sp(0.9, 300),
    fastEffects: sp(1, 3800), defaultEffects: sp(1, 1600), slowEffects: sp(1, 800),
  },
} as const;
export type M3Scheme = keyof typeof M3_SPRING_TOKENS;
export type M3SpringToken = keyof typeof M3_SPRING_TOKENS.expressive;

/**
 * Spec for a token. M3 picks the speed by the size of what moves: fast for small components,
 * default for medium, slow for full-screen. `slow` (0..1) slows the spring for film by lowering
 * stiffness while keeping the damping ratio, so the character (overshoot) is unchanged.
 */
export const m3Spring = (token: M3SpringToken = 'defaultSpatial', scheme: M3Scheme = 'expressive', filmSlow = 1 / FILM_STRETCH): SpringSpec => {
  const {dampingRatio, stiffness} = M3_SPRING_TOKENS[scheme][token];
  return fromStiffness(stiffness * filmSlow * filmSlow, dampingRatio);
};

/** Progress of an M3 spring started at film time `start`. */
export const m3SpringAt = (t: number, start: number, token: M3SpringToken = 'defaultSpatial', scheme: M3Scheme = 'expressive', filmSlow?: number) =>
  springStep(t - start, m3Spring(token, scheme, filmSlow));
