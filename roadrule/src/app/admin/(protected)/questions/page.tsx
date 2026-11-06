import AdminSection from "@/components/admin/layout/AdminSection";
import BankMonitor from "@/components/admin/questions/BankMonitor";

export default function Page() {
  return (
    <AdminSection
      eyebrow="Question library"
      title="Questions"
      description="Monitor source PDFs, automatic eligibility, and bank activation."
    >
      <BankMonitor />
    </AdminSection>
  );
}
