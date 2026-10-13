/**
 * Small CLI runner shared by the ombucore and website asset builds.
 *
 *   runBuild({ name, groups, watchTargets })
 *
 * Command line: `[group ...] [--watch]`. With no group names every group is
 * built. In watch mode, a change under a watch target's `dir` (matching its
 * `ext`, and not one of its `ignore` basenames) rebuilds that target's group.
 */
import { watch } from 'node:fs';
import path from 'node:path';

export async function runBuild({ name, groups, watchTargets = [], argv = process.argv.slice(2) }) {
  const isWatch = argv.includes('--watch');
  const requested = argv.filter((a) => !a.startsWith('--'));
  const unknown = requested.filter((group) => !groups[group]);
  if (unknown.length) {
    console.error(`[${name}] Unknown group(s): ${unknown.join(', ')}. Expected: ${Object.keys(groups).join(', ')}`);
    process.exit(1);
  }
  const selected = requested.length ? requested : Object.keys(groups);

  async function run(group) {
    const started = performance.now();
    try {
      await groups[group]();
      console.log(`✓ ${name}:${group} (${Math.round(performance.now() - started)} ms)`);
      return true;
    } catch (error) {
      console.error(`✗ ${name}:${group}\n${error.formatted ?? error.message ?? error}`);
      return false;
    }
  }

  const results = await Promise.all(selected.map(run));
  if (!isWatch) {
    process.exit(results.every(Boolean) ? 0 : 1);
  }

  const pending = new Map();
  for (const { dir, ext = '', group, ignore = [] } of watchTargets) {
    if (!selected.includes(group)) continue;
    watch(dir, { recursive: true }, (_event, filename) => {
      if (!filename || !filename.endsWith(ext) || ignore.includes(path.basename(filename))) return;
      clearTimeout(pending.get(group));
      pending.set(group, setTimeout(() => run(group), 100));
    });
  }
  console.log(`[${name}] Watching for changes…`);
}
