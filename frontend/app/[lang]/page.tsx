import { notFound } from "next/navigation";
import { isLang } from "@/lib/dict";
import SearchPanel from "@/components/SearchPanel";

export default async function Page({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  return <SearchPanel lang={lang} />;
}
