"use client";

import { useEffect, useState } from "react";
import { api, type Company, type Envelope, type NewsDoc } from "@/lib/api";
import { dict } from "@/lib/dict";
import { formatDate, formatNumber, formatPercent, type Lang, docTitle, nav } from "@/lib/format";
import HonestyBadge from "./HonestyBadge";

export default function EntityCard({ entity, lang }: { entity: Company; lang: Lang }) {
  const t = dict[lang];
  const [news, setNews] = useState<NewsDoc[] | null>(null);
  const [quote, setQuote] = useState<Envelope<Record<string, unknown>> | null>(null);
  const [quoteFailed, setQuoteFailed] = useState(false);

  useEffect(() => {
    let live = true;
    setNews(null);
    setQuote(null);
    setQuoteFailed(false);
    api.news(entity.ticker, lang).then((d) => live && setNews(d.documents)).catch(() => live && setNews([]));
    api.quote(entity.ticker).then((q) => live && setQuote(q)).catch(() => live && setQuoteFailed(true));
    return () => {
      live = false;
    };
  }, [entity.ticker]);

  const raw = (quote?.data ?? {}) as Record<string, unknown>;
  const num = (k: string) => (typeof raw[k] === "number" ? (raw[k] as number) : null);
  const price = num("price") ?? num("last") ?? num("close");
  const change = num("change_percent") ?? num("changePercent") ?? num("change_pct");

  return (
    <section className="col-12 tpanel priority">
      <header className="tpanel-head">
        <span className="mono" style={{ fontSize: 11, fontWeight: 600 }}>{entity.ticker}</span>
        <h3 className="tpanel-title">{lang === "ar" ? entity.name_ar : entity.name_en}</h3>
        <span className="tpanel-sub">· {lang === "ar" ? entity.sector_ar : entity.sector_en}</span>
      </header>

      <div className="entity-top">
        <div>
          <div className="entity-sector">{t.sector}: {lang === "ar" ? entity.sector_ar : entity.sector_en}</div>
          <a className="ask-btn" style={{ height: 30, marginTop: 8, textDecoration: "none", display: "inline-flex" }}
             href={nav(`/${lang}/company/${entity.ticker}`)}>
            {t.openDashboard} ›
          </a>
        </div>
        <div style={{ textAlign: lang === "ar" ? "left" : "right" }}>
          {quoteFailed ? (
            <span className="badge amber">{t.error}</span>
          ) : quote ? (
            <>
              <div className="entity-px mono">
                {formatNumber(price, lang)}
                {change !== null && (
                  <span className={`mono ${change >= 0 ? "pos" : "neg"}`} style={{ fontSize: 14, marginInlineStart: 8 }}>
                    {change >= 0 ? "▲" : "▼"} {formatPercent(change, lang)}
                  </span>
                )}
              </div>
              <div style={{ marginTop: 4 }}><HonestyBadge env={quote} lang={lang} /></div>
            </>
          ) : (
            <div className="skeleton" style={{ width: 140, height: 26 }} />
          )}
        </div>
      </div>

      <div className="tpanel-body">
        <div className="tgrid-head" style={{ gridTemplateColumns: "1fr" }}>
          <span>{t.latestNews}</span>
        </div>
        {news === null ? (
          <ul className="feed">
            {[0, 1, 2].map((i) => (
              <li className="feed-row" key={i}>
                <div className="skeleton" style={{ width: `${70 - i * 8}%` }} />
              </li>
            ))}
          </ul>
        ) : news.length === 0 ? (
          <p className="empty">{t.noNews}</p>
        ) : (
          <ul className="feed">
            {news.slice(0, 6).map((d) => (
              <li className="feed-row" key={d.id}>
                <span className="doctag">{t.docTypes[d.doc_type] ?? d.doc_type}</span>
                <div className="feed-main">
                  <div className="feed-title">
                    {d.url ? (
                      <a href={d.url} target="_blank" rel="noopener noreferrer">{docTitle(d, lang)}</a>
                    ) : (
                      d.title
                    )}
                  </div>
                  <div className="feed-meta">
                    <span className="mono" style={{ fontSize: 11, color: "var(--grey-mid)" }}>{formatDate(d.published_at, lang)}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
