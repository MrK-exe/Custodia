"""Descriptive TECHNICAL signal. NOT investment advice.

This is deliberately not a Buy/Sell rating. Directive language ("buy") would move
the product into the CMA "Advising" category; a technical read ("the trend is up,
momentum is positive") is a description of the series, which is what a terminal
shows. Every payload carries `advice: False` and a disclaimer key so the UI must
render the caveat.

Inputs blend the sample price series (trend, momentum, RSI) with the one real
market input available on the free tier: net money flow from the live quote. Each
component votes -1/0/+1; the sum maps to Bearish / Neutral / Bullish.
"""
import numpy as np
import pandas as pd

from ..storage import db


def _closes(symbol: str, anchor: float | None) -> pd.Series:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT close FROM history WHERE symbol = ? AND source = 'sample' ORDER BY date",
            (symbol,),
        ).fetchall()
    close = pd.Series([r["close"] for r in rows], dtype="float64")
    if anchor and anchor > 0 and len(close) and close.iloc[-1]:
        close = close * (anchor / float(close.iloc[-1]))
    return close


def _rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) <= period:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    v = rsi.iloc[-1]
    return None if pd.isna(v) else round(float(v), 1)


def technical_signal(symbol: str, anchor: float | None = None,
                     net_flow: float | None = None) -> dict:
    close = _closes(symbol, anchor)
    if len(close) < 50:
        return {"label": "unknown", "score": 0, "components": [], "advice": False,
                "disclaimer": True}

    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    last = float(close.iloc[-1])
    mom = (last - float(close.iloc[-21])) / float(close.iloc[-21]) * 100 if len(close) > 21 else 0.0
    rsi = _rsi(close)

    components = []

    # 1. trend: price vs SMA cross
    if not pd.isna(sma20) and not pd.isna(sma50):
        vote = 1 if sma20 > sma50 else -1
        components.append({
            "key": "trend", "vote": vote,
            "detail_en": f"SMA20 {'above' if vote > 0 else 'below'} SMA50",
            "detail_ar": f"متوسط 20 {'فوق' if vote > 0 else 'تحت'} متوسط 50",
        })

    # 2. momentum: 1-month return
    mvote = 1 if mom > 2 else -1 if mom < -2 else 0
    components.append({
        "key": "momentum", "vote": mvote,
        "detail_en": f"1M momentum {mom:+.1f}%",
        "detail_ar": f"زخم الشهر {mom:+.1f}%",
    })

    # 3. RSI: overbought/oversold (contrarian at extremes, neutral in band)
    if rsi is not None:
        rvote = -1 if rsi > 70 else 1 if rsi < 30 else 0
        state_en = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral"
        state_ar = "تشبّع شرائي" if rsi > 70 else "تشبّع بيعي" if rsi < 30 else "محايد"
        components.append({
            "key": "rsi", "vote": rvote,
            "detail_en": f"RSI {rsi} ({state_en})",
            "detail_ar": f"مؤشر القوة {rsi} ({state_ar})",
        })

    # 4. money flow: the one REAL input (net inflow/outflow from the live quote)
    if net_flow is not None:
        fvote = 1 if net_flow > 0 else -1 if net_flow < 0 else 0
        components.append({
            "key": "money_flow", "vote": fvote, "real": True,
            "detail_en": f"Net money flow {'positive' if fvote > 0 else 'negative'}",
            "detail_ar": f"صافي التدفق {'موجب' if fvote > 0 else 'سالب'}",
        })

    score = sum(c["vote"] for c in components)
    label = "bullish" if score >= 2 else "bearish" if score <= -2 else "neutral"

    return {
        "label": label,          # bullish | neutral | bearish (technical read)
        "score": score,
        "max_score": len(components),
        "components": components,
        "rsi": rsi,
        "advice": False,         # NEVER a buy/sell recommendation
        "disclaimer": True,      # UI must show "technical signal, not investment advice"
    }
