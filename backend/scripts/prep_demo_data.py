"""One-shot demo data preparation. Run with the backend STOPPED.

    cd backend && .venv/Scripts/python.exe scripts/prep_demo_data.py [--dry-run]

Ordering is load-bearing:

  1. load the curated corpus directly (never via refresh_all, which would drag a
     ~13 minute CMA registry re-pull behind it)
  2. retag SQLite with the current matcher, so the corpus rows are tagged too
  3. DELETE the changed ids from Chroma and re-add them. This is the step a plain
     re-upsert cannot do: Chroma merges metadata key by key, so a t_<ticker> boolean
     written by an earlier tagging run survives forever and a removed tag never
     disappears from the ticker filter.
  4. index anything still missing, seed the fetch-budget table, then verify both
     stores agree and fail loudly if they do not.

Idempotent: a second run should report 0 changes.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.aliases import COMPANIES, match_tickers, sectors_for  # noqa: E402
from app.ingestion.corpus_loader import load_corpus  # noqa: E402
from app.ingestion.refresh import reindex_missing  # noqa: E402
from app.storage import db  # noqa: E402
from app.storage import vectorstore  # noqa: E402

# The passage budget changed (1000 -> 1800 body chars), so any doc longer than the
# old cutoff embeds differently and has to be re-embedded to stay consistent.
OLD_PASSAGE_BODY_CHARS = 1000


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def chroma_divergent_ids(desired: dict[int, list[str]]) -> set[int]:
    """Ids whose Chroma t_<ticker> keys disagree with the tags they should carry.

    Chroma upsert merges metadata key by key, so a t_<ticker> boolean written by an
    earlier tagging run is never removed by re-upserting the doc. Those rows look
    clean in SQLite and wrong in the ticker filter, so they are invisible to a
    SQLite-only diff and have to be reconciled against the index itself.
    """
    col = vectorstore._get_collection()
    divergent: set[int] = set()
    for ticker in COMPANIES:
        in_chroma = {
            int(i)
            for i in col.get(where={f"t_{ticker}": {"$eq": True}}, include=[])["ids"]
        }
        should_have = {i for i, tags in desired.items() if ticker in tags}
        divergent |= in_chroma ^ should_have
    return divergent


def desired_tickers(row) -> list[str]:
    """Matcher output, unioned with curated tags for the hand-written corpus so an
    owner-assigned ticker is never silently dropped by the matcher."""
    matched = match_tickers(row["title"], row["body"] or "")
    if row["source"] == "corpus":
        curated = json.loads(row["tickers"])
        return sorted(set(curated) | set(matched))
    return matched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report, change nothing")
    args = ap.parse_args()
    dry = args.dry_run
    log(f"prep_demo_data starting{' (DRY RUN)' if dry else ''}")

    db.init_db()

    # 1. corpus ---------------------------------------------------------------
    with db.connect() as conn:
        before = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE source='corpus'"
        ).fetchone()[0]
    if dry:
        log(f"corpus rows already loaded: {before} (dry run, not loading)")
        inserted = []
    elif before:
        log(f"corpus already loaded ({before} rows), skipping load_corpus")
        inserted = []
    else:
        inserted = load_corpus()
        log(f"corpus loaded: {len(inserted)} rows inserted")

    # 2. retag ----------------------------------------------------------------
    changed: list[int] = []
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, source, title, body, tickers FROM documents"
        ).fetchall()
        log(f"retagging {len(rows)} documents")
        updates = []
        desired: dict[int, list[str]] = {}
        for row in rows:
            old = json.loads(row["tickers"])
            new = desired_tickers(row)
            desired[row["id"]] = new
            if sorted(old) != sorted(new):
                updates.append((row["id"], old, new))
        log(f"tag changes: {len(updates)}")
        for doc_id, old, new in updates[:25]:
            log(f"   #{doc_id}: {old} -> {new}")
        if len(updates) > 25:
            log(f"   ... and {len(updates) - 25} more")
        if not dry:
            for doc_id, _old, new in updates:
                conn.execute(
                    "UPDATE documents SET tickers = ?, sectors = ? WHERE id = ?",
                    (
                        json.dumps(new, ensure_ascii=False),
                        json.dumps(sectors_for(new), ensure_ascii=False),
                        doc_id,
                    ),
                )
        changed = [u[0] for u in updates]

    # 3. Chroma: delete + re-add ----------------------------------------------
    with db.connect() as conn:
        long_body = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM documents WHERE LENGTH(body) > ?",
                (OLD_PASSAGE_BODY_CHARS,),
            )
        ]
    stale = chroma_divergent_ids(desired) - {d["id"] for d in inserted}
    if stale:
        log(f"chroma metadata divergent from sqlite on {len(stale)} ids: "
            f"{sorted(stale)[:20]}")
    reembed = sorted(
        set(changed) | set(long_body) | set(stale) | {d["id"] for d in inserted}
    )
    log(
        f"to re-embed: {len(reembed)} (retagged {len(changed)}, "
        f"stale-chroma-keys {len(stale)}, longer-passage {len(long_body)}, "
        f"new {len(inserted)})"
    )
    if dry:
        log("dry run: stopping before any Chroma write")
        return 0

    if reembed:
        log("loading the embedding model (2.24 GB, one time)")
        vectorstore.delete_documents(reembed)
        log(f"deleted {len(reembed)} ids from Chroma")
        with db.connect() as conn:
            for start in range(0, len(reembed), 100):
                batch = db.get_documents(conn, reembed[start : start + 100])
                vectorstore.index_documents(batch)
                log(f"   re-added {min(start + 100, len(reembed))}/{len(reembed)}")

    # 4. heal + seed ----------------------------------------------------------
    healed = reindex_missing()
    log(f"reindex_missing indexed {healed} documents")
    with db.connect() as conn:
        seeded = db.seed_seen_articles(conn)
    log(f"seen_articles seeded: {seeded} rows")

    # 5. verify ---------------------------------------------------------------
    log("verifying")
    problems = []
    with db.connect() as conn:
        sq_total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        corpus_n = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE source='corpus'"
        ).fetchone()[0]
        sq_tickers = {}
        for t in COMPANIES:
            sq_tickers[t] = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE tickers LIKE ?", (f'%"{t}"%',)
            ).fetchone()[0]
    ch_ids = vectorstore.indexed_ids()
    if sq_total != len(ch_ids):
        problems.append(f"count mismatch: sqlite {sq_total} vs chroma {len(ch_ids)}")
    if corpus_n == 0:
        problems.append("corpus rows still 0")

    col = vectorstore._get_collection()
    for t in COMPANIES:
        got = col.get(where={f"t_{t}": {"$eq": True}}, include=[])
        n_ch = len(got["ids"])
        flag = "" if n_ch == sq_tickers[t] else "  <-- MISMATCH"
        log(f"   {t}: sqlite {sq_tickers[t]:>4}  chroma {n_ch:>4}{flag}")
        if n_ch != sq_tickers[t]:
            problems.append(f"t_{t}: sqlite {sq_tickers[t]} vs chroma {n_ch}")

    log(f"documents: {sq_total} sqlite / {len(ch_ids)} chroma; corpus rows {corpus_n}")
    if problems:
        log("FAILED:")
        for p in problems:
            log(f"   {p}")
        return 1
    log("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
