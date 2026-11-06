import { BadgeCheck } from "lucide-react";

import Container from "@/components/ui/Container";
import { HOW_IT_WORKS_STEPS } from "@/lib/constants";

/**
 * Classic "How it works" — matches HeroSection:
 *  - brand-800 → every design element (bars, numbers, icons)
 *  - ink       → every piece of writing
 * No table/grid lines: steps sit in open space, each marked by a short bar.
 */
export default function HowItWorks() {
  return (
    <section
      id="uko-bikora"
      aria-labelledby="how-it-works-heading"
      className="border-b-4 border-brand-800 bg-white py-20 sm:py-24 lg:py-32"
    >
      <Container>
        {/* Heading */}
        <div className="mx-auto max-w-3xl text-center">
          <div className="mx-auto flex max-w-xs items-center gap-4">
            <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
              Uko bikora
            </p>
            <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
          </div>

          <h2
            id="how-it-works-heading"
            className="mt-10 text-balance font-display text-3xl font-bold leading-[1.15] tracking-tight text-ink sm:text-4xl lg:text-5xl"
          >
            Mu ntambwe enye, uva ku kwiyandikisha ukagera ku bisubizo.
          </h2>

          <p className="mx-auto mt-6 max-w-2xl text-pretty text-base leading-8 text-ink sm:text-lg">
            Nta konti, nta email. Uzuza amakuru y&apos;ibanze, wishyure ku
            telefoni yawe, hanyuma utangire ikizamini.
          </p>
        </div>

        {/* Steps — open layout, no borders */}
        <ol className="mt-16 grid gap-x-12 gap-y-14 sm:grid-cols-2 lg:mt-20 xl:grid-cols-4">
          {HOW_IT_WORKS_STEPS.map(
            ({ number, title, description, icon: Icon, hint }) => (
              <li key={number} className="flex flex-col">
                <div className="flex items-end justify-between gap-4">
                  <span
                    className="font-display text-6xl font-bold leading-none tracking-tighter text-brand-800 sm:text-7xl"
                    aria-hidden="true"
                  >
                    {number}
                  </span>
                  <Icon
                    className="mb-1 size-7 text-brand-800"
                    strokeWidth={1.5}
                    aria-hidden="true"
                  />
                </div>

                <div
                  className="mt-5 h-1 w-14 bg-brand-800"
                  aria-hidden="true"
                />

                <h3 className="mt-6 font-display text-xl font-bold leading-snug text-ink">
                  {title}
                </h3>
                <p className="mt-3 flex-1 text-base leading-7 text-ink">
                  {description}
                </p>

                {hint ? (
                  <p className="mt-5 flex items-center gap-2 text-sm font-semibold text-ink">
                    <BadgeCheck
                      className="size-4 shrink-0 text-brand-800"
                      aria-hidden="true"
                    />
                    {hint}
                  </p>
                ) : null}
              </li>
            ),
          )}
        </ol>

        {/* Notice */}
        <div className="mx-auto mt-20 flex max-w-3xl flex-col items-center gap-3 text-center">
          <BadgeCheck
            className="size-6 text-brand-800"
            aria-hidden="true"
          />
          <p className="text-base leading-7 text-ink">
            <strong className="font-semibold">
              Nta konti cyangwa email bisabwa.
            </strong>{" "}
            Amazina yawe na nimero ya telefoni ni byo bikoreshwa mu
            kwiyandikisha.
          </p>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
            Ifishi iri kuza
          </p>
        </div>
      </Container>
    </section>
  );
}