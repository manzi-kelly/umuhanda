import AdminSection from "@/components/admin/layout/AdminSection";
import { adminRequest, requireAdmin } from "@/features/admin/server";

export default async function Page() {
  await requireAdmin();
  const response = await adminRequest(
    "/api/v1/admin/mock-payments/summary",
  ).catch(() => null);
  const data: { counts: Record<string, number> } | null = response?.ok
    ? await response.json()
    : null;
  return (
    <AdminSection
      eyebrow="Payment operations"
      title="Payments"
      description="Monitor test transaction states."
    >
      <section className="rounded-xl border border-ink/10 bg-surface p-5">
        <h2 className="font-display text-xl font-bold">
          Development mock payments
        </h2>
        <p className="mt-2">Test transaction counts only.</p>
        {data ? (
          <dl className="mt-4 space-y-2">
            {["PENDING", "SUCCESSFUL", "FAILED", "CANCELLED"].map((status) => (
              <div key={status} className="flex justify-between">
                <dt>{status}</dt>
                <dd>{data.counts[status] ?? 0}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p>Test statistics unavailable.</p>
        )}
        <p className="mt-4">Verified real revenue is unavailable.</p>
      </section>
    </AdminSection>
  );
}
