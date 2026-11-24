// Every composition this project renders. A film is registered here once (its id is "composition" in its
// storyboard.json); `spliced kit starter` adds the example films between the two markers below.
import React from 'react';
import {Composition} from 'remotion';
import {GlassSpecimen, MotionSystems, SPECIMEN} from './specimen/MotionSystems';
import {MOVES_SECONDS, SystemMoves} from './specimen/SystemMoves';
import {PROFILE_SECONDS, ProfileCompare} from './specimen/ProfileCompare';
// spliced:imports

export const RemotionRoot: React.FC = () => (
  <>
    {/* spliced:films */}
    {/* The kit's specimens (docs/MOTION-SYSTEMS.md): every move alone, the profiles side by side, the systems compared. */}
    <Composition id="Specimen-Moves" component={SystemMoves} durationInFrames={Math.round(MOVES_SECONDS * SPECIMEN.fps)} fps={SPECIMEN.fps} width={1920} height={1080} />
    <Composition id="Specimen-Profiles" component={ProfileCompare} durationInFrames={PROFILE_SECONDS * SPECIMEN.fps} fps={SPECIMEN.fps} width={1920} height={1080} />
    <Composition id="Specimen-MotionSystems" component={MotionSystems} durationInFrames={SPECIMEN.duration * SPECIMEN.fps} fps={SPECIMEN.fps} width={1920} height={1080} />
    <Composition id="Specimen-Glass" component={GlassSpecimen} durationInFrames={6 * SPECIMEN.fps} fps={SPECIMEN.fps} width={1920} height={1080} />
  </>
);
