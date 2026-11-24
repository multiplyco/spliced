// A film grade for generated footage, so stills and clips from different models land in one look.
// Modelled on the grade of a laptop launch film: muted colour, deep blacks, teal
// shadows, warm amber highlights, fine moving grain. Wrap footage only, never type or UI.
//
//   <FilmGrade look="apple">{footage}</FilmGrade>
import React, {useId} from 'react';
import {useCurrentFrame} from 'remotion';

type Look = {saturate: number; r: string; g: string; b: string; grain: number; vignette: number};

/** Channel curves as feComponentTransfer tables (input 0..1 in equal steps → output). */
export const LOOKS: Record<string, Look> = {
  // Apple-like: S-curve with crushed blacks; G and B lift in the shadows (teal), R leads in the highlights (warm).
  apple: {
    saturate: 0.8,
    r: '0 0.04 0.19 0.45 0.70 0.89 1.0',
    g: '0 0.06 0.22 0.45 0.67 0.85 0.96',
    b: '0.01 0.09 0.23 0.43 0.61 0.77 0.88',
    grain: 0.1,
    vignette: 0.28,
  },
  none: {saturate: 1, r: '0 1', g: '0 1', b: '0 1', grain: 0, vignette: 0},
};

export const FilmGrade: React.FC<{look?: keyof typeof LOOKS | Look; children: React.ReactNode}> = ({look = 'apple', children}) => {
  const L = typeof look === 'string' ? LOOKS[look] : look;
  const id = 'grade' + useId().replace(/[^a-zA-Z0-9]/g, '');
  const frame = useCurrentFrame();
  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden'}}>
      <svg width={0} height={0} style={{position: 'absolute'}}>
        <filter id={id} colorInterpolationFilters="sRGB">
          <feColorMatrix type="saturate" values={String(L.saturate)} />
          <feComponentTransfer>
            <feFuncR type="table" tableValues={L.r} />
            <feFuncG type="table" tableValues={L.g} />
            <feFuncB type="table" tableValues={L.b} />
          </feComponentTransfer>
        </filter>
        {/* Grain: a new noise field every frame (seeded by frame, so renders are deterministic). */}
        <filter id={`${id}n`} x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves={2} seed={frame % 97} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
      </svg>
      <div style={{position: 'absolute', inset: 0, filter: `url(#${id})`}}>{children}</div>
      {L.vignette > 0 && (
        <div style={{position: 'absolute', inset: 0, background: `radial-gradient(110% 85% at 50% 50%, transparent 55%, rgba(0,0,0,${L.vignette}))`}} />
      )}
      {L.grain > 0 && (
        <svg style={{position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: L.grain, mixBlendMode: 'overlay'}}>
          <rect width="100%" height="100%" filter={`url(#${id}n)`} />
        </svg>
      )}
    </div>
  );
};
