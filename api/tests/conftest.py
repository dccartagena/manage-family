"""Shared pytest fixtures for API tests."""

import uuid
from collections.abc import Callable, Generator

import pytest
from api.main import app
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

_TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests"

client = TestClient(app)


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required env vars for all tests."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _TEST_JWT_SECRET)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """Provide a fresh SQLite in-memory session per test."""
    import api.models  # ensure all SQLModel metadata is registered  # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def override_db(db_session: Session) -> Generator[None, None, None]:
    """Override FastAPI get_session dependency with test SQLite session."""
    from api.db import get_session

    def get_test_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = get_test_session
    yield
    app.dependency_overrides.clear()


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


@pytest.fixture()
def make_user(make_auth_token) -> Callable[[str], dict[str, str]]:
    """Return a factory: email → auth headers for a freshly synced person."""

    def _make(email: str) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {make_auth_token(email=email)}"}
        resp = client.post("/api/v1/person/sync", headers=headers)
        assert resp.status_code == 200
        return headers

    return _make


@pytest.fixture()
def make_group() -> Callable[..., str]:
    """Return a factory: (headers, name, parent_group_id=None) → group id."""

    def _make(headers: dict[str, str], name: str, parent_group_id: str | None = None) -> str:
        resp = client.post(
            "/api/v1/groups",
            headers=headers,
            json={"name": name, "parent_group_id": parent_group_id},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    return _make
