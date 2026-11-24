// Every motion-system move on its own, one after another, labelled: composition "Specimen-Moves".
// The render (docs/media/system-moves.mp4) is registered in the library as the film `system-moves`
// (Spliced's build_system_moves.py), so each move is a scene you can filter, review and put on a board.
// The list lives in moves.json; add a move there and a demo in DEMOS. Only ever APPEND moves: scene IDs
// (system-moves/sNN) are positions, and boards refer to them.
import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {Bell, CircleCheck, Heart, Loader, Sparkles, Star, Wand2} from 'lucide-react';
import data from './moves.json';
import {display, ui} from './type';
import {
  ContainerTransform, Fade, FadeThrough, LiquidGlass, M3_EASING, SharedAxis, appleSpringAt, clamp01, lerp, m3SpringAt, m3Tween,
  appleSpec, motion, sp, symbolFX, tw, type FX, type Profile,
} from '../lib/motion';
import {Chip, GlassBackdrop, Screen} from './MotionSystems';

const INK = '#0B152B', MUTED = 'rgba(11,21,43,0.5)', BG = '#F5F3EF';
const A = data.action_at;
export const MOVES = data.moves;
export const MOVES_SECONDS = MOVES.length * data.scene_seconds;

const S1 = <Screen hue="#5B47E0" title="Workspace" />;
const S2 = <Screen hue="#E8613C" title="Brief" rows={3} />;
const PANE: React.CSSProperties = {position: 'absolute', left: 960 - 280, top: 540 - 250 - 40, width: 560, height: 500, borderRadius: 28, overflow: 'hidden', boxShadow: '0 30px 80px rgba(15,20,40,0.12)'};
const Card: React.FC<{x?: number; y?: number; s?: number; label?: string; hue?: string}> = ({x = 960, y = 500, s = 1, label = 'Brief ready', hue = '#5B47E0'}) => (
  <div style={{position: 'absolute', left: x - 200, top: y - 70, width: 400, height: 140, borderRadius: 28, background: '#fff', transform: `scale(${s})`,
    boxShadow: '0 24px 60px rgba(15,20,40,0.12)', display: 'flex', alignItems: 'center', gap: 18, padding: '0 28px', font: `600 32px ${ui}`, color: INK}}>
    <div style={{width: 56, height: 56, borderRadius: 16, background: hue}} />{label}
  </div>
);
const Icon: React.FC<{fx: FX; children: React.ReactNode}> = ({fx, children}) => (
  <div style={{position: 'absolute', left: 960 - 150, top: 500 - 150, width: 300, height: 300, borderRadius: 72, background: '#fff', display: 'grid', placeItems: 'center', color: INK, boxShadow: '0 24px 60px rgba(15,20,40,0.10)'}}>
    <div style={{...fx, display: 'grid'}}>{children}</div>
  </div>
);
const rep = (s: number, period: number) => A + Math.floor(Math.max(0, s - A) / period) * period;
const soft = motion('soft');
/** A calm profile whose words land light grey and darken to ink, with blur dissolves between views: the text style
 * and view change two of the moves show. Any profile can use them (`text: {style: 'greyToInk'}`). */
const GREY_TO_INK: Profile = {
  name: 'grey-to-ink', feel: 'Calm: blur-ins, slow pushes, grey-to-ink type, no bounce.',
  roles: {
    enter: tw('emphasizedDecelerate', 0.7, 'M3 emphasized decelerate 0.7s'),
    exit: tw('emphasizedAccelerate', 0.35, 'M3 emphasized accelerate 0.35s'),
    move: tw('emphasized', 0.9, 'M3 emphasized 0.9s'),
    ui: sp(appleSpec({duration: 0.55, bounce: 0}), 'Apple smooth spring 0.55s (no bounce)'),
    emphasis: sp(appleSpec({duration: 0.6, bounce: 0}), 'Apple smooth spring 0.6s (no bounce)'),
    camera: tw('glide', 1.0, 'kit glide 1.0s'),
    textReveal: tw('emphasizedDecelerate', 0.45, 'grey-to-ink: land grey, darken over ~0.3s'),
  },
  stagger: 0.11, viewChange: {kind: 'blurThrough', seconds: 0.7}, idle: 0.4,
  text: {style: 'greyToInk', grey: '#C9C9CE'},
};

