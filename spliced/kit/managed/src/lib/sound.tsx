// Plays a film's sound.json: one <Audio> per track at its start, from its offset, at its gain.
// The music leans back under the voice: for each spoken phrase in `duck.phrases` its level dips by `duck.db`,
// easing down over `attack` and back over `release`, so the two share the space instead of switching.
// sound.json is written by remotion/scripts/score_sketch.py and read by Spliced's sound.py (Spliced's Sound panel).
import React from 'react';
import {Audio, Sequence, interpolate, staticFile, useVideoConfig} from 'remotion';

export type Track = {
  id: string; lane: 'music' | 'voice' | 'sfx'; file: string; start: number; offset?: number; dur?: number; gain?: number; name?: string;
  fadeIn?: number; fadeOut?: number; duck?: {db: number; attack: number; release: number; phrases: [number, number][]};
};
export type Sound = {tracks: Track[]};

const pub = (file: string) => staticFile(file.replace(/^remotion\/public\//, ''));

/** 0..1 depth of the dip at film time t: up during a phrase, eased in and out. */
const duckDepth = (t: number, d: NonNullable<Track['duck']>) => {
  let k = 0;
  for (const [a, b] of d.phrases) {
    const inP = interpolate(t, [a - d.attack, a, b, b + d.release], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
    k = Math.max(k, inP);
  }
  return k;
};

export const SoundTracks: React.FC<{sound: Sound; duration: number}> = ({sound, duration}) => {
  const {fps} = useVideoConfig();
  return (
    <>
      {sound.tracks.map((tr) => {
        const from = Math.round(tr.start * fps);
        const len = tr.dur ? Math.round(tr.dur * fps) : undefined;
        const volume = (f: number) => {
          const t = tr.start + f / fps;
          let v = tr.gain ?? 1;
          if (tr.duck) v *= Math.pow(10, (tr.duck.db * duckDepth(t, tr.duck)) / 20);
          const end = Math.min(duration, tr.start + (tr.dur ?? duration));
          if (tr.fadeIn) v *= interpolate(t, [tr.start, tr.start + tr.fadeIn], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          if (tr.fadeOut) v *= interpolate(t, [end - tr.fadeOut, end], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return v;
        };
        return (
          <Sequence key={tr.id} from={from} durationInFrames={len} layout="none" name={`${tr.lane}: ${tr.name ?? tr.id}`}>
            <Audio src={pub(tr.file)} startFrom={Math.round((tr.offset ?? 0) * fps)} volume={volume} />
          </Sequence>
        );
      })}
    </>
  );
};
