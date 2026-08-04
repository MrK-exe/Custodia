"use client";

import { useEffect, useState } from "react";
import { api, type CompanyData } from "@/lib/api";
import { dict } from "@/lib/dict";
import { formatNumber, formatPercent, type Lang, docTitle, nav } from "@/lib/format";
import { RangeChart } from "./Charts";
import SignalPanel from "./SignalPanel";
import YahooSummary from "./YahooSummary";
import HonestyBadge from "./HonestyBadge";

function compact(v: number | null, lang: Lang): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  const abs = Math.abs(v);
  const nf = (n: number, d = 2) => new Intl.NumberFormat(lang === "ar" ? "ar-u-nu-latn" : "en-US", { maximumFractionDigits: d }).format(n);
  if (abs >= 1e9) return nf(v / 1e9) + "B";
  if (abs >= 1e6) return nf(v / 1e6) + "M";
  if (abs >= 1e3) return nf(v / 1e3, 1) + "K";
  return nf(v, 0);
}

export default function CompanyView({ ticker, lang }: { ticker: string; lang: Lang }) {
  const t = dict[lang];
  const [d, setD] = useState<CompanyData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setD(null);
    setError(null);
    api.company(ticker, lang).then(setD).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [ticker]);

  if (error) {
    return (
      <main className="term-main">
        <div className="col-12 tpanel"><div className="tpanel-body" style={{ padding: 16 }}>
          <span className="badge amber">{t.error}</span><p className="empty">{error}</p>
          <a href={nav(`/${lang}`)}>{t.backToSearch}</a>
        </div></div>
      </main>
    );
  }
  if (!d) {
    return (
      <main className="term-main">
        <div className="col-12 tpanel" style={{ minHeight: 300 }}>
          <div className="tpanel-body" style={{ padding: 16 }}>
            <div className="skeleton" style={{ width: "30%", marginBottom: 14 }} />
            <div className="skeleton" style={{ width: "100%", height: 200 }} />
          </div>
        </div>
      </main>
    );
  }

  const raw = (d.quote?.data ?? {}) as Record<string, unknown>;
  const qn = (k: string) => (typeof raw[k] === "number" ? (raw[k] as number) : null);
  const liq = (raw.liquidity ?? {}) as Record<string, number>;
  const price = qn("price") ?? qn("last") ?? qn("close") ?? d.series?.last ?? null;
  const change = qn("change_percent") ?? qn("changePercent");
  const s = d.series;
  const name = lang === "ar" ? d.entity.name_ar : d.entity.name_en;
  const sector = lang === "ar" ? d.entity.sector_ar : d.entity.sector_en;
  const perf = d.performance ?? {};

  const inV = liq.inflow_value ?? 0, outV = liq.outflow_value ?? 0;
  const flowTotal = inV + outV || 1;
  const inflowPct = (inV / flowTotal) * 100;
  const net = liq.net_value ?? inV - outV;

  return (
    <main className="term-main">
      {/* header + live price */}
      <section className="col-12 tpanel priority">
        <header className="tpanel-head">
          <a href={nav(`/${lang}`)} style={{ color: "var(--grey-light)", fontSize: 12 }}>‹ {t.backToSearch}</a>
          <span className="mono" style={{ fontSize: 11, fontWeight: 600, marginInlineStart: 8 }}>{d.entity.ticker}</span>
          <h3 className="tpanel-title">{name}</h3>
          <span className="tpanel-sub">· {sector}</span>
          {d.quote && <span style={{ marginInlineStart: "auto" }}><HonestyBadge env={d.quote} lang={lang} /></span>}
        </header>
        <div className="entity-top" style={{ alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <span className="entity-px mono">{formatNumber(price, lang)}</span>
            <span className="mono" style={{ color: "var(--grey-mid)", fontSize: 12 }}>SAR</span>
            {change !== null && (
              <span className={`mono ${change >= 0 ? "pos" : "neg"}`} style={{ fontSize: 16 }}>
                {change >= 0 ? "▲" : "▼"} {formatPercent(change, lang)}
              </span>
            )}
            {qn("change") !== null && (
              <span className={`mono ${(qn("change") ?? 0) >= 0 ? "pos" : "neg"}`} style={{ fontSize: 13 }}>
                ({(qn("change") ?? 0) >= 0 ? "+" : ""}{formatNumber(qn("change"), lang)})
              </span>
            )}
          </div>
          {!d.quote && <span className="badge amber">{t.quoteUnavailable}</span>}
        </div>
      </section>

      {/* price chart */}
      <section className="col-12 tpanel">
        <header className="tpanel-head">
          <h3 className="tpanel-title">{t.priceChart}</h3>
          <span className="tpanel-sub">· {t.smaLegend}</span>
          <span className="doctag" style={{ marginInlineStart: "auto", background: "var(--amber)" }}>{t.sampleShort}</span>
        </header>
        <div className="tpanel-body" style={{ padding: "8px 4px 0" }}>
          {s ? <RangeChart points={s.points} lang={lang} height={240} /> : <div className="empty">{t.noData}</div>}
          <div className="chart-legend">
            <span><i style={{ background: "var(--pos)" }} /> {t.close}</span>
            <span><i style={{ background: "var(--amber)" }} /> SMA20</span>
            <span><i style={{ background: "var(--violet)" }} /> SMA50</span>
            <span className="chart-note">{t.sampleNote}</span>
          </div>
        </div>
      </section>

      {/* MARKET DATA — all real, cache-first */}
      <section className="col-4 tpanel">
        <header className="tpanel-head"><h3 className="tpanel-title">{t.marketData}</h3>
          <span className="doctag" style={{ marginInlineStart: "auto", background: "var(--pos)" }}>{t.realShort}</span></header>
        <div className="tpanel-body">
          <Row k={t.open_} v={formatNumber(qn("open"), lang)} />
          <Row k={t.high} v={formatNumber(qn("high"), lang)} />
          <Row k={t.low} v={formatNumber(qn("low"), lang)} />
          <Row k={t.prevClose} v={formatNumber(qn("previous_close"), lang)} />
          <Row k={t.dayRange} v={qn("low") !== null ? `${formatNumber(qn("low"), lang)} – ${formatNumber(qn("high"), lang)}` : "—"} />
          <Row k={t.volume} v={compact(qn("volume"), lang)} />
          <Row k={t.turnover} v={`${compact(qn("value"), lang)}`} />
          <Row k={t.bid} v={qn("bid") !== null ? `${formatNumber(qn("bid"), lang)} × ${compact(qn("bid_size"), lang)}` : "—"} />
          <Row k={t.ask} v={qn("ask") !== null ? `${formatNumber(qn("ask"), lang)} × ${compact(qn("ask_size"), lang)}` : "—"} />
        </div>
      </section>

      {/* MONEY FLOW — real liquidity analytics */}
      <section className="col-4 tpanel">
        <header className="tpanel-head"><h3 className="tpanel-title">{t.moneyFlow}</h3>
          <span className="doctag" style={{ marginInlineStart: "auto", background: "var(--pos)" }}>{t.realShort}</span></header>
        <div className="tpanel-body" style={{ padding: 12 }}>
          {liq.inflow_value === undefined ? <p className="empty" style={{ padding: 0 }}>{t.noData}</p> : (
            <>
              <div className="flowbar">
                <div className="flowbar-in" style={{ width: `${inflowPct}%` }} />
                <div className="flowbar-out" style={{ width: `${100 - inflowPct}%` }} />
              </div>
              <div className="flowrow"><span className="pos">● {t.inflow}</span><span className="mono">{compact(inV, lang)} SAR</span></div>
              <div className="flowsub mono">{compact(liq.inflow_trades, lang)} {t.trades} · {compact(liq.inflow_volume, lang)} {t.shares}</div>
              <div className="flowrow"><span className="neg">● {t.outflow}</span><span className="mono">{compact(outV, lang)} SAR</span></div>
              <div className="flowsub mono">{compact(liq.outflow_trades, lang)} {t.trades} · {compact(liq.outflow_volume, lang)} {t.shares}</div>
              <div className="flowrow" style={{ borderTop: "1px solid var(--border)", paddingTop: 8, marginTop: 4 }}>
                <span style={{ fontWeight: 600 }}>{t.netFlow}</span>
                <span className={`mono ${net >= 0 ? "pos" : "neg"}`} style={{ fontWeight: 600 }}>{net >= 0 ? "+" : ""}{compact(net, lang)} SAR</span>
              </div>
            </>
          )}
        </div>
      </section>

      {/* TECHNICAL SIGNAL — descriptive, CMA-safe (not advice) */}
      <SignalPanel signal={d.signal} lang={lang} />

      {/* YAHOO-STYLE SUMMARY — our data, offline-safe */}
      <YahooSummary d={d} lang={lang} />

      {/* PERFORMANCE — 1D real, longer periods sample */}
      <section className="col-5 tpanel">
        <header className="tpanel-head"><h3 className="tpanel-title">{t.performance}</h3></header>
        <div className="tpanel-body">
          <PerfRow k={t.p1d} v={change} real lang={lang} />
          <PerfRow k={t.p5d} v={perf["5d"] ?? null} lang={lang} />
          <PerfRow k={t.p1m} v={perf["1m"] ?? null} lang={lang} />
          <PerfRow k={t.p3m} v={perf["3m"] ?? null} lang={lang} />
          <PerfRow k={t.p6m} v={perf["6m"] ?? null} lang={lang} />
          {s && <Row k={`${t.high} · ${t.low}`} v={`${formatNumber(s.high_52, lang)} · ${formatNumber(s.low_52, lang)}`} sample />}
        </div>
      </section>

      {/* news */}
      <section className="col-7 tpanel">
        <header className="tpanel-head"><h3 className="tpanel-title">{t.latestNews}</h3>
          <span className="tpanel-sub mono">· {d.news.length}</span></header>
        <div className="tpanel-body">
          {d.news.length === 0 ? <p className="empty">{t.noNews}</p> : (
            <ul className="feed">
              {d.news.map((n) => (
                <li className="feed-row" key={n.id}>
                  <span className="doctag">{t.docTypes[n.doc_type] ?? n.doc_type}</span>
                  <div className="feed-main">
                    <div className="feed-title">
                      {n.url ? <a href={n.url} target="_blank" rel="noopener noreferrer">{docTitle(n, lang)}</a> : docTitle(n, lang)}
                    </div>
                    <div className="feed-meta">
                      <span className="feed-src">{n.publisher}</span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {/* context — real corpus */}
      <section className="col-5 tpanel">
        <header className="tpanel-head"><h3 className="tpanel-title">{t.context}</h3>
          <span className="tpanel-sub">· {t.contextSub}</span></header>
        <div className="tpanel-body">
          {d.context.length === 0 ? <p className="empty">{t.noContext}</p> : (
            <ul className="feed">
              {d.context.map((c) => (
                <li className="feed-row" key={c.id}>
                  <span className="ttag"><span className="dot violet" />{t.docTypes[c.doc_type] ?? c.doc_type}</span>
                  <div className="feed-main">
                    <div className="feed-title">
                      {c.url ? <a href={c.url} target="_blank" rel="noopener noreferrer">{docTitle(c, lang)}</a> : docTitle(c, lang)}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}

function Row({ k, v, sample }: { k: string; v: React.ReactNode; sample?: boolean }) {
  return (
    <div className="kv">
      <span className="kv-k">{k}{sample ? <span style={{ color: "var(--amber)" }}> ~</span> : ""}</span>
      <span className="kv-v mono">{v}</span>
    </div>
  );
}

function PerfRow({ k, v, real, lang }: { k: string; v: number | null; real?: boolean; lang: Lang }) {
  return (
    <div className="kv">
      <span className="kv-k">{k}{real ? "" : <span style={{ color: "var(--amber)" }}> ~</span>}</span>
      <span className={`kv-v mono ${v === null ? "" : v >= 0 ? "pos" : "neg"}`}>
        {v === null ? "—" : formatPercent(v, lang)}
      </span>
    </div>
  );
}
