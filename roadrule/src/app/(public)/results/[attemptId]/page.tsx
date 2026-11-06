import { Suspense } from "react";
import ResultPanel from "@/components/exam/ResultPanel";

async function Result({ params }: { params: Promise<{ attemptId: string }> }) {
  const { attemptId } = await params;
  return <ResultPanel key={attemptId} attemptId={attemptId} />;
}

export default function Page({
  params,
}: {
  params: Promise<{ attemptId: string }>;
}) {
  return (
    <Suspense fallback={<p role="status">Turimo gushaka ibisubizo…</p>}>
      <Result params={params} />
    </Suspense>
  );
}
