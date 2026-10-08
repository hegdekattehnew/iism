import { execFileSync } from "node:child_process";
import path from "node:path";

import { E2E } from "../playwright.config";

/**
 * Start every run with no vacancies or courses left over from the last one.
 *
 * The journeys register their own people and write their own listings, so nothing else needs
 * resetting -- but `/matches` shows a top twenty, and the identical vacancies earlier runs leave
 * behind all tie on score, so a fresh one can fall off the page. That reads as a flaky test and
 * is really a dirty database. (CI starts from an empty one; this is for a laptop.)
 */
export default function globalSetup(): void {
  const repo = path.resolve(__dirname, "..", "..");
  const out = execFileSync(path.join(repo, ".venv", "bin", "python"), ["scripts/seed_e2e.py", "--clear-listings"], {
    cwd: repo,
    env: { ...process.env, DATABASE_URL: E2E.database, REDIS_URL: E2E.redis, ENVIRONMENT: "test" },
  });
  console.log(out.toString().trim());
}
