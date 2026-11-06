import { LockKeyhole } from "lucide-react";

import Container from "@/components/ui/Container";
import { PAYMENT_METHODS, PAYMENT_STEPS } from "@/lib/constants";

/**
 * Compact "Payment information" — same two-color style as the other sections:
 *  - brand-800 → design (bars, numbers, icons)
 *  - ink       → writing
 * Short on purpose: no intro paragraph, no step descriptions.
 */
export default function PaymentInformation() {
  return (
    <section
      id="ishyura"
      aria-labelledby="payment-heading"
      className="border-b-4 border-brand-800 bg-white py-12 sm:py-16"
    >
      <Container>
        {/* Heading */}
        <div className="mx-auto max-w-2xl text-center">
          <div className="mx-auto flex max-w-xs items-center gap-4">
            <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
              Kwishyura
            </p>
            <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
          </div>

          <h2
            id="payment-heading"
            className="mt-6 text-balance font-display text-2xl font-bold leading-tight tracking-tight text-ink sm:text-3xl lg:text-4xl"
          >
            Ishyura ukoresheje telefoni yawe.
          </h2>
        </div>

        {/* Payment methods — icon + name only */}
        <div className="mx-auto mt-10 grid max-w-4xl gap-8 sm:grid-cols-3">
          {PAYMENT_METHODS.map((method) => {
            const Icon = method.icon;

            return (
              <div
                key={method.name}
                className="flex flex-col items-center text-center"
              >
                <Icon
                  className="size-8 text-brand-800"
                  strokeWidth={1.5}
                  aria-hidden="true"
                />
                <div
                  className="mt-4 h-1 w-10 bg-brand-800"
                  aria-hidden="true"
                />
                <h3 className="mt-4 font-display text-xl font-bold text-ink">
                  {method.name}
                </h3>
                <p className="mt-1 text-xs font-semibold uppercase tracking-[0.2em] text-ink">
                  {method.label}
                </p>
              </div>
            );
          })}
        </div>

        {/* Steps — number + title only */}
        <ol className="mx-auto mt-10 grid max-w-3xl gap-4 sm:grid-cols-3 sm:gap-8">
          {PAYMENT_STEPS.map((step, index) => (
            <li key={step.title} className="flex items-center gap-3">
              <span
                className="font-display text-3xl font-bold text-brand-800"
                aria-hidden="true"
              >
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="text-base font-semibold text-ink">
                {step.title}
              </span>
            </li>
          ))}
        </ol>

        {/* One-line PIN notice */}
        <p className="mx-auto mt-10 flex max-w-2xl items-center justify-center gap-2 text-center text-sm font-semibold text-ink">
          <LockKeyhole
            className="size-4 shrink-0 text-brand-800"
            aria-hidden="true"
          />
          Ntitukusaba PIN yawe. Ubwishyu buzatangira vuba.
        </p>
      </Container>
    </section>
  );
}