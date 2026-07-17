"""Repair fabricated publish dates in rows already stored. Backend STOPPED.

    cd backend && .venv/Scripts/python.exe scripts/backfill_dates.py [--dry-run]

Two populations carry fetch time where a real date belongs:

  registry - re-derived offline from the stored cma_records payload through the
             fixed parser, so code and data cannot drift apart again. Records with
             no date field at all (licensed persons, CRAs) become NULL rather than
             "today", which is what made them sort newest and wall the news feed.
  argaam   - the date only exists on the article page, so those are re-fetched.
             ~38 pages at one every 2s. Never touches SAHMK.

Chroma published_at is patched in place (metadata-only, no re-embedding). Unknown
dates are 0 there, since Chroma metadata cannot hold NULL.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion import argaam_news  # noqa: E402
from app.ingestion.cma_opendata import _record_published_at  # noqa: E402
from app.storage import db, vectorstore  # noqa: E402


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def fix_registry(dry: bool) -> dict:
    """Recompute every registry doc's date from its stored payload."""
    changes: dict[int, int | None] = {}
    with db.connect() as conn:
        payloads = {
            r["record_id"]: r["payload"]
            for r in conn.execute("SELECT record_id, payload FROM cma_records")
        }
        rows = conn.execute(
            "SELECT id, external_id, published_at, fetched_at FROM documents "
            "WHERE source = 'cma'"
        ).fetchall()
        for row in rows:
            payload = payloads.get(row["external_id"])
            if payload is None:
                continue
            real = _record_published_at(json.loads(payload))
            if real != row["published_at"]:
                changes[row["id"]] = real
    nulled = sum(1 for v in changes.values() if v is None)
    log(f"registry: {len(changes)} dates to correct ({nulled} -> NULL, no date exists)")
    if dry or not changes:
        return changes
    with db.connect() as conn:
        for doc_id, ts in changes.items():
            conn.execute(
                "UPDATE documents SET published_at = ? WHERE id = ?", (ts, doc_id)
            )
    vectorstore.update_metadata({i: {"published_at": ts or 0} for i, ts in changes.items()})
    log(f"registry: {len(changes)} rows updated in both stores")
    return changes


def fix_argaam(dry: bool) -> dict:
    """Re-fetch the article pages; the publish date lives only there."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, external_id, published_at, fetched_at, title FROM documents "
            "WHERE source LIKE 'argaam%' ORDER BY id"
        ).fetchall()
    suspect = [r for r in rows if abs((r["published_at"] or 0) - r["fetched_at"]) < 900]
    log(f"argaam: {len(suspect)}/{len(rows)} rows carry fetch-time dates")
    if dry:
        return {}
    changes: dict[int, int] = {}
    failed = []
    for i, row in enumerate(suspect, 1):
        try:
            article = argaam_news._fetch_with_retry(row["external_id"])
        except Exception as exc:  # noqa: BLE001
            article = None
            log(f"   {row['external_id']}: {type(exc).__name__}")
        time.sleep(argaam_news.FETCH_INTERVAL_SECONDS)
        if not article or not article.get("published_at"):
            failed.append(row["external_id"])
            continue
        changes[row["id"]] = article["published_at"]
        if i % 10 == 0:
            log(f"   {i}/{len(suspect)} fetched")
    log(f"argaam: {len(changes)} real dates recovered, {len(failed)} unrecoverable")
    if failed:
        log(f"   unrecovered ids: {failed}")
    if changes:
        with db.connect() as conn:
            for doc_id, ts in changes.items():
                conn.execute(
                    "UPDATE documents SET published_at = ? WHERE id = ?", (ts, doc_id)
                )
        vectorstore.update_metadata({i: {"published_at": t} for i, t in changes.items()})
    return changes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-argaam", action="store_true", help="no network fetches")
    args = ap.parse_args()
    log(f"backfill_dates starting{' (DRY RUN)' if args.dry_run else ''}")

    fix_registry(args.dry_run)
    if not args.skip_argaam:
        fix_argaam(args.dry_run)

    with db.connect() as conn:
        fabricated = conn.execute(
            "SELECT COUNT(*) FROM documents "
            "WHERE published_at IS NOT NULL AND ABS(published_at - fetched_at) < 900"
        ).fetchone()[0]
        undated = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE published_at IS NULL"
        ).fetchone()[0]
    log(f"remaining fetch-time dates: {fabricated}; honestly undated (NULL): {undated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
