# Household Manager

Private household coordination PWA. Shared chores with recurrence, real-time shopping list, household events with iCal feed, food inventory with barcode scanning, and an urgency-ranked dashboard.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Browser / PWA (Next.js 14)                  │
│  Auth & Realtime ──► Supabase (cloud)        │
│  Data ─────────────► FastAPI via /api/*      │
└─────────────────────────────────────────────┘
         │
┌────────▼────────────────────────────────────┐
│  FastAPI (Python 3.12, serverless)          │
│  JWT verification via Supabase JWKS         │
│  Data ──► Supabase Postgres (pooler)        │
└─────────────────────────────────────────────┘
```

One Vercel project serves both apps: `vercel.json` routes `/api/*` to the FastAPI
serverless function (`api/main.py`) and everything else to the Next.js app (`web/`).
Postgres, Auth, and Realtime live in a free-tier Supabase project.

## Deploy (Vercel free tier + Supabase free tier)

### 1. Create the Supabase project

1. Create a free project at [supabase.com](https://supabase.com).
2. Apply the database schema: dashboard → **SQL Editor** → paste the contents of
   [`supabase/migrations/20260612000000_initial_schema.sql`](supabase/migrations/20260612000000_initial_schema.sql)
   → **Run**. (Or, with the Supabase CLI: `supabase link && supabase db push`.)
3. Email/password auth is enabled by default — nothing else to configure yet.

### 2. Deploy to Vercel

1. Push this repo to GitHub and **Import** it in Vercel. Leave the *Root Directory*
   as the repository root — `vercel.json` builds both `api/` and `web/`.
2. Add these environment variables (Project Settings → Environment Variables):

| Variable | Value |
|---|---|
| `POSTGRES_URL` | Supabase dashboard → **Connect** → **Transaction pooler** URI (port **6543**). The direct connection (port 5432) is IPv6-only and unreachable from Vercel. |
| `SUPABASE_URL` | Dashboard → Project Settings → Data API → Project URL |
| `SUPABASE_JWT_SECRET` | Dashboard → Project Settings → JWT Keys → *Legacy JWT secret*. Only needed for older projects that sign tokens with HS256; new projects are verified via JWKS automatically. |
| `NEXT_PUBLIC_SUPABASE_URL` | Same as `SUPABASE_URL` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Dashboard → Project Settings → API Keys → anon/public |

   Leave `NEXT_PUBLIC_API_URL` **unset** — frontend and API share one domain.
   (The [Supabase-Vercel integration](https://vercel.com/integrations/supabase) can
   set `POSTGRES_URL` and the `NEXT_PUBLIC_*` vars for you.)
3. Deploy.

### 3. Point Supabase back at your app

In the Supabase dashboard → **Authentication → URL Configuration**:

- **Site URL**: `https://<your-app>.vercel.app`
- **Redirect URLs**: add `https://<your-app>.vercel.app/callback`

This makes email-confirmation links land back in your app (including invite
sign-ups, which return to the `/join/<token>` page after confirmation).

### 4. Verify

Open `https://<your-app>.vercel.app/api/health`. Healthy output:

```json
{ "status": "ok", "env": { "database_url": true, "supabase_url": true, ... }, "database": "ok" }
```

Then sign up, create a household under **Groups**, and you're done.

### Troubleshooting "Failed to load … : 500"

Every tab failing with a 500 means the API function itself is failing. Check in order:

1. **`/api/health`** — `env.database_url: false` means `POSTGRES_URL` is missing;
   `database: error: OperationalError` usually means you used the direct
   connection string instead of the **transaction pooler** (port 6543).
2. **Schema not applied** — re-run the SQL file from step 1.2 (it's idempotent).
3. **Vercel function logs** — Vercel dashboard → Deployment → Functions → `api/main.py`.
   An `ImportError`/`ModuleNotFoundError` at startup means `api/requirements.txt`
   was not installed (it must exist — Vercel's Python builder does not read
   `pyproject.toml`).

## Inviting people to a household

1. Open **Groups** → select your household (you must be its **owner**).
2. Tap **Generate Invite Link** and share the copied `…/join/<token>` URL.
3. The invitee opens the link; if they don't have an account they are sent to
   sign-up and bounced back to the invite afterwards, then tap **Accept invite**.

## Local development

Requires Python 3.12+, Node 20+, and a Supabase project (cloud free tier works,
or `supabase start` for a fully local stack).

```bash
# API
cd api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # fill in values (schema comes from the SQL file, step 1.2)
cd .. && uvicorn api.main:app --reload --port 8000

# Web (second terminal)
cd web
npm install
cp .env.local.example .env.local   # fill in values; NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

## Tests

```bash
# API — uses in-memory SQLite, no Postgres needed
cd api && pytest

# Web
cd web && npm test
```

## Database migrations

The schema lives in `supabase/migrations/*.sql` — plain SQL, applied via the
Supabase SQL Editor or `supabase db push`. To change the schema, add a new
timestamped `.sql` file (existing files are idempotent and safe to re-run).

## Project structure

```
api/                  FastAPI app (one Vercel serverless function)
├── main.py           App factory, CORS, /api/health diagnostics, routers
├── auth.py           JWT verification (Supabase HS256 secret or JWKS)
├── db.py             Engine (NullPool for serverless) + session dependency
├── models.py         SQLModel table definitions
├── requirements.txt  Runtime deps for Vercel (mirror of pyproject.toml)
└── routers/          One file per resource

web/                  Next.js 14 PWA
├── src/app/          App Router pages
├── src/components/   Shared UI
└── src/lib/          Supabase client, Realtime, offline sync

supabase/migrations/  Consolidated SQL schema (paste-and-run setup)
vercel.json           Routing: /api/* → FastAPI, /* → Next.js
```
