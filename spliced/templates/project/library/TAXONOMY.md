# Taxonomy

The controlled vocabulary for tagging films and scenes. Every tag in a `breakdown.json` must come from
this file, so the index can group scenes from different films ("show me every `mask-reveal` transition").
If nothing fits, use the closest tag and describe the difference in prose. To add a tag, add it here
first with a one-line definition, then use it.

Tags are kebab-case. A scene usually has 1 tag per single-value field and 1–4 per list field.

---

## 1. Film level

### `category`: what kind of video it is (one)

| Tag | Definition |
| --- | --- |
| `feature-launch` | One new feature in an existing product, shown working. |
| `product-launch` | A new product or major version, several features or a hero overview. |
| `model-launch` | A new AI model or capability; usually outputs/demos, benchmarks, claims. |
| `event-recap` | A roundup of many announcements (a conference, a launch week). |
| `brand-film` | Feeling and positioning over features; a manifesto or "how X works". |
| `funding-announcement` | A raise, fund, accelerator or company milestone. |
| `explainer` | How something works, step by step. |
| `customer-story` | Told through a customer, quotes or logos. |
| `social-promo` | Short, single-message, built for the feed (a challenge, a teaser, a CTA). |
| `teaser` | Withholds the product; mood and anticipation. |
| `system-specimen` | Not a reference: a specimen of our own motion kit's moves (library film `system-moves`). |

### `format` (one): `16x9`, `9x16`, `1x1`, `4x5`

### `voice` (one): how the words reach the viewer

`on-screen-type-only` · `voice-over` · `on-camera-speaker` · `dialogue` · `none`

### `music_feel` (1–3)

`driving-electronic` · `minimal-pulse` · `piano-ambient` · `orchestral-swell` · `indie-pop` · `hip-hop-beat` ·
`synth-wave` · `acoustic-warm` · `sound-design-only` · `silent`

---

## 2. Scene level

### `role`: what the scene does in the story (one)

| Tag | Definition |
| --- | --- |
| `cold-open` | Opens before the brand or topic is clear; a texture, a sound, an image. |
| `hook` | The first claim or tension that makes you keep watching. |
| `problem` | The "before": the mess, the pain, the old way. |
| `headline` | The news in words: "Introducing X", "You can now…". |
| `product-reveal` | First full look at the product, device or UI. |
| `feature-demo` | A feature doing its job on screen. |
| `use-case` | A specific job a user gets done (often title → action → result). |
| `proof` | A number, benchmark, quote, logo wall, testimonial. |
| `montage` | Fast run of many things to show breadth. |
| `bridge` | Moves from one section to the next; carries no new message. |
| `payoff` | The line that sums it up. |
| `end-card` | Logo, lockup, URL, date, CTA. |

### `world`: the visual environment (one)

| Tag | Definition |
| --- | --- |
| `white-stage` | Pure or near-white space; UI and type float on it. |
| `light-tint-stage` | Pale coloured or off-white flat background. |
| `dark-stage` | Black or near-black flat space. |
| `colour-field` | A saturated flat brand colour fills the frame. |
| `gradient-field` | A soft multi-colour gradient or mesh, often blurred or textured. |
| `brand-texture` | A photographic or rendered brand texture/plate (not a CSS gradient). |
| `ui-fullscreen` | The product UI fills the frame, no stage around it. |
| `device-in-space` | A device (laptop, phone, car) as a rendered object in a 3D or studio space. |
| `live-action` | Filmed people, places or objects. |
| `live-action-composite` | Footage with UI, type or graphics composited into the scene (tracked or floating). |
| `ai-generated-imagery` | Generated stills or video as the main subject. |
| `illustration` | Drawn/vector characters or scenes. |
| `collage` | Mixed media: cut-outs, photos, UI, type layered together. |
| `3d-abstract` | Rendered abstract forms, materials, particles. |
| `shadow-stage` | A pale flat stage crossed by soft window-light shadows that drift slowly. |

### `subject`: what we're looking at (1–3)

`ui-rebuild` (crisp vector UI, clearly rebuilt) · `ui-screen-recording` · `ui-fragment` (one card, button,
input or panel isolated) · `device` · `typography` · `logo` · `people` · `hands` · `product-object` ·
`data-viz` · `abstract-shapes` · `icons` · `generated-media` · `cursor` · `nature-place` ·
`ai-working-state` (an abstract "thinking/generating" loader as the subject)

### `camera` (1–2): how the virtual or real camera behaves

| Tag | Definition |
| --- | --- |
| `locked` | Doesn't move. |
| `hold-push` | Slow constant push-in on a hold, almost unnoticeable. |
| `push-in` | A deliberate move in to a detail. |
| `pull-back-reveal` | Starts close, pulls out to reveal context. |
| `pan-track` | Slides sideways/vertically across a layout, or follows something. |
| `macro-ui` | Very close on a UI element (button, text, cursor), 2x+ scale. |
| `fly-through` | Flies into/through an element (a letter, a window) to the next scene. |
| `orbit-3d` | Rotates around a 3D object or tilted UI plane. |
| `tilted-plane` | UI laid in perspective (isometric or tilted) rather than flat to camera. |
| `handheld` | Live-action handheld or simulated shake. |
| `parallax-layers` | Foreground/background layers move at different speeds. |

### `motion`: how elements move (1–4)

