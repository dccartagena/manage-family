# Household Manager

Private household coordination PWA. Shared chores with recurrence, real-time shopping list, household events with iCal feed, and an urgency-ranked dashboard.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Browser / PWA (Next.js 14, port 3000)      │
│  Auth & Realtime ──► Supabase (cloud)        │
│  Data ─────────────► FastAPI (port 8000)     │
└─────────────────────────────────────────────┘
         │
┌────────▼────────────────────────────────────┐
│  FastAPI (Python 3.12, port 8000)           │
│  JWT verification via Supabase JWKS         │
│  Data ──► Postgres                          │
└─────────────────────────────────────────────┘
```

**Production**: both services deploy to Vercel Hobby (serverless). Postgres lives in Supabase free tier. Magic-link auth and Realtime subscriptions are Supabase infrastructure.

**Local**: Postgres runs in Docker. Auth still requires a Supabase project (magic-link email delivery cannot be replicated locally).

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2
- A free [Supabase](https://supabase.com) project (for Auth + Realtime)

## Local Setup

### 1. Create env files

```bash
cp api/.env.example api/.env
cp web/.env.local.example web/.env.local
```

Edit `api/.env` — fill in your Supabase values. The two DB vars are overridden by docker-compose to point at the local Postgres container, so you can leave them as-is for local use:

| Variable | Where to find it |
|---|---|
| `SUPABASE_URL` | Supabase dashboard → Project Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase dashboard → Project Settings → API |
| `SUPABASE_JWT_SECRET` | Supabase dashboard → Project Settings → API → JWT Secret |
| `SCHEDULER_SECRET` | Any random string (e.g. `openssl rand -hex 32`) |

Edit `web/.env.local`:

| Variable | Where to find it |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Same as `SUPABASE_URL` above |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase dashboard → Project Settings → API → anon/public key |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` |

### 2. Start services

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Web | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Postgres | localhost:5432 |

### 3. Run database migrations

```bash
docker compose exec api alembic upgrade head
```

## Development (without Docker)

### API

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp api/.env.example api/.env   # fill in values
source api/.env
uvicorn api.main:app --reload
```

### Web

```bash
cd web
npm install
cp .env.local.example .env.local   # fill in values
npm run dev
```

## Tests

### API

```bash
# requires a running Postgres — start only the db service:
docker compose up db -d
source api/.env
pytest
```

### Web

```bash
cd web
npm test
```

## Database Migrations

Alembic manages schema. Migrations live in `api/migrations/versions/`.

```bash
# create a new migration
alembic revision --autogenerate -m "describe change"

# apply
alembic upgrade head

# rollback one step
alembic downgrade -1
```

`DATABASE_URL` (direct connection) is used by Alembic. `DATABASE_POOL_URL` (pooler) is used by the runtime API.

## Project Structure

```
api/                  FastAPI app
├── main.py           App factory, CORS, router registration
├── auth.py           JWT verification (Supabase)
├── db.py             SQLAlchemy engine + session dependency
├── models.py         SQLModel table definitions
├── routers/          One file per resource
└── migrations/       Alembic migration scripts

web/                  Next.js 14 PWA
├── src/app/          App Router pages
├── src/components/   Shared UI (shadcn/ui + Radix)
└── src/lib/          Supabase client, Realtime, offline sync

specs/001-household-mvp/   Feature spec, data model, API contracts
vercel.json                Vercel routing: /api/* → FastAPI, /* → Next.js
pyproject.toml             Python deps + ruff/black/pytest config
```

## Deployment (Vercel)

1. Push to GitHub.
2. Import repo in Vercel. Both `api/` and `web/` are built from the same project via `vercel.json`.
3. Set all env vars from `api/.env.example` and `web/.env.local.example` in Vercel project settings.
4. Run migrations against the Supabase DB once: `DATABASE_URL=<supabase-direct-url> alembic upgrade head`.
