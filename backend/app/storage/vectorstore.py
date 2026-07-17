import threading

import chromadb

from ..config import BACKEND_DIR, CHROMA_DIR, EMBEDDING_MODEL
from ..text_utils import normalize_ar

# Keep the model cache out of %TEMP% so Windows cleanup cannot evict it before a demo.
_MODEL_CACHE_DIR = BACKEND_DIR / ".fastembed_cache"

_lock = threading.Lock()
_embedder = None
_collection = None


def _get_embedder():
    """Lazy singleton. First call downloads the ONNX model into the local cache."""
    global _embedder
    with _lock:
        if _embedder is None:
            from fastembed import TextEmbedding

            _embedder = TextEmbedding(
                model_name=EMBEDDING_MODEL, cache_dir=str(_MODEL_CACHE_DIR)
            )
    return _embedder


def _get_collection():
    global _collection
    with _lock:
        if _collection is None:
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            _collection = client.get_or_create_collection(
                "documents", metadata={"hnsw:space": "cosine"}
            )
    return _collection


# e5 truncates at 512 tokens. Arabic runs ~3.5 chars/token, so ~1800 body chars
# plus the title and the "passage: " prefix is what actually fills that window;
# 1000 left roughly 40% of it unused, and the curated corpus docs are the
# longest in the index.
PASSAGE_BODY_CHARS = 1800


def _passage_text(title: str, body: str) -> str:
    return f"{title}\n{body[:PASSAGE_BODY_CHARS]}"


def index_documents(docs: list[dict]) -> None:
    """docs: dicts with id, title, body, doc_type, tickers, sectors, source,
    publisher, published_at (epoch int). fastembed 0.8.0 does NOT apply the e5
    prefixes itself (verified in its source), so they are added explicitly here."""
    if not docs:
        return
    texts = [
        "passage: " + normalize_ar(_passage_text(d["title"], d.get("body", "")))
        for d in docs
    ]
    embeddings = [e.tolist() for e in _get_embedder().embed(texts)]
    metadatas = []
    for d in docs:
        meta = {
            "doc_type": d["doc_type"],
            "tickers": ",".join(d.get("tickers", [])),
            "sector": (d.get("sectors") or [""])[0],
            "source": d["source"],
            "publisher": d.get("publisher", ""),
            "published_at": int(d.get("published_at") or 0),
        }
        for ticker in d.get("tickers", []):
            meta[f"t_{ticker}"] = True
        metadatas.append(meta)
    _get_collection().upsert(
        ids=[str(d["id"]) for d in docs],
        embeddings=embeddings,
        documents=[_passage_text(d["title"], d.get("body", "")) for d in docs],
        metadatas=metadatas,
    )


def update_metadata(updates: dict) -> None:
    """{id: {key: value}} -> patch Chroma metadata without re-embedding. Chroma
    merges key by key, so this can CHANGE a value but never REMOVE a key; use
    delete_documents + index_documents when a key must disappear."""
    if not updates:
        return
    ids = [str(i) for i in updates]
    _get_collection().update(ids=ids, metadatas=[updates[i] for i in updates])


def delete_documents(ids: list) -> None:
    """Remove ids from the index. Required before re-adding a doc whose tickers
    changed: upsert MERGES metadata key by key, so a t_<ticker> boolean written
    by an earlier tagging run survives a plain re-upsert forever."""
    if not ids:
        return
    _get_collection().delete(ids=[str(i) for i in ids])


def indexed_ids() -> set[str]:
    return set(_get_collection().get(include=[])["ids"])


def search(
    query: str,
    k: int = 5,
    doc_type: str | None = None,
    sector: str | None = None,
    ticker: str | None = None,
    date_from: int | None = None,
    date_to: int | None = None,
) -> list[dict]:
    """Registry docs (93% of the index) drown every query, so the default search
    excludes them; they remain reachable by explicitly passing doc_type='registry'."""
    conditions = []
    if doc_type:
        conditions.append({"doc_type": {"$eq": doc_type}})
    else:
        conditions.append({"doc_type": {"$ne": "registry"}})
    if sector:
        conditions.append({"sector": {"$eq": sector}})
    if ticker:
        conditions.append({f"t_{ticker}": {"$eq": True}})
    if date_from is not None:
        conditions.append({"published_at": {"$gte": date_from}})
    if date_to is not None:
        conditions.append({"published_at": {"$lte": date_to}})
    where = None
    if len(conditions) == 1:
        where = conditions[0]
    elif conditions:
        where = {"$and": conditions}

    embedding = next(
        iter(_get_embedder().embed(["query: " + normalize_ar(query)]))
    ).tolist()
    res = _get_collection().query(
        query_embeddings=[embedding], n_results=k, where=where
    )
    hits = []
    for i, doc_id in enumerate(res["ids"][0]):
        hits.append(
            {
                "id": int(doc_id),
                "distance": res["distances"][0][i],
                "document": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
            }
        )
    return hits
