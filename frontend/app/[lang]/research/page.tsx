import { Suspense } from "react";
import { notFound } from "next/navigation";
import { isLang } from "@/lib/dict";
import ResearchView from "@/components/ResearchView";

// The query lives in ?q= and is read client-side (useSearchParams) so this route
// exports as a static shell. No server-side searchParams read (that would force it
// dynamic and break `output: export`).
export default async function ResearchPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  return (
    <Suspense>
      <ResearchView lang={lang} />
    </Suspense>
  );
}
