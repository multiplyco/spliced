// A Spliced profile's motion as code: a base motion profile and what the look changes about it (pace, bounce,
// stagger, scene changes, how words arrive, idle), turned into a full Profile. Spliced writes every profile of the
// project into src/profiles.generated.ts (`spliced profile code`, and whenever a profile changes); profile.tsx derives
// each one with deriveProfile, so motion('<profile>') works with no hand-written code. Only types come from spec, so
// this file runs on its own (the kit's tests run it with Node).
import type {MotionSpec, Profile, Role, ViewChangeKind} from './spec';

/** A profile's motion as Spliced stores it (profiles/<slug>/profile.json "motion"): the base, and only what it changes. */
export type ProfileMotion = {
  base: string;
  /** How long every move takes against the base: 1 = the base's, 1.25 = slower. */
  pace?: number;
  /** Overshoot on UI and emphasis: 0 = none, 0.15 = a little, 0.3 = playful. */
  bounce?: number;
  /** Seconds between grouped items. */
  stagger?: number;
  /** Scene changes the look uses, the first leading (cut, blur, fade, slide, push-in, whip, ...). */
  transition?: string[];
  /** How words arrive, the first leading (sharpen, grey-to-ink, typewriter, ...). */
  text?: string[];
  /** How much held things float (0 = still). */
  idle?: number;
};

export type GeneratedProfile = {
  name: string;
  about?: string;
  motion: ProfileMotion;
  palette?: {hex: string; name?: string}[];
  /** The palette by name (camelCase), so film code says colors.ink, never a copied hex. */
  colors?: Record<string, string>;
  fonts?: {headline?: {family: string; source?: string}; text?: {family: string; source?: string}};
  /** The logo the digest found, copied under public/: a staticFile() path. */
  logo?: string;
};

/** The scene changes the kit has a ViewChange for. The rest a film builds itself (see library scenes with the tag). */
export const TRANSITION_KINDS: Record<string, ViewChangeKind> = {
  cut: 'cut',
  'cut-on-beat': 'cut',
  blur: 'blurThrough',
  fade: 'fadeThrough',
  slide: 'sharedAxisX',
  'push-in': 'sharedAxisZ',
};

/** The word styles m.word draws. */
export const TEXT_STYLES: Record<string, 'sharpen' | 'greyToInk'> = {sharpen: 'sharpen', 'grey-to-ink': 'greyToInk'};

/** The roles a bounce applies to. */
export const BOUNCY_ROLES: Role[] = ['ui', 'emphasis'];

const round = (x: number) => Math.round(x * 1000) / 1000;

/**
 * A full Profile from a base and what a look changes:
 * - pace: every tween's seconds and every spring's duration times pace (a spring's natural frequency over pace);
 * - bounce: UI and emphasis overshoot by it (damping ratio 1 - bounce); a tween there becomes an Apple-style spring
 *   of the same length when bounce > 0, since a curve can't overshoot;
 * - stagger, idle: as given, else the base's;
 * - viewChange: the first scene change the kit has a ViewChange for, else the base's; its seconds times pace;
 * - text: the first word style m.word draws, else the base's.
 */
export const deriveProfile = (base: Profile, m: ProfileMotion, name: string, feel?: string): Profile => {
  const pace = m.pace ?? 1;
  const roles = {} as Record<Role, MotionSpec>;
  for (const r of Object.keys(base.roles) as Role[]) {
    const s = base.roles[r];
    const bounce = BOUNCY_ROLES.includes(r) ? m.bounce : undefined;
    const note = `${s.source}${pace !== 1 ? ` x${pace}` : ''}${bounce !== undefined ? `, bounce ${bounce}` : ''}`;
    if (s.kind === 'tween') {
      const raw = s.seconds * pace, seconds = round(raw);
      roles[r] = bounce && bounce > 0
        ? {kind: 'spring', spring: {omega: (2 * Math.PI) / raw, zeta: 1 - bounce}, source: `${note} (as a spring)`}
        : {...s, seconds, source: note};
    } else {
      roles[r] = {kind: 'spring', spring: {omega: s.spring.omega / pace, zeta: bounce !== undefined ? 1 - bounce : s.spring.zeta}, source: note};
    }
  }
  const kind = (m.transition ?? []).map((t) => TRANSITION_KINDS[t]).find(Boolean) ?? base.viewChange.kind;
  const style = (m.text ?? []).map((t) => TEXT_STYLES[t]).find(Boolean);
  const text = style ? {style, ...(base.text?.grey ? {grey: base.text.grey} : {})} : base.text;
  return {
    name,
    feel: feel ?? `${base.feel} (changed by its profile)`,
    roles,
    stagger: m.stagger ?? base.stagger,
    viewChange: {kind, seconds: kind === 'cut' ? 0 : round((base.viewChange.seconds || 0.6) * pace)},
    idle: m.idle ?? base.idle,
    ...(text ? {text} : {}),
  };
};
