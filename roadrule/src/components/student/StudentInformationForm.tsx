import { useRef, useState, type FormEvent } from "react";
import { AlertCircle, ArrowRight } from "lucide-react";

import type { StudentInformation } from "@/features/onboarding/types";
import {
  validateStudent,
  type StudentErrors,
} from "@/features/onboarding/validation";

type Props = {
  value: StudentInformation;
  pending?: boolean;
  onChange: (value: StudentInformation) => void;
  onContinue: (value: StudentInformation) => void;
};

/**
 * Classic student form — same two-color style as the rest of the site:
 *  - brand-800 → design (borders, icons, button)
 *  - ink       → writing
 * Errors are shown with an icon, bold text and a thicker border (no red).
 */
const labelClass = "block text-sm font-semibold text-ink";

const inputClass =
  "mt-2 block h-12 w-full border border-brand-800 bg-white px-4 text-base text-ink placeholder:text-ink/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-800 focus-visible:ring-offset-2 aria-[invalid=true]:border-2";

const errorClass = "mt-2 flex items-start gap-2 text-sm font-semibold text-ink";

export default function StudentInformationForm({
  value,
  onChange,
  onContinue,
  pending = false,
}: Props) {
  const [errors, setErrors] = useState<StudentErrors>({});
  const nameRef = useRef<HTMLInputElement>(null);
  const phoneRef = useRef<HTMLInputElement>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const result = validateStudent(value);
    setErrors(result.errors);
    if (result.student) onContinue(result.student);
    else (result.errors.fullName ? nameRef : phoneRef).current?.focus();
  }

  return (
    <form
      aria-busy={pending}
      noValidate
      onSubmit={submit}
      className="space-y-6"
    >
      {/* Full name */}
      <div>
        <label htmlFor="full-name" className={labelClass}>
          Amazina yawe yose
        </label>
        <input
          ref={nameRef}
          id="full-name"
          name="fullName"
          autoComplete="name"
          required
          disabled={pending}
          maxLength={120}
          value={value.fullName}
          onChange={(e) => {
            onChange({ ...value, fullName: e.target.value });
            setErrors({ ...errors, fullName: undefined });
          }}
          aria-invalid={!!errors.fullName}
          aria-describedby={errors.fullName ? "name-error" : undefined}
          className={inputClass}
        />
        {errors.fullName && (
          <p id="name-error" className={errorClass}>
            <AlertCircle
              className="mt-0.5 size-4 shrink-0 text-brand-800"
              aria-hidden="true"
            />
            {errors.fullName}
          </p>
        )}
      </div>

      {/* Phone number */}
      <div>
        <label htmlFor="phone-number" className={labelClass}>
          Nimero ya telefoni
        </label>
        <input
          ref={phoneRef}
          id="phone-number"
          name="phoneNumber"
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          required
          disabled={pending}
          maxLength={30}
          value={value.phoneNumber}
          onChange={(e) => {
            onChange({ ...value, phoneNumber: e.target.value });
            setErrors({ ...errors, phoneNumber: undefined });
          }}
          aria-invalid={!!errors.phoneNumber}
          aria-describedby={`phone-hint${errors.phoneNumber ? " phone-error" : ""}`}
          className={inputClass}
          placeholder="0781234567"
        />
        <p id="phone-hint" className="mt-2 text-sm text-ink">
          Koresha nimero yo mu Rwanda: 07XXXXXXXX cyangwa +2507XXXXXXXX.
        </p>
        {errors.phoneNumber && (
          <p id="phone-error" className={errorClass}>
            <AlertCircle
              className="mt-0.5 size-4 shrink-0 text-brand-800"
              aria-hidden="true"
            />
            {errors.phoneNumber}
          </p>
        )}
      </div>

      <button
        type="submit"
        disabled={pending}
        className="inline-flex h-12 w-full items-center justify-center gap-2 border border-brand-800 bg-brand-800 px-8 text-sm font-semibold text-white transition-colors duration-200 hover:bg-white hover:text-brand-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-800 focus-visible:ring-offset-2 sm:w-auto"
      >
        {pending ? "Turimo kubika amakuru…" : "Komeza ku kwishyura"}
        <ArrowRight className="size-4" aria-hidden="true" />
      </button>
    </form>
  );
}
