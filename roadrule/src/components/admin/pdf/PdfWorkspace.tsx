"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { FileUp, RefreshCw, FileText, TriangleAlert } from "lucide-react";
import type {
  PdfDocument,
  PdfJob,
  Draft,
  ResultPage,
} from "@/features/admin/pdf-types";
import DraftPreview from "./DraftPreview";

const base = "/admin/pdf-api/";
const statusText: Record<string, string> = {
  QUEUED: "Itegereje gutunganywa",
  PROCESSING: "Iri gutunganywa",
  COMPLETED: "Gusoma byarangiye",
  COMPLETED_WITH_WARNINGS: "Byarangiye; hari ibyo gusuzuma",
  FAILED: "Gutunganya byanze",
};
const messages: Record<string, string> = {
  FILE_SIZE_LIMIT: "PDF irarenze ingano yemewe.",
  PAGE_LIMIT: "PDF ifite impapuro zirenze umubare wemewe.",
  INVALID_PDF: "Iyi dosiye si PDF nzima.",
  PDF_CONTENT_TYPE_REQUIRED: "Hitamo dosiye ya PDF gusa.",
  ENCRYPTED_OR_MALFORMED_PDF: "PDF ifunze cyangwa yangiritse ntiyemewe.",
  UPLOAD_RATE_LIMIT: "Wohereje dosiye nyinshi. Tegereza wongere ugerageze.",
  UNSUPPORTED_ACTIVE_DOCUMENT:
    "PDF irimo imigereka cyangwa ibikorwa bitashyigikiwe.",
  PAGE_DIMENSION_LIMIT: "Ingano y’urupapuro rwa PDF ntishyigikiwe.",
  ADMIN_AUTH_REQUIRED: "Igihe cyo kwinjira cyarangiye. Ongera winjire.",
  INVALID_FILENAME: "Izina rya dosiye ntiryemewe.",
};
async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(base + path, { cache: "no-store", signal });
  if (!response.ok)
    throw new Error(
      response.status === 401
        ? messages.ADMIN_AUTH_REQUIRED
        : "Serivisi ntibashije gusubiza. Ongera ugerageze.",
    );
  return response.json();
}

