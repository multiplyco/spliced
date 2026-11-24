# Motion systems: Material 3, Apple-style motion and Liquid Glass

`src/lib/motion/` brings two design systems' motion into the kit, plus a Liquid-Glass-style material, behind one
semantic layer: **motion profiles**. Every function takes film time `t` in seconds, so any frame renders on its own.

**Specimens** (open in `npm run dev`, or watch the renders in `docs/media/`, rebuilt with `npm run specimens`):

| Composition | Render | Shows |
| --- | --- | --- |
| `Specimen-Profiles` | `motion-profiles.mp4` | The same sequence under each profile, side by side: choose a film's profile here |
| `Specimen-Moves` | `system-moves.mp4` | Every move alone (24). Also in the library as the film `system-moves`: open **Systems** in Spliced |
| `Specimen-MotionSystems` | `motion-systems.mp4` | Curves and springs compared, the four transitions at once, icon effects, glass |

## Profiles: start here

Film code asks for a **role**, never a raw curve. A profile maps each role to one system's token:

```ts
import {motion} from '../../lib/motion';
const m = motion('soft');                   // one line decides the film's motion language
m.enter(t, cue)    m.exit(t, cue)    m.move(t, cue)    m.ui(t, cue)    m.emphasis(t, cue)    m.camera(t, cue)
m.textReveal(t, cue, i)                    // i-th word / card / row, staggered by the profile
<m.ViewChange t={t} start={cue} from={<A/>} to={<B/>} />
m.seconds('enter')                         // how long a role takes, for laying out cues.json
m.idle(t, k)                               // never-still float for holds
```

| Role | `soft` | `material` | `apple` | `splice` (Spliced app) |
| --- | --- | --- | --- | --- |
| enter | kit land 0.6s | emphasized decelerate 0.8s | smooth spring 0.6s | Spliced ease-out 0.75s |
| exit | emphasized accelerate 0.3s | emphasized accelerate 0.4s | accelerate 0.3s | emphasized accelerate 0.3s |
| move | kit land 0.75s | emphasized 1.0s | smooth spring 0.7s | Spliced ease-out 0.85s |
| ui | kit land 0.45s | expressive default spatial | snappy spring | Spliced ease-ui 0.4s |
| emphasis | kit land 0.5s | expressive fast spatial | bouncy spring 0.6s | Spliced ease-sink 0.9s |
| camera | kit glide 1.0s | emphasized 1.4s | smooth spring 1.1s | Spliced ease-sink 1.0s |
| textReveal | kit land 0.5s, 0.1s apart | emphasized decelerate 0.6s, 0.05s | smooth spring 0.5s, 0.06s | Spliced ease-out 0.55s sharpen, 0.07s |
| view change | cut | shared axis Z | shared axis X | blur through 0.5s |

`splice` is the Spliced app's own language, from its brand tokens (`Spliced's web/splice-tokens.css`: ease-out, ease-ui, ease-sink), film-slowed; first used by the `splice-explainer` film.

**Your own profile.** A project adds its own in `src/profiles.ts` (the project's file: `spliced kit update` never
touches it), written with the same `tw()` and `sp()` helpers as the built-in ones, for example a house profile tuned
to the brand's own film. `Specimen-Profiles` shows the first of them beside `soft`, `material` and `apple`, so you can
tune it by eye, and every film using it follows. Add its name and one line on how it feels to `spliced.json`
(`"profiles"`), so boards and the app offer it.

**Words in the profile's style:** `m.word(t, cue, i, ink)` returns a style for the i-th word: blur-and-rise, or
grey-to-ink for a profile with `text: {style: 'greyToInk'}` (words land light grey and darken to ink). Spread it on a `<span>`; unsaid words keep their space, so lines never shift.

**The motion check** (`npm run check:motion`, `Spliced's check_motion.py`) flags easing curves, springs and GSAP-style
eases written inline in film code. A line can opt out with `// motion-ok: <reason>`.

## Use one motion language per film

Pick one and use it everywhere: Material's curves and transitions, Apple's springs, or our own `land`/`glide`.
Mixing systems in one film reads as inconsistent. The brand (colour, type, logo) stays the brand's either way.

| If the film feels... | Use |
| --- | --- |
| Precise, editorial, "productivity tool" | Material 3: `m3Tween(..., 'emphasized')` for moves, the transition patterns for view changes |
| Physical, friendly, tactile | Apple-style springs: `appleSpringAt(t, start, 'snappy')`, symbol effects on icons |
| Calm, premium, white stage | `motion('soft')`: `land` for arrivals (fast, then a soft landing), `glide` for the camera |

