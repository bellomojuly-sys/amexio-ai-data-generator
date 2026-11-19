// Bundles v1's export for the v2 page: site/v1_export.js (see v1_export/entry.ts).
//
// v1's files (generator/demo_dossier_generator/src) are bundled as they are,
// with their dependencies (pdf-lib, fflate) from v1's node_modules, into one
// script that sets the global V1Export. The output is generated, so git
// ignores it.
//
//   cd generator/demo_dossier_generator && npm ci     # once: v1's packages, esbuild included
//   node generator/Second_demo_generator/build_v1_export.mjs [NODE_MODULES]
//
// NODE_MODULES: another node_modules folder with esbuild, pdf-lib and fflate
// (default: v1's).
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const v1 = resolve(here, "..", "demo_dossier_generator");
const nodeModules = resolve(process.argv[2] ?? join(v1, "node_modules"));
const esbuild = createRequire(join(nodeModules, "noop.js"))("esbuild");

const result = await esbuild.build({
  entryPoints: [join(here, "v1_export", "entry.ts")],
  outfile: join(here, "site", "v1_export.js"),
  bundle: true,
  format: "iife",
  globalName: "V1Export",
  platform: "browser",
  target: "es2020",
  minify: true,
  nodePaths: [nodeModules],
  legalComments: "eof",
  banner: { js: "/* v1's export (generator/demo_dossier_generator, unchanged), bundled by build_v1_export.mjs for the v2 demo. */" },
  metafile: true,
  logLevel: "warning",
});
const inputs = Object.keys(result.metafile.inputs);
const fromV1 = inputs.filter((p) => p.includes("demo_dossier_generator/src")).length;
const size = Object.values(result.metafile.outputs)[0].bytes;
console.log(`wrote generator/Second_demo_generator/site/v1_export.js (${Math.round(size / 1024)} KB; ${fromV1} of v1's files, ${inputs.length} in all)`);
