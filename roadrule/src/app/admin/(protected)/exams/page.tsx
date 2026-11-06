import Link from "next/link";
import AdminSection from "@/components/admin/layout/AdminSection";
import { adminRequest, requireAdmin } from "@/features/admin/server";

type Stats = {
  total: number;
  active: number;
  completed: number;
  expired: number;
  passed: number;
  failed: number;
  passPercentage: number | null;
  averageScore: number | null;
};
type Attempt = {
  attemptId: string;
  studentName: string;
  startedAt: string;
  completedAt: string | null;
  status: string;
  completionReason: string | null;
  gradingIssue: boolean;
  result: {
    score: number;
    correct: number;
    incorrect: number;
    unanswered: number;
  } | null;
};

const pageSize = 20;
const statuses = ["STARTED", "COMPLETED", "PASSED", "FAILED", "EXPIRED"];
const periods = ["all", "daily", "weekly", "monthly", "yearly"];
const dateFormat = new Intl.DateTimeFormat("en", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});
const formatDate = (value: string | null) =>
  value ? dateFormat.format(new Date(value)) : "—";
const card = "space-y-3 rounded-xl border border-ink/10 bg-surface p-5";

async function read<T>(path: string): Promise<T | null> {
  const response = await adminRequest("/api/v1/admin/" + path).catch(
    () => null,
  );
  return response?.ok ? response.json() : null;
}

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  await requireAdmin();
  const params = await searchParams;
  const value = (key: string) =>
    typeof params[key] === "string" ? (params[key] as string) : "";
  const filters = new URLSearchParams();
  const name = value("search").slice(0, 120);
  if (name) filters.set("search", name);
  const status = value("status");
  if (statuses.includes(status)) filters.set("status", status);
  for (const key of ["start", "end"]) {
    if (/^\d{4}-\d{2}-\d{2}$/.test(value(key))) filters.set(key, value(key));
  }
  const period = periods.includes(value("period")) ? value("period") : "all";
  const offset = /^\d{1,8}$/.test(value("offset"))
    ? Number(value("offset"))
    : 0;
  const selected = value("attempt");
  const [stats, list, detail, operations] = await Promise.all([
    read<Stats>(`exam-results/stats?period=${period}`),
    read<{ items: Attempt[]; hasMore: boolean }>(
      `exam-results?${filters}&limit=${pageSize}&offset=${offset}`,
    ),
    /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(selected)
      ? read<Attempt>(`exam-results/${selected}`)
      : null,
    read<{ startFailures: number }>("exam-execution/summary"),
  ]);
  function href(nextOffset: number, attempt?: string) {
    const query = new URLSearchParams(filters);
    query.set("period", period);
    query.set("offset", String(nextOffset));
    if (attempt) query.set("attempt", attempt);
    return `/admin/exams?${query}`;
  }
  return (
    <AdminSection
      eyebrow="Examination operations"
      title="Examinations"
      description="Review stored examination attempts and grades. Dates and reporting periods use UTC."
    >
      <div className="space-y-5">
        <form method="get" className={card}>
          <div className="flex flex-wrap items-end gap-4">
            <label className="grid gap-1">
              Student name
              <input
                name="search"
                maxLength={120}
                defaultValue={name}
                className="rounded border p-2"
              />
            </label>
            <label className="grid gap-1">
              Status
              <select
                name="status"
                defaultValue={filters.get("status") ?? ""}
                className="rounded border p-2"
              >
                <option value="">All</option>
                {statuses.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
            <label className="grid gap-1">
              Started from
              <input
                type="date"
                name="start"
                defaultValue={filters.get("start") ?? ""}
                className="rounded border p-2"
              />
            </label>
            <label className="grid gap-1">
              Started through
              <input
                type="date"
                name="end"
                defaultValue={filters.get("end") ?? ""}
                className="rounded border p-2"
              />
            </label>
            <label className="grid gap-1">
              Statistics period
              <select
                name="period"
                defaultValue={period}
                className="rounded border p-2"
              >
                {periods.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
            <button className="form-button" type="submit">
              Apply filters
            </button>
          </div>
        </form>
        <section className={card}>
          <h2 className="font-display text-xl font-bold">
            Timed examination activity
          </h2>
          {stats ? (
            <dl className="grid grid-cols-2 gap-4 lg:grid-cols-3">
              {[
                ["Total attempts", stats.total],
                ["Active", stats.active],
                ["Completed", stats.completed],
                ["Passed", stats.passed],
                ["Failed", stats.failed],
                ["Time expired", stats.expired],
                [
                  "Pass percentage",
                  stats.passPercentage === null
                    ? "—"
                    : `${stats.passPercentage}%`,
                ],
                ["Average score /20", stats.averageScore ?? "—"],
                [
                  "Unavailable starts (all time)",
                  operations?.startFailures ?? "—",
                ],
              ].map(([label, count]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd className="font-bold">{count}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p>Examination statistics unavailable.</p>
          )}
          <p className="text-sm">
            Pass percentage and average use graded attempts. Stored active
            states update when an attempt synchronizes.
          </p>
        </section>
        {selected && (
          <section className={card} id="details">
            <h2 className="font-display text-xl font-bold">
              Examination details
            </h2>
            {detail ? (
              <>
                <p className="break-all">
                  {detail.studentName} · {detail.attemptId}
                </p>
                <p>
                  {detail.status} · Started {formatDate(detail.startedAt)} ·
                  Completed {formatDate(detail.completedAt)}
                </p>
                {detail.completionReason && <p>{detail.completionReason}</p>}
                {detail.gradingIssue && (
                  <p role="status">
                    Grading integrity issue. Review the retained snapshot.
                  </p>
                )}
                {detail.result && (
                  <p>
                    Correct {detail.result.correct} · Incorrect{" "}
                    {detail.result.incorrect} · Unanswered{" "}
                    {detail.result.unanswered}
                  </p>
                )}
              </>
            ) : (
              <p>Examination details unavailable.</p>
            )}
          </section>
        )}
        <section className={card}>
          <h2 className="font-display text-xl font-bold">
            Recent examinations
          </h2>
          {!list ? (
            <p>Examination history unavailable.</p>
          ) : list.items.length === 0 ? (
            <p>No examinations match these filters.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr>
                    {[
                      "Student",
                      "Completed (UTC)",
                      "Score",
                      "Status",
                      "Details",
                    ].map((label) => (
                      <th className="p-2" key={label}>
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {list.items.map((item) => (
                    <tr className="border-t border-ink/10" key={item.attemptId}>
                      <td className="p-2">{item.studentName}</td>
                      <td className="p-2">{formatDate(item.completedAt)}</td>
                      <td className="p-2">
                        {item.result ? `${item.result.score}/20` : "—"}
                      </td>
                      <td className="p-2">
                        {item.status}
                        {item.gradingIssue ? " · Grading issue" : ""}
                      </td>
                      <td className="p-2">
                        <Link
                          className="underline"
                          href={href(offset, item.attemptId) + "#details"}
                        >
                          View details
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <nav className="flex gap-4" aria-label="Examination pages">
            {offset > 0 && (
              <Link
                className="underline"
                href={href(Math.max(0, offset - pageSize))}
              >
                Previous
              </Link>
            )}
            {list?.hasMore && (
              <Link className="underline" href={href(offset + pageSize)}>
                Next
              </Link>
            )}
          </nav>
        </section>
      </div>
    </AdminSection>
  );
}
