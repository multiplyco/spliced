// The Spliced explainer: nine beats (cues.json scenes), each a scene component driven by film time. Score: sound.json (score.py).
import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {SCENE_OF} from './Scenes';
import {T} from './brand';
import cues from './cues.json';
import sound from './sound.json';
import {SoundTracks, type Sound} from '../../lib/sound';

/** Film time to the scenes' design clock: interpolate between sync.py's [design, film] anchors (cues.json sync). */
const SYNC = cues.sync as [number, number][];
export const designTime = (t: number) => {
  let i = 1;
  while (i < SYNC.length - 1 && SYNC[i][1] < t) i++;
  const [d0, f0] = SYNC[i - 1], [d1, f1] = SYNC[i];
  return d0 + ((t - f0) * (d1 - d0)) / (f1 - f0);
};

const Beat: React.FC<{id: string; start: number}> = ({id, start}) => {
  const f = useCurrentFrame(), {fps} = useVideoConfig();
  const S = SCENE_OF[id];
  return <S t={designTime(start + f / fps)} />;
};

export const Film: React.FC = () => {
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{background: T.ink}}>
      {Object.entries(cues.scenes).map(([id, [a, b]]) => (
        <Sequence key={id} from={Math.round(a * fps)} durationInFrames={Math.round((b - a) * fps)} name={id}>
          <Beat id={id} start={a} />
        </Sequence>
      ))}
      <SoundTracks sound={sound as unknown as Sound} duration={cues.duration} />
    </AbsoluteFill>
  );
};
export const FILM_SECONDS = cues.duration;
