import re
from enum import Enum


class PiiMode(str, Enum):
    BLOCK = "block"   # reject request containing PII
    MASK = "mask"     # replace PII with [MASKED]


# ─── Regex patterns ───

_PHONE_RU = re.compile(
    r"(?<!\d)"
    r"(\+7|8)[\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
    r"(?!\d)"
)
_PHONE_INTL = re.compile(
    r"(?<!\d)\+(?!7)\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{1,4}[\s\-]?\d{1,9}(?!\d)"
)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_CARD = re.compile(r"\b(?:\d[ \-]?){13,16}\b")
_PASSPORT_RU = re.compile(r"\b\d{4}\s?\d{6}\b")  # серия + номер
_INN = re.compile(r"\b(?:ИНН|inn)[:\s]*\d{10,12}\b", re.I)
_SNILS = re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b")

_PATTERNS: list[tuple[re.Pattern, str]] = [
    (_PHONE_RU, "PHONE"),
    (_PHONE_INTL, "PHONE"),
    (_EMAIL, "EMAIL"),
    (_CARD, "CARD"),
    (_PASSPORT_RU, "PASSPORT"),
    (_INN, "INN"),
    (_SNILS, "SNILS"),
]


def _luhn_check(number: str) -> bool:
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10 == 0


def contains_pii(text: str) -> bool:
    """Return True if the text contains any detectable PII."""
    for pattern, kind in _PATTERNS:
        match = pattern.search(text)
        if match:
            if kind == "CARD" and not _luhn_check(match.group()):
                continue  # false positive — skip
            return True
    return False


def mask_pii(text: str) -> str:
    """Replace all detected PII with [MASKED]."""
    result = text
    for pattern, kind in _PATTERNS:
        def _replace(m: re.Match) -> str:
            raw = m.group()
            if kind == "CARD" and not _luhn_check(raw):
                return raw  # not a real card number
            return f"[{kind}_MASKED]"
        result = pattern.sub(_replace, result)
    return result
