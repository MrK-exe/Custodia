import { notFound } from "next/navigation";
import { isLang } from "@/lib/dict";
import ResearchView from "@/components/ResearchView";

export default async function ResearchPage({
  params,
  searchParams,
}: {
  params: Promise<{ lang: string }>;
  searchParams: Promise<{ q?: string }>;
}) {
  const { lang } = await params;
  const { q } = await searchParams;
  if (!isLang(lang)) notFound();
  return <ResearchView query={q ?? ""} lang={lang} />;
}
