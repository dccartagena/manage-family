# Household Manager

Private coordination tool for households. Centralizes chores, tasks, reminders, events, shopping, and finances — connects outward to Google/Outlook calendars via iCal feed.

Designed for extended families where one person belongs to several households across generations. Accessibility-first (ASD-friendly). 

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12 + FastAPI (Vercel serverless) |
| Database | Supabase Postgres + RLS + Realtime |
| ORM / migrations | SQLModel + Alembic |
| Auth | Supabase magic links (passwordless) |
| Frontend | SvelteKit or Next.js + Tailwind (PWA) |
| UI components | Melt UI / Bits UI (Svelte) or Radix / shadcn (React) |
| Offline | Workbox + IndexedDB |
| Scheduling | cron-job.org → `GET /jobs/tick` |
| Notifications | Per-user iCal `.ics` feed → native calendar alerts |

## Repo structure

```
household-app/
├── api/                     # FastAPI app — deploys as one Vercel function
│   ├── main.py              # FastAPI app instance (Vercel entrypoint)
│   ├── models.py            # SQLModel models
│   ├── db.py                # Postgres session via Supabase pooler
│   ├── auth.py              # JWT verification (Supabase)
│   ├── routers/             # tasks, shopping, events, groups, jobs, ical
│   └── migrations/          # Alembic
├── web/                     # PWA frontend
│   ├── src/
│   ├── service-worker/      # Workbox config
│   └── manifest.webmanifest
├── vercel.json
└── pyproject.toml
```

## Key constraints

- **Vercel Hobby only** — no Pro. Functions are stateless; no SQLite, no in-process workers.
- **Cron = once/day** on Vercel free. All timed reminders via external scheduler (cron-job.org) hitting `GET /jobs/tick` with a secret header.
- **No iPhone push.** Notifications delivered through the iCal feed; native calendar app handles alerting cross-platform.
- **Non-commercial** — private extended-family use only.

## MVP scope

**v1 includes:** magic-link auth · group hierarchy + invite links · chores/tasks with RRULE recurrence · shared shopping list (realtime sync) · household events + iCal feed · overview dashboard

**Post-MVP:** food inventory · finances · Web Push · two-way OAuth calendar sync

See [MASTERPLAN.md](MASTERPLAN.md) for full architecture, data model, build phases, and definition of done.

## Local development

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in Supabase credentials
uvicorn api.main:app --reload

# Frontend
cd web
npm install
npm run dev
```

## Environment variables

See `.env.example`. Required:

```
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
DATABASE_URL=               # Supabase pooler connection string
JOBS_TICK_SECRET=           # shared secret for /jobs/tick
```
