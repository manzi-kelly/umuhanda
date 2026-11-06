"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import StudentInformationForm from "@/components/student/StudentInformationForm";
import StudentStepIndicator from "@/components/student/StudentStepIndicator";
import PaymentMethodSelector from "@/components/payment/PaymentMethodSelector";
import {
  AccessRequestError,
  accessRequest,
  type AccessState,
} from "./access-client";
import type { StudentInformation } from "./types";

export default function OnboardingFlow() {
  const [student, setStudent] = useState<StudentInformation>({
    fullName: "",
    phoneNumber: "",
  });
  const [access, setAccess] = useState<AccessState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const submitted = useRef<StudentInformation | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const [retake, setRetake] = useState<boolean | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const requested =
      new URLSearchParams(window.location.search).get("retake") === "1";
    if (requested) {
      accessRequest<AccessState>("exam-access/me", undefined, controller.signal)
        .then(setAccess)
        .catch((failure: Error) => {
          if (!controller.signal.aborted) setError(failure.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setRetake(true);
        });
    } else {
      queueMicrotask(() => {
        if (!controller.signal.aborted) setRetake(false);
      });
    }
    return () => controller.abort();
  }, []);
  const step = access ? 2 : 1;
  useEffect(() => {
    if (step === 2) heading.current?.focus();
  }, [step]);

  async function continueWith(value: StudentInformation) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      if (
        submitted.current?.fullName !== value.fullName ||
        submitted.current?.phoneNumber !== value.phoneNumber
      ) {
        await accessRequest("students/sessions", value);
        submitted.current = value;
      }
      setStudent(value);
      setAccess(await accessRequest<AccessState>("exam-access/me"));
    } catch (error) {
      if (error instanceof AccessRequestError && error.status === 401)
        submitted.current = null;
      setError(error instanceof Error ? error.message : "Ongera ugerageze.");
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  if (retake === null) return <p role="status">Tegereza gato…</p>;
  if (retake && !access)
    return (
      <>
        <p role="alert">{error}</p>
        <Link href="/">Subira ahabanza</Link>
      </>
    );

  return (
    <>
      <StudentStepIndicator step={step} />
      <h1
        ref={heading}
        tabIndex={-1}
        className="mb-3 font-display text-3xl font-extrabold tracking-tight sm:text-4xl"
      >
        {step === 1 ? "Tangira n’amakuru yawe." : "Hitamo uko wishyura."}
      </h1>
      <p className="mb-8 text-sm leading-7 text-ink-soft">
        Nta konti, email cyangwa ijambo ry’ibanga bisabwa.
      </p>
      {error && (
        <p role="alert" className="mb-4 text-red-800">
          {error}
        </p>
      )}
      {access ? (
        <PaymentMethodSelector
          access={access}
          retake={retake}
          onEdit={retake ? undefined : () => setAccess(null)}
        />
      ) : (
        <StudentInformationForm
          value={student}
          onChange={setStudent}
          onContinue={continueWith}
          pending={busy}
        />
      )}
    </>
  );
}