| Tag | Definition |
| --- | --- |
| `arrive-soft` | Fast start, long soft settle (expo/quart out). No bounce. |
| `spring-overshoot` | Lands past its mark and settles back; bouncy, playful. |
| `snap-mechanical` | Very short, near-linear moves; precise, techy. |
| `stagger-cascade` | A group arrives one after another, 2–6 frames apart. |
| `word-by-word` | Text appears a word at a time (fade, blur-in, rise). |
| `typewriter` | Text types character by character, usually in an input. |
| `mask-reveal` | Elements wipe on through a mask or clip (line, shape, pill). |
| `scale-pop` | Pops in from small scale (with or without overshoot). |
| `blur-in` | Sharpens from blur as it arrives. |
| `morph` | One shape/element becomes another (size, shape, colour). |
| `shared-element` | The same element continues across scenes, moving to a new role. |
| `inline-swap` | A word/icon inside a line swaps in place (rotating word, icon chip). |
| `count-up` | Numbers count up. |
| `draw-on` | Lines, charts or strokes draw themselves. |
| `data-reshuffle` | Items sort/filter/re-rank, flying to new slots. |
| `loop-float` | Idle float, hover, gentle drift. |
| `kinetic-type` | Type itself moves big: scale, rotation, tracking, slides as the main action. |
| `ui-interaction` | Clicks, typing, hovering, as a user would. |
| `physics-tumble` | Things fall, scatter, pile, collide. |
| `glitch-distort` | RGB split, scanlines, distortion, datamosh. |
| `speed-ramp` | Footage or motion speeds up/slows down sharply. |
| `slot-reel` | A word, digit or icon spins through options like a slot machine and lands on one. |
| `scramble-type` | Characters show as random glyphs first, then resolve into the real text. |
| `type-highlight-sweep` | Words in a static line change colour in reading order, as if read aloud. |
| `fly-past` | Type scales past the lens while the camera pushes through it. |
| `ink-boil` | Hand-drawn texture redrawn every 2–3 frames so line art never sits still. |
| `restyle-cycle` | The same subject or word holds its place while its style or material swaps, hard cuts every 0.1–0.7s. |
| `doodle-to-real` | A sketch, box or note drawn on an image is replaced by the rendered result in the same framing. |
| `image-swarm` | Hundreds of thumbnails burst, drift or collapse like particles. |
| `liquid-type` | Letters form from, or melt into, gooey ink blobs. |
| `blueprint-reveal` | A finished image cuts or strobes to its own labelled construction drawing (outlines, grid, callouts) in the same layout. |

### `transition_in`: how this scene arrives (one)

| Tag | Definition |
| --- | --- |
| `hard-cut` | A straight cut. |
| `cut-on-beat` | A cut placed on a music beat or accent. |
| `match-cut` | Cuts between two shots that share a shape, position or motion. |
| `morph-transition` | An element from the previous scene transforms into this one. |
| `shared-element-carry` | An element stays and the world changes around it. |
| `mask-wipe` | A shape, pill or line wipes the new scene on. |
| `colour-wipe` | A flat colour field sweeps across, carrying the cut. |
| `zoom-through` | Camera zooms into something and out into the next scene. |
| `pull-out-transition` | The previous scene shrinks into a frame/window in the new scene. |
| `whip-pan` | Fast blurred pan into the next scene. |
| `crossfade` | Dissolve. |
| `blur-dissolve` | Blur out of one and sharpen into the next. |
| `dip-to-colour` | Fades through white, black or brand colour. |
| `push-slide` | The new scene pushes the old one out of frame. |
| `none` | First scene of the film. |
| `continuous-move` | The scene changes inside one unbroken camera move; any cut is hidden in blur or a foreground wipe. |
| `iris` | A circular or vignette mask closes on one scene and opens the next. |

### `type_treatment` (0–3)

| Tag | Definition |
| --- | --- |
| `centered-headline` | Big, centred, few words. |
| `left-aligned-headline` | Big, flush-left. |
| `quote` | Quote marks, attribution. |
| `inline-icon-chips` | Icons, logos or avatars inside a line of text. |
| `type-over-footage` | Type laid over live action or imagery. |
| `type-in-ui` | The words are part of the UI (prompt, chat, button). |
| `label-callout` | Small labels, lines or pointers annotating something. |
| `oversized-crop` | Type so big it crops out of the frame. |
| `serif-editorial` | A serif or editorial face as the voice. |
| `mono-technical` | Monospace or terminal type. |
| `stat-number` | A big number as the hero. |
| `lower-third` | Small text in a lower or corner position. |
| `world-locked-type` | Type tracked into footage: it moves with the scene and can pass behind objects. |
| `object-in-line` | A product or object sits between words of a sentence. |
| `right-aligned-headline` | Big, flush-right. |

### `pace` (one): read from shot length and motion energy

| Tag | Shots last about | Feels |
| --- | --- | --- |
| `slow` | 4s+ | Calm, premium, room to read |
| `medium` | 2–4s | Steady, explanatory |
| `fast` | 0.8–2s | Energetic |
| `rapid-fire` | under 0.8s | Montage, beat-driven |

### `energy` (one): `calm` · `steady` · `punchy` · `frantic`

### `sound_sync` (0–3): what the picture is locked to

`cuts-on-beat` · `motion-on-beat` · `sfx-per-element` · `typing-sfx` · `music-drop-reveal` · `vo-led` · `none-visible`

### `production` (1–2): what it would take to recreate

| Tag | Means |
| --- | --- |
| `code-only` | Doable entirely in Remotion/HTML: UI, type, shapes, gradients. |
| `code-plus-generated` | Code for the layout and motion, plus generated images or video. |
| `generated-video` | The shot itself is AI video (or could be). |
| `3d-render` | Needs a 3D tool (Blender, Cinema 4D) or a generated 3D clip. |
| `live-shoot` | Needs real filming; for us, a generated-video stand-in or skip. |
| `stock-footage` | Could be stock footage plus code overlays. |
