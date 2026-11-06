"use client";

import { useEffect, useState } from "react";
import { ArrowRight, CircleCheck, CircleX, Home } from "lucide-react";

import ButtonLink from "@/components/ui/ButtonLink";
import Container from "@/components/ui/Container";
import { accessRequest } from "@/features/onboarding/access-client";

type Result = {
  studentName: string;
  completedAt: string;
  correct: number;
  incorrect: number;
  unanswered: number;
  score: number;
  total: number;
  percentage: number;
  status: "PASSED" | "FAILED";
};

const dateFormat = new Intl.DateTimeFormat("rw-RW", {
  dateStyle: "long",
  timeStyle: "short",
  timeZone: "Africa/Kigali",
});

/**
 * Classic result page — same two-color style as the rest of the site:
 *  - brand-800 → design (rules, numbers, icons, buttons)
 *  - ink       → writing
 * Passed / failed is shown with an icon and text, not green / amber.
 */
export default function ResultPanel({ attemptId }: { attemptId: string }) {
  const [state, setState] = useState<Result | string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    accessRequest<Result>(
      `exams/${encodeURIComponent(attemptId)}/result`,
      undefined,
      controller.signal,
    )
      .then(setState)
      .catch((error: Error) => {
        if (!controller.signal.aborted) setState(error.message);
      });
    return () => controller.abort();
  }, [attemptId]);

  const result = typeof state === "object" ? state : null;
  const passed = result?.status === "PASSED";
  const StatusIcon = passed ? CircleCheck : CircleX;

  return (
    <Container className="py-14 sm:py-20">
      <section
        aria-labelledby="result-heading"
        className="mx-auto max-w-3xl border-y-4 border-brand-800 bg-white px-4 py-12 text-center sm:px-10 sm:py-16"
      >
        <div className="mx-auto flex max-w-xs items-center gap-4">
          <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
            Ibisubizo
          </p>
          <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
        </div>

        <h1
          id="result-heading"
          className="mt-6 text-balance font-display text-3xl font-bold leading-tight tracking-tight text-ink sm:text-4xl"
        >
          Ibisubizo by’ikizamini
        </h1>

        {typeof state === "string" && (
          <p
            role="alert"
            className="mt-8 border border-brand-800 px-5 py-4 text-sm font-semibold text-ink"
          >
            {state}
          </p>
        )}
        {state === null && (
          <p role="status" className="mt-8 text-base font-medium text-ink">
            Turimo gushaka ibisubizo…
          </p>
        )}

        {result && (
          <>
            <div
              className="mx-auto mt-6 h-1 w-16 bg-brand-800"
              aria-hidden="true"
            />

            <p className="mt-6 font-display text-xl font-bold text-ink">
              {result.studentName}
            </p>
            <p className="mt-2 text-sm text-ink">
              Ikizamini cyarangiye ku wa{" "}
              {dateFormat.format(new Date(result.completedAt))}.
            </p>

            {/* Score */}
            <p className="mt-10 font-display text-7xl font-bold leading-none tracking-tighter text-brand-800 tabular-nums sm:text-8xl">
              {result.score}/{result.total}
            </p>
            <p className="mt-3 text-lg font-semibold text-ink">
              {result.percentage}%
            </p>

            {/* Status */}
            <p
              role="status"
              className="mx-auto mt-8 flex max-w-md items-center justify-center gap-3 border border-brand-800 px-5 py-4 text-base font-bold text-ink"
            >
              <StatusIcon
                className="size-6 shrink-0 text-brand-800"
                aria-hidden="true"
              />
              {passed
                ? "Congratulations! Watsinze ikizamini."
                : "Ntabwo watsinze ikizamini. Ushobora kongera kugerageza."}
            </p>

            {/* Breakdown */}
            <dl className="mt-12 grid gap-8 sm:grid-cols-3">
              {[
                ["Ibyo wasubije neza", result.correct],
                ["Ibyo wasubije nabi", result.incorrect],
                ["Ibyo utasubije", result.unanswered],
              ].map(([label, count]) => (
                <div key={label} className="flex flex-col items-center">
                  <dd className="font-display text-5xl font-bold leading-none tracking-tighter text-brand-800 tabular-nums">
                    {count}
                  </dd>
                  <div
                    className="mt-4 h-1 w-10 bg-brand-800"
                    aria-hidden="true"
                  />
                  <dt className="mt-3 text-sm font-semibold text-ink">
                    {label}
                  </dt>
                </div>
              ))}
            </dl>
          </>
        )}

        {/* Actions */}
        <div className="mt-12 flex flex-col items-center justify-center gap-4 sm:flex-row">
          {result && (
            <ButtonLink
              href="/tangira?retake=1"
              size="lg"
              icon={ArrowRight}
              className="rounded-none border border-brand-800 bg-brand-800 text-white hover:bg-white hover:text-brand-800"
            >
              {passed ? "Ongera ugerageze" : "Pay to Try Again"}
            </ButtonLink>
          )}
          <ButtonLink
            href="/"
            variant="secondary"
            size="lg"
            icon={Home}
            className="rounded-none border border-brand-800 bg-white text-ink hover:bg-brand-800 hover:text-white"
          >
            Subira ahabanza
          </ButtonLink>
        </div>
      </section>
    </Container>
  );
}