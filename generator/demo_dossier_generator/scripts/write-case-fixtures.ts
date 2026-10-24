import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { FIXTURE_DIR, renderFixtures, SCENARIOS } from "./caseFixtures";

rmSync(join(FIXTURE_DIR, "demo_cases"), { recursive: true, force: true });
for (const s of SCENARIOS) rmSync(join(FIXTURE_DIR, "generator", `demo_${s.name}`), { recursive: true, force: true });
const files = renderFixtures();
for (const [path, text] of Object.entries(files)) {
  const full = join(FIXTURE_DIR, path);
  mkdirSync(dirname(full), { recursive: true });
  writeFileSync(full, text);
}
console.log(`wrote ${Object.keys(files).length} files to ${FIXTURE_DIR}`);
