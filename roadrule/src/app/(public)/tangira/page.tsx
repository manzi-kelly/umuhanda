import type { Metadata } from "next";
import Link from "next/link";
import Container from "@/components/ui/Container";
import OnboardingFlow from "@/features/onboarding/OnboardingFlow";

export const metadata: Metadata = {
  title: "Amakuru y’umunyeshuri n’ubwishyu",
  description: "Andika amazina yawe na telefoni, uhitemo uburyo bwo kwishyura. Koresha kode cyangwa uburyo bw’igerageza igihe bwafunguwe.",
};

export default function StartPage() {
  return (
    <div className="relative overflow-hidden">
      <div className="pattern-grid pointer-events-none absolute inset-0 opacity-60" aria-hidden="true" />
      <Container className="relative py-12 sm:py-20">
        <div className="mx-auto max-w-3xl">
          <Link href="/" className="rounded text-sm font-semibold text-brand-700">← Subira ahabanza</Link>
          <div className="mt-6 overflow-hidden rounded-[2rem] border border-ink/10 bg-surface shadow-card">
            <div className="h-1.5 bg-linear-to-r from-brand-700 via-accent-400 to-brand-700" aria-hidden="true" />
            <div className="p-5 sm:p-10"><OnboardingFlow /></div>
          </div>
          <p className="mt-6 text-center text-sm text-ink-muted">Seriveri ibika igihe cyawe cyo gukoresha serivisi n’uruhushya rw’ikizamini.</p>
        </div>
      </Container>
    </div>
  );
}
