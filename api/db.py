import os
from collections.abc import Generator

from sqlmodel import Session, create_engine

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get("POSTGRES_URL")
        if not url:
            raise RuntimeError("POSTGRES_URL env var is not set")
        _engine = create_engine(
            url,
            pool_pre_ping=True,
        )
    return _engine


def get_session() -> Generator[Session, None, None]:
    with Session(_get_engine()) as session:
        yield session
