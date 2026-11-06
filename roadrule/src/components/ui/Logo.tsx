import Link from "next/link";
import { Route } from "lucide-react";

import { cn } from "@/lib/cn";

type LogoProps = {
  variant?: "default" | "inverse";
  className?: string;
};

export default function Logo({ variant = "default", className }: LogoProps) {
  const isInverse = variant === "inverse";

  return (
    <Link
      href="/"
      className={cn(
        "group inline-flex shrink-0 items-center gap-3 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2",
        isInverse ? "focus-visible:ring-offset-ink" : "focus-visible:ring-offset-canvas",
        className,
      )}
      aria-label="Umuhanda — subira ahabanza"
    >
      <span
        className={cn(
          "relative grid size-11 place-items-center rounded-2xl shadow-soft transition-colors duration-200",
          isInverse
            ? "bg-white text-brand-950 group-hover:bg-brand-50"
            : "bg-brand-950 text-white group-hover:bg-brand-900",
        )}
        aria-hidden="true"
      >
        <Route className="size-5" strokeWidth={2.2} />
        <span
          className={cn(
            "absolute -right-1 -top-1 size-3 rounded-full bg-accent-400 ring-2",
            isInverse ? "ring-ink" : "ring-canvas",
          )}
        />
      </span>

      <span className="flex flex-col">
        <span
          className={cn(
            "font-display text-base font-extrabold uppercase leading-none tracking-[0.16em]",
            isInverse ? "text-white" : "text-ink",
          )}
        >
          Umuhanda
        </span>
        <span
          className={cn(
            "mt-1 text-[0.58rem] font-semibold uppercase tracking-[0.16em]",
            isInverse ? "text-white/55" : "text-ink-muted",
          )}
        >
          Amategeko y&apos;umuhanda
        </span>
      </span>
    </Link>
  );
}
