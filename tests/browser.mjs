import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import http from "node:http";
import { pathToFileURL, fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const out = process.env.KIT_DIR ? path.resolve(process.env.KIT_DIR) : path.join(root, "dist/octodesk-r1");
const evidence = path.join(root, "build/browser");
await fs.mkdir(evidence, { recursive: true });
const kit = JSON.parse(await fs.readFile(path.join(out, "data/kit.json"), "utf8"));
const manifest = JSON.parse(await fs.readFile(path.join(out, "data/print-manifest.json"), "utf8"));
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
  ".png": "image/png", ".svg": "image/svg+xml", ".mp4": "video/mp4", ".webm": "video/webm", ".vtt": "text/vtt",
  ".json": "application/json", ".pdf": "application/pdf" };
const server = http.createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    const relative = pathname.replace(/^\/octodesk-brick-kit\/?/, "") || "index.html";
    const resolved = path.resolve(out, relative);
    if (!resolved.startsWith(out + path.sep)) { response.writeHead(403).end(); return; }
    const buffer = await fs.readFile(resolved);
    const type = mime[path.extname(resolved)] || "application/octet-stream";
    if (request.headers.range) {
      const match = /^bytes=(\d+)-(\d*)$/.exec(request.headers.range);
      if (!match) { response.writeHead(416).end(); return; }
      const start = Number(match[1]), end = match[2] ? Number(match[2]) : buffer.length - 1;
      response.writeHead(206, { "Content-Type": type, "Content-Range": `bytes ${start}-${end}/${buffer.length}`,
        "Content-Length": end - start + 1, "Accept-Ranges": "bytes" }).end(buffer.subarray(start, end + 1));
    } else response.writeHead(200, { "Content-Type": type, "Content-Length": buffer.length }).end(buffer);
  } catch (error) {
    if (error.code === "ENOENT") response.writeHead(404).end("not found");
    else { console.error(error); response.writeHead(500).end(); }
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const url = process.env.BASE_URL || `http://127.0.0.1:${server.address().port}/octodesk-brick-kit/`;
const browser = await chromium.launch({ headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const errors = [], checks = [];
const strictMedia = process.env.SMOKE !== "1";

function observe(page, label) {
  page.on("pageerror", (error) => errors.push(`${label}: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error" && (strictMedia || !/404|ERR_FILE_NOT_FOUND/.test(message.text())))
      errors.push(`${label}: ${message.text()}`);
  });
  page.on("response", (response) => {
    if (response.status() >= 400 && strictMedia) {
      errors.push(`${label}: HTTP ${response.status()} ${new URL(response.url()).pathname}`);
    }
  });
  page.on("requestfailed", (request) => {
    const error = request.failure()?.errorText;
    if (error !== "net::ERR_ABORTED" && strictMedia) {
      errors.push(`${label}: network failure ${error}`);
    }
  });
}

async function inspect(page, label, media) {
  console.log("BROWSER_START", label);
  await page.waitForFunction(() => window.OCTODESK_APP?.ready, null, { timeout: 90000 });
  assert.equal(await page.locator("#load-error").isVisible(), false);
  assert.equal(await page.evaluate(() => OCTODESK_APP.getState().count), 0);
  assert.equal(await page.evaluate(() => OCTODESK_APP.getTransforms().filter((x) => x.visible).length), 0);
  checks.push(`${label}: genuinely empty step zero`);
  await page.selectOption("#speed", "300");
  await page.click("#next");
  await page.waitForFunction(() => OCTODESK_APP.getState().count === 1 && !OCTODESK_APP.getState().motion);
  assert.match(await page.locator("#instance-info").textContent(), /O-001/);
  await page.click("#previous");
  assert.equal(await page.evaluate(() => OCTODESK_APP.getState().count), 0);
  await page.click("#play");
  await page.waitForFunction(() => OCTODESK_APP.getState().count >= 2);
  await page.click("#pause");
  const paused = await page.evaluate(() => OCTODESK_APP.getState().count);
  await page.waitForTimeout(600);
  assert.equal(await page.evaluate(() => OCTODESK_APP.getState().count), paused);
  checks.push(`${label}: next, previous, play, pause`);
  await page.selectOption("#step-select", "24");
  await page.click("#replay-step");
  await page.waitForFunction(() => !OCTODESK_APP.getState().playing && !OCTODESK_APP.getState().motion);
  const mug = kit.instances.find((i) => i.part === "MUG-2x3");
  const step24 = kit.instances.findLastIndex((i) => i.step === 24) + 1;
  assert.equal(await page.evaluate(() => OCTODESK_APP.getState().count), step24);
  assert.match(await page.locator("#instance-info").textContent(), /工程24/);
  checks.push(`${label}: isolated step replay stops at boundary`);
  const yellowPlate = manifest.plates.findIndex((p) => p.color === "yellow");
  await page.selectOption("#plate-select", String(yellowPlate));
  assert.match(await page.locator("#instance-info").textContent(), new RegExp(mug.id));
  assert.equal(await page.locator("#candidates button").count(), 1);
  assert.match(await page.locator("#slot-info").textContent(), /MUG-2x3/);
  await page.locator(".panel-body details summary").click();
  await page.locator("#source-list button").first().click();
  assert.equal(await page.locator("#plate-select").inputValue(), String(yellowPlate));
  await page.check("#isolate-part");
  await page.locator('.views[data-viewer="plate"] [data-view="bottom"]').click();
  await page.uncheck("#isolate-part");
  checks.push(`${label}: file-slot-instance and reverse mapping, underside`);
  await page.click("#complete");
  assert.equal(await page.evaluate(() => OCTODESK_APP.getState().count), kit.instances.length);
  const original = await page.evaluate(() => OCTODESK_APP.getTransforms());
  for (const fraction of [0, 50, 100, 0]) {
    await page.locator("#explode").evaluate((element, value) => { element.value = String(value); element.dispatchEvent(new Event("input", { bubbles: true })); }, fraction);
    await page.waitForTimeout(100);
    const projected = await page.evaluate(() => OCTODESK_APP.projectedBounds());
    assert.ok(projected.every((p) => Math.abs(p[0]) < 1 && Math.abs(p[1]) < 1 && p[2] < 1), `${label} exploded clip ${fraction}`);
  }
  const restored = await page.evaluate(() => OCTODESK_APP.getTransforms());
  assert.deepEqual(original, restored);
  for (let i = 0; i < restored.length; i++) {
    assert.ok(restored[i].position.every((v, j) => Math.abs(v - kit.instances[i].translation_mm[j]) < 1e-7));
  }
  for (const view of ["front", "right", "back", "top", "bottom", "iso"]) {
    await page.locator(`.views[data-viewer="assembly"] [data-view="${view}"]`).click();
  }
  checks.push(`${label}: completion, explosion 0/50/100/0, exact transforms, six views`);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${label} horizontal overflow`);
  if (media && strictMedia) {
    console.log("VIDEO_START", label);
    await page.locator("video").scrollIntoViewIfNeeded();
    await page.locator("video").evaluate(async (video) => {
      video.muted = true;
      await Promise.race([
        video.play(),
        new Promise((_, reject) => setTimeout(() => reject(new Error(
          `Video timeout: ready=${video.readyState}, network=${video.networkState}, error=${video.error?.message}, supports=${video.canPlayType('video/mp4; codecs="avc1.64001f"')}`
        )), 15000))
      ]);
    });
    await page.waitForFunction(() => document.querySelector("video").currentTime > .25, null, { timeout: 15000 });
    await page.locator("video").evaluate((video) => video.pause());
    checks.push(`${label}: actual HTML5 video decode`);
  }
  await page.locator("#guide").scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(evidence, `${label}-guide.png`), fullPage: false });
  await page.evaluate(() => { document.documentElement.style.scrollBehavior = "auto"; scrollTo(0, 0); });
  await page.waitForFunction(() => scrollY === 0);
  await page.screenshot({ path: path.join(evidence, `${label}-top.png`), fullPage: false });
  await page.click("#reset");
  await page.click("#play");
  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    document.dispatchEvent(new Event("visibilitychange"));
    delete document.hidden;
  });
  assert.equal(await page.evaluate(() => OCTODESK_APP.getState().playing), false);
  checks.push(`${label}: hidden tab pauses rather than skipping steps`);
  console.log("BROWSER_DONE", label);
}

