// Holds are never dead still: a held shot keeps creeping in, a scale that compounds `rate` per 30fps frame from
// `start` (1 before it). Typical rates: 0.0008 for wide UI that must not run off the frame, 0.0025 to 0.004 for
// footage and plates. Use it as a factor on the shot's own scale: `scale(${1.05 * holdPush(t, shotStart, 0.0025)})`.
export const holdPush = (t: number, start: number, rate = 0.0025) => Math.pow(1 + rate, Math.max(0, t - start) * 30);
