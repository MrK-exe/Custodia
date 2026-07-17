"""Prime the quote cache for the whole watchlist, once, before a demo.

Each watchlist ticker gets one real SAHMK quote (cache-first, budget-aware) so the
dashboard and company pages have live order-book + money-flow data for every company
without spending budget during the demo itself. Run off-hours (after 15:25 AST or on
the weekend) so cached entries stay fresh through demo day.

    cd backend && .venv/Scripts/python.exe scripts/prime_quotes.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import WATCHLIST  # noqa: E402
from app.ingestion import sahmk_client  # noqa: E402


def main() -> int:
    start = sahmk_client.requests_today()
    print(f"budget before: {sahmk_client.budget_remaining()} remaining ({start} used)")
    for t in WATCHLIST:
        try:
            q = sahmk_client.get_quote(t)
            data = q.get("data") or {}
            px = data.get("price")
            has_flow = "liquidity" in data
            has_book = "bid" in data and "ask" in data
            print(f"  {t}: price {px} | src {q['source']} | book {has_book} | flow {has_flow}")
        except sahmk_client.SahmkError as exc:
            print(f"  {t}: FAILED {exc}")
    spent = sahmk_client.requests_today() - start
    print(f"budget after: {sahmk_client.budget_remaining()} remaining (spent {spent} this run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
