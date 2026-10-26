// Turns the single-file Vite build (dist-artifact/index.html) into the page
// fragment the Claude artifact host expects: no <html>/<head>/<body> of its own,
// <title> and <style> first, then the app root and the inlined module script.
import { readFileSync, writeFileSync } from "node:fs";

const src = readFileSync("dist-artifact/index.html", "utf8");

const title = /<title>[\s\S]*?<\/title>/.exec(src)?.[0];
const links = src.match(/<link[\s\S]*?\/?>/g) ?? [];
const style = /<style[^>]*>([\s\S]*?)<\/style>/.exec(src)?.[1];
const scriptStart = src.indexOf('<script type="module"');
const scriptOpenEnd = src.indexOf(">", scriptStart) + 1;
const scriptEnd = src.lastIndexOf("</script>");
if (!title || style === undefined || scriptStart < 0 || scriptEnd < scriptOpenEnd) {
  throw new Error("Unexpected build output: could not find title, style or script.");
}
// pdf-lib's encoding tables contain U+FFFD inside string literals; write it as an
// escape so the published page holds no replacement characters.
const script = src.slice(scriptOpenEnd, scriptEnd).replace(/\uFFFD/g, "\\uFFFD");
if (/(?:sk-ant-|sk-proj-)[A-Za-z0-9_-]{8,}/.test(script)) {
  throw new Error("The bundle looks like it contains an API key. Refusing to write the artifact.");
}

const page = [
  title,
  '<meta name="claude:viewport-fit-sides" content="cover">',
  ...links.map((l) => l.replace(/\s+/g, " ").replace(" />", ">")),
  `<style>${style}</style>`,
  '<div id="root"></div>',
  `<script type="module">${script}</script>`,
  "",
].join("\n");

writeFileSync("dist-artifact/dossier-generator.html", page);
console.log(`dist-artifact/dossier-generator.html: ${(page.length / 1024).toFixed(0)} KB`);
