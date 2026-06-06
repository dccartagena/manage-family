"""Tests for db layer — requires DATABASE_POOL_URL for the live-connection test."""

import contextlib
import os

import pytest
from sqlmodel import Session, text


@pytest.mark.skipif(
    not os.environ.get("DATABASE_POOL_URL"),
    reason="DATABASE_POOL_URL not set — skipping live DB connection test",
)
def test_get_session_yields_live_session() -> None:
    """get_session dependency yields a live database session via DATABASE_POOL_URL."""
    from api.db import get_session

    gen = get_session()
    session = next(gen)
    assert isinstance(session, Session)
    result = session.exec(text("SELECT 1")).first()
    assert result is not None
    with contextlib.suppress(StopIteration):
        next(gen)
