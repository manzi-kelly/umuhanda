import AdminSection from "@/components/admin/layout/AdminSection";
import UnavailableWorkspace from "@/components/admin/questions/UnavailableWorkspace";

export default function Page() {
  return <AdminSection eyebrow='Workspace controls' title='Settings' description="A protected workspace reserved for the next platform capabilities."><UnavailableWorkspace title='Account and platform settings unavailable' detail='This phase provides secure login and logout. Account management, password recovery and platform configuration controls require a later approved implementation.' /></AdminSection>;
}
