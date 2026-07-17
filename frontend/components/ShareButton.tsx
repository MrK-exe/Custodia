"use client";

import { useEffect, useRef, useState } from "react";
import { api, type DmThreadSummary } from "@/lib/api";
import { dict } from "@/lib/dict";
import type { Lang } from "@/lib/format";

/** Share a document into a DM thread. This is the join between the two halves of
 *  the product: search finds it, DM is how it reaches a colleague. */
export default function ShareButton({ docId, lang }: { docId: number; lang: Lang }) {
  const t = dict[lang];
  const [open, setOpen] = useState(false);
  const [threads, setThreads] = useState<DmThreadSummary[] | null>(null);
  const [sent, setSent] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    if (!threads) api.dmThreads().then((d) => setThreads(d.threads)).catch(() => setThreads([]));
    const away = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open, threads]);

  async function share(threadId: number) {
    try {
      await api.dmSend(threadId, { doc_id: docId });
      setSent(true);
      setOpen(false);
      setTimeout(() => setSent(false), 2200);
    } catch {
      setOpen(false);
    }
  }

  if (sent) return <span className="badge brand">{t.shared}</span>;

  return (
    <div ref={box} style={{ position: "relative", display: "inline-block" }}>
      <button
        className="linkish"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={t.share}
      >
        {t.share}
      </button>
      {open && (
        <div className="pop">
          <p className="pophead">{t.shareTo}</p>
          {threads === null ? (
            <div className="skeleton" style={{ width: 120 }} />
          ) : (
            threads.map((th) => (
              <button key={th.id} className="popitem" onClick={() => share(th.id)}>
                {lang === "ar" ? th.persona.name_ar : th.persona.name_en}
                <span>{lang === "ar" ? th.persona.role_ar : th.persona.role_en}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
