"use client";
import { useState } from "react";
import { ChartNoAxesCombined } from "lucide-react";

export default function StatisticsPlaceholder() {
  const [period, setPeriod] = useState("Daily");
  return <section aria-labelledby="statistics-title" className="mt-8 overflow-hidden rounded-2xl border border-ink/10 bg-surface shadow-soft"><div className="flex flex-wrap items-center justify-between gap-4 border-b border-ink/10 p-5 sm:p-6"><div><h2 id="statistics-title" className="font-display text-lg font-bold">Activity overview</h2><p className="mt-1 text-xs leading-5 text-ink-muted">Reporting workspace · future aggregated data</p></div><div role="group" aria-label="Statistics period" className="flex flex-wrap gap-1 rounded-xl bg-canvas p-1">{["Daily", "Weekly", "Monthly", "Yearly"].map(item => <button key={item} type="button" aria-pressed={item === period} onClick={() => setPeriod(item)} className={`min-h-10 rounded-lg px-3 text-xs font-semibold ${item === period ? "bg-white text-brand-800 shadow-soft" : "text-ink-muted hover:text-ink"}`}>{item}</button>)}</div></div><div className="pattern-grid flex min-h-72 items-center justify-center p-6"><div className="max-w-sm rounded-2xl border border-ink/10 bg-surface p-6 text-center"><ChartNoAxesCombined className="mx-auto mb-4 size-8 text-brand-600" aria-hidden="true" /><p className="font-semibold">Statistics unavailable</p><p role="status" className="mt-2 text-sm leading-6 text-ink-muted">{period} exam and verified-revenue aggregates are not implemented. No sample trends are shown.</p></div></div></section>;
}