try {
  const desktop = await browser.newContext({ viewport: { width: 1365, height: 1000 }, deviceScaleFactor: 1 });
  const p = await desktop.newPage();
  observe(p, "desktop-http");
  await p.goto(url, { waitUntil: "load" });
  await inspect(p, "desktop-http", true);
  await desktop.close();
  const mobile = await browser.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  const m = await mobile.newPage();
  observe(m, "mobile-http");
  await m.goto(url, { waitUntil: "load" });
  await inspect(m, "mobile-http", true);
  await mobile.close();
  const offline = await browser.newContext({ viewport: { width: 1280, height: 950 }, offline: true });
  const f = await offline.newPage();
  observe(f, "offline-file");
  const networkRequests = [];
  f.on("request", (r) => { if (/^https?:/.test(r.url())) networkRequests.push(r.url()); });
  await f.goto(pathToFileURL(path.join(out, "index.html")).href, { waitUntil: "load" });
  await inspect(f, "offline-file", true);
  assert.deepEqual(networkRequests, []);
  checks.push("offline-file: network disabled and zero HTTP(S) requests");
  await offline.close();
  assert.deepEqual(errors, []);
  const reportPath = process.env.BROWSER_REPORT ? path.resolve(process.env.BROWSER_REPORT) : path.join(out, "validation/browser.json");
  await fs.mkdir(path.dirname(reportPath), { recursive: true });
  await fs.writeFile(reportPath, JSON.stringify({
    status: "PASS", smoke_only: !strictMedia, browser: browser.version(),
    desktop: [1365, 1000], mobile: [375, 812], file_protocol: true,
    network_disabled: true, errors, checks,
    live_public_base_url: process.env.BASE_URL || null
  }, null, 2));
  console.log("BROWSER_VALIDATED", checks.length, "checks", !strictMedia ? "(smoke, media excluded)" : "");
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
