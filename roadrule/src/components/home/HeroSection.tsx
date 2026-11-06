import { ArrowDown, ArrowRight } from "lucide-react";

import ButtonLink from "@/components/ui/ButtonLink";
import Container from "@/components/ui/Container";
import { ROUTES, TRUST_POINTS } from "@/lib/constants";

/**
 * Classic hero — two colors only:
 *  - brand-800 → every design element (rules, buttons, icons, borders)
 *  - ink       → every piece of writing
 */
export default function HeroSection() {
  return (
    <section
      id="ahabanza"
      aria-labelledby="hero-heading"
      className="border-b-4 border-brand-800 bg-white"
    >
      <Container className="py-20 text-center sm:py-24 lg:py-32">
        {/* Eyebrow with classic double rule */}
        <div className="mx-auto flex max-w-md items-center gap-4">
          <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
            Ikizamini cy&apos;amategeko · U Rwanda
          </p>
          <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
        </div>

        <h1
          id="hero-heading"
          className="mx-auto mt-10 max-w-4xl text-balance font-display text-4xl font-bold leading-[1.1] tracking-tight text-ink sm:text-5xl lg:text-6xl"
        >
          Witegure ikizamini cy&apos;amategeko y&apos;umuhanda mu Rwanda.
        </h1>

        {/* Short ornamental rule */}
        <div
          className="mx-auto mt-8 h-1 w-20 bg-brand-800"
          aria-hidden="true"
        />

        <p className="mx-auto mt-8 max-w-2xl text-pretty text-base leading-8 text-ink sm:text-lg">
          Ntuzakenera konti. Uzatangira utanga amazina yawe na nimero ya
          telefoni, wishyure ukoresheje MTN MoMo cyangwa Airtel Money, cyangwa
          ukoreshe kode y&apos;ubusonerwe, hanyuma utangire ikizamini
          cy&apos;iminota 20.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
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
            icon={ArrowDown}
            className="rounded-none border border-brand-800 bg-white text-ink hover:bg-brand-800 hover:text-white"
          >
            Uko Bikora
          </ButtonLink>
        </div>

        <p className="mt-6 text-sm text-ink">
          Ikizamini gisaba uruhushya rwemejwe. Nta mafaranga nyayo yishyurwa.
        </p>

        {/* Trust points — ruled strip */}
        <ul className="mx-auto mt-16 grid max-w-4xl grid-cols-2 border-y border-brand-800 sm:grid-cols-4">
          {TRUST_POINTS.map(({ icon: Icon, label }) => (
            <li
              key={label}
              className="flex items-center justify-center gap-2 border-brand-800 px-4 py-5 text-sm font-medium text-ink sm:border-r sm:last:border-r-0"
            >
              <Icon
                className="size-4 shrink-0 text-brand-800"
                aria-hidden="true"
              />
              <span>{label}</span>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}