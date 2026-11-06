"use client";
import { useActionState, useEffect, useRef } from "react";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { loginAdmin } from "@/features/admin/actions";
import type { AuthState } from "@/features/admin/types";

export default function AdminLoginForm() {
  const [state, action, pending] = useActionState<AuthState, FormData>(loginAdmin, {});
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  useEffect(() => { if (state.fields?.email) emailRef.current?.focus(); else if (state.fields?.password) passwordRef.current?.focus(); }, [state]);
  return <form action={action} noValidate className="mt-8 space-y-5">
    <div><label htmlFor="admin-email" className="form-label">Administrator email</label>
      <input ref={emailRef} id="admin-email" name="email" type="email" autoComplete="username" maxLength={254} required className="form-input" aria-invalid={!!state.fields?.email} aria-describedby={state.fields?.email ? "email-error" : undefined} />
      {state.fields?.email && <p id="email-error" className="form-error">{state.fields.email}</p>}</div>
    <div><label htmlFor="admin-password" className="form-label">Password</label>
      <input ref={passwordRef} id="admin-password" name="password" type="password" autoComplete="current-password" maxLength={256} required className="form-input" aria-invalid={!!state.fields?.password} aria-describedby={state.fields?.password ? "password-error" : undefined} />
      {state.fields?.password && <p id="password-error" className="form-error">{state.fields.password}</p>}</div>
    <div aria-live="polite" aria-atomic="true">{state.error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{state.error}</p>}</div>
    <button type="submit" disabled={pending} className="form-button w-full gap-2">{pending ? "Verifying accessâ€¦" : "Sign in securely"}<ArrowRight className="size-4" aria-hidden="true" /></button>
    <p className="flex gap-2 text-xs leading-6 text-ink-muted"><LockKeyhole className="mt-1 size-4 shrink-0" aria-hidden="true" />Administrator access only. Accounts are provisioned locally; public registration is unavailable.</p>
  </form>;
}
