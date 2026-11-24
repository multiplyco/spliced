// A Liquid-Glass-style material for Remotion: a lens that bends what's behind it, a specular rim,
// soft frost and a shadow, on shapes that can melt into each other and split apart.
//
// How it works (all deterministic, recomputed per frame from the shapes):
// 1. The shapes are signed distance fields (rounded rects: pills, circles, cards), joined with a
//    smooth union, so two blobs merge with a liquid neck instead of overlapping.
// 2. From the field we paint three small images on a canvas: a displacement map (how far each
//    pixel inside the glass samples the backdrop, strongest at the rim like a convex lens), the
//    shape mask, and the rim light (bright where the edge faces the light, a fainter echo opposite).
// 3. The backdrop is rendered a second time inside the glass, bent by an SVG feDisplacementMap,
//    then frosted (blur, saturation), masked to the shape and lit by the rim.
//
// The backdrop must be passed in (it is drawn twice: once as the scene, once inside the glass),
// in the same 1920x1080 coordinates as the glass. This avoids backdrop-filter, which renders
// unreliably in headless Chrome.
import React, {useId, useMemo} from 'react';

export type GlassShape = {cx: number; cy: number; w: number; h: number; r?: number};

export type LiquidGlassProps = {
  shapes: GlassShape[];
  /** Renders the scene behind the glass, in frame coordinates. Called again for the inside of the glass. */
  backdrop: () => React.ReactNode;
  /** Smooth-union radius in px: how far apart two shapes start to melt together. */
  blend?: number;
  /** Max lens displacement at the rim, px. */
  refraction?: number;
  /** Width of the curved rim band where refraction happens, px. */
  bevel?: number;
  /** Frost blur inside the glass, px. 0 = Apple's "clear" variant, ~6-12 = "regular". */
  frost?: number;
  saturate?: number;
  brightness?: number;
  /** A colour wash over the glass, e.g. 'rgba(255,255,255,0.08)' or a brand tint. */
  tint?: string;
  /** Rim highlight strength 0-1, and the light direction in degrees (0 = from the right, -90 = from the top). */
  rim?: number;
  lightAngle?: number;
  shadow?: number;
  /** Canvas resolution relative to the frame (0.5 is plenty at 1080p; raise for 4K masters). */
  res?: number;
  children?: React.ReactNode;
};

const sdRoundRect = (px: number, py: number, s: GlassShape) => {
  const hw = s.w / 2, hh = s.h / 2;
  const r = Math.min(s.r ?? Math.min(hw, hh), hw, hh);
  const qx = Math.abs(px - s.cx) - hw + r;
  const qy = Math.abs(py - s.cy) - hh + r;
  return Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) - r;
};
const smin = (a: number, b: number, k: number) => {
  if (k <= 0) return Math.min(a, b);
  const h = Math.max(k - Math.abs(a - b), 0) / k;
  return Math.min(a, b) - (h * h * k) / 4;
};
const field = (x: number, y: number, shapes: GlassShape[], k: number) => {
  let d = Infinity;
  for (const s of shapes) d = d === Infinity ? sdRoundRect(x, y, s) : smin(d, sdRoundRect(x, y, s), k);
  return d;
};

type Maps = {x: number; y: number; w: number; h: number; map: string; mask: string; rim: string};

