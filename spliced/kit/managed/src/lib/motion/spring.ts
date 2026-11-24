// Exact damped-spring motion as a function of time, shared by the Apple and Material 3 kits.
// Like every helper in this kit it takes film time in seconds, so any frame renders on its own
// and the result is the same at 30, 60 or 120 fps (Remotion's spring() steps frame by frame).

/** A spring as physicists write it: natural frequency (rad/s) and damping ratio (1 = no overshoot). */
export type SpringSpec = {omega: number; zeta: number};

/** Mass 1, stiffness k, damping ratio z (Material 3 tokens are given this way). */
export const fromStiffness = (stiffness: number, dampingRatio: number): SpringSpec => ({omega: Math.sqrt(stiffness), zeta: dampingRatio});

/** Mass 1, stiffness k, damping coefficient c (Remotion's / CSS-in-JS springs). */
export const fromDamping = (stiffness: number, damping: number, mass = 1): SpringSpec => ({
  omega: Math.sqrt(stiffness / mass),
  zeta: damping / (2 * Math.sqrt(stiffness * mass)),
});

/**
 * Position of a spring released at rest from 0 towards 1, `s` seconds after release.
 * Underdamped springs overshoot 1 and settle; critically and overdamped ones approach it.
 */
export const springStep = (s: number, {omega, zeta}: SpringSpec): number => {
  if (s <= 0) return 0;
  if (zeta < 1) {
    const wd = omega * Math.sqrt(1 - zeta * zeta);
    return 1 - Math.exp(-zeta * omega * s) * (Math.cos(wd * s) + ((zeta * omega) / wd) * Math.sin(wd * s));
  }
  if (zeta === 1) return 1 - Math.exp(-omega * s) * (1 + omega * s);
  const r = Math.sqrt(zeta * zeta - 1);
  const r1 = -omega * (zeta - r);
  const r2 = -omega * (zeta + r);
  return 1 + (r2 * Math.exp(r1 * s) - r1 * Math.exp(r2 * s)) / (r1 - r2);
};

/** Velocity of the same motion (units per second), handy for motion blur and speed-scaled effects. */
export const springVelocity = (s: number, spec: SpringSpec, h = 1 / 1200) => (springStep(s + h, spec) - springStep(Math.max(0, s - h), spec)) / (2 * h);

/** Seconds until the spring stays within `eps` of its target (for laying out cues). */
export const settleTime = (spec: SpringSpec, eps = 0.001) => {
  let last = 0;
  for (let s = 0; s < 20; s += 1 / 240) if (Math.abs(1 - springStep(s, spec)) > eps) last = s;
  return Math.ceil(last * 100) / 100;
};

/** Progress of a spring started at film time `start` (0 before it). */
export const springAt = (t: number, start: number, spec: SpringSpec) => springStep(t - start, spec);

export const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
