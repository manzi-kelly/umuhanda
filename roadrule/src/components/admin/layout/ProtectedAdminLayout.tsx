import { requireAdmin } from "@/features/admin/server";
import AdminShell from "./AdminShell";

export default async function ProtectedAdminLayout({ children }: { children: React.ReactNode }) {
  const admin = await requireAdmin();
  return <AdminShell admin={admin}>{children}</AdminShell>;
}
