import json
import time

import requests

from ..dates import parse_timestamp
from ..storage import db

API_BASE = "https://opendataapi.cma.gov.sa/api"
ENDPOINTS = {
    "license": "/Licenses/GetAllOrganizations",
    "cra": "/CRACompanies/GetAllCRACompanies",
    "public_fund": "/PublicFunds/GetAllPublicFunds",
    "private_fund": "/PrivateFunds/GetAllPrivateFunds",
}
HEADERS = {"User-Agent": "KSATerminal/0.1"}
PORTAL_URL = "https://cma.gov.sa/en/AboutCMA/ResearchAndReports/opendata/Pages/default.aspx"

_NAME_KEYS = ("fundName", "name", "organizationName", "companyName", "nameAr", "entityName")


def _record_name(record: dict) -> str:
    for key in _NAME_KEYS:
        value = record.get(key)
        if value:
            return str(value).strip()
    for value in record.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "بدون اسم"


def _record_id(kind: str, record: dict, position: int) -> str:
    for key in ("id", "fundID", "licenseNumber", "crNumber"):
        if record.get(key) is not None:
            return f"{kind}:{record[key]}"
    return f"{kind}:pos{position}"


# Funds carry classification/manager/date fields; licensed persons and credit
# rating agencies carry an entirely different set (title/url/licenses/notes), which
# is why the licence rows indexed as bare names with empty bodies.
_BODY_KEYS = ("classification", "manager", "placeOfIncorporation", "notificationDate",
              "offerStartDate", "offerEndDate", "city", "activity", "licenseDate",
              "licenses", "url", "notes", "craComments", "fundID", "eMail")


def _record_body(record: dict) -> str:
    parts = []
    for key in _BODY_KEYS:
        value = record.get(key)
        if value:
            parts.append(f"{key}: {value}")
    return "\n".join(parts)


def _record_published_at(record: dict) -> int | None:
    """None when the record carries no date. Licensed persons and CRAs have no date
    field at all, and stamping those with fetch time is what made 607 undated rows
    sort newest and bury real news in every per-ticker feed."""
    for key in ("notificationDate", "licenseDate", "offerStartDate"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            ts = parse_timestamp(value)
            if ts:
                return ts
    return None


def ingest_registries() -> list[dict]:
    """Fetch the 4 keyless CMA registries (Arabic), store rows in cma_records and
    as searchable registry documents. Returns inserted documents for indexing."""
    inserted: list[dict] = []
    now = int(time.time())
    with db.connect() as conn:
        for kind, path in ENDPOINTS.items():
            response = requests.get(
                f"{API_BASE}{path}", params={"lang": "ar"}, headers=HEADERS, timeout=60
            )
            response.raise_for_status()
            records = response.json()
            if not isinstance(records, list):
                records = records.get("data", [])
            for position, record in enumerate(records):
                external_id = _record_id(kind, record, position)
                name = _record_name(record)
                conn.execute(
                    "INSERT OR REPLACE INTO cma_records "
                    "(kind, record_id, name, payload, fetched_at) VALUES (?, ?, ?, ?, ?)",
                    (kind, external_id, name, json.dumps(record, ensure_ascii=False), now),
                )
                classification = record.get("classification") or ""
                doc = {
                    "source": "cma",
                    "external_id": external_id,
                    "title": f"{name} - {classification}" if classification else name,
                    "body": _record_body(record),
                    "publisher": "هيئة السوق المالية",
                    "url": PORTAL_URL,
                    "doc_type": "registry",
                    "tickers": [],
                    "sectors": [],
                    "published_at": _record_published_at(record),
                }
                row_id = db.insert_document(conn, doc)
                if row_id is not None:
                    inserted.append({**doc, "id": row_id})
    return inserted


def registry_counts() -> dict[str, int]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT kind, COUNT(*) AS n FROM cma_records GROUP BY kind"
        ).fetchall()
    return {row["kind"]: row["n"] for row in rows}
