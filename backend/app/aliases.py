import re

from .text_utils import normalize_ar

# Matching modes per alias:
#   text       - substring anywhere (safe, specific Arabic phrases)
#   word       - word-boundary regex (Latin names and anything digit-adjacent)
#   title_word - word-boundary match in the TITLE only (common-noun Arabic aliases)
# Bare ticker codes are deliberately NOT free-text aliases (the year 2010 must not
# tag SABIC); resolve_query handles exact ticker lookups separately.
#
# `vetoes` are longer phrases that outrank an alias: an alias match falling inside a
# veto span does not count. This is what separates a company from the common noun it
# is named after (معادن the company vs معادن نادرة "rare earths") and from a
# differently-listed sibling (سابك vs سابك للمغذيات, which is 2020). A veto only
# suppresses the occurrence it covers; a second unvetoed mention still tags.

COMPANIES = {
    "2222": {
        "name_ar": "أرامكو السعودية",
        "name_en": "Saudi Aramco",
        "sector_ar": "الطاقة",
        "sector_en": "Energy",
        "aliases": {"ارامكو": "text", "aramco": "word"},
    },
    "1120": {
        "name_ar": "مصرف الراجحي",
        "name_en": "Al Rajhi Bank",
        "sector_ar": "البنوك",
        "sector_en": "Banks",
        # Al Rajhi Takaful is a separate listed company and is written with تكافل
        # FIRST, so a trailing lookahead never fires. Veto the whole phrase instead.
        "aliases": {"الراجحي": "text", "al rajhi": "word", "alrajhi": "word"},
        "vetoes": ["تكافل الراجحي", "الراجحي تكافل", "al rajhi takaful"],
    },
    "7010": {
        "name_ar": "إس تي سي",
        "name_en": "stc",
        "sector_ar": "الاتصالات",
        "sector_en": "Telecom",
        "aliases": {"اس تي سي": "text", "الاتصالات السعودية": "text", "stc": "word"},
    },
    "2010": {
        "name_ar": "سابك",
        "name_en": "SABIC",
        "sector_ar": "المواد الأساسية",
        "sector_en": "Materials",
        # SABIC Agri-Nutrients is 2020, a separate listed company. The veto replaces a
        # lookahead that the name_ar fallback re-added as a plain substring, silently
        # defeating it.
        "aliases": {"سابك": "text", "sabic": "word"},
        "vetoes": ["سابك للمغذيات", "sabic agri"],
    },
    "1180": {
        "name_ar": "البنك الأهلي السعودي",
        "name_en": "Saudi National Bank",
        "sector_ar": "البنوك",
        "sector_en": "Banks",
        # bare "الاهلي" collides with Al-Ahli football club; require the bank context
        "aliases": {"البنك الاهلي": "text", "الاهلي المالية": "text",
                    "saudi national bank": "word", "snb": "word"},
    },
    "2280": {
        "name_ar": "المراعي",
        "name_en": "Almarai",
        "sector_ar": "السلع الاستهلاكية",
        "sector_en": "Consumer Staples",
        # المراعي is also "pastures" and the adjective "considerate"
        # (النهج المراعي = trauma-informed approach). Both occur live.
        "aliases": {"المراعي": "text", "almarai": "word"},
        "vetoes": ["النهج المراعي", "الى المراعي", "المراعي الطبيعية",
                   "المراعي والغابات"],
    },
    "4013": {
        "name_ar": "سليمان الحبيب",
        "name_en": "Dr. Sulaiman Al Habib",
        "sector_ar": "الرعاية الصحية",
        "sector_en": "Healthcare",
        "aliases": {"سليمان الحبيب": "text", "sulaiman al habib": "word",
                    "al habib medical": "word"},
    },
    "1211": {
        "name_ar": "معادن",
        "name_en": "Maaden",
        "sector_ar": "المواد الأساسية",
        "sector_en": "Materials",
        # معادن is the common noun "minerals". Live headlines write the company as a
        # standalone word, usually quoted (سهم "معادن"), while the generic sense is
        # nearly always the definite المعادن, which word boundaries reject for free.
        # title_word keeps the noun out of body prose; vetoes cover the indefinite
        # generic phrases (معادن نادرة, معادن الدم).
        "query_ar": "شركة معادن السعودية",
        "name_ar_matchable": False,
        "aliases": {"معادن": "title_word",
                    "شركة التعدين العربية السعودية": "text",
                    "maaden": "word", "ma'aden": "word"},
        "vetoes": ["معادن نادرة", "معادن النادرة", "معادن الدم", "معادن ثمينة",
                   "معادن حرجة", "معادن حيوية", "معادن صناعية", "معادن اساسية",
                   "معادن خام", "معادن مشعة", "معادن ارضية"],
    },
}

_WORD_CHARS = r"0-9a-zA-Zء-ي"


def _compile(alias: str, mode: str) -> re.Pattern:
    body = alias if mode == "regex" else re.escape(alias)
    if mode in ("word", "title_word"):
        return re.compile(rf"(?<![{_WORD_CHARS}]){body}(?![{_WORD_CHARS}])")
    return re.compile(body)


