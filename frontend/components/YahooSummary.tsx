"use client";

import type { CompanyData } from "@/lib/api";
import { dict } from "@/lib/dict";
import { formatNumber, type Lang } from "@/lib/format";

/** Yahoo-Finance-style quote summary: the two-column stat card, built with our own
 *  real data (offline-safe, no external embed). Fields that need licensed
 *  fundamentals (market cap, P/E, EPS) are shown as "—" with an honest note rather
 *  than fabricated. */
function big(v: number | null, lang: Lang): string {
  if (v === null || !Number.isFinite(v)) return "—";
  const a = Math.abs(v);
  const nf = (n: number, d = 2) => new Intl.NumberFormat(lang === "ar" ? "ar-u-nu-latn" : "en-US", { maximumFractionDigits: d }).format(n);
  if (a >= 1e9) return nf(v / 1e9) + "B";
  if (a >= 1e6) return nf(v / 1e6) + "M";
  if (a >= 1e3) return nf(v / 1e3, 1) + "K";
  return nf(v, 0);
}

export default function YahooSummary({ d, lang }: { d: CompanyData; lang: Lang }) {
  const t = dict[lang];
  const raw = (d.quote?.data ?? {}) as Record<string, unknown>;
  const qn = (k: string) => (typeof raw[k] === "number" ? (raw[k] as number) : null);
  const s = d.series;

  const rows: [string, React.ReactNode, boolean?][] = [
    [t.prevClose, formatNumber(qn("previous_close"), lang)],
    [t.open_, formatNumber(qn("open"), lang)],
    [t.bid, qn("bid") !== null ? `${formatNumber(qn("bid"), lang)} × ${big(qn("bid_size"), lang)}` : "—"],
    [t.ask, qn("ask") !== null ? `${formatNumber(qn("ask"), lang)} × ${big(qn("ask_size"), lang)}` : "—"],
    [t.dayRange, qn("low") !== null ? `${formatNumber(qn("low"), lang)} – ${formatNumber(qn("high"), lang)}` : "—"],
    [t.week52, s ? `${formatNumber(s.low_52, lang)} – ${formatNumber(s.high_52, lang)}` : "—", true],
    [t.volume, big(qn("volume"), lang)],
    [t.turnover, `${big(qn("value"), lang)} SAR`],
    [t.marketCap, "—", false],
    [t.peRatio, "—", false],
    [t.eps, "—", false],
    [t.rsiLabel, s && d.signal.rsi !== null ? formatNumber(d.signal.rsi, lang, 1) : "—", true],
  ];

  return (
    <section className="col-7 tpanel">
      <header className="tpanel-head">
        <h3 className="tpanel-title">{t.summary}</h3>
        <span className="tpanel-sub">· {t.quoteSummary}</span>
        <span className="doctag" style={{ marginInlineStart: "auto", background: "var(--pos)" }}>{t.realShort}</span>
      </header>
      <div className="tpanel-body">
        <div className="ysum">
          {rows.map(([k, v, sample], i) => (
            <div className="ysum-cell" key={i}>
              <span className="ysum-k">{k}{sample ? <span style={{ color: "var(--amber)" }}> ~</span> : ""}</span>
              <span className="ysum-v mono">{v}</span>
            </div>
          ))}
        </div>
        <p className="ysum-note">{t.fundamentalsNote}</p>
      </div>
    </section>
  );
}
