"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FileUp, ListChecks, Users, ClipboardCheck, Wallet, Ticket, Settings, Menu, X, ShieldCheck, Route } from "lucide-react";
import type { AdminIdentity } from "@/features/admin/types";
import LogoutButton from "@/components/admin/auth/LogoutButton";

const navigation = [
  ["Dashboard", "dashboard", LayoutDashboard], ["PDF Uploads", "pdf-uploads", FileUp],
  ["Questions", "questions", ListChecks], ["Students", "students", Users],
  ["Examinations", "exams", ClipboardCheck], ["Payments", "payments", Wallet],
  ["Promo Codes", "promo-codes", Ticket], ["Settings", "settings", Settings],
  ["System", "system", ShieldCheck], ["Refunds", "refunds", Wallet],
] as const;

export default function AdminShell({ admin, children }: { admin: AdminIdentity; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const title = navigation.find(([, slug]) => pathname === `/admin/${slug}`)?.[0] ?? "Administrator";
  useEffect(() => { const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); }; window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, []);
  return <div lang="en" className="min-h-dvh bg-canvas lg:grid lg:grid-cols-[260px_1fr]">
    <aside className={`${open ? "block" : "hidden"} sticky top-0 z-30 border-b border-white/10 bg-brand-950 text-white lg:fixed lg:inset-y-0 lg:left-0 lg:block lg:w-[260px] lg:border-r`}>
      <div className="flex items-center justify-between px-6 py-7"><Link href="/admin/dashboard" className="flex items-center gap-3 rounded-lg"><span className="grid size-10 place-items-center rounded-xl bg-accent-400 text-brand-950"><Route className="size-5" aria-hidden="true" /></span><span><span className="block font-display text-sm font-extrabold tracking-[0.14em]">UMUHANDA</span><span className="mt-1 block text-[0.6rem] tracking-[0.2em] text-brand-200">ADMIN WORKSPACE</span></span></Link><button aria-label="Close admin menu" onClick={() => setOpen(false)} className="rounded-lg p-2 lg:hidden"><X className="size-5" /></button></div>
      <div className="px-6 pb-4 text-[0.62rem] font-bold uppercase tracking-[0.2em] text-brand-300">Workspace</div>
      <nav id="admin-navigation" aria-label="Administrator navigation" className="space-y-1 px-3">{navigation.map(([label, slug, Icon]) => <Link key={slug} href={`/admin/${slug}`} prefetch={false} onClick={() => setOpen(false)} aria-current={pathname === `/admin/${slug}` ? "page" : undefined} className={`flex min-h-11 items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium ${pathname === `/admin/${slug}` ? "bg-brand-100 text-brand-950" : "text-brand-100 hover:bg-white/10"}`}><Icon className="size-4 shrink-0" aria-hidden="true" />{label}</Link>)}</nav>
      <div className="mx-3 mt-8 border-t border-white/15 pt-4"><LogoutButton /><p className="flex items-center gap-2 px-4 py-5 text-[0.65rem] text-brand-200"><ShieldCheck className="size-4" aria-hidden="true" />Server-verified administrator session</p></div>
    </aside>
    <div className="min-w-0 lg:col-start-2"><header className="sticky top-0 z-20 flex min-h-20 items-center justify-between gap-4 border-b border-ink/10 bg-surface px-5 py-4 sm:px-8"><div className="flex min-w-0 items-center gap-3"><button type="button" aria-label="Open admin menu" aria-controls="admin-navigation" aria-expanded={open} onClick={() => setOpen(true)} className="rounded-xl border border-ink/15 p-2.5 lg:hidden"><Menu className="size-5" /></button><div><p className="text-[0.6rem] font-bold uppercase tracking-[0.16em] text-ink-muted">Umuhanda / Administration</p><p className="mt-1 font-display text-base font-bold">{title}</p></div></div><div className="flex min-w-0 items-center gap-3"><span className="hidden size-10 shrink-0 place-items-center rounded-full bg-brand-100 font-bold text-brand-800 sm:grid">{admin.fullName.slice(0, 1)}</span><div className="min-w-0 text-right"><p className="max-w-40 truncate text-sm font-semibold">{admin.fullName}</p><p className="mt-1 text-[0.6rem] font-bold uppercase tracking-wider text-brand-700">Administrator</p></div></div></header>
      <main id="main-content" className="mx-auto max-w-[1500px] px-5 py-8 sm:px-8 sm:py-10">{children}</main>
    </div>
  </div>;
}
