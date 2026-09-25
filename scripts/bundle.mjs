import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const out = path.join(root, "dist/octodesk-r1");
const read = async (file) => JSON.parse(await fs.readFile(path.join(out, file), "utf8"));
const kit = await read("data/kit.json");
const catalog = await read("data/catalog.json");
const manifest = await read("data/print-manifest.json");
const translations = JSON.parse(await fs.readFile(path.join(root, "design/translations.json"), "utf8"));
const captions = await read("media/assembly-caption-data.json");
for (const step of kit.steps) {
  if (!translations.en.steps[step.number]) throw new Error(`Missing English step ${step.number}`);
}
for (const instance of kit.instances) {
  if (!translations.en.roles[instance.role]) throw new Error(`Missing English role for ${instance.id}`);
}
const meshes = {};
for (const pid of new Set(kit.instances.map((i) => i.part))) {
  meshes[pid] = (await fs.readFile(path.join(out, catalog.parts[pid].stl))).toString("base64");
}
await fs.mkdir(path.join(out, "assets"), { recursive: true });
await fs.mkdir(path.join(out, "licenses"), { recursive: true });
await fs.writeFile(path.join(out, "assets/data.js"), `window.OCTODESK_DATA=${JSON.stringify({ kit, catalog, manifest, meshes, translations, captions })};\n`);
await fs.copyFile(path.join(root, "design/translations.json"), path.join(out, "data/translations.json"));
await fs.copyFile(path.join(root, "web/index.html"), path.join(out, "index.html"));
await fs.copyFile(path.join(root, "web/style.css"), path.join(out, "assets/style.css"));
await fs.copyFile(path.join(root, "node_modules/three/LICENSE"), path.join(out, "licenses/THREE-LICENSE.txt"));
await build({
  entryPoints: [path.join(root, "web/guide.js")], outfile: path.join(out, "assets/guide.js"),
  bundle: true, format: "iife", platform: "browser", target: "es2020",
  minify: true, legalComments: "eof"
});
console.log(`OFFLINE_VIEWER_BUILT ${kit.instances.length} instances / ${Object.keys(meshes).length} embedded STL geometries`);
