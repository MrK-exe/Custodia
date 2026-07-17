import json
from urllib.parse import urlparse

from ..config import CORPUS_DIR
from ..dates import parse_timestamp
from ..storage import db


def _published_at(date_str: str) -> int | None:
    return parse_timestamp(date_str)


def load_corpus() -> list[dict]:
    """Load the curated corpus files (content reviewed by the owner before this
    runs). Dedup-safe via slug external ids; returns inserted docs for indexing."""
    if not CORPUS_DIR.exists():
        return []
    inserted: list[dict] = []
    with db.connect() as conn:
        for path in sorted(CORPUS_DIR.glob("*.json")):
            entries = json.loads(path.read_text(encoding="utf-8"))
            for entry in entries:
                domain = urlparse(entry.get("source_url", "")).netloc.replace("www.", "")
                doc = {
                    "source": "corpus",
                    "external_id": entry["slug"],
                    "title": entry["title_ar"],
                    "title_en": entry.get("title_en"),
                    "body": entry.get("body_ar", ""),
                    "publisher": "data.gov.sa" if entry["doc_type"] == "dataset" else domain,
                    "url": entry.get("source_url", ""),
                    "doc_type": entry["doc_type"],
                    "tickers": entry.get("tickers", []),
                    "sectors": entry.get("sectors", []),
                    "published_at": _published_at(entry.get("date", "")),
                }
                row_id = db.insert_document(conn, doc)
                if row_id is not None:
                    inserted.append({**doc, "id": row_id})
    return inserted
