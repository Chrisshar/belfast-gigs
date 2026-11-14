// Hero film generator: keyframe stills and shot clips from higgsfield/shots.json, through the
// official Higgsfield SDK. Server-side only: never import this from Astro pages or client code.
//
//   npm run seedance -- --still <shot>          4 keyframe options for a shot (Soul Cinema)
//   npm run seedance -- <shot> [--takes N]      animate higgsfield/keyframes/<shot>.(jpg|png|webp)
//                      [--draft]                cheapest settings (480p, 4 s) for a look test
//                      [--end <shot>]           use another shot's keyframe as the last frame
//   add --dry to any command to print the request and its cost without running it
//
// Reads HF_CREDENTIALS ("key-id:key-secret") from .env.local at runtime (Node's --env-file).
// Everything lands in higgsfield/out/<shot>/ (gitignored) with a .json sidecar per request.
// Higgsfield deletes request files after 7 days, so results are downloaded straight away.

import { readFile, writeFile, mkdir, readdir } from "node:fs/promises";
import { join, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { config, higgsfield, TimeoutError } from "@higgsfield/client/v2";
import type { V2Response } from "@higgsfield/client/v2";

const HERE = dirname(fileURLToPath(import.meta.url));
const API = "https://api.higgsfield.ai";

interface Shot { id: string; scene: string; motion: string }
interface Spec {
  style: string;
  still: Record<string, unknown> & { endpoint: string; batch_size: number };
  video: {
    endpoint: string; resolution: string; duration: number; generate_audio: boolean;
    draft: { resolution: string; duration: number };
    usd_per_second: Record<string, number>;
  };
  shots: Shot[];
}

const { values: opts, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    still: { type: "string" },
    takes: { type: "string", default: "1" },
    draft: { type: "boolean", default: false },
    end: { type: "string" },
    dry: { type: "boolean", default: false },
  },
});

const spec: Spec = JSON.parse(await readFile(join(HERE, "shots.json"), "utf8"));
const shotId = opts.still ?? positionals[0];
const shot = spec.shots.find((s) => s.id === shotId);
if (!shot) {
  console.error(`Unknown or missing shot. Choose one of: ${spec.shots.map((s) => s.id).join(", ")}`);
  process.exit(1);
}
const takes = Math.max(1, Number.parseInt(opts.takes, 10) || 1);
const stamp = () => new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const outDir = join(HERE, "out", shot.id);

if (!opts.dry && !process.env.HF_CREDENTIALS) {
  console.error("HF_CREDENTIALS is not set. Add it to .env.local as key-id:key-secret.");
  process.exit(1);
}
config({
  credentials: process.env.HF_CREDENTIALS ?? "dry:run",
  pollInterval: 5_000,
  // The SDK only stops polling on completed / failed / nsfw, so a canceled request would
  // otherwise poll forever. Cap the wait.
  maxPollTime: 15 * 60_000,
});

/** Find the approved keyframe for a shot. */
async function keyframe(id: string): Promise<string> {
  const dir = join(HERE, "keyframes");
  const file = (await readdir(dir).catch(() => [] as string[])).find((f) => f.replace(extname(f), "") === id);
  if (!file) throw new Error(`No keyframe for ${id}: save the chosen still as higgsfield/keyframes/${id}.jpg (or .png/.webp).`);
  return join(dir, file);
}

/** Upload a local image through a presigned URL and return its public URL. Credentials go to
 * Higgsfield's API only, never to the storage URL. */
async function upload(path: string): Promise<string> {
  const ext = extname(path).slice(1).toLowerCase();
  const contentType = `image/${ext === "jpg" ? "jpeg" : ext}`;
  const res = await fetch(`${API}/files/generate-upload-url`, {
    method: "POST",
    headers: { Authorization: `Key ${process.env.HF_CREDENTIALS}`, "Content-Type": "application/json" },
    body: JSON.stringify({ content_type: contentType }),
  });
  if (!res.ok) throw new Error(`Upload URL request failed: HTTP ${res.status}`);
  const { public_url, upload_url, upload_headers } = (await res.json()) as { public_url: string; upload_url: string; upload_headers?: Record<string, string> };
  const put = await fetch(upload_url, { method: "PUT", headers: upload_headers ?? { "Content-Type": contentType }, body: await readFile(path) });
  if (!put.ok) throw new Error(`Upload failed: HTTP ${put.status}`);
  return public_url;
}

