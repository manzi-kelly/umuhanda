"use client";
/* eslint-disable @next/next/no-img-element -- Authenticated private images must not use a public image optimizer. */
import { useState } from "react";
import type { Draft } from "@/features/admin/pdf-types";

export default function DraftPreview({ draft }: { draft: Draft }) {
  const [source, setSource] = useState<number | null>(null);
  const answerPage = draft.answer?.evidence_page_number;
  function toggleSource(page: number) {
    setSource((current) => (current === page ? null : page));
  }
  return (
    <article className="rounded-2xl border border-ink/10 bg-surface p-5 shadow-soft sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-display text-lg font-bold">
          Ikibazo {draft.source_question_number}
        </h3>
        <span className="rounded-full bg-accent-100 px-3 py-1 text-xs font-semibold text-accent-800">
          Inyandiko yasomwe
        </span>
      </div>
      <p className="mt-4 whitespace-pre-wrap text-sm leading-7">
        {draft.question_text}
      </p>
      <ol className="mt-4 space-y-2">
        {draft.options.map((option) => (
          <li
            key={option.id}
            className="rounded-xl bg-canvas p-3 text-sm leading-6"
          >
            <span className="mr-2 font-bold">{option.option_label}.</span>
            <span className="whitespace-pre-wrap">{option.option_text}</span>
            <span className="ml-2 text-xs text-ink-muted">
              (urupapuro {option.source_page_number})
            </span>
          </li>
        ))}
      </ol>
      {draft.assets.length > 0 && (
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {draft.assets.map((asset) => (
            <figure
              key={asset.id}
              className="rounded-xl border border-ink/10 p-3"
            >
              <img
                src={`/admin/pdf-api/question-draft-assets/${asset.id}`}
                alt={`Ishusho ijyanye n'ikibazo ${draft.source_question_number}`}
                className="mx-auto max-h-64 max-w-full object-contain"
                loading="lazy"
              />
              <figcaption className="mt-2 text-xs text-ink-muted">
                Urupapuro {asset.source_page_number} ·{" "}
                {asset.source_location?.option_label
                  ? `Ihitamo ${asset.source_location.option_label} · `
                  : ""}
                Isano y’ishusho n’ikibazo igenzurwa na sisitemu.
              </figcaption>
            </figure>
          ))}
        </div>
      )}
      <div className="mt-5 rounded-xl border border-accent-200 bg-accent-50 p-4 text-sm leading-6">
        <p className="font-semibold">Igisubizo kiri muri PDF</p>
        {draft.answer?.raw_answer_text ? (
          <>
            <p className="mt-2 whitespace-pre-wrap">
              {draft.answer.raw_answer_text}
            </p>
            <p className="mt-2">
              {draft.answer.selected_option_id
                ? `Inyuguti yasomwe: ${draft.options.find((option) => option.id === draft.answer?.selected_option_id)?.option_label ?? "—"}. Sisitemu igenzura ibimenyetso byayo.`
                : "Ntihashoboye guhuzwa igisubizo kimwe n’inyuguti imwe. Biracyasuzumwa."}
            </p>
            <p className="mt-1 text-xs">
              Ikimenyetso kiri ku rupapuro {draft.answer.evidence_page_number}.
            </p>
          </>
        ) : (
          <p className="mt-2">
            Nta gisubizo cyabonetse mu nyandiko. Nta gisubizo cyahimbwe.
          </p>
        )}
      </div>
      <p className="mt-4 text-xs leading-6 text-ink-muted">
        {draft.extraction_status === "NEEDS_REVIEW"
          ? "Imiterere y’iki kibazo ntirasobanuka neza."
          : "Sisitemu ihita igenzura ibyavuye muri PDF."}{" "}
        Ibibazo byujuje ibisabwa ni byo byinjira mu bubiko bw’ikizamini.
      </p>
      <button
        type="button"
        onClick={() => toggleSource(draft.source_page_number)}
        className="mt-4 rounded-xl border border-brand-700/20 px-4 py-3 text-sm font-semibold text-brand-800"
      >
        {source === draft.source_page_number
          ? "Funga urupapuro"
          : "Reba urupapuro rw’umwimerere"}{" "}
        · {draft.source_page_number}
      </button>
      {answerPage && answerPage !== draft.source_page_number && (
        <button
          type="button"
          onClick={() => toggleSource(answerPage)}
          className="mt-4 ml-2 rounded-xl border border-brand-700/20 px-4 py-3 text-sm font-semibold text-brand-800"
        >
          {source === answerPage
            ? "Funga urupapuro rw’igisubizo"
            : "Reba urupapuro rw’igisubizo"}{" "}
          · {answerPage}
        </button>
      )}
      {source && (
        <img
          src={`/admin/pdf-api/pdf-documents/${draft.document_id}/pages/${source}`}
          alt={`Urupapuro rw’umwimerere ${source}`}
          className="mt-4 h-auto w-full rounded-xl border border-ink/10"
        />
      )}
    </article>
  );
}
