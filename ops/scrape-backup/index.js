// Backup trigger for the Scrape workflow. GitHub's own schedule (06:17 and 17:17 UTC) is
// best-effort and sometimes skips runs, so this Worker checks about 50 minutes after each slot
// and starts a run if none has started recently. A run that overlaps is harmless: the workflow's
// concurrency group queues it, and a run with nothing new to write commits nothing.
//
// Needs the secret GITHUB_TOKEN: a fine-grained token for this repo only, with
// "Actions: Read and write" (wrangler secret put GITHUB_TOKEN).

const RECENT_MINUTES = 150; // a run that started this recently counts as this slot's run

async function github(env, path, init = {}) {
  const res = await fetch(`https://api.github.com/repos/${env.REPO}${path}`, {
    ...init,
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      'User-Agent': 'belfast-gigs-scrape-backup',
      'X-GitHub-Api-Version': '2022-11-28',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
    },
  });
  if (!res.ok) throw new Error(`GitHub ${init.method ?? 'GET'} ${path}: ${res.status} ${await res.text()}`);
  return res.status === 204 ? null : res.json();
}

export async function check(env, now = Date.now()) {
  const { workflow_runs: runs } = await github(env, `/actions/workflows/${env.WORKFLOW}/runs?per_page=5`);
  const recent = runs.find((r) => now - Date.parse(r.created_at) < RECENT_MINUTES * 60_000);
  if (recent) return `ok: run ${recent.id} (${recent.event}) started ${recent.created_at}`;
  await github(env, `/actions/workflows/${env.WORKFLOW}/dispatches`, {
    method: 'POST',
    body: JSON.stringify({ ref: env.BRANCH }),
  });
  return 'no recent run: started one';
}

export default {
  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(check(env).then((msg) => console.log(msg)));
  },
  // Nothing to see over HTTP; the Worker only runs on its timer.
  async fetch() {
    return new Response('Not found', { status: 404 });
  },
};
