import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const browserFixtureRoot =
  process.env.PHASE04L_ISOLATED_BROWSER === "1"
    ? "backend/.local/phase04l-browser"
    : "backend/.local";

test("real PDF activates and grades a 2-sign 18-general browser exam", async ({ page }, info) => {
  const source = process.env.PHASE04I_SOURCE_PDF;
  test.skip(!source, "Set PHASE04I_SOURCE_PDF to the local source.");
  test.setTimeout(300_000);
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });
  const python = resolve("backend/.venv/Scripts/python.exe");
  const cwd = resolve("backend");
  const admin = JSON.parse(readFileSync(resolve(browserFixtureRoot, "admin-browser.json"), "utf8"));
  await page.goto("/admin/login");
  await page.getByLabel("Administrator email").fill(admin.email);
  await page.getByLabel("Password", { exact: true }).fill(admin.password);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page).toHaveURL(/\/admin\/dashboard$/);
  await page.goto("/admin/pdf-uploads");
  await page.getByLabel("Dosiye ya PDF", { exact: true }).setInputFiles({
    name: "Road rules.pdf", mimeType: "application/pdf", buffer: readFileSync(source!),
  });
  const uploadReply = page.waitForResponse(
    (reply) => reply.request().method() === "POST" && reply.url().endsWith("/pdf-documents"),
    { timeout: 90_000 },
  );
  await page.getByRole("button", { name: "Ohereza PDF", exact: true }).click();
  const uploaded = await uploadReply;
  expect(uploaded.status(), uploaded.ok() ? undefined : await uploaded.text()).toBe(202);
  await expect(page.getByText("PDF yabitswe.", { exact: true })).toBeVisible();
  const workerStarted = performance.now();
  execFileSync(python, ["scripts/pdf_worker.py", "--once"], {
    cwd, windowsHide: true, stdio: "pipe", timeout: 200_000,
    env: {
      ...process.env,
      APP_ENV: "testing",
      PDF_STORAGE_ROOT: resolve(browserFixtureRoot, "admin-browser-pdf-storage"),
      EXAM_SELECTION_POLICY: "CATEGORY_BALANCED",
      EXAM_CATEGORY_ROAD_SIGN_COUNT: "2",
    },
  });
  const workerMs = Math.round(performance.now() - workerStarted);
  await page.goto("/admin/questions");
  await expect(page.getByRole("listitem").filter({ hasText: "Road rules.pdf" })).toContainText("Active source");
  await expect(page.getByText("Guhitamo hakurikijwe ibyiciro", { exact: false })).toBeVisible();
  const created = await page.request.post("/admin/pdf-api/promo-codes", {
    headers: { Origin: new URL(page.url()).origin },
    data: { code: `ROAD-PILOT-${Date.now()}`, usageLimit: 1 },
  });
  expect(created.status()).toBe(201);
  const { code } = await created.json();
  await page.goto("/tangira");
  await page.getByLabel("Amazina yawe yose").fill("Real Source Pilot");
  await page.getByLabel("Nimero ya telefoni").fill("0781234567");
  await page.getByRole("button", { name: "Komeza ku kwishyura" }).click();
  await page.getByRole("textbox", { name: "Kode ya promo" }).fill(code);
  const redemption = page.waitForResponse((reply) => reply.url().endsWith("/promos/redeem"));
  await page.getByRole("button", { name: "Koresha kode" }).click();
  expect((await redemption).status()).toBe(200);
  await expect(page).toHaveURL(/\/exam$/);
  const started = page.waitForResponse((response) => response.url().endsWith("/exams/start"));
  await page.getByRole("button", { name: "Tangira ikizamini" }).click();
  const response = await started;
  expect(response.status()).toBe(200);
  const first = (await response.json()).exam;
  const startMs = Math.round(response.request().timing().responseEnd);
  const root = `/student-api/exams/${first.id}`;
  let loadedImages = 0;
  for (let position = 1; position <= 20; position += 1) {
    await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", String(position));
    const current = await page.request.get(root + "/current");
    expect(current.status()).toBe(200);
    const { exam } = await current.json();
    expect(exam.position).toBe(position);
    expect(exam.questions).toBeUndefined();
    for (const option of exam.question.options) {
      expect(Object.keys(option).every((key) => ["id", "label", "text", "image"].includes(key))).toBe(true);
    }
    const images = page.locator("main img");
    for (let index = 0; index < await images.count(); index += 1) {
      await expect.poll(() => images.nth(index).evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);
      loadedImages += 1;
    }
    const option = page.getByRole("radio").first();
    const saved = page.waitForResponse((reply) => reply.url().endsWith("/answer"));
    await option.locator("..").click();
    const answer = await saved;
    expect(answer.status(), `answer for position ${position}: ${answer.request().postData()} ${await answer.text()}`).toBe(200);
    expect((await answer.json()).exam.question.selectedOption).toBe(0);
    await expect(option).toBeChecked();
    await page.getByRole("button", { name: position === 20 ? "Rangiza ikizamini" : "Ikibazo gikurikira" }).click();
  }
  await page.getByRole("link", { name: "Reba ibisubizo" }).click();
  await expect(page.getByRole("heading", { name: "Ibisubizo by’ikizamini" })).toBeVisible();
  const result = await (await page.request.get(root + "/result")).json();
  const database = JSON.parse(execFileSync(python, ["-c", `
import json,sys
from sqlalchemy import text
from app.core.config import Settings
from app.db.session import Database
with Database(Settings(app_env="testing")).engine.connect() as db:
    assert db.scalar(text("SELECT current_database()")) == "roadrules_test"
    rows = db.execute(text("""
        SELECT a.policy, count(*) AS total, count(DISTINCT q.fingerprint) AS unique_questions,
               count(*) FILTER (WHERE q.category = 'ROAD_SIGN') AS signs,
               count(*) FILTER (WHERE q.correct_index = r.selected_option) AS expected_score,
               g.correct AS persisted_score
        FROM exam_attempts a JOIN exam_attempt_items i ON i.attempt_id = a.id
        JOIN exam_bank_questions q ON q.id = i.question_id
        JOIN exam_responses r ON r.attempt_id = a.id AND r.position = i.position
        JOIN exam_results g ON g.attempt_id = a.id
        WHERE a.id = CAST(:attempt AS uuid) GROUP BY a.policy, g.correct
    """), {"attempt": sys.argv[1]}).mappings().one()
    assert db.scalar(text("""
        SELECT count(*) FROM payment_transactions p
        JOIN exam_attempts a ON a.guest_session_id = p.guest_session_id
        WHERE a.id = CAST(:attempt AS uuid)
    """), {"attempt": sys.argv[1]}) == 0
    print(json.dumps(dict(rows)))
`, first.id], { cwd, windowsHide: true, encoding: "utf8" }));
  expect(database).toMatchObject({ policy: "CATEGORY_BALANCED", total: 20, unique_questions: 20, signs: 2, persisted_score: result.score, expected_score: result.score });
  await expect(page.getByText(`${result.score}/20`, { exact: true })).toBeVisible();
  await expect(page.getByText(`${result.percentage}%`, { exact: true })).toBeVisible();
  expect(loadedImages).toBeGreaterThanOrEqual(2);
  expect(browserErrors).toEqual([]);
  await info.attach("real-pilot", {
    body: JSON.stringify({ workerMs, startMs, loadedImages, ...database, status: result.status }),
    contentType: "application/json",
  });
});
