import { ArrowRight, BookOpenCheck } from "lucide-react";

import ButtonLink from "@/components/ui/ButtonLink";
import Container from "@/components/ui/Container";
import { ROUTES } from "@/lib/constants";

/**
 * Compact "Final CTA" — same two-color style as the other sections:
 *  - brand-800 → design (rules, buttons)
 *  - ink       → writing
 */
export default function FinalCTA() {
  return (
    <section
      aria-labelledby="final-cta-heading"
      className="border-b-4 border-brand-800 bg-white py-14 text-center sm:py-20"
    >
      <Container>
        <div className="mx-auto flex max-w-xs items-center gap-4">
          <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
            Intambwe ikurikira
          </p>
          <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
        </div>

        <h2
          id="final-cta-heading"
          className="mx-auto mt-6 max-w-3xl text-balance font-display text-3xl font-bold leading-tight tracking-tight text-ink sm:text-4xl lg:text-5xl"
        >
          Witeguye kwiga amategeko y&apos;umuhanda?
        </h2>

        <div
          className="mx-auto mt-6 h-1 w-16 bg-brand-800"
          aria-hidden="true"
        />

        <p className="mx-auto mt-6 max-w-xl text-base leading-7 text-ink sm:text-lg">
          Iminota 20, ibibazo 20, n&apos;ibisubizo ako kanya.
        </p>

        <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <ButtonLink
            href={ROUTES.start}
            size="lg"
            icon={ArrowRight}
            ariaLabel="Tangira ikizamini"
            className="rounded-none border border-brand-800 bg-brand-800 text-white hover:bg-white hover:text-brand-800"
          >
            Tangira Ikizamini
          </ButtonLink>
          <ButtonLink
            href={ROUTES.howItWorks}
            variant="secondary"
            size="lg"
            icon={BookOpenCheck}
            className="rounded-none border border-brand-800 bg-white text-ink hover:bg-brand-800 hover:text-white"
          >
            Reba uko bikora
          </ButtonLink>
        </div>
      </Container>
    </section>
  );
}