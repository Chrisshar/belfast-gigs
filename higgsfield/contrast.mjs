// Contrast check for the hero copy over the video: samples every 10th frame of the master, applies
// the same scrim as the CSS (src/styles hero section), and reports white text's worst contrast in
// the area the copy covers. Targets: 4.5:1 for the lede and buttons, 3:1 for the large headline.
//   node higgsfield/contrast.mjs [master.mp4]
// Layouts are approximated at 1440x700 (desktop band) and 375x680 (phone band), video object-fit:
// cover. Frames are scaled down 2x first, which averages 2x2 pixels: fine for a backdrop check.

import { execFileSync } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const src = process.argv[2] ?? join(HERE, 'out', 'master-v1.mp4');
const W = 640, H = 360;
const raw = execFileSync('ffmpeg', ['-v', 'error', '-i', src, '-vf', `select='not(mod(n\\,10))',scale=${W}:${H}`, '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], { maxBuffer: 1 << 30 });
const frames = raw.length / (W * H * 3);

const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
const LUT = Float64Array.from({ length: 256 }, (_, i) => lin(i));
const SCRIM = [12, 14, 20];
const lerp = (stops, p) => { // stops: [[pos, alpha], ...] sorted
  if (p <= stops[0][0]) return stops[0][1];
  for (let i = 1; i < stops.length; i++) if (p <= stops[i][0]) { const [a, x] = stops[i - 1], [b, y] = stops[i]; return x + (y - x) * (p - a) / (b - a); }
  return stops.at(-1)[1];
};

/** Worst contrast in a text box. view: band size; box: [x0,y0,x1,y1] in band px; crop: video x offset share. */
function check(name, view, box, scrim, cropX = 0.5) {
  const scale = Math.max(view.w / W, view.h / H);
  const offX = (W * scale - view.w) * cropX, offY = (W * 0 + H * scale - view.h) / 2;
  let worst = Infinity, worstFrame = 0;
  for (let f = 0; f < frames; f++) {
    const base = f * W * H * 3;
    for (let y = box[1]; y < box[3]; y += 2) for (let x = box[0]; x < box[2]; x += 2) {
      const vx = Math.min(W - 1, Math.floor((x + offX) / scale)), vy = Math.min(H - 1, Math.floor((y + offY) / scale));
      const i = base + (vy * W + vx) * 3;
      const a = scrim(x / view.w, y / view.h);
      const ch = [0, 1, 2].map((k) => raw[i + k] * (1 - a) + SCRIM[k] * a);
      const L = 0.2126 * LUT[Math.round(ch[0])] + 0.7152 * LUT[Math.round(ch[1])] + 0.0722 * LUT[Math.round(ch[2])];
      const c = 1.05 / (L + 0.05);
      if (c < worst) { worst = c; worstFrame = f * 10; }
    }
  }
  return { name, worst: +worst.toFixed(2), frame: worstFrame };
}

// Desktop: horizontal scrim + bottom scrim, composited (1 - (1-a)(1-b)).
const desk = (px, py) => {
  const a = lerp([[0, .80], [.45, .55], [.78, .10], [1, 0]], px);
  const b = lerp([[0, 0], [.55, 0], [1, .65]], py); // 0deg gradient: .65 at bottom, clear by 45% up
  return 1 - (1 - a) * (1 - b);
};
const phone = (_px, py) => lerp([[0, .15], [.5, .55], [1, .85]], py);

const results = [
  // Desktop band 1440x700. Copy column x 16..790; headline ~ y 260..520, lede/buttons ~ y 530..680.
  check('desktop headline (3:1)', { w: 1440, h: 700 }, [16, 260, 790, 520], desk),
  check('desktop lede + buttons (4.5:1)', { w: 1440, h: 700 }, [16, 520, 700, 690], desk),
  // Phone band 375x680, crop centred at 70%. Headline ~ y 330..480, lede/buttons ~ y 480..650.
  check('phone headline (3:1)', { w: 375, h: 680 }, [16, 330, 360, 480], phone, 0.7),
  check('phone lede + buttons (4.5:1)', { w: 375, h: 680 }, [16, 480, 360, 650], phone, 0.7),
];
console.log(`${frames} frames sampled`);
for (const r of results) {
  const target = r.name.includes('3:1') ? 3 : 4.5;
  console.log(`${r.worst >= target ? 'PASS' : 'FAIL'}  ${r.name.padEnd(32)} worst ${r.worst}:1 (frame ${r.frame})`);
}
