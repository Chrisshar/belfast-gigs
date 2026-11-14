// Cut the picked takes into the seamless hero loop, grade it, and encode the web files.
//   node higgsfield/cut.mjs            reads higgsfield/cut.json, writes public/hero/
// Needs ffmpeg (with libsvtav1, libx264 and libaom) on PATH.
//
// The loop: the shots are joined with short crossfades into one sequence S of length L. The
// last D seconds of S are then crossfaded into S's first D seconds, and the output starts at D,
// so the final frame flows straight into the first one.

import { readFile, mkdir, stat } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..');
const cut = JSON.parse(await readFile(join(HERE, 'cut.json'), 'utf8'));
const OUT = join(ROOT, 'public', 'hero');
const TMP = join(HERE, 'out');
const X = cut.crossfade; // between shots
const D = cut.loopFade; // end back into the start
const V = cut.version;

const ff = (...args) => execFileSync('ffmpeg', ['-v', 'error', '-y', ...args], { stdio: 'inherit' });

// 1. Join the shots: trim each, normalise to 1280x720 at 24 fps, chain xfades.
const inputs = cut.shots.flatMap((s) => ['-ss', String(s.in), '-t', String(s.len), '-i', join(HERE, s.file)]);
const parts = cut.shots.map((_, i) => `[${i}:v]scale=1280:720:flags=lanczos,fps=24,format=yuv420p,setpts=PTS-STARTPTS[s${i}]`);
let chain = '[s0]';
let t = cut.shots[0].len;
const fades = [];
for (let i = 1; i < cut.shots.length; i++) {
  const label = i === cut.shots.length - 1 ? '[seq]' : `[x${i}]`;
  fades.push(`${chain}[s${i}]xfade=transition=fade:duration=${X}:offset=${(t - X).toFixed(3)}${label}`);
  chain = label;
  t += cut.shots[i].len - X;
}
const L = t;
// 2. Loop: A = S[D, L], B = S[0, D]; fade A's tail into B.
const loop = `[seq]split[a][b];[a]trim=${D}:${L},setpts=PTS-STARTPTS[A];[b]trim=0:${D},setpts=PTS-STARTPTS[B];[A][B]xfade=transition=fade:duration=${D}:offset=${(L - 2 * D).toFixed(3)}[lp]`;
// 3. Grade toward the palette: a touch more contrast, cooler shadows, warmer highlights, and a
//    light denoise so the grain doesn't eat the bitrate.
const grade = `[lp]hqdn3d=1.5:1.5:4:4,eq=contrast=1.06:saturation=1.12,colorbalance=bs=.05:rs=-.02:rh=.05:bh=-.04[out]`;
const master = join(TMP, `master-${V}.mp4`);
await mkdir(OUT, { recursive: true });
ff(...inputs, '-filter_complex', [...parts, ...fades, loop, grade].join(';'), '-map', '[out]', '-an', '-c:v', 'libx264', '-crf', '12', '-preset', 'slow', master);
console.log(`Master: ${(L - D).toFixed(2)} s`);

// 4. Web encodes. The phone file is a 4:5 crop, centred where the CSS object-position puts it.
const phoneCrop = `crop=576:720:${Math.round((1280 - 576) * cut.phoneX)}:0`;
const enc = [
  [`night-1280-${V}.webm`, [], ['-c:v', 'libsvtav1', '-crf', String(cut.av1Crf), '-preset', '5', '-g', '96']],
  [`night-1280-${V}.mp4`, [], ['-c:v', 'libx264', '-crf', String(cut.x264Crf), '-preset', 'slow', '-profile:v', 'high', '-movflags', '+faststart']],
  [`night-576x720-${V}.webm`, ['-vf', phoneCrop], ['-c:v', 'libsvtav1', '-crf', String(cut.av1Crf), '-preset', '5', '-g', '96']],
  [`night-576x720-${V}.mp4`, ['-vf', phoneCrop], ['-c:v', 'libx264', '-crf', String(cut.x264Crf), '-preset', 'slow', '-profile:v', 'high', '-movflags', '+faststart']],
];
for (const [name, vf, codec] of enc) ff('-i', master, ...vf, '-an', '-pix_fmt', 'yuv420p', ...codec, join(OUT, name));

// 5. Posters: the loop's first frame, so the swap from poster to video is invisible.
ff('-i', master, '-frames:v', '1', '-q:v', '4', join(OUT, `night-poster-1280-${V}.jpg`));
ff('-i', master, '-frames:v', '1', '-c:v', 'libaom-av1', '-still-picture', '1', '-crf', '24', join(OUT, `night-poster-1280-${V}.avif`));
ff('-i', master, '-frames:v', '1', '-vf', phoneCrop, '-q:v', '4', join(OUT, `night-poster-576x720-${V}.jpg`));
ff('-i', master, '-frames:v', '1', '-vf', phoneCrop, '-c:v', 'libaom-av1', '-still-picture', '1', '-crf', '24', join(OUT, `night-poster-576x720-${V}.avif`));

for (const name of [...enc.map((e) => e[0]), `night-poster-1280-${V}.jpg`, `night-poster-1280-${V}.avif`, `night-poster-576x720-${V}.jpg`, `night-poster-576x720-${V}.avif`]) {
  console.log(`${name.padEnd(34)} ${((await stat(join(OUT, name))).size / 1024).toFixed(0)} KB`);
}
