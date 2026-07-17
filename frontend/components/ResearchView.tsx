"use client";

import { useEffect, useState } from "react";
import { api, type ResearchData } from "@/lib/api";
import { dict } from "@/lib/dict";
import { formatDate, type Lang, docTitle } from "@/lib/format";

export default function ResearchView({ query, lang }: { query: string; lang: Lang }) {
  const t = dict[lang];
  const [d, setD] = useState<ResearchData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setD(null);
    setError(null);
    if (!query) return;
    api.research(query).then(setD).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [query]);

  if (!query) {
    return <main className="term-main"><div className="col-12 empty" style={{ textAlign: "center", padding: 40 }}>{t.researchPrompt}</div></main>;
  }
  if (error) {
    return <main className="term-main"><div className="col-12 tpanel"><div className="tpanel-body" style={{ padding: 16 }}><span className="badge amber">{t.error}</span><p className="empty">{error}</p></div></div></main>;
  }
  if (!d) {
    return (
      <main className="term-main">
        <div className="col-12 tpanel" style={{ minHeight: 240 }}><div className="tpanel-body" style={{ padding: 16 }}>
          <div className="skeleton" style={{ width: "40%", marginBottom: 12 }} />
          <div className="skeleton" style={{ width: "90%", marginBottom: 6 }} />
          <div className="skeleton" style={{ width: "80%" }} />
        </div></div>
      </main>
    );
  }

  const a = d.answer;

  return (
    <main className="term-main">
      {/* research header */}
      <section className="col-12 tpanel priority">
        <header className="tpanel-head">
          <a href={`/${lang}`} style={{ color: "var(--grey-light)", fontSize: 12 }}>‹ {t.backToSearch}</a>
          <h3 className="tpanel-title">{t.deepResearch}</h3>
          <span className="tpanel-sub">· “{d.query}” · {d.result_count} {t.documents}</span>
        </header>
        {a.status === "ok" ? (
          <div className="tpanel-body">
            {a.passages.map((p, i) => {
              const c = a.citations[i];
              return (
                <div className="passage" key={p.doc_id}>
                  <p className="quote">{p.text}</p>
                  <div className="meta">
                    <span className="ttag"><span className="dot brand" />{t.docTypes[p.doc_type] ?? p.doc_type}</span>
                    {c?.url ? <a href={c.url} target="_blank" rel="noopener noreferrer">{c.publisher}</a> : <span>{c?.publisher}</span>}
                    <span className="mono">{formatDate(c?.published_at, lang)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="tpanel-body"><p className="empty">{t.belowThreshold}</p></div>
        )}
      </section>

      {/* companies implicated */}
      {d.entities.length > 0 && (
        <section className="col-4 tpanel">
          <header className="tpanel-head"><h3 className="tpanel-title">{t.companiesInvolved}</h3></header>
          <div className="tpanel-body">
            {d.entities.map((e) => (
              <a key={e.ticker} href={`/${lang}/company/${e.ticker}`} className="kv" style={{ color: "inherit", textDecoration: "none" }}>
                <span className="kv-k"><span className="mono" style={{ fontWeight: 600 }}>{e.ticker}</span> {lang === "ar" ? e.name_ar : e.name_en}</span>
                <span className="kv-v mono">{e.count}</span>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* timeline */}
      <section className={d.entities.length > 0 ? "col-8 tpanel" : "col-12 tpanel"}>
        <header className="tpanel-head"><h3 className="tpanel-title">{t.timeline}</h3>
          <span className="tpanel-sub mono">· {d.timeline.length}</span></header>
        <div className="tpanel-body">
          <ul className="feed">
            {d.timeline.map((e) => (
              <li className="feed-row" key={e.id}>
                <span className="feed-time mono" style={{ width: 92 }}>{formatDate(e.published_at, lang)}</span>
                <div className="feed-main">
                  <div className="feed-title">{e.url ? <a href={e.url} target="_blank" rel="noopener noreferrer">{docTitle(e, lang)}</a> : docTitle(e, lang)}</div>
                  <div className="feed-meta"><span className="feed-src">{e.publisher}</span></div>
                </div>
                <span className="ttag"><span className="dot brand" />{t.docTypes[e.doc_type] ?? e.doc_type}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* grouped by document type */}
      {d.groups.map((g) => (
        <section className="col-6 tpanel" key={g.doc_type}>
          <header className="tpanel-head">
            <span className="doctag">{t.docTypes[g.doc_type] ?? g.doc_type}</span>
            <h3 className="tpanel-title" style={{ marginInlineStart: 6 }}>{t.docTypes[g.doc_type] ?? g.doc_type}</h3>
            <span className="tpanel-sub mono">· {g.docs.length}</span>
          </header>
          <div className="tpanel-body">
            <ul className="feed">
              {g.docs.slice(0, 8).map((doc) => (
                <li className="feed-row" key={doc.id}>
                  <div className="feed-main">
                    <div className="feed-title">{doc.url ? <a href={doc.url} target="_blank" rel="noopener noreferrer">{docTitle(doc, lang)}</a> : docTitle(doc, lang)}</div>
                    <div className="feed-meta">
                      <span className="feed-src">{doc.publisher}</span>
                      <span className="mono" style={{ fontSize: 11, color: "var(--grey-mid)" }}>{formatDate(doc.published_at, lang)}</span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ))}
    </main>
  );
}
