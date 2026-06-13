-- Household Manager — complete database schema (single source of truth).
--
-- Apply it either way:
--   * Supabase dashboard → SQL Editor → paste this file → Run, or
--   * supabase CLI: `supabase db push` (this file lives in supabase/migrations/).
--
-- The script is idempotent: safe to re-run on a database where it already ran.
-- Schema changes are made by adding new timestamped .sql files to this directory.

create extension if not exists pgcrypto;

-- ============================================================================
-- Tables
-- ============================================================================

create table if not exists persons (
    id uuid primary key default gen_random_uuid(),
    email text not null unique,
    display_name text not null,
    ui_prefs jsonb not null default '{}',
    ical_secret uuid not null unique default gen_random_uuid(),
    created_at timestamptz not null default now()
);

create table if not exists groups (
    id uuid primary key default gen_random_uuid(),
    parent_group_id uuid references groups(id) on delete cascade,
    name text not null,
    depth smallint not null default 0 check (depth between 0 and 4),
    created_at timestamptz not null default now()
);

create table if not exists memberships (
    id uuid primary key default gen_random_uuid(),
    person_id uuid not null references persons(id) on delete cascade,
    group_id uuid not null references groups(id) on delete cascade,
    role text not null check (role in ('owner', 'member')),
    joined_at timestamptz not null default now(),
    unique (person_id, group_id)
);

create table if not exists invites (
    id uuid primary key default gen_random_uuid(),
    group_id uuid not null references groups(id) on delete cascade,
    created_by uuid not null references persons(id) on delete cascade,
    token text not null unique default encode(gen_random_bytes(32), 'hex'),
    expires_at timestamptz,
    max_uses integer check (max_uses > 0),
    uses integer not null default 0,
    created_at timestamptz not null default now()
);

