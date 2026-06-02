"""Failing tests for db layer — must fail before api/db.py is implemented."""
import pytest
from sqlmodel import Session, text


def test_get_session_yields_live_session() -> None:
    """get_session dependency yields a live database session via DATABASE_POOL_URL."""
    from api.db import get_session

    gen = get_session()
    session = next(gen)
    assert isinstance(session, Session)
    result = session.exec(text("SELECT 1")).first()
    assert result is not None
    try:
        next(gen)
    except StopIteration:
        pass
