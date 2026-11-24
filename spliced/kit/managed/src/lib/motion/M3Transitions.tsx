// Material 3's transition patterns as Remotion components. Each takes film time `t`, a `start`,
// a duration (token or ms, stretched for film by FILM_STRETCH), and the outgoing / incoming views.
//
// Durations and easing follow material-components-android (300ms, FastOutSlowIn there; we use M3
// emphasized). The choreography numbers (fade-through split at 35%, incoming scale 92%, shared-axis
// slide and Z scales, container fade thresholds) are material-components-android's defaults as we
// know them; the official M3 pages weren't readable to confirm them. Tune by eye.
import React from 'react';
import {M3_EASING, m3Seconds, type M3Duration, type M3Easing, FILM_STRETCH} from './material3';
import {clamp01, lerp} from './spring';

type Base = {t: number; start: number; duration?: M3Duration | number; easing?: M3Easing; film?: number; from: React.ReactNode; to: React.ReactNode; style?: React.CSSProperties};
const prog = (t: number, start: number, duration: M3Duration | number, film: number) => clamp01((t - start) / m3Seconds(duration, film));
const seg = (p: number, a: number, b: number) => clamp01((p - a) / (b - a));
const Layer: React.FC<{style: React.CSSProperties; children: React.ReactNode}> = ({style, children}) => (
  <div style={{position: 'absolute', inset: 0, ...style}}>{children}</div>
);

/**
 * Shared axis: two views related by navigation, moving along one axis together.
 * x / y: both slide `distance` px the same way while the old fades out (first 35%) and the new fades in.
 * z: the new grows in from 80% while the old grows past 110% and fades (forward; reversed for back).
 */
export const SharedAxis: React.FC<Base & {axis?: 'x' | 'y' | 'z'; back?: boolean; distance?: number}> = ({
  t, start, duration = 'medium2', easing = 'emphasized', film = FILM_STRETCH, from, to, axis = 'x', back = false, distance = 90, style,
}) => {
  const p = prog(t, start, duration, film);
  const e = M3_EASING[easing](p);
  const outO = 1 - seg(p, 0, 0.35), inO = seg(p, 0.35, 1);
  const dir = back ? -1 : 1;
  const tr = (k: number, entering: boolean) => {
    if (axis === 'z') {
      const s = entering ? lerp(back ? 1.1 : 0.8, 1, k) : lerp(1, back ? 0.8 : 1.1, k);
      return `scale(${s})`;
    }
    const d = entering ? dir * distance * (1 - k) : -dir * distance * k;
    return axis === 'x' ? `translateX(${d}px)` : `translateY(${d}px)`;
  };
  return (
    <div style={{position: 'relative', overflow: 'hidden', ...style}}>
      {p < 1 && <Layer style={{opacity: outO, transform: tr(e, false)}}>{from}</Layer>}
      {p > 0 && <Layer style={{opacity: inO, transform: tr(e, true)}}>{to}</Layer>}
    </div>
  );
};

/** Fade through: unrelated views. The old fades out in the first 35%; the new fades in and grows from 92%. */
export const FadeThrough: React.FC<Base & {scaleFrom?: number}> = ({t, start, duration = 'medium2', easing = 'emphasized', film = FILM_STRETCH, from, to, scaleFrom = 0.92, style}) => {
  const p = prog(t, start, duration, film);
  const inP = M3_EASING[easing](seg(p, 0.35, 1));
  return (
    <div style={{position: 'relative', overflow: 'hidden', ...style}}>
      {p < 0.35 && <Layer style={{opacity: 1 - seg(p, 0, 0.35)}}>{from}</Layer>}
      {p > 0.35 && <Layer style={{opacity: inP, transform: `scale(${lerp(scaleFrom, 1, inP)})`}}>{to}</Layer>}
    </div>
  );
};

/** Fade: something entering or leaving within the screen (a dialog, a menu, a toast). Enter grows from 80%. */
export const Fade: React.FC<{t: number; start: number; out?: boolean; film?: number; children: React.ReactNode; style?: React.CSSProperties}> = ({t, start, out = false, film = FILM_STRETCH, children, style}) => {
  const p = prog(t, start, out ? 75 : 150, film);
  const sc = out ? 1 : lerp(0.8, 1, M3_EASING.emphasizedDecelerate(p));
  return <div style={{opacity: out ? 1 - p : p, transform: `scale(${sc})`, ...style}}>{children}</div>;
};

export type Box = {x: number; y: number; w: number; h: number; r: number};

/**
 * Container transform: an element (a card, a chip, a FAB) becomes the next view. The container's
 * bounds and corner radius morph from `fromBox` to `toBox`; its contents fade through (old out in
 * the first 30%, new in from 30%), each scaled to the container's width so nothing reflows.
 */
export const ContainerTransform: React.FC<Base & {fromBox: Box; toBox: Box; fromSize: {w: number; h: number}; toSize: {w: number; h: number}; background?: string; elevation?: number; scrim?: number}> = ({
  t, start, duration = 'long2', easing = 'emphasized', film = FILM_STRETCH, from, to, fromBox, toBox, fromSize, toSize, background = '#fff', elevation = 0.18, scrim = 0, style,
}) => {
  const p = prog(t, start, duration, film);
  const e = M3_EASING[easing](p);
  const b = {x: lerp(fromBox.x, toBox.x, e), y: lerp(fromBox.y, toBox.y, e), w: lerp(fromBox.w, toBox.w, e), h: lerp(fromBox.h, toBox.h, e), r: lerp(fromBox.r, toBox.r, e)};
  const outO = 1 - seg(p, 0, 0.3), inO = M3_EASING.standardDecelerate(seg(p, 0.3, 0.8));
  return (
    <>
      {scrim > 0 && <div style={{position: 'absolute', inset: 0, background: `rgba(0,0,0,${scrim * Math.sin(Math.PI * p)})`}} />}
      <div style={{position: 'absolute', left: b.x, top: b.y, width: b.w, height: b.h, borderRadius: b.r, overflow: 'hidden', background,
        boxShadow: `0 ${10 + 30 * Math.sin(Math.PI * p)}px ${30 + 60 * Math.sin(Math.PI * p)}px rgba(15,20,40,${elevation})`, ...style}}>
        {outO > 0 && <div style={{position: 'absolute', left: 0, top: 0, width: fromSize.w, height: fromSize.h, transformOrigin: '0 0', transform: `scale(${b.w / fromSize.w})`, opacity: outO}}>{from}</div>}
        {inO > 0 && <div style={{position: 'absolute', left: 0, top: 0, width: toSize.w, height: toSize.h, transformOrigin: '0 0', transform: `scale(${b.w / toSize.w})`, opacity: inO}}>{to}</div>}
      </div>
    </>
  );
};
