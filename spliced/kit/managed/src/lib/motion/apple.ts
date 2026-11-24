// Apple-style motion for Remotion: SwiftUI's duration + bounce springs and SF-Symbols-like icon
// effects, as functions of film time in seconds.
//
// Source: WWDC23 "Animate with springs" (10158) and "Explore SwiftUI animation" (10156).
// A spring is a perceptual duration and a bounce (-1..1): bounce 0 is critically damped (smooth,
// SwiftUI's default since iOS 17), > 0 overshoots, < 0 is flattened. Mass 1,
// stiffness = (2π / duration)², damping = 4π(1 − bounce) / duration (bounce ≥ 0) or
// 4π / (duration(1 + bounce)) (bounce < 0), i.e. damping ratio = 1 − bounce (or 1 / (1 + bounce)).
// Apple's guidance: ~0.15 is "a small bounce", ~0.3 is noticeably bouncy, be careful above ~0.4.
//
// The presets' exact numbers weren't readable from Apple's docs (JS-rendered). The values below
// are SwiftUI's documented defaults as we know them (duration 0.5; bounce 0 / 0.15 / 0.3), and
// they match the WWDC guidance above. Override freely.
//
// We copy motion, never assets: don't use SF Symbols or Apple UI kits in your films.
import {springStep, type SpringSpec} from './spring';

export type AppleSpring = {duration: number; bounce: number};

export const APPLE_SPRING = {
  smooth: {duration: 0.5, bounce: 0},
  snappy: {duration: 0.5, bounce: 0.15},
  bouncy: {duration: 0.5, bounce: 0.3},
} as const satisfies Record<string, AppleSpring>;

/** Duration + bounce → natural frequency and damping ratio. */
export const appleSpec = ({duration, bounce}: AppleSpring): SpringSpec => ({
  omega: (2 * Math.PI) / duration,
  zeta: bounce >= 0 ? 1 - bounce : 1 / (1 + bounce),
});

/** Remotion `spring({config})` equivalent (mass 1), if you prefer Remotion's frame-based spring. */
export const appleToRemotion = ({duration, bounce}: AppleSpring) => ({
  mass: 1,
  stiffness: Math.pow((2 * Math.PI) / duration, 2),
  damping: bounce >= 0 ? (4 * Math.PI * (1 - bounce)) / duration : (4 * Math.PI) / (duration * (1 + bounce)),
});

/** Progress of an Apple spring started at film time `start`. `s` may be a preset name. */
export const appleSpringAt = (t: number, start: number, s: AppleSpring | keyof typeof APPLE_SPRING = 'smooth') =>
  springStep(t - start, appleSpec(typeof s === 'string' ? APPLE_SPRING[s] : s));

// ---------- Symbol-style effects ----------
// Each returns a CSS transform/opacity for an icon (or any small element) at film time t.
// Modelled on what SF Symbols' effects do, applied to our own icons (Lucide in this kit).

export type FX = {transform: string; opacity: number; filter?: string};
const fx = (scale = 1, x = 0, y = 0, rot = 0, opacity = 1, blur = 0): FX => ({
  transform: `translate(${x}px, ${y}px) rotate(${rot}deg) scale(${scale})`,
  opacity,
  filter: blur ? `blur(${blur}px)` : undefined,
});

export const symbolFX = {
  /** A quick squash and spring back, for a tap or a "done". */
  bounce: (t: number, start: number, up = true): FX => {
    const s = t - start;
    if (s < 0) return fx();
    const squash = s < 0.09 ? Math.sin((s / 0.09) * (Math.PI / 2)) : 1;
    const back = s < 0.09 ? 0 : springStep(s - 0.09, appleSpec({duration: 0.45, bounce: 0.45}));
    const k = s < 0.09 ? squash : 1 - back;
    return fx(1 - 0.18 * k, 0, up ? -10 * (s < 0.09 ? 0 : Math.sin(Math.min(1, (s - 0.09) / 0.35) * Math.PI)) : 0);
  },
  /** Opacity dips and returns, on repeat: "working on it". */
  pulse: (t: number, start: number, period = 1.2): FX => {
    if (t < start) return fx();
    const p = ((t - start) % period) / period;
    return fx(1, 0, 0, 0, 1 - 0.55 * Math.sin(p * Math.PI) ** 2);
  },
  /** Presence swells and recedes (size and opacity together). */
  breathe: (t: number, start: number, period = 2.4): FX => {
    if (t < start) return fx();
    const p = (1 - Math.cos((((t - start) % period) / period) * 2 * Math.PI)) / 2;
    return fx(1 + 0.1 * p, 0, 0, 0, 0.75 + 0.25 * p);
  },
  /** A decaying side-to-side rotation, to draw the eye ("look here"). */
  wiggle: (t: number, start: number, deg = 14): FX => {
    const s = t - start;
    if (s < 0) return fx();
    return fx(1, 0, 0, deg * Math.exp(-5 * s) * Math.sin(2 * Math.PI * 3.2 * s));
  },
  /** Continuous rotation, for in-progress. */
  rotate: (t: number, start: number, rps = 0.8): FX => fx(1, 0, 0, t < start ? 0 : (t - start) * 360 * rps),
  /** Springs in from nothing. */
  appear: (t: number, start: number): FX => {
    const p = appleSpringAt(t, start, {duration: 0.4, bounce: 0.25});
    return fx(Math.max(0, p), 0, 0, 0, Math.min(1, Math.max(0, (t - start) / 0.12)));
  },
  /** Old icon shrinks and blurs out while the new one springs up: pass `which` = 'out' | 'in'. */
  replace: (t: number, start: number, which: 'out' | 'in'): FX => {
    const s = t - start;
    if (which === 'out') {
      if (s < 0) return fx();
      const k = Math.min(1, s / 0.16);
      return fx(1 - 0.5 * k, 0, 0, 0, 1 - k, 6 * k);
    }
    if (s < 0.08) return fx(0.5, 0, 0, 0, 0, 6);
    const p = springStep(s - 0.08, appleSpec({duration: 0.42, bounce: 0.3}));
    const o = Math.min(1, (s - 0.08) / 0.14);
    return fx(0.5 + 0.5 * p, 0, 0, 0, o, 6 * (1 - o));
  },
};
