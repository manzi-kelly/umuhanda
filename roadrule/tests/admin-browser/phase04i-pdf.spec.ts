import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

test("uploaded synthetic bank is processed and activated automatically", async ({
  page,
}, info) => {
  const python = resolve("backend/.venv/Scripts/python.exe");
  const cwd = resolve("backend");
  const fixture = JSON.parse(
    readFileSync("backend/.local/admin-browser.json", "utf8"),
  );
  await page.goto("/admin/login");
  await page.getByLabel("Administrator email").fill(fixture.email);
  await page.getByLabel("Password", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page).toHaveURL(/\/admin\/dashboard$/);
  await page.goto("/admin/pdf-uploads");
  const filename = "synthetic-acceptance-42.pdf";
  const source = execFileSync(
    python,
    [
      "-c",
      "import sys; from tests.integration.test_exam_bank import fixture_pdf; sys.stdout.buffer.write(fixture_pdf(42, variant='acceptance', sign_interval=2))",
    ],
    { cwd, windowsHide: true },
  );
  await page.getByLabel("Dosiye ya PDF", { exact: true }).setInputFiles({
    name: filename,
    mimeType: "application/pdf",
    buffer: source,
  });
  await page.getByRole("button", { name: "Ohereza PDF", exact: true }).click();
  await expect(page.getByText("PDF yabitswe.", { exact: true })).toBeVisible();
  const progress = page.locator("#job-progress");
  await expect(progress).toHaveAttribute("value", "0");
  await expect(
    page.getByText("Itegereje umukozi wo gutunganya PDF.", { exact: false }),
  ).toBeVisible();
  execFileSync(python, ["-m", "scripts.admin_browser_fixture", "drain"], {
    cwd,
    stdio: "pipe",
    windowsHide: true,
  });
  await expect(progress).toHaveAttribute("value", "7");
  await expect(progress).toHaveAttribute("max", "7");
  await expect(
    page.getByRole("heading", { name: "Ibibazo byasomwe (42)", exact: true }),
  ).toBeVisible();
  const draft = page.getByRole("article").filter({
    has: page.getByRole("heading", { name: "Ikibazo 1", exact: true }),
  });
  await expect(draft).toContainText("Inyuguti yasomwe: A");
  await expect
    .poll(() =>
      draft
        .getByRole("img")
        .first()
        .evaluate((image: HTMLImageElement) => image.naturalWidth),
    )
    .toBeGreaterThan(0);
  await page.goto("/admin/questions");
  await expect(
    page.getByText("Question bank ready", { exact: true }),
  ).toBeVisible();
  const bank = page.getByRole("listitem").filter({ hasText: filename });
  await expect(bank).toContainText("Active source");
  await expect(
    bank.getByText("Eligible", { exact: true }).locator(".."),
  ).toContainText("42");
  await expect(
    bank.getByText("Eligible road signs", { exact: true }).locator(".."),
  ).toContainText("21");
  await info.attach("activated-synthetic-bank", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
});

test("available road-rules source reaches a recorded worker outcome", async ({ page }, info) => {
  const source = process.env.PHASE04I_SOURCE_PDF;
  test.skip(!source, "No local road-rules source was provided to this run.");
  test.setTimeout(300_000);
  const python = resolve("backend/.venv/Scripts/python.exe");
  const cwd = resolve("backend");
  const fixture = JSON.parse(readFileSync("backend/.local/admin-browser.json", "utf8"));
  await page.goto("/admin/login");
  await page.getByLabel("Administrator email").fill(fixture.email);
  await page.getByLabel("Password", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page).toHaveURL(/\/admin\/dashboard$/);
  await page.goto("/admin/pdf-uploads");
  await page.getByLabel("Dosiye ya PDF", { exact: true }).setInputFiles({
    name: "Road rules.pdf", mimeType: "application/pdf", buffer: readFileSync(source!),
  });
  await page.getByRole("button", { name: "Ohereza PDF", exact: true }).click();
  await expect(page.getByText("PDF yabitswe.", { exact: true })).toBeVisible();
  await expect(page.locator("#job-progress")).toHaveAttribute("value", "0");
  const started = performance.now();
  execFileSync(python, ["scripts/pdf_worker.py", "--once"], {
    cwd, stdio: "pipe", windowsHide: true, timeout: 240_000,
    env: { ...process.env, APP_ENV: "testing", PDF_STORAGE_ROOT: resolve("backend/.local/admin-browser-pdf-storage"), EXAM_SELECTION_POLICY: "UNSTRATIFIED" },
  });
  const elapsedMs = Math.round(performance.now() - started);
  const evidence = execFileSync(python, ["-c", `
import json
from sqlalchemy import func, select, text
from app.core.config import get_settings
from app.db.session import Database
from app.models.exam_bank import BankQuestion, BankRevision
from app.models.pdf_import import PdfDocument, PdfImportJob
with Database(get_settings()).session_factory() as db:
    assert db.scalar(text("select current_database()")) == "roadrules_test"
    document = db.scalar(select(PdfDocument).where(PdfDocument.original_filename == "Road rules.pdf"))
    job = db.scalar(select(PdfImportJob).where(PdfImportJob.document_id == document.id))
    revision = db.scalar(select(BankRevision).where(BankRevision.document_id == document.id))
    active = db.scalar(select(BankRevision).where(BankRevision.active))
    answers = images = 0
    if revision:
        answers, images = db.execute(select(
            func.count().filter(func.jsonb_typeof(BankQuestion.answer_evidence) == "object"),
            func.count().filter(func.jsonb_array_length(BankQuestion.assets) > 0),
        ).where(BankQuestion.revision_id == revision.id)).one()
    print(json.dumps({
        "pages": job.total_pages, "processed": job.processed_pages,
        "jobStatus": job.status, "extracted": job.extracted_question_count,
        "failedItems": job.failed_item_count, "diagnostics": len(job.diagnostics),
        "revisionStatus": revision.status if revision else None,
        "counts": revision.counts if revision else {},
        "answerEvidence": answers, "imageAssociations": images,
        "activeSource": active is not None and active.document_id == document.id,
        "priorBankStillActive": active is not None and active.document_id != document.id,
    }))
`], { cwd, env: { ...process.env, APP_ENV: "testing" }, windowsHide: true, encoding: "utf8" });
  const result = { ...JSON.parse(evidence), workerElapsedMs: elapsedMs };
  expect(["COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED"]).toContain(result.jobStatus);
  expect(result.pages).toBe(149);
  expect(result.counts.green_answers).toBeGreaterThan(0);
  expect(result.counts.parenthesized_answers).toBeGreaterThan(0);
  expect(result.counts.road_sign).toBeGreaterThan(0);
  expect(result.counts.image_only_options).toBeGreaterThanOrEqual(20);

  if (result.revisionStatus === "READY") expect(result.activeSource).toBe(true);
  else expect(result.priorBankStillActive).toBe(true);
  await expect(page.locator("#job-progress")).toHaveAttribute("value", String(result.processed));
  console.log("Road-rules source outcome", JSON.stringify(result));
  await info.attach("road-rules-source-outcome", { body: JSON.stringify(result), contentType: "application/json" });
});
