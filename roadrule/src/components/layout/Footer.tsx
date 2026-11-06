import { ShieldCheck } from "lucide-react";

import Container from "@/components/ui/Container";
import Logo from "@/components/ui/Logo";
import {
  FOOTER_CONTACT,
  FOOTER_LINKS,
  SITE,
} from "@/lib/constants";

/**
 * Classic footer — same two-color style as the other sections:
 *  - brand-800 → design (rules, icons)
 *  - ink       → writing
 */
export default function Footer() {
  return (
    <footer className="border-t-4 border-brand-800 bg-white">
      <Container className="py-12 sm:py-14">
        <div className="grid gap-10 text-center md:grid-cols-3 md:text-left">
          {/* Brand */}
          <div className="flex flex-col items-center md:items-start">
            <Logo />
            <div className="mt-5 h-1 w-12 bg-brand-800" aria-hidden="true" />
            <p className="mt-5 max-w-xs text-sm leading-6 text-ink">
              {SITE.description}
            </p>
            <p className="mt-4 flex items-center gap-2 text-sm font-semibold text-ink">
              <ShieldCheck
                className="size-4 shrink-0 text-brand-800"
                aria-hidden="true"
              />
              Ikizamini gisaba uruhushya rwemejwe
            </p>
          </div>

          {/* Links */}
          <nav aria-label="Ihuza ry'epaji">
            <h2 className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
              Ihuza
            </h2>
            <div className="mt-3 h-1 w-12 bg-brand-800 max-md:mx-auto" aria-hidden="true" />
            <ul className="mt-5 space-y-3">
              {FOOTER_LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    className="inline-flex text-sm font-medium text-ink underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-800"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          {/* Contact */}
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
              Twandikire
            </h2>
            <div className="mt-3 h-1 w-12 bg-brand-800 max-md:mx-auto" aria-hidden="true" />
            <ul className="mt-5 space-y-4">
              {FOOTER_CONTACT.map(({ icon: Icon, label, value }) => (
                <li
                  key={label}
                  className="flex items-center justify-center gap-3 md:justify-start"
                >
                  <Icon
                    className="size-5 shrink-0 text-brand-800"
                    strokeWidth={1.75}
                    aria-hidden="true"
                  />
                  <span className="text-sm text-ink">
                    <span className="font-semibold">{label}:</span> {value}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom line */}
        <div className="mt-12 flex flex-col items-center gap-2 text-center text-xs leading-5 text-ink sm:flex-row sm:justify-between sm:text-left">
          <p>
            © {SITE.copyrightYear} {SITE.name}. Uburenganzira bwose
            burabitswe.
          </p>
          <p>Ikizamini gisaba uruhushya rwemejwe.</p>
        </div>
      </Container>
    </footer>
  );
}