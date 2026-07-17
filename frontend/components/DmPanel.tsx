"use client";

import { useEffect, useRef, useState } from "react";
import { api, type DmThread, type DmThreadSummary } from "@/lib/api";
import { dict } from "@/lib/dict";
import { formatDate, relativeTime, type Lang, docTitle } from "@/lib/format";

export default function DmPanel({ lang }: { lang: Lang }) {
  const t = dict[lang];
  const [threads, setThreads] = useState<DmThreadSummary[] | null>(null);
  const [active, setActive] = useState<number | null>(null);
  const [thread, setThread] = useState<DmThread | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const tail = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .dmThreads()
      .then((d) => {
        setThreads(d.threads);
        if (d.threads.length && active === null) setActive(d.threads[0].id);
      })
      .catch(() => setThreads([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (active === null) return;
    setThread(null);
    api.dmThread(active).then(setThread).catch(() => setThread(null));
  }, [active]);

  useEffect(() => {
    tail.current?.scrollIntoView({ block: "end" });
  }, [thread]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim() || active === null) return;
    setSending(true);
    try {
      setThread(await api.dmSend(active, { body: draft }));
      setDraft("");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="dmgrid">
      <aside className="tpanel">
        <header className="tpanel-head">
          <h3 className="tpanel-title">{t.dm}</h3>
          <span className="doctag" style={{ marginInlineStart: "auto", background: "var(--amber)" }}>{t.dmSample}</span>
        </header>
        <div className="tpanel-body">
          {threads === null ? (
            <div style={{ padding: 12 }}><div className="skeleton" style={{ width: "80%" }} /></div>
          ) : (
            threads.map((th) => (
              <button
                key={th.id}
                className={`threadrow${th.id === active ? " on" : ""}`}
                onClick={() => setActive(th.id)}
              >
                <div className="nm">{lang === "ar" ? th.persona.name_ar : th.persona.name_en}</div>
                <div className="rl">{lang === "ar" ? th.persona.role_ar : th.persona.role_en}</div>
              </button>
            ))
          )}
        </div>
      </aside>

      <section className="tpanel priority" style={{ minHeight: 360 }}>
        {thread === null ? (
          <div style={{ padding: 12 }}><div className="skeleton" style={{ width: "60%" }} /></div>
        ) : (
          <>
            <header className="tpanel-head">
              <h3 className="tpanel-title">{lang === "ar" ? thread.persona.name_ar : thread.persona.name_en}</h3>
              <span className="tpanel-sub">· {lang === "ar" ? thread.persona.role_ar : thread.persona.role_en}</span>
            </header>

            <div className="msgs">
              {thread.messages.length === 0 && <p className="empty">{t.dmEmpty}</p>}
              {thread.messages.map((m) => (
                <div key={m.id} className={`msg ${m.sender}`}>
                  {m.body && <p className="b">{m.body}</p>}
                  {m.document && (
                    <a className="card" href={m.document.url || "#"} target="_blank" rel="noopener noreferrer">
                      <span className="doctag">{t.docTypes[m.document.doc_type] ?? m.document.doc_type}</span>
                      <span className="ti">{docTitle(m.document, lang)}</span>
                      <span className="mt">{m.document.publisher} · {formatDate(m.document.published_at, lang)}</span>
                    </a>
                  )}
                  <span className="ts mono">{relativeTime(m.created_at, lang)}</span>
                </div>
              ))}
              <div ref={tail} />
            </div>

            <form className="composer" onSubmit={send}>
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={t.dmPlaceholder}
                maxLength={2000}
                aria-label={t.dmPlaceholder}
              />
              <button type="submit" disabled={sending || !draft.trim()}>{t.send}</button>
            </form>
          </>
        )}
      </section>
    </div>
  );
}
