"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, LockKeyhole } from "lucide-react";

import ButtonLink from "@/components/ui/ButtonLink";
import { EXAM_RULES } from "@/lib/constants";
import {
  accessRequest,
  examUnavailableReason,
  AccessRequestError,
  type AccessState,
} from "@/features/onboarding/access-client";
import TimedExam, { type ClockedExam, type ExamState } from "./TimedExam";

type ExamResponse = { exam: ExamState | null };
const recovery =
  "Ntitwabashije kuvugurura ikizamini. Reba umurongo wa interineti cyangwa wongere winjire.";

/**
 * Classic exam entry — same two-color style as the rest of the site:
 *  - brand-800 → design (rules, icons, buttons)
 *  - ink       → writing
 */
export default function ExamEntryShell() {
  const [access, setAccess] = useState<AccessState | null>(null);
  const [active, setActive] = useState<ClockedExam | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const current = useRef<ExamState | null>(null);

  const apply = useCallback((response: ExamResponse) => {
    current.current = response.exam;
    setActive(
      response.exam
        ? { exam: response.exam, received: performance.now() }
        : null,
    );
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      accessRequest<AccessState>(
        "exam-access/me",
        undefined,
        controller.signal,
      ),
      accessRequest<ExamResponse>("exams/me", undefined, controller.signal),
    ])
      .then(([state, exam]) => {
        setAccess(state);
        const retake =
          new URLSearchParams(window.location.search).get("retake") === "1";
        apply(
          retake && exam.exam?.status === "COMPLETED" ? { exam: null } : exam,
        );
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(recovery);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [apply]);

  const perform = useCallback(
    async (request: () => Promise<ExamResponse>, resync = false) => {
      if (pending.current) return;
      pending.current = true;
      setBusy(true);
      setError("");
      try {
        apply(await request());
      } catch (failure) {
        setError(failure instanceof Error ? failure.message : recovery);
        if (failure instanceof AccessRequestError && failure.status === 401) {
          apply({ exam: null });
          setAccess(null);
        } else if (resync && current.current) {
          try {
            apply(
              await accessRequest<ExamResponse>(
                `exams/${current.current.id}/current`,
              ),
            );
          } catch (refreshFailure) {
            if (
              refreshFailure instanceof AccessRequestError &&
              refreshFailure.status === 401
            ) {
              apply({ exam: null });
              setAccess(null);
            }
          }
        }
      } finally {
        pending.current = false;
        setBusy(false);
      }
    },
    [apply],
  );

  const sync = useCallback(() => {
    const exam = current.current;
    void perform(() =>
      accessRequest<ExamResponse>(
        exam ? `exams/${exam.id}/current` : "exams/me",
      ),
    );
  }, [perform]);

  const grant = access?.entitlements.find(
    (item) => item.status === "AVAILABLE",
  );
  const ready = Boolean(access?.examReady && grant);
  const shell = "mx-auto max-w-3xl bg-white px-4 py-10 sm:px-10 sm:py-14";

  if (active) {
    const { exam } = active;
    return (
      <div className={shell}>
        <TimedExam
          value={active}
          busy={busy}
          error={error}
          sync={sync}
          choose={(optionId) => {
            const question = exam.question;
            if (question)
              void perform(
                () =>
                  accessRequest<ExamResponse>(
                    `exams/${exam.id}/answer`,
                    {
                      position: exam.position,
                      optionId,
                      answerVersion: question.answerVersion,
                    },
                    undefined,
                    "PUT",
                  ),
                true,
              );
          }}
          advance={() =>
            void perform(
              () =>
                accessRequest<ExamResponse>(`exams/${exam.id}/next`, {
                  position: exam.position,
                }),
              true,
            )
          }
        />
      </div>
    );
  }

  return (
    <div className={`${shell} border-y-4 border-brand-800 text-center`}>
      <div className="mx-auto flex max-w-xs items-center gap-4">
        <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
          Ikizamini
        </p>
        <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
      </div>

      <LockKeyhole
        className="mx-auto mt-8 size-9 text-brand-800"
        strokeWidth={1.5}
        aria-hidden="true"
      />
      <h1 className="mt-4 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
        Kwitegura ikizamini
      </h1>
      <div className="mx-auto mt-6 h-1 w-16 bg-brand-800" aria-hidden="true" />

      {/* Access status */}
      <div
        role="status"
        id="access-unavailable"
        className="mx-auto mt-8 max-w-xl border border-brand-800 px-5 py-4 text-sm font-semibold leading-6 text-ink"
      >
        {ready
          ? "Uruhushya rwemejwe. Ikizamini kiriteguye. Kanda “Tangira ikizamini” igihe witeguye."
          : grant
            ? examUnavailableReason(access?.bankReason)
            : "Nta ruhushya rwo gutangira ufite. Tanga kode ya promo cyangwa wishyure mbere."}
      </div>

      {/* Student */}
      <dl className="mt-8">
        <dt className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
          Amazina y’umunyeshuri
        </dt>
        <dd className="mt-2 font-display text-xl font-bold text-ink">
          {access?.fullName ?? "Azagaragara nyuma yo kwemezwa na seriveri."}
        </dd>
      </dl>

      {/* Rules — titles only */}
      <h2 className="mt-10 text-xs font-semibold uppercase tracking-[0.28em] text-ink">
        Amategeko y’ikizamini
      </h2>
      <ol className="mx-auto mt-5 grid max-w-xl gap-x-8 gap-y-3 text-left sm:grid-cols-2">
        {EXAM_RULES.map((rule, index) => (
          <li key={rule.title} className="flex items-center gap-3">
            <span
              className="font-display text-xl font-bold text-brand-800"
              aria-hidden="true"
            >
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="text-sm font-semibold text-ink">
              {rule.title}
            </span>
          </li>
        ))}
      </ol>

      {error && (
        <p
          role="alert"
          className="mx-auto mt-8 max-w-xl border-2 border-brand-800 px-5 py-4 text-sm font-semibold text-ink"
        >
          {error}
        </p>
      )}

      {/* Actions */}
      <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
        <button
          type="button"
          disabled={loading || busy || !ready}
          aria-describedby="access-unavailable"
          className="inline-flex h-12 w-full items-center justify-center gap-2 border border-brand-800 bg-brand-800 px-8 text-sm font-semibold text-white transition-colors duration-200 hover:bg-white hover:text-brand-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-800 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 sm:w-auto"
          onClick={() => {
            if (grant)
              void perform(() =>
                accessRequest<ExamResponse>("exams/start", {
                  entitlementId: grant.id,
                }),
              );
          }}
        >
          Tangira ikizamini
          <ArrowRight className="size-4" aria-hidden="true" />
        </button>
        <ButtonLink
          href="/tangira"
          variant="secondary"
          size="lg"
          icon={ArrowLeft}
          className="rounded-none border border-brand-800 bg-white text-ink hover:bg-brand-800 hover:text-white"
        >
          Subira ku makuru yawe
        </ButtonLink>
      </div>
    </div>
  );
}