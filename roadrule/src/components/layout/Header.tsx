import Link from "next/link";
import { ArrowRight } from "lucide-react";

import Container from "@/components/ui/Container";
import Logo from "@/components/ui/Logo";
import { NAV_LINKS, ROUTES } from "@/lib/navigation";
import MobileNav from "./MobileNav";

/**
 * Classic header — same two-color style as the other sections:
 *  - brand-800 → design (rules, button)
 *  - ink       → writing
 */
export default function Header() {
  return (
    <header className="sticky top-0 z-50 border-b-4 border-brand-800 bg-white">
      <Container className="flex h-20 items-center justify-between gap-4">
        <Logo />

        <nav
          aria-label="Menyu nyamukuru"
          className="hidden items-center gap-8 lg:flex"
        >
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-semibold text-ink underline-offset-8 decoration-2 decoration-brand-800 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-800"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden lg:flex">
          <Link
            href={ROUTES.start}
            aria-label="Tangira Ikizamini"
            className="inline-flex h-11 items-center gap-2 border border-brand-800 bg-brand-800 px-6 text-sm font-semibold text-white transition-colors duration-200 hover:bg-white hover:text-brand-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-800 focus-visible:ring-offset-2"
          >
            Tangira Ikizamini
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>

        <MobileNav />
      </Container>
    </header>
  );
}