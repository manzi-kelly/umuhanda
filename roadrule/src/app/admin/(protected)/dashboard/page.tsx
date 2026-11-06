import AdminSection from "@/components/admin/layout/AdminSection";
import AnalyticsPanel from "@/components/admin/dashboard/AnalyticsPanel";

export default function DashboardPage() {
  const seconds = Number(process.env.ADMIN_ANALYTICS_REFRESH_SECONDS ?? 60);
  const refreshMs =
    Number.isInteger(seconds) && seconds >= 30 && seconds <= 300
      ? seconds * 1000
      : 60000;
  return (
    <AdminSection
      eyebrow="Imibare ya serivisi"
      title="Administrator dashboard"
      description="Imibare ibarwa hakoreshejwe amakuru yabitswe."
    >
      <AnalyticsPanel refreshMs={refreshMs} />
    </AdminSection>
  );
}
