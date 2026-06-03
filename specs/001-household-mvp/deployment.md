# Deployment Guide: GitHub + Vercel + Supabase

**Branch**: `001-household-mvp` | Stack: FastAPI (Python 3.12) + Next.js 14 + Supabase Postgres

---

## 1. Supabase Setup

### 1.1 Create Project

1. Go to [supabase.com](https://supabase.com) → New project
2. Name: `manage-family` | Region: pick closest to users | Plan: Free
3. Save the generated **database password** — not shown again
4. Wait for provisioning (~2 min)

### 1.2 Collect Credentials

From **Project Settings → API**:

| Key | Where Used |
|-----|-----------|
| Project URL (`https://[ref].supabase.co`) | `SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL` |
| `anon` public key | `NEXT_PUBLIC_SUPABASE_ANON_KEY` |
| `service_role` secret key | `SUPABASE_SERVICE_ROLE_KEY` (API only, never frontend) |
| JWT Secret | `SUPABASE_JWT_SECRET` |

From **Project Settings → Database → Connection string**:
- **Direct** (migrations only): `postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres`
- **Pooler (Transaction mode)** (runtime): `postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`

### 1.3 Auth — Passwordless (Magic Link)

1. **Authentication → Providers → Email** → Enable "Magic Link", disable "Email + Password"
2. **Authentication → URL Configuration**:
   - Site URL: `https://your-vercel-domain.vercel.app`
   - Redirect URLs: add `https://your-vercel-domain.vercel.app/**`
3. **Authentication → Email Templates** → customize magic link email if desired

### 1.4 Run Migrations

```bash
# Link local CLI to project
supabase link --project-ref <ref>

# Push migrations (creates tables, RLS policies, indexes)
supabase db push
```

Or via Alembic (same result):
```bash
DATABASE_URL=<direct-url> alembic upgrade head
```

### 1.5 Row-Level Security

Verify RLS is enabled on all tables after migration:

```sql
-- Run in Supabase SQL Editor
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public';
```

All tables must show `rowsecurity = true`. If any show `false`, check migration files.

### 1.6 Realtime

Enable realtime for the shopping list table:

1. **Database → Replication** → toggle on `shopping_items` table
2. No other tables need realtime for this app

---

## 2. GitHub Setup

### 2.1 Create Repository

```bash
gh repo create manage-family --private
git remote add origin git@github.com:<username>/manage-family.git
git push -u origin master
```

### 2.2 Branch Protection (master)

**Settings → Branches → Add branch protection rule** for `master`:

- [x] Require pull request reviews before merging (1 reviewer)
- [x] Require status checks to pass before merging
  - Add: `test-api`, `test-web` (after CI is set up)
- [x] Require branches to be up to date before merging
- [x] Do not allow bypassing the above settings

### 2.3 Repository Secrets (for CI)

**Settings → Secrets and variables → Actions → New repository secret**:

| Secret Name | Value |
|-------------|-------|
| `DATABASE_URL` | Direct Supabase connection string |
| `SUPABASE_URL` | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key |
| `SUPABASE_JWT_SECRET` | JWT secret |
| `SCHEDULER_SECRET` | `openssl rand -hex 32` output |

> **Never commit `.env` files.** Add `api/.env`, `web/.env.local`, `.env` to `.gitignore`.

### 2.4 CI Workflow (GitHub Actions)

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [master, "001-*"]
  pull_request:
    branches: [master]

jobs:
  test-api:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: cd api && pytest tests/ -v
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          SUPABASE_JWT_SECRET: ${{ secrets.SUPABASE_JWT_SECRET }}

  test-web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: cd web && npm ci && npm test
```

---

## 3. Vercel Setup

### 3.1 Install CLI and Login

```bash
npm i -g vercel
vercel login
```

### 3.2 Import Project

Option A — CLI:
```bash
vercel link   # links current directory to a Vercel project (creates if new)
```

Option B — Dashboard:
1. [vercel.com/new](https://vercel.com/new) → Import Git Repository → select `manage-family`
2. Framework Preset: **Other** (not Next.js — the root is a monorepo)

### 3.3 Build Configuration

Vercel reads `vercel.json` at repo root. Current config routes `/api/*` to FastAPI and `/*` to Next.js. No changes needed unless you rename directories.

Verify `vercel.json` is committed:
```json
{
  "version": 2,
  "builds": [
    { "src": "api/main.py", "use": "@vercel/python" },
    { "src": "web/package.json", "use": "@vercel/next" }
  ],
  "routes": [
    { "src": "/api/(.*)", "dest": "api/main.py" },
    { "src": "/(.*)", "dest": "web/$1" }
  ]
}
```

### 3.4 Environment Variables

Set all env vars via CLI **before** first deploy:

```bash
# API vars
vercel env add DATABASE_POOL_URL production
vercel env add SUPABASE_URL production
vercel env add SUPABASE_SERVICE_ROLE_KEY production
vercel env add SUPABASE_JWT_SECRET production
vercel env add SCHEDULER_SECRET production
vercel env add APP_TIMEZONE production   # e.g. America/Bogota

# Frontend vars (NEXT_PUBLIC_ prefix = exposed to browser)
vercel env add NEXT_PUBLIC_SUPABASE_URL production
vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY production
vercel env add NEXT_PUBLIC_API_URL production  # https://your-domain.vercel.app/api/v1
```

Or set them in **Vercel Dashboard → Project → Settings → Environment Variables**.

> Set `DATABASE_POOL_URL` (pooler), NOT `DATABASE_URL` (direct). Serverless functions must use the pooler.

### 3.5 Deploy

```bash
vercel --prod
```

Vercel assigns a domain like `manage-family-xyz.vercel.app`. Note it for:
- Supabase Auth redirect URL (step 1.3)
- `NEXT_PUBLIC_API_URL` value
- cron-job.org scheduler URL (step 4)

### 3.6 Custom Domain (optional)

**Vercel Dashboard → Project → Settings → Domains → Add** your domain.
Update Supabase Auth → URL Configuration with the custom domain.

### 3.7 Vercel GitHub Integration

If imported via dashboard, Vercel auto-deploys on every push to `master` (production) and creates preview deployments for PRs. No extra config needed.

To disable preview deployments for draft PRs:
**Project Settings → Git → Deploy Hooks** — configure as needed.

---

## 4. External Scheduler (cron-job.org)

Vercel Hobby allows cron only once/day. Use cron-job.org for the 5-minute reminder tick.

1. Create free account at [cron-job.org](https://cron-job.org)
2. **Cronjobs → Create cronjob**:
   - Title: `manage-family tick`
   - URL: `https://your-vercel-domain.vercel.app/api/v1/jobs/tick`
   - Schedule: Every 5 minutes (`*/5 * * * *`)
   - Method: `GET`
   - **Headers → Add**: `X-Scheduler-Secret: <SCHEDULER_SECRET value>`
3. Save and enable

---

## 5. Post-Deploy Checklist

- [ ] Visit app URL — magic link login works end-to-end
- [ ] Check Supabase Auth → Users — new user created after first login
- [ ] `/api/v1/health` (or any API route) returns 200
- [ ] Supabase Dashboard → Realtime → Logs — shopping list events appear on item check
- [ ] cron-job.org job status shows successful execution after first run
- [ ] Subscribe iCal feed in Google Calendar / Outlook — events appear within 15 min

---

## Environment Variable Reference

| Variable | Used By | Secret? | Example |
|----------|---------|---------|---------|
| `DATABASE_POOL_URL` | API | Yes | `postgresql://postgres.[ref]:pass@pooler.supabase.com:6543/postgres` |
| `DATABASE_URL` | Migrations only | Yes | `postgresql://postgres:pass@db.[ref].supabase.co:5432/postgres` |
| `SUPABASE_URL` | API + Web | No | `https://[ref].supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | API only | Yes | `eyJ...` |
| `SUPABASE_JWT_SECRET` | API only | Yes | `your-jwt-secret` |
| `SCHEDULER_SECRET` | API + cron-job.org | Yes | `openssl rand -hex 32` |
| `APP_TIMEZONE` | API | No | `America/Bogota` |
| `NEXT_PUBLIC_SUPABASE_URL` | Web (browser) | No | `https://[ref].supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Web (browser) | No | `eyJ...` |
| `NEXT_PUBLIC_API_URL` | Web (browser) | No | `https://domain.vercel.app/api/v1` |
