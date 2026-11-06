"use client";

import { useEffect, useState } from "react";

type Metrics = Record<string, number | null>;
type Overview = {
  asOf: string;
  students: Metrics;
  examinations: Metrics;
  promos: Metrics;
  payments: Metrics;
};
const periods = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  yearly: "Yearly",
};
type Period = keyof typeof periods;
const labels = {
  students: {
    records: "Total Students",
    uniqueIds: "Distinct student IDs",
    registered: "Abiyandikishije",
    recentlyActiveIds: "Abakoresheje serivisi",
  },
  examinations: {
    attempts: "Ibyatangiye",
    active: "Ibirimo gukorwa",
    completed: "Ibyarangiye",
    expired: "Ibyarengeje igihe",
    passed: "Abatsinze",
    failed: "Abatsinzwe",
    averageScore: "Impuzandengo /20",
    passRate: "Abatsinze (%)",
    unanswered: "Ibibazo bitasubijwe",
  },
  promos: {
    generated: "Kode zakozwe",
    redeemed: "Kode zakoreshejwe",
    active: "Zikora ubu",
    disabled: "Zahagaritswe",
    expired: "Zarangiye",
    exhausted: "Zashize",
    remainingCapacity: "Inshuro zisigaye",
    entitlementsIssued: "Impushya zatanzwe",
  },
  payments: {
    initiated: "Ibyatangiye",
    pending: "Bitegereje",
    successful: "Byemejwe",
    failed: "Byanze",
    cancelled: "Byahagaritswe",
    simulatedSuccessfulRwf: "Amafaranga y’igerageza (RWF)",
    realVerifiedRevenue: "Total Verified Revenue",
  },
};
const sections = {
  students: "Abanyeshuri",
  examinations: "Ibizamini",
  promos: "Kode za promo",
  payments: "Ubwishyu bw’igerageza",
};

type Section = keyof typeof sections;

/** Which metrics are drawn as bars, and what they are measured against. */
const bars: Partial<
  Record<Section, { total: string; items: string[] }>
> = {
  examinations: { total: "attempts", items: ["completed", "active", "expired"] },
  promos: {
    total: "generated",
    items: ["redeemed", "active", "disabled", "expired", "exhausted"],
  },
  payments: {
    total: "initiated",
    items: ["successful", "pending", "failed", "cancelled"],
  },
};

function format(value: number | null | undefined) {
  if (value == null) return "—";
  return value.toLocaleString("en-US", { maximumFractionDigits: 1 });
}

