import { test, expect, type Page } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

const browserFixtureRoot =
  process.env.PHASE04L_ISOLATED_BROWSER === "1"
    ? "backend/.local/phase04l-browser"
    : "backend/.local";

function fixture(): { email: string; password: string } {
  return JSON.parse(readFileSync(resolve(browserFixtureRoot, "admin-browser.json"), "utf8"));
}
async function signIn(page: Page) {
  const credentials = fixture();
  await page.goto("/admin/login");
  await page.getByLabel("Administrator email").fill(credentials.email);
  await page.getByLabel("Password", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page).toHaveURL(/\/admin\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Administrator dashboard", exact: true }),
  ).toBeVisible();
}
async function navigate(page: Page, label: string) {
  const open = page.getByRole("button", {
    name: "Open admin menu",
    exact: true,
  });
  const link = page
    .getByRole("navigation", { name: "Administrator navigation" })
    .getByRole("link", { name: label, exact: true });
  await expect(async () => {
    if (await open.isVisible()) await open.click();
    await expect(link).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 10000 });
  await link.click();
}
async function screenshot(page: Page, width: string, name: string) {
  mkdirSync(
    (process.env.PHASE_BROWSER_EVIDENCE ?? "docs/evidence/phase04i") +
      "/browser",
    { recursive: true },
  );
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: `${process.env.PHASE_BROWSER_EVIDENCE ?? "docs/evidence/phase04i"}/browser/${width}-${name}.png`,
    fullPage: true,
  });
}

test("unauthorized, forged-role and forged-cookie routes fail closed", async ({
  page,
  context,
}, info) => {
  for (const slug of [
    "dashboard",
    "questions",
    "pdf-uploads",
    "students",
    "exams",
    "payments",
    "promo-codes",
    "settings",
    "system",
    "refunds",
  ]) {
    await page.goto(`/admin/${slug}`);
    await expect(page).toHaveURL(/\/admin\/login/);
    await expect(
      page.getByText("Dashboard Reviewer", { exact: true }),
    ).toHaveCount(0);
  }
  await page.evaluate(() => {
    localStorage.setItem("role", "ADMIN");
    localStorage.setItem(
      "admin",
      JSON.stringify({ role: "ADMIN", isAuthenticated: true }),
    );
  });
  await context.addCookies([
    {
      name: "roadrules_admin_ui",
      value: "forged-administrator-credential",
      domain: "127.0.0.1",
      path: "/admin",
    },
  ]);
  await page.goto("/admin/dashboard");
  await expect(page).toHaveURL(/\/admin\/login/);
  await context.clearCookies();
  expect((await page.request.get("/admin/analytics-api")).status()).toBe(401);
  await screenshot(page, info.project.name, "login");
});

