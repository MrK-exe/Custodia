"use client";

import type { BriefDoc } from "@/lib/api";
import { dict } from "@/lib/dict";
import { docTitle, type Lang } from "@/lib/format";

/** MARKET PULSE — a y2k news-anchor crawl. Leads with the pulse summary line, then
 *  revolves the latest indexed headlines. No fabricated ticker values (we never
 *  invent TASI/Brent numbers): every item is a real indexed document, click-through
 *  to its source. The track is duplicated so the scroll loops seamlessly; the copy
 *  is aria-hidden so a screen reader reads the headlines once. */
export default function MarketTicker({
  lang,
  summary,
  items,
}: {
  lang: Lang;
  summary: string;
  items: BriefDoc[];
}) {
  const t = dict[lang];
  const heads = items.slice(0, 8);
  if (!heads.length) return null;

  const Seq = ({ dup }: { dup: boolean }) => (
    <span className="ticker-seq" aria-hidden={dup}>
      <span className="ticker-lead">{summary}</span>
      {heads.map((n) => (
        <span className="ticker-item" key={`${dup ? "b" : "a"}-${n.id}`}>
          <span className="ticker-sep">›</span>
          {n.url ? (
            <a href={n.url} target="_blank" rel="noopener noreferrer">
              {docTitle(n, lang)}
            </a>
          ) : (
            <span>{docTitle(n, lang)}</span>
          )}
        </span>
      ))}
    </span>
  );

  return (
    <div className="market-ticker" aria-label={t.marketPulse}>
      <span className="ticker-tag">
        <span className="ticker-led" />
        {t.marketPulse}
      </span>
      <div className="ticker-viewport">
        <div className="ticker-track">
          <Seq dup={false} />
          <Seq dup={true} />
        </div>
      </div>
    </div>
  );
}
