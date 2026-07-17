"""Dashboard aggregates.

Honesty split, kept deliberate and now maximally real:
  - watchlist prices + daily change: REAL, from the cached SAHMK quote (cache-only,
    never spends budget). Only the sparkline trend-shape is the sample series.
  - sector heatmap: REAL intraday change, weighted by sector.
  - trending, calendar, brief: REAL, derived from the document corpus.
Nothing here invents a price, a headline, or an event. Sample data appears only as
the small sparkline trend, and the frontend badges it.
"""
import json

from ..aliases import COMPANIES
from ..config import WATCHLIST
from ..ingestion import sahmk_client
from ..storage import db
from . import series as series_mod

# Notional index weights (approximate TASI free-float order) for the heatmap only.
_WEIGHT = {
    "2222": 32, "1120": 12, "7010": 8, "2010": 10,
    "1180": 11, "2280": 4, "4013": 4, "1211": 6,
}


def _real_quote(ticker: str) -> dict | None:
    q = sahmk_client.cached_quote(ticker)
    if not q or not isinstance(q.get("data"), dict):
        return None
    d = q["data"]
    px = d.get("price") or d.get("last") or d.get("close")
    if not isinstance(px, (int, float)):
        return None
    chg = d.get("change_percent")
    return {
        "price": float(px),
        "change": float(chg) if isinstance(chg, (int, float)) else None,
        "stale": bool(q.get("stale")),
        "as_of": q.get("as_of"),
    }


def watchlist() -> list[dict]:
    """Real price + real daily change per ticker (cache-only), with a sample sparkline
    for the trend shape. Falls back to the sample series when no quote is cached."""
    out = []
    for t in WATCHLIST:
        q = _real_quote(t)
        s = series_mod.series(t, anchor=q["price"] if q else None)
        if not s:
            continue
        out.append({
            "ticker": t,
            "name_ar": s["name_ar"], "name_en": s["name_en"],
            "sector_ar": s["sector_ar"], "sector_en": s["sector_en"],
            "last": q["price"] if q else s["last"],
            "change": q["change"] if q else s["period_change"],
            "change_real": q is not None and q["change"] is not None,
            "spark": series_mod.sparkline(t, 30),
            "quote_source": "cache" if q else "sample",
            "stale": q["stale"] if q else False,
        })
    return out


def sector_heat() -> list[dict]:
    """Sector-level intraday change, weighted, from REAL quotes (falls back to the
    sample period change only for tickers with no cached quote)."""
    agg: dict[str, dict] = {}
    real_any = False
    for t in WATCHLIST:
        q = _real_quote(t)
        if q and q["change"] is not None:
            change = q["change"]
            real_any = True
        else:
            s = series_mod.series(t)
            change = s["period_change"] if s and s["period_change"] is not None else 0.0
        info = COMPANIES[t]
        w = _WEIGHT.get(t, 4)
        bucket = agg.setdefault(info["sector_en"], {
            "sector_en": info["sector_en"], "sector_ar": info["sector_ar"], "wsum": 0.0, "w": 0,
        })
        bucket["wsum"] += change * w
        bucket["w"] += w
    rows = []
    for b in agg.values():
        rows.append({
            "sector_en": b["sector_en"], "sector_ar": b["sector_ar"],
            "change": round(b["wsum"] / b["w"], 2) if b["w"] else 0.0,
            "weight": b["w"],
            "source": "live" if real_any else "sample",
        })
    return sorted(rows, key=lambda r: -r["weight"])


def trending(limit: int = 6) -> list[dict]:
    """REAL: watchlist companies ranked by how many documents mention them."""
    with db.connect() as conn:
        rows = []
        for t in WATCHLIST:
            n = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE tickers LIKE ? AND doc_type != 'registry'",
                (f'%"{t}"%',),
            ).fetchone()[0]
            rows.append({
                "ticker": t,
                "name_ar": COMPANIES[t]["name_ar"], "name_en": COMPANIES[t]["name_en"],
                "count": n,
            })
    return sorted(rows, key=lambda r: -r["count"])[:limit]


def calendar(limit: int = 6) -> list[dict]:
    """REAL: dated corpus events (mandates, geopolitics, laws, market events),
    most recent first. Historical facts with real dates, not forecasts."""
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT id, title, title_en, doc_type, published_at, url, publisher FROM documents
               WHERE source = 'corpus' AND doc_type IN ('mandate','geopolitics','law','ownership','news')
                 AND published_at IS NOT NULL
               ORDER BY published_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def brief() -> dict:
    """REAL market pulse: counts and latest headlines. No generated prose."""
    with db.connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        by_type = dict(conn.execute(
            "SELECT doc_type, COUNT(*) FROM documents GROUP BY doc_type"
        ).fetchall())
        latest = [dict(r) for r in conn.execute(
            """SELECT id, title, title_en, doc_type, publisher, url, published_at, tickers FROM documents
               WHERE doc_type != 'registry' ORDER BY published_at DESC LIMIT 5"""
        )]
        tagged = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE tickers != '[]' AND doc_type != 'registry'"
        ).fetchone()[0]
    for d in latest:
        d["tickers"] = json.loads(d["tickers"])
    return {
        "total_documents": total,
        "by_type": by_type,
        "tagged_documents": tagged,
        "latest": latest,
    }


def dashboard() -> dict:
    return {
        "brief": brief(),
        "watchlist": watchlist(),
        "sectors": sector_heat(),
        "trending": trending(),
        "calendar": calendar(),
    }
