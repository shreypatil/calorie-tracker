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

console.log(errors.length ? `CONSOLE ERRORS:\n${errors.join("\n")}` : "No console errors.");
await browser.close();
