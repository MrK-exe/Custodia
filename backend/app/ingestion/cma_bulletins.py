import io
import json
import time
import zipfile

import requests

from ..storage import db

HEADERS = {"User-Agent": "KSATerminal/0.1"}
BULLETINS = {
    "equities": "https://cma.gov.sa/AboutCMA/ResearchAndReports/opendata/Documents/Statistical%20Bulletin/JSON/Statistical_Bulletin%202%20Equities_JSON.zip",
    "fintech": "https://cma.gov.sa/AboutCMA/ResearchAndReports/opendata/Documents/Statistical%20Bulletin/JSON/Statistical_Bulletin%207%20Fintech_JSON.zip",
}


def ingest_bulletins() -> list[dict]:
    """Download the Equities and Fintech statistical bulletins (JSON zips) and
    store every inner sheet raw in cma_stats. Returns [] (no vector documents)."""
    now = int(time.time())
    with db.connect() as conn:
        for bulletin, url in BULLETINS.items():
            response = requests.get(url, headers=HEADERS, timeout=120)
            response.raise_for_status()
            archive = zipfile.ZipFile(io.BytesIO(response.content))
            for member in archive.namelist():
                if not member.lower().endswith(".json"):
                    continue
                raw = archive.read(member).decode("utf-8-sig", errors="replace")
                try:
                    payload = json.dumps(json.loads(raw), ensure_ascii=False)
                except json.JSONDecodeError:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO cma_stats "
                    "(bulletin, sheet, payload, fetched_at) VALUES (?, ?, ?, ?)",
                    (bulletin, member, payload, now),
                )
    return []


def bulletin_sheets() -> dict[str, list[str]]:
    with db.connect() as conn:
        rows = conn.execute("SELECT bulletin, sheet FROM cma_stats ORDER BY bulletin, sheet").fetchall()
    sheets: dict[str, list[str]] = {}
    for row in rows:
        sheets.setdefault(row["bulletin"], []).append(row["sheet"])
    return sheets
