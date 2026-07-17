"""One tolerant date parser for every ingestion source.

Saudi publishers ship slash dates that datetime.fromisoformat rejects outright and
silently: Argaam's JSON-LD datePublished is "2026/07/16" and the CMA registry API's
notificationDate is "2017/04/20". Each source having its own parser is how both ended
up stamping fetch time instead, so they all come through here.

Returns None when there is no parseable date. None means "unknown", and unknown must
never be rendered as today.
"""
from datetime import datetime, timezone

_FORMATS = (
    "%Y/%m/%d",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
)


def parse_timestamp(value) -> int | None:
    """Epoch seconds (UTC) for an ISO-8601 or slash-formatted date, else None."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        dt = None
    if dt is None:
        for fmt in _FORMATS:
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.astimezone(timezone.utc).timestamp())
