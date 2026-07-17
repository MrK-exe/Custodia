import { notFound } from "next/navigation";
import { isLang } from "@/lib/dict";
import CompanyView from "@/components/CompanyView";

const WATCHLIST = ["2222", "1120", "7010", "2010", "1180", "2280", "4013", "1211"];

export function generateStaticParams() {
  return ["ar", "en"].flatMap((lang) => WATCHLIST.map((ticker) => ({ lang, ticker })));
}

export default async function CompanyPage({
  params,
}: {
  params: Promise<{ lang: string; ticker: string }>;
}) {
  const { lang, ticker } = await params;
  if (!isLang(lang) || !/^\d{4}$/.test(ticker)) notFound();
  return <CompanyView ticker={ticker} lang={lang} />;
}
