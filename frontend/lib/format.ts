/**
 * Every number, date and percentage on screen goes through this file.
 *
 * Arabic locale formatting has two traps that only surface on someone else's
 * machine, which on demo day is the projector laptop:
 *
 *  1. "ar-SA" resolves to arab digits (٢٠٢٦) and embeds invisible U+061C marks
 *     around a minus sign. "ar" resolves to latn. The project's own scraped
 *     headlines use Western digits, and normalize_ar folds Arabic-Indic to
 *     Western, so the corpus is Western-digit throughout.
 *  2. "ar-SA" historically defaulted to the Islamic calendar. CLDR flipped it to
 *     gregory, so the rendering depends on the ICU build shipped with whatever
 *     Node/browser is running. A different machine can silently print ١٤٤٧-١٢-٠٣.
 *
 * Pinning the extensions is the only version-safe answer:
 *   -u-ca-gregory  force the Gregorian calendar
 *   -u-nu-latn     force Western digits
 */

const AR = "ar-u-ca-gregory-nu-latn";
const EN = "en-US-u-ca-gregory-nu-latn";

export type Lang = "ar" | "en";

const locale = (lang: Lang) => (lang === "ar" ? AR : EN);

export function formatNumber(value: number | null | undefined, lang: Lang, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(locale(lang), {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatPercent(value: number | null | undefined, lang: Lang): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  // Intl owns the sign and the % symbol. Hand-concatenating either is how the
  // minus ends up on the wrong side of the number in RTL.
  return new Intl.NumberFormat(locale(lang), {
    style: "percent",
    signDisplay: "exceptZero",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value / 100);
}

export function formatDate(epochSeconds: number | null | undefined, lang: Lang): string {
  // null is honest: 607 registry rows genuinely have no publication date, and
  // "unknown" must never render as today.
  if (!epochSeconds) return lang === "ar" ? "بدون تاريخ" : "no date";
  return new Intl.DateTimeFormat(locale(lang), {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(epochSeconds * 1000));
}

export function formatTime(epochSeconds: number | null | undefined, lang: Lang): string {
  if (!epochSeconds) return "—";
  return new Intl.DateTimeFormat(locale(lang), {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Riyadh",
  }).format(new Date(epochSeconds * 1000));
}

export function relativeTime(epochSeconds: number | null | undefined, lang: Lang): string {
  if (!epochSeconds) return lang === "ar" ? "بدون تاريخ" : "no date";
  const diff = Math.round((epochSeconds * 1000 - Date.now()) / 1000);
  const abs = Math.abs(diff);
  const rtf = new Intl.RelativeTimeFormat(locale(lang), { numeric: "auto" });
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  return rtf.format(Math.round(diff / 86400), "day");
}


/** Prefer the English title on the English UI, when one exists. Scraped Arabic news
 *  has no English title, so it stays in its source language (real, uncensored). */
export function docTitle(d: { title: string; title_en?: string | null }, lang: Lang): string {
  return lang === "en" && d.title_en ? d.title_en : d.title;
}

/** Prefix internal links with the deploy base path ("/Custodia" on GitHub Pages,
 *  "" for local/dev). Raw <a> tags are NOT basePath-prefixed by Next. */
const NAV_BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
export function nav(path: string): string {
  return NAV_BASE + path;
}
