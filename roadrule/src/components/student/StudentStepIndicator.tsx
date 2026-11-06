export default function StudentStepIndicator({ step }: { step: 1 | 2 }) {
  return <nav aria-label="Intambwe zo kwiyandikisha"><ol className="mb-8 grid grid-cols-2 gap-3 text-sm">{["Amakuru yawe", "Uburyo bwo kwishyura"].map((label, index) => <li key={label} aria-current={step === index + 1 ? "step" : undefined} className={`rounded-2xl border p-3 ${step === index + 1 ? "border-brand-700 bg-brand-50 font-semibold text-brand-900" : "border-ink/10 text-ink-muted"}`}><span className="mr-2">0{index + 1}</span>{label}</li>)}</ol></nav>;
}
