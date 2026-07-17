import type { Metadata } from "next";
import { notFound } from "next/navigation";
import "../globals.css";
import { dict, isLang } from "@/lib/dict";
import LangToggle from "@/components/LangToggle";
import StatusStrip from "@/components/StatusStrip";

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
            <a href={`/${lang}`} className="logo" style={{ textDecoration: "none", color: "inherit" }}>
              <span className="mark">ت</span>
              <span className="nm">{t.brandName}</span>
              <span className="sub">/ {t.terminal}</span>
            </a>
            <span className="dotsep">·</span>
            <StatusStrip lang={lang} variant="bar" />
            <div className="right">
              <a href={`/${lang}/dm`} className="navlink">{t.dm}</a>
              <LangToggle lang={lang} />
              <span className="avatar">{lang === "ar" ? "مب" : "IN"}</span>
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
