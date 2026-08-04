"use client";

import { useEffect, useState } from "react";
import { api, type Dashboard as DashData } from "@/lib/api";
import { dict } from "@/lib/dict";
import { formatNumber, nav, type Lang } from "@/lib/format";

/** Demo account page, rendered as a single centered card. Everything here is sample
 *  data for the demo persona and is badged as such; the only live part is the
 *  watchlist, which reuses the real Portfolio Monitor set so each ticker still
 *  clicks through to its terminal. */
export default function AccountView({ lang }: { lang: Lang }) {
  const t = dict[lang];
  const a = t.account;
  const [dash, setDash] = useState<DashData | null>(null);

  useEffect(() => {
    api.dashboard(lang).then(setDash).catch(() => {});
  }, []);

  const company = (ticker: string) => nav(`/${lang}/company/${ticker}`);
  const initials = lang === "ar" ? "مب" : "IN";

  return (
    <main className="acct-wrap">
      <div className="acct-card">
        {/* identity header */}
        <div className="acct-card-head">
          <span className="acct-avatar">{initials}</span>
          <div className="acct-idmain">
            <div className="acct-name">{a.personaName}</div>
            <div className="acct-firm">{a.firm} · {a.seat}</div>
          </div>
          <div className="acct-idside">
            <span className="badge amber">{a.demoBadge}</span>
            <span className="acct-licence-pill"><span className="ent-dot pos" /> {a.plan} · {a.licenceStatus}</span>
          </div>
        </div>

        {/* licence + billing */}
        <div className="acct-sec acct-cols">
          <div>
            <div className="acct-sec-h">{a.licenceLabel}</div>
            <div className="kv"><span className="kv-k">{a.licenceLabel}</span><span className="kv-v">{a.plan}</span></div>
            <div className="kv"><span className="kv-k">{a.firmLabel}</span><span className="kv-v">{a.firm}</span></div>
            <div className="kv"><span className="kv-k">{a.seatLabel}</span><span className="kv-v">{a.seat}</span></div>
            <p className="acct-note">{a.licenceNote}</p>
          </div>
          <div>
            <div className="acct-sec-h">{a.renewalLabel}</div>
            <div className="kv"><span className="kv-k">{a.renewalOn}</span><span className="kv-v mono">{a.renewalDate}</span></div>
            <div className="kv"><span className="kv-k">{a.seatsLabel}</span><span className="kv-v">{a.seatsVal}</span></div>
            <div className="kv"><span className="kv-k">{a.billingOwnerLabel}</span><span className="kv-v">{a.personaName}</span></div>
          </div>
        </div>

        {/* data entitlements — honest about the demo's real limits */}
        <div className="acct-sec">
          <div className="acct-sec-h">{a.entitlementsLabel}</div>
          <div className="acct-cols">
            <div>
              <div className="ent-group-h">{a.entLiveLabel}</div>
              {a.entLive.map((x) => (
                <div className="ent-row" key={x}><span className="ent-dot pos" />{x}</div>
              ))}
            </div>
            <div>
              <div className="ent-group-h locked">{a.entLockedLabel}</div>
              {a.entLocked.map((x) => (
                <div className="ent-row locked" key={x}><span className="ent-dot amber" />{x}</div>
              ))}
            </div>
          </div>
        </div>

        {/* watchlist — reuse the portfolio monitor set, click-through */}
        <div className="acct-sec">
          <div className="acct-sec-h">{a.watchlistLabel} <span className="acct-sec-sub">· {a.watchlistNote}</span></div>
          {!dash ? (
            <div className="empty" style={{ padding: "8px 0" }}>{t.warmingUp}</div>
          ) : (
            dash.watchlist.map((w) => (
              <a href={company(w.ticker)} key={w.ticker} className="kv" style={{ color: "inherit", textDecoration: "none" }}>
                <span className="kv-k">
                  <span className="mono" style={{ fontWeight: 600 }}>{w.ticker}</span> {lang === "ar" ? w.name_ar : w.name_en}
                </span>
                <span className="kv-v mono">{formatNumber(w.last, lang)}</span>
              </a>
            ))
          )}
        </div>

        {/* saved searches + alerts */}
        <div className="acct-sec acct-cols">
          <div>
            <div className="acct-sec-h">{a.savedLabel}</div>
            {a.savedSearches.map((q) => (
              <a key={q} href={nav(`/${lang}/research?q=${encodeURIComponent(q)}`)} className="acct-chiprow">
                <span className="acct-chip-ico">⌕</span>{q}
              </a>
            ))}
          </div>
          <div>
            <div className="acct-sec-h">{a.alertsLabel}</div>
            {a.alerts.map((q) => (
              <div key={q} className="acct-chiprow"><span className="acct-chip-ico amber">◔</span>{q}</div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
