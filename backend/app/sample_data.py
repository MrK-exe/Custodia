"""Correlated sample OHLCV for the 8 watchlist tickers.

The SAHMK free tier paywalls the historical endpoint, so 1.0 charts run on a
clearly-labeled simulated series (plan item A). This is NOT a forecast and NOT real
history: it is a plausible, internally-consistent price path so the terminal has
charts, sparklines and a sector heatmap to render. Every surface that shows it
carries a "sample" badge, and get_history upgrades to live automatically the moment
a paid key is present.

Spec (council H5):
  - seed 20260716, deterministic
  - business days Sun-Thu (Tadawul week)
  - cross-ticker correlation via Cholesky of a PD target matrix (same-sector pairs
    correlate higher); verified positive-definite before factoring
  - backward pass anchored to the live/cached quote, so the last point equals the
    real current price
  - daily move clamped to +/-10% (Tadawul limit), volume strictly positive
"""
import sqlite3

import numpy as np
import pandas as pd

from .aliases import COMPANIES
from .config import WATCHLIST
from .storage import db

SEED = 20260716
DAYS = 180
WEEKMASK = "Sun Mon Tue Wed Thu"
DAILY_LIMIT = 0.10

# Anchor prices: the real current price wins (chart endpoint matches reality); these
# are only the fallback when no quote is cached. Sample data, so approximate is fine.
_BASE_PRICE = {
    "2222": 26.68, "1120": 91.20, "7010": 43.18, "2010": 72.80,
    "1180": 34.05, "2280": 55.40, "4013": 285.60, "1211": 55.10,
}
# Annualized vol assumption per ticker, translated to daily.
_ANN_VOL = {
    "2222": 0.18, "1120": 0.22, "7010": 0.20, "2010": 0.24,
    "1180": 0.23, "2280": 0.19, "4013": 0.26, "1211": 0.30,
}


def _sector_correlation(tickers: list[str]) -> np.ndarray:
    """Same-sector pairs correlate at 0.6, cross-sector at 0.25, plus a small market
    factor. Ridge-adjusted until positive-definite so the Cholesky factor exists."""
    n = len(tickers)
    sectors = [COMPANIES[t]["sector_en"] for t in tickers]
    m = np.full((n, n), 0.25)
    for i in range(n):
        for j in range(n):
            if i == j:
                m[i, j] = 1.0
            elif sectors[i] == sectors[j]:
                m[i, j] = 0.60
    # symmetric market factor nudge, then ridge to guarantee PD
    m = (m + m.T) / 2
    ridge = 0.0
    while True:
        test = m * (1 - ridge) + np.eye(n) * ridge
        eig = np.linalg.eigvalsh(test)
        if eig.min() > 0.05:
            return test
        ridge += 0.02


def _anchor_prices() -> dict[str, float]:
    anchors = dict(_BASE_PRICE)
    with db.connect() as conn:
        for t in WATCHLIST:
            row = conn.execute(
                "SELECT payload FROM quotes_cache WHERE key = ?", (f"quote:{t}",)
            ).fetchone()
            if not row:
                continue
            import json

            data = json.loads(row["payload"])
            px = data.get("price") or data.get("last") or data.get("close")
            if isinstance(px, (int, float)) and px > 0:
                anchors[t] = float(px)
    return anchors


def generate() -> int:
    """Build and store the sample series. Returns rows written."""
    tickers = list(WATCHLIST)
    rng = np.random.default_rng(SEED)
    n = len(tickers)

    dates = pd.bdate_range(end="2026-07-16", periods=DAYS, freq="C", weekmask=WEEKMASK)

    corr = _sector_correlation(tickers)
    chol = np.linalg.cholesky(corr)

    daily_vol = np.array([_ANN_VOL[t] / np.sqrt(252) for t in tickers])
    # correlated standard normals -> daily log returns with a tiny positive drift
    z = rng.standard_normal((DAYS, n)) @ chol.T
    drift = 0.0002
    rets = drift + z * daily_vol
    rets = np.clip(rets, -DAILY_LIMIT, DAILY_LIMIT)

    anchors = _anchor_prices()
    rows: list[tuple] = []
    for j, t in enumerate(tickers):
        r = rets[:, j]  # this ticker's daily return column
        # backward pass: last close == anchor (the real current price)
        closes = np.empty(DAYS)
        closes[-1] = anchors[t]
        for i in range(DAYS - 2, -1, -1):
            closes[i] = closes[i + 1] / (1 + r[i + 1])
        # OHLC around each close, volume strictly positive and vol-scaled
        base_vol = {"2222": 12_000_000, "1120": 6_000_000, "7010": 3_900_000}.get(t, 4_000_000)
        for i in range(DAYS):
            c = float(closes[i])
            o = float(closes[i - 1]) if i > 0 else c / (1 + r[i])
            intraday = abs(r[i]) + 0.004
            hi = max(o, c) * (1 + intraday * abs(rng.standard_normal()) * 0.5)
            lo = min(o, c) * (1 - intraday * abs(rng.standard_normal()) * 0.5)
            vol = int(base_vol * (0.6 + abs(rng.standard_normal()) * 0.8)) + 1
            rows.append((t, dates[i].strftime("%Y-%m-%d"),
                         round(o, 2), round(hi, 2), round(lo, 2), round(c, 2), vol, "sample"))

    with db.connect() as conn:
        conn.execute("DELETE FROM history WHERE source = 'sample'")
        conn.executemany(
            """INSERT OR REPLACE INTO history
               (symbol, date, open, high, low, close, volume, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
    return len(rows)


if __name__ == "__main__":
    print(f"generated {generate()} sample OHLCV rows for {len(WATCHLIST)} tickers")
