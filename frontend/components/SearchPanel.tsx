"use client";

import { useEffect, useRef, useState } from "react";
import { api, type SearchResponse, type Dashboard as DashData } from "@/lib/api";
import { dict, SUGGESTIONS } from "@/lib/dict";
import type { RecentItem } from "@/lib/api";
import { docTitle, formatNumber, nav, type Lang } from "@/lib/format";
import AnswerCard from "./AnswerCard";
import DocResults from "./DocResults";
import EntityCard from "./EntityCard";
import Dashboard from "./Dashboard";
import MarketTicker from "./MarketTicker";

function SearchIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

export default function SearchPanel({ lang }: { lang: Lang }) {
  const t = dict[lang];
  const [query, setQuery] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warm, setWarm] = useState(true);
  const [recent, setRecent] = useState<RecentItem[]>([]);
  const [dash, setDash] = useState<DashData | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    api.health().then((h) => setWarm(h.warm_up.state === "ready" || h.model_loaded)).catch(() => setWarm(true));
    api.recent(6, lang).then((r) => setRecent(r.recent)).catch(() => {});
    api.dashboard(lang).then(setDash).catch(() => {});
  }, []);

  async function run(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    setQuery(trimmed);
    setLoading(true);
    setError(null);
    try {
      setData(await api.search({ query: trimmed, k: 8 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* dark command hero */}
      <section className="hero-command">
        <div className="hero-inner">
          <form
            className="command-box"
            onSubmit={(e) => {
              e.preventDefault();
              run(query);
            }}
          >
            <span className="glass"><SearchIcon /></span>
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t.searchPlaceholder}
              aria-label={t.searchButton}
              maxLength={200}
            />
            <div className="actions">
              <button type="submit" className="ask-btn" disabled={loading || !query.trim()}>
                <SearchIcon /> {loading ? t.searching : t.searchButton}
              </button>
            </div>
          </form>
          <div className="suggested">
            <span className="lbl">{recent.length ? t.recentLbl : t.suggested}</span>
            {(recent.length ? recent.map((r) => docTitle(r, lang)) : SUGGESTIONS[lang]).slice(0, 5).map((q) => (
              <button key={q} onClick={() => run(q)} type="button" title={q}>
                {q.length > 46 ? q.slice(0, 46) + "…" : q}
              </button>
            ))}
          </div>

          {/* TRACKED FOR YOU — horizontal strip, above the ticker */}
          {dash && (
            <div className="hero-tracked">
              <span className="ht-lbl">{t.tracked}</span>
              <span className="ht-stat">
                <b className="mono pos">{formatNumber(dash.brief.total_documents, lang, 0)}</b> {t.docsIndexed}
              </span>
              <span className="ht-stat">
                <b className="mono" style={{ color: "var(--amber)" }}>{formatNumber(dash.brief.tagged_documents, lang, 0)}</b> {t.taggedDocs}
              </span>
              <span className="ht-stat">
                <b className="mono" style={{ color: "var(--brand-2, #6ea8fe)" }}>{dash.trending.length}</b> {t.companiesCovered}
              </span>
            </div>
          )}
        </div>

        {/* MARKET PULSE — near-full-width revolving banner; the split between the
            dark search hero and the white analytics grid below it */}
        {dash && <MarketTicker lang={lang} summary={t.pulseHeadline} items={dash.brief.latest} />}
      </section>

      <main className="term-main">
        {!warm && !data && (
          <div className="col-12 empty" style={{ textAlign: "center" }}>{t.warmingUp}</div>
        )}

        {loading && (
          <div className="col-12 tpanel">
            <div className="tpanel-body" style={{ padding: 16 }}>
              <div className="skeleton" style={{ width: "35%", marginBottom: 12 }} />
              <div className="skeleton" style={{ width: "92%", marginBottom: 7 }} />
              <div className="skeleton" style={{ width: "84%" }} />
            </div>
          </div>
        )}

        {error && (
          <div className="col-12 tpanel">
            <div className="tpanel-body" style={{ padding: 16 }}>
              <span className="badge amber">{t.error}</span>
              <p className="empty">{error}</p>
            </div>
          </div>
        )}

        {data && !loading && (
          <>
            <div className="col-12 resbar">
              <span className="mono" style={{ color: "var(--grey-mid)", fontSize: 12 }}>“{data.query}”</span>
              <a className="ask-btn" style={{ height: 30, textDecoration: "none" }}
                 href={nav(`/${lang}/research?q=${encodeURIComponent(data.query)}`)}>
                {t.deepResearchBtn} ›
              </a>
            </div>
            {data.entity && data.entity.match !== "prefix" && (
              <EntityCard entity={data.entity} lang={lang} />
            )}
            {!(data.entity?.match === "exact" && data.answer.status !== "ok") && (
              <AnswerCard answer={data.answer} lang={lang} onSuggest={run} />
            )}
            {data.entity && data.entity.match === "prefix" && (
              <EntityCard entity={data.entity} lang={lang} />
            )}
            <DocResults results={data.results} lang={lang} />
          </>
        )}

        {!data && !loading && !error && <Dashboard lang={lang} />}
      </main>
    </>
  );
}
