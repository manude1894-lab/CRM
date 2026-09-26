// Screenshot every field on the New Client form (Corporate + Individual), one PNG per field.
//
// Read-only: opens the form, expands sections and ticks toggles only in the browser's
// local form state — never clicks a Save / Create button, so nothing reaches the database.
//
// Usage (PowerShell):
//   $env:CRM_URL="https://<frontend-url>"; $env:CRM_EMAIL="..."; $env:CRM_PASSWORD="..."
//   node scripts/field-screenshots/capture.mjs
// Output: screenshots/client-form/<Corporate|Individual>/NN - <Section> - <Field>.png + index.md

import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const { CRM_URL, CRM_EMAIL, CRM_PASSWORD } = process.env;
if (!CRM_URL || !CRM_EMAIL || !CRM_PASSWORD) {
  console.error("Set CRM_URL, CRM_EMAIL and CRM_PASSWORD environment variables first.");
  process.exit(1);
}
const OUT_DIR = path.resolve(process.env.OUT_DIR || "screenshots/client-form");
const CLIENT_TYPES = ["Corporate", "Individual"];
// Selects whose value reveals extra fields: [field label, pattern for the option to pick].
const REVEALING_SELECTS = [["Regulator", /^Other$/], ["AML Classification", /^EDD$/], ["Country of Residence", /^(UAE|United Arab Emirates)/]];

const safe = (s) => s.replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, " ").trim().slice(0, 80);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });

// ── Log in ──
await page.goto(CRM_URL, { waitUntil: "networkidle" });
await page.fill('input[type="email"]', CRM_EMAIL);
await page.fill('input[type="password"]', CRM_PASSWORD);
await page.getByRole("button", { name: "Sign In" }).click();
await page.getByRole("button", { name: "Clients" }).waitFor({ timeout: 30000 });

// ── Open New Client ──
await page.getByRole("button", { name: "Clients" }).click();
await page.getByRole("button", { name: "New Client" }).click();
const modal = page.locator("div.fixed.inset-0").filter({ hasText: "New Client" }).last();
await modal.waitFor();

const index = [];

for (const clientType of CLIENT_TYPES) {
  await modal.locator("select").first().selectOption(clientType);
  await page.waitForTimeout(300);

  // Expand every collapsible section (chevron without rotate-90 = closed). Repeat until
  // stable, since opening one can reveal another.
  for (let pass = 0; pass < 3; pass++) {
    const closed = modal.locator("div.mb-2.border > button:has(svg:not(.rotate-90))");
    const n = await closed.count();
    if (!n) break;
    for (let i = n - 1; i >= 0; i--) await closed.nth(i).click();
  }

  // Tick on/off toggles (not MultiSelect options) so their conditional fields appear.
  const toggles = modal.locator('label.flex > input[type="checkbox"]');
  for (let i = 0; i < await toggles.count(); i++) {
    const cb = toggles.nth(i);
    const inMultiSelect = await cb.evaluate((el) => !!el.closest(".max-h-40"));
    if (!inMultiSelect && !(await cb.isChecked())) await cb.check();
  }
  for (const [label, option] of REVEALING_SELECTS) {
    const select = modal.locator("div.mb-4", { has: page.locator(":scope > label", { hasText: new RegExp(`^${label}`) }) }).locator("select");
    if (!(await select.count())) continue;
    const value = await select.first().evaluate((el, src) => {
      const re = new RegExp(src);
      return [...el.options].find((o) => re.test(o.textContent.trim()))?.value;
    }, option.source);
    if (value !== undefined) await select.first().selectOption(value);
  }
  await page.waitForTimeout(300);

  // Fields = <Field> wrappers (div.mb-4 > label), standalone checkbox toggles, and
  // unlabelled multi-selects that make up a whole section (e.g. Services Obtained).
  const fields = modal.locator("div.mb-4:has(> label), label.flex:has(> input[type=checkbox]), div.max-h-40");
  const count = await fields.count();
  const dir = path.join(OUT_DIR, clientType);
  fs.mkdirSync(dir, { recursive: true });

  let n = 0;
  for (let i = 0; i < count; i++) {
    const el = fields.nth(i);
    const info = await el.evaluate((node) => {
      const section = node.closest("div.mb-2.border")?.querySelector(":scope > button span")?.textContent || "Client Info";
      if (node.matches(".max-h-40")) {
        // A MultiSelect inside a <Field> is already captured with its label.
        return node.closest("div.mb-4") ? null : { label: section.trim(), section: section.trim() };
      }
      if (node.closest(".max-h-40")) return null; // MultiSelect option, not a field
      const label = (node.matches("label") ? node.textContent : node.querySelector(":scope > label")?.textContent) || "";
      return { label: label.replace("*", "").trim(), section: section.trim() };
    });
    if (!info || !info.label || !(await el.isVisible())) continue;

    n++;
    const file = `${String(n).padStart(2, "0")} - ${safe(info.section)} - ${safe(info.label)}.png`;
    await el.scrollIntoViewIfNeeded();
    await el.screenshot({ path: path.join(dir, file) });
    index.push({ clientType, section: info.section, label: info.label, file: `${clientType}/${file}` });
  }
  console.log(`${clientType}: ${n} fields captured`);
}

await page.keyboard.press("Escape").catch(() => {});
await browser.close();

const md = ["# New Client form — field screenshots", "", `Captured ${new Date().toISOString()} from ${CRM_URL}`, "",
  "| Client Type | Section | Field | Image |", "|---|---|---|---|",
  ...index.map((r) => `| ${r.clientType} | ${r.section} | ${r.label} | [${r.file}](${encodeURI(r.file)}) |`)];
fs.writeFileSync(path.join(OUT_DIR, "index.md"), md.join("\n") + "\n");
console.log(`Done — ${index.length} screenshots in ${OUT_DIR}`);
