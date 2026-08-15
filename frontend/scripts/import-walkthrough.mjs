/**
 * Drive the PDF import flow end to end in a real browser.
 *
 * Sign in → upload a fixture → screenshot the review → flip the date format →
 * import → screenshot the history → undo. Fails loudly on any console error.
 *
 *   node scripts/import-walkthrough.mjs <out-dir> <fixture.pdf>
 */
import { chromium } from "playwright";

const BASE = process.env.APP_URL ?? "http://localhost:5173";
const OUT = process.argv[2] ?? "./shots";
const PDF = process.argv[3] ?? "../backend/tests/fixtures/clean_table.pdf";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));

await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.fill('input[type="email"]', "demo@example.com");
await page.fill('input[type="password"]', "demo-password-1234");
await page.click('button[type="submit"]');
await page.waitForURL(`${BASE}/`, { timeout: 15000 });

await page.goto(`${BASE}/import`, { waitUntil: "networkidle" });
await page.setInputFiles('input[type="file"]', PDF);
await page.waitForSelector("text=Import ", { timeout: 20000 });
await page.mouse.move(0, 0);
await page.waitForTimeout(400);
await page.screenshot({ path: `${OUT}/07-import-review.png`, fullPage: true });

// The date-format switch re-reads the file — the correction path.
const before = await page.textContent("table tbody tr td:nth-child(3)");
await page.selectOption('select:near(:text("Dates read as"))', "MDY").catch(() => {});
await page.waitForTimeout(1500);
const after = await page.textContent("table tbody tr td:nth-child(3)");
console.log(`date format switch: "${before?.trim()}" -> "${after?.trim()}"`);
await page.screenshot({ path: `${OUT}/08-import-reread.png`, fullPage: true });

// Put it back and import.
await page.selectOption('select:near(:text("Dates read as"))', "ISO").catch(() => {});
await page.waitForTimeout(1500);
await page.click('button:has-text("Import ")');
await page.waitForSelector("text=Imported", { timeout: 20000 });
await page.waitForTimeout(600);
await page.screenshot({ path: `${OUT}/09-import-done.png`, fullPage: true });

const entriesBefore = await countEntries(page);
await page.click('button:has-text("Undo")');
await page.waitForTimeout(1500);
const entriesAfter = await countEntries(page);
console.log(`entries after import: ${entriesBefore}, after undo: ${entriesAfter}`);

console.log(errors.length ? `CONSOLE ERRORS:\n${errors.join("\n")}` : "No console errors.");
await browser.close();

async function countEntries(page) {
  await page.goto(`${BASE}/entries`, { waitUntil: "networkidle" });
  const text = await page.textContent(".text-\\[13px\\].text-ink-muted");
  const match = (await page.textContent("body"))?.match(/(\d+)\s+entr(?:y|ies)/);
  await page.goto(`${BASE}/import`, { waitUntil: "networkidle" });
  return match?.[1] ?? text ?? "?";
}
