import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { mkdir } from "node:fs/promises";

test("student flow, navigation, responsive layout and locked exam", async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(180_000);
  const clockFile = "backend/.local/exam-browser-clock.txt";
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  const unexpectedResponses: string[] = [];
  const mutations: string[] = [];
  const timings: Record<string, object> = {};
  async function recordTiming(name: string, path?: string) {
    timings[name] = await page.evaluate(
      ({ name, path }) => {
        const click = performance
          .getEntriesByName(name, "mark")
          .at(-1)?.startTime;
        if (click === undefined) return {};
        const resource = performance
          .getEntriesByType("resource")
          .filter(
            (entry): entry is PerformanceResourceTiming =>
              entry instanceof PerformanceResourceTiming &&
              entry.startTime >= click &&
              entry.name.endsWith(path ?? "INVALID"),
          )
          .at(0);
        return {
          clickToReadyMs: Math.round(performance.now() - click),
          ...(resource
            ? {
                clickToRequestMs: Math.round(resource.startTime - click),
                browserRequestMs: Math.round(resource.duration),
                server: Object.fromEntries(
                  resource.serverTiming.map((item) => [
                    item.name,
                    item.duration,
                  ]),
                ),
              }
            : {}),
        };
      },
      { name, path },
    );
  }
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      !message.text().includes("422") &&
      !message.text().includes("ERR_INTERNET_DISCONNECTED")
    )
      consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    if (
      !request.failure()?.errorText.includes("ERR_ABORTED") &&
      !request.failure()?.errorText.includes("ERR_INTERNET_DISCONNECTED")
    )
      failedRequests.push(
        `${request.method()} ${request.url()}: ${request.failure()?.errorText}`,
      );
  });
  page.on("response", (response) => {
    if (
      response.status() >= 400 &&
      !(response.status() === 422 && response.url().endsWith("/promos/redeem"))
    )
      unexpectedResponses.push(`${response.status()} ${response.url()}`);
  });
  page.on("request", (request) => {
    if (request.method() !== "GET")
      mutations.push(`${request.method()} ${request.url()}`);
  });

  const width = testInfo.project.name;
  await mkdir(
    (process.env.PHASE_BROWSER_EVIDENCE ?? "docs/evidence/phase04i") +
      "/browser",
    { recursive: true },
  );
  async function capture(name: string) {
    await expect
      .poll(() =>
        page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      )
      .toBe(true);
    // Full-page screenshots otherwise pin sticky/fixed elements at the current scroll offset.
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
    await page.screenshot({
      path: `${process.env.PHASE_BROWSER_EVIDENCE ?? "docs/evidence/phase04i"}/browser/${width}-${name}.png`,
      fullPage: true,
    });
  }

  try {
    const home = await page.goto("/");
    expect(home?.status()).toBe(200);
    await expect(page.locator("#hero-heading")).toBeVisible();
    expect(
      await page
        .locator("body")
        .evaluate((element) => getComputedStyle(element).backgroundColor),
    ).toBe("rgb(246, 244, 237)");
    await capture("home");

    // Header navigation at both desktop and mobile breakpoints.
    const mobile = page.getByRole("button", { name: "Fungura menyu" });
    if (await mobile.isVisible()) {
      await mobile.focus();
      await page.keyboard.press("Enter");
      await expect(
        page.getByRole("button", { name: "Funga menyu" }),
      ).toHaveAttribute("aria-expanded", "true");
      await page.keyboard.press("Escape");
      await expect(mobile).toHaveAttribute("aria-expanded", "false");
      await mobile.click();
      await page
        .getByRole("navigation", { name: "Menyu ya telefoni" })
        .getByRole("link", { name: "Amategeko", exact: true })
        .click();
      await expect(page).toHaveURL(/#amategeko$/);
      await expect(page.locator("#amategeko")).toBeInViewport();
      await expect(mobile).toHaveAttribute("aria-expanded", "false");
      await mobile.click();
      await page
        .getByRole("navigation", { name: "Menyu ya telefoni" })
        .getByRole("link", { name: /Tangira Ikizamini/ })
        .click();
    } else {
      const navigation = page.getByRole("navigation", {
        name: "Menyu nyamukuru",
      });
      await navigation.getByRole("link", { name: "Uko Bikora" }).click();
      await expect(page).toHaveURL(/#uko-bikora$/);
      await expect(page.locator("#uko-bikora")).toBeInViewport();
      await navigation
        .getByRole("link", { name: "Amategeko", exact: true })
        .click();
      await expect(page).toHaveURL(/#amategeko$/);
      await expect(page.locator("#amategeko")).toBeInViewport();
      await page
        .locator("header")
        .getByRole("link", { name: /Tangira Ikizamini/ })
        .click();
    }
    await expect(page).toHaveURL(/\/tangira$/);
    await expect(
      page.getByRole("heading", { name: "Tangira n’amakuru yawe." }),
    ).toBeVisible();
    await capture("student");

    const fullName = page.getByRole("textbox", { name: "Amazina yawe yose" });
    const phone = page.getByRole("textbox", { name: "Nimero ya telefoni" });
    const next = page.getByRole("button", { name: "Komeza ku kwishyura" });
    await next.click();
    await expect(fullName).toHaveAttribute("aria-invalid", "true");
    await expect(phone).toHaveAttribute("aria-invalid", "true");
    await expect(fullName).toBeFocused();
    await expect(page.locator("#name-error")).toBeVisible();
    await expect(page.locator("#phone-error")).toBeVisible();
    await fullName.fill("   ");
    await phone.fill("0781234567");
    await next.click();
    await expect(fullName).toHaveAttribute("aria-invalid", "true");
    await fullName.fill("Student123");
    await next.click();
    await expect(fullName).toHaveAttribute("aria-invalid", "true");
    await fullName.fill("  QA   Student  ");
    await phone.fill("0251234567");
    await next.click();
    await expect(phone).toHaveAttribute("aria-invalid", "true");
    await expect(phone).toBeFocused();
    await capture("validation");

    // Complete this transition using keyboard navigation and Enter submission.
    await phone.fill("0781234567");
    await page.keyboard.press("Tab");
    await expect(next).toBeFocused();
    await page.keyboard.press("Enter");
    const paymentHeading = page.getByRole("heading", {
      name: "Hitamo uko wishyura.",
    });
    await expect(paymentHeading).toBeFocused();
    await expect(page.locator("main")).toContainText("QA Student");
    const sessionCookie = (await page.context().cookies()).find(
      (cookie) => cookie.name === "roadrules_student_ui",
    );
    expect(sessionCookie?.httpOnly).toBe(true);
    await capture("payment");

    await page.getByRole("button", { name: "Hindura amakuru" }).click();
    await expect(fullName).toHaveValue("QA Student");
    await expect(phone).toHaveValue("+250781234567");
    await phone.fill("+250 (73) 123-4567");
    await next.click();
    await expect(paymentHeading).toBeFocused();

    const promo = page.getByRole("textbox", { name: "Kode ya promo" });
    await promo.fill("ARBITRARY-QA-CODE");
    await page.getByRole("button", { name: "Koresha kode" }).click();
    await expect(page.locator("main").getByRole("alert")).toContainText(
      "Kode ntiyemewe",
    );
    await expect(
      page.locator('input[type="password"], input[name*="pin" i]'),
    ).toHaveCount(0);

    const started = page.waitForResponse((response) =>
      response.url().endsWith("/payments/mock/initiate"),
    );
    const mtn = page.getByRole("radio", { name: "MTN Mobile Money" });
    await mtn.evaluate((element) =>
      element.addEventListener("click", () => performance.mark("selectMtn"), {
        once: true,
      }),
    );
    const writesBeforeSelection = mutations.length;
    await mtn.check();
    const payer = page.getByLabel("Nimero ya telefoni y’uwishyura");
    await expect(payer).toHaveValue("+250731234567");
    await recordTiming("selectMtn");
    expect(mutations.length).toBe(writesBeforeSelection);
    await payer.fill("0781234567");
    await page.getByRole("button", { name: "MTN · Igerageza" }).click();
    const paymentResponse = await started;
    expect(paymentResponse.status()).toBe(201);
    const payment = await paymentResponse.json();
    await expect(
      page.getByText("Igerageza rirategereje kwemezwa."),
    ).toBeVisible();
    expect(
      (await (await page.request.get("/student-api/exam-access/me")).json())
        .entitlements,
    ).toEqual([]);
    await page.getByRole("radio", { name: "Airtel Money" }).check();
    await expect(payer).toHaveValue("+250781234567");
    await page.getByRole("button", { name: "AIRTEL · Igerageza" }).click();
    await expect(
      page.getByText("Igerageza rirategereje kwemezwa."),
    ).toBeVisible();

    const admin = JSON.parse(
      readFileSync("backend/.local/admin-browser.json", "utf8"),
    );
    const adminContext = await browser.newContext();
    try {
      const login = await adminContext.request.post(
        "http://127.0.0.1:8310/api/v1/admin/auth/login",
        {
          headers: {
            Origin: "http://127.0.0.1:3100",
            "X-CSRF-Protection": "1",
          },
          data: { email: admin.email, password: admin.password },
        },
      );
      expect(login.status()).toBe(200);
      const created = await adminContext.request.post(
        "http://127.0.0.1:8310/api/v1/admin/promo-codes",
        {
          headers: {
            Origin: "http://127.0.0.1:3100",
            "X-CSRF-Protection": "1",
          },
          data: { code: `ROAD-QA-${Date.now()}`, usageLimit: 1 },
        },
      );
      expect(created.status()).toBe(201);
      const { code } = await created.json();
      const redemption = page.waitForResponse((response) =>
        response.url().endsWith("/promos/redeem"),
      );
      await page.getByRole("radio", { name: "Kode ya promo" }).check();
      await expect(payer).toHaveCount(0);
      await promo.fill(" " + code.toLowerCase() + " ");
      const apply = page.getByRole("button", { name: "Koresha kode" });
      await apply.evaluate((element) =>
        element.addEventListener(
          "click",
          () => performance.mark("redeemPromo"),
          { once: true },
        ),
      );
      let release!: () => void;
      const wait = new Promise<void>((resolve) => {
        release = resolve;
      });
      const promoRoute = "**/student-api/promos/redeem";
      await page.route(promoRoute, async (route) => {
        await wait;
        await route.continue();
      });
      const sent = page.waitForRequest((request) =>
        request.url().endsWith("/promos/redeem"),
      );
      const before = mutations.filter((request) =>
        request.endsWith("/promos/redeem"),
      ).length;
      try {
        await apply.click();
        const request = await sent;
        expect(request.headers()["content-type"]).toBe("application/json");
        const payload = request.postDataJSON();
        expect(Object.keys(payload)).toEqual(["code"]);
        expect(payload.code === code.toLowerCase()).toBe(true);
        await expect(
          page.getByRole("button", { name: "Turimo kugenzura kode…" }),
        ).toBeDisabled();
        await promo.evaluate((input) =>
          (input as HTMLInputElement).form?.requestSubmit(),
        );
      } finally {
        release();
      }
      expect((await redemption).status()).toBe(200);
      await page.unroute(promoRoute);
      expect(
        mutations.filter((request) => request.endsWith("/promos/redeem"))
          .length,
      ).toBe(before + 1);
      await expect(page).toHaveURL(/\/exam$/);
      await expect(page.locator("#access-unavailable")).toContainText(
        "Uruhushya rwemejwe",
      );
      await recordTiming("redeemPromo", "/student-api/promos/redeem");
    } finally {
      await adminContext.close();
    }

    execFileSync(
      resolve("backend/.venv/Scripts/python.exe"),
      ["-m", "scripts.admin_browser_fixture", "settle", payment.id],
      {
        cwd: resolve("backend"),
        env: { ...process.env, PHASE04D_BROWSER_ACCESS: "1" },
        windowsHide: true,
      },
    );
    const settled = await page.request.get(`/student-api/payments/${payment.id}/status`);
    expect(settled.status()).toBe(200);
    expect((await settled.json()).status).toBe("SUCCESSFUL");

    // Attack browser-controlled state and query parameters; the server shell stays locked.
    await page.evaluate(() => {
      const fabricated = JSON.stringify({
        status: "SUCCESS",
        verified: true,
        accessGranted: true,
        fullName: "INJECTED NAME",
      });
      for (const storage of [localStorage, sessionStorage]) {
        for (const key of [
          "payment",
          "paymentStatus",
          "promo",
          "examAccess",
          "student",
          "accessGranted",
        ])
          storage.setItem(key, fabricated);
      }
    });
    const exam = await page.goto(
      "/exam?status=SUCCESS&accessGranted=true&verified=true&fullName=INJECTED",
    );
    expect(exam?.status()).toBe(200);
    await expect(page.locator("#access-unavailable")).toContainText(
      "Uruhushya rwemejwe",
    );
    await expect(page.locator("main dd")).toHaveText("QA Student");
    await expect(
      page.getByRole("heading", { name: "Amategeko y’ikizamini" }),
    ).toBeVisible();
    await expect(page.locator("main")).not.toContainText("INJECTED");
    const startButton = page.getByRole("button", {
      name: "Tangira ikizamini",
    });
    await expect(startButton).toBeEnabled();
    await page.clock.install();
    const startResponse = page.waitForResponse((response) =>
      response.url().endsWith("/exams/start"),
    );
    await startButton.click();
    const startedExam = (await (await startResponse).json()).exam;
    expect(startedExam.position).toBe(1);
    expect(startedExam.questions).toBeUndefined();
    const startedAt = Date.parse(startedExam.startedAt);
    const jump = (seconds: number) =>
      writeFileSync(
        clockFile,
        new Date(startedAt + seconds * 1000).toISOString(),
      );
    await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
    await expect(page.getByTestId("global-countdown")).toBeVisible();
    await expect(page.getByTestId("question-countdown")).toBeVisible();
    await page.route("**/student-api/exams/*/answer", (route) =>
      route.abort("internetdisconnected"),
    );
    await page.getByRole("radio").first().click();
    await expect(page.locator("main").getByRole("alert")).toContainText(
      "Reba interineti",
    );
    await page.unroute("**/student-api/exams/*/answer");
    await page.getByRole("radio").first().click();
    await expect(page.getByRole("radio").first()).toBeChecked();
    await page.reload();
    await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
    await expect(page.getByRole("radio").first()).toBeChecked();
    await page.getByRole("button", { name: "Ikibazo gikurikira" }).click();
    await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
    await expect(page.getByRole("radio").first()).not.toBeChecked();
    const recovered = await (
      await page.request.get("/student-api/exams/me")
    ).json();
    expect(recovered.exam.globalDeadline).toBe(startedExam.globalDeadline);
    jump(125);
    await page.clock.fastForward(65000);
    await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", /^[34]$/);
    await expect
      .poll(() =>
        page
          .locator("main img")
          .evaluateAll((images) =>
            images.every(
              (image) =>
                image instanceof HTMLImageElement &&
                image.complete &&
                image.naturalWidth > 0,
            ),
          ),
      )
      .toBe(true);
    jump(1080);
    await page.getByRole("button", { name: "Vugurura" }).click();
    await expect(page.getByTestId("global-countdown")).toHaveText(
      /^(2:00|1:5[0-9])$/,
    );
    await expect(
      page.getByTestId("global-countdown").locator(".."),
    ).toHaveClass(/animate-pulse/);
    await capture("warning");
    jump(1201);
    await page.getByRole("button", { name: "Vugurura" }).click();
    await expect(
      page.getByRole("heading", { name: "Ikizamini cyarangiye" }),
    ).toBeVisible();
    await expect(page.getByRole("radio")).toHaveCount(0);
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Ikizamini cyarangiye" }),
    ).toBeVisible();
    await page.getByRole("link", { name: "Reba ibisubizo" }).click();
    await expect(
      page.getByText("Ntabwo watsinze ikizamini. Ushobora kongera kugerageza."),
    ).toBeVisible();
    await expect(page.getByText("1/20", { exact: true })).toBeVisible();
    await expect(page.getByText("5%", { exact: true })).toBeVisible();
    await capture("failed-result");
    const originalResultPath = `/student-api/exams/${startedExam.id}/result`;
    const original = await (await page.request.get(originalResultPath)).json();
    const anonymous = await browser.newContext();
    try {
      const response = await anonymous.request.get(
        new URL(originalResultPath, page.url()).href,
      );
      expect(response.status()).toBe(401);
      expect(await response.text()).not.toContain("QA Student");
      const anonymousPage = await anonymous.newPage();
      let allowRequest!: () => void;
      const blocked = new Promise<void>((resolve) => {
        allowRequest = resolve;
      });
      await anonymousPage.route(
        "**/student-api/exams/*/result",
        async (route) => {
          await blocked;
          await route.continue();
        },
      );
      try {
        await anonymousPage.goto(
          new URL(`/results/${startedExam.id}`, page.url()).href,
        );
        await expect(
          anonymousPage.getByText("Turimo gushaka ibisubizo…", { exact: true }),
        ).toBeVisible();
      } finally {
        allowRequest();
      }
      await expect(
        anonymousPage.locator("main").getByRole("alert"),
      ).toContainText("Igihe cyo gukoresha serivisi cyarangiye");
      await expect(
        anonymousPage.getByText("QA Student", { exact: true }),
      ).toHaveCount(0);
    } finally {
      await anonymous.close();
    }

    const missing = await page.request.get(
      "/student-api/exams/00000000-0000-0000-0000-000000000000/result",
    );
    expect(missing.status()).toBe(404);
    expect(await missing.text()).not.toContain("QA Student");

    await page.getByRole("link", { name: "Pay to Try Again" }).click();
    await expect(
      page.getByText("QA Student", { exact: true }).filter({ visible: true }),
    ).toBeVisible();
    await page
      .getByRole("link", { name: "Komeza ku kwitegura ikizamini" })
      .click();
    await expect(page).toHaveURL(/retake=1$/);
    rmSync(clockFile, { force: true });
    const retakeStarted = page.waitForResponse((response) =>
      response.url().endsWith("/exams/start"),
    );
    await startButton.click();
    const retakeResponse = await retakeStarted;
    const retake = (await retakeResponse.json()).exam;
    expect(retake.id).not.toBe(startedExam.id);
    const retakeRoot = `/student-api/exams/${retake.id}`;
    const headers = { Origin: new URL(page.url()).origin };
    const retakeTime = Date.parse(retake.startedAt);
    const latency: Record<string, number[]> = {
      start: [Math.round(retakeResponse.request().timing().responseEnd)],
    };
    async function measure<T>(
      name: string,
      action: () => Promise<T>,
    ): Promise<T> {
      const start = performance.now();
      const result = await action();
      (latency[name] ??= []).push(Math.round(performance.now() - start));
      return result;
    }
    for (let position = 1; position <= 20; position += 1) {
      writeFileSync(
        clockFile,
        new Date(retakeTime + position * 1000).toISOString(),
      );
      const current = await measure("current", () =>
        page.request.get(retakeRoot + "/current"),
      );
      expect(current.status()).toBe(200);
      const { exam } = await current.json();
      expect(exam.position).toBe(position);
      expect(exam.total).toBe(20);
      expect(exam.questions).toBeUndefined();
      expect(Object.keys(exam.question).sort()).toEqual([
        "answerVersion",
        "deadline",
        "images",
        "options",
        "selectedOption",
        "text",
      ]);
      const saved = await measure("answer", () =>
        page.request.put(retakeRoot + "/answer", {
          headers,
          data: {
            position,
            optionId: position <= 12 ? 0 : 1,
            answerVersion: 0,
          },
        }),
      );
      expect(saved.status()).toBe(200);
      const next = await measure("next", () =>
        page.request.post(retakeRoot + "/next", {
          headers,
          data: { position },
        }),
      );
      expect(next.status()).toBe(200);
      if (position === 20) {
        const completed = (await next.json()).exam;
        expect(completed.question).toBeNull();
        expect(completed.completionReason).toBe("ALL_QUESTIONS_FINISHED");
      }
    }
    for (let sample = 0; sample < 5; sample += 1) {
      const response = await measure("result", () =>
        page.request.get(retakeRoot + "/result"),
      );
      expect(response.status()).toBe(200);
      const grade = await response.json();
      expect([
        grade.correct,
        grade.incorrect,
        grade.unanswered,
        grade.status,
      ]).toEqual([12, 8, 0, "PASSED"]);
    }
    const databaseEvidence = execFileSync(
      resolve("backend/.venv/Scripts/python.exe"),
      [
        "-c",
        `
import json
import sys
from uuid import UUID
from sqlalchemy import func, select, text
from app.core.config import get_settings
from app.db.session import Database
from app.models.exam_access import ExamEntitlement
from app.models.exam_bank import BankQuestion, ExamAttempt, ExamItem
from app.models.exam_results import ExamResult
with Database(get_settings()).session_factory() as db:
    assert db.scalar(text("select current_database()")) == "roadrules_test"
    first, second = [db.get(ExamAttempt, UUID(value)) for value in sys.argv[1:]]
    assert first.student_id == second.student_id and first.guest_session_id == second.guest_session_id
    assert first.entitlement_id != second.entitlement_id
    snapshots = [
        set(db.scalars(select(BankQuestion.fingerprint).join(
            ExamItem, ExamItem.question_id == BankQuestion.id
        ).where(ExamItem.attempt_id == attempt.id)))
        for attempt in (first, second)
    ]
    assert [len(items) for items in snapshots] == [20, 20] and not snapshots[0] & snapshots[1]
    grants = [db.get(ExamEntitlement, attempt.entitlement_id) for attempt in (first, second)]
    assert all(grant.status == "CONSUMED" for grant in grants)
    assert [grant.attempt_id for grant in grants] == [first.id, second.id]
    grades = [db.get(ExamResult, attempt.id) for attempt in (first, second)]
    assert [grade.correct for grade in grades] == [1, 12]
    assert db.scalar(select(func.count()).select_from(ExamResult).where(
        ExamResult.attempt_id.in_([first.id, second.id])
    )) == 2
    counts = db.execute(text("""
        SELECT (SELECT count(*) FROM students), (SELECT count(*) FROM exam_attempts),
               (SELECT count(*) FROM exam_results WHERE correct >= 12),
               (SELECT count(*) FROM exam_results WHERE correct < 12),
               (SELECT count(*) FROM exam_entitlements WHERE promo_id IS NOT NULL),
               (SELECT count(*) FROM payment_transactions WHERE mode = 'MOCK')
    """)).one()
    print(json.dumps({
        "items": [20, 20], "fingerprintOverlap": 0, "scores": [1, 12], "consumedGrants": 2,
        "overview": dict(zip(("students", "attempts", "passed", "failed", "redeemed", "mock"), counts)),
    }))
`,
        startedExam.id,
        retake.id,
      ],
      {
        cwd: resolve("backend"),
        env: { ...process.env, APP_ENV: "testing" },
        windowsHide: true,
        encoding: "utf8",
      },
    );
    const database = JSON.parse(databaseEvidence);
    console.log("PHASE04I_ACCEPTANCE " + JSON.stringify({ latency, database }));
    await testInfo.attach("acceptance-data", {
      body: JSON.stringify({ latency, database }),
      contentType: "application/json",
    });
    await page.goto(`/results/${retake.id}`);
    await expect(
      page.getByText("Congratulations! Watsinze ikizamini."),
    ).toBeVisible();
    await expect(page.getByText("12/20", { exact: true })).toBeVisible();
    await expect(page.getByText("60%", { exact: true })).toBeVisible();
    await capture("passed-result");
    expect(await (await page.request.get(originalResultPath)).json()).toEqual(
      original,
    );
    expect(
      await (
        await page.request.get("/student-api/students/exams/history")
      ).json(),
    ).toHaveLength(2);
    const replay = await page.request.post("/student-api/exams/start", {
      headers,
      data: retakeResponse.request().postDataJSON(),
    });
    expect(replay.status()).toBe(200);
    expect((await replay.json()).exam.id).toBe(retake.id);
    expect(
      (
        await page.request.put(retakeRoot + "/result", {
          headers,
          data: { score: 20 },
        })
      ).status(),
    ).toBe(404);
    const stranger = await browser.newContext();
    try {
      const api = stranger.request;
      const target = (path: string) => new URL(path, page.url()).href;
      expect(
        (
          await api.post(target("/student-api/students/sessions"), {
            headers,
            data: {
              fullName: "Isolated Student",
              phoneNumber: "+250781234567",
            },
          })
        ).status(),
      ).toBe(201);
      for (const suffix of ["/current", "/result"]) {
        expect((await api.get(target(retakeRoot + suffix))).status()).toBe(404);
      }
    } finally {
      await stranger.close();
    }
    const reporting = await browser.newContext();
    try {
      const reportPage = await reporting.newPage();
      await reportPage.goto(new URL("/admin/login", page.url()).href);
      await reportPage.getByLabel("Administrator email").fill(admin.email);
      await reportPage
        .getByLabel("Password", { exact: true })
        .fill(admin.password);
      await reportPage
        .getByRole("button", { name: "Sign in securely" })
        .click();
      await expect(reportPage).toHaveURL(/\/admin\/dashboard$/);
      const summary = await reporting.request.get(
        new URL("/admin/analytics-api?period=weekly", page.url()).href,
      );
      expect(summary.status()).toBe(200);
      const overview = await summary.json();
      expect(overview.students.records).toBe(database.overview.students + 1);
      expect(overview.examinations.attempts).toBe(database.overview.attempts);
      expect(overview.examinations.passed).toBe(database.overview.passed);
      expect(overview.examinations.failed).toBe(database.overview.failed);
      expect(overview.promos.redeemed).toBe(database.overview.redeemed);
      expect(overview.payments.initiated).toBe(database.overview.mock);
      expect(overview.payments.realVerifiedRevenue).toBeNull();
      expect(overview.window.timezone).toBe("Africa/Kigali");
      expect(overview.window.start).toContain("T22:00:00");
      await expect(
        reportPage.getByRole("meter", { name: "Ijanisha ry’abatsinze" }),
      ).toBeVisible();
    } finally {
      await reporting.close();
    }
    expect(
      mutations.some(
        (request) => request.startsWith("PUT ") && request.endsWith("/answer"),
      ),
    ).toBe(true);
  } finally {
    rmSync(clockFile, { force: true });
    await testInfo.attach("browser-observations", {
      body: JSON.stringify(
        {
          width,
          browserVersion: browser.version(),
          consoleErrors,
          pageErrors,
          failedRequests,
          unexpectedResponses,
          mutations,
          timings,
        },
        null,
        2,
      ),
      contentType: "application/json",
    });
    expect(consoleErrors, "browser console errors").toEqual([]);
    expect(pageErrors, "uncaught application errors").toEqual([]);
    expect(failedRequests, "failed requests").toEqual([]);
    expect(unexpectedResponses, "HTTP errors").toEqual([]);
  }
});

test("direct exam entry stays locked without JavaScript", async ({
  browser,
}, testInfo) => {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: testInfo.project.use.viewport,
  });
  const page = await context.newPage();
  try {
    const response = await page.goto(
      "http://127.0.0.1:3100/exam?accessGranted=true",
    );
    expect(response?.status()).toBe(200);
    await expect(
      page.getByRole("button", { name: "Tangira ikizamini" }),
    ).toBeDisabled();
    await expect(page.locator("#access-unavailable")).toContainText(
      "Nta ruhushya",
    );
  } finally {
    await context.close();
  }
});