export default function PdfWorkspace() {
  const [documents, setDocuments] = useState<ResultPage<PdfDocument>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
  });
  const [documentPage, setDocumentPage] = useState(1);
  const [selected, setSelected] = useState<PdfDocument | null>(null);
  const [job, setJob] = useState<PdfJob | null>(null);
  const [drafts, setDrafts] = useState<ResultPage<Draft>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
  });
  const [draftPage, setDraftPage] = useState(1);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [loading, setLoading] = useState(true);
  const input = useRef<HTMLInputElement>(null);
  const [filename, setFilename] = useState("");
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      xhrRef.current?.abort();
    };
  }, []);
  const loadDocuments = useCallback(
    async (signal?: AbortSignal) => {
      const result = await get<ResultPage<PdfDocument>>(
        `pdf-documents?page=${documentPage}&page_size=10`,
        signal,
      );
      if (!signal?.aborted) setDocuments(result);
    },
    [documentPage],
  );
  useEffect(() => {
    const controller = new AbortController();
    get<ResultPage<PdfDocument>>(
      `pdf-documents?page=${documentPage}&page_size=10`,
      controller.signal,
    )
      .then((result) => {
        if (!controller.signal.aborted) setDocuments(result);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [documentPage]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const jobs = await get<PdfJob[]>(
          `pdf-documents/${selected.id}/jobs`,
          controller.signal,
        );
        const result = await get<ResultPage<Draft>>(
          `question-drafts?document_id=${selected.id}&page=${draftPage}&page_size=10`,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        setJob(jobs[0] ?? null);
        setDrafts(result);
        if (jobs[0] && ["QUEUED", "PROCESSING"].includes(jobs[0].status))
          timer = setTimeout(refresh, 2000);
      } catch (e) {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : "Gusoma byanze.");
      }
    };
    refresh();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [selected, draftPage]);
  function choose(document: PdfDocument) {
    setSelected(document);
    setDraftPage(1);
    setJob(null);
    setDrafts({ items: [], total: 0, page: 1, page_size: 10 });
    setError("");
  }
  function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    const file = input.current?.files?.[0];
    if (
      !file ||
      !file.name.toLowerCase().endsWith(".pdf") ||
      (file.type && file.type !== "application/pdf")
    ) {
      setError("Hitamo dosiye ya PDF gusa.");
      return;
    }
    if (file.size > 26214400) {
      setError(messages.FILE_SIZE_LIMIT);
      return;
    }
    setUploading(true);
    setProgress(0);
    const xhr = new XMLHttpRequest();
    xhrRef.current = xhr;
    xhr.open("POST", base + "pdf-documents");
    xhr.setRequestHeader("Content-Type", "application/pdf");
    xhr.setRequestHeader("X-PDF-Filename", encodeURIComponent(file.name));
    xhr.timeout = 90000;
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && mounted.current)
        setProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (!mounted.current) return;
      setUploading(false);
      try {
        const value = JSON.parse(xhr.responseText);
        if (xhr.status !== 202) {
          setError(
            messages[value.error?.code] ??
              "Kohereza PDF byanze. Ongera ugerageze.",
          );
          return;
        }
        setNotice(
          value.duplicate
            ? "Iyi PDF yari isanzwe ihari; nta yindi yakozwe."
            : "PDF yabitswe.",
        );
        if (input.current) input.current.value = "";
        setFilename("");
        choose(value.document);
        loadDocuments().catch(() =>
          setError("Urutonde rwa PDF ntirubashije kuvugururwa."),
        );
      } catch {
        setError("Serivisi ntibashije kwemeza ko PDF yabitswe.");
      }
    };
    const failed = () => {
      if (mounted.current) {
        setUploading(false);
        setError("Kohereza PDF byahagaze. Ongera ugerageze.");
      }
    };
    xhr.onerror = failed;
    xhr.ontimeout = failed;
    xhr.onabort = failed;
    xhr.send(file);
  }
  async function retry() {
    if (!job || !selected) return;
    try {
      const response = await fetch(base + `pdf-import-jobs/${job.id}/retry`, {
        method: "POST",
      });
      if (!response.ok)
        throw new Error(
          "Gusubiramo ntibyashobotse. Umurimo ushobora kuba ugikora.",
        );
      choose({ ...selected, import_status: "QUEUED" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gusubiramo byanze.");
    }
  }
  return (
    <div className="space-y-7">
      <form
        onSubmit={upload}
        className="rounded-2xl border border-dashed border-brand-700/30 bg-surface p-6 shadow-soft sm:p-8"
      >
        <FileUp className="size-9 text-brand-700" aria-hidden="true" />
        <h2 className="mt-4 font-display text-xl font-bold">
          Ohereza PDF y’ibibazo
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-ink-soft">
          Ibibazo n’ibisubizo bisomwa muri PDF y’umwimerere gusa. Ibyasomwe
          bigenzurwa na sisitemu mbere yo kwinjira mu bubiko.
        </p>
        <input
          ref={input}
          id="source-pdf"
          type="file"
          accept="application/pdf,.pdf"
          disabled={uploading}
          onChange={(event) =>
            setFilename(event.currentTarget.files?.[0]?.name ?? "")
          }
          className="peer sr-only"
        />
        <div className="mt-5 flex flex-wrap items-center gap-3 rounded-xl border border-ink/15 p-3 peer-focus-visible:ring-2 peer-focus-visible:ring-brand-600">
          <label
            htmlFor="source-pdf"
            className="cursor-pointer rounded-lg bg-brand-50 px-3 py-2 text-sm font-semibold text-brand-800"
          >
            Dosiye ya PDF
          </label>
          <span className="min-w-0 break-all text-sm text-ink-soft">
            {filename || "Nta dosiye yahiswemo"}
          </span>
        </div>
        <p className="mt-2 text-xs leading-6 text-ink-muted">
          Kugeza kuri 25 MiB. PDF ifunze, yangiritse cyangwa ifite imiterere
          idashyigikiwe irangwa. PDF iskenwe ishobora gusaba OCR itaraboneka.
        </p>
        <button disabled={uploading} type="submit" className="form-button mt-5">
          {uploading ? "Iri koherezwa…" : "Ohereza PDF"}
        </button>
        {uploading && (
          <div className="mt-4">
            <label htmlFor="upload-progress" className="text-sm">
              {progress < 100
                ? `Kohereza dosiye: ${progress}%`
                : "Dosiye yoherejwe; iragenzurwa kandi irabikwa…"}
            </label>
            <progress
              id="upload-progress"
              className="mt-2 h-2 w-full accent-brand-700"
              value={progress}
              max={100}
            />
          </div>
        )}
      </form>
      {error && (
        <p
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm leading-6 text-red-800"
        >
          {error}{" "}
          <a href="/admin/login" className="ml-2 underline">
            Kwinjira
          </a>
        </p>
      )}
      {notice && (
        <p
          role="status"
          className="rounded-xl bg-brand-50 p-4 text-sm text-brand-800"
        >
          {notice}
        </p>
      )}
      <section className="rounded-2xl border border-ink/10 bg-surface p-5 sm:p-7">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-xl font-bold">
            PDF zabitswe{" "}
            <span className="text-sm text-ink-muted">({documents.total})</span>
          </h2>
          <button
            type="button"
            aria-label="Vugurura urutonde"
            onClick={() => loadDocuments().catch((e) => setError(e.message))}
            className="rounded-xl border border-ink/10 p-3"
          >
            <RefreshCw className="size-4" />
          </button>
        </div>
        {loading ? (
          <p className="mt-5 text-sm">Urutonde ruri gusomwa…</p>
        ) : !documents.items.length ? (
          <p className="mt-5 text-sm text-ink-muted">Nta PDF irabikwa.</p>
        ) : (
          <ul className="mt-5 divide-y divide-ink/10">
            {documents.items.map((document) => (
              <li key={document.id}>
                <button
                  type="button"
                  onClick={() => choose(document)}
                  className={`flex w-full min-w-0 items-start gap-3 rounded-xl p-4 text-left ${selected?.id === document.id ? "bg-brand-50" : "hover:bg-canvas"}`}
                >
                  <FileText className="mt-1 size-5 shrink-0 text-brand-700" />
                  <span className="min-w-0">
                    <span className="block break-all text-sm font-semibold">
                      {document.original_filename}
                    </span>
                    <span className="mt-1 block text-xs leading-6 text-ink-muted">
                      Impapuro {document.page_count} ·{" "}
                      {
                        statusText[
                          selected?.id === document.id && job
                            ? job.status
                            : document.import_status
                        ]
                      }
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-4 flex items-center justify-between gap-3 text-sm">
          <button
            disabled={documentPage === 1}
            onClick={() => setDocumentPage((value) => value - 1)}
            className="rounded-lg border border-ink/10 p-2 disabled:opacity-40"
          >
            Ibibanza
          </button>
          <span>Urupapuro {documentPage}</span>
          <button
            disabled={documentPage * 10 >= documents.total}
            onClick={() => setDocumentPage((value) => value + 1)}
            className="rounded-lg border border-ink/10 p-2 disabled:opacity-40"
          >
            Ibikurikira
          </button>
        </div>
      </section>
      {selected && (
        <section aria-label="Ibyavuye muri PDF" className="space-y-5">
          <div className="rounded-2xl border border-brand-700/20 bg-brand-50 p-5 sm:p-7">
            <h2 className="break-all font-display text-xl font-bold">
              {selected.original_filename}
            </h2>
            {job ? (
              <>
                <p className="mt-3 text-sm font-semibold">
                  {statusText[job.status]}
                </p>
                <label htmlFor="job-progress" className="mt-3 block text-sm">
                  Impapuro zasomwe: {job.processed_pages} / {job.total_pages}
                </label>
                <progress
                  id="job-progress"
                  value={job.processed_pages}
                  max={job.total_pages}
                  className="mt-2 h-2 w-full accent-brand-700"
                />
                <dl className="mt-5 grid gap-4 sm:grid-cols-3">
                  {[
                    ["Ibibazo byasomwe", job.extracted_question_count],
                    ["Ibice bitasomwe neza", job.failed_item_count],
                  ].map(([label, count]) => (
                    <div key={label} className="rounded-xl bg-surface p-4">
                      <dt className="text-xs text-ink-muted">{label}</dt>
                      <dd className="mt-2 font-display text-2xl font-bold">
                        {count}
                      </dd>
                    </div>
                  ))}
                </dl>
                {job.status === "QUEUED" && (
                  <p className="mt-4 text-sm leading-6">
                    Itegereje umukozi wo gutunganya PDF. Niba itangira ritinda,
                    menyesha ushinzwe sisitemu.
                  </p>
                )}
                {job.diagnostics.length > 0 && (
                  <div className="mt-4 rounded-xl bg-accent-50 p-4 text-sm leading-6">
                    <p className="flex items-center gap-2 font-semibold">
                      <TriangleAlert className="size-4" />
                      Hari ibyo gusuzuma
                    </p>
                    <ul className="mt-2 list-inside list-disc">
                      {job.diagnostics.map((item, index) => (
                        <li key={index}>
                          {item.page ? `Urupapuro ${item.page}: ` : ""}
                          {item.question ? `Ikibazo ${item.question} · ` : ""}
                          {item.labels?.length
                            ? `${item.labels.join(", ")} · `
                            : ""}
                          {item.code === "AMBIGUOUS_OPTION_IMAGE"
                            ? "Ishusho y’ihitamo ntishobora guhuzwa neza."
                            : item.code.includes("OCR")
                              ? "Rukeneye OCR; ntirwasomwe mu buryo bwizewe."
                              : item.code === "NO_SUPPORTED_QUESTIONS"
                                ? "Nta bibazo bifite imiterere ishyigikiwe byabonetse."
                                : "Hari igice cy’inyandiko kitashoboye gusomwa neza. Gereranya na PDF y’umwimerere."}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {[
                  "FAILED",
                  "PROCESSING",
                  "COMPLETED",
                  "COMPLETED_WITH_WARNINGS",
                ].includes(job.status) && (
                  <button
                    type="button"
                    onClick={retry}
                    className="mt-4 rounded-xl border border-brand-700/25 bg-surface px-4 py-3 text-sm font-semibold"
                  >
                    Saba kongera gutunganya
                  </button>
                )}
              </>
            ) : (
              <p className="mt-3 text-sm">Iby’umurimo biri gusomwa…</p>
            )}
          </div>
          <h2 className="font-display text-xl font-bold">
            Ibibazo byasomwe ({drafts.total})
          </h2>
          {drafts.items.map((draft) => (
            <DraftPreview key={draft.id} draft={draft} />
          ))}
          <div className="flex items-center justify-between gap-3 text-sm">
            <button
              disabled={draftPage === 1}
              onClick={() => setDraftPage((value) => value - 1)}
              className="rounded-lg border border-ink/10 bg-surface p-3 disabled:opacity-40"
            >
              Ibibazo bibanza
            </button>
            <span>Urupapuro {draftPage}</span>
            <button
              disabled={draftPage * 10 >= drafts.total}
              onClick={() => setDraftPage((value) => value + 1)}
              className="rounded-lg border border-ink/10 bg-surface p-3 disabled:opacity-40"
            >
              Ibibazo bikurikira
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