## Film timing

Both systems are tuned for someone using an app (a 300ms transition). A viewer watching a film needs longer,
so the Material helpers stretch durations by `FILM_STRETCH` (2x) by default, and `m3Spring` slows springs by the
same factor while keeping their damping, so the character (overshoot) stays the same. Pass `film: 1` for the
literal tokens. Apple springs take their duration directly, so choose a film-length one (0.6–1.0s for UI moves).

## Material 3 (`material3.ts`, `M3Transitions.tsx`)

**Easing** (`M3_EASING`, `m3Tween(t, start, duration, easing)`):

| Token | Curve |
| --- | --- |
| `emphasized` | Two-segment path (slow start, fast middle, long settle). The default for most moves. The web tokens approximate it with standard's curve; we use the true path. |
| `emphasizedDecelerate` | `cubic-bezier(0.05, 0.7, 0.1, 1)`: things entering |
| `emphasizedAccelerate` | `cubic-bezier(0.3, 0, 0.8, 0.15)`: things leaving |
| `standard` | `cubic-bezier(0.2, 0, 0, 1)`: small utility moves |
| `standardDecelerate` / `standardAccelerate` | `(0, 0, 0, 1)` / `(0.3, 0, 1, 1)` |
| `legacy` (+ accelerate / decelerate) | `(0.4, 0, 0.2, 1)`: Material 2's FastOutSlowIn |

**Durations** (`M3_DURATION`, ms): short1–4 = 50/100/150/200, medium1–4 = 250/300/350/400,
long1–4 = 450/500/550/600, extraLong1–4 = 700/800/900/1000.

**Springs** (`m3SpringAt(t, start, token, scheme)`): pick the speed by the size of what moves (fast for small
components, default for medium, slow for full screen). Spatial springs move position and size; effects springs
change opacity and colour and never overshoot.

| Token | Expressive (ratio, stiffness) | Standard (ratio, stiffness) |
| --- | --- | --- |
| fastSpatial | 0.6, 800 | 0.9, 1400 |
| defaultSpatial | 0.8, 380 | 0.9, 700 |
| slowSpatial | 0.8, 200 | 0.9, 300 |
| fast / default / slow effects | 1, 3800 / 1600 / 800 | same |

**Transition patterns** (components; each takes `t`, `start`, `from`, `to`):

| Pattern | Use when | Component |
| --- | --- | --- |
| Container transform | An element becomes the next view (a card opens, a chip becomes a panel) | `<ContainerTransform fromBox toBox fromSize toSize>` |
| Shared axis X / Y | Steps in a sequence (next / previous, onboarding, tabs) | `<SharedAxis axis="x" back?>` |
| Shared axis Z | Into / out of a level (list to detail) | `<SharedAxis axis="z">` |
| Fade through | Unrelated views (switching sections) | `<FadeThrough>` |
| Fade | Something appearing within a view (dialog, menu, toast) | `<Fade out?>` |

## Apple-style (`apple.ts`)

