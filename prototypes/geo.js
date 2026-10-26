// Generated Bauhaus tiles: a small geometric poster per gig, deterministic from its id.
// tile(seedString, { palette, cols, rows, size, genres, ratio }) -> "<svg ...>"

function hash(str) {
  let h = 2166136261 >>> 0;
  for (const c of str) {
    h ^= c.charCodeAt(0);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function rng(seed) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Which shapes each genre leans towards. Unlisted genres use everything.
const MOTIFS_BY_GENRE = {
  "Jazz/Blues": ["circle", "ring", "dot", "half", "vinyl"],
  "Soul/R&B/Funk": ["circle", "half", "ring", "vinyl"],
  "Folk/Trad": ["quarter", "half", "dot", "arch"],
  "Country/Americana": ["quarter", "arch", "half", "bars"],
  "Singer-Songwriter": ["half", "circle", "arch", "dot"],
  "Rock": ["bars", "diag", "half", "circle"],
  "Punk/Hardcore": ["diag", "bars", "quarter"],
  "Metal": ["diag", "bars", "quarter"],
  "Indie/Alternative": ["half", "bars", "circle", "diag"],
  "Electronic": ["bars", "dot", "ring", "diag"],
  "Pop": ["circle", "dot", "half", "quarter"],
  "Hip-Hop/Rap": ["bars", "quarter", "circle"],
  "Tribute/Covers": ["vinyl", "ring", "half"],
  "World": ["arch", "half", "dot", "quarter"],
  "Contemporary/New Music": ["ring", "dot", "arch"],
};
const ALL_MOTIFS = ["circle", "half", "quarter", "bars", "diag", "ring", "dot", "arch", "vinyl"];

function motifSet(genres) {
  const set = new Set();
  for (const g of genres || []) (MOTIFS_BY_GENRE[g] || []).forEach((m) => set.add(m));
  return set.size ? [...set] : ALL_MOTIFS;
}

function cell(m, x, y, w, h, fg, bg, r) {
  const cx = x + w / 2, cy = y + h / 2, s = Math.min(w, h);
  const rot = Math.floor(r() * 4) * 90;
  const tr = `transform="rotate(${rot} ${cx} ${cy})"`;
  switch (m) {
    case "circle":
      return `<circle cx="${cx}" cy="${cy}" r="${s * 0.4}" fill="${fg}"/>`;
    case "dot":
      return `<circle cx="${cx}" cy="${cy}" r="${s * 0.16}" fill="${fg}"/>`;
    case "ring":
      return `<circle cx="${cx}" cy="${cy}" r="${s * 0.4}" fill="${fg}"/><circle cx="${cx}" cy="${cy}" r="${s * 0.14}" fill="${bg}"/>`;
    case "half":
      return `<path ${tr} d="M${x} ${cy} A${w / 2} ${w / 2} 0 0 1 ${x + w} ${cy} Z" fill="${fg}"/>`;
    case "arch":
      return `<path ${tr} d="M${x + w * 0.15} ${y + h} V${cy} A${w * 0.35} ${w * 0.35} 0 0 1 ${x + w * 0.85} ${cy} V${y + h} Z" fill="${fg}"/>`;
    case "quarter":
      return `<path ${tr} d="M${x} ${y} H${x + w} A${w} ${h} 0 0 1 ${x} ${y + h} Z" fill="${fg}"/>`;
    case "diag":
      return `<path ${tr} d="M${x} ${y} H${x + w} L${x} ${y + h} Z" fill="${fg}"/>`;
    case "bars": {
      const n = 3 + Math.floor(r() * 2), bw = w / (n * 2 - 1);
      const vertical = r() < 0.5;
      return Array.from({ length: n }, (_, i) =>
        vertical ? `<rect x="${x + i * 2 * bw}" y="${y}" width="${bw}" height="${h}" fill="${fg}"/>` : `<rect x="${x}" y="${y + i * 2 * (h / (n * 2 - 1))}" width="${w}" height="${h / (n * 2 - 1)}" fill="${fg}"/>`,
      ).join("");
    }
    case "vinyl": {
      // A record seen from its edge, like a sleeve corner: concentric arcs from one corner.
      const ox = r() < 0.5 ? x : x + w, oy = r() < 0.5 ? y : y + h;
      let out = `<clipPath id="c${Math.floor(r() * 1e9)}"><rect x="${x}" y="${y}" width="${w}" height="${h}"/></clipPath>`;
      const id = out.match(/id="(c\d+)"/)[1];
      out += `<g clip-path="url(#${id})"><circle cx="${ox}" cy="${oy}" r="${s * 0.95}" fill="${fg}"/>`;
      for (let k = 0.38; k < 0.95; k += 0.14) out += `<circle cx="${ox}" cy="${oy}" r="${s * k}" fill="none" stroke="${bg}" stroke-width="${s * 0.025}"/>`;
      out += `<circle cx="${ox}" cy="${oy}" r="${s * 0.22}" fill="${bg}"/></g>`;
      return out;
    }
  }
  return "";
}

function tile(seed, { palette, cols = 2, rows = 2, size = 240, genres = [], ratio = 1, gap = 0 } = {}) {
  const r = rng(hash(seed));
  const W = size, H = size * ratio;
  const w = (W - gap * (cols - 1)) / cols, h = (H - gap * (rows - 1)) / rows;
  const motifs = motifSet(genres);
  let body = "";
  for (let j = 0; j < rows; j++) {
    for (let i = 0; i < cols; i++) {
      const bg = palette[Math.floor(r() * palette.length)];
      let fg = palette[Math.floor(r() * palette.length)];
      if (fg === bg) fg = palette[(palette.indexOf(bg) + 1 + Math.floor(r() * (palette.length - 1))) % palette.length];
      const x = i * (w + gap), y = j * (h + gap);
      body += `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${bg}"/>` + cell(motifs[Math.floor(r() * motifs.length)], x, y, w, h, fg, bg, r);
    }
  }
  return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false" preserveAspectRatio="xMidYMid slice">${body}</svg>`;
}
