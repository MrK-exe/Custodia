"""FastAPI entrypoint.

Bound to 127.0.0.1 on purpose (see launch.json). POST /api/ingest/refresh is
unauthenticated, and CORS restricts reading a response, never sending the request,
so on 0.0.0.0 any web page the presenter has open could start an 18 minute scrape
mid-demo. Loopback is the control.
"""
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Path, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import aliases, dm
from .analysis import market as market_analysis
from .analysis import research as research_analysis
from .analysis import series as series_analysis
from .analysis import signal as signal_analysis
from .answers import extractive
from .config import WATCHLIST
from .ingestion import refresh as refresh_mod
from .ingestion import sahmk_client
from .ingestion.sahmk_client import SahmkError
from .storage import db, vectorstore

SYMBOL = Path(pattern=r"^\d{4}$", description="Tadawul 4-digit code")

_warm = {"state": "cold", "seconds": None}


def _warm_embedder() -> None:
    """Load the 2.24 GB ONNX model off the request path.

    Cold, the first search pays the whole load. Measured 5-12s, and the first search
    of the day is the one a judge types.
    """
    started = time.time()
    _warm["state"] = "loading"
    try:
        vectorstore.search("تهيئة", k=1)
        _warm["state"] = "ready"
    except Exception as exc:  # noqa: BLE001
        _warm["state"] = f"failed: {type(exc).__name__}"
    finally:
        _warm["seconds"] = round(time.time() - started, 1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    dm.ensure_seeded()
    try:
        from .storage import db as _db
        with _db.connect() as _c:
            if _c.execute("SELECT COUNT(*) FROM history WHERE source='sample'").fetchone()[0] == 0:
                from . import sample_data
                sample_data.generate()
                print("[startup] generated sample OHLCV series")
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] sample series generation skipped: {exc}")
    try:
        healed = refresh_mod.reindex_missing()
        if healed:
            print(f"[startup] reindexed {healed} documents missing from chroma")
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] reindex_missing skipped: {exc}")
    threading.Thread(target=_warm_embedder, name="warm-embedder", daemon=True).start()
    yield


