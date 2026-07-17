import json
import re
import sqlite3
import time

from ..config import DATA_DIR, DB_PATH
from ..text_utils import title_hash

_TICKER_RE = re.compile(r"^\d{4}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    title_en TEXT,
    body TEXT NOT NULL DEFAULT '',
    publisher TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    doc_type TEXT NOT NULL,
    tickers TEXT NOT NULL DEFAULT '[]',
    sectors TEXT NOT NULL DEFAULT '[]',
    published_at INTEGER,
    fetched_at INTEGER NOT NULL,
    title_hash TEXT NOT NULL,
    UNIQUE (source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_documents_title_hash ON documents (title_hash);
CREATE INDEX IF NOT EXISTS idx_documents_published_at ON documents (published_at);

CREATE TABLE IF NOT EXISTS quotes_cache (
    key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    fetched_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS seen_articles (
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    fetched_at INTEGER NOT NULL,
    PRIMARY KEY (source, external_id)
);

CREATE TABLE IF NOT EXISTS cma_records (
    kind TEXT NOT NULL,
    record_id TEXT NOT NULL,
    name TEXT NOT NULL,
    payload TEXT NOT NULL,
    fetched_at INTEGER NOT NULL,
    PRIMARY KEY (kind, record_id)
);

CREATE TABLE IF NOT EXISTS cma_stats (
    bulletin TEXT NOT NULL,
    sheet TEXT NOT NULL,
    payload TEXT NOT NULL,
    fetched_at INTEGER NOT NULL,
    PRIMARY KEY (bulletin, sheet)
);

CREATE TABLE IF NOT EXISTS dm_personas (
    id TEXT PRIMARY KEY,
    name_ar TEXT NOT NULL,
    name_en TEXT NOT NULL,
    role_ar TEXT NOT NULL,
    role_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dm_threads (
    id INTEGER PRIMARY KEY,
    persona_id TEXT NOT NULL REFERENCES dm_personas (id),
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dm_messages (
    id INTEGER PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES dm_threads (id),
    sender TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    -- a share stores the id, never a copy of the document
    doc_id INTEGER REFERENCES documents (id),
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dm_messages_thread ON dm_messages (thread_id);

CREATE TABLE IF NOT EXISTS history (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    source TEXT NOT NULL DEFAULT 'sample',
    PRIMARY KEY (symbol, date)
);
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)")}
        if "title_en" not in cols:
            conn.execute("ALTER TABLE documents ADD COLUMN title_en TEXT")


def insert_document(conn: sqlite3.Connection, doc: dict) -> int | None:
    """Insert one document. Returns the new row id, or None when deduplicated
    (same (source, external_id) or same normalized-title hash)."""
    thash = title_hash(doc["title"])
    dup = conn.execute(
        "SELECT 1 FROM documents WHERE title_hash = ? OR (source = ? AND external_id = ?)",
        (thash, doc["source"], doc["external_id"]),
    ).fetchone()
    if dup:
        return None
    cur = conn.execute(
        """INSERT INTO documents
           (source, external_id, title, title_en, body, publisher, url, doc_type,
            tickers, sectors, published_at, fetched_at, title_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            doc["source"],
            doc["external_id"],
            doc["title"],
            doc.get("title_en"),
            doc.get("body", ""),
            doc.get("publisher", ""),
            doc.get("url", ""),
            doc["doc_type"],
            json.dumps(doc.get("tickers", []), ensure_ascii=False),
            json.dumps(doc.get("sectors", []), ensure_ascii=False),
            doc.get("published_at"),
            int(time.time()),
            thash,
        ),
    )
    return cur.lastrowid


def _row_to_doc(row: sqlite3.Row) -> dict:
    doc = dict(row)
    doc["tickers"] = json.loads(doc["tickers"])
    doc["sectors"] = json.loads(doc["sectors"])
    return doc


def get_documents(conn: sqlite3.Connection, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    rows = conn.execute(f"SELECT * FROM documents WHERE id IN ({marks})", ids).fetchall()
    by_id = {row["id"]: _row_to_doc(row) for row in rows}
    return [by_id[i] for i in ids if i in by_id]


# CMA registry rows outnumber real news 30:1 for the banks (1180: 236 registry vs 4
# news) and the ones still stamped at fetch time sort newest, so an unfiltered feed
# is a wall of fund registrations. Registries stay reachable via exclude_types=().
NEWS_FEED_EXCLUDED_TYPES = ("registry",)


def documents_by_ticker(
    conn: sqlite3.Connection,
    ticker: str,
    limit: int = 20,
    exclude_types: tuple[str, ...] = NEWS_FEED_EXCLUDED_TYPES,
) -> list[dict]:
    if not _TICKER_RE.match(ticker):
        return []
    clause = ""
    params: list = [f'%"{ticker}"%']
    if exclude_types:
        clause = f" AND doc_type NOT IN ({','.join('?' * len(exclude_types))})"
        params.extend(exclude_types)
    params.append(limit)
    rows = conn.execute(
        f"""SELECT * FROM documents
           WHERE tickers LIKE ?{clause}
           ORDER BY published_at DESC
           LIMIT ?""",
        params,
    ).fetchall()
    return [_row_to_doc(row) for row in rows]


def seed_seen_articles(conn: sqlite3.Connection) -> int:
    """Backfill seen_articles from documents already stored, so the fetch-budget
    guard does not re-fetch the corpus it already has. Idempotent."""
    cur = conn.execute(
        """INSERT OR IGNORE INTO seen_articles (source, external_id, fetched_at)
           SELECT source, external_id, fetched_at FROM documents
           WHERE source LIKE 'argaam%'"""
    )
    return cur.rowcount
