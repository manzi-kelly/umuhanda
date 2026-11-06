"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { ArrowRight, Clock, Home, RefreshCw } from "lucide-react";

import ButtonLink from "@/components/ui/ButtonLink";

export type ExamState = {
  id: string;
  status: "STARTED" | "COMPLETED";
  position: number;
  total: number;
  serverNow: string;
  globalDeadline: string;
  warningAt: string;
  completionReason: "GLOBAL_TIME_EXPIRED" | "ALL_QUESTIONS_FINISHED" | null;
  question: {
    text: string;
    options: { id: number; label: string; text: string; image?: string }[];
    deadline: string;
    selectedOption: number | null;
    answerVersion: number;
    images: string[];
  } | null;
};

export type ClockedExam = { exam: ExamState; received: number };

function duration(ms: number) {
  const seconds = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

const primaryButton =
  "inline-flex h-12 items-center justify-center gap-2 border border-brand-800 bg-brand-800 px-8 text-sm font-semibold text-white transition-colors duration-200 hover:bg-white hover:text-brand-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-800 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50";

const secondaryButton =
  "inline-flex h-12 items-center justify-center gap-2 border border-brand-800 bg-white px-8 text-sm font-semibold text-ink transition-colors duration-200 hover:bg-brand-800 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-800 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50";

function ExamImage({ path }: { path: string }) {
  const [failed, setFailed] = useState(false);
  if (failed)
    return (
      <div
        role="status"
        className="border border-brand-800 px-5 py-4 text-sm text-ink"
      >
        <p className="font-semibold">Ishusho ntibashije kugaragara.</p>
        <button
          type="button"
          className="mt-2 font-semibold underline decoration-brand-800 decoration-2 underline-offset-4"
          onClick={() => setFailed(false)}
        >
          Ongera usome ishusho
        </button>
      </div>
    );
  return (
    <Image
      unoptimized
      width={640}
      height={480}
      src={"/student-api/" + path}
      alt="Ishusho ijyanye n’ikibazo"
      onError={() => setFailed(true)}
      className="h-auto max-h-64 max-w-full border border-brand-800 object-contain"
    />
  );
}

/**
 * Classic timed exam — same two-color style as the rest of the site:
 *  - brand-800 → design (rules, bars, borders, buttons)
 *  - ink       → writing
 * The low-time warning and selected answer are shown by inverting to a
 * solid brand-800 block, not by red / extra colors.
 */
export default function TimedExam({
  value,
  busy,
  error,
  sync,
  choose,
  advance,
}: {
  value: ClockedExam;
  busy: boolean;
  error: string;
  sync: () => void;
  choose: (option: number) => void;
  advance: () => void;
}) {
  const { exam, received } = value;
  const [tick, setTick] = useState(0);
  const server = Date.parse(exam.serverNow);
  const estimate = server + Math.max(0, tick - received);
  const global = Date.parse(exam.globalDeadline) - estimate;
  const question = exam.question;
  const remaining = question ? Date.parse(question.deadline) - estimate : 0;
  const expired = global <= 0 || remaining <= 0;
  useEffect(() => {
    if (!question) return;
    const timer = window.setInterval(() => setTick(performance.now()), 250);
    const retry = window.setInterval(() => {
      const timestamp = server + Math.max(0, performance.now() - received);
      if (timestamp >= Date.parse(question.deadline)) sync();
    }, 1000);
    const wake = () => {
      if (document.visibilityState === "visible") sync();
    };
    document.addEventListener("visibilitychange", wake);
    window.addEventListener("online", sync);
    return () => {
      window.clearInterval(timer);
      window.clearInterval(retry);
      document.removeEventListener("visibilitychange", wake);
      window.removeEventListener("online", sync);
    };
  }, [question, received, server, sync]);

  if (!question)
    return (
      <section className="border-y-4 border-brand-800 py-12 text-center sm:py-16">
        <div className="mx-auto flex max-w-xs items-center gap-4">
          <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
            Ikizamini
          </p>
          <span className="h-px flex-1 bg-brand-800" aria-hidden="true" />
        </div>
        <h1 className="mt-6 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
          Ikizamini cyarangiye
        </h1>
        <div
          className="mx-auto mt-6 h-1 w-16 bg-brand-800"
          aria-hidden="true"
        />
        <p
          role="status"
          className="mx-auto mt-6 max-w-md text-base leading-7 text-ink"
        >
          {exam.completionReason === "GLOBAL_TIME_EXPIRED"
            ? "Igihe cy’ikizamini cyarangiye. Ibisubizo byawe byabitswe."
            : "Warangije ibibazo. Ibisubizo byawe byabitswe."}
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <ButtonLink
            href={`/results/${exam.id}`}
            size="lg"
            icon={ArrowRight}
            className="rounded-none border border-brand-800 bg-brand-800 text-white hover:bg-white hover:text-brand-800"
          >
            Reba ibisubizo
          </ButtonLink>
          <ButtonLink
            href="/"
            variant="secondary"
            size="lg"
            icon={Home}
            className="rounded-none border border-brand-800 bg-white text-ink hover:bg-brand-800 hover:text-white"
          >
            Subira ahabanza
          </ButtonLink>
        </div>
      </section>
    );

  const warning = estimate >= Date.parse(exam.warningAt);
  const percent = Math.round((exam.position / exam.total) * 100);

  return (
    <section className="space-y-6" aria-busy={busy}>
      {/* Header: question number + global timer */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b-4 border-brand-800 pb-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-ink">
            Ikibazo
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold tracking-tight text-ink">
            <span className="text-brand-800">{exam.position}</span>/
            {exam.total}
          </h1>
        </div>
        <div
          className={`flex items-center gap-3 border border-brand-800 px-5 py-3 font-display text-2xl font-bold tabular-nums ${
            warning
              ? "animate-pulse bg-brand-800 text-white motion-reduce:animate-none"
              : "bg-white text-brand-800"
          }`}
        >
          <Clock className="size-5 shrink-0" aria-hidden="true" />
          <span className="sr-only">Igihe cy’ikizamini gisigaye</span>
          <span data-testid="global-countdown">{duration(global)}</span>
        </div>
      </header>

      {/* Progress */}
      <div
        role="progressbar"
        aria-label="Aho ugeze mu kizamini"
        aria-valuemin={0}
        aria-valuemax={exam.total}
        aria-valuenow={exam.position}
        className="h-2 w-full border border-brand-800 bg-white"
      >
        <div
          className="h-full bg-brand-800 transition-[width] duration-500 motion-reduce:transition-none"
          style={{ width: `${percent}%` }}
        />
      </div>

      <p className="text-sm font-medium text-ink">
        Igihe gisigaye kuri iki kibazo:{" "}
        <span
          data-testid="question-countdown"
          className="font-bold tabular-nums text-brand-800"
        >
          {duration(remaining)}
        </span>
      </p>

      {!expired && (
        <>
          <p className="whitespace-pre-wrap break-words font-display text-xl font-bold leading-snug text-ink sm:text-2xl">
            {question.text}
          </p>
          {question.images.map((path) => (
            <ExamImage key={path} path={path} />
          ))}
          <fieldset disabled={busy || expired} className="space-y-3">
            <legend className="mb-3 text-xs font-semibold uppercase tracking-[0.28em] text-ink">
              Hitamo igisubizo
            </legend>
            {question.options.map((option) => (
              <label
                key={option.id}
                className="flex cursor-pointer items-start gap-4 border border-brand-800 bg-white p-4 text-ink transition-colors duration-200 hover:bg-brand-800/5 has-[:checked]:bg-brand-800 has-[:checked]:text-white has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-800 has-[:focus-visible]:ring-offset-2"
              >
                <input
                  type="radio"
                  name="answer"
                  value={option.id}
                  checked={question.selectedOption === option.id}
                  onChange={() => choose(option.id)}
                  className="mt-1 size-4 shrink-0 accent-brand-800"
                />
                <span className="min-w-0 whitespace-pre-wrap text-base font-medium leading-7 wrap-anywhere">
                  <span className="font-bold">{option.label}.</span>{" "}
                  {option.text}
                  {option.image && (
                    <Image
                      unoptimized
                      width={640}
                      height={480}
                      src={`/student-api/${option.image}`}
                      alt={`Ishusho y’ihitamo ${option.label}`}
                      className="mt-3 h-auto max-h-48 max-w-full bg-white object-contain"
                    />
                  )}
                </span>
              </label>
            ))}
          </fieldset>
        </>
      )}

      {error && (
        <p
          role="alert"
          className="border-2 border-brand-800 px-5 py-4 text-sm font-semibold text-ink"
        >
          {error}
        </p>
      )}
      {expired && (
        <p
          role="status"
          className="border border-brand-800 px-5 py-4 text-sm font-semibold text-ink"
        >
          Igihe cy’iki kibazo cyarangiye. Turavugurura ikizamini.
        </p>
      )}

      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          className={primaryButton}
          disabled={busy || expired}
          onClick={advance}
        >
          {exam.position === exam.total
            ? "Rangiza ikizamini"
            : "Ikibazo gikurikira"}
          <ArrowRight className="size-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          className={secondaryButton}
          disabled={busy}
          onClick={sync}
        >
          <RefreshCw className="size-4" aria-hidden="true" />
          Vugurura
        </button>
      </div>
    </section>
  );
}