async function download(url: string, base: string, fallbackExt: string): Promise<string> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Download failed: HTTP ${res.status}`);
  const ext = extname(new URL(url).pathname) || fallbackExt;
  const file = `${base}${ext}`;
  await writeFile(file, Buffer.from(await res.arrayBuffer()));
  return file;
}

async function run(endpoint: string, input: Record<string, unknown>): Promise<V2Response | null> {
  try {
    const result = await higgsfield.subscribe(endpoint, { input, withPolling: true });
    const status: string = result.status; // the API can also say "canceled", which the SDK's type omits
    if (status === "completed") return result;
    console.error(`Request ${result.request_id} ended "${status}"${status === "nsfw" ? " (blocked by moderation)" : ""}. Not charged.`);
  } catch (err) {
    if (err instanceof TimeoutError) console.error("Gave up waiting: the request did not finish (it may have been canceled).");
    // Print the message only: never dump the error object, which can carry request headers.
    else console.error(`Request failed: ${err instanceof Error ? `${err.name}: ${err.message}` : String(err)}`);
  }
  return null;
}

await mkdir(outDir, { recursive: true });

if (opts.still) {
  const { endpoint, ...settings } = spec.still;
  const input: Record<string, unknown> = { ...settings, prompt: `${shot.scene} ${spec.style}` };
  console.log(`Still ${shot.id} × ${takes} (${spec.still.batch_size} images each, about $0.02 per request)`);
  if (opts.dry) { console.log(endpoint, JSON.stringify(input, null, 2)); process.exit(0); }
  for (let t = 0; t < takes; t++) {
    // A different seed per take, so extra takes give new options instead of the same four.
    const seeded = { ...input, seed: (input.seed as number) + t };
    const result = await run(endpoint, seeded);
    if (!result?.images?.length) continue;
    // Request ids are time-ordered UUIDs, so the tail is the distinctive part.
    const base = join(outDir, `still-${stamp()}-${result.request_id.slice(-8)}`);
    const files = await Promise.all(result.images.map((img, i) => download(img.url, `${base}-${i + 1}`, ".png")));
    await writeFile(`${base}.json`, JSON.stringify({ endpoint, input: seeded, request_id: result.request_id, files }, null, 2));
    for (const f of files) console.log(`Saved ${f}`);
  }
} else {
  const v = spec.video;
  const resolution = opts.draft ? v.draft.resolution : v.resolution;
  const duration = opts.draft ? v.draft.duration : v.duration;
  const cost = v.usd_per_second[resolution] * duration * takes;
  let image: string, end: string | null;
  try {
    image = await keyframe(shot.id);
    end = opts.end ? await keyframe(opts.end) : null;
  } catch (err) {
    console.error((err as Error).message);
    process.exit(1);
  }
  const input: Record<string, unknown> = { prompt: `${shot.motion} ${spec.style}`, resolution, duration, generate_audio: v.generate_audio };
  console.log(`Clip ${shot.id} × ${takes} at ${resolution}, ${duration} s: about $${cost.toFixed(2)}`);
  if (opts.dry) { console.log(v.endpoint, JSON.stringify({ ...input, image_url: image, end_image_url: end ?? undefined }, null, 2)); process.exit(0); }
  input.image_url = await upload(image);
  if (end) input.end_image_url = await upload(end);
  for (let t = 0; t < takes; t++) {
    const result = await run(v.endpoint, input);
    if (!result?.video?.url) continue;
    const base = join(outDir, `${opts.draft ? "draft" : "clip"}-${stamp()}-${result.request_id.slice(-8)}`);
    const file = await download(result.video.url, base, ".mp4");
    await writeFile(`${base}.json`, JSON.stringify({ endpoint: v.endpoint, input, request_id: result.request_id, file }, null, 2));
    console.log(`Saved ${file}`);
  }
}
