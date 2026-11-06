import Logo from "@/components/ui/Logo";
import AdminLoginForm from "@/components/admin/auth/AdminLoginForm";
import { ShieldCheck } from "lucide-react";

export default function AdminLoginPage() {
  return (
    <main
      id="main-content"
      lang="en"
      className="pattern-grid flex min-h-dvh items-center justify-center p-5 sm:p-10"
    >
      <div className="grid w-full max-w-5xl overflow-hidden rounded-[2rem] border border-ink/10 bg-surface shadow-card lg:grid-cols-2">
        <section className="relative hidden flex-col justify-between bg-brand-950 p-10 text-white lg:flex">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-brand-200">
              <ShieldCheck className="size-5" aria-hidden="true" />
              UMUHANDA ADMINISTRATION
            </div>
            <h1 className="mt-16 font-display text-4xl font-extrabold leading-tight tracking-tight">
              A trusted workspace for better road education.
            </h1>
            <p className="mt-6 text-sm leading-7 text-brand-100">
              Prepare a question bank grounded in your source PDF. Review
              carefully, publish with confidence, and keep administration
              secure.
            </p>
          </div>
          <p className="mt-12 text-xs leading-6 text-brand-200">
            The administrator workspace supports private PDF imports and source
            evidence review.
          </p>
        </section>
        <section className="p-6 sm:p-10">
          <Logo />
          <p className="mt-10 text-[0.65rem] font-bold uppercase tracking-[0.18em] text-brand-700">
            Administrator access
          </p>
          <h2 className="mt-3 font-display text-3xl font-extrabold tracking-tight">
            Welcome back.
          </h2>
          <p className="mt-3 text-sm leading-7 text-ink-muted">
            Sign in to manage the platform workspace.
          </p>
          <AdminLoginForm />
        </section>
      </div>
    </main>
  );
}
