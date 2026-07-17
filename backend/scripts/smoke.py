"""End-to-end smoke test. No pytest needed (it is not installed); httpx ships with
fastapi's TestClient.

    cd backend && .venv/Scripts/python.exe scripts/smoke.py [--allow-sahmk]

The load-bearing assertion is the last one: a full demo pass must spend ZERO SAHMK
requests. The free tier allows 100/day and a rehearsal that quietly spends them is
how the live panels die on stage.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.ingestion import sahmk_client  # noqa: E402
from app.main import app  # noqa: E402
from app.storage import vectorstore  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, ok, detail=""):
    results.append((PASS if ok else FAIL, name, detail))
    print(f"  {PASS if ok else FAIL}  {name}" + (f"  ({detail})" if detail else ""), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-sahmk", action="store_true",
                    help="permit live market calls (spends daily budget)")
    args = ap.parse_args()

    before = sahmk_client.requests_today()
    print(f"SAHMK requests used today at start: {before}/{sahmk_client.DAILY_BUDGET}\n")

    started = time.time()
    with TestClient(app) as client:
        print(f"--- lifespan ({round(time.time() - started, 1)}s to ready)")

        r = client.get("/api/health")
        h = r.json()
        check("health 200", r.status_code == 200)
        check("corpus loaded", h.get("corpus_loaded"), f"{h.get('corpus_documents')} docs")
        check("documents indexed", h.get("documents", 0) > 2900, str(h.get("documents")))
        check("budget reported", isinstance(h.get("budget_remaining"), int),
              f"{h.get('budget_remaining')} left")

        print("\n--- warm-up (the 2.24 GB model must load OFF the request path)")
        # Poll the real readiness signal, not the embedder singleton: the singleton
        # becomes non-null partway through the warm threads search, before it flips
        # state to "ready", so checking the singleton races the state field.
        w = {"state": "loading", "seconds": None}
        for _ in range(180):
            w = client.get("/api/health").json()["warm_up"]
            if w["state"] == "ready":
                break
            time.sleep(1)
        check("model warmed at startup", w["state"] == "ready", f"{w['state']} in {w['seconds']}s")

        print("\n--- search")
        t0 = time.time()
        r = client.post("/api/search", json={"query": "ارامكو"})
        warm_latency = time.time() - t0
        d = r.json()
        check("search 200", r.status_code == 200)
        check("entity routes on ارامكو", (d.get("entity") or {}).get("ticker") == "2222")
        check("warm search is fast", warm_latency < 2.0, f"{warm_latency:.2f}s")

        d = client.post("/api/search", json={"query": "aramco helicopter crash"}).json()
        ok = d["answer"]["status"] == "ok" and d["answer"]["passages"]
        arabic = any("؀" <= c <= "ۿ" for c in (d["answer"]["passages"] or [{}])[0].get("text", ""))
        check("EN query returns Arabic docs (cross-lingual)", bool(ok and arabic))
        check("citations carry a url", bool(d["answer"]["citations"][0].get("url")))

        for q, dt in [("نظام الشركات الجديد", "law"), ("رؤية السعودية 2030", "mandate"),
                      ("جولة تمويل شركة سعودية", "funding"),
                      ("طرح أرامكو العام الأولي", "ownership"),
                      ("هجوم بقيق", "geopolitics"), ("مؤشرات سوق الأسهم", "dataset")]:
            d = client.post("/api/search", json={"query": q, "doc_type": dt}).json()
            check(f"corpus facet {dt}", d["answer"]["status"] == "ok",
                  f"{len(d['answer']['passages'])} passages")

        for q in ["أفضل مطاعم البرجر في الرياض", "asdfghjkl"]:
            d = client.post("/api/search", json={"query": q}).json()
            check(f"empty state for {q[:22]!r}",
                  d["answer"]["status"] in ("below_threshold", "no_results"),
                  d["answer"]["status"])

        d = client.post("/api/search", json={"query": "معادن", "ticker": "1211"}).json()
        titles = " ".join(p["title"] for p in d["answer"]["passages"])
        check("ticker filter 1211 has no rare-earth noise",
              all(w not in titles for w in ["الكونغو", "نادرة", "الصين"]),
              f"{len(d['answer']['passages'])} passages")

        print("\n--- news feeds")
        for sym in ["2222", "1120", "1180", "1211"]:
            d = client.get(f"/api/news/{sym}").json()
            docs = d["documents"]
            reg = [x for x in docs if x["doc_type"] == "registry"]
            check(f"news/{sym} non-empty, no registry", bool(docs) and not reg,
                  f"{len(docs)} docs")

        r = client.get("/api/news/abc")
        check("news/{symbol} rejects non-tickers", r.status_code in (400, 422), str(r.status_code))

        print("\n--- companies typeahead (must not spend budget)")
        d = client.get("/api/companies", params={"q": "الراجحي"}).json()
        check("typeahead answers locally", d["source"] == "aliases" and d["results"])

        print("\n--- market data")
        r = client.get("/api/quote/2222")
        q = r.json()
        check("quote 2222 served from cache", q.get("source") == "cache",
              f"source={q.get('source')} stale={q.get('stale')}")
        check("quote carries honesty envelope",
              all(k in q for k in ("delayed", "as_of", "fetched_at", "stale")))
        if args.allow_sahmk:
            m = client.get("/api/market").json()
            check("market summary present", "summary" in m and "movers" in m)

        print("")
        print("--- analytics (dashboard + charts + per-company, budget-safe)")
        dash = client.get("/api/dashboard").json()
        check("dashboard watchlist 8", len(dash["watchlist"]) == 8, str(len(dash["watchlist"])))
        check("dashboard sectors present", len(dash["sectors"]) > 0)
        check("dashboard trending real (Aramco top)", dash["trending"][0]["ticker"] == "2222")
        check("dashboard calendar from corpus", len(dash["calendar"]) > 0)
        hist = client.get("/api/history/2222").json()
        check("history 2222 full series", len(hist["points"]) >= 120 and hist["source"] == "sample")
        check("history NaN-safe (early sma20 null)", hist["points"][3]["sma20"] is None)
        before_co = sahmk_client.requests_today()
        co = client.get("/api/company/2222").json()
        check("company 2222 chart+news+context", bool(co["series"]) and len(co["news"]) > 0 and len(co["context"]) > 0, f"news {len(co['news'])} context {len(co['context'])}")
        for sym in ["1120", "7010", "2010", "1180", "2280", "4013", "1211"]:
            client.get(f"/api/company/{sym}")
        check("browsing all company pages spends 0 SAHMK", sahmk_client.requests_today() - before_co == 0, f"spent {sahmk_client.requests_today() - before_co}")
        check("company bad ticker 404", client.get("/api/company/0000").status_code == 404)

        print("")
        print("--- deep research + technical signal + recent (extractive, budget-safe)")
        before_r = sahmk_client.requests_today()
        co = client.get("/api/company/2222").json()
        sig = co["signal"]
        check("technical signal present, not advice", sig["label"] in ("bullish","neutral","bearish") and sig["advice"] is False, f"{sig['label']} advice={sig['advice']}")
        check("signal has money-flow (real) component", any(c.get("real") for c in sig["components"]))
        rec = client.get("/api/recent?limit=5").json()["recent"]
        check("recent headlines returned", len(rec) == 5)
        res = client.post("/api/research", json={"query": "Vision 2030"}).json()
        check("research aggregates docs+entities+timeline", res["result_count"] > 5 and len(res["entities"]) > 0 and len(res["timeline"]) > 0, f"docs {res['result_count']} entities {len(res['entities'])}")
        check("research spends 0 SAHMK", sahmk_client.requests_today() - before_r == 0)

        print("\n--- store integrity")
        docs = client.get("/api/health").json()["documents"]
        chroma = len(vectorstore.indexed_ids())
        check("sqlite count == chroma count", docs == chroma, f"{docs} vs {chroma}")

    after = sahmk_client.requests_today()
    spent = after - before
    print()
    budgeted = 2 if args.allow_sahmk else 0
    check(f"SAHMK spend within budget (<= {budgeted})", spent <= budgeted, f"spent {spent}")

    failed = [r for r in results if r[0] == FAIL]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    for _, name, detail in failed:
        print(f"  FAILED: {name} {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
