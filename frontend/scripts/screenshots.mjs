/**
 * Sign in as the demo user and screenshot every page.
 *
 * A quick way to eyeball the whole UI — and to catch runtime errors that the
 * type checker cannot, since it fails loudly on any console error.
 *
 *   npm run screenshots -- ./shots 1280
 *
 * Needs the dev server and API running, the seed data loaded, and a browser:
 * `npx playwright install chromium`.
 */
import { chromium } from "playwright";

const BASE = process.env.APP_URL ?? "http://localhost:5173";
const OUT = process.argv[2] ?? "./shots";
const WIDTH = Number(process.argv[3] ?? 1280);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: WIDTH, height: 900 } });

const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));

await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.screenshot({ path: `${OUT}/01-login.png`, fullPage: true });

await page.fill('input[type="email"]', "demo@example.com");
await page.fill('input[type="password"]', "demo-password-1234");
await page.click('button[type="submit"]');
await page.waitForURL(`${BASE}/`, { timeout: 15000 });
await page.waitForLoadState("networkidle");
await page.mouse.move(0, 0); // otherwise a chart tooltip stays open under the cursor
await page.waitForTimeout(600); // let charts finish their layout pass
await page.screenshot({ path: `${OUT}/02-dashboard.png`, fullPage: true });

for (const [name, path] of [
  ["03-entries", "/entries"],
  ["04-reports", "/reports"],
  ["05-goals", "/goals"],
  ["06-import", "/import"],
  ["07-chat", "/chat"],
]) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
}

// The log-a-meal form, expanded.
await page.goto(`${BASE}/entries`, { waitUntil: "networkidle" });
await page.click("text=Log a meal");
await page.waitForTimeout(300);
await page.screenshot({ path: `${OUT}/06-log-form.png`, fullPage: true });

// AI nutrition estimation: a named dish fills only the untouched fields.
await page.goto(`${BASE}/entries?log=1`, { waitUntil: "networkidle" });
await page.waitForTimeout(500);
await page.fill('input[name="food_name"]', "Chicken rice bowl");
await page.fill('input[name="quantity"]', "350");
await page.fill('input[name="unit"]', "g");
await page.fill('input[name="calories"]', "600");
await page.click('button:text-is("Estimate nutrition")');
await page.waitForSelector("text=estimated by AI", { timeout: 20000 });
await page.screenshot({ path: `${OUT}/11-estimate.png`, fullPage: true });

// Photo extraction: a label fills the form, a plate produces an itemised draft.
const FIXTURES = "../backend/tests/fixtures";

/** Drive the real button, so the label/meal mode is set the way a user sets it. */
async function scan(label, file) {
  const chooser = page.waitForEvent("filechooser");
  await page.click(`button:has-text("${label}")`);
  await (await chooser).setFiles(file);
}

await page.goto(`${BASE}/entries`, { waitUntil: "networkidle" });
await page.click("text=Log a meal");

await scan("Scan a label", `${FIXTURES}/label.jpg`);
await page.waitForFunction(
  () => document.querySelector('input[name="food_name"]')?.value?.length > 0,
  { timeout: 20000 },
);
await page.screenshot({ path: `${OUT}/09-photo-label.png`, fullPage: true });

await scan("Estimate a meal", `${FIXTURES}/plate.jpg`);
await page.waitForSelector("text=Add all", { timeout: 20000 });
await page.screenshot({ path: `${OUT}/10-photo-plate.png`, fullPage: true });

// A chat turn that proposes a write, so the draft card is covered too.
await page.goto(`${BASE}/chat`, { waitUntil: "networkidle" });
await page.fill("#chat-message", "log 2 eggs and toast for breakfast");
await page.click("button:has-text('Send')");
await page.waitForSelector("text=Draft", { timeout: 15000 });
await page.screenshot({ path: `${OUT}/08-chat-draft.png`, fullPage: true });

console.log(errors.length ? `CONSOLE ERRORS:\n${errors.join("\n")}` : "No console errors.");
await browser.close();
