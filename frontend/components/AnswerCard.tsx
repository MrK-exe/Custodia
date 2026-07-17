"use client";

import type { Answer } from "@/lib/api";
import { dict, SUGGESTIONS } from "@/lib/dict";
import { formatDate, type Lang, docTitle } from "@/lib/format";

export default function AnswerCard({
  answer,
  lang,
  onSuggest,
}: {
  answer: Answer;
  lang: Lang;
  onSuggest: (q: string) => void;
}) {
  const t = dict[lang];

  if (answer.status !== "ok") {
    const message =
      answer.status === "no_results"
        ? t.noResults
        : answer.reason === "no_anchor"
          ? t.noAnchor
          : t.belowThreshold;
    return (
      <section className="col-12 tpanel">
        <header className="tpanel-head">
          <h3 className="tpanel-title">{t.answer}</h3>
        </header>
        <div className="tpanel-body" style={{ padding: 12 }}>
          <p className="empty" style={{ padding: 0 }}>{message}</p>
          <div className="suggested" style={{ marginTop: 10 }}>
            <span className="lbl" style={{ color: "var(--grey-mid)" }}>{t.tryThese}</span>
            {SUGGESTIONS[lang].slice(0, 3).map((s) => (
              <button
                key={s}
                onClick={() => onSuggest(s)}
                type="button"
                style={{ border: "1px solid var(--border)", color: "var(--grey-mid)", borderRadius: 6, padding: "3px 8px", background: "var(--card)", cursor: "pointer", fontSize: 11 }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="col-12 tpanel priority">
      <header className="tpanel-head">
        <h3 className="tpanel-title">{t.answer}</h3>
        <span className="tpanel-sub">· {t.extractiveNote}</span>
        <span className="doctag" style={{ marginInlineStart: "auto" }}>{answer.mode}</span>
      </header>
      <div className="tpanel-body">
        {answer.passages.map((p, i) => {
          const c = answer.citations[i];
          return (
            <div className="passage" key={p.doc_id}>
              <p className="quote">{p.text}</p>
              <div className="meta">
                <span className="ttag"><span className="dot brand" />{t.docTypes[p.doc_type] ?? p.doc_type}</span>
                {c?.url ? (
                  <a href={c.url} target="_blank" rel="noopener noreferrer">{c.publisher || docTitle(c, lang).slice(0, 40)}</a>
                ) : (
                  <span>{c?.publisher}</span>
                )}
                <span className="mono">{formatDate(c?.published_at, lang)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
