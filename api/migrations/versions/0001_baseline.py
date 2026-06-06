"""Baseline: create all 8 tables, indexes, triggers, RLS policies, person_reachable_groups.

Revision ID: 0001
Revises:
Create Date: 2026-06-03
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            ui_prefs JSONB NOT NULL DEFAULT '{}',
            ical_secret UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            parent_group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            depth SMALLINT NOT NULL DEFAULT 0 CHECK (depth BETWEEN 0 AND 4),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS memberships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
            group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('owner', 'member')),
            joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (person_id, group_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS invites (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            created_by UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
            token TEXT NOT NULL UNIQUE DEFAULT encode(gen_random_bytes(32), 'hex'),
            expires_at TIMESTAMPTZ,
            max_uses INTEGER CHECK (max_uses > 0),
            uses INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            assignee_id UUID REFERENCES persons(id) ON DELETE SET NULL,
            title TEXT NOT NULL,
            rrule TEXT,
            done BOOLEAN NOT NULL DEFAULT FALSE,
            due_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS shopping_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            checked BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            starts_at TIMESTAMPTZ NOT NULL,
            rrule TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            fire_at TIMESTAMPTZ NOT NULL,
            delivered BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # Indexes per data-model.md §Key indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_memberships_person_id ON memberships(person_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_memberships_group_id ON memberships(group_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_group_done_due ON tasks(group_id, done, due_at)"
    )  # noqa: E501
    op.execute("CREATE INDEX IF NOT EXISTS idx_shopping_items_group_id ON shopping_items(group_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_group_starts ON events(group_id, starts_at)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reminders_person_delivered_fire ON reminders(person_id, delivered, fire_at)"
    )  # noqa: E501
    op.execute("CREATE INDEX IF NOT EXISTS idx_invites_token ON invites(token)")

    # updated_at auto-trigger for tasks and shopping_items
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER tasks_set_updated_at
        BEFORE UPDATE ON tasks
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    op.execute("""
        CREATE TRIGGER shopping_items_set_updated_at
        BEFORE UPDATE ON shopping_items
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # person_reachable_groups — recursive CTE function for event RLS rollup
    op.execute("""
        CREATE OR REPLACE FUNCTION person_reachable_groups(p_id UUID)
        RETURNS TABLE(id UUID) AS $$
          WITH RECURSIVE tree AS (
            SELECT g.id, g.parent_group_id
            FROM groups g
            JOIN memberships m ON m.group_id = g.id AND m.person_id = p_id
            UNION ALL
            SELECT g.id, g.parent_group_id
            FROM groups g
            JOIN tree t ON g.id = t.parent_group_id
          )
          SELECT tree.id FROM tree;
        $$ LANGUAGE sql STABLE SECURITY DEFINER
    """)

    # Enable Row Level Security on all tables
    for table in (
        "persons",
        "groups",
        "memberships",
        "invites",
        "tasks",
        "shopping_items",
        "events",
        "reminders",
    ):  # noqa: E501
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    # RLS policies per data-model.md §RLS Policy Summary

    # persons: SELECT/UPDATE own row
    op.execute("""
        CREATE POLICY persons_select_own ON persons FOR SELECT
        USING (id = auth.uid())
    """)
    op.execute("""
        CREATE POLICY persons_update_own ON persons FOR UPDATE
        USING (id = auth.uid())
    """)

    # groups: SELECT for members, INSERT for authenticated users
    op.execute("""
        CREATE POLICY groups_select_member ON groups FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.group_id = id AND m.person_id = auth.uid()
            )
        )
    """)
    op.execute("""
        CREATE POLICY groups_insert_authenticated ON groups FOR INSERT
        WITH CHECK (auth.uid() IS NOT NULL)
    """)

    # memberships: SELECT own rows OR rows in groups user belongs to
    op.execute("""
        CREATE POLICY memberships_select ON memberships FOR SELECT
        USING (
            person_id = auth.uid()
            OR EXISTS (
                SELECT 1 FROM memberships m2
                WHERE m2.group_id = group_id AND m2.person_id = auth.uid()
            )
        )
    """)
    op.execute("""
        CREATE POLICY memberships_insert_authenticated ON memberships FOR INSERT
        WITH CHECK (auth.uid() IS NOT NULL)
    """)
    op.execute("""
        CREATE POLICY memberships_update_own ON memberships FOR UPDATE
        USING (person_id = auth.uid())
    """)
    op.execute("""
        CREATE POLICY memberships_delete_own ON memberships FOR DELETE
        USING (person_id = auth.uid())
    """)

    # invites: SELECT/INSERT owner of referenced group
    op.execute("""
        CREATE POLICY invites_select_owner ON invites FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.group_id = group_id AND m.person_id = auth.uid() AND m.role = 'owner'
            )
        )
    """)
    op.execute("""
        CREATE POLICY invites_insert_owner ON invites FOR INSERT
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.group_id = group_id AND m.person_id = auth.uid() AND m.role = 'owner'
            )
        )
    """)

    # tasks: ALL for group members
    op.execute("""
        CREATE POLICY tasks_member ON tasks FOR ALL
        USING (
            EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.group_id = group_id AND m.person_id = auth.uid()
            )
        )
    """)

    # shopping_items: ALL for group members
    op.execute("""
        CREATE POLICY shopping_items_member ON shopping_items FOR ALL
        USING (
            EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.group_id = group_id AND m.person_id = auth.uid()
            )
        )
    """)

    # events: SELECT via person_reachable_groups rollup; INSERT/UPDATE/DELETE for direct members
    op.execute("""
        CREATE POLICY events_select_reachable ON events FOR SELECT
        USING (
            group_id IN (SELECT id FROM person_reachable_groups(auth.uid()))
        )
    """)
    op.execute("""
        CREATE POLICY events_write_member ON events FOR INSERT
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.group_id = group_id AND m.person_id = auth.uid()
            )
        )
    """)
    op.execute("""
        CREATE POLICY events_update_member ON events FOR UPDATE
        USING (
            EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.group_id = group_id AND m.person_id = auth.uid()
            )
        )
    """)
    op.execute("""
        CREATE POLICY events_delete_member ON events FOR DELETE
        USING (
            EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.group_id = group_id AND m.person_id = auth.uid()
            )
        )
    """)

    # reminders: ALL for own person
    op.execute("""
        CREATE POLICY reminders_own ON reminders FOR ALL
        USING (person_id = auth.uid())
    """)


def downgrade() -> None:
    for table in (
        "persons",
        "groups",
        "memberships",
        "invites",
        "tasks",
        "shopping_items",
        "events",
        "reminders",
    ):  # noqa: E501
        op.execute(f"DROP POLICY IF EXISTS {table}_select_own ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP FUNCTION IF EXISTS person_reachable_groups(UUID)")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")

    for table in (
        "reminders",
        "events",
        "shopping_items",
        "tasks",
        "invites",
        "memberships",
        "groups",
        "persons",
    ):  # noqa: E501
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
