import AdminSection from "@/components/admin/layout/AdminSection";
import BankMonitor from "@/components/admin/questions/BankMonitor";
import { adminRequest, requireAdmin } from "@/features/admin/server";

type System = {
  status: string;
  backend: string;
  database: string;
  pdfWorker: {
    status: string;
    lastObservedActivity: string | null;
    staleProcessing: number;
  };
  pdf: {
    documents: number;
    jobs: Record<string, number>;
    lastSuccessfulImport: string | null;
    extractionErrors: number;
  };
  recentExamStartFailures: number;
  recentGradingIntegrityIssues: number;
  warnings: string[];
};
export default async function Page() {
  await requireAdmin();
  const response = await adminRequest("/api/v1/admin/system").catch(() => null);
  const data: System | null = response?.ok ? await response.json() : null;
  return (
    <AdminSection
      eyebrow="Imikorere ya serivisi"
      title="System monitoring"
      description="Amakuru y’imikorere n’ibibazo byanditswe."
    >
      {!data ? (
        <p role="alert">UNAVAILABLE · Amakuru y’imikorere ntabonetse.</p>
      ) : (
        <section className="space-y-3 rounded-xl border border-ink/10 bg-surface p-5">
          <h2 className="text-xl font-bold">{data.status}</h2>
          <p>
            Backend · {data.backend} / PostgreSQL · {data.database}
          </p>
          <p>
            PDF worker · {data.pdfWorker.status} ·{" "}
            {data.pdfWorker.lastObservedActivity ?? "—"}
          </p>
          <p>
            PDF · {data.pdf.documents} · Ibibazo by’isesengura{" "}
            {data.pdf.extractionErrors}
          </p>
          <p>
            PDF ya nyuma yasesenguwe · {data.pdf.lastSuccessfulImport ?? "—"}
          </p>
          <p>Imirimo imaze igihe · {data.pdfWorker.staleProcessing}</p>
          <ul>
            {Object.entries(data.pdf.jobs).map(([status, count]) => (
              <li key={status}>
                {status} · {count}
              </li>
            ))}
          </ul>
          <p>Ibizamini bitatangiye (24h) · {data.recentExamStartFailures}</p>
          <p>
            Ibibazo mu gutanga amanota (24h) ·{" "}
            {data.recentGradingIntegrityIssues}
          </p>
          {data.warnings.length > 0 && (
            <ul aria-label="Operational warnings">
              {data.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
        </section>
      )}
      <BankMonitor />
    </AdminSection>
  );
}
