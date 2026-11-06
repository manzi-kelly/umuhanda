import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

type SectionHeadingProps = {
  id: string;
  eyebrow: string;
  title: ReactNode;
  description?: ReactNode;
  tone?: "light" | "dark";
  align?: "left" | "center";
  className?: string;
};

export default function SectionHeading({
  id,
  eyebrow,
  title,
  description,
  tone = "light",
  align = "left",
  className,
}: SectionHeadingProps) {
  const isDark = tone === "dark";

  return (
    <div
      className={cn(
        "max-w-3xl",
        align === "center" && "mx-auto text-center",
        className,
      )}
    >
      <p
        className={cn(
          "flex items-center gap-3 text-[0.68rem] font-bold uppercase tracking-[0.22em]",
          align === "center" && "justify-center",
          isDark ? "text-brand-200" : "text-brand-700",
        )}
      >
        <span
          className={cn(
            "h-px w-8",
            isDark ? "bg-brand-300/60" : "bg-brand-600/40",
          )}
          aria-hidden="true"
        />
        {eyebrow}
      </p>

      <h2
        id={id}
        className={cn(
          "mt-4 text-balance font-display text-3xl font-extrabold leading-[1.12] tracking-[-0.02em] sm:text-4xl lg:text-[2.75rem]",
          isDark ? "text-white" : "text-ink",
        )}
      >
        {title}
      </h2>

      {description ? (
        <p
          className={cn(
            "mt-5 max-w-2xl text-pretty text-base leading-7 sm:text-lg sm:leading-8",
            align === "center" && "mx-auto",
            isDark ? "text-brand-100/75" : "text-ink-soft",
          )}
        >
          {description}
        </p>
      ) : null}
    </div>
  );
}
