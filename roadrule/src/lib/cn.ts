type ClassValue = string | false | null | undefined;

/**
 * Small dependency-free class name helper. Keeps conditional Tailwind
 * class lists readable without adding another runtime dependency.
 */
export function cn(...classes: ClassValue[]): string {
  return classes.filter(Boolean).join(" ");
}
