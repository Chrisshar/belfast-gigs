// Genre drawings: fine line art, one hairline weight at every size, upright and true to each
// instrument's proportions, with one small solid detail in the brand red. Punk is the exception:
// a head in profile with a mohawk. Rendered to SVG strings at build time.
// The approved reference is prototypes/instruments.html.

export const INK = '#1f1f1d';
export const PAPER = '#ece6da';
export const RED = '#c8452f';
const BG = { bone: '#ebe5d8', mist: '#dde3e6', clay: '#ecdcd1', sage: '#dfe2d4', sand: '#efe4c9', night: '#1f1f1d' };

const line = (ink: string, d: string) => `<path d="${d}" fill="none" stroke="${ink}"/>`;

interface Instrument {
  label: string;
  bg: string;
  draw: (ink: string) => string;
}

const INSTRUMENTS = {
  rock: {
    label: 'Les Paul electric guitar',
    bg: BG.mist,
    draw: (ink) => `
      ${line(ink, 'M46 51 C38 49 33 55 35 62 C36 67 30 71 30 79 C30 88 40 94 50 94 C60 94 70 88 70 79 C70 72 64 68 65 62 C66 57 63 52 59 51 C57 53 55.5 55 54.5 57')}
      ${line(ink, 'M46 51 V16 M54.5 57 V16')}
      ${line(ink, 'M45.5 16 L44 5 H56 L54.5 16 Z')}
      <rect x="43.5" y="62" width="13" height="4" fill="${RED}"/><rect x="43.5" y="71" width="13" height="4" fill="${RED}"/>
      ${line(ink, 'M44 80 H56 M45 85 H55')}
      <circle cx="61" cy="82" r="1.6" fill="${ink}"/><circle cx="64" cy="87" r="1.6" fill="${ink}"/>`,
  },
  metal: {
    label: 'Flying V guitar',
    bg: BG.night,
    draw: (ink) => `
      ${line(ink, 'M46 50 L26 92 Q26 94.5 29 94.5 H39 L50 72 L61 94.5 H71 Q74 94.5 74 92 L54 50')}
      ${line(ink, 'M46 50 V14 M54 50 V14')}
      ${line(ink, 'M45.5 14 L50 3 L54.5 14 Z')}
      <rect x="44.5" y="54" width="11" height="3.5" fill="${RED}"/><rect x="44.5" y="60.5" width="11" height="3.5" fill="${RED}"/>
      ${line(ink, 'M45.5 67 H54.5')}`,
  },
  indie: {
    label: 'Jazzmaster guitar',
    bg: BG.sage,
    draw: (ink) => `
      ${line(ink, 'M46 50 C40 46 33 48 32 55 C31 61 37 63 35 69 C33 75 27 79 28 86 C30 94 43 95 51 92 C59 89 71 93 73 85 C75 77 66 73 66 67 C66 61 72 57 68 51 C65 47 59 48 54 51')}
      ${line(ink, 'M46 50 V16 M54 51 V16')}
      ${line(ink, 'M46 16 C44 10 45 5 51 4.5 C57 4 59 9 54 16')}
      <rect x="42" y="61" width="16" height="4.5" rx="1" fill="${RED}"/><rect x="42" y="71" width="16" height="4.5" rx="1" fill="${RED}"/>
      ${line(ink, 'M34 56 H40 M44 82 H56')}`,
  },
  songwriter: {
    label: 'Acoustic guitar',
    bg: BG.bone,
    draw: (ink) => `
      ${line(ink, 'M46 45 C38 43 33 47 33 55 C33 61 38 63 37 67 C36 71 28 74 28 82 C28 90 38 95 50 95 C62 95 72 90 72 82 C72 74 64 71 63 67 C62 63 67 61 67 55 C67 47 62 43 54 45')}
      ${line(ink, 'M46 45 V13 M54 45 V13')}
      ${line(ink, 'M45 13 V3 H55 V13 Z M47.5 5.5 V10.5 M52.5 5.5 V10.5')}
      <circle cx="50" cy="61" r="5.5" fill="${RED}"/>
      <circle cx="50" cy="61" r="8" fill="none" stroke="${ink}"/>
      ${line(ink, 'M42 81 H58')}`,
  },
  punk: {
    label: 'Mohawk, in profile',
    bg: BG.clay,
    draw: (ink) => `
      <path d="M31 51 L19 41 L34 45 L26 29 L39 39 L37 20 L46 36 L51 15 L55 34 L64 17 L62 36 L75 25 L67 41 C63 37 58 35 52 35 C43 35 36 40 32 46 Z" fill="${RED}" stroke="${ink}"/>
      ${line(ink, 'M39 97 V83 C31 79 27 68 28.5 57 C29.5 51 30.5 49 32 46 C36 40 43 35 52 35 C58 35 63 37 67 41 C70 45 71 50 71 55 L76.5 65 Q77 67 74.5 67.5 L72 68 L73 71.5 L70.5 73 L71.5 76.5 L68.5 79 C67 84 61 86 56 86 V97')}
      ${line(ink, 'M45 57 C40.5 57 40 67 45 68.5')}
      <circle cx="44.5" cy="71.5" r="1.9" fill="none" stroke="${ink}"/>
      ${line(ink, 'M61 53.5 H66')}`,
  },
  pop: {
    label: 'Microphone',
    bg: BG.sand,
    draw: (ink) => `
      <circle cx="50" cy="26" r="12" fill="none" stroke="${ink}"/>
      ${line(ink, 'M39 22 H61 M38 26 H62 M39 30 H61')}
      <rect x="42" y="37" width="16" height="4" fill="${RED}"/>
      ${line(ink, 'M42 41 L46 76 Q50 79 54 76 L58 41')}
      ${line(ink, 'M50 79 C50 88 62 86 64 92 C65 95 62 97 58 97')}`,
  },
  hiphop: {
    label: 'Turntable',
    bg: BG.mist,
    draw: (ink) => `
      <rect x="12" y="20" width="76" height="60" rx="2.5" fill="none" stroke="${ink}"/>
      <circle cx="42" cy="50" r="24" fill="none" stroke="${ink}"/>
      <circle cx="42" cy="50" r="17" fill="none" stroke="${ink}" stroke-dasharray="1 2"/>
      <circle cx="42" cy="50" r="7" fill="${RED}"/>
      <circle cx="42" cy="50" r="1" fill="${ink}"/>
      <circle cx="76" cy="30" r="4" fill="none" stroke="${ink}"/>
      ${line(ink, 'M76 34 L74 58 L66 63')}
      ${line(ink, 'M82 52 V72')}`,
  },
  electronic: {
    label: 'Synthesiser',
    bg: BG.night,
    draw: (ink) => `
      <rect x="10" y="34" width="80" height="46" rx="2" fill="none" stroke="${ink}"/>
      ${line(ink, 'M10 56 H90')}
      ${[20, 30, 40, 50].map((x) => `<circle cx="${x}" cy="45" r="3" fill="none" stroke="${ink}"/>`).join('')}
      <circle cx="60" cy="45" r="3" fill="${RED}"/>
      <rect x="68" y="41" width="16" height="8" fill="none" stroke="${ink}"/>
      ${[1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => line(ink, `M${10 + i * 8} 56 V80`)).join('')}
      ${[1, 2, 4, 5, 6, 8, 9].map((i) => `<rect x="${10 + i * 8 - 2}" y="56" width="4" height="13" fill="${ink}"/>`).join('')}`,
  },
  folk: {
    label: 'Fiddle and bow',
    bg: BG.sage,
    draw: (ink) => `
      ${line(ink, 'M50 40 C42 40 37 44 37 50 C37 55 42 56 41 60 C40 64 34 66 34 74 C34 84 41 91 50 91 C59 91 66 84 66 74 C66 66 60 64 59 60 C58 56 63 55 63 50 C63 44 58 40 50 40 Z')}
      <rect x="47.5" y="20" width="5" height="50" fill="${ink}"/>
      <circle cx="50" cy="12" r="4" fill="none" stroke="${ink}"/>
      ${line(ink, 'M48 16 V20 M52 16 V20')}
      ${line(ink, 'M42 59 C40 62 44 66 42 69 M58 59 C60 62 56 66 58 69')}
      <rect x="47" y="78" width="6" height="8" rx="1" fill="${RED}"/>
      ${line(ink, 'M82 8 V92 M80 8 H83 M79 86 H84 V92 H79 Z')}`,
  },
  country: {
    label: 'Banjo',
    bg: BG.sand,
    draw: (ink) => `
      ${line(ink, 'M47.5 47 V12 M52.5 47 V12')}
      ${line(ink, 'M47 12 V3 H53 V12')}
      <circle cx="54.5" cy="30" r="1.4" fill="${ink}"/>
      <circle cx="50" cy="68" r="21" fill="none" stroke="${RED}" class="thick"/>
      <circle cx="50" cy="68" r="17" fill="none" stroke="${ink}"/>
      ${line(ink, 'M44 78 H56 M50 86 V89')}`,
  },
  jazz: {
    label: 'Tenor saxophone',
    bg: BG.mist,
    draw: (ink) => `
      ${line(ink, 'M16 15 L23 10 L26 14 L19 19 Z')}
      <path d="M21.5 11.7 L24 15.2 L25.6 14 L23.1 10.5 Z" fill="${RED}"/>
      ${line(ink, 'M25 12.5 C31 7 38 6 42 9 C46 12 46 17 45.5 22 M22.6 16.5 C29 11 36 10.5 39 13 C41.5 15 41 19 40.5 22')}
      ${line(ink, 'M40.5 22 H45.5')}
      ${line(ink, 'M40.5 22 L36 68 C34.5 84 43 92 55 92 C67 92 75 85 75.5 75')}
      ${line(ink, 'M45.5 22 L43.5 66 C42.5 79 48 85 55 85 C62 85 67.5 81 68 74')}
      ${line(ink, 'M68 74 L66.5 50 M75.5 75 L90 45')}
      <ellipse cx="78.3" cy="46.5" rx="12" ry="3.6" transform="rotate(-8 78.3 46.5)" fill="none" stroke="${ink}"/>
      ${[[42, 31, 2.1], [41.4, 38, 2.3], [40.8, 45, 2.5], [40.1, 52, 2.7], [39.4, 59, 2.9]].map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${ink}"/>`).join('')}
      ${line(ink, 'M47.5 30 V60 M46 76 Q52 80 58 79')}
      <circle cx="71" cy="62" r="2.4" fill="none" stroke="${ink}"/><circle cx="72" cy="69" r="2.4" fill="none" stroke="${ink}"/>`,
  },
  soul: {
    label: 'Trumpet',
    bg: BG.clay,
    draw: (ink) => `
      ${line(ink, 'M8 47 H62 M14 53 H62')}
      ${line(ink, 'M62 46 L86 34 M62 54 L86 66')}
      <ellipse cx="86" cy="50" rx="3" ry="16" fill="none" stroke="${ink}"/>
      ${[30, 39, 48].map((x) => `<rect x="${x}" y="35" width="5" height="12" fill="none" stroke="${ink}"/><rect x="${x - 0.5}" y="31" width="6" height="3.5" fill="${RED}"/>`).join('')}
      ${line(ink, 'M22 53 V63 Q22 67 26 67 H52 Q56 67 56 63 V53')}
      ${line(ink, 'M4 45 V49 M4 47 H8')}`,
  },
  tribute: {
    label: 'Record and sleeve',
    bg: BG.bone,
    draw: (ink) => `
      <circle cx="64" cy="50" r="28" fill="none" stroke="${ink}"/>
      ${[23, 18, 13].map((r) => `<circle cx="64" cy="50" r="${r}" fill="none" stroke="${ink}" stroke-dasharray="1 1.6"/>`).join('')}
      <circle cx="64" cy="50" r="8" fill="${RED}"/>
      <circle cx="64" cy="50" r="1.1" fill="${ink}"/>
      <rect x="6" y="22" width="56" height="56" fill="${BG.bone}" stroke="${ink}"/>`,
  },
  world: {
    label: 'Djembe',
    bg: BG.sand,
    draw: (ink) => `
      <ellipse cx="50" cy="22" rx="24" ry="6" fill="none" stroke="${ink}"/>
      ${line(ink, 'M26 22 C26 40 38 49 44 53 L42 90 H58 L56 53 C62 49 74 40 74 22')}
      ${line(ink, 'M28 28 L36 50 L44 28 L50 52 L56 28 L64 50 L72 28')}
      <rect x="42.5" y="53" width="15" height="4" fill="${RED}"/>`,
  },
  contemporary: {
    label: 'Grand piano',
    bg: BG.bone,
    draw: (ink) => `
      ${line(ink, 'M22 80 V32 C22 21 30 15 40 15 C54 15 60 25 64 39 C68 51 74 57 80 59 Q84 61 84 67 V80 Z')}
      <rect x="22" y="80" width="62" height="8" fill="none" stroke="${ink}"/>
      ${[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13].map((i) => line(ink, `M${22 + i * 4.43} 80 V88`)).join('')}
      ${line(ink, 'M30 30 L72 72 M34 26 L76 68')}
      <rect x="34" y="72" width="34" height="3" fill="${RED}"/>`,
  },
  default: {
    label: 'Speaker',
    bg: BG.bone,
    draw: (ink) => `
      <rect x="30" y="10" width="40" height="80" rx="2" fill="none" stroke="${ink}"/>
      <circle cx="50" cy="30" r="6" fill="none" stroke="${ink}"/><circle cx="50" cy="30" r="2" fill="${ink}"/>
      <circle cx="50" cy="62" r="14" fill="none" stroke="${ink}"/><circle cx="50" cy="62" r="9" fill="none" stroke="${ink}"/>
      <circle cx="50" cy="62" r="3.5" fill="${RED}"/>`,
  },
} satisfies Record<string, Instrument>;

export type InstrumentKey = keyof typeof INSTRUMENTS;

const GENRE_INSTRUMENT: Record<string, InstrumentKey> = {
  Rock: 'rock',
  Metal: 'metal',
  'Indie/Alternative': 'indie',
  'Punk/Hardcore': 'punk',
  Pop: 'pop',
  'Hip-Hop/Rap': 'hiphop',
  Electronic: 'electronic',
  'Folk/Trad': 'folk',
  'Country/Americana': 'country',
  'Jazz/Blues': 'jazz',
  'Soul/R&B/Funk': 'soul',
  'Singer-Songwriter': 'songwriter',
  'Tribute/Covers': 'tribute',
  World: 'world',
  'Contemporary/New Music': 'contemporary',
};

/** The first genre decides; a tribute act shows as a tribute whatever else it is. */
export function instrumentFor(genres: readonly string[]): InstrumentKey {
  if (genres.includes('Tribute/Covers')) return 'tribute';
  for (const g of genres) if (GENRE_INSTRUMENT[g]) return GENRE_INSTRUMENT[g];
  return 'default';
}

export function instrumentLabel(key: InstrumentKey): string {
  return INSTRUMENTS[key].label;
}

export type ArtShape = 'square' | 'banner' | 'wide';

/** An SVG of the instrument on its background. Square for list rows, banner (2:1) for cards, wide (4:1) for gig pages. */
export function instrumentSvg(key: InstrumentKey, shape: ArtShape = 'square'): string {
  const ins: Instrument = INSTRUMENTS[key];
  const ink = ins.bg === BG.night ? PAPER : INK;
  const w = shape === 'wide' ? 400 : shape === 'banner' ? 200 : 100;
  const place = shape === 'square' ? 'translate(14 14) scale(.72)' : `translate(${(w - 76) / 2} 12) scale(.76)`;
  return `<svg class="art-svg" viewBox="0 0 ${w} 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false" preserveAspectRatio="xMidYMid slice"><rect width="${w}" height="100" fill="${ins.bg}"/><g transform="${place}">${ins.draw(ink)}</g></svg>`;
}
