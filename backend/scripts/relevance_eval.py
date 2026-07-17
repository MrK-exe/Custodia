"""Bilingual relevance eval + threshold tuning.

A single absolute cosine threshold is not separable across languages: a cross-lingual
hit (EN query, AR document) sits systematically further away than a same-language one,
so one tau either lets English junk through or silently drops real English answers.
Hence tau per query language, measured rather than guessed.

Procedure (run with the backend stopped):
  1. retrieve at k=8 with NO threshold
  2. gate on RECALL first. If a gold doc is missing from the raw top-8 that is a
     retrieval bug; fix retrieval, do not move tau to paper over it.
  3. tau = max gold distance + margin, per language
  4. verify every negative's BEST distance is above tau
  5. freeze into app/answers/extractive.py

    cd backend && .venv/Scripts/python.exe scripts/relevance_eval.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.answers.extractive import TAU_AR, TAU_EN, query_locale  # noqa: E402
from app.storage import vectorstore  # noqa: E402

MARGIN = 0.02

# (query, locale, [substrings that identify an acceptable gold document])
POSITIVES = [
    ("عقد أرامكو مع هاليبرتون لتطوير الغاز", "ar", ["هاليبرتون"]),
    ("توزيعات أرباح اس تي سي", "ar", ["stc", "اس تي سي", "إس تي سي"]),
    ("نتائج المراعي الربع الثاني", "ar", ["المراعي"]),
    ("زيادة رأس مال مصرف الراجحي", "ar", ["الراجحي"]),
    ("أرباح معادن", "ar", ["معادن"]),
    ("نظام الشركات الجديد", "ar", ["نظام الشركات"]),
    ("رؤية السعودية 2030", "ar", ["رؤية السعودية"]),
    ("هجوم بقيق", "ar", ["بقيق"]),
    ("إدراج أرامكو في تداول", "ar", ["أرامكو", "ارامكو"]),
    ("تمويل الشركات الناشئة السعودية", "ar", ["تمارا", "تابي", "جولة"]),
    ("aramco helicopter crash", "en", ["مروحية"]),
    ("stc dividends", "en", ["stc", "إس تي سي"]),
    ("almarai quarterly profits", "en", ["المراعي"]),
    ("saudi aramco ipo", "en", ["أرامكو", "ارامكو"]),
    ("vision 2030 economic reform", "en", ["رؤية السعودية", "2030"]),
]

NEGATIVES = [
    ("أفضل مطاعم البرجر في الرياض", "ar"),
    ("كيف أطبخ الكبسة السعودية", "ar"),
    ("مواعيد رحلات الطيران الى دبي", "ar"),
    ("asdfghjkl", "en"),
    ("weather in tokyo tomorrow", "en"),
    ("best football players of 2026", "en"),
]


def main() -> int:
    print("loading model\n")
    rows = []
    recall_fail = []
    for query, locale, golds in POSITIVES:
        hits = vectorstore.search(query, k=8)
        gold_d = None
        for h in hits:
            text = h["document"]
            if any(g.lower() in text.lower() for g in golds):
                gold_d = h["distance"]
                break
        if gold_d is None:
            recall_fail.append((query, hits[0]["distance"] if hits else None,
                                hits[0]["document"].splitlines()[0][:50] if hits else ""))
        rows.append((locale, query, gold_d, hits[0]["distance"] if hits else None))

    print("=== POSITIVES (distance of the first gold doc in the raw top-8) ===")
    for locale, query, gold_d, best in rows:
        mark = "  <-- NOT RETRIEVED" if gold_d is None else ""
        print(f"  [{locale}] {gold_d if gold_d is None else f'{gold_d:.3f}'}  "
              f"(best {best:.3f})  {query}{mark}")

    if recall_fail:
        print("\nRECALL FAILURES (fix retrieval, do NOT raise tau):")
        for q, d, t in recall_fail:
            print(f"  {q}  -> best {d:.3f} {t}")

    print("\n=== NEGATIVES (best distance; must land ABOVE tau) ===")
    neg = {"ar": [], "en": []}
    for query, locale in NEGATIVES:
        hits = vectorstore.search(query, k=3)
        best = hits[0]["distance"] if hits else 1.0
        neg[locale].append(best)
        print(f"  [{locale}] {best:.3f}  {query}")
        print(f"           top: {hits[0]['document'].splitlines()[0][:62]}")

    print("\n=== TAU ===")
    proposed = {}
    for locale in ("ar", "en"):
        golds = [d for lo, _q, d, _b in rows if lo == locale and d is not None]
        if not golds:
            continue
        worst_gold = max(golds)
        best_neg = min(neg[locale]) if neg[locale] else 1.0
        tau = round(worst_gold + MARGIN, 3)
        proposed[locale] = tau
        gap = best_neg - worst_gold
        verdict = "SEPARABLE" if tau < best_neg else "NOT SEPARABLE"
        print(f"  {locale}: worst gold {worst_gold:.3f} | nearest negative {best_neg:.3f} "
              f"| gap {gap:+.3f} -> tau {tau}  [{verdict}]")
    print(f"\n  current in code: TAU_AR={TAU_AR}  TAU_EN={TAU_EN}")
    print(f"  proposed       : TAU_AR={proposed.get('ar')}  TAU_EN={proposed.get('en')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
