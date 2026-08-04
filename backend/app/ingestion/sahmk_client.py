import dataclasses
import json
import os
import threading
import time
from datetime import date, datetime, timedelta, timezone

from ..config import SAHMK_API_KEY
from ..storage import db

# Public/demo mode: when DEMO_CACHE_ONLY=1, the engine NEVER calls the live
# SAHMK feed. It serves whatever is cached (stale-flagged) so a public URL
# cannot burn the 100/day quota. Read once at import; set it before startup.
CACHE_ONLY = os.getenv("DEMO_CACHE_ONLY") == "1"

AST = timezone(timedelta(hours=3))
TRADING_WEEKDAYS = {6, 0, 1, 2, 3}  # Sun-Thu (Python: Mon=0 .. Sun=6)
OPEN_HOUR, OPEN_MINUTE = 10, 0
CLOSE_HOUR, CLOSE_MINUTE = 15, 10
FEED_DELAY = timedelta(minutes=15)  # free tier serves 15-min delayed prices
TTL = timedelta(minutes=15)
HISTORY_TTL = timedelta(hours=6)

_lock = threading.Lock()
_client = None


class SahmkError(Exception):
    pass


def _get_client():
    global _client
    with _lock:
        if _client is None:
            from sahmk import SahmkClient

            if not SAHMK_API_KEY:
                raise SahmkError("SAHMK_API_KEY is not set")
            # retries=0: the SDK sleeps float(Retry-After) with no ceiling, so a
            # throttled call can park a worker for as long as the server asks.
            # A quote is not worth a stall; the cache is the fallback.
            _client = SahmkClient(SAHMK_API_KEY, retries=0, timeout=15)
    return _client


def _is_market_open(now: datetime) -> bool:
    if now.weekday() not in TRADING_WEEKDAYS:
        return False
    open_t = now.replace(hour=OPEN_HOUR, minute=OPEN_MINUTE, second=0, microsecond=0)
    close_t = now.replace(hour=CLOSE_HOUR, minute=CLOSE_MINUTE, second=0, microsecond=0)
    return open_t <= now < close_t


def _last_close(now: datetime) -> datetime:
    for days_back in range(8):
        day = now - timedelta(days=days_back)
        if day.weekday() not in TRADING_WEEKDAYS:
            continue
        close_t = day.replace(hour=CLOSE_HOUR, minute=CLOSE_MINUTE, second=0, microsecond=0)
        if close_t <= now:
            return close_t
    raise SahmkError("no trading day found in the last week")


def _is_fresh(fetched_at: int, ttl: timedelta) -> bool:
    now = datetime.now(AST)
    fetched = datetime.fromtimestamp(fetched_at, AST)
    if _is_market_open(now):
        return now - fetched < ttl
    cutoff = _last_close(now) + FEED_DELAY
    if now < cutoff:
        # Settlement window right after close (15:10-15:25 AST): the closing print
        # has not reached the delayed feed yet, so TTL-throttle instead of treating
        # every cached entry as stale (which made every request a live call).
        return now - fetched < ttl
    return fetched >= cutoff


def _cache_get(key: str):
    with db.connect() as conn:
        row = conn.execute(
            "SELECT payload, fetched_at FROM quotes_cache WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return None, None
    return json.loads(row["payload"]), row["fetched_at"]


def _cache_put(key: str, payload) -> None:
    with db.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO quotes_cache (key, payload, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(payload, ensure_ascii=False), int(time.time())),
        )


def _count_request() -> None:
    today = date.today().isoformat()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT payload FROM quotes_cache WHERE key = '_meta:requests'"
        ).fetchone()
        counts = json.loads(row["payload"]) if row else {}
        counts = {today: counts.get(today, 0) + 1}
        conn.execute(
            "INSERT OR REPLACE INTO quotes_cache (key, payload, fetched_at) VALUES (?, ?, ?)",
            ("_meta:requests", json.dumps(counts), int(time.time())),
        )


DAILY_BUDGET = 100  # free tier
# Stop spending before the wall so the last requests stay available for a live demo
# rather than being burned by a background panel refresh.
BUDGET_SOFT_LIMIT = 90


def requests_today() -> int:
    payload, _ = _cache_get("_meta:requests")
    return (payload or {}).get(date.today().isoformat(), 0)


def budget_remaining() -> int:
    return max(0, DAILY_BUDGET - requests_today())


def _to_plain(obj):
    """SDK models are dataclasses keeping the original API payload in `.raw`."""
    raw = getattr(obj, "raw", None)
    if isinstance(raw, dict) and raw:
        return raw
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(v) for v in obj]
    return obj