/** Demos take local time s (seconds into the scene); the move starts at A. */
const DEMOS: Record<string, (s: number) => React.ReactNode> = {
  'm3-container-transform': (s) => (
    <ContainerTransform t={s} start={A} from={<Chip />} to={S2} fromBox={{x: 960 - 160, y: 420, w: 320, h: 80, r: 40}} toBox={{x: 960 - 280, y: 230, w: 560, h: 500, r: 28}}
      fromSize={{w: 320, h: 80}} toSize={{w: 560, h: 500}} />
  ),
  'm3-shared-axis-x': (s) => <SharedAxis t={s} start={A} axis="x" from={S1} to={S2} style={PANE} />,
  'm3-shared-axis-y': (s) => <SharedAxis t={s} start={A} axis="y" from={S1} to={S2} style={PANE} />,
  'm3-shared-axis-z': (s) => <SharedAxis t={s} start={A} axis="z" from={S1} to={S2} style={PANE} />,
  'm3-fade-through': (s) => <FadeThrough t={s} start={A} from={S1} to={S2} style={PANE} />,
  'm3-fade': (s) => (
    <>
      <div style={{...PANE, opacity: 0.5}}>{S1}</div>
      <Fade t={s} start={A} style={{position: 'absolute', left: 960 - 220, top: 380, width: 440, transformOrigin: '50% 50%'}}>
        <div style={{height: 180, borderRadius: 28, background: '#fff', boxShadow: '0 30px 80px rgba(15,20,40,0.2)', padding: 28, font: `600 30px ${ui}`, color: INK}}>Share this brief?<div style={{marginTop: 22, height: 14, width: '70%', borderRadius: 7, background: 'rgba(11,21,43,0.08)'}} /></div>
      </Fade>
    </>
  ),
  'm3-emphasized-move': (s) => <Card x={lerp(560, 1360, m3Tween(s, A, 'long2', 'emphasized'))} />,
  'm3-expressive-pop': (s) => <Card s={Math.max(0, m3SpringAt(s, A, 'fastSpatial', 'expressive'))} />,
  'apple-smooth-move': (s) => <Card x={lerp(560, 1360, appleSpringAt(s, A, {duration: 0.8, bounce: 0}))} hue="#E8613C" />,
  'apple-snappy-pop': (s) => <Card s={lerp(0.4, 1, appleSpringAt(s, A, 'snappy'))} hue="#E8613C" label="Approved" />,
  'apple-bouncy-pop': (s) => <Card s={lerp(0.4, 1, appleSpringAt(s, A, 'bouncy'))} hue="#E8613C" label="Approved" />,
  'fx-bounce': (s) => <Icon fx={symbolFX.bounce(s, rep(s, 1.0))}><Bell size={150} /></Icon>,
  'fx-pulse': (s) => <Icon fx={symbolFX.pulse(s, A)}><Loader size={150} /></Icon>,
  'fx-breathe': (s) => <Icon fx={symbolFX.breathe(s, A, 1.8)}><Heart size={150} /></Icon>,
  'fx-wiggle': (s) => <Icon fx={symbolFX.wiggle(s, rep(s, 1.0))}><Sparkles size={150} /></Icon>,
  'fx-rotate': (s) => <Icon fx={symbolFX.rotate(s, A)}><Loader size={150} /></Icon>,
  'fx-appear': (s) => <Icon fx={symbolFX.appear(s, A)}><Star size={150} /></Icon>,
  'fx-replace': (s) => (
    <Icon fx={{transform: 'none', opacity: 1}}>
      <div style={{position: 'relative', width: 150, height: 150}}>
        <div style={{position: 'absolute', inset: 0, ...symbolFX.replace(s, A, 'out')}}><Wand2 size={150} /></div>
        <div style={{position: 'absolute', inset: 0, ...symbolFX.replace(s, A, 'in'), color: '#1F8A4C'}}><CircleCheck size={150} /></div>
      </div>
    </Icon>
  ),
  'kit-word-sharpen': (s) => (
    <div style={{position: 'absolute', left: 0, right: 0, top: 420, textAlign: 'center', font: `500 120px ${display}`, letterSpacing: '-0.04em', color: INK}}>
      {'Your brief is ready.'.split(' ').map((w, i) => {
        const k = soft.textReveal(s, A, i);
        return <span key={i} style={{display: 'inline-block', marginRight: 28, opacity: k, filter: `blur(${10 * (1 - k)}px)`, transform: `translateY(${18 * (1 - k)}px)`}}>{w}</span>;
      })}
    </div>
  ),
  'kit-glide-camera': (s) => {
    const k = soft.camera(s, A);
    return (
      <div style={{position: 'absolute', inset: 0, transformOrigin: '1180px 610px', transform: `scale(${lerp(1, 2.1, k)})`}}>
        {[0, 1, 2, 3, 4, 5].map((i) => <Card key={i} x={560 + (i % 3) * 420} y={380 + Math.floor(i / 3) * 230} s={0.9} label={['Brief', 'Notes', 'Plans', 'Drafts', 'Review', 'Email'][i]} hue={i === 4 ? '#E8613C' : '#C9C3F2'} />)}
      </div>
    );
  },
  'blur-through': (s) => {
    const {ViewChange} = motion(GREY_TO_INK);
    return <ViewChange kind="blurThrough" t={s} start={A} from={S1} to={S2} style={PANE} />;
  },
  'grey-to-ink': (s) => {
    const m = motion(GREY_TO_INK);
    return (
      <div style={{position: 'absolute', left: 0, right: 0, top: 420, textAlign: 'center', font: `700 104px ${display}`, letterSpacing: '-0.035em'}}>
        {'Words land grey, then turn to ink.'.split(' ').map((w, i) => <span key={i} style={{...m.word(s, A, i, '#0B0B0D'), marginRight: 26}}>{w}</span>)}
      </div>
    );
  },
  'glass-pill': (s) => <GlassScene s={s} variant="pill" />,
  'glass-split-merge': (s) => <GlassScene s={s} variant="split" />,
  'glass-morph-card': (s) => <GlassScene s={s} variant="morph" />,
};

