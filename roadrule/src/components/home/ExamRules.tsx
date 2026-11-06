import { TimerOff } from "lucide-react";

import Container from "@/components/ui/Container";
import { EXAM_RULES, EXAM_SUMMARY } from "@/lib/constants";

/**
 * Compact "Exam rules" — same two-color style as the other sections:
 *  - brand-800 → design (bars, numbers, icons)
 *  - ink       → writing
 * Short on purpose: one heading, one summary row, titles only.
 */
export default function ExamRules() {
  return (
    <section
      id="amategeko"
      aria-labelledby="exam-rules-heading"
      className="border-b-4 border-brand-800 bg-white py-12 sm:py-16"
    >
      <Container>
        {/* Heading */}
        <div className="mx-auto max-w-2xl text-center">
          <div className="mx-auto flex max-w-xs items-center gap-4">
            <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
              Amategeko
            </p>
            <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
          </div>

          <h2
            id="exam-rules-heading"
            className="mt-6 text-balance font-display text-2xl font-bold leading-tight tracking-tight text-ink sm:text-3xl lg:text-4xl"
          >
            Amategeko ni imwe kuri bose.
          </h2>
        </div>

        {/* Summary — one compact row */}
        <dl className="mx-auto mt-10 grid max-w-3xl grid-cols-3 gap-6 text-center">
          {EXAM_SUMMARY.map(({ label, value }) => (
            <div key={label}>
              <dd className="font-display text-4xl font-bold leading-none tracking-tighter text-brand-800 sm:text-5xl">
                {value}
              </dd>
              <div
                className="mx-auto mt-3 h-1 w-10 bg-brand-800"
                aria-hidden="true"
              />
              <dt className="mt-3 text-sm font-medium text-ink">{label}</dt>
            </div>
          ))}
        </dl>

        {/* Rules — titles only */}
        <ol className="mx-auto mt-10 grid max-w-4xl gap-x-10 gap-y-4 sm:grid-cols-2">
          {EXAM_RULES.map((rule, index) => {
            const Icon = rule.icon;

            return (
              <li key={rule.title} className="flex items-center gap-3">
                <span
                  className="font-display text-xl font-bold text-brand-800"
                  aria-hidden="true"
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
                <Icon
                  className="size-5 shrink-0 text-brand-800"
                  strokeWidth={1.75}
                  aria-hidden="true"
                />
                <span className="text-base font-semibold text-ink">
                  {rule.title}
                </span>
              </li>
            );
          })}
        </ol>

        {/* One-line time warning */}
        <p className="mx-auto mt-10 flex max-w-2xl items-center justify-center gap-2 text-center text-sm font-semibold text-ink">
          <TimerOff
            className="size-4 shrink-0 text-brand-800"
            aria-hidden="true"
          />
          Iminota 18 nimara kwita, igihe gihinduka umutuku.
        </p>
      </Container>
    </section>
  );
}