_MATCHERS: dict[str, dict] = {}
for _ticker, _info in COMPANIES.items():
    _pats = []
    for _alias, _mode in _info["aliases"].items():
        _pats.append((_compile(normalize_ar(_alias).lower(), _mode), _mode))
    if _info.get("name_ar_matchable", True):
        _pats.append((_compile(normalize_ar(_info["name_ar"]).lower(), "text"), "text"))
    _pats.append((_compile(normalize_ar(_info["name_en"]).lower(), "word"), "word"))
    _MATCHERS[_ticker] = {
        "patterns": _pats,
        "vetoes": [_compile(normalize_ar(_v).lower(), "text")
                   for _v in _info.get("vetoes", [])],
    }

_PUNCT = re.compile(r"[؟?!.,؛;:\"'«»()\[\]{}|/\\-]+")
_QUERY_PREFIXES = ("سهم", "شركة", "اخبار", "أخبار", "سعر", "بنك", "مصرف", "مستشفى",
                   "مجموعة", "ما", "ماهي", "ماهو", "كم", "وش", "ايش",
                   "news", "stock", "quote", "price", "about")
_TICKER_RE = re.compile(r"^\d{4}$")
# Tadawul code decorations that punctuation stripping alone would not resolve
_TICKER_DECOR = re.compile(r"^(?:tadawul\s*:\s*)?(\d{4})(?:\s*\.\s*sr)?$")


def _veto_spans(patterns: list[re.Pattern], hay: str) -> list[tuple[int, int]]:
    return [m.span() for p in patterns for m in p.finditer(hay)]


def _vetoed(span: tuple[int, int], vetoes: list[tuple[int, int]]) -> bool:
    return any(vs <= span[0] and span[1] <= ve for vs, ve in vetoes)


def match_tickers(title: str, body: str = "") -> list[str]:
    """Tickers evidenced in a document. Title and body are matched separately so
    title_word aliases stay title-scoped. Alias matches inside a veto span are
    ignored; an unvetoed occurrence anywhere else still counts."""
    t = normalize_ar(title).lower()
    b = normalize_ar(body).lower()
    full = f"{t}\n{b}"
    hits = []
    for ticker, entry in _MATCHERS.items():
        veto_title = _veto_spans(entry["vetoes"], t)
        veto_full = _veto_spans(entry["vetoes"], full)
        for pattern, mode in entry["patterns"]:
            hay, vetoes = (t, veto_title) if mode == "title_word" else (full, veto_full)
            if any(not _vetoed(m.span(), vetoes) for m in pattern.finditer(hay)):
                hits.append(ticker)
                break
    return hits


def display_name(ticker: str, lang: str) -> str:
    info = COMPANIES.get(ticker)
    if not info:
        return ticker
    return info["name_ar"] if lang == "ar" else info["name_en"]


def sectors_for(tickers: list[str]) -> list[str]:
    seen = []
    for t in tickers:
        sector = COMPANIES.get(t, {}).get("sector_ar")
        if sector and sector not in seen:
            seen.append(sector)
    return seen


def _query_form(text: str) -> str:
    """Normalized, punctuation-stripped, whitespace-collapsed. Applied to the query
    AND to every candidate, so "Dr. Sulaiman Al Habib" can match its own name_en."""
    q = _PUNCT.sub(" ", normalize_ar(text).lower())
    return re.sub(r"\s+", " ", q).strip()


def resolve_query_detail(query: str) -> tuple[str | None, str | None]:
    """(ticker, kind) where kind is "exact" for a bare company lookup ("ارامكو",
    "2222") and "prefix" for a query that merely starts with one
    ("aramco helicopter crash"). Both route; only "exact" means the company IS the
    question, which is what decides whether the price card or the answer leads."""
    raw = re.sub(r"\s+", " ", normalize_ar(query).lower()).strip()
    decorated = _TICKER_DECOR.match(raw)
    if decorated:
        code = decorated.group(1)
        return (code, "exact") if code in COMPANIES else (None, None)
    q = _query_form(query)
    words = q.split(" ")
    while words and words[0] in _QUERY_PREFIXES:
        words = words[1:]
    q = " ".join(words)
    if not q or len(q) > 40:
        return (None, None)
    if _TICKER_RE.match(q):
        return (q, "exact") if q in COMPANIES else (None, None)
    for ticker, info in COMPANIES.items():
        candidates = {_query_form(info["name_ar"]), _query_form(info["name_en"])}
        for alias, mode in info["aliases"].items():
            if mode != "regex":
                candidates.add(_query_form(alias))
        if q in candidates:
            return ticker, "exact"
        # "ارامكو السعودية اليوم" still routes, but as a prefix match
        if any(q.startswith(c + " ") for c in candidates if len(c) >= 4):
            return ticker, "prefix"
    return (None, None)


def resolve_query(query: str) -> str | None:
    """Ticker for entity routing when the query IS a company, else None."""
    return resolve_query_detail(query)[0]