const GlassScene: React.FC<{s: number; variant: 'pill' | 'split' | 'morph'}> = ({s, variant}) => {
  const t = 20 + s; // keep the backdrop drifting
  const grow = variant === 'pill' ? appleSpringAt(s, A, {duration: 0.7, bounce: 0.25}) : 1;
  const k = variant === 'morph' ? M3_EASING.emphasized(clamp01((s - A) / 1.2)) : 0;
  const out = variant === 'split' ? appleSpringAt(s, A, {duration: 0.8, bounce: 0.2}) - appleSpringAt(s, A + 0.9, {duration: 0.8, bounce: 0.15}) : 0;
  const pill = {cx: 960, cy: lerp(560, 520, k), w: lerp(560, 760, k) * Math.max(0.05, grow), h: lerp(124, 380, k) * Math.max(0.05, grow), r: lerp(62, 56, k)};
  const shapes = variant === 'split' ? [pill, {cx: 960 + 210 + 300 * out, cy: 560 - 40 * out, w: 140, h: 140, r: 70}] : [pill];
  return (
    <AbsoluteFill>
      <GlassBackdrop t={t} />
      <LiquidGlass shapes={shapes} backdrop={() => <GlassBackdrop t={t} />} blend={70} refraction={42} bevel={40} frost={5} />
    </AbsoluteFill>
  );
};

export const SystemMoves: React.FC = () => {
  const f = useCurrentFrame(), {fps} = useVideoConfig();
  const t = f / fps;
  const i = Math.min(MOVES.length - 1, Math.floor(t / data.scene_seconds));
  const mv = MOVES[i], s = t - i * data.scene_seconds;
  const glass = mv.key.startsWith('glass');
  return (
    <AbsoluteFill style={{background: BG}}>
      {DEMOS[mv.key]?.(s)}
      <div style={{position: 'absolute', left: 80, bottom: 70, right: 80, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between'}}>
        <div style={glass ? {background: 'rgba(255,255,255,0.75)', padding: '14px 20px', borderRadius: 18} : undefined}>
          <div style={{font: `500 20px ${ui}`, letterSpacing: '0.14em', textTransform: 'uppercase', color: MUTED}}>{mv.system} · {mv.key}</div>
          <div style={{font: `500 40px ${display}`, letterSpacing: '-0.02em', color: INK, marginTop: 6}}>{mv.title}</div>
        </div>
        <div style={{font: `500 22px ${ui}`, color: MUTED}}>{String(i + 1).padStart(2, '0')} / {MOVES.length}</div>
      </div>
    </AbsoluteFill>
  );
};
