import { CircleAlert, CircleCheck } from "lucide-react";

import { getExamBankStatus } from "@/features/admin/server";

const counts = [
  ["extracted", "Extracted"],
  ["ELIGIBLE", "Eligible"],
  ["INELIGIBLE_MISSING_ANSWER", "Missing answer"],
  ["INELIGIBLE_AMBIGUOUS_ANSWER", "Ambiguous answer"],
  ["INELIGIBLE_IMAGE_ERROR", "Image errors"],
  ["road_sign", "Eligible road signs"],
  ["supported_answers", "Ibisubizo bifite ibimenyetso"],
  ["parenthesized_answers", "Ibisubizo biri mu dukubo"],
  ["image_only_options", "Amahitamo agizwe n’amashusho"],
  ["green_answers", "Ibisubizo byagaragajwe n’icyatsi"],
  ["INELIGIBLE_INCOMPLETE_OPTIONS", "Amahitamo atuzuye"],
  ["INELIGIBLE_EXTRACTION_ERROR", "Ibibazo byo gusoma PDF"],
] as const;

const bankLabels: Record<string, string> = {
  READY: "Validated",
  INSUFFICIENT_CATEGORIES: "Ibyiciro ntibifite ibibazo bihagije",
  INSUFFICIENT_QUESTIONS: "Insufficient question mix",
  INSUFFICIENT_DIFFICULTY: "Insufficient source difficulty labels",
  EXTRACTION_IMPROVEMENTS_REQUIRED: "Extraction improvements required",
};

/**
 * Classic bank monitor — same two-color style as the rest of the site:
 *  - brand-800 → design (rules, numbers, icons)
 *  - ink       → writing
 */
export default async function BankMonitor() {
  const bank = await getExamBankStatus();
  const StatusIcon = bank?.ready ? CircleCheck : CircleAlert;

  return (
    <section
      aria-labelledby="bank-monitor-heading"
      className="mt-10 border-t-4 border-brand-800 pt-8"
    >
      <h2
        id="bank-monitor-heading"
        className="font-display text-2xl font-bold text-ink sm:text-3xl"
      >
        Automatic exam bank
      </h2>
      <div className="mt-3 h-1 w-14 bg-brand-800" aria-hidden="true" />

      {!bank ? (
        <p className="mt-6 border border-brand-800 px-5 py-4 text-sm font-semibold text-ink">
          Bank status is unavailable.
        </p>
      ) : (
        <>
          {/* Overall status */}
          <p
            role="status"
            className="mt-6 flex items-center gap-3 text-lg font-bold text-ink"
          >
            <StatusIcon
              className="size-6 shrink-0 text-brand-800"
              aria-hidden="true"
            />
            {bank.ready ? "Question bank ready" : "No exam-ready bank"}
          </p>

          {bank.activeRevisionId && (
            <p className="mt-3 break-all text-sm text-ink">
              Active revision{" "}
              <span className="font-semibold">{bank.activeRevisionId}</span> ·{" "}
              {bank.policy === "UNSTRATIFIED"
                ? "Unstratified selection"
                : bank.policy === "CATEGORY_BALANCED"
                  ? "Guhitamo hakurikijwe ibyiciro"
                  : "7 bikomeye, 4 biciriritse, 9 byoroshye"}
            </p>
          )}
          <p className="mt-2 text-sm text-ink">
            Last successful processing{" "}
            <span className="font-semibold">
              {bank.lastProcessedAt
                ? new Date(bank.lastProcessedAt)
                    .toISOString()
                    .replace("T", " ")
                    .slice(0, 16) + " UTC"
                : "—"}
            </span>{" "}
            · Unavailable events{" "}
            <span className="font-semibold">{bank.unavailableEvents}</span>
          </p>

          {/* Source documents */}
          <ul className="mt-10 space-y-12">
            {bank.documents.map((document) => {
              const values = document.counts;
              const isActive = document.id === bank.activeDocumentId;

              return (
                <li key={document.id}>
                  <p className="break-all font-display text-lg font-bold text-ink">
                    {document.filename}
                  </p>
                  <p className="mt-1 text-sm text-ink">
                    {isActive && (
                      <span className="mr-2 border border-brand-800 bg-brand-800 px-2 py-0.5 text-xs font-semibold uppercase tracking-[0.14em] text-white">
                        Active source
                      </span>
                    )}
                    {document.processingStatus
                      .replaceAll("_", " ")
                      .toLowerCase()}
                    {document.bankStatus
                      ? " · " + bankLabels[document.bankStatus]
                      : ""}
                  </p>
                  {document.errorCode && (
                    <p className="mt-2 flex items-center gap-2 text-sm font-semibold text-ink">
                      <CircleAlert
                        className="size-4 shrink-0 text-brand-800"
                        aria-hidden="true"
                      />
                      Processing issue {document.errorCode}
                    </p>
                  )}

                  {values?.category_targets && values.category_available && (
                    <div className="mt-4 space-y-1 text-sm text-ink">
                      <p>
                        Ibyapa:{" "}
                        <span className="font-semibold">
                          {values.category_available.ROAD_SIGN} bihari ·{" "}
                          {values.category_targets.ROAD_SIGN} bisabwa
                        </span>
                      </p>
                      <p>
                        Ibindi:{" "}
                        <span className="font-semibold">
                          {values.category_available.GENERAL} bihari ·{" "}
                          {values.category_targets.GENERAL} bisabwa
                        </span>
                      </p>
                      <p>
                        Imiburo y’imiterere:{" "}
                        <span className="font-semibold">
                          {values.structural_warnings}
                        </span>{" "}
                        · Ibibuza gukora ikizamini:{" "}
                        <span className="font-semibold">
                          {values.blocking_warnings}
                        </span>
                      </p>
                    </div>
                  )}

                  {values && (
                    <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-3 lg:grid-cols-4">
                      {counts
                        .filter(
                          ([key]) =>
                            ![
                              "supported_answers",
                              "parenthesized_answers",
                              "green_answers",
                            ].includes(key) || values[key] !== undefined,
                        )
                        .map(([key, label]) => (
                          <div key={key}>
                            <dd className="font-display text-3xl font-bold leading-none tracking-tight text-brand-800 tabular-nums">
                              {values[key] ?? 0}
                            </dd>
                            <div
                              className="mt-3 h-1 w-8 bg-brand-800"
                              aria-hidden="true"
                            />
                            <dt className="mt-2 text-sm font-medium text-ink">
                              {label}
                            </dt>
                          </div>
                        ))}
                      <div>
                        <dd className="font-display text-3xl font-bold leading-none tracking-tight text-brand-800 tabular-nums">
                          {(values.extracted ?? 0) - (values.ELIGIBLE ?? 0)}
                        </dd>
                        <div
                          className="mt-3 h-1 w-8 bg-brand-800"
                          aria-hidden="true"
                        />
                        <dt className="mt-2 text-sm font-medium text-ink">
                          Ineligible
                        </dt>
                      </div>
                    </dl>
                  )}
                </li>
              );
            })}
          </ul>
          {!bank.documents.length && (
            <p className="mt-6 text-sm font-medium text-ink">
              No PDFs uploaded.
            </p>
          )}
        </>
      )}
    </section>
  );
}