from .argaam_news import BASE, ingest

LISTING_URL = f"{BASE}/ar/company/disclosure/sectionid/245/marketid/3/pageno"


def ingest_disclosures() -> list[dict]:
    return ingest(listing_url=LISTING_URL, source="argaam_disclosures", doc_type="disclosure")
