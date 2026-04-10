import re

_PATTERNS: list[re.Pattern] = [
    # OpenAI API key
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    # Anthropic API key
    re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b"),
    # AWS Access Key
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # JWT token (three base64url segments separated by dots)
    re.compile(r"\beyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\b"),
    # Bearer token in text
    re.compile(r"\bBearer\s+[A-Za-z0-9\-_.~+/]{20,}\b", re.I),
    # Passwords in plain text
    re.compile(r"\b(?:password|passwd|pwd)\s*[=:]\s*\S+", re.I),
    # Generic secret/token assignments
    re.compile(r"\b(?:secret|token|api[_\-]?key)\s*[=:]\s*['\"]?[A-Za-z0-9\-_]{8,}['\"]?", re.I),
    # Private key header
    re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"),
]


def contains_secret(text: str) -> bool:
    """Return True if the text appears to contain an API key, token, or secret."""
    return any(p.search(text) for p in _PATTERNS)
