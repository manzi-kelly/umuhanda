"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Menu, X } from "lucide-react";

import { NAV_LINKS, ROUTES } from "@/lib/navigation";
import { cn } from "@/lib/cn";

/**
 * Classic mobile menu — same two-color style as the header:
 *  - brand-800 → design (borders, button)
 *  - ink       → writing
 */
export default function MobileNav() {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  useEffect(() => {
    const desktopQuery = window.matchMedia("(min-width: 1024px)");
    const handleViewportChange = (event: MediaQueryListEvent) => {
      if (event.matches) {
        setIsOpen(false);
      }
    };

    desktopQuery.addEventListener("change", handleViewportChange);
    return () =>
      desktopQuery.removeEventListener("change", handleViewportChange);
  }, []);

  const closeMenu = () => setIsOpen(false);

  return (
    <div className="lg:hidden">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
        aria-controls="mobile-navigation"
        aria-label={isOpen ? "Funga menyu" : "Fungura menyu"}
        className={cn(
          "grid size-11 place-items-center border border-brand-800 transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-800 focus-visible:ring-offset-2",
          isOpen
            ? "bg-brand-800 text-white"
            : "bg-white text-brand-800 hover:bg-brand-800 hover:text-white",
        )}
      >
        {isOpen ? (
          <X className="size-5" aria-hidden="true" />
        ) : (
          <Menu className="size-5" aria-hidden="true" />
        )}
      </button>

      {isOpen ? (
        <div
          id="mobile-navigation"
          className="absolute inset-x-0 top-full max-h-[calc(100dvh-5rem)] overflow-y-auto border-b-4 border-brand-800 bg-white"
        >
          <nav
            aria-label="Menyu ya telefoni"
            className="mx-auto w-full max-w-7xl px-5 py-6 text-center sm:px-8"
          >
            <ul className="space-y-1">
              {NAV_LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    onClick={closeMenu}
                    className="block py-3 text-lg font-semibold text-ink underline-offset-8 decoration-2 decoration-brand-800 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-800"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>

            <div
              className="mx-auto my-5 h-1 w-14 bg-brand-800"
              aria-hidden="true"
            />

            <Link
              href={ROUTES.start}
              onClick={closeMenu}
              aria-label="Tangira Ikizamini"
              className="flex h-12 items-center justify-center gap-2 border border-brand-800 bg-brand-800 text-sm font-semibold text-white transition-colors hover:bg-white hover:text-brand-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-800 focus-visible:ring-offset-2"
            >
              Tangira Ikizamini
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </nav>
        </div>
      ) : null}
    </div>
  );
}