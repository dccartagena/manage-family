"""Failing tests for auth layer — must fail before api/auth.py is implemented."""

import pytest
from api.main import app
from fastapi import HTTPException
from fastapi.testclient import TestClient

client = TestClient(app)


def test_get_current_person_missing_token() -> None:
    """No Authorization header raises HTTP 401."""
    from api.auth import get_current_person

    with pytest.raises(HTTPException) as exc_info:
        import asyncio

        asyncio.run(get_current_person(authorization=None))
    assert exc_info.value.status_code == 401


def test_get_current_person_invalid_token() -> None:
    """Garbage token raises HTTP 401."""
    from api.auth import get_current_person

    with pytest.raises(HTTPException) as exc_info:
        import asyncio

        asyncio.run(get_current_person(authorization="Bearer not.a.jwt"))
    assert exc_info.value.status_code == 401


def test_get_current_person_expired_token() -> None:
    """Expired JWT raises HTTP 401."""
    from api.auth import get_current_person

    expired_token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE1MTYyMzkwMjJ9."
        "4Adcj3UFYzPUVaVF43FmMab6RlaQD8A9V8wFzzht-KQ"
    )
    with pytest.raises(HTTPException) as exc_info:
        import asyncio

        asyncio.run(get_current_person(authorization=f"Bearer {expired_token}"))
    assert exc_info.value.status_code == 401


def test_health_endpoint_no_auth() -> None:
    """Health endpoint accessible without auth."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
