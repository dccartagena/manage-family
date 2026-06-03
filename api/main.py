import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import dashboard, events, groups, ical, invites, jobs, person, reminders, shopping, tasks

app = FastAPI(
    title="Household Manager API",
    version="0.1.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

_vercel_domain = os.environ.get("VERCEL_URL", "")
_allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
]
if _vercel_domain:
    _allowed_origins.append(f"https://{_vercel_domain}")

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
