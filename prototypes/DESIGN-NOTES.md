# Design reference

**Approved (26 Oct 2026):** `2-index.html`, with `instruments.js` (line-art genre drawings; see `instruments.html`)
and the "cranes" mark from `logo.js` (all options are in `logos.html`). This is the reference for building the real site.
`1-print-shop.html` and `3-gallery.html` are alternatives that weren't chosen, and `geo.js` belongs to them.

To view: run the "prototypes" launch configuration (`python -m http.server 4400 --directory prototypes`) and open
http://localhost:4400/2-index.html. The pages need a server, because they load their scripts by relative path.

# Design principles (round 2)

From the references: Eventbrite (structure), Dawid Ryski's gig posters, and the Retrodrome
retro gig prints on Etsy. Round 1 was rejected as generic "AI gig site" design.

## What the references share
- **Light paper, not dark screens.** Off-white sheets (Retrodrome ~#f2eee3, Eventbrite linen #f8f7fa, Ryski cream mounts).
- **Restraint.** Two to four flat colours per piece. No gradients, glows, neon, tape, tilted cards, grain overload.
- **Geometry carries the expression.** Circles, half and quarter circles, bars, diagonals, a vinyl arc. One idea per piece.
- **Type is small and confident.** The act name is not shouting: a modest serif title (Retrodrome), or compact
  letter-spaced caps (Ryski). Details live on one quiet line: `Sat 31 Oct / Limelight 1 / 19:00 / £18`.
- **Hairlines and space instead of boxes and shadows.** Double rules, 1px borders, generous margins (Eventbrite: no shadows).
- **A grid.** Eventbrite's 4/2/1-column card grid; Bauhaus modular cells.

## The device all three directions share
We have no artwork for gigs (and shouldn't hotlink it). So each gig gets a **generated Bauhaus tile**:
a small poster made of geometric cells, built deterministically from the gig's id, so it never changes
between builds and no two neighbouring gigs look alike. The genre picks the motif family and palette
emphasis, so jazz, folk and metal feel different at a glance.

## Avoid (round 1 mistakes)
All-caps everywhere, display type at 6rem, dark backgrounds by default, fake print effects, rotated
elements, emoji, more than one accent "voice", decorative stars and tape.
