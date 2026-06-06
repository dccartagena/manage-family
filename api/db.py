import os
from collections.abc import Generator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlmodel import Session, create_engine

_engine = None

_PSYCOPG2_INVALID_PARAMS = frozenset({
    "supa",
    "pgbouncer",
    "workaround",
    "connection_limit",
    "pool_timeout",
    "prepared_statements",
})


def _clean_db_url(url: str) -> str:
    url = url.replace("postgres://", "postgresql://", 1)
    parsed = urlparse(url)
    params = {k: v for k, v in parse_qs(parsed.query).items() if k not in _PSYCOPG2_INVALID_PARAMS}
    cleaned_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=cleaned_query))


def _get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get("POSTGRES_URL")
        if not url:
            raise RuntimeError("POSTGRES_URL env var is not set")
        _engine = create_engine(
            _clean_db_url(url),
            pool_pre_ping=True,
        )
    return _engine


def get_session() -> Generator[Session, None, None]:
    with Session(_get_engine()) as session:
        yield session