test("login validation, real dashboard, all navigation, unavailable states and logout", async ({
  page,
  context,
}, info) => {
  await page.clock.install();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto("/admin/login");
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(
    page.getByText("Enter a valid administrator email.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Administrator email")).toBeFocused();
  await page.getByLabel("Administrator email").fill(fixture().email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("deliberately-incorrect");
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Unable to sign in" }),
  ).toContainText("Unable to sign in");
  await signIn(page);
  // "Total Students" is intentionally rendered twice: once as a headline
  // figure and once in the students detail section. Scope the assertion to the
  // first (headline) occurrence instead of relying on an ambiguous text match.
  const studentsHeadline = page
    .getByText("Total Students", { exact: true })
    .first()
    .locator("..");
  await expect(studentsHeadline.locator("dd").first()).toHaveText("1");
  await expect(
    page.getByText("Total Verified Revenue", { exact: true }).locator(".."),
  ).toContainText("Not Available");
  for (const period of ["Weekly", "Monthly", "Yearly", "Daily"]) {
    await page.getByRole("button", { name: period, exact: true }).click();
    await expect(
      page.getByText(`${period} · Africa/Kigali`, { exact: false }),
    ).toBeVisible();
  }
  await expect(page.locator("main time")).toBeVisible();
  await expect(page.locator("main meter")).toHaveCount(0);
  const refreshed = page.waitForResponse((response) =>
    response.url().endsWith("/admin/analytics-api?period=daily"),
  );
  await page.clock.fastForward(61000);
  expect((await refreshed).status()).toBe(200);
  await screenshot(page, info.project.name, "dashboard");
  await navigate(page, "System");
  await expect(
    page.getByRole("heading", { name: "System monitoring" }),
  ).toBeVisible();
  await expect(
    page.getByText("EXAM_BANK_UNAVAILABLE", { exact: true }),
  ).toBeVisible();
  await navigate(page, "Refunds");
  await expect(
    page.getByRole("heading", { name: "Refund requests" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "UNAVAILABLE" }),
  ).toBeVisible();
  await navigate(page, "PDF Uploads");
  await expect(
    page.getByRole("heading", { name: "PDF z’ibibazo", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Ohereza PDF", exact: true }),
  ).toBeEnabled();
  await expect(page.getByLabel("Dosiye ya PDF", { exact: true })).toBeVisible();
  await screenshot(page, info.project.name, "pdf");
  for (const [label, heading] of [
    ["Questions", "Questions"],
    ["Students", "Students"],
    ["Examinations", "Examinations"],
    ["Payments", "Payments"],
    ["Promo Codes", "Promo codes"],
    ["Settings", "Settings"],
  ]) {
    await navigate(page, label);
    await expect(
      page.getByRole("heading", { name: heading, exact: true, level: 1 }),
    ).toBeVisible();
    if (label === "Questions") {
      await expect(
        page.getByRole("heading", { name: "Automatic exam bank" }),
      ).toBeVisible();
      await expect(
        page
          .getByText("No exam-ready bank", { exact: true })
          .filter({ visible: true }),
      ).toBeVisible();
    } else if (label === "Examinations") {
      await expect(
        page.getByRole("heading", { name: "Timed examination activity" }),
      ).toBeVisible();
      await expect(
        page.getByText("Total attempts", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("heading", { name: "Recent examinations" }),
      ).toBeVisible();
      await expect(
        page.getByText("No examinations match these filters."),
      ).toBeVisible();
      await page.getByLabel("Statistics period").selectOption("weekly");
      await Promise.all([
        page.waitForEvent("load"),
        page.getByRole("button", { name: "Apply filters" }).click(),
      ]);
      await expect(page).toHaveURL(/period=weekly/);
      await expect(
        page.getByText("Total attempts", { exact: true }),
      ).toBeVisible();
      await screenshot(page, info.project.name, "exam-report");
    } else if (label === "Payments") {
      await expect(
        page.getByRole("heading", { name: "Development mock payments" }),
      ).toBeVisible();
    } else if (label === "Promo Codes") {
      const promoCode = `ROAD-UI-${Date.now()}`;
      await page.getByLabel("Promo code", { exact: true }).fill(promoCode);
      await page
        .getByRole("button", { name: "Generate / Publish code" })
        .click();
      await expect(
        page.getByText("Published promo code", { exact: true }),
      ).toBeVisible();
      await expect(page.getByRole("status").filter({ hasText: "Published promo code" }).getByText(promoCode, { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Hide code" }).click();
      const latest = page
        .getByRole("listitem")
        .filter({ hasText: "ACTIVE" })
        .first();
      await latest.getByRole("button", { name: "Redemption history" }).click();
      await expect(latest).toContainText("No redemptions.");
      await latest
        .getByRole("button", { name: "Disable", exact: true })
        .click();
      await expect(page.getByText("DISABLED · 0/1 used").first()).toBeVisible();
    } else {
      await expect(
        page
          .getByText("Feature unavailable", { exact: true })
          .filter({ visible: true }),
      ).toBeVisible();
    }
  }
  await navigate(page, "Dashboard");
  const cookies = await context.cookies();
  const cookie = cookies.find((item) => item.name === "roadrules_admin_ui");
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
  expect(cookie?.path).toBe("/admin");
  const open = page.getByRole("button", {
    name: "Open admin menu",
    exact: true,
  });
  if (await open.isVisible()) await open.click();
  await page.getByRole("button", { name: "Logout", exact: true }).click();
  await expect(page).toHaveURL(/\/admin\/login$/);
  expect(
    (await context.cookies()).some(
      (item) => item.name === "roadrules_admin_ui",
    ),
  ).toBe(false);
  await page.goto("/admin/dashboard");
  await expect(page).toHaveURL(/\/admin\/login/);
  expect(errors, "unexpected browser application errors").toEqual([]);
  await info.attach("browser-observations", {
    body: JSON.stringify({
      width: info.project.name,
      errors,
      realStudentCount: 1,
      unimplementedMetrics: "unavailable",
      cookieHttpOnly: true,
      logoutVerified: true,
    }),
    contentType: "application/json",
  });
});

test("server expiration overrides an existing browser cookie", async ({
  page,
}) => {
  await signIn(page);
  execFileSync(
    resolve("backend/.venv/Scripts/python.exe"),
    ["-m", "scripts.admin_browser_fixture", "expire"],
    { cwd: resolve("backend"), stdio: "pipe", windowsHide: true },
  );
  await page.goto("/admin/settings");
  await expect(page).toHaveURL(/\/admin\/login/);
  await expect(
    page.getByText("Dashboard Reviewer", { exact: true }),
  ).toHaveCount(0);
});

test("private PDF upload, source-backed draft and duplicate recovery", async ({
  page,
  context,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("422"))
      errors.push(message.text());
  });
  expect(
    (await context.request.get("/admin/pdf-api/pdf-documents")).status(),
  ).toBe(401);
  await signIn(page);
  await navigate(page, "PDF Uploads");
  const input = page.getByLabel("Dosiye ya PDF", { exact: true });
  const button = page.getByRole("button", { name: "Ohereza PDF", exact: true });
  await input.setInputFiles({
    name: "invalid-synthetic.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("invalid"),
  });
  await button.click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Iyi dosiye si PDF nzima." }),
  ).toBeVisible();
  const fixtureFile = {
    name: `synthetic-${info.project.name}.pdf`,
    mimeType: "application/pdf",
    buffer: Buffer.concat([
      readFileSync("backend/.local/admin-browser-synthetic.pdf"),
      Buffer.from(`\n% viewport ${info.project.name}\n`),
    ]),
  };
  await input.setInputFiles(fixtureFile);
  await button.click();
  await expect(
    page.getByText("PDF yabitswe.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Itegereje umukozi wo gutunganya PDF.", { exact: false }),
  ).toBeVisible();
  execFileSync(
    resolve("backend/.venv/Scripts/python.exe"),
    ["-m", "scripts.admin_browser_fixture", "drain"],
    { cwd: resolve("backend"), stdio: "pipe", windowsHide: true },
  );
  await expect(
    page.getByRole("heading", {
      name: "Ibibazo byasomwe (2)",
      exact: true,
    }),
  ).toBeVisible();
  const draft = page.getByRole("article").filter({
    has: page.getByRole("heading", { name: "Ikibazo 1", exact: true }),
  });
  await expect(draft).toContainText("Uyu ni umurongo wa kabiri.");
  await expect(draft).toContainText("Inyuguti yasomwe: A");
  await expect(draft.getByRole("img")).toHaveCount(2);
  await draft
    .getByRole("button", { name: /Reba urupapuro rw’umwimerere/ })
    .click();
  const preview = draft.getByRole("img", { name: "Urupapuro rw’umwimerere 1" });
  await expect
    .poll(() => preview.evaluate((node: HTMLImageElement) => node.naturalWidth))
    .toBeGreaterThan(0);
  await expect
    .poll(() =>
      draft
        .getByRole("img")
        .evaluateAll((nodes) =>
          nodes.every((node) => (node as HTMLImageElement).naturalWidth > 0),
        ),
    )
    .toBe(true);
  await screenshot(page, info.project.name, "draft-preview");
  const imagePath = await preview.getAttribute("src");
  expect(imagePath).toBeTruthy();
  const answerPageResponse = page.waitForResponse((response) =>
    response.url().endsWith("/pages/3"),
  );
  await draft
    .getByRole("button", { name: /Reba urupapuro rw’igisubizo/ })
    .click();
  expect((await answerPageResponse).status()).toBe(200);
  await expect(
    draft.getByRole("img", { name: "Urupapuro rw’umwimerere 3" }),
  ).toBeVisible();
  await input.setInputFiles(fixtureFile);
  await button.click();
  await expect(
    page.getByText("Iyi PDF yari isanzwe ihari; nta yindi yakozwe.", {
      exact: true,
    }),
  ).toBeVisible();
  const csrf = await context.request.post("/admin/pdf-api/pdf-documents", {
    headers: {
      Origin: "https://evil.example",
      "Content-Type": "application/pdf",
    },
    data: "invalid",
  });
  expect(csrf.status()).toBe(403);
  await navigate(page, "Questions");
  const source = page
    .getByRole("listitem")
    .filter({ hasText: fixtureFile.name });
  await expect(source).toContainText("Insufficient question mix");
  await expect(
    source
      .getByText("Eligible", { exact: true })
      .locator("..")
      .getByText("2", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByText("No exam-ready bank", { exact: true })
      .filter({ visible: true }),
  ).toBeVisible();
  await screenshot(page, info.project.name, "exam-bank");
  await context.clearCookies();
  expect((await context.request.get(imagePath!)).status()).toBe(401);
  expect(errors).toEqual([]);
});
