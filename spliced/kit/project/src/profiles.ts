// This project's own motion profiles, beside the built-in soft, material, apple and splice (src/lib/motion,
// docs/MOTION-SYSTEMS.md). A film picks one with motion('<name>'). This file is the project's: `spliced kit update`
// never touches it. Name each one in spliced.json ("profiles") too, so boards and the app offer it.
import {appleSpec} from './lib/motion/apple';
import {sp, tw, type Profile} from './lib/motion/spec';

export const PROJECT_PROFILES = {
  // house: {
  //   name: 'house', feel: 'Calm: blur-ins, slow pushes, no bounce.',
  //   roles: {
  //     enter: tw('emphasizedDecelerate', 0.7, 'M3 emphasized decelerate 0.7s'),
  //     exit: tw('emphasizedAccelerate', 0.35, 'M3 emphasized accelerate 0.35s'),
  //     move: tw('emphasized', 0.9, 'M3 emphasized 0.9s'),
  //     ui: sp(appleSpec({duration: 0.55, bounce: 0}), 'Apple smooth spring 0.55s'),
  //     emphasis: sp(appleSpec({duration: 0.6, bounce: 0}), 'Apple smooth spring 0.6s'),
  //     camera: tw('glide', 1.0, 'kit glide 1.0s'),
  //     textReveal: tw('emphasizedDecelerate', 0.45, 'words blur in'),
  //   },
  //   stagger: 0.1, viewChange: {kind: 'blurThrough', seconds: 0.6}, idle: 0.4,
  // },
} satisfies Record<string, Profile>;
