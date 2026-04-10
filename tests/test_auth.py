"""Tests for JWT-based token authentication."""
import time

import pytest
from jose import jwt

from src.auth.token_auth import TokenAuth, VALID_SCOPES, ALGORITHM


@pytest.fixture
def auth():
    return TokenAuth(secret_key="test-secret-key-for-tests")


class TestTokenCreation:
    def test_create_token_returns_string(self, auth):
        token = auth.create_token("user1", ["chat:read"])
        assert isinstance(token, str)
        assert len(token) > 20

    def test_create_token_with_multiple_scopes(self, auth):
        token = auth.create_token("agent1", ["chat:read", "agents:read"])
        payload = auth.verify_token(token)
        assert "chat:read" in payload.scopes
        assert "agents:read" in payload.scopes

    def test_create_token_with_admin_scope(self, auth):
        token = auth.create_token("admin", ["admin"])
        payload = auth.verify_token(token)
        assert "admin" in payload.scopes

    def test_create_token_invalid_scope_raises(self, auth):
        with pytest.raises(ValueError, match="Unknown scopes"):
            auth.create_token("user", ["invalid:scope"])

    def test_create_token_has_correct_subject(self, auth):
        token = auth.create_token("my_user", ["chat:read"])
        payload = auth.verify_token(token)
        assert payload.sub == "my_user"

    def test_create_token_has_jti(self, auth):
        token = auth.create_token("u", ["chat:read"])
        payload = auth.verify_token(token)
        assert payload.jti
        assert len(payload.jti) > 0

    def test_create_token_has_expiry(self, auth):
        token = auth.create_token("u", ["chat:read"], expire_seconds=60)
        payload = auth.verify_token(token)
        assert payload.exp > int(time.time())

    def test_custom_expiry(self, auth):
        token = auth.create_token("u", ["chat:read"], expire_seconds=3600)
        raw = jwt.decode(token, "test-secret-key-for-tests", algorithms=[ALGORITHM])
        assert raw["exp"] - raw["iat"] == 3600


class TestTokenVerification:
    def test_verify_valid_token(self, auth):
        token = auth.create_token("user", ["chat:read"])
        payload = auth.verify_token(token)
        assert payload.sub == "user"

    def test_verify_invalid_token_raises(self, auth):
        with pytest.raises(ValueError):
            auth.verify_token("not.a.valid.jwt.token")

    def test_verify_tampered_token_raises(self, auth):
        token = auth.create_token("user", ["chat:read"])
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(ValueError):
            auth.verify_token(tampered)

    def test_verify_expired_token_raises(self, auth):
        token = auth.create_token("user", ["chat:read"], expire_seconds=-1)
        with pytest.raises(ValueError):
            auth.verify_token(token)

    def test_verify_wrong_secret_raises(self, auth):
        other_auth = TokenAuth(secret_key="different-secret")
        token = other_auth.create_token("user", ["chat:read"])
        with pytest.raises(ValueError):
            auth.verify_token(token)


class TestTokenRevocation:
    def test_revoke_token(self, auth):
        token = auth.create_token("user", ["chat:read"])
        payload = auth.verify_token(token)
        auth.revoke_token(payload.jti)
        with pytest.raises(ValueError, match="revoked"):
            auth.verify_token(token)

    def test_revoke_nonexistent_jti_no_error(self, auth):
        # Should not raise even if JTI was never issued
        auth.revoke_token("nonexistent-jti-12345")


class TestScopeChecking:
    def test_has_required_scope(self, auth):
        token = auth.create_token("user", ["chat:read", "agents:read"])
        payload = auth.verify_token(token)
        assert auth.has_scope(payload, "chat:read")
        assert auth.has_scope(payload, "agents:read")

    def test_missing_scope(self, auth):
        token = auth.create_token("user", ["chat:read"])
        payload = auth.verify_token(token)
        assert not auth.has_scope(payload, "agents:write")

    def test_admin_grants_all_scopes(self, auth):
        token = auth.create_token("admin", ["admin"])
        payload = auth.verify_token(token)
        for scope in VALID_SCOPES:
            assert auth.has_scope(payload, scope)


class TestValidScopes:
    def test_all_expected_scopes_defined(self):
        expected = {
            "chat:read",
            "agents:read",
            "agents:write",
            "providers:read",
            "providers:write",
            "admin",
        }
        assert expected == VALID_SCOPES
