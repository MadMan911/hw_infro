import secrets
import time
from dataclasses import dataclass, field

from jose import JWTError, jwt

from src.config import settings

ALGORITHM = "HS256"
DEFAULT_EXPIRE_SECONDS = 3600  # 1 hour

# Valid scopes
VALID_SCOPES = {
    "chat:read",
    "agents:read",
    "agents:write",
    "providers:read",
    "providers:write",
    "admin",
}

# In-memory revocation set (token JTI → revoked)
_revoked_tokens: set[str] = set()


@dataclass
class TokenPayload:
    sub: str           # subject (agent_id or user_id)
    scopes: list[str]
    jti: str           # unique token ID (for revocation)
    exp: int           # expiry unix timestamp


class TokenAuth:
    """JWT-based token authentication."""

    def __init__(self, secret_key: str | None = None) -> None:
        self._secret = secret_key or settings.auth_secret_key

    def create_token(
        self,
        subject: str,
        scopes: list[str],
        expire_seconds: int = DEFAULT_EXPIRE_SECONDS,
    ) -> str:
        """Create a signed JWT token."""
        unknown = set(scopes) - VALID_SCOPES
        if unknown:
            raise ValueError(f"Unknown scopes: {unknown}")

        jti = secrets.token_hex(16)
        payload = {
            "sub": subject,
            "scopes": scopes,
            "jti": jti,
            "exp": int(time.time()) + expire_seconds,
            "iat": int(time.time()),
        }
        return jwt.encode(payload, self._secret, algorithm=ALGORITHM)

    def verify_token(self, token: str) -> TokenPayload:
        """Decode and validate a JWT token. Raises ValueError on failure."""
        try:
            data = jwt.decode(token, self._secret, algorithms=[ALGORITHM])
        except JWTError as exc:
            raise ValueError(f"Invalid token: {exc}") from exc

        jti = data.get("jti", "")
        if jti in _revoked_tokens:
            raise ValueError("Token has been revoked")

        return TokenPayload(
            sub=data["sub"],
            scopes=data.get("scopes", []),
            jti=jti,
            exp=data["exp"],
        )

    def revoke_token(self, jti: str) -> None:
        """Add token JTI to revocation list."""
        _revoked_tokens.add(jti)

    def has_scope(self, payload: TokenPayload, required: str) -> bool:
        """Check if token has a required scope (admin grants all)."""
        return "admin" in payload.scopes or required in payload.scopes


# Singleton used by middleware and routes
token_auth = TokenAuth()