**Springs** are a perceptual `duration` and a `bounce`: 0 is smooth (critically damped, SwiftUI's default),
about 0.15 is a small bounce, about 0.3 is noticeably bouncy, and Apple advises care above about 0.4. Negative
bounce flattens. Presets: `smooth` (0.5s, 0), `snappy` (0.5s, 0.15), `bouncy` (0.5s, 0.3).
`appleSpringAt(t, start, 'snappy')` or `appleSpringAt(t, start, {duration: 0.8, bounce: 0.2})`.
`appleToRemotion(spec)` gives the equivalent `{mass, stiffness, damping}` for Remotion's `spring()`.

**Symbol effects** (`symbolFX.<name>(t, start)` returns `{transform, opacity, filter}` for any icon):
`bounce` (tap / done), `pulse` (working), `breathe` (alive, waiting), `wiggle` (look here), `rotate`
(in progress), `appear` (springs in), `replace` (old out, new springs in; call with `'out'` and `'in'`).
Use them on our own icons (Lucide is in the kit).

## Liquid Glass (`LiquidGlass.tsx`)

```tsx
<GlassBackdrop t={t} />                       {/* the scene, drawn once normally */}
<LiquidGlass
  shapes={[{cx: 960, cy: 820, w: 560, h: 124, r: 62}, {cx: 1300, cy: 800, w: 140, h: 140, r: 70}]}
  backdrop={() => <GlassBackdrop t={t} />}    {/* and once more, inside the glass */}
  blend={70} refraction={42} bevel={40} frost={5}
/>
```

- **Shapes** are rounded rects (a pill when `r = h/2`, a circle when `w = h = 2r`). Animate their numbers with
  any of the springs above. Shapes closer than `blend` px melt together with a liquid neck and split apart the
  same way: Apple's morphing glass.
- **Look:** `refraction` (how far the rim bends the backdrop, px), `bevel` (how wide the curved rim is),
  `frost` (blur: 0 is Apple's "clear" variant, 4–8 is "regular"), `saturate`, `brightness`, `tint`, `rim`
  (highlight strength), `lightAngle` (degrees; -120 is top-left), `shadow`.
- **The backdrop must be passed in** and drawn in frame coordinates, because the glass renders it a second time to
  bend it. This avoids `backdrop-filter`, which is unreliable in headless rendering.
- **Cost:** the maps are painted on a canvas every frame at half resolution (`res`). The 17s specimen renders in
  about 11s at 1080p. For a 4K master, set `res={1}`.
- **Apple's guidance:** use glass for controls and navigation that float over content, not for content itself;
  larger glass refracts more; "clear" glass needs bright, bold content around it.

## How sure the values are

| Values | Source | Confidence |
| --- | --- | --- |
| M3 easing and durations | material-web tokens v0_192 and Jetpack Compose MotionTokens (they agree) | Confirmed |
| M3 emphasized path | material-components-android `docs/theming/Motion.md` | Confirmed |
| M3 expressive springs | Compose `ExpressiveMotionTokens.kt` | Confirmed |
| M3 standard springs | material-components-android `MaterialSpring` table | Likely (Compose's standard tokens not cross-checked) |
| Transition choreography (35% fade split, 92% scale, shared-axis slide, Z scales, container fade thresholds) | material-components-android defaults as we know them | Unconfirmed: the M3 site is JS-rendered. Tune by eye |
| Apple spring model (duration, bounce → stiffness, damping) | WWDC23 "Animate with springs" | Confirmed |
| Apple preset numbers (0.5s; 0 / 0.15 / 0.3) | SwiftUI defaults as we know them; match WWDC guidance | Unconfirmed: the docs pages are JS-rendered |
| Liquid Glass | Our own approximation from WWDC25 "Meet Liquid Glass" (lensing, highlights, adaptive shadow, morphing) | Apple publishes no numbers |

## Licensing

Copy the motion and the look, never the assets: no SF Symbols, Apple UI kits, system screenshots or device
renders in your films. Material Symbols icons are Apache 2.0 and free to use.

## From library tags to helpers

When a board borrows a reference scene, its tags point to the helper that builds the move:

| Library tag | Build it with |
| --- | --- |
| `arrive-soft`, `blur-in`, `word-by-word` | `m.enter`, `m.textReveal(t, cue, i)` with blur and rise |
| `stagger-cascade` | any role with `m.stagger(i)` added to the start |
| `spring-overshoot`, `scale-pop` | `m.ui` / `m.emphasis` (springs), or `appleSpringAt` |
| `morph`, `shared-element` | `ContainerTransform`, or interpolate boxes with `m.move` |
| `inline-swap`, `slot-reel` | `symbolFX.replace` for icons; a vertical reel driven by `m.move` |
| `loop-float` | `m.idle`, `symbolFX.pulse` / `breathe` / `rotate` |
| `push-slide`, `zoom-through`, `crossfade`, `blur-dissolve` (transition in) | `<m.ViewChange kind="sharedAxisX" / "sharedAxisZ" / "fadeThrough" / "blurThrough">` |
| `pull-back-reveal`, `push-in`, `hold-push`, `macro-ui` (camera) | `m.camera` driving one camera transform (scale and translate) shared by everything in the shot; `holdPush` (`hold.ts`) for holds |
| `mask-reveal`, `mask-wipe`, `colour-wipe`, `iris` | a clip-path or mask whose size runs on `m.move` |
| frosted or glass objects (`shadow-stage`) | `LiquidGlass` (`frost` 4 to 8 for regular, 0 for clear) |

Moves with no helper yet (`liquid-type`, `scramble-type`, `image-swarm`, `restyle-cycle`, `doodle-to-real`) are built
per film from the scene's Recreate notes; when one is reused, promote it into `src/lib/motion/`.
