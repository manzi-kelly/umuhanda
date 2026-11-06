import AdminSection from "@/components/admin/layout/AdminSection";
import AnalyticsPanel from "@/components/admin/dashboard/AnalyticsPanel";
import PromoManager from "@/components/admin/promo/PromoManager";

export default function Page() {
  return (
    <AdminSection
      eyebrow="Promotional access"
      title="Promo codes"
      description="Publish exact promo codes, control their availability and monitor redemptions."
    >
      <AnalyticsPanel refreshMs={60000} focus="promos" />
      <PromoManager />
    </AdminSection>
  );
}
