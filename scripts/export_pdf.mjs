import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const out = path.join(root, "dist/octodesk-r1");
const publication = JSON.parse(await fs.readFile(path.join(root, "design/publication.json"), "utf8"));
const browser = await chromium.launch({ headless: true });
try {
  for (const language of ["ja", "en"]) {
    const suffix = language === "ja" ? "" : ".en";
    const page = await browser.newPage();
    const errors = [], failed = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("requestfailed", (r) => failed.push(r.url()));
    await page.goto(pathToFileURL(path.join(out, `docs/assembly-manual${suffix}.html`)).href, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    const images = await page.locator("img").evaluateAll((items) => items.map((img) => ({ src: img.getAttribute("src"), loaded: img.complete && img.naturalWidth > 0 })));
    if (images.some((x) => !x.loaded) || errors.length || failed.length) throw new Error(JSON.stringify({ language, images, errors, failed }));
    const oversized = await page.locator(".page").evaluateAll((items) => items.map((p, i) => ({ page: i + 1, height: p.scrollHeight })).filter((p) => p.height > 1000));
    if (oversized.length) throw new Error(`Manual page overflow (${language}): ${JSON.stringify(oversized)}`);
    // Chromium otherwise writes the local file URL into clickable PDF annotations.
    await page.locator("a[href]").evaluateAll((links, base) => {
      for (const link of links) if (link.protocol === "file:") {
        link.href = new URL(link.getAttribute("href"), base).href;
      }
    }, new URL("docs/", publication.pages).href);
    await page.pdf({ path: path.join(out, `docs/assembly-manual${suffix}.pdf`), printBackground: true, preferCSSPageSize: true });
    await fs.writeFile(path.join(out, `validation/pdf-generation${suffix}.json`), JSON.stringify({
      status: "PASS", language, engine: "Chromium print-to-PDF", logical_pages: await page.locator(".page").count(),
      source_images: images.length, images_loaded: true, overflow_pages: oversized,
      fonts_ready: true, local_pdf_link_uris_replaced_with_public_urls: true, errors, failed
    }, null, 2));
    console.log("PDF_EXPORTED", language, await page.locator(".page").count(), "logical pages");
    await page.close();
  }
} finally { await browser.close(); }
