// Logo options. Each mark is drawn on a 40x40 grid with hairline strokes and one red accent,
// to sit with the line-art instruments. logoMark(key) -> "<svg>", logo(key) -> mark + wordmark.
const LOGO_INK = "#1f1f1d", LOGO_RED = "#c8452f";
const LOGO_STYLE = `<style>.lg path,.lg circle,.lg rect,.lg line{vector-effect:non-scaling-stroke;stroke-linecap:round;stroke-linejoin:round}</style>`;

const LOGO_MARKS = {
  // Samson and Goliath, the Harland & Wolff gantry cranes, with a red disc between the legs:
  // a setting sun over the shipyard, or a record.
  cranes: (ink) => `
    <path d="M12.5 35 A7.5 7.5 0 0 1 27.5 35 Z" fill="${LOGO_RED}"/>
    <path d="M1.5 6.5 H38.5 V10 H1.5 Z" fill="none" stroke="${ink}" stroke-width="1.3"/>
    <path d="M4 10 L6 35 M9.5 10 L8.5 35 M36 10 L34 35 M30.5 10 L31.5 35" fill="none" stroke="${ink}" stroke-width="1.3"/>
    <rect x="17.5" y="10" width="5" height="2.6" fill="${ink}"/>
    <path d="M20 12.6 V20.5 M18.6 20.5 H21.4" fill="none" stroke="${ink}" stroke-width="1"/>
    <path d="M1.5 35 H38.5" fill="none" stroke="${ink}" stroke-width="1.3"/>`,
  // A record, its label set off-centre like a Bauhaus composition.
  record: (ink) => `
    <circle cx="20" cy="20" r="17" fill="none" stroke="${ink}" stroke-width="1.4"/>
    <circle cx="20" cy="20" r="12.5" fill="none" stroke="${ink}" stroke-width="1" stroke-dasharray="1 2"/>
    <circle cx="23.5" cy="16.5" r="6" fill="${LOGO_RED}"/>
    <circle cx="20" cy="20" r="1.2" fill="${ink}"/>`,
  // A "B" of two semicircles beside an open-circle "G"; one half in red.
  monogram: (ink) => `
    <path d="M4 5 V35" fill="none" stroke="${ink}" stroke-width="1.4"/>
    <path d="M4 5 H8 A7.5 7.5 0 0 1 8 20 H4 Z" fill="none" stroke="${ink}" stroke-width="1.4"/>
    <path d="M4 20 H9 A7.5 7.5 0 0 1 9 35 H4 Z" fill="${LOGO_RED}"/>
    <path d="M36.5 13 A9 9 0 1 0 37 23 H29.5" fill="none" stroke="${ink}" stroke-width="1.4"/>`,
};

function logoMark(key, ink = LOGO_INK) {
  return `<svg class="lg" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">${LOGO_STYLE}${LOGO_MARKS[key](ink)}</svg>`;
}
