"""Shared pytest fixtures for API tests."""
import os
import uuid
from collections.abc import Callable

import pytest
from jose import jwt

_TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests"


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required env vars for all tests."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _TEST_JWT_SECRET)


@pytest.fixture()
def make_auth_token() -> Callable[[str], str]:
    """Return a factory that creates valid HS256 JWT tokens for tests."""

    def _make(email: str, person_id: uuid.UUID | None = None) -> str:
        sub = str(person_id or uuid.uuid4())
        return jwt.encode(
            {"sub": sub, "email": email},
            _TEST_JWT_SECRET,
            algorithm="HS256",
        )

    return _make
