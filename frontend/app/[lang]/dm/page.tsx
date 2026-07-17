import { notFound } from "next/navigation";
import { dict, isLang } from "@/lib/dict";
import DmPanel from "@/components/DmPanel";

export default async function DmPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = dict[lang];

  return (
    <main className="term-main" style={{ display: "block" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
        <h1 className="tpanel-title" style={{ fontSize: 13 }}>{t.dm}</h1>
        <a href={`/${lang}`}>{t.backToSearch}</a>
      </div>
      <DmPanel lang={lang} />
    </main>
  );
}