function paint(shapes: GlassShape[], o: Required<Pick<LiquidGlassProps, 'blend' | 'refraction' | 'bevel' | 'rim' | 'lightAngle' | 'res'>>): Maps | null {
  if (!shapes.length || typeof document === 'undefined') return null;
  const pad = Math.ceil(o.refraction + o.blend + 6);
  const x0 = Math.floor(Math.min(...shapes.map((s) => s.cx - s.w / 2)) - pad);
  const y0 = Math.floor(Math.min(...shapes.map((s) => s.cy - s.h / 2)) - pad);
  const x1 = Math.ceil(Math.max(...shapes.map((s) => s.cx + s.w / 2)) + pad);
  const y1 = Math.ceil(Math.max(...shapes.map((s) => s.cy + s.h / 2)) + pad);
  const W = x1 - x0, H = y1 - y0;
  const cw = Math.max(1, Math.round(W * o.res)), ch = Math.max(1, Math.round(H * o.res));
  const mk = () => { const c = document.createElement('canvas'); c.width = cw; c.height = ch; return c; };
  const [cm, ck, cr] = [mk(), mk(), mk()];
  const [gm, gk, gr] = [cm, ck, cr].map((c) => c.getContext('2d')!);
  const [im, ik, ir] = [gm, gk, gr].map((g) => g.createImageData(cw, ch));
  const lx = Math.cos((o.lightAngle * Math.PI) / 180), ly = Math.sin((o.lightAngle * Math.PI) / 180);
  const e = 1 / o.res; // finite-difference step = one canvas pixel
  const aa = 0.75 / o.res;
  for (let j = 0; j < ch; j++) {
    for (let i = 0; i < cw; i++) {
      const x = x0 + (i + 0.5) / o.res, y = y0 + (j + 0.5) / o.res;
      const d = field(x, y, shapes, o.blend);
      const p = (j * cw + i) * 4;
      // Mask: antialiased inside.
      const a = Math.max(0, Math.min(1, 0.5 - d / (2 * aa)));
      ik.data[p] = ik.data[p + 1] = ik.data[p + 2] = 255; ik.data[p + 3] = Math.round(a * 255);
      // Outward normal from the field's gradient.
      let nx = field(x + e, y, shapes, o.blend) - field(x - e, y, shapes, o.blend);
      let ny = field(x, y + e, shapes, o.blend) - field(x, y - e, shapes, o.blend);
      const nl = Math.hypot(nx, ny) || 1; nx /= nl; ny /= nl;
      // Lens: displacement grows towards the rim (0 at the inner edge of the bevel, max at the rim),
      // sampling outward so the edge bends the backdrop like a thick convex lens.
      const band = d < 0 ? Math.max(0, 1 + d / o.bevel) : 1;
      const mag = d < 0 ? Math.pow(band, 2.2) : 1;
      im.data[p] = Math.round(127.5 + 127.5 * nx * mag);
      im.data[p + 1] = Math.round(127.5 + 127.5 * ny * mag);
      im.data[p + 2] = 128; im.data[p + 3] = 255;
      // Rim light: a thin bright edge facing the light, a fainter one opposite (glass lit from both sides).
      // Plus a soft shade just inside the edge on the side away from the light, for thickness.
      if (d < 0.5 && d > -o.bevel) {
        const px1 = 1 / o.res;
        const edge = Math.exp(-Math.pow((d + px1) / Math.max(1.2, o.bevel * 0.07), 2));
        const facing = Math.max(0, nx * lx + ny * ly), back = Math.max(0, -(nx * lx + ny * ly));
        const v = (0.32 + 0.68 * Math.pow(facing, 2) + 0.5 * Math.pow(back, 3)) * edge * o.rim * a;
        const shade = 0.16 * Math.pow(back, 1.5) * Math.exp(-Math.pow((d + o.bevel * 0.35) / (o.bevel * 0.3), 2)) * a;
        const al = Math.min(1, v + shade);
        const white = al > 0 ? v / al : 1;
        const c = Math.round(255 * white + 20 * (1 - white));
        ir.data[p] = ir.data[p + 1] = ir.data[p + 2] = c; ir.data[p + 3] = Math.round(al * 255);
      }
    }
  }
  gm.putImageData(im, 0, 0); gk.putImageData(ik, 0, 0); gr.putImageData(ir, 0, 0);
  return {x: x0, y: y0, w: W, h: H, map: cm.toDataURL(), mask: ck.toDataURL(), rim: cr.toDataURL()};
}

export const LiquidGlass: React.FC<LiquidGlassProps> = ({
  shapes, backdrop, blend = 60, refraction = 38, bevel = 34, frost = 5, saturate = 1.3, brightness = 1.05,
  tint = 'rgba(255,255,255,0.12)', rim = 1, lightAngle = -120, shadow = 0.22, res = 0.5, children,
}) => {
  const id = 'lg' + useId().replace(/[^a-zA-Z0-9]/g, '');
  const key = JSON.stringify([shapes, blend, refraction, bevel, rim, lightAngle, res]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const m = useMemo(() => paint(shapes, {blend, refraction, bevel, rim, lightAngle, res}), [key]);
  if (!m) return null;
  const maskStyle: React.CSSProperties = {WebkitMaskImage: `url(${m.mask})`, maskImage: `url(${m.mask})`, WebkitMaskSize: '100% 100%', maskSize: '100% 100%'};
  return (
    <div style={{position: 'absolute', left: m.x, top: m.y, width: m.w, height: m.h, pointerEvents: 'none'}}>
      <svg width={0} height={0} style={{position: 'absolute'}}>
        {/* The filter runs on a full-frame layer, so everything is in frame coordinates (no origin guessing). */}
        <filter id={id} x={m.x} y={m.y} width={m.w} height={m.h} filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
          <feImage href={m.map} x={m.x} y={m.y} width={m.w} height={m.h} preserveAspectRatio="none" result="map" />
          <feDisplacementMap in="SourceGraphic" in2="map" scale={refraction * 2} xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </svg>
      {shadow > 0 && (
        <div style={{position: 'absolute', inset: 0, ...maskStyle, background: `rgba(10,14,30,${shadow})`, filter: 'blur(22px)', transform: 'translateY(14px) scale(0.98)'}} />
      )}
      <div style={{position: 'absolute', inset: 0, overflow: 'hidden', ...maskStyle}}>
        <div style={{position: 'absolute', left: -m.x, top: -m.y, width: 1920, height: 1080, filter: `url(#${id}) blur(${frost}px) saturate(${saturate}) brightness(${brightness})`}}>
          {backdrop()}
        </div>
        <div style={{position: 'absolute', inset: 0, background: tint}} />
        <img src={m.rim} style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}} />
      </div>
      {children && <div style={{position: 'absolute', left: -m.x, top: -m.y, width: 1920, height: 1080}}>{children}</div>}
    </div>
  );
};