def _envelope(payload, source: str, stale: bool, fetched_at: int) -> dict:
    """One honesty contract for every panel: the feed is 15-min delayed, and the
    payload's own timestamp is surfaced as as_of rather than implied fresh."""
    as_of = None
    delayed = True
    if isinstance(payload, dict):
        as_of = payload.get("updated_at") or payload.get("timestamp")
        delayed = bool(payload.get("is_delayed", True))
    return {
        "data": payload,
        "source": source,
        "stale": stale,
        "delayed": delayed,
        "as_of": as_of,
        "fetched_at": fetched_at,
    }


def _cached(key: str, fetch, ttl: timedelta = TTL) -> dict:
    payload, fetched_at = _cache_get(key)
    if payload is not None and _is_fresh(fetched_at, ttl):
        return _envelope(payload, "cache", False, fetched_at)
    if CACHE_ONLY:
        # public/demo mode: never spend the live budget
        if payload is not None:
            return _envelope(payload, "cache", True, fetched_at)
        raise SahmkError(f"{key}: cache-only mode is on and nothing is cached")
    if requests_today() >= BUDGET_SOFT_LIMIT:
        # Out of budget: serve stale and say so, rather than throwing on stage.
        if payload is not None:
            return _envelope(payload, "cache", True, fetched_at)
        raise SahmkError(
            f"{key}: daily request budget reached "
            f"({requests_today()}/{DAILY_BUDGET}) and nothing cached"
        )
    try:
        _count_request()
        fresh = _to_plain(fetch())
        _cache_put(key, fresh)
        return _envelope(fresh, "live", False, int(time.time()))
    except Exception as exc:
        if payload is not None:
            return _envelope(payload, "cache", True, fetched_at)
        raise SahmkError(f"{key}: {exc}") from exc


def cached_quote(symbol: str) -> dict | None:
    """Cache-only read: returns the last stored quote (stale-flagged if past TTL) and
    NEVER fetches. Used by the dashboard and company pages so drilling into tickers
    cannot spend the daily budget."""
    payload, fetched_at = _cache_get(f"quote:{symbol}")
    if payload is None:
        return None
    return _envelope(payload, "cache", not _is_fresh(fetched_at, TTL), fetched_at)


def get_quote(symbol: str) -> dict:
    return _cached(f"quote:{symbol}", lambda: _get_client().quote(symbol))


def get_market_summary() -> dict:
    return _cached("market:summary", lambda: _get_client().market_summary("TASI"))


def get_movers() -> dict:
    return {
        "gainers": _cached("market:gainers", lambda: _get_client().gainers()),
        "losers": _cached("market:losers", lambda: _get_client().losers()),
        "volume": _cached("market:volume", lambda: _get_client().volume_leaders()),
    }


def get_company(symbol: str) -> dict:
    return _cached(f"company:{symbol}", lambda: _get_client().company(symbol), ttl=HISTORY_TTL)


def search_companies(query: str) -> dict:
    return _cached(
        f"companies:{query}", lambda: _get_client().companies(search=query), ttl=HISTORY_TTL
    )


def _history_rows(symbol: str) -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT date, open, high, low, close, volume, source FROM history "
            "WHERE symbol = ? ORDER BY date",
            (symbol,),
        ).fetchall()
    return [dict(r) for r in rows]


HISTORY_BLOCKED_TTL_SECONDS = 24 * 3600


def _history_blocked() -> bool:
    payload, fetched_at = _cache_get("history_blocked")
    return bool(payload) and (time.time() - fetched_at) < HISTORY_BLOCKED_TTL_SECONDS


def get_history(symbol: str) -> dict:
    """Live historical() first; on plan restriction fall back to the sample series
    (checkpoint 6). A plan-gated failure is negative-cached for 24h so dashboard
    loads stop re-attempting the paywalled endpoint (which sleep-retries on 429)."""
    if not _history_blocked():
        try:
            result = _cached(
                f"history:{symbol}", lambda: _get_client().historical(symbol), ttl=HISTORY_TTL
            )
            result["history_source"] = "live" if not result["stale"] else "cache"
            return result
        except SahmkError:
            _cache_put("history_blocked", {"blocked": True})
    rows = _history_rows(symbol)
    if rows:
        return {
            "data": rows,
            "source": "sample",
            "stale": False,
            "delayed": False,
            "as_of": rows[-1]["date"] if rows else None,
            "fetched_at": int(time.time()),
            "history_source": "sample",
        }
    raise SahmkError(
        f"history:{symbol}: live endpoint unavailable on this plan and no sample series loaded"
    )
