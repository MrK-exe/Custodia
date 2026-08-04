"use client";

import { usePathname } from "next/navigation";
import { nav, type Lang } from "@/lib/format";

export default function LangToggle({ lang }: { lang: Lang }) {
  const pathname = usePathname();
  const other: Lang = lang === "ar" ? "en" : "ar";
  const href = nav(pathname.replace(/^\/(ar|en)/, `/${other}`) || `/${other}`);

  // Plain <a>, not <Link>: the document lang/dir is set by the layout, and a client
  // navigation would not swap direction. A full load is correct and costs nothing.
  return (
    <a className="chrome-toggle" href={href} hrefLang={other} aria-label={`Switch to ${other}`}>
      {other === "ar" ? "عربي" : "EN"}
    </a>
  );
}
