import { requireAdmin } from "@/features/admin/server";

export default async function AdminSection({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: React.ReactNode }) {
  // Every page checks the DAL independently; authorization is never layout-only.
  await requireAdmin();
  return <section><p className="text-[0.65rem] font-bold uppercase tracking-[0.18em] text-brand-700">{eyebrow}</p><h1 className="mt-3 font-display text-3xl font-extrabold tracking-tight sm:text-4xl">{title}</h1><p className="mt-3 max-w-2xl text-sm leading-7 text-ink-soft">{description}</p><div className="mt-8">{children}</div></section>;
}
