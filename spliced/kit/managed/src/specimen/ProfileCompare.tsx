// The same little sequence under each motion profile, side by side: composition "Specimen-Profiles".
// Use it to choose a film's profile, and to tune a project's own profile (src/profiles.ts) by eye.
import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {Check} from 'lucide-react';
import {display, ui} from './type';
import {PROFILES, lerp, motion, type ProfileName} from '../lib/motion';
import {PROJECT_PROFILES} from '../profiles';
import {Screen} from './MotionSystems';

const INK = '#0B152B', MUTED = 'rgba(11,21,43,0.5)';
export const PROFILE_SECONDS = 7;
// three built-in profiles, then this project's first own profile (or Spliced's)
const ORDER: ProfileName[] = ['soft', 'material', 'apple', ((Object.keys(PROJECT_PROFILES)[0] ?? 'splice') as ProfileName)];
const CUE = {card: 0.6, words: 1.5, chip: 2.6, badge: 3.2, view: 4.3, back: 5.6};

const Column: React.FC<{name: ProfileName; t: number; x: number}> = ({name, t, x}) => {
  const m = motion(name);
  const card = m.enter(t, CUE.card);
  const chip = m.ui(t, CUE.chip);
  const badge = m.emphasis(t, CUE.badge);
  const words = ['Your', 'brief', 'is', 'ready.'];
  const content = (
    <div style={{position: 'absolute', inset: 0, background: '#fff', padding: 26}}>
      <div style={{font: `500 34px ${display}`, letterSpacing: '-0.03em', color: INK, lineHeight: 1.15}}>
        {words.map((w, i) => <span key={i} style={{...m.word(t, CUE.words, i, INK), marginRight: 9}}>{w}</span>)}
      </div>
      {[0, 1, 2].map((i) => <div key={i} style={{marginTop: 18, height: 14, width: `${88 - i * 18}%`, borderRadius: 7, background: 'rgba(11,21,43,0.07)'}} />)}
      <div style={{position: 'absolute', left: 26, bottom: 26, display: 'flex', alignItems: 'center', gap: 10, padding: '12px 18px', borderRadius: 999, background: '#0B152B', color: '#fff',
        font: `600 20px ${ui}`, transform: `scale(${lerp(0.4, 1, chip)})`, opacity: Math.min(1, chip * 3), transformOrigin: '0 50%'}}>Share</div>
      <div style={{position: 'absolute', right: 22, top: 22, width: 46, height: 46, borderRadius: 23, background: '#1F8A4C', color: '#fff', display: 'grid', placeItems: 'center',
        transform: `scale(${Math.max(0, badge)})`}}><Check size={26} /></div>
    </div>
  );
  const {ViewChange} = m;
  const shown = t < CUE.view ? content : null;
  return (
    <div style={{position: 'absolute', left: x, top: 150, width: 400}}>
      <div style={{font: `500 40px ${display}`, letterSpacing: '-0.02em', color: INK}}>{name}</div>
      <div style={{font: `400 18px ${ui}`, color: MUTED, height: 52, marginTop: 4}}>{PROFILES[name].feel}</div>
      <div style={{position: 'absolute', top: 120, width: 400, height: 520, transform: `translateY(${60 * (1 - card)}px) scale(${lerp(0.94, 1, card)})`, opacity: Math.min(1, card * 1.5)}}>
        <ViewChange t={t} start={CUE.view} from={shown ?? content} to={<Screen hue="#E8613C" title="Proposal" rows={4} />}
          style={{position: 'absolute', inset: 0, borderRadius: 26, overflow: 'hidden', boxShadow: '0 24px 60px rgba(15,20,40,0.12)'}} />
      </div>
      <div style={{position: 'absolute', top: 660, font: `400 15px ${ui}`, color: MUTED, lineHeight: 1.5}}>
        enter: {PROFILES[name].roles.enter.source}<br />ui: {PROFILES[name].roles.ui.source}<br />view change: {PROFILES[name].viewChange.kind}
      </div>
    </div>
  );
};

export const ProfileCompare: React.FC = () => {
  const f = useCurrentFrame(), {fps} = useVideoConfig();
  const t = f / fps;
  return (
    <AbsoluteFill style={{background: '#F5F3EF'}}>
      <div style={{position: 'absolute', left: 80, top: 56, font: `500 20px ${ui}`, letterSpacing: '0.14em', textTransform: 'uppercase', color: MUTED}}>Motion profiles · same sequence, four languages</div>
      {ORDER.map((n, i) => <Column key={n} name={n} t={t} x={80 + i * 450} />)}
    </AbsoluteFill>
  );
};
