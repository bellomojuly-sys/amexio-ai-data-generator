/**
 * Command-line generation, without the browser:
 *
 *   npm run example                  AMEXIO's example package  -> out/mock-import-dossier/
 *   npm run example -- --offline 40  40 employees, "No AI" mode -> out/hr-dossier-import/
 *
 * Same TypeScript modules as the web app. This is the route to the large
 * volumes AMEXIO mentioned (100 dossiers x thousands of documents).
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { examplePreset } from "../src/generate/examplePreset";
import { expandDossiers } from "../src/generate/expand";
import { buildPackageFiles } from "../src/export/package";
import { generateOffline } from "../src/generate/offline";
import { DEFAULT_CONFIG, cloneConfig } from "../src/generate/config";
import { validate } from "../src/validate/validate";

const args = process.argv.slice(2);
const offlineIndex = args.indexOf("--offline");
let set;
if (offlineIndex >= 0) {
  const config = cloneConfig(DEFAULT_CONFIG);
  config.employeeCount = Number(args[offlineIndex + 1] ?? 10);
  const yearsIndex = args.indexOf("--years");
  if (yearsIndex >= 0) config.historyYears = Number(args[yearsIndex + 1]);
  const seedIndex = args.indexOf("--seed");
  if (seedIndex >= 0) config.seed = Number(args[seedIndex + 1]);
  set = generateOffline(config);
} else {
  set = examplePreset();
}

const pkg = expandDossiers(set);
const report = validate(set, pkg);
console.log(`${pkg.folders.length} folders, ${pkg.documents.length} documents`);
console.log(`Validation: ${report.errors} errors, ${report.warnings} warnings`);
for (const issue of report.issues.filter((i) => i.severity === "error").slice(0, 20)) console.log(`  ERROR ${issue.code}: ${issue.message}`);
if (report.errors > 0) {
  console.error("Export blocked: fix the errors first.");
  process.exit(1);
}
const files = await buildPackageFiles(set, pkg);
const outDir = join(process.cwd(), "out");
for (const [path, data] of Object.entries(files)) {
  const full = join(outDir, path);
  mkdirSync(dirname(full), { recursive: true });
  writeFileSync(full, data);
}
console.log(`Written to ${join(outDir, set.config.target.packageName)}`);