app = FastAPI(title="KSA Market Intelligence", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Next dev serves on both spellings and they are different origins to a browser
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(SahmkError)
def _sahmk_error(request, exc: SahmkError):
    return _error(503, "market_data_unavailable", str(exc))


@app.exception_handler(refresh_mod.RefreshAlreadyRunning)
def _refresh_running(request, exc):
    return _error(409, "refresh_already_running", str(exc))


@app.exception_handler(RequestValidationError)
def _validation_error(request, exc: RequestValidationError):
    return _error(400, "invalid_request", str(exc.errors()[:3]))


@app.exception_handler(Exception)
def _unhandled(request, exc: Exception):
    return _error(500, "internal_error", f"{type(exc).__name__}: {exc}"[:200])


# --- search ----------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    k: int = Field(default=8, ge=1, le=25)
    doc_type: str | None = None
    sector: str | None = None
    ticker: str | None = Field(default=None, pattern=r"^\d{4}$")
    date_from: int | None = None
    date_to: int | None = None


@app.post("/api/search")
def search(req: SearchRequest):
    """Retrieval plus an extractive answer. `entity` is set when the query IS a
    company ("ارامكو", "2222", "Al Rajhi Bank"), which is what the UI routes on."""
    ticker, match = aliases.resolve_query_detail(req.query)
    hits = vectorstore.search(
        req.query, k=req.k, doc_type=req.doc_type, sector=req.sector,
        ticker=req.ticker, date_from=req.date_from, date_to=req.date_to,
    )
    with db.connect() as conn:
        docs = db.get_documents(conn, [h["id"] for h in hits])
    by_id = {d["id"]: d for d in docs}
    answer = extractive.build_answer(req.query, hits, by_id)
    return {
        "query": req.query,
        "entity": _entity(ticker, match),
        "answer": answer,
        "results": [
            {
                "id": d["id"], "title": d["title"], "title_en": d.get("title_en"), "publisher": d.get("publisher", ""),
                "url": d.get("url", ""), "doc_type": d["doc_type"],
                "published_at": d.get("published_at"), "source": d["source"],
                "tickers": d.get("tickers", []),
                "distance": round(next(h["distance"] for h in hits if h["id"] == d["id"]), 4),
            }
            for d in docs
        ],
    }


def _entity(ticker: str | None, match: str | None = "exact") -> dict | None:
    if not ticker:
        return None
    info = aliases.COMPANIES.get(ticker)
    if info is None:
        return None
    return {
        "ticker": ticker,
        "name_ar": info["name_ar"],
        "name_en": info["name_en"],
        "sector_ar": info["sector_ar"],
        "sector_en": info["sector_en"],
        # "exact": the company IS the query, so lead with the price card.
        # "prefix": the query is a question about it, so lead with the answer.
        "match": match or "exact",
    }


# --- market data (every response carries the honesty envelope) --------------------

@app.get("/api/quote/{symbol}")
def quote(symbol: str = SYMBOL):
    return sahmk_client.get_quote(symbol)


@app.get("/api/market")
def market():
    return {"summary": sahmk_client.get_market_summary(), "movers": sahmk_client.get_movers()}


@app.get("/api/news/{symbol}")
def news(symbol: str = SYMBOL, limit: int = Query(default=20, ge=1, le=50), lang: str = Query(default="ar")):
    with db.connect() as conn:
        docs = db.documents_by_ticker(conn, symbol, limit=limit, lang=lang)
    return {"symbol": symbol, "entity": _entity(symbol), "documents": docs}


@app.get("/api/companies")
def companies(q: str = Query(min_length=1, max_length=60)):
    """Watchlist first. The typeahead must never spend the SAHMK budget per
    keystroke: 8 companies of local aliases answer every demo query for free."""
    ticker = aliases.resolve_query(q)
    if ticker:
        return {"source": "aliases", "results": [_entity(ticker)]}
    needle = q.strip().lower()
    local = [
        _entity(t) for t, info in aliases.COMPANIES.items()
        if needle in info["name_ar"].lower() or needle in info["name_en"].lower()
        or needle in t
    ]
    return {"source": "aliases", "results": local}


# --- dm --------------------------------------------------------------------------
# Seeded personas, no auth, no replies. Sample data, and the UI badges it as such.

class MessageRequest(BaseModel):
    body: str = Field(default="", max_length=2000)
    doc_id: int | None = None


@app.get("/api/dm/threads")
def dm_threads():
    return {"threads": dm.list_threads(), "sample": True}


@app.get("/api/dm/threads/{thread_id}")
def dm_thread(thread_id: int = Path(ge=1)):
    thread = dm.get_thread(thread_id)
    if thread is None:
        return _error(404, "thread_not_found", f"thread {thread_id} does not exist")
    return {**thread, "sample": True}


@app.post("/api/dm/threads/{thread_id}/messages")
def dm_post(req: MessageRequest, thread_id: int = Path(ge=1)):
    if not req.body.strip() and req.doc_id is None:
        return _error(400, "empty_message", "a message needs text, a document, or both")
    try:
        sent = dm.post_message(thread_id, req.body, req.doc_id)
    except ValueError as exc:
        return _error(400, "invalid_document", str(exc))
    if sent is None:
        return _error(404, "thread_not_found", f"thread {thread_id} does not exist")
    return dm.get_thread(thread_id)


# --- analytics (charts run on the sample series; every response says source) -----

@app.get("/api/dashboard")
def dashboard(lang: str = Query(default="ar")):
    """Splash dashboard: real brief/trending/calendar + sample-badged watchlist and
    sector heat. The frontend badges every sample-sourced panel."""
    return market_analysis.dashboard(lang)


@app.get("/api/history/{symbol}")
def history(symbol: str = SYMBOL):
    q = sahmk_client.cached_quote(symbol)
    anchor = None
    if q and isinstance(q.get("data"), dict):
        raw = q["data"]
        anchor = raw.get("price") or raw.get("last") or raw.get("close")
    s = series_analysis.series(symbol, anchor=anchor if isinstance(anchor, (int, float)) else None)
    if s is None:
        return _error(404, "no_series", f"no sample series for {symbol}; run app.sample_data")
    return s


@app.get("/api/company/{symbol}")
def company(symbol: str = SYMBOL, lang: str = Query(default="ar")):
    """Everything about one ticker in one call: identity, best-effort cached quote,
    the sample price series, its real news feed, and the real corpus context
    (laws, mandates, ownership, geopolitics that mention it)."""
    entity = _entity(symbol)
    if entity is None:
        return _error(404, "unknown_ticker", f"{symbol} is not on the watchlist")
    # cache-only: a company drill-in must never spend the daily SAHMK budget
    quote = sahmk_client.cached_quote(symbol)
    anchor = None
    if quote and isinstance(quote.get("data"), dict):
        raw = quote["data"]
        px = raw.get("price") or raw.get("last") or raw.get("close")
        anchor = px if isinstance(px, (int, float)) else None
    with db.connect() as conn:
        news = db.documents_by_ticker(conn, symbol, limit=12, lang=lang)
        context = db.documents_by_ticker(
            conn, symbol, limit=12, lang=lang,
            exclude_types=("registry", "news", "disclosure"),
        )
    net_flow = None
    if quote and isinstance(quote.get("data"), dict):
        liq = quote["data"].get("liquidity")
        if isinstance(liq, dict):
            net_flow = liq.get("net_value")
    return {
        "entity": entity,
        "quote": quote,  # carries bid/ask + liquidity (money flow), all real
        "series": series_analysis.series(symbol, anchor=anchor),
        "performance": series_analysis.performance(symbol, anchor=anchor),  # sample
        "signal": signal_analysis.technical_signal(symbol, anchor=anchor, net_flow=net_flow),
        "news": news,
        "context": context,
    }


@app.get("/api/recent")
def recent(limit: int = Query(default=6, ge=1, le=20), lang: str = Query(default="ar")):
    return {"recent": research_analysis.recent(limit, lang)}


@app.post("/api/research")
def research(req: SearchRequest):
    """Deep research on a topic: extractive answer + all matching docs grouped by
    type + companies implicated + a dated timeline. Extractive, no LLM."""
    return research_analysis.research(req.query, k=max(req.k, 24))


# --- ops -------------------------------------------------------------------------

@app.get("/api/health")
def health():
    with db.connect() as conn:
        documents = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        corpus = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE source='corpus'"
        ).fetchone()[0]
    return {
        "status": "ok",
        "documents": documents,
        "corpus_loaded": corpus > 0,
        "corpus_documents": corpus,
        # never call _get_embedder() here: a health check must not block on a 2.24 GB load
        "model_loaded": vectorstore._embedder is not None,
        "warm_up": _warm,
        "requests_today": sahmk_client.requests_today(),
        "budget_remaining": sahmk_client.budget_remaining(),
        "last_refresh": refresh_mod.last_refresh(),
        "watchlist": WATCHLIST,
    }


@app.post("/api/ingest/refresh")
def ingest_refresh(light: bool = Query(default=True)):
    """light=true by default: the CMA registries are effectively static and cost a
    ~13 minute single-transaction re-pull. Never run this during a demo."""
    sources = refresh_mod.LIGHT_SOURCES if light else None
    return refresh_mod.refresh_all(sources=sources)
