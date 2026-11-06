import type { Metadata } from "next";
import Container from "@/components/ui/Container";
import ExamEntryShell from "@/components/exam/ExamEntryShell";
export const metadata: Metadata = { title: "Kwitegura ikizamini", robots: { index: false, follow: false } };
/** Static entry shell. The authenticated API supplies readiness and the current question. */
export default function ExamPage() {
  return <Container className="py-12 sm:py-20"><ExamEntryShell /></Container>;
}
