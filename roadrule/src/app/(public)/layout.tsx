import Header from "@/components/layout/Header";
import Footer from "@/components/layout/Footer";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return <><Header /><main id="main-content" className="flex-1">{children}</main><Footer /></>;
}
