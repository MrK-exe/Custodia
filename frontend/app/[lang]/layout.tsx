import type { Metadata } from "next";
import { notFound } from "next/navigation";
import "../globals.css";
import { dict, isLang } from "@/lib/dict";
import LangToggle from "@/components/LangToggle";
import StatusStrip from "@/components/StatusStrip";
import { nav } from "@/lib/format";

export const dynamicParams = false;

export function generateStaticParams() {
  return [{ lang: "ar" }, { lang: "en" }];
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang } = await params;
  const t = isLang(lang) ? dict[lang] : dict.ar;
  return { title: t.title, description: t.tagline };
}

export default async function LangLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = dict[lang];

  return (
    <html lang={lang} dir={t.dir}>
      <body>
        {/* dark status bar */}
        <header className="statusbar">
          <div className="statusbar-inner">
            <a href={nav(`/${lang}`)} className="logo" style={{ textDecoration: "none", color: "inherit" }}>
              <span className="mark">C</span>
              <span className="nm">{t.brandName}</span>
              <span className="sub">/ {t.terminal}</span>
            </a>
            <span className="dotsep">·</span>
            <StatusStrip lang={lang} variant="bar" />
            <div className="right">
              <a href={nav(`/${lang}/dm`)} className="navlink">{t.dm}</a>
              <LangToggle lang={lang} />
              <a href={nav(`/${lang}/account`)} className="avatar" title={t.account.heading} aria-label={t.account.heading}>{lang === "ar" ? "مب" : "IN"}</a>
            </div>
          </div>
        </header>

        {children}

        {/* dark status footer */}
        <footer className="statusfoot">
          <StatusStrip lang={lang} variant="foot" />
        </footer>
      </body>
    </html>
  );
}
