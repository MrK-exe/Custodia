"""Per-topic deep research: everything the index knows about a query, on one page.

Extractive aggregation, no LLM (locked for 1.0): the extractive answer, the full
result set grouped by document type, the companies implicated, and a dated timeline.
Nothing is generated; every item is a real document with a citation.
"""
from ..aliases import COMPANIES, display_name
from ..answers import extractive
from ..storage import db, vectorstore

DOC_TYPE_ORDER = ["news", "disclosure", "law", "mandate", "ownership",
                  "geopolitics", "funding", "dataset", "registry"]


def _doc_public(d: dict) -> dict:
    return {
        "id": d["id"], "title": d["title"], "title_en": d.get("title_en"), "publisher": d.get("publisher", ""),
        "url": d.get("url", ""), "doc_type": d["doc_type"],
        "published_at": d.get("published_at"), "source": d["source"],
        "tickers": d.get("tickers", []),
    }


def research(query: str, k: int = 24) -> dict:
    hits = vectorstore.search(query, k=k)
    with db.connect() as conn:
        docs = db.get_documents(conn, [h["id"] for h in hits])
    by_id = {d["id"]: d for d in docs}
    answer = extractive.build_answer(query, hits, by_id)

    # group by doc_type, preserving a sensible order
    groups: dict[str, list] = {}
    for d in docs:
        groups.setdefault(d["doc_type"], []).append(_doc_public(d))
    grouped = [
        {"doc_type": dt, "docs": groups[dt]}
        for dt in DOC_TYPE_ORDER if dt in groups
    ]

    # companies implicated across the result set, by mention count
    counts: dict[str, int] = {}
    for d in docs:
        for t in d.get("tickers", []):
            counts[t] = counts.get(t, 0) + 1
    entities = sorted(
        (
            {"ticker": t, "name_ar": COMPANIES.get(t, {}).get("name_ar", t),
             "name_en": COMPANIES.get(t, {}).get("name_en", t), "count": n}
            for t, n in counts.items() if t in COMPANIES
        ),
        key=lambda e: -e["count"],
    )

    # dated timeline, newest first
    timeline = sorted(
        (_doc_public(d) for d in docs if d.get("published_at")),
        key=lambda d: -(d["published_at"] or 0),
    )[:20]

    return {
        "query": query,
        "answer": answer,
        "result_count": len(docs),
        "groups": grouped,
        "entities": entities,
        "timeline": timeline,
    }


def recent(limit: int = 6, lang: str = "ar") -> list[dict]:
    """Latest real headlines (non-registry), newest first, for the splash chips."""
    with db.connect() as conn:
        lang_clause = " AND title_en IS NOT NULL" if lang == "en" else " AND source != 'google_news_en'"
        rows = conn.execute(
            f"""SELECT id, title, title_en, doc_type, url, published_at, tickers FROM documents
               WHERE doc_type != 'registry' AND published_at IS NOT NULL{lang_clause}
               ORDER BY published_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    out = []
    import json
    for r in rows:
        out.append({
            "id": r["id"], "title": r["title"], "title_en": r["title_en"], "doc_type": r["doc_type"],
            "url": r["url"], "published_at": r["published_at"],
            "tickers": json.loads(r["tickers"]),
        })
    return out
