import AdminSection from "@/components/admin/layout/AdminSection";
import { requireAdmin } from "@/features/admin/server";

export default async function Page() {
  await requireAdmin();
  return (
    <AdminSection
      eyebrow="Ubwishyu"
      title="Refund requests"
      description="Gusuzuma ubusabe bwo gusubizwa amafaranga."
    >
      <section className="rounded-xl border border-ink/10 bg-surface p-5">
        <h2 className="text-xl font-bold">UNAVAILABLE</h2>
        <p>
          Gusubiza amafaranga bizashoboka igihe ubwishyu nyabwo bushobora
          kugenzurwa.
        </p>
      </section>
    </AdminSection>
  );
}
