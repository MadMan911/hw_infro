import base64
import logging
import re

logger = logging.getLogger(__name__)

# Patterns that indicate prompt injection attempts
_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"ignore\s+(previous|all|prior)\s+instructions?", re.I), 1.0),
    (re.compile(r"disregard\s+(previous|all|prior)\s+instructions?", re.I), 1.0),
    (re.compile(r"forget\s+(everything|all|prior|previous)", re.I), 0.8),
    (re.compile(r"you\s+are\s+now\b", re.I), 1.0),
    (re.compile(r"act\s+as\s+(if\s+you\s+are|a|an)\b", re.I), 1.0),
    (re.compile(r"pretend\s+(you\s+are|to\s+be)\b", re.I), 1.0),
    (re.compile(r"(reveal|show|print|display)\s+(your\s+)?(system\s+)?prompt", re.I), 0.9),
    (re.compile(r"your\s+(true|real|actual)\s+(instructions?|purpose|goal)", re.I), 0.8),
    (re.compile(r"(new|updated)\s+instructions?\s*:", re.I), 0.7),
    (re.compile(r"\[SYSTEM\]|\[INST\]|\[\/INST\]", re.I), 0.8),
    (re.compile(r"jailbreak", re.I), 0.9),
    (re.compile(r"DAN\b|do\s+anything\s+now", re.I), 0.9),
]

BLOCK_THRESHOLD = 0.8  # score >= threshold → blocked


def _check_base64_encoded(text: str) -> float:
    """Detect Base64/hex encoded injection attempts."""
    # Find potential base64 blobs (≥20 chars of base64 alphabet)
    b64_pattern = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")
    for match in b64_pattern.finditer(text):
        try:
            decoded = base64.b64decode(match.group()).decode("utf-8", errors="ignore")
            # Recursively score the decoded text
            score = score_text(decoded)
            if score >= BLOCK_THRESHOLD:
                return score
        except Exception:
            logger.debug("Base64 decode check failed (non-fatal)", exc_info=True)
    return 0.0


def score_text(text: str) -> float:
    """Return injection score [0.0, 1.0]. Values >= BLOCK_THRESHOLD indicate injection."""
    total = 0.0
    for pattern, weight in _PATTERNS:
        if pattern.search(text):
            total += weight
            if total >= 1.0:
                return 1.0
    return min(total, 1.0)


def is_injection(text: str) -> bool:
    """Return True if the text contains a prompt injection attempt."""
    if score_text(text) >= BLOCK_THRESHOLD:
        return True
    if _check_base64_encoded(text) >= BLOCK_THRESHOLD:
        return True
    return False
