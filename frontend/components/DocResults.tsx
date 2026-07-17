"use client";

import type { SearchResult } from "@/lib/api";
import { dict } from "@/lib/dict";
import { formatDate, type Lang, docTitle } from "@/lib/format";
import ShareButton from "./ShareButton";

export default function DocResults({ results, lang }: { results: SearchResult[]; lang: Lang }) {
  const t = dict[lang];
  if (!results.length) return null;

  return (
    <section className="col-12 tpanel">
      <header className="tpanel-head">
        <h3 className="tpanel-title">{t.results}</h3>
        <span className="tpanel-sub mono">· {results.length}</span>
      </header>
      <div className="tpanel-body">
        <ul className="feed">
          {results.map((r) => (
            <li className="feed-row" key={r.id}>
              <span className="doctag">{t.docTypes[r.doc_type] ?? r.doc_type}</span>
              <div className="feed-main">
                <div className="feed-title">
                  {r.url ? (
                    <a href={r.url} target="_blank" rel="noopener noreferrer">{docTitle(r, lang)}</a>
                  ) : (
                    r.title
                  )}
                </div>
                <div className="feed-meta">
                  <span className="feed-src">{r.publisher}</span>
                  <span className="mono" style={{ fontSize: 11, color: "var(--grey-mid)" }}>{formatDate(r.published_at, lang)}</span>
                  <ShareButton docId={r.id} lang={lang} />
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
