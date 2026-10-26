// The mark: Samson and Goliath, the Harland & Wolff gantry cranes, with a red sun setting between
// the legs. Drawn on a 40x40 grid in hairlines to match the instrument drawings.

const RED = '#c8452f';

export function craneMark(ink = 'currentColor'): string {
  return `<svg class="mark-svg" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">
    <path d="M12.5 35 A7.5 7.5 0 0 1 27.5 35 Z" fill="${RED}"/>
    <path d="M1.5 6.5 H38.5 V10 H1.5 Z M4 10 L6 35 M9.5 10 L8.5 35 M36 10 L34 35 M30.5 10 L31.5 35 M1.5 35 H38.5" fill="none" stroke="${ink}" stroke-width="1.3"/>
    <rect x="17.5" y="10" width="5" height="2.6" fill="${ink}"/>
    <path d="M20 12.6 V20.5 M18.6 20.5 H21.4" fill="none" stroke="${ink}" stroke-width="1"/>
  </svg>`;
}
