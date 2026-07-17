"use client";

import { useEffect, useState } from "react";
import { api, type Health } from "@/lib/api";
import { dict } from "@/lib/dict";
import type { Lang } from "@/lib/format";

/** The live bits of the terminal chrome: a real Riyadh clock and the real indexed
 *  document count. No fabricated ticker tape: the Lovable mockup shows invented
 *  TASI/Brent/USD-SAR values, and inventing market numbers is the one thing this
 *  build will not do. */
export default function StatusStrip({ lang, variant }: { lang: Lang; variant: "bar" | "foot" }) {
  const t = dict[lang];
  const [clock, setClock] = useState("");
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    const tick = () =>
      setClock(
        new Intl.DateTimeFormat("en-US-u-ca-gregory-nu-latn", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
          timeZone: "Asia/Riyadh",
        }).format(new Date()),
      );
    tick();
    const id = setInterval(tick, 30000);
    api.health().then(setHealth).catch(() => {});
    return () => clearInterval(id);
  }, []);

  const docs = health ? new Intl.NumberFormat("en-US").format(health.documents) : "—";

  if (variant === "foot") {
    return (
      <>
        <span className="ok">● {t.connected}</span>
        <span>{t.workspace}: {t.terminal}</span>
        <span className="end mono">
          {docs} {t.docsIndexed} · {t.updatedNow}
        </span>
      </>
    );
  }

  return (
    <span className="livewrap">
      <span className="livedot" />
      {t.live} · {t.riyadh} <span className="mono">{clock}</span>
    </span>
  );
}
