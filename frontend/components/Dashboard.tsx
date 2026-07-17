"use client";

import { useEffect, useState } from "react";
import { api, type Dashboard as DashData } from "@/lib/api";
import { dict } from "@/lib/dict";
import { formatDate, formatNumber, type Lang, docTitle } from "@/lib/format";
import { Sparkline, Heatmap } from "./Charts";

export default function Dashboard({ lang }: { lang: Lang }) {
  const t = dict[lang];
  const [d, setD] = useState<DashData | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api.dashboard().then(setD).catch(() => setFailed(true));
  }, []);

  if (failed) return <div className="col-12 empty" style={{ textAlign: "center" }}>{t.error}</div>;
  if (!d) {
    return (
      <>
        {[7, 5, 7, 5].map((c, i) => (
          <div key={i} className={`col-${c} tpanel`} style={{ minHeight: 160 }}>
            <div className="tpanel-body" style={{ padding: 16 }}>
              <div className="skeleton" style={{ width: "60%", marginBottom: 10 }} />
              <div className="skeleton" style={{ width: "90%", marginBottom: 6 }} />
              <div className="skeleton" style={{ width: "80%" }} />
            </div>
          </div>
        ))}
      </>
    );
  }

  const company = (ticker: string) => `/${lang}/company/${ticker}`;

  return (
    <>
      {/* MARKET PULSE — real, derived by counting, no generated prose */}
      <section className="col-12 brief-hero">
        <div className="brief-glow" />
        <div className="brief-grid">
          <div className="brief-main">
            <div className="brief-badgerow">
              <span className="brief-badge">{t.marketPulse}</span>
              <span className="brief-when">{t.brandName} · {formatDate(Math.floor(Date.now() / 1000), lang)}</span>
            </div>
            <h2 className="brief-headline">{t.pulseHeadline}</h2>
            <ul className="brief-bullets">
              {d.brief.latest.slice(0, 4).map((n) => (
                <li key={n.id}>
                  <span className="arw">›</span>
                  {n.url ? <a href={n.url} target="_blank" rel="noopener noreferrer">{docTitle(n, lang)}</a> : docTitle(n, lang)}
                </li>
              ))}
            </ul>
          </div>
          <div className="brief-side">
            <div className="brief-side-h">{t.tracked}</div>
            <div className="brief-stat"><span className="mono pos">{formatNumber(d.brief.total_documents, lang, 0)}</span> {t.docsIndexed}</div>
            <div className="brief-stat"><span className="mono" style={{ color: "var(--amber)" }}>{formatNumber(d.brief.tagged_documents, lang, 0)}</span> {t.taggedDocs}</div>
            <div className="brief-stat"><span className="mono" style={{ color: "var(--brand-2, #6ea8fe)" }}>{d.trending.length}</span> {t.companiesCovered}</div>
          </div>
        </div>
      </section>

      {/* PORTFOLIO MONITOR — sample series, badged, clickable */}
      <section className="col-7 tpanel">
        <header className="tpanel-head">
          <h3 className="tpanel-title">{t.portfolio}</h3>
          <span className="tpanel-sub">· {`${d.watchlist.length} ${t.tickers}`}</span>
          <span className="doctag" style={{ marginInlineStart: "auto", background: "var(--pos)" }}>{t.realShort}</span>
        </header>
        <div className="tpanel-body">
          <div className="tgrid-head" style={{ gridTemplateColumns: "58px 1fr 76px 74px 68px" }}>
            <span>{t.ticker}</span><span>{t.company}</span><span className="tar">{t.last}</span><span className="tar">{t.chg}</span><span className="tar">{t.trend7}</span>
          </div>
          {d.watchlist.map((w, i) => {
            const up = (w.change ?? 0) >= 0;
            return (
              <a href={company(w.ticker)} key={w.ticker} className={`tgrid-row${i === 0 ? " first" : ""}`}
                style={{ gridTemplateColumns: "58px 1fr 76px 74px 68px", color: "inherit", textDecoration: "none" }}>
                <span className="mono" style={{ fontSize: 11, fontWeight: 600 }}>{w.ticker}</span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{lang === "ar" ? w.name_ar : w.name_en}</span>
                <span className="tar mono">{formatNumber(w.last, lang)}</span>
                <span className={`tar mono ${up ? "pos" : "neg"}`}>{up ? "▲" : "▼"} {Math.abs(w.change ?? 0).toFixed(2)}%</span>
                <span className="tar" style={{ display: "flex", justifyContent: "flex-end" }}><Sparkline data={w.spark} up={up} /></span>
              </a>
            );
          })}
        </div>
      </section>

      {/* SECTOR HEATMAP — sample */}
      <section className="col-5 tpanel">
        <header className="tpanel-head">
          <h3 className="tpanel-title">{t.sectorHeat}</h3>
          <span className="doctag" style={{ marginInlineStart: "auto", background: d.sectors[0]?.source === "live" ? "var(--pos)" : "var(--amber)" }}>{d.sectors[0]?.source === "live" ? t.realShort : t.sampleShort}</span>
        </header>
        <div className="tpanel-body">
          <Heatmap sectors={d.sectors} lang={lang} />
          <div className="heat-legend">
            <span>{t.sizeWeight}</span>
            <span className="heat-scale"><span className="neg">-</span><i /><span className="pos">+</span></span>
          </div>
        </div>
      </section>

      {/* NEWS & FILINGS — real */}
      <section className="col-7 tpanel">
        <header className="tpanel-head">
          <h3 className="tpanel-title">{t.newsFilings}</h3>
          <span className="tpanel-sub">· {t.liveCoverage}</span>
        </header>
        <div className="tpanel-body">
          <ul className="feed">
            {d.brief.latest.map((n) => (
              <li className="feed-row" key={n.id}>
                <span className="feed-time mono">{formatDate(n.published_at, lang)}</span>
                <div className="feed-main">
                  <div className="feed-title">
                    {n.url ? <a href={n.url} target="_blank" rel="noopener noreferrer">{docTitle(n, lang)}</a> : docTitle(n, lang)}
                  </div>
                  <div className="feed-meta">
                    <span className="ttag"><span className="dot brand" />{t.docTypes[n.doc_type] ?? n.doc_type}</span>
                    <span className="feed-src">{n.publisher}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* TRENDING — real, by mention count */}
      <section className="col-5 tpanel">
        <header className="tpanel-head">
          <h3 className="tpanel-title">{t.trendingTitle}</h3>
          <span className="tpanel-sub">· {t.byMentions}</span>
        </header>
        <div className="tpanel-body">
          <ul className="feed">
            {d.trending.map((x, i) => (
              <li key={x.ticker} className="feed-row" style={{ alignItems: "center" }}>
                <span className="mono" style={{ width: 22, color: "var(--grey-mid)", fontSize: 11 }}>{String(i + 1).padStart(2, "0")}</span>
                <a href={company(x.ticker)} className="feed-main" style={{ color: "inherit" }}>{lang === "ar" ? x.name_ar : x.name_en}</a>
                <span className="mono" style={{ fontSize: 11, color: "var(--grey-mid)" }}>{x.count} {t.mentions}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* CALENDAR — real dated corpus events */}
      <section className="col-12 tpanel">
        <header className="tpanel-head">
          <h3 className="tpanel-title">{t.timeline}</h3>
          <span className="tpanel-sub">· {t.fromCorpus}</span>
        </header>
        <div className="tpanel-body">
          <ul className="feed">
            {d.calendar.map((e) => (
              <li className="feed-row" key={e.id}>
                <span className="feed-time mono" style={{ width: 92 }}>{formatDate(e.published_at, lang)}</span>
                <div className="feed-main">
                  <div className="feed-title">
                    {e.url ? <a href={e.url} target="_blank" rel="noopener noreferrer">{docTitle(e, lang)}</a> : docTitle(e, lang)}
                  </div>
                </div>
                <span className="ttag"><span className="dot amber" />{t.docTypes[e.doc_type] ?? e.doc_type}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </>
  );
}
