import os

from dotenv import load_dotenv

load_dotenv()

from api.db import DB_URL_ENV_VARS, check_connection  # noqa: E402
from api.routers import (  # noqa: E402
    dashboard,
    events,
    groups,
    ical,
    inventory,
    invites,
    jobs,
    person,
    reminders,
    shopping,
    tasks,
)
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app = FastAPI(
    title="Household Manager API",
    version="0.1.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

_allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
]
# VERCEL_URL is the per-deployment domain; VERCEL_PROJECT_PRODUCTION_URL is the
# stable production domain. NEXT_PUBLIC_APP_URL covers custom domains.
for _env_var in ("NEXT_PUBLIC_APP_URL", "VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_URL"):
    _value = os.environ.get(_env_var, "")
    if _value:
        _allowed_origins.append(_value if _value.startswith("http") else f"https://{_value}")
_allowed_origins = list(dict.fromkeys(_allowed_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
def deployment_health() -> dict:
    """Deployment diagnostics: reports env var presence and DB connectivity.

    Never returns secret values — only booleans and exception class names —
    so it is safe to leave enabled in production.
    """
    env = {
        "database_url": any(os.environ.get(name) for name in DB_URL_ENV_VARS),
        "supabase_url": bool(os.environ.get("SUPABASE_URL")),
        "supabase_jwt_secret": bool(os.environ.get("SUPABASE_JWT_SECRET")),
    }
    try:
        check_connection()
        database = "ok"
    except Exception as exc:  # noqa: BLE001 — diagnostics must not crash
        database = f"error: {type(exc).__name__}"

    status = "ok" if database == "ok" and env["supabase_url"] else "degraded"
    return {"status": status, "env": env, "database": database}


app.include_router(person.router, prefix="/api/v1")
app.include_router(groups.router, prefix="/api/v1")
app.include_router(invites.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(shopping.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(ical.router, prefix="/api/v1")
app.include_router(reminders.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
