"use client";

import { useState } from "react";

import type { SeriesPoint, SectorHeat } from "@/lib/api";
import { dict } from "@/lib/dict";
import { formatNumber, type Lang } from "@/lib/format";

/** All charts are inline SVG: no chart library, no CDN, offline-safe, and canvas-free
 *  so RTL never mirrors the axes. Matches Lovable's inline-SVG sparkline approach. */

export function Sparkline({ data, up, w = 68, h = 20 }: { data: (number | null)[]; up: boolean; w?: number; h?: number }) {
  const vals = data.filter((v): v is number => v !== null);
  if (vals.length < 2) return <svg width={w} height={h} />;
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
  const step = w / (vals.length - 1);
  const pts = vals.map((v, i) => `${(i * step).toFixed(1)},${(h - ((v - min) / span) * (h - 2) - 1).toFixed(1)}`).join(" ");
  return (
    <svg width={w} height={h} style={{ flexShrink: 0, display: "block" }}>
      <polyline points={pts} fill="none" stroke={up ? "var(--pos)" : "var(--neg)"} strokeWidth="1.3" />
    </svg>
  );
}

export function PriceChart({ points, lang, height = 240 }: { points: SeriesPoint[]; lang: Lang; height?: number }) {
  const t = dict[lang];
  const rows = points.filter((p) => p.close !== null);
  if (rows.length < 2) return <div className="empty">{t.noData}</div>;

  const W = 900, H = height, padT = 12, padB = 22, padX = 8;
  const closes = rows.map((p) => p.close as number);
  const lows = rows.map((p) => p.low ?? (p.close as number));
  const highs = rows.map((p) => p.high ?? (p.close as number));
  const min = Math.min(...lows), max = Math.max(...highs), span = max - min || 1;
  const x = (i: number) => padX + (i / (rows.length - 1)) * (W - padX * 2);
  const y = (v: number) => padT + (1 - (v - min) / span) * (H - padT - padB);

  const line = (key: "close" | "sma20" | "sma50") =>
    rows
      .map((p, i) => (p[key] === null ? null : `${x(i).toFixed(1)},${y(p[key] as number).toFixed(1)}`))
      .filter(Boolean)
      .join(" ");

  const areaPts = rows.map((p, i) => `${x(i).toFixed(1)},${y(p.close as number).toFixed(1)}`);
  const area = `${padX},${y(min)} ${areaPts.join(" ")} ${x(rows.length - 1)},${y(min)}`;
  const up = (closes[closes.length - 1] ?? 0) >= (closes[0] ?? 0);
  const stroke = up ? "var(--pos)" : "var(--neg)";

  // ~6 date ticks
  const ticks = Array.from({ length: 6 }, (_, k) => Math.round((k / 5) * (rows.length - 1)));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" style={{ display: "block" }}>
      <defs>
        <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.18" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 0.25, 0.5, 0.75, 1].map((f) => (
        <line key={f} x1={padX} x2={W - padX} y1={padT + f * (H - padT - padB)} y2={padT + f * (H - padT - padB)}
          stroke="var(--border)" strokeWidth="1" />
      ))}
      <polygon points={area} fill="url(#areaFill)" />
      <polyline points={line("close")} fill="none" stroke={stroke} strokeWidth="1.6" />
      {rows.some((p) => p.sma50 !== null) && (
        <polyline points={line("sma50")} fill="none" stroke="var(--violet)" strokeWidth="1.1" strokeDasharray="4 3" opacity="0.8" />
      )}
      {rows.some((p) => p.sma20 !== null) && (
        <polyline points={line("sma20")} fill="none" stroke="var(--amber)" strokeWidth="1.1" strokeDasharray="4 3" opacity="0.8" />
      )}
      {ticks.map((i) => (
        <text key={i} x={x(i)} y={H - 6} fontSize="9" fill="var(--grey-mid)"
          textAnchor={i === 0 ? "start" : i === rows.length - 1 ? "end" : "middle"}
          fontFamily="var(--font-mono)">
          {rows[i].date.slice(2)}
        </text>
      ))}
      <text x={W - padX} y={padT + 8} fontSize="10" fill="var(--grey-mid)" textAnchor="end" fontFamily="var(--font-mono)">
        {formatNumber(max, lang)}
      </text>
      <text x={W - padX} y={H - padB - 2} fontSize="10" fill="var(--grey-mid)" textAnchor="end" fontFamily="var(--font-mono)">
        {formatNumber(min, lang)}
      </text>
    </svg>
  );
}

export function Heatmap({ sectors, lang }: { sectors: SectorHeat[]; lang: Lang }) {
  const total = sectors.reduce((s, x) => s + x.weight, 0) || 1;
  const color = (c: number) => {
    const intensity = Math.min(Math.abs(c) / 12, 1);
    const [r, g, b] = c >= 0 ? [22, 163, 74] : [220, 38, 38];
    return `rgba(${r},${g},${b},${0.15 + intensity * 0.7})`;
  };
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, padding: 8, height: 250 }}>
      {sectors.map((s) => {
        const pct = (s.weight / total) * 100;
        return (
          <div
            key={s.sector_en}
            style={{
              background: color(s.change),
              flex: `${pct} 1 30%`,
              minWidth: 92,
              minHeight: 58,
              borderRadius: 6,
              padding: 8,
              color: "#fff",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              overflow: "hidden",
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 600, lineHeight: 1.15, textShadow: "0 1px 2px rgba(0,0,0,.3)" }}>
              {lang === "ar" ? s.sector_ar : s.sector_en}
            </div>
            <div className="mono" style={{ fontSize: 13, fontWeight: 700, textShadow: "0 1px 2px rgba(0,0,0,.3)" }}>
              {s.change >= 0 ? "+" : ""}{s.change.toFixed(2)}%
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function RangeChart({ points, lang, height = 260 }: { points: SeriesPoint[]; lang: Lang; height?: number }) {
  const RANGES: [string, number][] = [["1M", 21], ["3M", 63], ["6M", 126], ["ALL", 9999]];
  const [range, setRange] = useState(63);
  const sliced = range >= points.length ? points : points.slice(-range);
  return (
    <div>
      <div className="rangetabs">
        {RANGES.map(([label, n]) => (
          <button key={label} className={`rangetab${range === n ? " on" : ""}`} onClick={() => setRange(n)}>
            {label}
          </button>
        ))}
      </div>
      <PriceChart points={sliced} lang={lang} height={height} />
    </div>
  );
}