function Bar({
  label,
  value,
  total,
}: {
  label: string;
  value: number | null | undefined;
  total: number | null | undefined;
}) {
  const pct =
    value != null && total ? Math.min(100, Math.max(0, (value / total) * 100)) : 0;

  return (
    <div>
      <div className="flex items-baseline justify-between gap-4 text-sm text-ink">
        <span className="font-medium">{label}</span>
        <span className="font-semibold tabular-nums">
          {format(value)}
          {value != null && total ? ` · ${Math.round(pct)}%` : ""}
        </span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        className="mt-2 h-2 w-full border border-brand-800 bg-white"
      >
        <div
          className="h-full bg-brand-800 transition-[width] duration-700 ease-out motion-reduce:transition-none"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Admin analytics — same two-color style as the public site:
 *  - brand-800 → design (bars, buttons, rules)
 *  - ink       → writing
 */
export default function AnalyticsPanel({
  refreshMs,
  focus,
}: {
  refreshMs: number;
  focus?: Section;
}) {
  const [period, setPeriod] = useState<Period>("weekly");
  const [sample, setSample] = useState<{
    period: Period;
    data: Overview;
  } | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let request: AbortController | undefined;
    async function refresh() {
      clearTimeout(timer);
      if (stopped || request || document.hidden || !navigator.onLine) return;
      request = new AbortController();
      try {
        const response = await fetch(`/admin/analytics-api?period=${period}`, {
          signal: request.signal,
          cache: "no-store",
        });
        if (response.status === 401) {
          stopped = true;
          setSample(null);
          setFailed(true);
          return;
        }
        if (!response.ok) throw new Error("Unavailable");
        const data: Overview = await response.json();
        if (!stopped) {
          setSample({ period, data });
          setFailed(false);
        }
      } catch {
        if (!stopped) setFailed(true);
      } finally {
        request = undefined;
        if (!stopped && !document.hidden && navigator.onLine)
          timer = setTimeout(refresh, refreshMs);
      }
    }
    function wake() {
      if (document.hidden || !navigator.onLine) clearTimeout(timer);
      else void refresh();
    }
    void refresh();
    document.addEventListener("visibilitychange", wake);
    window.addEventListener("online", wake);
    window.addEventListener("offline", wake);
    return () => {
      stopped = true;
      clearTimeout(timer);
      request?.abort();
      document.removeEventListener("visibilitychange", wake);
      window.removeEventListener("online", wake);
      window.removeEventListener("offline", wake);
    };
  }, [period, refreshMs]);
  const data = sample?.period === period ? sample.data : null;
  const isLive = !!data && !failed;

  const highlights = [
    { label: "Total Students", value: format(data?.students.records) },
    { label: "Ibizamini byatangiye", value: format(data?.examinations.attempts) },
    {
      label: "Abatsinze (%)",
      value:
        data?.examinations.passRate != null
          ? `${format(data.examinations.passRate)}%`
          : "—",
    },
    { label: "Ubwishyu bwemejwe", value: format(data?.payments.successful) },
  ];

  return (
    <div className="space-y-12">
      {/* Top bar: live status + period switch */}
      <div className="flex flex-col gap-5 border-b-4 border-brand-800 pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p
            role="status"
            className="flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.28em] text-ink"
          >
            <span className="relative flex size-3" aria-hidden="true">
              {isLive && (
                <span className="absolute inline-flex h-full w-full animate-ping bg-brand-800 opacity-60 motion-reduce:animate-none" />
              )}
              <span
                className={
                  isLive
                    ? "relative inline-flex size-3 bg-brand-800"
                    : "relative inline-flex size-3 border-2 border-brand-800 bg-white"
                }
              />
            </span>
            {failed ? "Byahagaze" : isLive ? "Live" : "Birimo gufungura"}
          </p>
          <p className="mt-3 text-sm text-ink">
            {periods[period]} · Africa/Kigali
            {data && (
              <>
                {" "}
                · Amakuru yo ku wa{" "}
                <time dateTime={data.asOf} className="font-semibold">
                  {new Date(data.asOf).toLocaleString("rw-RW", {
                    timeZone: "Africa/Kigali",
                  })}
                </time>
              </>
            )}
          </p>
        </div>

        <div
          role="group"
          className="flex flex-wrap gap-2"
          aria-label="Reporting period"
        >
          {(Object.keys(periods) as Period[]).map((key) => (
            <button
              key={key}
              type="button"
              aria-pressed={period === key}
              onClick={() => setPeriod(key)}
              className="h-10 border border-brand-800 bg-white px-5 text-sm font-semibold text-ink transition-colors duration-200 hover:bg-brand-800 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-800 focus-visible:ring-offset-2 aria-pressed:bg-brand-800 aria-pressed:text-white"
            >
              {periods[key]}
            </button>
          ))}
        </div>
      </div>

      {failed && (
        <p
          role="alert"
          className="border border-brand-800 px-5 py-4 text-sm font-semibold text-ink"
        >
          Ntitwashoboye kuvugurura imibare.
        </p>
      )}

      {/* Headline figures (full dashboard only) */}
      {!focus && (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-10 text-center lg:grid-cols-4">
          {highlights.map(({ label, value }) => (
            <div key={label} className="flex flex-col items-center">
              <dd className="font-display text-5xl font-bold leading-none tracking-tighter text-brand-800 tabular-nums sm:text-6xl">
                {value}
              </dd>
              <div className="mt-4 h-1 w-10 bg-brand-800" aria-hidden="true" />
              <dt className="mt-3 text-sm font-semibold text-ink">{label}</dt>
            </div>
          ))}
        </dl>
      )}

      {/* Sections */}
      {(focus ? [focus] : (Object.keys(sections) as Section[])).map(
        (section) => {
          const barConfig = bars[section];
          const total = barConfig ? data?.[section][barConfig.total] : null;
          const labelMap = labels[section] as Record<string, string>;

          return (
            <section key={section} aria-labelledby={`${section}-heading`}>
              <h2
                id={`${section}-heading`}
                className="font-display text-2xl font-bold text-ink sm:text-3xl"
              >
                {sections[section]}
              </h2>
              <div className="mt-3 h-1 w-14 bg-brand-800" aria-hidden="true" />

              <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-8 lg:grid-cols-4">
                {Object.entries(labels[section]).map(([key, label]) => (
                  <div key={key}>
                    <dt className="text-sm font-medium text-ink">{label}</dt>
                    <dd className="mt-1 font-display text-3xl font-bold tracking-tight text-brand-800 tabular-nums">
                      {key === "realVerifiedRevenue"
                        ? "Not Available"
                        : format(data?.[section][key])}
                    </dd>
                  </div>
                ))}
              </dl>

              {barConfig && (
                <div className="mt-10 grid gap-x-12 gap-y-5 md:grid-cols-2">
                  {barConfig.items.map((key) => (
                    <Bar
                      key={key}
                      label={labelMap[key]}
                      value={data?.[section][key]}
                      total={total}
                    />
                  ))}
                  {section === "examinations" &&
                    data?.examinations.passRate != null && (
                      <Bar
                        label="Ijanisha ry’abatsinze"
                        value={data.examinations.passRate}
                        total={100}
                      />
                    )}
                </div>
              )}
            </section>
          );
        },
      )}

      <p className="border-t-4 border-brand-800 pt-5 text-sm text-ink">
        Imibare y’abanyeshuri ishingiye ku nyandiko. Amafaranga y’igerageza
        ntiyakiriwe.
      </p>
    </div>
  );
}