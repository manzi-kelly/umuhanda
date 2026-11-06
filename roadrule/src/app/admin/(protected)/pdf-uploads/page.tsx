import AdminSection from "@/components/admin/layout/AdminSection";
import PdfWorkspace from "@/components/admin/pdf/PdfWorkspace";

import BankMonitor from "@/components/admin/questions/BankMonitor";

export default function PdfPage() {
  return (
    <AdminSection
      eyebrow="Inkomoko y’ibibazo"
      title="PDF z’ibibazo"
      description="Ohereza inyandiko y’umwimerere, ukurikirane gusoma kwayo, ugenzure ibibazo n’ibimenyetso by’ibisubizo. Sisitemu ihita igenzura ibibazo kandi igakoresha ibyemewe."
    >
      <div lang="rw">
        <PdfWorkspace />
        <BankMonitor />
      </div>
    </AdminSection>
  );
}
