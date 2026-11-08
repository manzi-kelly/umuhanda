import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

test("source-backed vector choices render inside the authenticated student options", async ({ page }, info) => {
  test.setTimeout(180_000);
  const python = resolve("backend/.venv/Scripts/python.exe");
  const cwd = resolve("backend");
  const admin = JSON.parse(readFileSync("backend/.local/admin-browser.json", "utf8"));
  await page.goto("/admin/login");
  await page.getByLabel("Administrator email").fill(admin.email);
  await page.getByLabel("Password", { exact: true }).fill(admin.password);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page).toHaveURL(/\/admin\/dashboard$/);
  await page.goto("/admin/pdf-uploads");
  const source = execFileSync(python, ["-c",
    "import sys; from tests.integration.test_image_option_exam import vector_option_bank; sys.stdout.buffer.write(vector_option_bank())",
  ], { cwd, windowsHide: true });
  await page.getByLabel("Dosiye ya PDF", { exact: true }).setInputFiles({
    name: "synthetic-vector-choice-bank.pdf", mimeType: "application/pdf", buffer: source,
  });
  await page.getByRole("button", { name: "Ohereza PDF", exact: true }).click();
  await expect(page.getByText("PDF yabitswe.", { exact: true })).toBeVisible();
  execFileSync(python, ["-m", "scripts.admin_browser_fixture", "drain"], {
    cwd, windowsHide: true, stdio: "pipe",
  });
  await expect(page.getByRole("heading", { name: "Ibibazo byasomwe (20)", exact: true })).toBeVisible();
  await page.goto("/admin/questions");
  await expect(page.getByRole("listitem").filter({ hasText: "synthetic-vector-choice-bank.pdf" }))
    .toContainText("Active source");
  const created = await page.request.post("/admin/pdf-api/promo-codes", {
    headers: { Origin: new URL(page.url()).origin },
    data: { code: `ROAD-IMAGE-${Date.now()}`, usageLimit: 1 },
  });
  expect(created.status()).toBe(201);
  const { code } = await created.json();
  await page.goto("/tangira");
  await page.getByLabel("Amazina yawe yose").fill("Vector Fixture Student");
  await page.getByLabel("Nimero ya telefoni").fill("0781234567");
  await page.getByRole("button", { name: "Komeza ku kwishyura" }).click();
  await page.getByRole("textbox", { name: "Kode ya promo" }).fill(code);
  await page.getByRole("button", { name: "Koresha kode" }).click();
  await expect(page).toHaveURL(/\/exam$/);
  await page.getByRole("button", { name: "Tangira ikizamini" }).click();
  const choices = page.locator("fieldset img");
  for (let position = 1; position <= 20; position += 1) {
    await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", String(position));
    if (await choices.count()) break;
    if (position < 20) await page.getByRole("button", { name: "Ikibazo gikurikira" }).click();
  }
  await expect(choices).toHaveCount(4);
  for (const label of ["A", "B", "C", "D"]) {
    const image = page.getByRole("img", { name: `Ishusho y’ihitamo ${label}` });
    await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await info.attach("synthetic-vector-student-options", { body: await page.screenshot(), contentType: "image/png" });
});