create table if not exists tasks (
    id uuid primary key default gen_random_uuid(),
    group_id uuid not null references groups(id) on delete cascade,
    assignee_id uuid references persons(id) on delete set null,
    title text not null,
    rrule text,
    done boolean not null default false,
    due_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists shopping_items (
    id uuid primary key default gen_random_uuid(),
    group_id uuid not null references groups(id) on delete cascade,
    name text not null,
    checked boolean not null default false,
    updated_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create table if not exists events (
    id uuid primary key default gen_random_uuid(),
    group_id uuid not null references groups(id) on delete cascade,
    title text not null,
    starts_at timestamptz not null,
    rrule text,
    created_at timestamptz not null default now()
);

create table if not exists reminders (
    id uuid primary key default gen_random_uuid(),
    person_id uuid not null references persons(id) on delete cascade,
    title text not null,
    fire_at timestamptz not null,
    delivered boolean not null default false,
    created_at timestamptz not null default now()
);

-- Food inventory (revision 0002)

create table if not exists canonical_products (
    id uuid primary key default gen_random_uuid(),
    group_id uuid not null references groups(id) on delete cascade,
    name text not null,
    category text not null,
    is_staple boolean not null default false,
    usual_location text not null
        check (usual_location in ('fridge','freezer','pantry','other')),
    expiry_days_default integer check (expiry_days_default > 0)
);

create table if not exists product_cache (
    barcode text primary key,
    canonical_product_id uuid references canonical_products(id),
    source text not null check (source in ('off','ah','jumbo','manual')),
    name text not null,
    brand text,
    category text,
    raw_data jsonb not null default '{}',
    cached_at timestamptz not null default now()
);

create table if not exists inventory_items (
    id uuid primary key default gen_random_uuid(),
    group_id uuid not null references groups(id) on delete cascade,
    canonical_product_id uuid not null references canonical_products(id),
    barcode text references product_cache(barcode),
    name text not null,
    location text not null check (location in ('fridge','freezer','pantry','other')),
    status text not null default 'ok' check (status in ('ok','low','out')),
    expiry_date date,
    added_by uuid not null references persons(id),
    added_at timestamptz not null default now(),
    removed_at timestamptz,
    removed_reason text check (removed_reason in ('used','thrown','transferred'))
);

alter table shopping_items
    add column if not exists canonical_product_id uuid references canonical_products(id);

-- ============================================================================
-- Indexes
-- ============================================================================

create index if not exists idx_memberships_person_id on memberships(person_id);
create index if not exists idx_memberships_group_id on memberships(group_id);
create index if not exists idx_tasks_group_done_due on tasks(group_id, done, due_at);
create index if not exists idx_shopping_items_group_id on shopping_items(group_id);
create index if not exists idx_events_group_starts on events(group_id, starts_at);
create index if not exists idx_reminders_person_delivered_fire
    on reminders(person_id, delivered, fire_at);
create index if not exists idx_invites_token on invites(token);
create index if not exists idx_inventory_items_group_active
    on inventory_items(group_id, location) where removed_at is null;
create index if not exists idx_inventory_items_expiry
    on inventory_items(group_id, expiry_date)
    where removed_at is null and expiry_date is not null;
create index if not exists idx_shopping_items_canonical
    on shopping_items(group_id, canonical_product_id)
    where checked = false and canonical_product_id is not null;
create index if not exists idx_canonical_products_group on canonical_products(group_id);

-- ============================================================================
-- Triggers & functions
-- ============================================================================

create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists tasks_set_updated_at on tasks;
create trigger tasks_set_updated_at
    before update on tasks
    for each row execute function set_updated_at();

drop trigger if exists shopping_items_set_updated_at on shopping_items;
create trigger shopping_items_set_updated_at
    before update on shopping_items
    for each row execute function set_updated_at();

-- Recursive group rollup used by the events RLS policy.
create or replace function person_reachable_groups(p_id uuid)
returns table(id uuid) as $$
  with recursive tree as (
    select g.id, g.parent_group_id
    from groups g
    join memberships m on m.group_id = g.id and m.person_id = p_id
    union all
    select g.id, g.parent_group_id
    from groups g
    join tree t on g.id = t.parent_group_id
  )
  select tree.id from tree;
$$ language sql stable security definer;

-- ============================================================================
-- Row Level Security
-- (The FastAPI service connects as the table owner and is not constrained by
-- these policies; they protect direct access via Supabase Realtime/PostgREST.)
-- ============================================================================

alter table persons enable row level security;
alter table groups enable row level security;
alter table memberships enable row level security;
alter table invites enable row level security;
alter table tasks enable row level security;
alter table shopping_items enable row level security;
alter table events enable row level security;
alter table reminders enable row level security;
alter table canonical_products enable row level security;
alter table product_cache enable row level security;
alter table inventory_items enable row level security;

drop policy if exists persons_select_own on persons;
create policy persons_select_own on persons for select
    using (id = auth.uid());

drop policy if exists persons_update_own on persons;
create policy persons_update_own on persons for update
    using (id = auth.uid());

drop policy if exists groups_select_member on groups;
create policy groups_select_member on groups for select
    using (
        exists (
            select 1 from memberships m
            where m.group_id = id and m.person_id = auth.uid()
        )
    );

drop policy if exists groups_insert_authenticated on groups;
create policy groups_insert_authenticated on groups for insert
    with check (auth.uid() is not null);

drop policy if exists memberships_select on memberships;
create policy memberships_select on memberships for select
    using (
        person_id = auth.uid()
        or exists (
            select 1 from memberships m2
            where m2.group_id = group_id and m2.person_id = auth.uid()
        )
    );

drop policy if exists memberships_insert_authenticated on memberships;
create policy memberships_insert_authenticated on memberships for insert
    with check (auth.uid() is not null);

drop policy if exists memberships_update_own on memberships;
create policy memberships_update_own on memberships for update
    using (person_id = auth.uid());

drop policy if exists memberships_delete_own on memberships;
create policy memberships_delete_own on memberships for delete
    using (person_id = auth.uid());

drop policy if exists invites_select_owner on invites;
create policy invites_select_owner on invites for select
    using (
        exists (
            select 1 from memberships m
            where m.group_id = group_id and m.person_id = auth.uid() and m.role = 'owner'
        )
    );

drop policy if exists invites_insert_owner on invites;
create policy invites_insert_owner on invites for insert
    with check (
        exists (
            select 1 from memberships m
            where m.group_id = group_id and m.person_id = auth.uid() and m.role = 'owner'
        )
    );

drop policy if exists tasks_member on tasks;
create policy tasks_member on tasks for all
    using (
        exists (
            select 1 from memberships m
            where m.group_id = group_id and m.person_id = auth.uid()
        )
    );

drop policy if exists shopping_items_member on shopping_items;
create policy shopping_items_member on shopping_items for all
    using (
        exists (
            select 1 from memberships m
            where m.group_id = group_id and m.person_id = auth.uid()
        )
    );

drop policy if exists events_select_reachable on events;
create policy events_select_reachable on events for select
    using (group_id in (select id from person_reachable_groups(auth.uid())));

drop policy if exists events_write_member on events;
create policy events_write_member on events for insert
    with check (
        exists (
            select 1 from memberships m
            where m.group_id = group_id and m.person_id = auth.uid()
        )
    );

drop policy if exists events_update_member on events;
create policy events_update_member on events for update
    using (
        exists (
            select 1 from memberships m
            where m.group_id = group_id and m.person_id = auth.uid()
        )
    );

drop policy if exists events_delete_member on events;
create policy events_delete_member on events for delete
    using (
        exists (
            select 1 from memberships m
            where m.group_id = group_id and m.person_id = auth.uid()
        )
    );

drop policy if exists reminders_own on reminders;
create policy reminders_own on reminders for all
    using (person_id = auth.uid());

drop policy if exists canonical_products_group_member on canonical_products;
create policy canonical_products_group_member on canonical_products for all
    using (
        exists (
            select 1 from memberships
            where memberships.group_id = canonical_products.group_id
              and memberships.person_id = auth.uid()
        )
    );

drop policy if exists inventory_items_group_member on inventory_items;
create policy inventory_items_group_member on inventory_items for all
    using (
        exists (
            select 1 from memberships
            where memberships.group_id = inventory_items.group_id
              and memberships.person_id = auth.uid()
        )
    );

drop policy if exists product_cache_read on product_cache;
create policy product_cache_read on product_cache for select
    using (auth.uid() is not null);
