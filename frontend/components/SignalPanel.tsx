"use client";

import type { Signal } from "@/lib/api";
import { dict } from "@/lib/dict";
import type { Lang } from "@/lib/format";

const TONE: Record<string, { color: string; bg: string }> = {
  bullish: { color: "var(--pos)", bg: "rgba(22,163,74,0.10)" },
  bearish: { color: "var(--neg)", bg: "rgba(220,38,38,0.10)" },
  neutral: { color: "var(--grey-mid)", bg: "var(--ui-wash)" },
  unknown: { color: "var(--grey-mid)", bg: "var(--ui-wash)" },
};

export default function SignalPanel({ signal, lang }: { signal: Signal; lang: Lang }) {
  const t = dict[lang];
  const tone = TONE[signal.label] ?? TONE.neutral;
  const label =
    signal.label === "bullish" ? t.bullish
    : signal.label === "bearish" ? t.bearish
    : signal.label === "neutral" ? t.neutralSig
    : t.noData;

  return (
    <section className="col-4 tpanel">
      <header className="tpanel-head">
        <h3 className="tpanel-title">{t.techSignal}</h3>
        <span className="doctag" style={{ marginInlineStart: "auto" }}>{t.technical}</span>
      </header>
      <div className="tpanel-body" style={{ padding: 12 }}>
        <div className="sig-headline" style={{ background: tone.bg, color: tone.color }}>
          <span className="sig-label">{label}</span>
          <span className="mono sig-score">{signal.score > 0 ? "+" : ""}{signal.score} / {signal.max_score}</span>
        </div>
        <div className="sig-components">
          {signal.components.map((c) => (
            <div className="sig-row" key={c.key}>
              <span className={`sig-dot ${c.vote > 0 ? "pos" : c.vote < 0 ? "neg" : "neu"}`}>
                {c.vote > 0 ? "▲" : c.vote < 0 ? "▼" : "■"}
              </span>
              <span className="sig-detail">{lang === "ar" ? c.detail_ar : c.detail_en}</span>
              {c.real && <span className="badge" style={{ fontSize: 9, padding: "0 5px" }}>{t.realShort}</span>}
            </div>
          ))}
        </div>
        {/* CMA-safe: this is a description of the series, not advice */}
        <p className="sig-disclaimer">{t.notAdvice}</p>
      </div>
    </section>
  );
}
