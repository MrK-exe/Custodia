"""Bake every display payload from the running local engine into static JSON so the
frontend can run with NO backend (GitHub Pages). Search/research are precomputed for a
curated query set. Run with the engine up on :8000 (0 SAHMK; all reads are cache/local)."""
import json, os, sys, urllib.parse
import requests

API = "http://127.0.0.1:8000"
OUT = r"C:/Users/abdul/ksa-terminal/frontend/public/data"
os.makedirs(OUT, exist_ok=True)

TICKERS = ["2222", "1120", "7010", "2010", "1180", "2280", "4013", "1211"]
COMPANIES = {
    "2222": ("Saudi Aramco", "أرامكو"),
    "1120": ("Al Rajhi Bank", "الراجحي"),
    "7010": ("stc", "إس تي سي"),
    "2010": ("SABIC", "سابك"),
    "1180": ("Saudi National Bank", "البنك الأهلي"),
    "2280": ("Almarai", "المراعي"),
    "4013": ("Dr Sulaiman Al Habib", "سليمان الحبيب"),
    "1211": ("Maaden", "معادن"),
}
SUGGESTIONS = [
    "عقد أرامكو مع هاليبرتون لتطوير الغاز", "نتائج المراعي الربع الثاني",
    "رؤية السعودية 2030", "نظام الشركات الجديد",
    "aramco helicopter crash", "stc dividends", "saudi aramco ipo",
]
EXTRA = ["aramco", "al rajhi", "sabic", "almarai", "maaden", "snb", "stc",
         "al habib", "saudi national bank", "vision 2030"]

def norm(q):
    return " ".join(q.strip().split()).lower()

def save(name, obj):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return name

def get(path):
    r = requests.get(API + path, timeout=30); r.raise_for_status(); return r.json()

def post(path, body):
    r = requests.post(API + path, json=body, timeout=60); r.raise_for_status(); return r.json()

written = []

# health
try: written.append(save("health.json", get("/api/health")))
except Exception as e: print("health FAIL", e)

# dashboard + recent (both langs)
for lang in ("ar", "en"):
    written.append(save(f"dashboard-{lang}.json", get(f"/api/dashboard?lang={lang}")))
    written.append(save(f"recent-{lang}.json", get(f"/api/recent?limit=6&lang={lang}")))

# per-company: company payload (both langs), quote, news (both langs)
for tk in TICKERS:
    written.append(save(f"quote-{tk}.json", get(f"/api/quote/{tk}")))
    for lang in ("ar", "en"):
        written.append(save(f"company-{tk}-{lang}.json", get(f"/api/company/{tk}?lang={lang}")))
        written.append(save(f"news-{tk}-{lang}.json", get(f"/api/news/{tk}?lang={lang}")))

# recent headlines feed the clickable chips -> add them to the curated search set
recent_terms = []
for lang in ("ar", "en"):
    rec = json.load(open(os.path.join(OUT, f"recent-{lang}.json"), encoding="utf-8"))
    for it in rec.get("recent", []):
        title = it.get("title_en") if lang == "en" else it.get("title")
        if title:
            recent_terms.append(title)

# curated search index (0 SAHMK: /api/search is local vector search)
company_terms = []
for tk, (en, ar) in COMPANIES.items():
    company_terms += [tk, en, ar]
queries = SUGGESTIONS + EXTRA + company_terms + recent_terms
search_index = {}
ok = 0
for q in queries:
    try:
        search_index[norm(q)] = post("/api/search", {"query": q, "k": 8})
        ok += 1
    except Exception as e:
        print("search FAIL", q[:30], e)
written.append(save("search-index.json", search_index))
print(f"search-index: {ok}/{len(queries)} queries baked, {len(search_index)} keys")

# curated research index (subset)
research_queries = SUGGESTIONS + ["aramco", "stc", "sabic", "vision 2030", "maaden"]
research_index = {}
for q in research_queries:
    try:
        research_index[norm(q)] = post("/api/research", {"query": q, "k": 24})
    except Exception as e:
        print("research FAIL", q[:30], e)
written.append(save("research-index.json", research_index))
print(f"research-index: {len(research_index)} keys")

# DM threads (read-only): list + each thread
try:
    threads = get("/api/dm/threads")
    written.append(save("dm-threads.json", threads))
    for th in threads.get("threads", []):
        tid = th["id"]
        written.append(save(f"dm-thread-{tid}.json", get(f"/api/dm/threads/{tid}")))
except Exception as e:
    print("dm FAIL", e)

print(f"\nBAKED {len(written)} files into {OUT}")
