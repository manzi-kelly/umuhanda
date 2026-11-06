import AdminSection from "@/components/admin/layout/AdminSection";
import UnavailableWorkspace from "@/components/admin/questions/UnavailableWorkspace";

export default function Page() {
  return <AdminSection eyebrow='Student records' title='Students' description="A protected workspace reserved for the next platform capabilities."><UnavailableWorkspace title='Student directory unavailable' detail='Student records exist in the backend. The dashboard shows a real aggregate count; a personal-data directory is not implemented here.' /></AdminSection>;
}
