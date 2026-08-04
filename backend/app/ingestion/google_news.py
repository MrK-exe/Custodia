import calendar
import time
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup

from .. import aliases
from ..storage import db

TOPIC_QUERIES = [
    "الاقتصاد السعودي",
    "هيئة السوق المالية",
    "أسعار النفط أوبك",
    "السوق الموازية نمو تداول",
    "الاكتتابات السعودية",
]
FEED_URL = "https://news.google.com/rss/search?q={q}&hl=ar&gl=SA&ceid=SA:ar"
USER_AGENT = "KSATerminal/0.1"
MAX_ITEMS_PER_FEED = 15
FEED_TIMEOUT_SECONDS = 20


def _queries() -> list[str]:
    company_queries = [
        info.get("query_ar", info["name_ar"]) for info in aliases.COMPANIES.values()
    ]
    return company_queries + TOPIC_QUERIES


def _entry_doc(entry) -> dict | None:
    title = getattr(entry, "title", "").strip()
    guid = getattr(entry, "id", "") or getattr(entry, "link", "")
    if not title or not guid:
        return None
    summary_html = getattr(entry, "summary", "")
    summary = BeautifulSoup(summary_html, "html.parser").get_text(" ", strip=True)
    publisher = ""
    if getattr(entry, "source", None) is not None:
        publisher = getattr(entry.source, "title", "") or ""
    published_at = None
    if getattr(entry, "published_parsed", None):
        published_at = calendar.timegm(entry.published_parsed)
    tickers = aliases.match_tickers(title, summary)
    return {
        "source": "google_news",
        "external_id": guid,
        "title": title,
        "body": summary,
        "publisher": publisher,
        "url": getattr(entry, "link", ""),
        "doc_type": "news",
        "tickers": tickers,
        "sectors": aliases.sectors_for(tickers),
        "published_at": published_at or int(time.time()),
    }


def _fetch_feed(query: str):
    """Bounded fetch: requests with a timeout, then feedparser on the text.
    feedparser's own URL fetching has no timeout and can hang a refresh forever."""
    response = requests.get(
        FEED_URL.format(q=quote(query)),
        headers={"User-Agent": USER_AGENT},
        timeout=FEED_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    feed = feedparser.parse(response.text)
    if feed.bozo and not feed.entries:
        raise ValueError(f"unparseable feed for query {query!r}: {feed.bozo_exception}")
    return feed


def ingest_feeds() -> list[dict]:
    inserted: list[dict] = []
    failures = 0
    for query in _queries():
        try:
            feed = _fetch_feed(query)
        except Exception:
            failures += 1
            continue
        with db.connect() as conn:
            for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
                doc = _entry_doc(entry)
                if doc is None:
                    continue
                row_id = db.insert_document(conn, doc)
                if row_id is not None:
                    inserted.append({**doc, "id": row_id})
        time.sleep(0.5)
    if failures and not inserted:
        raise RuntimeError(f"all {failures} google news feeds failed")
    return inserted

# --- English feed (real English-language wires; no machine translation) ----------
FEED_URL_EN = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
QUERY_EN = {
    "2222": "Saudi Aramco",
    "1120": "Al Rajhi Bank Saudi",
    "7010": "STC Saudi Telecom",
    "2010": "SABIC Saudi",
    "1180": "Saudi National Bank SNB",
    "2280": "Almarai Saudi",
    "4013": "Dr Sulaiman Al Habib Medical",
    "1211": "Maaden Saudi Arabian Mining",
}
TOPIC_QUERIES_EN = [
    "Saudi stock market Tadawul TASI",
    "Saudi Capital Market Authority CMA",
    "Saudi Arabia IPO listing Tadawul",
    "Saudi oil OPEC exports",
]


def _queries_en() -> list[str]:
    company = [QUERY_EN.get(t, info["name_en"]) for t, info in aliases.COMPANIES.items()]
    return company + TOPIC_QUERIES_EN


def _fetch_feed_en(query: str):
    response = requests.get(
        FEED_URL_EN.format(q=quote(query)),
        headers={"User-Agent": USER_AGENT},
        timeout=FEED_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    feed = feedparser.parse(response.text)
    if feed.bozo and not feed.entries:
        raise ValueError(f"unparseable EN feed for query {query!r}: {feed.bozo_exception}")
    return feed


def _entry_doc_en(entry) -> dict | None:
    doc = _entry_doc(entry)
    if doc is None:
        return None
    doc["source"] = "google_news_en"
    doc["title_en"] = doc["title"]  # title is already English -> renders on /en
    return doc


def ingest_feeds_en() -> list[dict]:
    """Same mechanism as ingest_feeds, English locale. Feed-only (not embedded)."""
    inserted: list[dict] = []
    failures = 0
    for query in _queries_en():
        try:
            feed = _fetch_feed_en(query)
        except Exception:
            failures += 1
            continue
        with db.connect() as conn:
            for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
                doc = _entry_doc_en(entry)
                if doc is None:
                    continue
                row_id = db.insert_document(conn, doc)
                if row_id is not None:
                    inserted.append({**doc, "id": row_id})
        time.sleep(0.5)
    if failures and not inserted:
        raise RuntimeError(f"all {failures} english google news feeds failed")
    return inserted
