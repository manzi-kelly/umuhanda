import { Suspense } from "react";
import ProtectedAdminLayout from "@/components/admin/layout/ProtectedAdminLayout";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<main id="main-content" className="grid min-h-dvh place-items-center text-sm text-ink-muted">Verifying administrator access…</main>}><ProtectedAdminLayout>{children}</ProtectedAdminLayout></Suspense>;
}
