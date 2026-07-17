import json
import threading
import time
import traceback

from ..storage import db
from ..storage.vectorstore import index_documents, indexed_ids
from . import (
    argaam_disclosures,
    argaam_news,
    cma_bulletins,
    cma_opendata,
    corpus_loader,
    google_news,
)

_refresh_lock = threading.Lock()

SOURCES = [
    ("corpus", corpus_loader.load_corpus),
    ("argaam_news", argaam_news.ingest),
    ("argaam_disclosures", argaam_disclosures.ingest_disclosures),
    ("google_news", google_news.ingest_feeds),
    ("cma_opendata", cma_opendata.ingest_registries),
    ("cma_bulletins", cma_bulletins.ingest_bulletins),
]


class RefreshAlreadyRunning(Exception):
    pass


# cma_opendata re-pulls ~2,700 registry rows in one ~13 minute write transaction
# and the registries are effectively static, so the demo-time refresh runs only
# the sources that actually produce fresh news.
LIGHT_SOURCES = ("corpus", "argaam_news", "argaam_disclosures", "google_news")


def refresh_all(sources: tuple[str, ...] | None = None) -> dict:
    """Run every source with per-source error isolation, index new documents,
    persist a status record. Single-flight: concurrent calls raise.
    sources: restrict to these source names (see LIGHT_SOURCES)."""
    if not _refresh_lock.acquire(blocking=False):
        raise RefreshAlreadyRunning("a refresh is already running")
    try:
        selected = [s for s in SOURCES if sources is None or s[0] in sources]
        status: dict = {"started_at": int(time.time()), "sources": {}}
        for name, run in selected:
            source_started = time.time()
            try:
                inserted = run()
                index_documents(inserted)
                status["sources"][name] = {
                    "ok": True,
                    "inserted": len(inserted),
                    "seconds": round(time.time() - source_started, 1),
                }
            except Exception as exc:
                traceback.print_exc()
                status["sources"][name] = {"ok": False, "error": str(exc)[:300]}
        status["finished_at"] = int(time.time())
        with db.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO quotes_cache (key, payload, fetched_at) VALUES (?, ?, ?)",
                ("_meta:refresh", json.dumps(status, ensure_ascii=False), int(time.time())),
            )
        return status
    finally:
        _refresh_lock.release()


def reindex_missing(batch_size: int = 200) -> int:
    """Index documents that made it into SQLite but not into Chroma (e.g. an
    interrupted refresh). Makes refresh crash-safe."""
    with db.connect() as conn:
        all_ids = [row["id"] for row in conn.execute("SELECT id FROM documents")]
        existing = indexed_ids()
        missing = [i for i in all_ids if str(i) not in existing]
        indexed = 0
        for start in range(0, len(missing), batch_size):
            docs = db.get_documents(conn, missing[start : start + batch_size])
            index_documents(docs)
            indexed += len(docs)
    return indexed


def last_refresh() -> dict | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT payload FROM quotes_cache WHERE key = '_meta:refresh'"
        ).fetchone()
    return json.loads(row["payload"]) if row else None
