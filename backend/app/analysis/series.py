"""Per-symbol series and indicators over the sample OHLCV.

All indicators are descriptive, never directive: "SMA20 crossed above SMA50" is a
fact about the series; "buy" would move the product into the CMA "Advising"
category. NaN/inf are converted to None at this boundary because Starlette's
JSONResponse hard-500s on NaN.
"""
import math

import numpy as np
import pandas as pd

from ..aliases import COMPANIES
from ..storage import db


def _clean(x) -> float | None:
    if x is None:
        return None
    v = float(x)
    return None if (math.isnan(v) or math.isinf(v)) else round(v, 4)


def _frame(symbol: str) -> pd.DataFrame:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT date, open, high, low, close, volume FROM history "
            "WHERE symbol = ? AND source = 'sample' ORDER BY date",
            (symbol,),
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def series(symbol: str, anchor: float | None = None) -> dict | None:
    """OHLCV plus SMA20/SMA50 and a shift(1) z-score, all JSON-safe.

    z is computed on returns shifted by one day (the current point is excluded) so a
    genuine spike reads as an outlier instead of being absorbed into its own window.

    anchor: if given, the whole series is rescaled so its last close equals this
    price. The generated series is anchored to whatever quote was cached at generation
    time; passing the currently displayed price keeps the chart endpoint consistent
    with the number shown above it.
    """
    df = _frame(symbol)
    if df.empty:
        return None

    if anchor and anchor > 0 and df["close"].iloc[-1]:
        factor = anchor / float(df["close"].iloc[-1])
        for col in ("open", "high", "low", "close"):
            df[col] = df[col] * factor

    close = df["close"]
    sma20 = close.rolling(20, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=50).mean()

    ret = close.pct_change()
    prior = ret.shift(1)
    mean = prior.rolling(20, min_periods=10).mean()
    std = prior.rolling(20, min_periods=10).std()
    z = (ret - mean) / std.replace(0, np.nan)

    points = []
    for i in range(len(df)):
        points.append({
            "date": df["date"].iloc[i],
            "open": _clean(df["open"].iloc[i]),
            "high": _clean(df["high"].iloc[i]),
            "low": _clean(df["low"].iloc[i]),
            "close": _clean(close.iloc[i]),
            "volume": int(df["volume"].iloc[i]),
            "sma20": _clean(sma20.iloc[i]),
            "sma50": _clean(sma50.iloc[i]),
            "z": _clean(z.iloc[i]),
        })

    first, last = float(close.iloc[0]), float(close.iloc[-1])
    period_change = (last - first) / first * 100 if first else 0.0
    hi = float(df["high"].max())
    lo = float(df["low"].min())

    # descriptive trend signal only
    s20, s50 = _clean(sma20.iloc[-1]), _clean(sma50.iloc[-1])
    trend = None
    if s20 is not None and s50 is not None:
        trend = "above" if s20 >= s50 else "below"

    return {
        "symbol": symbol,
        "name_ar": COMPANIES.get(symbol, {}).get("name_ar", symbol),
        "name_en": COMPANIES.get(symbol, {}).get("name_en", symbol),
        "sector_ar": COMPANIES.get(symbol, {}).get("sector_ar", ""),
        "sector_en": COMPANIES.get(symbol, {}).get("sector_en", ""),
        "points": points,
        "last": _clean(last),
        "period_change": _clean(period_change),
        "high_52": _clean(hi),
        "low_52": _clean(lo),
        "trend": trend,
        "source": "sample",  # the frontend badges this
    }


def performance(symbol: str, anchor: float | None = None) -> dict:
    """Multi-period % returns from the sample series (badged sample by the caller).
    The 1-day figure is intentionally omitted here: the real 1-day change comes from
    the live quote, not the simulated series."""
    df = _frame(symbol)
    if df.empty:
        return {}
    close = df["close"]
    if anchor and anchor > 0 and close.iloc[-1]:
        close = close * (anchor / float(close.iloc[-1]))
    last = float(close.iloc[-1])
    periods = {"5d": 5, "1m": 21, "3m": 63, "6m": 126}
    out: dict[str, float | None] = {}
    for label, days in periods.items():
        if len(close) > days:
            prior = float(close.iloc[-1 - days])
            out[label] = _clean((last - prior) / prior * 100) if prior else None
        else:
            out[label] = None
    first = float(close.iloc[0])
    out["period"] = _clean((last - first) / first * 100) if first else None
    return out


def sparkline(symbol: str, n: int = 30) -> list[float | None]:
    """Downsampled closes for a mini chart."""
    df = _frame(symbol)
    if df.empty:
        return []
    closes = df["close"].tolist()[-n:]
    return [_clean(c) for c in closes]
