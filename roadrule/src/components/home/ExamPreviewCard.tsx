import { CheckCircle2, Clock3, Timer } from "lucide-react";

import { cn } from "@/lib/cn";

const PREVIEW_OPTIONS = [
  { letter: "A", text: "Guhagarara", selected: true },
  { letter: "B", text: "Kugenda buhoro", selected: false },
  { letter: "C", text: "Kudahagarara", selected: false },
  { letter: "D", text: "Guhindura umurongo", selected: false },
] as const;

export default function ExamPreviewCard() {
  return (
    <figure
      className="relative mx-auto w-full max-w-[34rem]"
      aria-labelledby="exam-preview-caption"
    >
      <div
        className="absolute -inset-6 rounded-[3rem] bg-linear-to-br from-brand-200/60 via-transparent to-accent-200/50 blur-2xl"
        aria-hidden="true"
      />

      <div className="relative rounded-[2.25rem] border border-white/80 bg-surface/85 p-2.5 shadow-card backdrop-blur">
        <div className="rounded-[1.75rem] border border-ink/10 bg-white p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-brand-700/15 bg-brand-50 px-3 py-1.5 text-[0.6rem] font-bold uppercase tracking-[0.16em] text-brand-800">
              <span
                className="size-1.5 rounded-full bg-brand-600"
                aria-hidden="true"
              />
              Urugero gusa
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3 py-1.5 text-xs font-semibold tabular-nums text-white">
              <Clock3 className="size-3.5" aria-hidden="true" />
              19:42
            </span>
          </div>

          <div className="mt-5 flex items-center justify-between text-[0.62rem] font-bold uppercase tracking-[0.14em] text-ink-muted">
            <span>Ikibazo 08 / 20</span>
            <span>40%</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ink/10">
            <div className="h-full w-2/5 rounded-full bg-brand-600" />
          </div>

          <p className="mt-6 text-[0.62rem] font-bold uppercase tracking-[0.18em] text-brand-700">
            Amategeko y&apos;umuhanda
          </p>
          <h3 className="mt-2 text-balance font-display text-lg font-bold leading-7 text-ink sm:text-xl">
            Icyapa cy&apos;umuhanda gitukura gisobanura iki?
          </h3>

          <ul className="mt-5 space-y-2.5">
            {PREVIEW_OPTIONS.map((option) => (
              <li
                key={option.letter}
                className={cn(
                  "flex items-center gap-3 rounded-xl border px-3.5 py-3 text-sm transition-colors",
                  option.selected
                    ? "border-brand-600 bg-brand-50 font-semibold text-brand-950"
                    : "border-ink/10 bg-canvas/60 text-ink-soft",
                )}
              >
                <span
                  className={cn(
                    "grid size-6 shrink-0 place-items-center rounded-lg text-[0.62rem] font-bold",
                    option.selected
                      ? "bg-brand-700 text-white"
                      : "bg-ink/5 text-ink-muted",
                  )}
                  aria-hidden="true"
                >
                  {option.letter}
                </span>
                <span>{option.text}</span>
                {option.selected ? (
                  <CheckCircle2
                    className="ml-auto size-4 shrink-0 text-brand-700"
                    aria-hidden="true"
                  />
                ) : null}
              </li>
            ))}
          </ul>

          <div className="mt-5 flex items-start gap-2 rounded-xl bg-canvas p-3 text-[0.7rem] leading-5 text-ink-muted">
            <Timer
              className="mt-0.5 size-3.5 shrink-0 text-brand-700"
              aria-hidden="true"
            />
            <p>
              Igihe kirangiye, sisitemu yimuka ku kibazo gikurikira. Nta gusubira
              inyuma.
            </p>
          </div>
        </div>
      </div>

      <div
        className="absolute -right-3 top-24 hidden items-center gap-2.5 rounded-2xl border border-ink/10 bg-white px-4 py-3 shadow-card sm:flex"
        aria-hidden="true"
      >
        <span className="grid size-8 place-items-center rounded-xl bg-brand-50 text-brand-700">
          <Timer className="size-4" />
        </span>
        <div>
          <p className="text-[0.55rem] font-bold uppercase tracking-[0.14em] text-ink-muted">
            Igihe
          </p>
          <p className="text-sm font-bold text-ink">Iminota 20</p>
        </div>
      </div>

      <div
        className="absolute -bottom-5 -left-3 hidden items-center gap-2.5 rounded-2xl border border-ink/10 bg-white px-4 py-3 shadow-card sm:flex"
        aria-hidden="true"
      >
        <span className="grid size-8 place-items-center rounded-xl bg-accent-100 text-accent-700">
          <CheckCircle2 className="size-4" />
        </span>
        <div>
          <p className="text-[0.55rem] font-bold uppercase tracking-[0.14em] text-ink-muted">
            Nyuma y&apos;ikizamini
          </p>
          <p className="text-sm font-bold text-ink">Ibisubizo ako kanya</p>
        </div>
      </div>

      <figcaption id="exam-preview-caption" className="sr-only">
        Urugero rw&apos;ikizamini: ikibazo, amahitamo n&apos;igihe. Iri ni
        urugero gusa, nta kizamini gitangira kuri iyi paji.
      </figcaption>
    </figure>
  );
}
