import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const out = path.join(root, "dist/octodesk-r1");
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const failed = [];
  page.on("requestfailed", (r) => failed.push(r.url()));
  await page.goto(pathToFileURL(path.join(out, "docs/assembly-manual.html")).href, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  const images = await page.locator("img").evaluateAll((items) => items.map((img) => ({ src: img.getAttribute("src"), loaded: img.complete && img.naturalWidth > 0 })));
  if (images.some((x) => !x.loaded) || errors.length || failed.length) throw new Error(JSON.stringify({ images, errors, failed }));
  const oversized = await page.locator(".page").evaluateAll((items) => items.map((p, i) => ({ page: i + 1, height: p.scrollHeight })).filter((p) => p.height > 1000));
  if (oversized.length) throw new Error(`Manual page overflow: ${JSON.stringify(oversized)}`);
  await page.pdf({ path: path.join(out, "docs/assembly-manual.pdf"), printBackground: true, preferCSSPageSize: true });
  await fs.writeFile(path.join(out, "validation/pdf-generation.json"), JSON.stringify({
    status: "PASS", engine: "Chromium print-to-PDF", logical_pages: await page.locator(".page").count(),
    source_images: images.length, images_loaded: true, overflow_pages: oversized,
    fonts_ready: true, errors, failed
  }, null, 2));
  console.log("PDF_EXPORTED", await page.locator(".page").count(), "logical pages");
} finally { await browser.close(); }
