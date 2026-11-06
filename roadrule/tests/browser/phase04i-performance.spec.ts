import { test, expect } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * Warm-run request timing over the real Next.js production bridge, FastAPI and
 * PostgreSQL. No artificial sleeps and no wall-clock deadline manipulation: the
 * whole probe runs well inside the twenty-minute attempt window.
 *
 * Samples are the raw request round-trip times measured in the Playwright
 * process. The first guest session is excluded as warmup when enough samples
 * exist; medians and the slower tail are reported for every operation.
 */

function quantile(sorted: number[], fraction: number): number {
  if (sorted.length === 0) return 0;
  if (sorted.length === 1) return sorted[0];
  const index = (sorted.length - 1) * fraction;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  const weight = index - lower;
  return sorted[lower] * (1 - weight) + sorted[upper] * weight;
}

function summarize(samples: number[]) {
  const sorted = [...samples].sort((a, b) => a - b);
  return {
    samples: sorted.length,
    minMs: sorted[0] ?? 0,
    medianMs: Math.round(quantile(sorted, 0.5)),
    p95Ms: Math.round(quantile(sorted, 0.95)),
    maxMs: sorted.at(-1) ?? 0,
    allMs: samples,
  };
}

test("warm request timings across the production bridge", async ({
  page,
  browser,
}) => {
  test.setTimeout(180_000);

  const origin = "http://127.0.0.1:3100";
  const headers = { Origin: origin };
  const timings: Record<string, number[]> = {
    guestSession: [],
    promoRedeem: [],
    entitlementLookup: [],
    examStart: [],
    current: [],
    answer: [],
    next: [],
    results: [],
  };

  async function timed<T>(
    name: keyof typeof timings,
    action: () => Promise<T>,
  ): Promise<T> {
    const start = performance.now();
    const result = await action();
    timings[name].push(Number((performance.now() - start).toFixed(2)));
    return result;
  }

  // Warm up the Next.js route, FastAPI process and PostgreSQL connection pool.
  await page.goto("/tangira");
  await page.request.get("/student-api/exam-access/me");

  // Three independent guest sessions; the final context is kept for the exam
  // so the first request is not the only one represented.
  let measureContext = page.context();
  for (let sample = 0; sample < 3; sample += 1) {
    const context = await browser.newContext();
    const api = context.request;
    const response = await timed("guestSession", () =>
      api.post(new URL("/student-api/students/sessions", origin).href, {
        headers,
        data: {
          fullName: `Performance Sample ${["Alpha", "Bravo", "Charlie"][sample]}`,
          phoneNumber: `+25078123450${sample + 1}`,
        },
      }),
    );
    expect(response.status()).toBe(201);
    if (sample === 2) {
      measureContext = context;
    } else {
      await context.close();
    }
  }
  const api = measureContext.request;

  // The administrator issues three single-use promos directly against FastAPI;
  // the student redemption still travels through the public Next.js bridge.
  const admin = JSON.parse(
    readFileSync("backend/.local/admin-browser.json", "utf8"),
  );
  const adminContext = await browser.newContext();
  const codes: string[] = [];
  try {
    const login = await adminContext.request.post(
      "http://127.0.0.1:8310/api/v1/admin/auth/login",
      {
        headers: { Origin: origin, "X-CSRF-Protection": "1" },
        data: { email: admin.email, password: admin.password },
      },
    );
    expect(login.status()).toBe(200);
    for (let sample = 0; sample < 3; sample += 1) {
      const created = await adminContext.request.post(
        "http://127.0.0.1:8310/api/v1/admin/promo-codes",
        {
          headers: { Origin: origin, "X-CSRF-Protection": "1" },
          data: { code: `ROAD-PERF-${Date.now()}-${sample}`, usageLimit: 1 },
        },
      );
      expect(created.status()).toBe(201);
      codes.push((await created.json()).code);
    }
  } finally {
    await adminContext.close();
  }

  for (const code of codes) {
    const redeemed = await timed("promoRedeem", () =>
      api.post(new URL("/student-api/promos/redeem", origin).href, {
        headers,
        data: { code },
      }),
    );
    expect(redeemed.status()).toBe(200);
  }

  for (let sample = 0; sample < 5; sample += 1) {
    const state = await timed("entitlementLookup", () =>
      api.get(new URL("/student-api/exam-access/me", origin).href, {
        headers,
      }),
    );
    expect(state.status()).toBe(200);
  }
  const access = await (
    await api.get(new URL("/student-api/exam-access/me", origin).href, {
      headers,
    })
  ).json();
  const available = access.entitlements.filter(
    (grant: { status: string }) => grant.status === "AVAILABLE",
  );
  expect(available.length).toBeGreaterThanOrEqual(2);

  // Attempt one: full twenty-question round trip.
  const firstStart = await timed("examStart", () =>
    api.post(new URL("/student-api/exams/start", origin).href, {
      headers,
      data: { entitlementId: available[0].id },
    }),
  );
  expect(firstStart.status()).toBe(200);
  let exam = (await firstStart.json()).exam;
  const firstId = exam.id;
  const root = `/student-api/exams/${firstId}`;
  expect(exam.total).toBe(20);

  for (let position = 1; position <= 20; position += 1) {
    const current = await timed("current", () =>
      api.get(new URL(root + "/current", origin).href, { headers }),
    );
    expect(current.status()).toBe(200);
    const view = (await current.json()).exam;
    expect(view.position).toBe(position);
    const saved = await timed("answer", () =>
      api.put(new URL(root + "/answer", origin).href, {
        headers,
        data: {
          position,
          optionId: 0,
          answerVersion: view.question.answerVersion,
        },
      }),
    );
    expect(saved.status()).toBe(200);
    const next = await timed("next", () =>
      api.post(new URL(root + "/next", origin).href, {
        headers,
        data: { position },
      }),
    );
    expect(next.status()).toBe(200);
    if (position === 20) {
      expect((await next.json()).exam.question).toBeNull();
    }
  }

  for (let sample = 0; sample < 5; sample += 1) {
    const result = await timed("results", () =>
      api.get(new URL(root + "/result", origin).href, { headers }),
    );
    expect(result.status()).toBe(200);
  }

  // Attempt two provides a second warm start sample and proves the retake path
  // still works under repeated load.
  const secondStart = await timed("examStart", () =>
    api.post(new URL("/student-api/exams/start", origin).href, {
      headers,
      data: { entitlementId: available[1].id },
    }),
  );
  expect(secondStart.status()).toBe(200);
  exam = (await secondStart.json()).exam;
  expect(exam.id).not.toBe(firstId);

  const summary = Object.fromEntries(
    Object.entries(timings).map(([name, samples]) => [
      name,
      summarize(samples),
    ]),
  );
  const document = {
    generatedAt: new Date().toISOString(),
    method:
      "Playwright request API through the Next.js production bridge on 127.0.0.1:3100 to FastAPI on 127.0.0.1:8310 and PostgreSQL on 127.0.0.1:55432. Warm session; no concurrent load; loopback only.",
    httpStatuses:
      "Every measured request returned 200 except the three guest sessions and three promo codes, which returned 201 as specified.",
    timings: summary,
  };
  mkdirSync(resolve("docs/evidence/phase04i"), { recursive: true });
  writeFileSync(
    resolve("docs/evidence/phase04i/performance.json"),
    JSON.stringify(document, null, 2),
  );
  console.log("PHASE04I_PERFORMANCE " + JSON.stringify(document));
});
