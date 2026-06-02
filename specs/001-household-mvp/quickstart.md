# Quickstart: Household Manager MVP

**Branch**: `001-household-mvp` | **Date**: 2026-06-03

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | `pyenv install 3.12` |
| Node.js | 20+ | `nvm install 20` |
| Supabase CLI | latest | `brew install supabase/tap/supabase` |
| Vercel CLI | latest | `npm i -g vercel` |

## 1. Clone & Install

```bash
git clone <repo-url> household-app
cd household-app

# Python deps
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Node deps (from web/ directory)
cd web && npm install && cd ..
```

## 2. Supabase Project Setup

```bash
# Create project at supabase.com (free tier)
# Note: Project URL, anon key, service role key, JWT secret

# Link local CLI
supabase link --project-ref <your-project-ref>

# Run migrations (creates all tables, RLS, indexes)
supabase db push
# OR via Alembic:
cd api && alembic upgrade head
```

## 3. Environment Variables

Create `api/.env` and `web/.env.local`:

```bash
# api/.env
DATABASE_URL=postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres
DATABASE_POOL_URL=postgresql://postgres.[ref]:[password]@aws-0-eu-west-1.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
SUPABASE_JWT_SECRET=<jwt-secret>
SCHEDULER_SECRET=<generate: openssl rand -hex 32>
APP_TIMEZONE=Europe/London

# web/.env.local
NEXT_PUBLIC_SUPABASE_URL=https://[ref].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## 4. Run Locally

```bash
# Terminal 1 — FastAPI
cd api && uvicorn main:app --reload --port 8000

# Terminal 2 — Next.js
cd web && npm run dev
```

App available at `http://localhost:3000`. API at `http://localhost:8000`.

## 5. Configure External Scheduler (cron-job.org)

1. Create a free account at cron-job.org
2. Create a new cron job:
   - URL: `https://<your-vercel-domain>/api/v1/jobs/tick`
   - Schedule: Every 5 minutes (`*/5 * * * *`)
   - Method: GET
   - Custom header: `X-Scheduler-Secret: <SCHEDULER_SECRET value>`
3. Enable the job and note its ID for documentation

## 6. Subscribe Your iCal Feed

After logging in, retrieve your feed URL from the app settings.
Feed URL format: `https://<domain>/api/v1/ical/<your-ical-secret>`

**Google Calendar**: Settings → Other calendars → From URL → Paste URL
**Outlook**: Add calendar → Subscribe from web → Paste URL

The feed will be polled by your calendar app on its own schedule (typically every 15–60 minutes).

## 7. Deploy to Vercel

```bash
# Set env vars in Vercel dashboard (or via CLI)
vercel env add DATABASE_POOL_URL production
vercel env add SUPABASE_URL production
# ... (all env vars from step 3)

# Deploy
vercel --prod
```

`vercel.json` routes `/api/*` to the FastAPI serverless function and `/*` to Next.js.

## 8. Run Tests

```bash
# API tests
cd api && pytest tests/ -v

# Frontend tests
cd web && npm test
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| 403 on `/jobs/tick` | Wrong `SCHEDULER_SECRET` | Verify header matches env var exactly |
| iCal feed returns 404 | URL rotated | Re-subscribe using new URL from app settings |
| Shopping changes not syncing | Realtime channel not subscribed | Check browser console for Supabase Realtime errors |
| Reminder not in feed | `/jobs/tick` not running | Check cron-job.org job status; verify `delivered=false` reminders exist |
| Cold start latency | Python startup time | Expected on Vercel Hobby; keep bundle lean |
