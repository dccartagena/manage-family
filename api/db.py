import os
from collections.abc import Generator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.pool import NullPool
from sqlmodel import Session, create_engine

_engine = None

# Checked in order. POSTGRES_URL is set by the Supabase-Vercel integration;
# the others cover manual setups. Always use Supabase's *transaction pooler*
# URI (port 6543) — Vercel has no IPv6 egress, so the direct connection
# (db.<ref>.supabase.co:5432, IPv6-only on the free tier) is unreachable.
DB_URL_ENV_VARS = ("POSTGRES_URL", "POSTGRES_PRISMA_URL", "DATABASE_POOL_URL", "DATABASE_URL")

_PSYCOPG2_INVALID_PARAMS = frozenset(
    {
        "supa",
        "pgbouncer",
        "workaround",
        "connection_limit",
        "pool_timeout",
        "prepared_statements",
    }
)


def _clean_db_url(url: str) -> str:
    url = url.replace("postgres://", "postgresql://", 1)
    parsed = urlparse(url)
    params = {k: v for k, v in parse_qs(parsed.query).items() if k not in _PSYCOPG2_INVALID_PARAMS}
    cleaned_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=cleaned_query))


def _database_url() -> str:
    for name in DB_URL_ENV_VARS:
        url = os.environ.get(name)
        if url:
            return url
    raise RuntimeError(
        "No database URL configured — set POSTGRES_URL to the Supabase transaction pooler URI"
    )


def _get_engine():
    global _engine
    if _engine is None:
        # NullPool: serverless functions must not hold connections across
        # invocations — Supabase's pgbouncer (transaction mode) does the pooling.
        _engine = create_engine(
            _clean_db_url(_database_url()),
            poolclass=NullPool,
        )
    return _engine


def check_connection() -> None:
    """Open a connection and run SELECT 1. Raises on any connectivity failure."""
    with _get_engine().connect() as conn:
        conn.exec_driver_sql("SELECT 1")


def get_session() -> Generator[Session, None, None]:
    with Session(_get_engine()) as session:
        yield session
