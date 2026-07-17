import json
import re
import time

import requests
from bs4 import BeautifulSoup

from .. import aliases
from ..dates import parse_timestamp
from ..storage import db

BASE = "https://www.argaam.com"
HEADERS = {"User-Agent": "KSATerminal/0.1"}
ARTICLE_ID = re.compile(r"/ar/article/articledetail/id/(\d+)")
FETCH_BUDGET = 20
FETCH_INTERVAL_SECONDS = 2


def _get(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def list_articles(listing_url: str) -> dict[str, str]:
    """Article id -> anchor title found on a listing page."""
    soup = BeautifulSoup(_get(listing_url), "html.parser")
    found: dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        match = ARTICLE_ID.search(anchor["href"])
        title = anchor.get_text(strip=True)
        if match and title:
            found.setdefault(match.group(1), title)
    return found


def _parse_iso(value: str) -> int | None:
    return parse_timestamp(value)


def _published_at(soup: BeautifulSoup) -> int | None:
    """Real publish time. Primary source: JSON-LD datePublished (verified present
    on Argaam article pages); fallback: article meta tags."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            # strict=False: Argaam's Article block embeds raw control characters,
            # and a strict parse throws, silently skipping the only block that
            # carries datePublished.
            data = json.loads(script.get_text(), strict=False)
        except (json.JSONDecodeError, TypeError):
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if isinstance(node, dict) and node.get("datePublished"):
                ts = _parse_iso(str(node["datePublished"]))
                if ts:
                    return ts
    for prop in ("article:published_time", "og:article:published_time"):
        meta = soup.find("meta", attrs={"property": prop})
        if meta and meta.get("content"):
            ts = _parse_iso(meta["content"])
            if ts:
                return ts
    return None


def fetch_article(article_id: str) -> dict | None:
    url = f"{BASE}/ar/article/articledetail/id/{article_id}"
    soup = BeautifulSoup(_get(url), "html.parser")
    h1 = soup.find("h1")
    if not h1:
        return None
    title = h1.get_text(strip=True)
    content = soup.find("div", class_="article-detail-content")
    paragraphs = content.find_all("p") if content else []
    body = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
    return {"title": title, "body": body, "url": url, "published_at": _published_at(soup)}


def _fetch_with_retry(article_id: str) -> dict | None:
    for attempt in (1, 2):
        try:
            return fetch_article(article_id)
        except Exception:
            if attempt == 1:
                time.sleep(2)
    return None


def ingest(listing_url: str = f"{BASE}/ar", source: str = "argaam", doc_type: str = "news") -> list[dict]:
    """Scrape a listing page and fetch new article bodies within budget.
    Per-article error isolation and commits; every attempted id is recorded in
    seen_articles so failed dedups never burn the budget again."""
    listed = list_articles(listing_url)
    with db.connect() as conn:
        seen = {
            row["external_id"]
            for row in conn.execute(
                "SELECT external_id FROM seen_articles WHERE source = ?", (source,)
            )
        }
    new_ids = sorted((i for i in listed if i not in seen), key=int, reverse=True)
    inserted: list[dict] = []
    for article_id in new_ids[:FETCH_BUDGET]:
        article = _fetch_with_retry(article_id)
        time.sleep(FETCH_INTERVAL_SECONDS)
        with db.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO seen_articles (source, external_id, fetched_at) "
                "VALUES (?, ?, ?)",
                (source, article_id, int(time.time())),
            )
            if not article:
                continue
            tickers = aliases.match_tickers(article["title"], article["body"])
            doc = {
                "source": source,
                "external_id": article_id,
                "title": article["title"],
                "body": article["body"],
                "publisher": "أرقام",
                "url": article["url"],
                "doc_type": doc_type,
                "tickers": tickers,
                "sectors": aliases.sectors_for(tickers),
                "published_at": article["published_at"] or int(time.time()),
            }
            row_id = db.insert_document(conn, doc)
            if row_id is not None:
                inserted.append({**doc, "id": row_id})
    return inserted
