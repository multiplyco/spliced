// The specimens' type: Manrope (headings, the house film type) and Inter (labels), from Google Fonts at render time.
import {loadFont as loadManrope} from '@remotion/google-fonts/Manrope';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';

export const display = loadManrope('normal', {weights: ['400', '500', '600', '700'], subsets: ['latin']}).fontFamily;
export const ui = loadInter('normal', {weights: ['400', '500', '600'], subsets: ['latin']}).fontFamily;
