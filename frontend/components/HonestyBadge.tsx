"use client";

import type { Envelope } from "@/lib/api";
import { dict } from "@/lib/dict";
import { formatTime, type Lang } from "@/lib/format";

/**
 * The delay and the staleness are the product's credibility, not a disclaimer to
 * hide. The backend states both explicitly in every market envelope, so nothing
 * here is inferred: `delayed` comes from the feed's own is_delayed flag, `stale`
 * means the live call failed and this is the last good value.
 */
export default function HonestyBadge({
  env,
  lang,
}: {
  env: Pick<Envelope<unknown>, "source" | "stale" | "delayed" | "as_of" | "fetched_at">;
  lang: Lang;
}) {
  const t = dict[lang];
  const label =
    env.source === "sample" ? t.sample : env.stale ? t.stale : env.source === "cache" ? t.stale : t.live;
  const tone = env.source === "sample" ? "amber" : env.stale ? "amber" : "brand";

  return (
    <span className="row-badges" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
      <span className={`badge ${tone}`}>{label}</span>
      {env.delayed && <span className="badge">{t.delayedLatn}</span>}
      <span className="badge">
        {t.asOf} <span className="num">{formatTime(env.fetched_at, lang)}</span>
      </span>
    </span>
  );
}
