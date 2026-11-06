import { Users, ClipboardList, BadgeCheck, CircleX, Wallet, Ticket } from "lucide-react";
import type { AdminSummary } from "@/features/admin/types";

export default function DashboardCards({ summary }: { summary: AdminSummary | null }) {
  const metrics = [
    { label: "Total Students", icon: Users, value: summary?.totalStudents, note: summary ? "Live student records" : "Reporting service unavailable" },
    { label: "Total Exam Attempts", icon: ClipboardList }, { label: "Passed Exams", icon: BadgeCheck },
    { label: "Failed Exams", icon: CircleX }, { label: "Total Verified Revenue", icon: Wallet }, { label: "Active Promo Codes", icon: Ticket },
  ];
  return <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{metrics.map(({ label, icon: Icon, value, note }) => <article key={label} className="rounded-2xl border border-ink/10 bg-surface p-5 shadow-soft sm:p-6"><div className="flex items-center justify-between gap-3"><h2 className="text-sm font-medium text-ink-soft">{label}</h2><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-700"><Icon className="size-5" aria-hidden="true" /></span></div><p className="mt-5 font-display text-3xl font-extrabold tracking-tight">{value === undefined ? "—" : value.toLocaleString("en")}</p><p className={`mt-2 text-xs ${value === undefined ? "text-ink-muted" : "text-brand-700"}`}>{note ?? "Unavailable · feature not implemented"}</p></article>)}</div>;
}
