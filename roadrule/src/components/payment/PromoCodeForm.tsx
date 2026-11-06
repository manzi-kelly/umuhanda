import { useRef, useState, type FormEvent } from "react";
type Props = { code: string; onChange: (code: string) => void; onApply: (code: string) => Promise<void>; busy: boolean };
export default function PromoCodeForm({ code, onChange, onApply, busy }: Props) {
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!code.trim()) { setError("Andika kode y’ubusonerwe wahawe."); input.current?.focus(); return; }
    setError(""); void onApply(code.trim());
  }
  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div>
        <label htmlFor="promo-code" className="form-label">Kode y’ubusonerwe</label>
        <input ref={input} id="promo-code" name="promoCode" autoComplete="off" spellCheck={false} maxLength={100} required disabled={busy}
          value={code} onChange={e => { onChange(e.target.value); setError(""); }}
          aria-invalid={!!error} aria-describedby={`promo-hint${error ? " promo-error" : ""}`} className="form-input" />
        <p id="promo-hint" className="mt-2 text-sm leading-6 text-ink-muted">Kode izagenzurwa na seriveri mbere yo gutanga uruhushya. Iyi serivisi ntiraboneka ubu.</p>
        {error && <p id="promo-error" className="form-error">{error}</p>}
      </div>
      <button type="submit" disabled={busy} className="form-button">{busy ? "Tegereza…" : "Koresha kode"}</button>
    </form>
  );
}
