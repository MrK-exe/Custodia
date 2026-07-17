# KSA Market Intelligence 1.0 — Demo Runbook

Built 2026-07-17. Backend FastAPI + Next.js 16 frontend, Lovable terminal design.
Everything runs locally; only live quotes touch the network (SAHMK, cached).

## Start (two terminals)

Backend:
```
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
The 2.24 GB embedding model warms itself at startup on a background thread; wait for
`/api/health` to show `warm_up.state == "ready"` (about 3 s) before the first search.

Frontend (production mode, never `dev` — dev double-fetches under StrictMode and
would burn the SAHMK budget):
```
cd frontend
npx next build && npx next start -p 3000
```
Open http://127.0.0.1:3000 (redirects to /ar). Toggle EN/عربي top-right.

## Pre-demo checklist

- [ ] `curl http://127.0.0.1:8000/api/health` → `status ok`, `corpus_loaded true`,
      `warm_up.state ready`, `budget_remaining` high
- [ ] `backend/.venv/.../python.exe scripts/smoke.py` → 29/29, `SAHMK spent 0`
- [ ] **Rotate the SAHMK key** in the SAHMK dashboard (it transited chat) and put the
      new value in `backend/.env` only, then re-run one quote to reseed cache
- [ ] Rehearse off-hours (after 15:25 AST, or Fri/Sat) so cached quotes cost 0
- [ ] Run `scripts/prime_quotes.py` once (primes all 8 quotes: order book + money flow)

## Safe query list (every one backed by data that exists today)

Arabic:
- `عقد أرامكو مع هاليبرتون لتطوير الغاز`  (news, tagged 2222)
- `هجوم بقيق`  (geopolitics corpus, spa.gov.sa, 2019 — the differentiation moment)
- `رؤية السعودية 2030`  (mandate corpus)
- `نظام الشركات الجديد`  (law corpus)
- `نتائج المراعي الربع الثاني`  (news, 2280)
- `ارامكو`  (entity lookup: price card + news feed)

English (cross-lingual → returns Arabic sources):
- `aramco helicopter crash`  (the money moment)
- `stc dividends`, `saudi aramco ipo`, `vision 2030 economic reform`

Entity feeds that are clean: 2222, 2010, 2280, 7010, 4013, 1211, 1120.

## Do NOT

- Do not click the refresh path or run `refresh_all()` during the demo (18 min).
- Do not query anything expecting live intraday prices beyond the cached snapshot;
  quotes are 15-min delayed by license and badged as such.
- 1180 (SNB) entity feed has only ~4 real news docs; fine to show, thin.

## If something breaks

- SAHMK down / quota hit: quotes serve from cache with a stale badge automatically.
  Narrate it as the honesty feature. Never retry-hammer.
- Wifi down: search, answers, news, DM, the model, and fonts are all local. Only new
  quotes degrade to stale badges. Continue.
- Backend crash: restart uvicorn, then fire one search to reload the model before
  continuing.

## What is real vs sample

- Real: all documents (news, disclosures, CMA registries, the 58-doc curated corpus),
  entity routing, extractive answers with citations, publish dates.
- Sample / labeled: live quotes are 15-min delayed (badged); DM personas are seeded
  colleagues (badged "sample personas"). No fabricated market data anywhere.

## Dashboard + per-company (added)

- **Splash dashboard** (below the command search): Market Pulse (real doc counts +
  latest headlines), Portfolio Monitor with sparklines (SAMPLE), Sector Heatmap
  (SAMPLE), News & Filings (real), Trending Companies by mention count (real),
  Timeline of dated corpus events (real). Click any ticker → company page.
- **Company page** `/[lang]/company/{ticker}`: price chart with SMA20/SMA50 overlay
  (SAMPLE, anchored to the current price so the chart ends where the quote says),
  key stats, 12 real news items, and the real corpus Context (laws/mandates/
  ownership/geopolitics that mention the company). Try 2222 (rich context) and 7010.
- **Budget-safe**: the dashboard and company pages NEVER call SAHMK. Only the search
  EntityCard and /api/quote fetch, cache-first. `scripts/smoke.py` asserts browsing
  all 8 company pages spends 0 requests.
- **Sample data**: price history is a Cholesky-correlated simulated series
  (app/sample_data.py, generated at startup), because the free tier paywalls
  historical(). Every chart/heatmap/sparkline is badged "SAMPLE" / "تجريبي".

## Argaam-grade per-company market data (added)

The company page now shows what the Argaam Tadawul page shows, from the same real
Tadawul feed via SAHMK (verified field-for-field for stc: 43.18 / vol 1,487,894 /
turnover 64,278,611):
- **Market Data** (REAL): open, high, low, prev close, day range, volume, turnover,
  and the **order book** (bid/ask + sizes).
- **Money Flow** (REAL): inflow/outflow value, trades, shares, and net — the premium
  liquidity analytic, with a split inflow/outflow bar.
- **Performance**: 1D is real (from the quote); 5D/1M/3M/6M and 52-wk range are the
  sample series, marked with a `~`.

**Pre-demo: run `scripts/prime_quotes.py` once, off-hours.** It fetches one real
quote per watchlist ticker (~3-8 requests total, budget-aware) so every company has
live order-book + money-flow data on demo day. After that, browsing spends 0.

## Deep research, technical signal, Yahoo widgets, recent chips (added)

- **Deep research** — two scopes, both extractive (no LLM), 0 budget:
  - Per-topic: search anything, then "Deep research ›" → `/[lang]/research?q=` — the
    extractive answer + all matching docs grouped by type + companies involved
    (clickable) + a dated timeline. Try `Vision 2030`, `Saudi banks`, `NEOM`.
  - Per-company: the company page IS the dossier (chart, market data, money flow,
    technical signal, news, corpus context).
- **Technical signal** (company page): Bullish / Neutral / Bearish from SMA20/50 +
  momentum + RSI + real money flow. It is a TECHNICAL read, NOT buy/sell — the panel
  shows "not investment advice" (CMA-safe). Deliberately not a Buy/Sell rating.
- **Yahoo-style widgets** — native, offline-safe: the quote-summary two-column card
  and a price chart with range tabs (1M/3M/6M/ALL). Market cap / P·E / EPS show "—"
  until curated fundamentals are added (paywalled on the free tier).
- **Search → company**: the entity card has "Open company dashboard ›"; dashboard
  tickers and trending rows link straight to the company page.
- **Recent chips**: the splash suggestion chips are the latest real headlines.
