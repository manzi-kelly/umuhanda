import type { ReactNode } from "react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "light" | "outlineLight" | "accent";
type ButtonSize = "md" | "lg";

type ButtonLinkProps = {
  href: string;
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: LucideIcon;
  iconPosition?: "left" | "right";
  className?: string;
  ariaLabel?: string;
};

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-950 text-white shadow-soft hover:bg-brand-900 hover:shadow-card",
  secondary:
    "border border-ink/15 bg-surface/80 text-ink hover:border-brand-800/30 hover:bg-white",
  light: "bg-surface text-brand-950 shadow-soft hover:bg-brand-50",
  outlineLight:
    "border border-white/25 bg-white/5 text-white hover:border-white/40 hover:bg-white/10",
  accent: "bg-accent-400 text-ink shadow-soft hover:bg-accent-300",
};

const sizeClasses: Record<ButtonSize, string> = {
  md: "h-12 px-6 text-sm",
  lg: "h-14 px-7 text-base",
};

export default function ButtonLink({
  href,
  children,
  variant = "primary",
  size = "md",
  icon: Icon,
  iconPosition = "right",
  className,
  ariaLabel,
}: ButtonLinkProps) {
  const classes = cn(
    "group inline-flex items-center justify-center gap-2.5 rounded-full font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas",
    variantClasses[variant],
    sizeClasses[size],
    className,
  );

  const content = (
    <>
      {Icon && iconPosition === "left" ? (
        <Icon className="size-4 shrink-0" aria-hidden="true" />
      ) : null}
      <span>{children}</span>
      {Icon && iconPosition === "right" ? (
        <Icon className="size-4 shrink-0" aria-hidden="true" />
      ) : null}
    </>
  );

  const isHashLink = href.startsWith("#") || href.startsWith("/#");

  if (isHashLink) {
    return (
      <a href={href} className={classes} aria-label={ariaLabel}>
        {content}
      </a>
    );
  }

  return (
    <Link href={href} className={classes} aria-label={ariaLabel}>
      {content}
    </Link>
  );
}
