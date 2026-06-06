"""Shared pytest fixtures for API tests."""
import uuid
from collections.abc import Callable, Generator

import pytest
from jose import jwt
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

_TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests"


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
    from api.main import app

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
