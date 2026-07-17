import hashlib
import re

_DIACRITICS = re.compile(r"[ً-ْٰ]")
_TATWEEL = "ـ"
_CHAR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي"})
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_WS = re.compile(r"\s+")


def normalize_ar(text: str) -> str:
    """Normalization applied identically to indexed passages and search queries."""
    text = text.replace(_TATWEEL, "")
    text = _DIACRITICS.sub("", text)
    text = text.translate(_CHAR_MAP)
    text = text.translate(_AR_DIGITS)
    return _WS.sub(" ", text).strip()


def title_hash(title: str) -> str:
    return hashlib.sha1(normalize_ar(title).lower().encode("utf-8")).hexdigest()
