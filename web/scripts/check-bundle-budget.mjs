// First-load JavaScript, per route, against a ceiling.
//
// The target device is a low-end Android on mobile data, and nothing measured
// this: the heaviest route reached 638 KB of uncompressed JS without anyone
// deciding it should. This is a ceiling to stop silent growth, not a target --
// getting *down* is separate work. Reads the stats `next build` already writes.
import { readFileSync } from "node:fs";

const BUDGET = Number(process.env.FIRST_LOAD_JS_BUDGET ?? 700_000);
const stats = JSON.parse(
  readFileSync(".next/diagnostics/route-bundle-stats.json", "utf8"),
);

const kb = (bytes) => `${Math.round(bytes / 1024)} KB`;
const heaviest = [...stats].sort(
  (a, b) => b.firstLoadUncompressedJsBytes - a.firstLoadUncompressedJsBytes,
);
console.log(`First-load JS budget: ${kb(BUDGET)} per route`);
for (const route of heaviest.slice(0, 5)) {
  console.log(`  ${kb(route.firstLoadUncompressedJsBytes).padStart(7)}  ${route.route}`);
}

const over = heaviest.filter((r) => r.firstLoadUncompressedJsBytes > BUDGET);
if (over.length > 0) {
  console.error(`\n${over.length} route(s) over budget:`);
  for (const r of over) console.error(`  ${r.route}: ${kb(r.firstLoadUncompressedJsBytes)}`);
  process.exit(1);
}
