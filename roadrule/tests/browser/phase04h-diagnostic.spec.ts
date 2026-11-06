import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

test("local payment request timing and response diagnostics", async ({
  page,
  browser,
}) => {
  const headers = { Origin: "http://127.0.0.1:3100" };
  const admin = JSON.parse(
    readFileSync("backend/.local/admin-browser.json", "utf8"),
  );
  const context = await browser.newContext();
  const auth = { ...headers, "X-CSRF-Protection": "1" };
  expect(
    (
      await context.request.post(
        "http://127.0.0.1:8310/api/v1/admin/auth/login",
        {
          headers: auth,
          data: { email: admin.email, password: admin.password },
        },
      )
    ).status(),
  ).toBe(200);
  const created = await context.request.post(
    "http://127.0.0.1:8310/api/v1/admin/promo-codes",
    {
      headers: auth,
      data: { code: `ROAD-DIAG-${Date.now()}`, usageLimit: 3 },
    },
  );
  const { code } = await created.json();
  for (let i = 0; i < 3; i++) {
    for (const [path, data] of [
      [
        "students/sessions",
        { fullName: "Baseline Student", phoneNumber: "+250781234567" },
      ],
      ["exam-access/me", null],
      ["promos/redeem", { code: "ARBITRARY-QA-CODE" }],
      ["promos/redeem", { promoCode: "PLACEHOLDER" }],
      ["promos/redeem", { code: " " + code.toLowerCase() + " " }],
      ["exam-access/me", null],
    ] as const) {
      const start = performance.now();
      const result = await page.request.fetch("/student-api/" + path, {
        method: data ? "POST" : "GET",
        headers,
        data: data ?? undefined,
      });
      const value = await result.json();
      console.log(
        JSON.stringify({
          i,
          path,
          status: result.status(),
          ms: Math.round(performance.now() - start),
          timing: result.headers()["server-timing"],
          ...(result.status() >= 400 ? { body: value } : {}),
        }),
      );
    }
    const start = performance.now();
    await page.goto("/exam");
    await expect(
      page.getByRole("button", { name: "Tangira ikizamini" }),
    ).toBeEnabled();
    console.log(
      JSON.stringify({
        i,
        path: "exam-ready",
        ms: Math.round(performance.now() - start),
      }),
    );
  }
  const databaseTimings = execFileSync(
    resolve("backend/.venv/Scripts/python.exe"),
    [
      "-c",
      `
from uuid import UUID
from sqlalchemy import func, select
from app.core.config import get_settings
from app.db.session import Database
from app.models.exam_bank import BankQuestion, BankRevision
from app.services.exam_generation import unused_questions
with Database(get_settings()).session_factory() as db:
    bank = db.scalar(select(BankRevision).where(BankRevision.active))
    pool = unused_questions(bank, UUID(int=0))
    queries = {
        "previous_selection": pool.order_by(func.md5(BankQuestion.fingerprint + "timing")).limit(20),
        "grouped_readiness": pool.with_only_columns(
            BankQuestion.category, BankQuestion.difficulty, func.count()
        ).group_by(BankQuestion.category, BankQuestion.difficulty),
    }
    for name, query in queries.items():
        sql = query.compile(db.bind, compile_kwargs={"literal_binds": True})
        timings = []
        for _ in range(5):
            plan = db.connection().exec_driver_sql("EXPLAIN (ANALYZE, FORMAT JSON) " + str(sql)).scalar_one()[0]
            timings.append(round(plan["Execution Time"], 3))
        print(name, timings)
`,
    ],
    {
      cwd: resolve("backend"),
      env: { ...process.env, APP_ENV: "testing" },
      windowsHide: true,
      encoding: "utf8",
    },
  );
  console.log(databaseTimings.trim());
  await page.goto("/tangira");
  await page.getByLabel("Amazina yawe yose").fill("Timeout Student");
  await page.getByLabel("Nimero ya telefoni").fill("0781234567");
  await page.getByRole("button", { name: "Komeza ku kwishyura" }).click();
  const input = page.getByRole("textbox", { name: "Kode ya promo" });
  await input.fill("RETRY-PROBE");
  const promoPath = "**/student-api/promos/redeem";
  let release!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(promoPath, async (route) => {
    await held;
    await route.abort().catch(() => {});
  });
  try {
    await page.getByRole("button", { name: "Koresha kode" }).click();
    await expect(page.locator("main").getByRole("alert")).toContainText(
      "Seriveri yatinze",
      { timeout: 16000 },
    );
    await expect(input).toHaveValue("RETRY-PROBE");
    await expect(
      page.getByRole("button", { name: "Koresha kode" }),
    ).toBeEnabled();
  } finally {
    release();
    await page.unroute(promoPath);
  }
  await page.getByRole("button", { name: "Koresha kode" }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "Kode ntiyemewe",
  );
  await context.close();
});
