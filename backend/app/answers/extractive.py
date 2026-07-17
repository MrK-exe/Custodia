"""Extractive answers: real sentences from real documents, with citations.

No LLM in 1.0 by decision. Every word a judge reads here was written by a named
publisher and is traceable to a source URL, which is the honesty story, not a
limitation. `generate()` below is the reserved slot where LLM generation lands in
2.0 without any route or client change: the response contract already carries
`mode`, so a client that renders `mode == "extractive"` today keeps working when a
second mode appears.
"""
import re

from ..aliases import display_name
from ..text_utils import normalize_ar

MAX_PASSAGES = 5
SNIPPET_CHARS = 320

# Measured by scripts/relevance_eval.py against the live index, not guessed.
# ar: worst gold 0.174 vs nearest negative 0.199 -> separable.
# en: worst gold 0.209 vs nearest negative 0.204 -> OVERLAPS. "almarai quarterly
# profits" is a real query that sits FURTHER out than the gibberish "asdfghjkl",
# because a cross-lingual match is weaker than a same-language one. So distance
# alone cannot gate English, and MIN_SPREAD below carries the rest.
TAU_AR = 0.194
TAU_EN = 0.229

# A query with no anchor in the corpus is equidistant from every document, so its
# top-k is flat (asdfghjkl spans 0.005; a real query spans 0.03-0.08). This catches
# the gibberish that slips under tau_en. Needs enough hits to describe a shape.
MIN_SPREAD = 0.012
MIN_HITS_FOR_SPREAD = 5

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟।])\s+|\n+")
_ARABIC = re.compile(r"[؀-ۿ]")
_TOKEN = re.compile(r"[0-9a-zء-ي]+")
# Words too common to signal relevance when scoring which sentence to quote
_STOP = {
    "في", "من", "على", "الى", "عن", "مع", "هذا", "هذه", "التي", "الذي", "ان", "او",
    "the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "are", "what",
}


def query_locale(query: str) -> str:
    return "ar" if _ARABIC.search(query) else "en"


def threshold_for(locale: str) -> float:
    return TAU_AR if locale == "ar" else TAU_EN


def _tokens(text: str) -> set[str]:
    return {
        t for t in _TOKEN.findall(normalize_ar(text).lower())
        if len(t) > 1 and t not in _STOP
    }


def _sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s and s.strip()]
    return parts or ([text.strip()] if text and text.strip() else [])


def best_snippet(title: str, body: str, query: str, limit: int = SNIPPET_CHARS) -> str:
    """The stretch of the document that actually answers the query, cut on sentence
    boundaries. Falls back to the opening, which is the lede in news copy."""
    sents = _sentences(body)
    if not sents:
        return title.strip()
    q = _tokens(query)
    scores = [len(q & _tokens(s)) for s in sents]
    start = max(range(len(sents)), key=lambda i: (scores[i], -i)) if any(scores) else 0
    out, total = [], 0
    for s in sents[start:]:
        if total + len(s) > limit and out:
            break
        out.append(s)
        total += len(s) + 1
    snippet = " ".join(out).strip()
    if start > 0:
        snippet = "… " + snippet
    if start + len(out) < len(sents):
        snippet = snippet.rstrip(".") + " …"
    return snippet


def _citation(doc: dict, locale: str) -> dict:
    tickers = doc.get("tickers") or []
    return {
        "id": doc["id"],
        "title": doc["title"],
        "title_en": doc.get("title_en"),
        "publisher": doc.get("publisher") or "",
        "url": doc.get("url") or "",
        "doc_type": doc["doc_type"],
        "published_at": doc.get("published_at"),
        "source": doc["source"],
        "companies": [
            {"ticker": t, "name": display_name(t, locale)} for t in tickers
        ],
    }


def build_answer(query: str, hits: list[dict], docs_by_id: dict[int, dict],
                 locale: str | None = None) -> dict:
    """hits: vectorstore.search output (id + distance), ordered best-first.

    Returns the locked answer contract. `status` is a machine code; the display
    sentence belongs to the frontend, which owns its own Arabic and English copy.
    """
    locale = locale or query_locale(query)
    tau = threshold_for(locale)

    if not hits:
        return {"mode": "extractive", "status": "no_results", "text": None,
                "passages": [], "citations": [], "locale": locale, "threshold": tau}

    spread = hits[-1]["distance"] - hits[0]["distance"]
    if len(hits) >= MIN_HITS_FOR_SPREAD and spread < MIN_SPREAD:
        # Flat distribution: the query anchors on nothing, every doc is equally far.
        return {"mode": "extractive", "status": "below_threshold", "text": None,
                "passages": [], "citations": [], "locale": locale, "threshold": tau,
                "reason": "no_anchor", "best_distance": round(hits[0]["distance"], 4),
                "spread": round(spread, 4)}

    kept = [h for h in hits if h["distance"] <= tau][:MAX_PASSAGES]
    if not kept:
        return {"mode": "extractive", "status": "below_threshold", "text": None,
                "passages": [], "citations": [], "locale": locale, "threshold": tau,
                "reason": "too_far", "best_distance": round(hits[0]["distance"], 4),
                "spread": round(spread, 4)}

    # Ties on distance break toward the more recent document; undated (registry,
    # licences) sort last rather than pretending to be from today.
    kept.sort(key=lambda h: (round(h["distance"], 3),
                             -(docs_by_id.get(h["id"], {}).get("published_at") or 0)))

    passages, citations = [], []
    for hit in kept:
        doc = docs_by_id.get(hit["id"])
        if not doc:
            continue
        passages.append({
            "doc_id": doc["id"],
            "text": best_snippet(doc["title"], doc.get("body", ""), query),
            "title": doc["title"],
            "distance": round(hit["distance"], 4),
            "doc_type": doc["doc_type"],
        })
        citations.append(_citation(doc, locale))

    return {
        "mode": "extractive",
        "status": "ok",
        "text": None,  # reserved: 2.0 fills this from generate()
        "passages": passages,
        "citations": citations,
        "locale": locale,
        "threshold": tau,
    }


def generate(query: str, passages: list[dict], locale: str) -> str | None:
    """Reserved LLM slot. 1.0 answers extractively by decision, so this returns None
    and `mode` stays "extractive". A 2.0 implementation synthesizes `passages` into
    prose, sets mode="generated", and must keep citing the same citation ids: the
    contract around it does not change.
    """
    return None
