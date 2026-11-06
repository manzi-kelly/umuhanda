import { LockKeyhole } from "lucide-react";

export default function UnavailableWorkspace({ title, detail }: { title: string; detail: string }) {
  return <div className="rounded-2xl border border-ink/10 bg-surface p-6 shadow-soft sm:p-9"><span className="grid size-12 place-items-center rounded-2xl bg-brand-50 text-brand-700"><LockKeyhole className="size-6" aria-hidden="true" /></span><p className="mt-5 text-[0.65rem] font-bold uppercase tracking-[0.16em] text-accent-700">Feature unavailable</p><h2 className="mt-3 font-display text-xl font-bold">{title}</h2><p className="mt-3 max-w-2xl text-sm leading-7 text-ink-soft">{detail}</p><p className="mt-5 border-t border-ink/10 pt-5 text-xs leading-6 text-ink-muted">This workspace is reserved for a later phase. No data or working actions are simulated.</p></div>;
}
